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
      background: "radial-gradient(800px 120px at 70% 0%, rgba(45,212,191,0.16), transparent 70%), linear-gradient(90deg, #0a1120 0%, #0d1b2e 100%)",
      borderBottom: "1px solid rgba(45,212,191,0.18)",
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
        <span style={{ opacity: 0.75, fontWeight: 400, marginLeft: 8 }}>
          Дисконты до 80%, AI-аудит каждого лота, региональная аналитика.
        </span>
      </span>
      <Link
        href="/audit-lot"
        style={{
          background: "linear-gradient(135deg, #059669 0%, #0d9488 55%, #0ea5b7 100%)",
          color: "#fff",
          padding: "6px 16px",
          borderRadius: 10,
          textDecoration: "none",
          fontWeight: 700,
          fontSize: 13,
          whiteSpace: "nowrap",
          boxShadow: "0 2px 14px rgba(13,148,136,0.45)",
        }}
      >
        Бесплатный аудит →
      </Link>
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
