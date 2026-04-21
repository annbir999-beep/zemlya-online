"use client";
import type { LotListItem } from "@/lib/api";

const PURPOSE_LABEL: Record<string, string> = {
  izhs: "ИЖС", snt: "СНТ", lpkh: "ЛПХ", agricultural: "Сельхоз",
  commercial: "Коммерция", industrial: "Промышленность",
  forest: "Лес", water: "Водный фонд", special: "Спец.", other: "Иное",
};

const STATUS_CONFIG: Record<string, { label: string; cls: string }> = {
  active: { label: "Торги идут", cls: "badge-green" },
  upcoming: { label: "Скоро", cls: "badge-blue" },
  completed: { label: "Завершены", cls: "badge-gray" },
  cancelled: { label: "Отменены", cls: "badge-red" },
};

function formatPrice(p?: number): string {
  if (!p) return "—";
  if (p >= 1_000_000) return `${(p / 1_000_000).toFixed(1)} млн ₽`;
  if (p >= 1_000) return `${(p / 1_000).toFixed(0)} тыс. ₽`;
  return `${p.toLocaleString("ru")} ₽`;
}

function formatArea(sqm?: number): string {
  if (!sqm) return "—";
  if (sqm >= 10_000) return `${(sqm / 10_000).toFixed(2)} га`;
  return `${sqm.toLocaleString("ru")} кв.м`;
}

function formatDate(iso?: string): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("ru", { day: "2-digit", month: "2-digit", year: "numeric" });
}

function daysLeft(iso?: string): string {
  if (!iso) return "";
  const diff = Math.ceil((new Date(iso).getTime() - Date.now()) / 86_400_000);
  if (diff < 0) return "";
  if (diff === 0) return "сегодня!";
  if (diff === 1) return "1 день";
  return `${diff} дн.`;
}

interface Props {
  lot: LotListItem;
  selected?: boolean;
  compareIds?: number[];
  onSelect: (lot: LotListItem) => void;
  onToggleCompare?: (id: number) => void;
}

export default function LotCard({ lot, selected, compareIds = [], onSelect, onToggleCompare }: Props) {
  const status = STATUS_CONFIG[lot.status] || { label: lot.status, cls: "badge-gray" };
  const inCompare = compareIds.includes(lot.id);
  const dl = daysLeft(lot.submission_end);

  return (
    <div className={`lot-card ${selected ? "selected" : ""}`} onClick={() => onSelect(lot)}>
      <div className="lot-card-title">{lot.title || "Земельный участок"}</div>

      <div className="lot-card-meta">
        {lot.source === "avito" && (
          <span className="badge" style={{ background: "#00aaff22", color: "#0077cc", fontWeight: 700, letterSpacing: "0.02em" }}>
            Авито
          </span>
        )}
        {lot.source === "torgi_gov" && (
          <span className="badge badge-gray" style={{ fontSize: 10 }}>torgi.gov</span>
        )}
        <span className={`badge ${status.cls}`}>{status.label}</span>
        {lot.land_purpose && (
          <span className="badge badge-gray">{PURPOSE_LABEL[lot.land_purpose] || lot.land_purpose}</span>
        )}
        {lot.auction_type === "rent" && <span className="badge badge-orange">Аренда</span>}
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 6 }}>
        <span className="lot-card-price">{formatPrice(lot.start_price)}</span>
        <span style={{ fontSize: 12, color: "var(--text-3)" }}>{formatArea(lot.area_sqm)}</span>
      </div>

      {/* Кадастровая стоимость и % НЦ/КС */}
      {(lot.cadastral_cost || lot.pct_price_to_cadastral) && (
        <div style={{ display: "flex", gap: 8, marginBottom: 5, flexWrap: "wrap" }}>
          {lot.cadastral_cost && (
            <span style={{ fontSize: 11, color: "var(--text-3)" }}>
              КС: <b style={{ color: "var(--text-2)" }}>{formatPrice(lot.cadastral_cost)}</b>
            </span>
          )}
          {lot.pct_price_to_cadastral && (
            <span style={{ fontSize: 11, color: "var(--text-3)" }}>
              НЦ/КС: <b style={{ color: lot.pct_price_to_cadastral < 50 ? "var(--success, #16a34a)" : "var(--text-2)" }}>
                {lot.pct_price_to_cadastral.toFixed(1)}%
              </b>
            </span>
          )}
        </div>
      )}

      {/* ВРИ */}
      {lot.vri_tg && (
        <div style={{ fontSize: 11, color: "var(--text-3)", marginBottom: 5, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          {lot.vri_tg}
        </div>
      )}

      <div style={{ fontSize: 12, color: "var(--text-2)", display: "flex", gap: 8, flexWrap: "wrap" }}>
        {lot.region_name && <span>📍 {lot.region_name}</span>}
        {lot.submission_end && (
          <span>⏰ до {formatDate(lot.submission_end)}{dl && <b style={{ color: "var(--danger)", marginLeft: 4 }}>{dl}</b>}</span>
        )}
      </div>

      {/* Начало приёма заявок */}
      {lot.submission_start && (
        <div style={{ fontSize: 11, color: "var(--text-3)", marginTop: 4 }}>
          Заявки с {formatDate(lot.submission_start)}
        </div>
      )}

      <div className="lot-card-footer" onClick={(e) => e.stopPropagation()}>
        <a
          href={`/lots/${lot.id}`}
          className="btn btn-ghost btn-sm"
        >
          Подробнее →
        </a>
        <a
          href={lot.lot_url || "#"}
          target="_blank"
          rel="noopener noreferrer"
          className="btn btn-ghost btn-sm"
        >
          Оригинал ↗
        </a>
        {onToggleCompare && (
          <button
            className={`btn btn-sm ${inCompare ? "btn-primary" : "btn-secondary"}`}
            onClick={() => onToggleCompare(lot.id)}
            title={inCompare ? "Убрать из сравнения" : "Добавить в сравнение"}
          >
            {inCompare ? "✓ Сравниваю" : "+ Сравнить"}
          </button>
        )}
      </div>
    </div>
  );
}
