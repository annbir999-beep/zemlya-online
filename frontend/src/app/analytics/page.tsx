"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

interface Summary {
  total_active: number;
  new_24h: number;
  avg_price_per_sqm: number | null;
  avg_discount_pct: number | null;
  pdf_parsed: number;
  ai_analyzed: number;
}

interface RegionStat {
  code: string | null;
  name: string | null;
  count: number;
  avg_price_per_sqm: number | null;
}

interface PurposeStat {
  key: string;
  label: string;
  count: number;
}

interface ScoreBucket {
  label: string;
  count: number;
}

interface DailyPoint {
  date: string;
  count: number;
}

interface TopLot {
  id: number;
  title: string;
  region_name: string | null;
  score: number | null;
  discount_to_market_pct: number | null;
  start_price: number | null;
  area_sqm: number | null;
}

interface AnalyticsResponse {
  summary: Summary;
  by_region: RegionStat[];
  by_purpose: PurposeStat[];
  by_score: ScoreBucket[];
  daily_new: DailyPoint[];
  top_lots: TopLot[];
  generated_at: string;
}

const fmtN = (v: number | null | undefined) =>
  v == null ? "—" : Math.round(v).toLocaleString("ru");

const fmtArea = (v: number | null | undefined) => {
  if (v == null) return "—";
  return v >= 10000 ? `${(v / 10000).toFixed(1)} га` : `${Math.round(v).toLocaleString("ru")} м²`;
};

