"use client";

// Переиспользуемая заглушка для премиум-блоков лота: замок + ценность + CTA на тарифы.
export default function LockedBlock({
  title,
  description,
  planLabel = "Pro",
}: {
  title: string;
  description: string;
  planLabel?: string;
}) {
  return (
    <div style={{
      background: "var(--surface)", border: "1px solid var(--border)",
      borderRadius: 12, padding: 16,
    }}>
      <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 6 }}>🔒 {title}</div>
      <div style={{ fontSize: 13, color: "var(--text-3)", marginBottom: 10, lineHeight: 1.5 }}>
        {description}
      </div>
      <a href="/pricing" className="btn btn-primary btn-sm" style={{ textDecoration: "none" }}>
        ⚡ Доступно с тарифа {planLabel} →
      </a>
    </div>
  );
}
