"use client";
import { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

// ─── Types ────────────────────────────────────────────────────────────────────

interface LotFull {
  id: number;
  title: string;
  cadastral_number?: string;
  start_price?: number;
  cadastral_cost?: number;
  pct_price_to_cadastral?: number;
  area_sqm?: number;
  area_sqm_kn?: number;
  area_discrepancy?: string;
  land_purpose?: string;
  auction_type?: string;
  auction_form?: string;
  deal_type?: string;
  status: string;
  region_name?: string;
  address?: string;
  auction_end_date?: string;
  submission_start?: string;
  submission_end?: string;
  deposit?: number;
  deposit_pct?: number;
  etp?: string;
  resale_type?: string;
  notice_number?: string;
  source: string;
  lot_url?: string;
  rubric_tg?: number;
  rubric_kn?: number;
  category_tg?: string;
  vri_tg?: string;
  category_kn?: string;
  vri_kn?: string;
}

// ─── Formatters ───────────────────────────────────────────────────────────────

function fmtPrice(n?: number | null) {
  if (!n) return "—";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)} млн ₽`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)} тыс. ₽`;
  return `${n} ₽`;
}
function fmtArea(sqm?: number | null) {
  if (!sqm) return "—";
  if (sqm >= 10_000) return `${(sqm / 10_000).toFixed(4)} га`;
  return `${sqm.toLocaleString("ru")} м²`;
}
function fmtDate(iso?: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("ru", { day: "2-digit", month: "2-digit", year: "2-digit" });
}
function fmtPct(n?: number | null) {
  if (n == null) return "—";
  return `${n.toFixed(1)}%`;
}

const PURPOSE_LABEL: Record<string, string> = {
  izhs: "ИЖС", snt: "СНТ", lpkh: "ЛПХ", agricultural: "Сельхоз",
  commercial: "Коммерция", industrial: "Промышленность",
  forest: "Лес", water: "Вода", special: "Спец.", other: "Иное",
};
const STATUS_LABEL: Record<string, string> = {
  active: "Активный", upcoming: "Скоро",
  completed: "Завершён", cancelled: "Отменён",
};
const RESALE_LABEL: Record<string, string> = {
  yes: "Можно", no: "Нельзя",
  with_notice: "Можно уведомив", with_approval: "Можно согласовав",
};
const DISCREPANCY_LABEL: Record<string, string> = {
  match: "Совпадает", minor: "< 10%", major: "> 10%", no_kn: "Нет данных",
};

// ─── Row definition ───────────────────────────────────────────────────────────

interface FieldDef {
  label: string;
  group?: string;
  get: (l: LotFull) => string | number | null | undefined;
  fmt?: (v: string | number | null | undefined) => string;
  highlight?: boolean; // highlight differences
}

