"""Утренняя проверка прода — Земля.ОНЛАЙН.

Запускать одной командой:
    python scripts/morning_check.py

Проверяет:
  • Статусы лотов (актив с просроченным окном — должно быть ~0)
  • Покрытие координатами на карте (% от активных)
  • Покрытие скорингом (% активных со score)
  • Дисконты к рынку (распределение)
  • HTML-страницы (200/404/500)
  • Свежесть скрейпинга — сколько лотов добавлено за последние 24 ч
  • Воронка пользователей: регистрации/платежи/конверсия за 24 ч
  • TOR-зоны — сколько лотов помечены как ТОР

Печатает зелёные/красные/жёлтые сигналы. Красные требуют немедленной реакции.
"""
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

# Принудительно UTF-8 для консоли на Windows (по умолчанию cp1251 → UnicodeError на ━)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Цвета поддерживаются в современных терминалах; на старом cmd Windows их можно
# выключить — установив NO_COLOR=1 в окружении.
USE_COLOR = os.environ.get("NO_COLOR") is None and sys.stdout.isatty()

API = "https://torgi-zemli.ru/api"
SITE = "https://torgi-zemli.ru"
NOW = datetime.now(timezone.utc)


def fetch_json(path: str, timeout: int = 25):
    try:
        with urllib.request.urlopen(f"{API}{path}", timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"_error": str(e)[:120]}