export default function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<AnalyticsResponse>("/api/lots/analytics").then(setData).finally(() => setLoading(false));
  }, []);

  if (loading && !data) {
    return <div style={{ padding: 40, textAlign: "center", color: "var(--text-3)" }}>Загрузка статистики...</div>;
  }
  if (!data) return null;

  const { summary, by_region, by_purpose, by_score, daily_new, top_lots } = data;
  const maxRegion = Math.max(...by_region.map((r) => r.count), 1);
  const maxPurpose = Math.max(...by_purpose.map((p) => p.count), 1);
  const maxDaily = Math.max(...daily_new.map((d) => d.count), 1);

  return (
    <div style={{ flex: 1, overflow: "auto", padding: "32px 24px", maxWidth: 1100, margin: "0 auto", width: "100%" }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 6 }}>📊 Аналитика рынка</h1>
      <p style={{ color: "var(--text-3)", fontSize: 14, marginBottom: 24 }}>
        Срез активных земельных аукционов России. Обновляется каждые 5 минут.
      </p>

      {/* KPI cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12, marginBottom: 28 }}>
        <KpiCard label="Активных лотов" value={fmtN(summary.total_active)} />
        <KpiCard label="Новых за сутки" value={`+${fmtN(summary.new_24h)}`} accent />
        <KpiCard
          label="Средняя цена за м²"
          value={summary.avg_price_per_sqm ? `${fmtN(summary.avg_price_per_sqm)} ₽` : "—"}
        />
        <KpiCard
          label="Средний дисконт к рынку"
          value={summary.avg_discount_pct != null ? `${summary.avg_discount_pct.toFixed(1)}%` : "—"}
        />
        <KpiCard
          label="С распарсенным PDF"
          value={`${fmtN(summary.pdf_parsed)} / ${fmtN(summary.total_active)}`}
        />
        <KpiCard
          label="С ИИ-анализом"
          value={fmtN(summary.ai_analyzed)}
        />
      </div>

      {/* Top regions + purpose */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(420px, 1fr))", gap: 20, marginBottom: 28 }}>
        <Panel title="Топ регионов по числу лотов">
          {by_region.map((r) => (
            <BarRow
              key={r.code || r.name || ""}
              label={r.name || "—"}
              value={r.count}
              max={maxRegion}
              right={
                r.avg_price_per_sqm
                  ? `~${fmtN(r.avg_price_per_sqm)} ₽/м²`
                  : undefined
              }
            />
          ))}
        </Panel>

        <Panel title="Назначение земли">
          {by_purpose.map((p) => (
            <BarRow key={p.key} label={p.label} value={p.count} max={maxPurpose} color="#0d9488" />
          ))}
        </Panel>
      </div>

      {/* Score distribution + daily new */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(420px, 1fr))", gap: 20, marginBottom: 28 }}>
        <Panel title="Распределение по рентабельности (score)">
          {by_score.map((b) => (
            <BarRow
              key={b.label}
              label={`Score ${b.label}`}
              value={b.count}
              max={Math.max(...by_score.map((x) => x.count), 1)}
              color={b.label === "90+" ? "#dc2626" : b.label === "70-89" ? "#ea580c" : "#0ea5e9"}
            />
          ))}
        </Panel>

        <Panel title="Новых лотов по дням (30 дней)">
          <div style={{ display: "flex", alignItems: "flex-end", height: 120, gap: 2, padding: "0 4px" }}>
            {daily_new.map((d) => (
              <div
                key={d.date}
                title={`${new Date(d.date).toLocaleDateString("ru")}: ${d.count}`}
                style={{
                  flex: 1,
                  height: `${(d.count / maxDaily) * 100}%`,
                  background: "linear-gradient(180deg, #16a34a 0%, #0d9488 100%)",
                  borderRadius: "3px 3px 0 0",
                  minHeight: 2,
                }}
              />
            ))}
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--text-3)", marginTop: 6 }}>
            <span>{daily_new[0]?.date && new Date(daily_new[0].date).toLocaleDateString("ru", { day: "numeric", month: "short" })}</span>
            <span>{daily_new.at(-1)?.date && new Date(daily_new.at(-1)!.date).toLocaleDateString("ru", { day: "numeric", month: "short" })}</span>
          </div>
        </Panel>
      </div>

      {/* Top lots */}
      <Panel title="Топ-5 лотов по рентабельности">
        <div style={{ display: "grid", gap: 8 }}>
          {top_lots.map((l) => (
            <Link
              key={l.id}
              href={`/lots/${l.id}`}
              style={{
                background: "var(--surface-2)", padding: 12, borderRadius: 8,
                textDecoration: "none", color: "inherit", display: "flex",
                gap: 12, alignItems: "center", flexWrap: "wrap",
              }}
            >
              <span className="badge" style={{ background: "linear-gradient(135deg,#dc2626,#ea580c)", color: "white", fontWeight: 700 }}>
                {l.score}
              </span>
              <div style={{ flex: 1, minWidth: 200 }}>
                <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 2 }}>{l.title || `Лот #${l.id}`}</div>
                <div style={{ fontSize: 12, color: "var(--text-3)" }}>
                  {l.region_name && <span>{l.region_name}</span>}
                  {l.area_sqm && <span>  ·  {fmtArea(l.area_sqm)}</span>}
                  {l.start_price && <span>  ·  {fmtN(l.start_price)} ₽</span>}
                </div>
              </div>
              {l.discount_to_market_pct != null && l.discount_to_market_pct > 0 && (
                <span className="badge badge-green">−{Math.round(l.discount_to_market_pct)}% к рынку</span>
              )}
            </Link>
          ))}
        </div>
      </Panel>

      <p style={{ fontSize: 11, color: "var(--text-3)", marginTop: 24, textAlign: "center" }}>
        Срез на {new Date(data.generated_at).toLocaleString("ru")}
      </p>
    </div>
  );
}

function KpiCard({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div
      style={{
        background: accent ? "linear-gradient(135deg, #16a34a 0%, #0d9488 100%)" : "var(--surface)",
        color: accent ? "white" : "inherit",
        border: accent ? "none" : "1px solid var(--border)",
        borderRadius: 10, padding: "14px 16px",
      }}
    >
      <div style={{ fontSize: 12, opacity: accent ? 0.85 : 0.6, marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, lineHeight: 1.1 }}>{value}</div>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: 18 }}>
      <h2 style={{ fontSize: 14, fontWeight: 600, marginBottom: 14 }}>{title}</h2>
      {children}
    </div>
  );
}

function BarRow({
  label, value, max, color = "#16a34a", right,
}: { label: string; value: number; max: number; color?: string; right?: string }) {
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 3 }}>
        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", paddingRight: 8 }}>
          {label}
        </span>
        <span style={{ color: "var(--text-3)", flexShrink: 0 }}>
          {value.toLocaleString("ru")}
          {right && <span style={{ marginLeft: 8, fontSize: 11 }}>· {right}</span>}
        </span>
      </div>
      <div style={{ height: 6, background: "var(--surface-2)", borderRadius: 3, overflow: "hidden" }}>
        <div
          style={{
            width: `${(value / max) * 100}%`,
            height: "100%",
            background: color,
            transition: "width .3s",
          }}
        />
      </div>
    </div>
  );
}
