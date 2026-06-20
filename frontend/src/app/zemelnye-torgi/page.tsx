import Link from "next/link";

export const metadata = {
  title: "Земельные торги по регионам России — Торги Земли",
  description: "Земельные аукционы torgi.gov по всем регионам РФ: количество активных участков, средний дисконт к рынку, AI-оценка. Выберите регион.",
};

export const revalidate = 600;

const BACKEND_URL = process.env.BACKEND_URL || "http://backend:8000";

type RegionItem = {
  slug: string;
  code: string;
  name: string;
  count: number;
  avg_discount_pct: number | null;
  avg_score: number | null;
  min_price: number | null;
};

async function fetchRegions(): Promise<RegionItem[]> {
  try {
    const res = await fetch(`${BACKEND_URL}/api/seo/regions`, { next: { revalidate: 600 } });
    if (!res.ok) return [];
    const data = await res.json();
    return data.items || [];
  } catch {
    return [];
  }
}

const fmtPrice = (n: number | null) =>
  n == null ? "—" : n >= 1_000_000 ? `${(n / 1_000_000).toFixed(1)} млн ₽` : `${Math.round(n / 1000)} тыс. ₽`;

export default async function RegionsIndex() {
  const regions = await fetchRegions();

  return (
    <div style={{ flex: 1, overflow: "auto", padding: "32px 20px", maxWidth: 1000, margin: "0 auto", width: "100%" }}>
      <h1 style={{ fontSize: 30, fontWeight: 700, marginBottom: 8 }}>Земельные торги по регионам России</h1>
      <p style={{ color: "var(--text-3)", fontSize: 15, lineHeight: 1.5, marginBottom: 24 }}>
        Активные земельные аукционы с torgi.gov по субъектам РФ. Для каждого региона — количество участков,
        средний дисконт к рынку и AI-оценка привлекательности. Выберите регион, чтобы посмотреть лучшие лоты.
      </p>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 12 }}>
        {regions.map((r) => (
          <Link key={r.slug} href={`/zemelnye-torgi/${r.slug}`} style={{
            background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12,
            padding: 16, textDecoration: "none", color: "inherit", display: "block",
          }}>
            <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 6 }}>{r.name}</div>
            <div style={{ fontSize: 13, color: "var(--text-3)" }}>
              {r.count} {r.count === 1 ? "участок" : "участков"}
              {r.avg_discount_pct ? ` · дисконт ~${r.avg_discount_pct}%` : ""}
            </div>
            <div style={{ fontSize: 12, color: "var(--text-3)", marginTop: 4 }}>
              от {fmtPrice(r.min_price)}
            </div>
          </Link>
        ))}
      </div>
      {regions.length === 0 && (
        <p style={{ color: "var(--text-3)" }}>Данные загружаются. Загляните чуть позже.</p>
      )}
    </div>
  );
}
