"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

interface Comms {
  electricity?: boolean;
  gas?: boolean;
  water?: boolean;
  sewage?: boolean;
  road?: "asphalt" | "gravel" | "none";
  internet?: boolean;
}

const ICONS: Record<string, { emoji: string; label: string }> = {
  electricity: { emoji: "⚡", label: "Электричество" },
  gas: { emoji: "🔥", label: "Газ" },
  water: { emoji: "💧", label: "Вода" },
  sewage: { emoji: "🚽", label: "Канализация" },
  asphalt: { emoji: "🛣", label: "Асфальт" },
  gravel: { emoji: "🛤", label: "Грунтовая дорога" },
  none: { emoji: "🚫", label: "Нет дороги" },
  internet: { emoji: "📶", label: "Интернет" },
};

export function LocationCard({ city, distance, population }: {
  city?: string | null;
  distance?: number | null;
  population?: number | null;
}) {
  if (!city) return null;
  const popText = population ? (
    population >= 1_000_000 ? `${(population / 1_000_000).toFixed(1)} млн` :
    population >= 1000 ? `${Math.round(population / 1000)} тыс` :
    `${population}`
  ) : "";
  const liquidity = distance == null ? null :
    distance <= 30 && (population || 0) >= 500_000 ? "Высокая" :
    distance <= 50 && (population || 0) >= 200_000 ? "Хорошая" :
    distance <= 100 && (population || 0) >= 100_000 ? "Средняя" :
    distance > 200 ? "Низкая" : "Средняя";
  const liquidityColor = liquidity === "Высокая" ? "#16a34a" :
                          liquidity === "Хорошая" ? "#65a30d" :
                          liquidity === "Низкая" ? "#dc2626" : "#ca8a04";
  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: 16, marginBottom: 16 }}>
      <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 10 }}>📍 Локация и ликвидность</div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 16, fontSize: 13 }}>
        <div>
          <div style={{ color: "var(--text-3)", fontSize: 11 }}>Ближайший город</div>
          <div style={{ fontWeight: 600 }}>{city} {popText && <span style={{ color: "var(--text-3)", fontSize: 12 }}>({popText})</span>}</div>
        </div>
        {distance != null && (
          <div>
            <div style={{ color: "var(--text-3)", fontSize: 11 }}>Расстояние</div>
            <div style={{ fontWeight: 600 }}>{distance.toFixed(0)} км</div>
          </div>
        )}
        {liquidity && (
          <div>
            <div style={{ color: "var(--text-3)", fontSize: 11 }}>Ликвидность</div>
            <div style={{ fontWeight: 700, color: liquidityColor }}>{liquidity}</div>
          </div>
        )}
      </div>
    </div>
  );
}

export function CommsCard({ comms }: { comms?: Comms | null }) {
  if (!comms || Object.keys(comms).length === 0) return null;
  const items: React.ReactNode[] = [];
  const add = (key: string, available: boolean) => {
    const cfg = ICONS[key];
    if (!cfg) return;
    items.push(
      <span key={key} style={{
        background: available ? "#dcfce7" : "#fee2e2",
        color: available ? "#166534" : "#991b1b",
        padding: "4px 10px",
        borderRadius: 6,
        fontSize: 12,
        fontWeight: 500,
      }}>
        {cfg.emoji} {cfg.label} {available ? "✓" : "✗"}
      </span>
    );
  };
  if (comms.electricity != null) add("electricity", comms.electricity);
  if (comms.gas != null) add("gas", comms.gas);
  if (comms.water != null) add("water", comms.water);
  if (comms.sewage != null) add("sewage", comms.sewage);
  if (comms.road) {
    const cfg = ICONS[comms.road];
    if (cfg) {
      const isPositive = comms.road !== "none";
      items.push(
        <span key="road" style={{
          background: isPositive ? "#dcfce7" : "#fee2e2",
          color: isPositive ? "#166534" : "#991b1b",
          padding: "4px 10px", borderRadius: 6, fontSize: 12, fontWeight: 500,
        }}>{cfg.emoji} {cfg.label}</span>
      );
    }
  }
  if (comms.internet) add("internet", true);

  if (items.length === 0) return null;
  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: 16, marginBottom: 16 }}>
      <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 10 }}>🚦 Коммуникации (из описания)</div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>{items}</div>
      <div style={{ fontSize: 11, color: "var(--text-3)", marginTop: 8 }}>
        Парсинг автоматический — проверьте напрямую с продавцом перед сделкой.
      </div>
    </div>
  );
}

interface SimilarHistory {
  items: Array<{
    id: number; title: string; start_price: number; final_price?: number;
    area_sqm: number; address?: string; submission_end?: string; deal_type?: string;
  }>;
  stats: {
    count: number;
    median_price?: number;
    median_price_per_sqm?: number;
    min_price?: number;
    max_price?: number;
  };
}

export function SimilarHistoryCard({ lotId }: { lotId: number }) {
  const [data, setData] = useState<SimilarHistory | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    api.get<SimilarHistory>(`/api/lots/${lotId}/similar-history`).then(setData).catch(() => {}).finally(() => setLoading(false));
  }, [lotId]);

  if (loading) return null;
  if (!data || data.stats.count === 0) return null;

  const fmtPrice = (n?: number | null) => n == null ? "—" : (n >= 1_000_000 ? `${(n/1_000_000).toFixed(2)} млн ₽` : `${(n/1000).toFixed(0)} тыс ₽`);
  const fmtDate = (s?: string) => s ? new Date(s).toLocaleDateString("ru") : "—";

  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: 16, marginBottom: 16 }}>
      <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 8 }}>📊 История похожих лотов в регионе</div>
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", fontSize: 12, marginBottom: 10, color: "var(--text-2)" }}>
        <div>Найдено: <b>{data.stats.count}</b> завершённых лотов</div>
        {data.stats.median_price != null && <div>Медиана цены: <b>{fmtPrice(data.stats.median_price)}</b></div>}
        {data.stats.median_price_per_sqm != null && <div>Медиана за м²: <b>{Math.round(data.stats.median_price_per_sqm).toLocaleString("ru")} ₽</b></div>}
      </div>
      <div style={{ maxHeight: 200, overflowY: "auto" }}>
        {data.items.slice(0, 5).map(it => (
          <div key={it.id} style={{ borderTop: "1px solid var(--border)", padding: "6px 0", fontSize: 12, display: "flex", justifyContent: "space-between", gap: 8 }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{it.title || `Лот #${it.id}`}</div>
              <div style={{ color: "var(--text-3)", fontSize: 11 }}>
                {it.area_sqm ? `${it.area_sqm.toLocaleString("ru")} м²` : ""}
                {it.deal_type ? ` · ${it.deal_type === "lease" ? "Аренда" : "Продажа"}` : ""}
                {it.submission_end ? ` · ${fmtDate(it.submission_end)}` : ""}
              </div>
            </div>
            <div style={{ textAlign: "right", flexShrink: 0 }}>
              <div style={{ fontWeight: 600 }}>{fmtPrice(it.start_price)}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
