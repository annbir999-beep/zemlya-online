"use client";
import { useEffect, useState } from "react";
import Link from "next/link";

const KEY = "hero_dismissed_at";

/**
 * Sticky-баннер над шапкой с УТП. Можно закрыть — скрыт на 7 дней.
 */
export default function HeroBar() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const dismissed = localStorage.getItem(KEY);
    if (!dismissed) {
      setVisible(true);
      return;
    }
    const ts = parseInt(dismissed, 10);
    const sevenDays = 7 * 24 * 3600 * 1000;
    if (Date.now() - ts > sevenDays) {
      setVisible(true);
    }
  }, []);

  const dismiss = () => {
    localStorage.setItem(KEY, String(Date.now()));
    setVisible(false);
  };

  if (!visible) return null;

  return (
    <div style={{
      background: "linear-gradient(135deg, #16a34a 0%, #0d9488 100%)",
      color: "white",
      padding: "9px 16px",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      gap: 16,
      fontSize: 14,
      flexWrap: "wrap",
      position: "relative",
    }}>
      <span style={{ fontWeight: 600, lineHeight: 1.4 }}>
        💎 Сформируйте земельный портфель.
        <span style={{ opacity: 0.9, fontWeight: 400, marginLeft: 8 }}>
          Дисконты до 80%, AI-аудит каждого лота, региональная аналитика.
        </span>
      </span>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <Link
          href="/pricing"
          style={{
            background: "rgba(255,255,255,0.18)",
            color: "white",
            padding: "6px 14px",
            borderRadius: 8,
            textDecoration: "none",
            fontWeight: 700,
            fontSize: 13,
            whiteSpace: "nowrap",
            border: "1px solid rgba(255,255,255,0.4)",
          }}
        >
          ⚡ Тарифы
        </Link>
        <Link
          href="/audit-lot"
          style={{
            background: "white",
            color: "#0d9488",
            padding: "6px 16px",
            borderRadius: 8,
            textDecoration: "none",
            fontWeight: 700,
            fontSize: 13,
            whiteSpace: "nowrap",
          }}
        >
          Бесплатный аудит →
        </Link>
      </div>
      <button
        onClick={dismiss}
        aria-label="Закрыть"
        style={{
          position: "absolute",
          right: 10,
          top: "50%",
          transform: "translateY(-50%)",
          background: "transparent",
          border: "none",
          color: "white",
          fontSize: 18,
          cursor: "pointer",
          opacity: 0.7,
          padding: 4,
          lineHeight: 1,
        }}
      >
        ×
      </button>
    </div>
  );
}
