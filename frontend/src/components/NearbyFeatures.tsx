"use client";

interface WaterFeature { name?: string; kind?: string; distance_m: number }
interface DistFeature { distance_m: number }
interface SettlementFeature { name?: string; kind?: string; distance_m: number }
interface HighwayFeature { kind?: string; ref?: string; distance_m: number }
interface RailwayFeature { name?: string; distance_m: number }

export interface NearbyFeatures {
  water?: WaterFeature;
  forest?: DistFeature;
  highway?: HighwayFeature;
  settlement?: SettlementFeature;
  railway?: RailwayFeature;
}

const WATER_EMOJI: Record<string, string> = {
  lake: "🌊", pond: "🌊", reservoir: "🌊",
  river: "🏞", stream: "💧", canal: "💧", water: "🌊",
};

function fmtDistance(m: number): string {
  if (m < 1000) return `${m} м`;
  return `${(m / 1000).toFixed(1)} км`;
}

function band(m: number): { color: string; label: string } {
  if (m <= 500) return { color: "#16a34a", label: "вплотную" };
  if (m <= 1500) return { color: "#0d9488", label: "рядом" };
  if (m <= 3000) return { color: "#0ea5e9", label: "недалеко" };
  return { color: "#94a3b8", label: "" };
}

export default function NearbyFeaturesCard({ data }: { data?: NearbyFeatures | null }) {
  if (!data) return null;
  const items: Array<{ icon: string; text: string; m?: number }> = [];

  if (data.water) {
    const emoji = WATER_EMOJI[data.water.kind || "water"] || "🌊";
    items.push({
      icon: emoji,
      text: `${data.water.name || "Водоём"}`,
      m: data.water.distance_m,
    });
  }
  if (data.forest) items.push({ icon: "🌲", text: "Лес", m: data.forest.distance_m });
  if (data.settlement) {
    const inside = data.settlement.distance_m < 100;
    items.push({
      icon: "🏘",
      text: `${data.settlement.name || "Населённый пункт"}${inside ? " (внутри)" : ""}`,
      m: inside ? undefined : data.settlement.distance_m,
    });
  }
  if (data.highway) {
    const ref = data.highway.ref || (data.highway.kind === "motorway" ? "Магистраль" : "Трасса");
    items.push({ icon: "🛣", text: ref, m: data.highway.distance_m });
  }
  if (data.railway) {
    items.push({ icon: "🚆", text: data.railway.name || "Ж/д станция", m: data.railway.distance_m });
  }

  if (items.length === 0) return null;

  return (
    <div style={{
      background: "var(--surface)", border: "1px solid var(--border)",
      borderRadius: 12, padding: 16,
    }}>
      <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 12 }}>
        Что рядом
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {items.map((it, i) => {
          const b = it.m != null ? band(it.m) : { color: "var(--text-3)", label: "" };
          return (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ fontSize: 18 }}>{it.icon}</span>
              <span style={{ flex: 1, fontSize: 13 }}>{it.text}</span>
              {it.m != null && (
                <span style={{ fontSize: 12, fontWeight: 600, color: b.color }}>
                  {fmtDistance(it.m)}
                  {b.label && <span style={{ fontWeight: 400, color: "var(--text-3)", marginLeft: 4 }}>· {b.label}</span>}
                </span>
              )}
            </div>
          );
        })}
      </div>
      <div style={{ fontSize: 11, color: "var(--text-3)", marginTop: 10 }}>
        Источник — OpenStreetMap (радиус 3 км от точки участка)
      </div>
    </div>
  );
}
