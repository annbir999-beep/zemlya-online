"use client";
import { useState, useEffect, useCallback } from "react";
import FilterSidebar from "@/components/FilterSidebar";
import { FiltersState, filtersToQueryString, SORT_OPTIONS } from "@/lib/filters";
import type { LotListItem, LotsResponse } from "@/lib/api";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";
const DEFAULT_FILTERS: FiltersState = { status: "active", sort_by: "auction_end_date", sort_order: "asc" };

const PURPOSE_LABEL: Record<string, string> = {
  izhs: "ИЖС", snt: "СНТ", lpkh: "ЛПХ", agricultural: "Сельхоз",
  commercial: "Коммерция", industrial: "Промышленность",
  forest: "Лес", water: "Вода", special: "Спец.", other: "Иное",
};
const STATUS_CONFIG: Record<string, { label: string; cls: string }> = {
  active: { label: "Активный", cls: "badge-green" },
  upcoming: { label: "Скоро", cls: "badge-blue" },
  completed: { label: "Завершён", cls: "badge-gray" },
  cancelled: { label: "Отменён", cls: "badge-red" },
};
const RESALE_LABEL: Record<string, string> = {
  yes: "Можно", no: "Нельзя",
  with_notice: "Уведомив", with_approval: "Согласовав",
};