const FIELDS: FieldDef[] = [
  // Идентификация
  { group: "Участок", label: "Статус", get: l => l.status, fmt: v => STATUS_LABEL[v as string] || String(v ?? "—"), highlight: true },
  { label: "Кадастровый номер", get: l => l.cadastral_number, fmt: v => v ? String(v) : "—" },
  { label: "Регион", get: l => l.region_name, fmt: v => v ? String(v) : "—", highlight: true },
  { label: "Адрес", get: l => l.address, fmt: v => v ? String(v) : "—" },
  { label: "Назначение", get: l => l.land_purpose ? (PURPOSE_LABEL[l.land_purpose] || l.land_purpose) : null, fmt: v => v ? String(v) : "—", highlight: true },
  { label: "Источник данных", get: l => l.source, fmt: v => v ? String(v) : "—" },
  // Цены
  { group: "Цена", label: "Начальная цена", get: l => l.start_price, fmt: v => fmtPrice(v as number), highlight: true },
  { label: "Кадастровая стоимость", get: l => l.cadastral_cost, fmt: v => fmtPrice(v as number), highlight: true },
  { label: "% НЦ / КС", get: l => l.pct_price_to_cadastral, fmt: v => fmtPct(v as number), highlight: true },
  { label: "Задаток", get: l => l.deposit, fmt: v => fmtPrice(v as number) },
  { label: "% задатка от НЦ", get: l => l.deposit_pct, fmt: v => fmtPct(v as number) },
  // Площадь
  { group: "Площадь", label: "Площадь [TG]", get: l => l.area_sqm, fmt: v => fmtArea(v as number), highlight: true },
  { label: "Площадь [КН]", get: l => l.area_sqm_kn, fmt: v => fmtArea(v as number), highlight: true },
  { label: "Расхождение площади", get: l => l.area_discrepancy, fmt: v => v ? (DISCREPANCY_LABEL[v as string] || String(v)) : "—" },
  // ВРИ
  { group: "Вид разреш. использ.", label: "Категория [TG]", get: l => l.category_tg, fmt: v => v ? String(v) : "—" },
  { label: "ВРИ [TG]", get: l => l.vri_tg, fmt: v => v ? String(v) : "—" },
  { label: "Категория [КН]", get: l => l.category_kn, fmt: v => v ? String(v) : "—" },
  { label: "ВРИ [КН]", get: l => l.vri_kn, fmt: v => v ? String(v) : "—" },
  // Торги
  { group: "Торги", label: "Вид торгов", get: l => l.auction_type, fmt: v => v ? String(v) : "—", highlight: true },
  { label: "Форма проведения", get: l => l.auction_form, fmt: v => v ? String(v) : "—" },
  { label: "Вид сделки", get: l => l.deal_type, fmt: v => v ? String(v) : "—", highlight: true },
  { label: "Переуступка", get: l => l.resale_type, fmt: v => v ? (RESALE_LABEL[v as string] || String(v)) : "—", highlight: true },
  { label: "ЭТП", get: l => l.etp, fmt: v => v ? String(v) : "—" },
  { label: "Номер извещения", get: l => l.notice_number, fmt: v => v ? String(v) : "—" },
  // Даты
  { group: "Даты", label: "Начало подачи заявок", get: l => l.submission_start, fmt: v => fmtDate(v as string) },
  { label: "Срок подачи заявок", get: l => l.submission_end, fmt: v => fmtDate(v as string), highlight: true },
];

// ─── Comparison helpers ───────────────────────────────────────────────────────

function getValues(lots: LotFull[], field: FieldDef): string[] {
  return lots.map(l => {
    const v = field.get(l);
    return field.fmt ? field.fmt(v) : (v != null ? String(v) : "—");
  });
}

function isDiff(vals: string[]): boolean {
  return vals.some(v => v !== vals[0]);
}

const COL_COLORS = [
  "rgba(99,102,241,0.08)", // indigo
  "rgba(16,185,129,0.08)", // green
  "rgba(245,158,11,0.08)", // amber
  "rgba(239,68,68,0.08)",  // red
  "rgba(168,85,247,0.08)", // purple
];

// ─── Main page ────────────────────────────────────────────────────────────────

