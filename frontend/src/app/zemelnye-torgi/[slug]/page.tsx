import Link from "next/link";
import { notFound } from "next/navigation";

export const revalidate = 600;

const BACKEND_URL = process.env.BACKEND_URL || "http://backend:8000";

type TopLot = {
  id: number;
  title: string | null;
  start_price: number | null;
  area_sqm: number | null;
  land_purpose: string | null;
  score: number | null;
  discount_to_market_pct: number | null;
  submission_end: string | null;
};

type RegionData = {
  slug: string;
  code: string;
  name: string;
  count: number;
  avg_discount_pct: number | null;
  avg_score: number | null;
  min_price: number | null;
  top_lots: TopLot[];
  regional: Record<string, unknown>;
};

async function fetchRegion(slug: string): Promise<RegionData | null> {
  try {
    const res = await fetch(`${BACKEND_URL}/api/seo/regions/${encodeURIComponent(slug)}`, {
      next: { revalidate: 600 },
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

const PURPOSE: Record<string, string> = {
  izhs: "ИЖС", snt: "СНТ", lpkh: "ЛПХ", agricultural: "Сельхоз",
  commercial: "Коммерч.", industrial: "Промышл.", forest: "Лес", water: "Вода",
};
const fmtPrice = (n: number | null) =>
  n == null ? "—" : n >= 1_000_000 ? `${(n / 1_000_000).toFixed(2)} млн ₽` : `${Math.round(n / 1000)} тыс. ₽`;
const fmtArea = (n: number | null) =>
  n == null ? "—" : n >= 10000 ? `${(n / 10000).toFixed(2)} га` : `${Math.round(n)} м²`;

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const d = await fetchRegion(slug);
  if (!d) return { title: "Регион не найден — Торги Земли" };
  return {
    title: `Земельные торги в ${d.name} — ${d.count} участков с torgi.gov | Торги Земли`,
    description: `${d.count} активных земельных участков на аукционах в ${d.name}${d.avg_discount_pct ? `, средний дисконт ~${d.avg_discount_pct}% к рынку` : ""}. AI-оценка, фильтры, алерты. Найдите выгодный участок с торгов.`,
  };
}

export default async function RegionPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const d = await fetchRegion(slug);
  if (!d) notFound();

  return (
    <div style={{ flex: 1, overflow: "auto", padding: "32px 20px", maxWidth: 880, margin: "0 auto", width: "100%" }}>
      <Link href="/zemelnye-torgi" style={{ fontSize: 13, color: "var(--text-3)", textDecoration: "none" }}>
        ← Все регионы
      </Link>

      <h1 style={{ fontSize: 28, fontWeight: 700, margin: "14px 0 10px", lineHeight: 1.25 }}>
        Земельные торги в {d.name}
      </h1>

      <p style={{ fontSize: 15, color: "var(--text-2)", lineHeight: 1.6, marginBottom: 18 }}>
        Сейчас в {d.name} <b>{d.count}</b> активных земельных участков на аукционах с torgi.gov
        {d.avg_discount_pct ? <> со средним дисконтом <b>~{d.avg_discount_pct}%</b> к рыночной цене</> : null}
        {d.min_price ? <>, минимальная стартовая цена — от <b>{fmtPrice(d.min_price)}</b></> : null}.
        Каждый лот можно проверить AI-аудитом за 5 минут: ВРИ, обременения, риски договора и оценка ликвидности.
      </p>

      {/* Метрики */}
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 24 }}>
        {[
          { label: "Активных лотов", value: String(d.count) },
          { label: "Средний дисконт", value: d.avg_discount_pct ? `~${d.avg_discount_pct}%` : "—" },
          { label: "Средний AI-скор", value: d.avg_score != null ? String(d.avg_score) : "—" },
          { label: "Старт от", value: fmtPrice(d.min_price) },
        ].map((m) => (
          <div key={m.label} style={{
            background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 10,
            padding: "10px 16px", minWidth: 130,
          }}>
            <div style={{ fontSize: 20, fontWeight: 700, color: "var(--primary)" }}>{m.value}</div>
            <div style={{ fontSize: 12, color: "var(--text-3)" }}>{m.label}</div>
          </div>
        ))}
      </div>

      <h2 style={{ fontSize: 20, fontWeight: 600, marginBottom: 12 }}>Топ участков по AI-оценке</h2>
      <div style={{ display: "grid", gap: 10, marginBottom: 24 }}>
        {d.top_lots.map((l) => (
          <Link key={l.id} href={`/lots/${l.id}`} style={{
            background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 10,
            padding: 14, textDecoration: "none", color: "inherit",
            display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12,
          }}>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 14, fontWeight: 600 }}>
                {fmtPrice(l.start_price)}
                <span style={{ fontWeight: 400, color: "var(--text-3)" }}>
                  {" · "}{fmtArea(l.area_sqm)}{l.land_purpose && PURPOSE[l.land_purpose] ? ` · ${PURPOSE[l.land_purpose]}` : ""}
                </span>
              </div>
              {l.discount_to_market_pct ? (
                <div style={{ fontSize: 12, color: "#15803d", fontWeight: 600 }}>−{l.discount_to_market_pct}% к рынку</div>
              ) : null}
            </div>
            {l.score != null && (
              <div style={{
                flexShrink: 0, width: 38, height: 38, borderRadius: "50%",
                background: "var(--primary-light)", color: "var(--primary)",
                display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 800,
              }}>{l.score}</div>
            )}
          </Link>
        ))}
        {d.top_lots.length === 0 && (
          <p style={{ color: "var(--text-3)" }}>Активных лотов пока нет — загляните позже или настройте алерт.</p>
        )}
      </div>

      {/* CTA */}
      <div style={{
        background: "linear-gradient(135deg, #16a34a, #0d9488)", borderRadius: 14,
        padding: 24, color: "white", textAlign: "center",
      }}>
        <div style={{ fontSize: 19, fontWeight: 700, marginBottom: 6 }}>
          Не пропустите выгодный участок в {d.name}
        </div>
        <div style={{ fontSize: 14, opacity: 0.92, marginBottom: 16 }}>
          Настройте фильтр по региону — и получайте новые лоты в Telegram и на почту. Первый AI-аудит бесплатно.
        </div>
        <Link href={`/lots?region=${d.code}`} style={{
          display: "inline-block", background: "white", color: "#0d9488", fontWeight: 700,
          padding: "10px 24px", borderRadius: 10, textDecoration: "none", marginRight: 8,
        }}>
          Смотреть все лоты →
        </Link>
        <Link href="/register" style={{
          display: "inline-block", background: "rgba(255,255,255,0.18)", color: "white", fontWeight: 700,
          padding: "10px 24px", borderRadius: 10, textDecoration: "none",
        }}>
          Бесплатный аудит
        </Link>
      </div>
    </div>
  );
}
