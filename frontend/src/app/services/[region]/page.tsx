import Link from "next/link";
import { notFound } from "next/navigation";
import ServiceLeadForm from "@/components/ServiceLeadForm";
import { PRICE_SELECT, PRICE_TURNKEY_FROM, SUCCESS_FEE_PCT, money } from "@/lib/servicePricing";
import { regionIn } from "@/lib/regionCase";

/* Региональный лендинг услуги: /services/moskovskaya-oblast
 *
 * Под объявления на досках — человек приходит с запросом «участок в такой-то
 * области», и попадает на страницу про свою область, а не на общую.
 *
 * Страницы намеренно НЕ копии друг друга: цифры, топ-лоты и выводы у каждого
 * региона свои и обновляются вместе с базой. Копия с подменённым названием
 * области — это дорвей, за такое поисковики выбрасывают все страницы разом.
 */

// Тот же адрес, что у соседней страницы регионов: внутри docker бэкенд
// доступен по имени сервиса, наружу этот запрос не ходит
const BACKEND = process.env.BACKEND_URL || "http://backend:8000";

type Lot = { id: number; title?: string; start_price?: number; area_sqm?: number };
type Region = {
  slug: string; name: string; count: number;
  avg_discount_pct?: number; avg_score?: number; min_price?: number;
  top_lots?: Lot[];
};

