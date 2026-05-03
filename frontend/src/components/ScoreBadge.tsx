"use client";

const BADGE_LABELS: Record<string, { emoji: string; label: string; color: string; bg: string }> = {
  hot:      { emoji: "🔥", label: "Горячий",         color: "#dc2626", bg: "#fee2e2" },
  diamond:  { emoji: "💎", label: "Скидка к рынку",  color: "#0891b2", bg: "#cffafe" },
  split:    { emoji: "📐", label: "Под межевание",   color: "#7c3aed", bg: "#ede9fe" },
  vri:      { emoji: "🌾", label: "Перевод ВРИ",     color: "#a16207", bg: "#fef3c7" },
  build:    { emoji: "🏗",  label: "Под стройку",     color: "#16a34a", bg: "#dcfce7" },
  commerce: { emoji: "🏪", label: "Коммерция",       color: "#dc2626", bg: "#fee2e2" },
  urgent:   { emoji: "⚡", label: "Срочно",           color: "#ea580c", bg: "#ffedd5" },
  rent:     { emoji: "🔁", label: "Аренда с выкупом", color: "#0284c7", bg: "#e0f2fe" },
  cheap_buyout: { emoji: "💰", label: "Дешёвый выкуп", color: "#0d9488", bg: "#ccfbf1" },
  kfh_house:    { emoji: "🏡", label: "КФХ-дом разрешён", color: "#16a34a", bg: "#dcfce7" },
  garden:       { emoji: "🌱", label: "ВРИ Огород", color: "#15803d", bg: "#dcfce7" },
  water:        { emoji: "🌊", label: "У воды", color: "#0284c7", bg: "#e0f2fe" },
  forest:       { emoji: "🌲", label: "У леса", color: "#047857", bg: "#d1fae5" },
  price_drop:   { emoji: "📉", label: "Цена снижена", color: "#dc2626", bg: "#fee2e2" },
};

function scoreColor(score: number): string {
  if (score >= 80) return "#dc2626";   // красный — горячо
  if (score >= 60) return "#ea580c";   // оранжевый
  if (score >= 40) return "#ca8a04";   // янтарь
  if (score >= 20) return "#65a30d";   // салатовый
  return "#94a3b8";                     // серый
}

export function ScoreCircle({ score, size = 32 }: { score?: number | null; size?: number }) {
  if (score == null) return null;
  const color = scoreColor(score);
  return (
    <div style={{
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      width: size,
      height: size,
      borderRadius: "50%",
      background: `${color}22`,
      color,
      fontWeight: 800,
      fontSize: size * 0.4,
      flexShrink: 0,
    }} title={`Скор рентабельности: ${score}/100`}>
      {score}
    </div>
  );
}

export function ScoreBadges({ badges, max = 4, compact = false }: { badges?: string[] | null; max?: number; compact?: boolean }) {
  if (!badges || badges.length === 0) return null;
  return (
    <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
      {badges.slice(0, max).map((b) => {
        const cfg = BADGE_LABELS[b];
        if (!cfg) return null;
        return (
          <span key={b} title={cfg.label} style={{
            background: cfg.bg,
            color: cfg.color,
            fontSize: compact ? 10 : 11,
            fontWeight: 600,
            padding: compact ? "1px 5px" : "2px 6px",
            borderRadius: 4,
            whiteSpace: "nowrap",
          }}>
            {cfg.emoji}{compact ? "" : ` ${cfg.label}`}
          </span>
        );
      })}
    </div>
  );
}

export function DiscountTag({ pct }: { pct?: number | null }) {
  if (pct == null || pct < 5) return null;
  return (
    <span style={{
      background: pct >= 30 ? "#dcfce7" : "#f0fdf4",
      color: pct >= 30 ? "#15803d" : "#16a34a",
      fontSize: 11,
      fontWeight: 700,
      padding: "2px 6px",
      borderRadius: 4,
      whiteSpace: "nowrap",
    }} title="Дисконт к медианной рыночной цене (ЦИАН + Авито)">
      −{pct.toFixed(0)}% к рынку
    </span>
  );
}