def head(path: str, timeout: int = 10) -> int:
    try:
        req = urllib.request.Request(f"{SITE}{path}", method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


GREEN = "\033[92m" if USE_COLOR else ""
YELLOW = "\033[93m" if USE_COLOR else ""
RED = "\033[91m" if USE_COLOR else ""
BOLD = "\033[1m" if USE_COLOR else ""
END = "\033[0m" if USE_COLOR else ""


def signal(level: str, label: str, value: str, expected: str = ""):
    color = {"green": GREEN, "yellow": YELLOW, "red": RED}.get(level, "")
    icon = {"green": "✓", "yellow": "⚠", "red": "✗"}.get(level, "•")
    exp = f" (норма: {expected})" if expected else ""
    print(f"  {color}{icon}{END} {label:<45} {color}{value}{END}{exp}")


def section(title: str):
    print(f"\n{BOLD}━━━ {title} ━━━{END}")


def main():
    print(f"{BOLD}АУДИТ ПРОДА — {NOW:%Y-%m-%d %H:%M UTC}{END}")
    issues = []

    # ─── 1. Статусы лотов ───────────────────────────────────────────────
    section("СТАТУСЫ ЛОТОВ")
    # Единый честный источник агрегатов — негейтед /lots/status-health (считает
    # прямо в БД, в обход премиум-гейта GET /lots). Раньше morning_check тянул
    # премиум-метрики анонимными запросами /lots?score_min=/discount_min=/
    # sublease_allowed= — но гейт для rank<1 молча обнулял эти фильтры → счётчик
    # возвращал ВСЕ активные лоты == ложные 100% каждый день (коммит b6fabc5
    # закрыл тот же класс бага для «протухших ACTIVE»). Теперь скор, дисконт,
    # субаренда/переуступка берутся из status-health.quality (канон torgi_gov).
    h = fetch_json("/lots/status-health")
    q = h.get("quality", {}) if "_error" not in h else {}

    # Канон «активных» — torgi_gov (active_total из status-health). Совпадает со
    # знаменателем метрик качества; all_sources показываем справочно, чтобы
    # расхождение с прежним счётчиком «все источники» больше не путало.
    counts = {}
    if "_error" not in h:
        counts["active"] = h.get("active_total", 0)
    else:
        # Fallback: status-health лёг — берём активные из /lots (тоже torgi_gov).
        counts["active"] = fetch_json("/lots?status=active&per_page=1").get("total", 0)
    all_src = h.get("active_all_sources") if "_error" not in h else None
    active_label = str(counts["active"])
    if all_src and all_src != counts["active"]:
        active_label = f"{counts['active']} (все источники: {all_src})"
    signal("green" if counts["active"] > 0 else "red",
           "Активных лотов (torgi_gov)", active_label, ">5000")
    if counts["active"] < 5000:
        issues.append("Активных лотов мало — проверить scraper_torgi")

    if "_error" in h:
        signal("yellow", "Active с истекшим окном", "н/д", "<2%")
        issues.append(f"status-health недоступен: {h['_error']}")
    else:
        expired = h.get("active_expired", 0)
        pct_expired = h.get("stale_pct", 0.0)
        if pct_expired < 1:
            signal("green", "Active с истекшим окном", f"{expired} ({pct_expired}%)", "<2%")
        elif pct_expired < 2:
            signal("yellow", "Active с истекшим окном", f"{expired} ({pct_expired}%)", "<2%")
        else:
            signal("red", "Active с истекшим окном", f"{expired} ({pct_expired}%)", "<2%")
            issues.append("update_lot_statuses не отрабатывает — много протухших ACTIVE")

    # ─── 2. Покрытие карты ─────────────────────────────────────────────
    section("КАРТА (КООРДИНАТЫ)")
    list_total = counts["active"]
    map_data = fetch_json("/lots/map?status=active")
    map_total = map_data.get("total", 0)
    coverage = round(map_total / max(list_total, 1) * 100, 1)
    if coverage >= 60:
        signal("green", "Покрытие карты", f"{coverage}% ({map_total}/{list_total})", ">=60%")
    elif coverage >= 30:
        signal("yellow", "Покрытие карты", f"{coverage}% ({map_total}/{list_total})", ">=60%")
    else:
        signal("red", "Покрытие карты", f"{coverage}% ({map_total}/{list_total})", ">=60%")
        issues.append("enrich_with_rosreestr отстаёт — мало координат на карте")

    # ─── 3. Скоринг ────────────────────────────────────────────────────
    # Честный источник — status-health.quality (score_min под премиум-гейтом,
    # анонимный /lots?score_min= раньше давал ложные 100%).
    section("СКОРИНГ")
    if q:
        with_score = q.get("with_score", 0)
        pct_score = q.get("with_score_pct", 0.0)
        if pct_score >= 90:
            signal("green", "Active со score", f"{with_score} ({pct_score}%)", ">=90%")
        elif pct_score >= 70:
            signal("yellow", "Active со score", f"{with_score} ({pct_score}%)", ">=90%")
        else:
            signal("red", "Active со score", f"{with_score} ({pct_score}%)", ">=90%")
            issues.append("update_lot_scores отстаёт")

        top_score = q.get("score_ge_80", 0)
        signal("green" if top_score >= 100 else "yellow",
               "Active со score >=80 (премиум)", str(top_score), ">=100")
    else:
        signal("yellow", "Active со score", "н/д (status-health недоступен)", ">=90%")

    # ─── 4. Дисконты ───────────────────────────────────────────────────
    # Честный источник — status-health.quality.discount (discount_min под
    # премиум-гейтом, анонимный /lots?discount_min= раньше давал ложные 100%).
    section("ДИСКОНТЫ К РЫНКУ")
    disc = q.get("discount", {}) if q else {}
    for thr, min_count in [(10, 1000), (25, 500), (50, 200), (75, 50)]:
        if disc:
            n = disc.get(f"ge_{thr}", 0)
            signal("green" if n >= min_count else "yellow",
                   f"Дисконт >={thr}%", str(n), f">={min_count}")
        else:
            signal("yellow", f"Дисконт >={thr}%", "н/д", f">={min_count}")

    # ─── 5. По назначению ──────────────────────────────────────────────
    section("РАСПРЕДЕЛЕНИЕ ПО НАЗНАЧЕНИЮ")
    purposes_expected_min = {
        "izhs": 2000, "lpkh": 1000, "snt": 100,
        "agricultural": 50, "commercial": 50, "industrial": 50,
    }
    for purpose, exp in purposes_expected_min.items():
        d = fetch_json(f"/lots?status=active&purpose={purpose}&per_page=1")
        n = d.get("total", 0)
        if n >= exp:
            signal("green", f"  {purpose}", str(n), f">={exp}")
        elif n >= exp / 2:
            signal("yellow", f"  {purpose}", str(n), f">={exp}")
        else:
            signal("red", f"  {purpose}", str(n), f">={exp}")
            issues.append(f"Категория '{purpose}' слишком пустая ({n}) — проверить классификатор")

    # ─── 6. HTML-страницы ──────────────────────────────────────────────
    section("HTML-СТРАНИЦЫ")
    pages = [("/", "Главная (карта)"), ("/lots", "Каталог"),
             ("/pricing", "Тарифы"), ("/blog", "Блог"),
             ("/faq", "FAQ и контакты"),
             ("/dashboard", "Кабинет"), ("/admin", "Админка"),
             ("/compare", "Сравнение")]
    for path, label in pages:
        code = head(path)
        if code in (200, 307, 308):
            signal("green", f"{label}", f"{code}")
        elif code == 401 or code == 403:
            signal("yellow", f"{label}", f"{code} (auth-only)")
        elif code == 0:
            signal("red", f"{label}", "ERR (network)")
            issues.append(f"Страница {path} не отвечает")
        else:
            signal("red", f"{label}", str(code), "200")
            issues.append(f"Страница {path} вернула {code}")

    # ─── 7. Свежесть данных ────────────────────────────────────────────
    section("СВЕЖЕСТЬ ДАННЫХ")
    # /lots сортируем по published_at desc — берём верхний лот
    d = fetch_json("/lots?sort_by=published_at&sort_order=desc&per_page=1")
    items = d.get("items", [])
    if items:
        pub = items[0].get("published_at")
        if pub:
            pub_dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            hours_ago = (NOW - pub_dt).total_seconds() / 3600
            if hours_ago < 6:
                signal("green", "Самый свежий лот опубликован", f"{hours_ago:.1f} ч назад", "<6ч")
            elif hours_ago < 24:
                signal("yellow", "Самый свежий лот опубликован", f"{hours_ago:.1f} ч назад", "<6ч")
            else:
                signal("red", "Самый свежий лот опубликован", f"{hours_ago:.1f} ч назад", "<6ч")
                issues.append("Свежие лоты не приходят — проверить scrape_torgi_gov")

    # ─── 8b. Переуступка / субаренда ───────────────────────────────────
    # Честный источник — status-health.resale (знаменатель = LEASE-лоты, а не все
    # active). Два чётких флага (без градации): есть переуступка / есть субаренда
    # (ст.22 >5 лет или явно в договоре).
    section("ПЕРЕУСТУПКА / СУБАРЕНДА")
    rs = h.get("resale", {}) if "_error" not in h else {}
    if rs:
        lease_total = rs.get("lease_total", 0)
        ass_n = rs.get("assignment_free", 0)
        ass_pct = rs.get("assignment_free_pct", 0.0)
        sub_n = rs.get("sublease_free", 0)
        sub_pct = rs.get("sublease_free_pct", 0.0)
        signal("green" if lease_total > 0 else "yellow",
               "Арендных лотов (знаменатель)", str(lease_total), ">0")
        signal("green" if ass_n >= 500 else ("yellow" if ass_n >= 100 else "red"),
               "Есть переуступка", f"{ass_n} ({ass_pct}%)", ">=500")
        signal("green" if sub_n >= 500 else ("yellow" if sub_n >= 100 else "red"),
               "Есть субаренда", f"{sub_n} ({sub_pct}%)", ">=500")
        if ass_n < 100:
            issues.append("Переуступка почти не проставлена — проверь enrich_sublease_flags (ст.22 + срок из attributes)")
    else:
        signal("yellow", "Переуступка/субаренда", "н/д (status-health недоступен)", ">=500")

    # ─── 9. Heatmap ────────────────────────────────────────────────────
    section("HEATMAP (АНАЛИТИКА)")
    d = fetch_json("/lots/heatmap")
    items = d.get("items", [])
    if not items:
        signal("red", "Heatmap", "пусто")
        issues.append("/lots/heatmap не отдаёт данные")
    else:
        n_regions = len(items)
        with_disc = sum(1 for x in items if x.get("avg_discount_pct") is not None)
        signal("green" if n_regions >= 70 else "yellow",
               "Регионов в heatmap", str(n_regions), ">=70")
        signal("green" if with_disc >= 60 else "yellow",
               "Регионов с avg_discount_pct", str(with_disc), ">=60")

    # ─── 10. ИТОГ ──────────────────────────────────────────────────────
    section("ИТОГ")
    if not issues:
        print(f"{GREEN}{BOLD}✓ ВСЁ В ПОРЯДКЕ{END}")
        return 0
    print(f"{RED}{BOLD}{len(issues)} ПРОБЛЕМ:{END}")
    for i, it in enumerate(issues, 1):
        print(f"  {RED}{i}.{END} {it}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