async function fetchRegion(slug: string): Promise<Region | null> {
  try {
    const res = await fetch(`${BACKEND}/api/seo/regions/${encodeURIComponent(slug)}`, {
      next: { revalidate: 3600 },
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function generateMetadata({ params }: { params: Promise<{ region: string }> }) {
  const { region } = await params;
  const d = await fetchRegion(region);
  if (!d) return { title: "Подбор земельных участков на торгах" };
  return {
    title: `Купить землю на торгах в ${regionIn(d.name)} — подбор и сопровождение`,
    description: `Сейчас в регионе ${d.count} действующих земельных аукционов. ` +
      `Подберём участок под вашу задачу, проверим по кадастру и проведём торги. ` +
      `Подбор от ${money(PRICE_SELECT)}.`,
  };
}

const card: React.CSSProperties = {
  background: "var(--surface)", border: "1px solid var(--border)",
  borderRadius: 14, padding: 24,
};

export default async function RegionServicePage({ params }: { params: Promise<{ region: string }> }) {
  const { region } = await params;
  const d = await fetchRegion(region);
  if (!d) notFound();

  const discount = d.avg_discount_pct ?? 0;
  const lots = (d.top_lots || []).slice(0, 3);

  return (
    <div style={{ flex: 1, overflow: "auto" }}>
      <div style={{ maxWidth: 900, margin: "0 auto", padding: "40px 20px 80px" }}>

        <h1 style={{ fontSize: 32, fontWeight: 800, lineHeight: 1.25, marginBottom: 14 }}>
          Подберём участок на торгах в{" "}
          <span style={{ color: "var(--primary)" }}>{regionIn(d.name)}</span> — и доведём до договора
        </h1>

        <p style={{ fontSize: 17, color: "var(--text-2)", lineHeight: 1.65, marginBottom: 28 }}>
          Государство продаёт землю через аукционы: часто это дешевле рынка в разы.
          Но найти нужный участок среди тысяч извещений и не ошибиться с проверкой —
          отдельная работа. Её берём на себя.
        </p>

        {/* Живые цифры — главный аргумент и то, что нельзя подделать */}
        <div style={{ ...card, marginBottom: 28 }}>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 28 }}>
            <div>
              <div style={{ fontSize: 30, fontWeight: 800, color: "var(--primary)" }}>{d.count}</div>
              <div style={{ fontSize: 13.5, color: "var(--text-2)" }}>действующих аукционов сейчас</div>
            </div>
            {discount > 0 && (
              <div>
                <div style={{ fontSize: 30, fontWeight: 800, color: "var(--primary)" }}>{discount}%</div>
                <div style={{ fontSize: 13.5, color: "var(--text-2)" }}>средняя скидка к рынку</div>
              </div>
            )}
            {d.min_price ? (
              <div>
                <div style={{ fontSize: 30, fontWeight: 800, color: "var(--primary)" }}>
                  {Math.round(d.min_price).toLocaleString("ru-RU")} ₽
                </div>
                <div style={{ fontSize: 13.5, color: "var(--text-2)" }}>стартовая цена самого доступного</div>
              </div>
            ) : null}
          </div>
          <div style={{ fontSize: 13, color: "var(--text-2)", marginTop: 14, lineHeight: 1.5 }}>
            Цифры живые: обновляются вместе с базой аукционов каждые два часа.
            Скидка считается сравнением стартовой цены за метр с медианой предложений
            в том же регионе — методику показываем целиком, без «до 90%».
          </div>
        </div>

        {/* Что именно делаю */}
        <h2 style={{ fontSize: 23, fontWeight: 700, margin: "34px 0 14px" }}>Как это работает</h2>
        <ol style={{ paddingLeft: 22, lineHeight: 1.7, fontSize: 16, color: "var(--text)" }}>
          <li><b>Разбираем задачу.</b> Под что участок, какой район, площадь, потолок бюджета.</li>
          <li><b>Подбираем варианты.</b> Из всех действующих аукционов региона — те, что подходят,
            с расчётом скидки к рынку и оценкой ликвидности.</li>
          <li><b>Проверяем каждый.</b> Кадастр, вид разрешённого использования, обременения,
            охранные зоны, условия договора: срок аренды, переуступка, субаренда.</li>
          <li><b>Сопровождаем торги.</b> Задаток, электронная подпись, аккредитация на площадке,
            стратегия ставок, подписание договора.</li>
        </ol>

        {/* Цены */}
        <h2 style={{ fontSize: 23, fontWeight: 700, margin: "34px 0 14px" }}>Сколько стоит</h2>
        <div style={{ display: "grid", gap: 16, gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))" }}>
          <div style={card}>
            <div style={{ fontWeight: 700, fontSize: 18, marginBottom: 6 }}>Подбор</div>
            <div style={{ fontSize: 26, fontWeight: 800, color: "var(--primary)", marginBottom: 10 }}>
              {money(PRICE_SELECT)}
            </div>
            <div style={{ color: "var(--text-2)", lineHeight: 1.6, fontSize: 15 }}>
              Пять проверенных участков под вашу задачу: расчёт скидки к рынку, проверка
              по кадастру, сроки подачи заявок. Дальше решаете сами — участвовать или нет.
            </div>
          </div>
          <div style={{ ...card, borderColor: "var(--primary)" }}>
            <div style={{ fontWeight: 700, fontSize: 18, marginBottom: 6 }}>Под ключ</div>
            <div style={{ fontSize: 26, fontWeight: 800, color: "var(--primary)", marginBottom: 10 }}>
              от {money(PRICE_TURNKEY_FROM)}
            </div>
            <div style={{ color: "var(--text-2)", lineHeight: 1.6, fontSize: 15 }}>
              Всё то же плюс электронная подпись, аккредитация, участие в торгах и договор.
              Сверху {SUCCESS_FEE_PCT}% от подтверждённой экономии к рыночной цене.
              Не выиграли торги — половину фикса возвращаем.
            </div>
          </div>
        </div>

        {/* Примеры лотов — доказательство, что база живая */}
        {lots.length > 0 && (
          <>
            <h2 style={{ fontSize: 23, fontWeight: 700, margin: "34px 0 14px" }}>
              Что сейчас на торгах в регионе
            </h2>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {lots.map(l => (
                <Link key={l.id} href={`/lots/${l.id}`} style={{ ...card, padding: 16, textDecoration: "none", color: "inherit" }}>
                  <div style={{ fontWeight: 600, marginBottom: 4 }}>{(l.title || "Земельный участок").slice(0, 110)}</div>
                  <div style={{ color: "var(--text-2)", fontSize: 14 }}>
                    {l.start_price ? `Старт ${Math.round(l.start_price).toLocaleString("ru-RU")} ₽` : ""}
                    {l.area_sqm ? ` · ${Math.round(l.area_sqm / 100)} соток` : ""}
                  </div>
                </Link>
              ))}
            </div>
            <div style={{ marginTop: 12 }}>
              <Link href={`/zemelnye-torgi/${d.slug}`} style={{ color: "var(--primary)" }}>
                Посмотреть все аукционы региона на карте →
              </Link>
            </div>
          </>
        )}

        <div style={{ marginTop: 36 }}>
          <ServiceLeadForm
            defaultPackage="select"
            regionName={d.name}
            title={`Заявка на подбор — ${d.name}`}
          />
        </div>

        <p style={{ fontSize: 13.5, color: "var(--text-2)", marginTop: 22, lineHeight: 1.6 }}>
          «Торги Земли» — сервис по земельным аукционам РФ. Работаем по договору,
          заявки на электронных площадках подаём сами. Исполнитель — ИП Бирюкова А. И.,
          реквизиты и условия в оферте.
        </p>
      </div>
    </div>
  );
}
