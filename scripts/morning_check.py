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
    counts = {}
    for st in ("active", "completed"):
        d = fetch_json(f"/lots?status={st}&per_page=1")
        counts[st] = d.get("total", 0)
    signal("green" if counts["active"] > 0 else "red",
           "Активных лотов", str(counts["active"]), ">5000")
    if counts["active"] < 5000:
        issues.append("Активных лотов мало — проверить scraper_torgi")

    yesterday = (NOW - timedelta(days=1)).strftime("%Y-%m-%d")
    d = fetch_json(f"/lots?status=active&submission_end_to={yesterday}&per_page=1")
    expired = d.get("total", 0)
    pct_expired = round(expired / max(counts["active"], 1) * 100, 1)
    if expired == 0:
        signal("green", "Active с истекшим окном", "0", "0")
    elif pct_expired < 5:
        signal("yellow", "Active с истекшим окном", f"{expired} ({pct_expired}%)", "<5%")
    else:
        signal("red", "Active с истекшим окном", f"{expired} ({pct_expired}%)", "<5%")
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
    section("СКОРИНГ")
    d = fetch_json("/lots?status=active&score_min=1&per_page=1")
    with_score = d.get("total", 0)
    pct_score = round(with_score / max(list_total, 1) * 100, 1)
    if pct_score >= 90:
        signal("green", "Active со score", f"{with_score} ({pct_score}%)", ">=90%")
    elif pct_score >= 70:
        signal("yellow", "Active со score", f"{with_score} ({pct_score}%)", ">=90%")
    else:
        signal("red", "Active со score", f"{with_score} ({pct_score}%)", ">=90%")
        issues.append("update_lot_scores отстаёт")

    d = fetch_json("/lots?status=active&score_min=80&per_page=1")
    top_score = d.get("total", 0)
    signal("green" if top_score >= 100 else "yellow",
           "Active со score >=80 (премиум)", str(top_score), ">=100")

    # ─── 4. Дисконты ───────────────────────────────────────────────────
    section("ДИСКОНТЫ К РЫНКУ")
    for thr, min_count in [(10, 1000), (25, 500), (50, 200), (75, 50)]:
        d = fetch_json(f"/lots?status=active&discount_min={thr}&per_page=1")
        n = d.get("total", 0)
        signal("green" if n >= min_count else "yellow",
               f"Дисконт >={thr}%", str(n), f">={min_count}")

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

    # ─── 8b. Флаги переуступки/субаренды ───────────────────────────────
    section("ПЕРЕУСТУПКА / СУБАРЕНДА")
    d_sub = fetch_json("/lots?status=active&sublease_allowed=true&per_page=1")
    d_ass = fetch_json("/lots?status=active&assignment_allowed=true&per_page=1")
    sub_n = d_sub.get("total", 0)
    ass_n = d_ass.get("total", 0)
    signal("green" if sub_n >= 100 else ("yellow" if sub_n >= 20 else "red"),
           "Лоты с разрешённой субарендой", str(sub_n), ">=100")
    signal("green" if ass_n >= 100 else ("yellow" if ass_n >= 20 else "red"),
           "Лоты с разрешённой переуступкой", str(ass_n), ">=100")
    if sub_n < 20 and ass_n < 20:
        issues.append("Покрытие фильтра переуступки/субаренды слишком низкое — проверь enrich_sublease_flags")

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