function fmtPrice(n?: number) {
  if (!n) return "—";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)} млн`;
  return `${(n / 1_000).toFixed(0)} тыс.`;
}
function fmtArea(sqm?: number) {
  if (!sqm) return "—";
  if (sqm >= 10_000) return `${(sqm / 10_000).toFixed(2)} га`;
  return `${sqm.toLocaleString("ru")} м²`;
}
function fmtDate(iso?: string) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("ru", { day: "2-digit", month: "2-digit", year: "2-digit" });
}
function daysLeft(iso?: string) {
  if (!iso) return null;
  const d = Math.ceil((new Date(iso).getTime() - Date.now()) / 86_400_000);
  if (d < 0 || d > 30) return null;
  if (d === 0) return <span style={{ color: "var(--danger)", fontWeight: 700 }}>сегодня!</span>;
  return <span style={{ color: "var(--warning)", fontWeight: 600 }}>{d}д</span>;
}

export default function CatalogPage() {
  const [filters, setFilters] = useState<FiltersState>(DEFAULT_FILTERS);
  const [data, setData] = useState<LotsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [compareIds, setCompareIds] = useState<number[]>([]);

  const load = useCallback(async (f: FiltersState) => {
    setLoading(true);
    try {
      const qs = filtersToQueryString({ ...f, per_page: 50 });
      const res = await fetch(`${API}/api/lots?${qs}`);
      setData(await res.json());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(filters); }, [filters, load]);

  const toggleCompare = (id: number) =>
    setCompareIds(prev => prev.includes(id) ? prev.filter(x => x !== id) : prev.length < 5 ? [...prev, id] : prev);

  const sortValue = filters.sort_by ? `${filters.sort_by}:${filters.sort_order || "asc"}` : "auction_end_date:asc";

  const pages = data ? Math.ceil(data.total / 50) : 0;

  return (
    <>
      <FilterSidebar filters={filters} onChange={setFilters} onReset={() => setFilters(DEFAULT_FILTERS)} />

      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", background: "var(--bg)" }}>
        {/* Toolbar */}
        <div style={{ padding: "12px 20px", background: "var(--surface)", borderBottom: "1px solid var(--border)", display: "flex", gap: 12, alignItems: "center", flexShrink: 0 }}>
          <span style={{ fontSize: 13, color: "var(--text-2)", marginRight: "auto" }}>
            {loading ? "Загрузка..." : data ? `${data.total.toLocaleString("ru")} участков` : ""}
          </span>

          {/* Sort */}
          <select
            className="select"
            style={{ width: 260 }}
            value={sortValue}
            onChange={e => {
              const [by, order] = e.target.value.split(":");
              setFilters(f => ({ ...f, sort_by: by, sort_order: order, page: 1 }));
            }}
          >
            {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>

          {compareIds.length > 0 && (
            <a href={`/compare?ids=${compareIds.join(",")}`} className="btn btn-primary btn-sm">
              Сравнить {compareIds.length} →
            </a>
          )}
        </div>

        {/* Table */}
        <div style={{ flex: 1, overflowY: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead style={{ position: "sticky", top: 0, background: "var(--surface)", zIndex: 10, boxShadow: "0 1px 0 var(--border)" }}>
              <tr>
                <th style={th()}>
                  <input type="checkbox" style={{ cursor: "pointer" }} onChange={e => {
                    if (e.target.checked && data) setCompareIds(data.items.slice(0, 5).map(l => l.id));
                    else setCompareIds([]);
                  }} />
                </th>
                <th style={th("left")}>Участок</th>
                <th style={th()}>Статус</th>
                <th style={th()}>Назначение</th>
                {(["price", "pct_cadastral", "area", "deposit_pct", "auction_end_date", "submission_end"] as const).map((col, i) => {
                  const labels: Record<string, string> = { price: "Цена, ₽", pct_cadastral: "НЦ/КС", area: "Площадь [TG]", deposit_pct: "Задаток", auction_end_date: "Конец торгов", submission_end: "Конец заявок" };
                  const active = filters.sort_by === col;
                  const asc = filters.sort_order === "asc";
                  return (
                    <th key={col} style={{ ...th(), cursor: "pointer", userSelect: "none", color: active ? "var(--primary)" : "var(--text-2)" }}
                      onClick={() => setFilters(f => ({ ...f, sort_by: col, sort_order: active && asc ? "desc" : "asc", page: 1 }))}>
                      {labels[col]} {active ? (asc ? "↑" : "↓") : <span style={{ opacity: 0.3 }}>↕</span>}
                    </th>
                  );
                })}
                <th style={th()}>Площадь [КН]</th>
                <th style={th()}>Переуступка</th>
                <th style={th()}>Регион</th>
                <th style={th()}>Действия</th>
              </tr>
            </thead>
            <tbody>
              {!loading && data?.items.map((lot, i) => {
                const status = STATUS_CONFIG[lot.status] || { label: lot.status, cls: "badge-gray" };
                const inCompare = compareIds.includes(lot.id);
                return (
                  <tr key={lot.id}
                    style={{ background: i % 2 === 0 ? "var(--surface)" : "var(--surface-2)", cursor: "pointer" }}
                    onClick={() => window.open(`/lots/${lot.id}`, "_blank")}
                  >
                    <td style={td()} onClick={e => e.stopPropagation()}>
                      <input type="checkbox" checked={inCompare}
                        onChange={() => toggleCompare(lot.id)}
                        style={{ cursor: "pointer" }} />
                    </td>
                    <td style={{ ...td("left"), maxWidth: 260 }}>
                      <div style={{ fontWeight: 500, color: "var(--primary)", marginBottom: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {lot.title || `Лот #${lot.id}`}
                      </div>
                      {lot.cadastral_number && (
                        <div style={{ fontSize: 11, color: "var(--text-3)" }}>{lot.cadastral_number}</div>
                      )}
                    </td>
                    <td style={td()}>
                      <span className={`badge ${status.cls}`} style={{ fontSize: 11 }}>{status.label}</span>
                    </td>
                    <td style={td()}>
                      {lot.land_purpose ? <span className="badge badge-gray" style={{ fontSize: 11 }}>{PURPOSE_LABEL[lot.land_purpose] || lot.land_purpose}</span> : "—"}
                    </td>
                    {/* Цена */}
                    <td style={{ ...td(), fontWeight: 700, color: "var(--primary)", whiteSpace: "nowrap" }}>
                      {fmtPrice(lot.start_price)}
                    </td>
                    {/* НЦ/КС */}
                    <td style={td()}>
                      {lot.pct_price_to_cadastral
                        ? <span style={{ fontWeight: 600, color: lot.pct_price_to_cadastral < 50 ? "#16a34a" : lot.pct_price_to_cadastral > 100 ? "#dc2626" : "var(--text)" }}>{lot.pct_price_to_cadastral.toFixed(0)}%</span>
                        : "—"}
                    </td>
                    {/* Площадь TG */}
                    <td style={td()}>{fmtArea(lot.area_sqm)}</td>
                    {/* Задаток */}
                    <td style={td()}>
                      {lot.deposit
                        ? <>{fmtPrice(lot.deposit)}{lot.deposit_pct ? <div style={{ fontSize: 11, color: "var(--text-3)" }}>{lot.deposit_pct.toFixed(1)}%</div> : null}</>
                        : "—"}
                    </td>
                    {/* Конец торгов */}
                    <td style={{ ...td(), whiteSpace: "nowrap" }}>
                      <div>{fmtDate(lot.auction_end_date)}</div>
                      <div style={{ fontSize: 11 }}>{daysLeft(lot.auction_end_date)}</div>
                    </td>
                    {/* Конец заявок */}
                    <td style={{ ...td(), whiteSpace: "nowrap", fontSize: 12 }}>
                      {fmtDate(lot.submission_end)}
                    </td>
                    {/* Площадь КН */}
                    <td style={td()}>
                      {lot.area_sqm_kn ? fmtArea(lot.area_sqm_kn) : <span style={{ color: "var(--text-3)" }}>—</span>}
                    </td>
                    {/* Переуступка */}
                    <td style={td()}>
                      {lot.resale_type
                        ? <span style={{ fontSize: 11 }}>{RESALE_LABEL[lot.resale_type] || "—"}</span>
                        : "—"}
                    </td>
                    {/* Регион */}
                    <td style={{ ...td(), maxWidth: 120, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {lot.region_name || "—"}
                    </td>
                    <td style={td()} onClick={e => e.stopPropagation()}>
                      <a href={`/lots/${lot.id}`} className="btn btn-ghost btn-sm" style={{ padding: "3px 8px" }}>
                        →
                      </a>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {loading && (
            <div style={{ padding: 40, textAlign: "center", color: "var(--text-3)" }}>Загрузка...</div>
          )}
          {!loading && data?.items.length === 0 && (
            <div style={{ padding: 40, textAlign: "center", color: "var(--text-3)" }}>
              Ничего не найдено. Попробуйте изменить фильтры.
            </div>
          )}
        </div>

        {/* Pagination */}
        {pages > 1 && (
          <div className="pagination" style={{ borderTop: "1px solid var(--border)", background: "var(--surface)", padding: "10px 16px" }}>
            <button disabled={!filters.page || filters.page <= 1}
              onClick={() => setFilters(f => ({ ...f, page: (f.page || 1) - 1 }))}>
              ←
            </button>
            {Array.from({ length: Math.min(pages, 10) }, (_, i) => i + 1).map(p => (
              <button key={p} className={(filters.page || 1) === p ? "active" : ""}
                onClick={() => setFilters(f => ({ ...f, page: p }))}>
                {p}
              </button>
            ))}
            {pages > 10 && <span style={{ padding: "0 6px", color: "var(--text-3)" }}>...</span>}
            <button disabled={(filters.page || 1) >= pages}
              onClick={() => setFilters(f => ({ ...f, page: (f.page || 1) + 1 }))}>
              →
            </button>
          </div>
        )}
      </div>

      {/* Compare bar */}
      {compareIds.length > 0 && (
        <div className="compare-bar">
          <span style={{ fontSize: 13 }}>Сравниваю: {compareIds.length} из 5</span>
          <a href={`/compare?ids=${compareIds.join(",")}`} className="btn btn-primary btn-sm">
            Сравнить →
          </a>
          <button className="btn btn-ghost btn-sm" style={{ color: "#94a3b8" }} onClick={() => setCompareIds([])}>
            Очистить
          </button>
        </div>
      )}
    </>
  );
}

function th(align: "left" | "center" = "center") {
  return {
    padding: "10px 12px",
    textAlign: align as "left" | "center",
    fontSize: 12,
    fontWeight: 600,
    color: "var(--text-2)",
    textTransform: "uppercase" as const,
    letterSpacing: "0.04em",
    whiteSpace: "nowrap" as const,
  };
}
function td(align: "left" | "center" = "center") {
  return { padding: "8px 12px", textAlign: align as "left" | "center", verticalAlign: "middle" as const };
}