function CompareContent() {
  const params = useSearchParams();
  const [lots, setLots] = useState<(LotFull | null)[]>([]);
  const [loading, setLoading] = useState(true);
  const [showDiffOnly, setShowDiffOnly] = useState(false);

  const rawIds = params.get("ids") || "";
  const ids = rawIds.split(",").map(s => parseInt(s.trim())).filter(n => !isNaN(n)).slice(0, 5);

  useEffect(() => {
    if (!ids.length) { setLoading(false); return; }
    setLoading(true);
    Promise.all(
      ids.map(id =>
        fetch(`${API}/api/lots/${id}`)
          .then(r => r.ok ? r.json() : null)
          .catch(() => null)
      )
    ).then(results => {
      setLots(results);
      setLoading(false);
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rawIds]);

  const validLots = lots.filter((l): l is LotFull => l !== null);

  const removeLot = (idx: number) => {
    const newIds = ids.filter((_, i) => i !== idx);
    if (newIds.length) {
      window.location.href = `/compare?ids=${newIds.join(",")}`;
    } else {
      window.location.href = "/lots";
    }
  };

  if (loading) {
    return (
      <div style={{ padding: 60, textAlign: "center", color: "var(--text-3)" }}>
        Загрузка участков...
      </div>
    );
  }

  if (!validLots.length) {
    return (
      <div style={{ padding: 60, textAlign: "center" }}>
        <div style={{ fontSize: 48, marginBottom: 16 }}>📋</div>
        <div style={{ fontSize: 20, fontWeight: 700, marginBottom: 8 }}>Нечего сравнивать</div>
        <div style={{ color: "var(--text-3)", marginBottom: 24 }}>
          Выберите участки в каталоге и нажмите «Сравнить»
        </div>
        <a href="/lots" className="btn btn-primary">Перейти в каталог</a>
      </div>
    );
  }

  const colWidth = Math.max(200, Math.floor(800 / validLots.length));

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", overflow: "hidden", background: "var(--bg)" }}>
      {/* Toolbar */}
      <div style={{ padding: "12px 20px", background: "var(--surface)", borderBottom: "1px solid var(--border)", display: "flex", gap: 12, alignItems: "center", flexShrink: 0 }}>
        <a href="/lots" style={{ color: "var(--text-3)", fontSize: 13, textDecoration: "none" }}>← Каталог</a>
        <span style={{ color: "var(--text-3)" }}>/</span>
        <span style={{ fontSize: 13, fontWeight: 600 }}>Сравнение участков</span>
        <span style={{ fontSize: 12, color: "var(--text-3)" }}>({validLots.length} из 5)</span>
        <div style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
          <label style={{ display: "flex", gap: 6, alignItems: "center", fontSize: 13, cursor: "pointer" }}>
            <input type="checkbox" checked={showDiffOnly} onChange={e => setShowDiffOnly(e.target.checked)} />
            Только различия
          </label>
          <a href="/lots" className="btn btn-ghost btn-sm">+ Добавить участок</a>
        </div>
      </div>

      {/* Table */}
      <div style={{ flex: 1, overflowY: "auto", overflowX: "auto" }}>
        <table style={{ borderCollapse: "collapse", fontSize: 13, minWidth: `${200 + validLots.length * colWidth}px` }}>
          {/* Sticky header row with lot cards */}
          <thead style={{ position: "sticky", top: 0, zIndex: 20 }}>
            <tr style={{ background: "var(--surface)", boxShadow: "0 2px 0 var(--border)" }}>
              {/* Label column */}
              <th style={{
                width: 200, minWidth: 200, padding: "12px 16px",
                textAlign: "left", fontSize: 12, fontWeight: 600,
                color: "var(--text-2)", textTransform: "uppercase",
                letterSpacing: "0.04em", background: "var(--surface)",
                borderRight: "1px solid var(--border)",
              }}>
                Параметр
              </th>
              {validLots.map((lot, i) => (
                <th key={lot.id} style={{
                  width: colWidth, minWidth: colWidth,
                  padding: "10px 12px",
                  background: COL_COLORS[i % COL_COLORS.length],
                  borderRight: "1px solid var(--border)",
                  verticalAlign: "top",
                }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
                    <div>
                      <a href={`/lots/${lot.id}`} style={{
                        fontWeight: 700, color: "var(--primary)", fontSize: 13,
                        textDecoration: "none", display: "block", marginBottom: 4,
                        overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                        maxWidth: colWidth - 50,
                      }}>
                        {lot.title || `Лот #${lot.id}`}
                      </a>
                      {lot.cadastral_number && (
                        <div style={{ fontSize: 11, color: "var(--text-3)", marginBottom: 4 }}>
                          {lot.cadastral_number}
                        </div>
                      )}
                      <div style={{ fontSize: 12, fontWeight: 700, color: "var(--primary)" }}>
                        {fmtPrice(lot.start_price)}
                      </div>
                    </div>
                    <button
                      onClick={() => removeLot(i)}
                      style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-3)", fontSize: 16, lineHeight: 1, padding: 2, flexShrink: 0 }}
                      title="Убрать из сравнения"
                    >
                      ×
                    </button>
                  </div>
                </th>
              ))}
            </tr>
          </thead>

          <tbody>
            {(() => {
              let lastGroup = "";
              const rows: React.ReactNode[] = [];

              FIELDS.forEach((field, fi) => {
                const vals = getValues(validLots, field);
                const diff = isDiff(vals);

                if (showDiffOnly && !diff) return;

                // Group header
                if (field.group && field.group !== lastGroup) {
                  lastGroup = field.group;
                  rows.push(
                    <tr key={`group-${fi}`} style={{ background: "var(--surface)" }}>
                      <td colSpan={validLots.length + 1} style={{
                        padding: "10px 16px 4px",
                        fontSize: 11, fontWeight: 700,
                        color: "var(--text-3)",
                        textTransform: "uppercase",
                        letterSpacing: "0.05em",
                        borderBottom: "1px solid var(--border)",
                      }}>
                        {field.group}
                      </td>
                    </tr>
                  );
                }

                rows.push(
                  <tr key={fi} style={{
                    background: fi % 2 === 0 ? "var(--surface-2)" : "var(--surface)",
                  }}>
                    {/* Label */}
                    <td style={{
                      padding: "8px 16px",
                      fontSize: 12,
                      color: "var(--text-2)",
                      fontWeight: diff && field.highlight ? 600 : 400,
                      borderRight: "1px solid var(--border)",
                      whiteSpace: "nowrap",
                      verticalAlign: "middle",
                    }}>
                      {field.label}
                      {diff && field.highlight && (
                        <span style={{
                          display: "inline-block", marginLeft: 6,
                          width: 6, height: 6, borderRadius: "50%",
                          background: "var(--warning)", verticalAlign: "middle",
                        }} title="Значения различаются" />
                      )}
                    </td>
                    {/* Values */}
                    {vals.map((val, ci) => {
                      const isBest = field.highlight && diff && (() => {
                        // For price fields — lower is better; for НЦ/КС — lower is better; for area — highlight max
                        const numVals = vals.map(v => parseFloat(v.replace(/[^\d.]/g, "")));
                        if (numVals.some(isNaN)) return false;
                        if (field.label === "Площадь [TG]" || field.label === "Площадь [КН]") {
                          return numVals[ci] === Math.max(...numVals);
                        }
                        if (field.label === "Начальная цена" || field.label === "% НЦ / КС" || field.label === "Кадастровая стоимость") {
                          return numVals[ci] === Math.min(...numVals);
                        }
                        return false;
                      })();

                      return (
                        <td key={ci} style={{
                          padding: "8px 12px",
                          borderRight: "1px solid var(--border)",
                          background: isBest
                            ? "rgba(16,185,129,0.12)"
                            : COL_COLORS[ci % COL_COLORS.length],
                          verticalAlign: "middle",
                          textAlign: "center",
                          fontWeight: isBest ? 700 : 400,
                          color: isBest ? "var(--success)" : "inherit",
                        }}>
                          {val}
                        </td>
                      );
                    })}
                  </tr>
                );
              });

              return rows;
            })()}

            {/* CTA row */}
            <tr style={{ background: "var(--surface)" }}>
              <td style={{ padding: "16px", borderRight: "1px solid var(--border)", borderTop: "2px solid var(--border)" }} />
              {validLots.map((lot, i) => (
                <td key={lot.id} style={{
                  padding: "16px 12px",
                  textAlign: "center",
                  borderRight: "1px solid var(--border)",
                  borderTop: "2px solid var(--border)",
                  background: COL_COLORS[i % COL_COLORS.length],
                }}>
                  <div style={{ display: "flex", flexDirection: "column", gap: 8, alignItems: "center" }}>
                    <a href={`/lots/${lot.id}`} className="btn btn-primary btn-sm" style={{ width: "100%", textAlign: "center" }}>
                      Подробнее →
                    </a>
                    {lot.lot_url && (
                      <a href={lot.lot_url} target="_blank" rel="noopener noreferrer"
                        className="btn btn-ghost btn-sm" style={{ width: "100%", textAlign: "center", fontSize: 11 }}>
                        На torgi.gov ↗
                      </a>
                    )}
                  </div>
                </td>
              ))}
            </tr>
          </tbody>
        </table>

        {showDiffOnly && FIELDS.every(f => {
          const vals = getValues(validLots, f);
          return !isDiff(vals);
        }) && (
          <div style={{ padding: 40, textAlign: "center", color: "var(--text-3)" }}>
            Все значения совпадают — различий не найдено.
          </div>
        )}
      </div>

      {/* Legend */}
      <div style={{
        padding: "8px 20px",
        background: "var(--surface)",
        borderTop: "1px solid var(--border)",
        display: "flex",
        gap: 20,
        fontSize: 11,
        color: "var(--text-3)",
        flexShrink: 0,
      }}>
        <span style={{ display: "flex", gap: 4, alignItems: "center" }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--warning)", display: "inline-block" }} />
          Параметры различаются
        </span>
        <span style={{ display: "flex", gap: 4, alignItems: "center" }}>
          <span style={{ width: 14, height: 14, borderRadius: 3, background: "rgba(16,185,129,0.2)", display: "inline-block" }} />
          Лучшее значение (цена ↓, площадь ↑)
        </span>
      </div>
    </div>
  );
}

export default function ComparePage() {
  return (
    <Suspense fallback={<div style={{ padding: 60, textAlign: "center", color: "var(--text-3)" }}>Загрузка...</div>}>
      <CompareContent />
    </Suspense>
  );
}
