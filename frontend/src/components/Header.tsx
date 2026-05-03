"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { getMe, logout } from "@/lib/auth";
import type { UserProfile } from "@/lib/api";
import { useCompareIds } from "@/lib/useCompare";

const PLAN_LABEL: Record<string, string> = {
  free: "Free", personal: "Личный", expert: "Эксперт", landlord: "Лендлорд",
};

export default function Header() {
  const pathname = usePathname();
  const [user, setUser] = useState<UserProfile | null>(null);
  const compareIds = useCompareIds();
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    getMe().then(setUser);
  }, []);

  const nav = [
    { href: "/", label: "Карта", icon: "🗺" },
    { href: "/lots", label: "Лоты", icon: "🔥" },
    { href: "/ai-picks", label: "ИИ-разборы", icon: "🤖" },
    { href: "/analytics", label: "Аналитика", icon: "📊" },
    { href: "/strategies", label: "Стратегии", icon: "💎" },
    { href: "/pricing", label: "Тарифы", icon: "⚡" },
  ];

  return (
    <header className="header">
      <Link href="/" className="header-logo" style={{ display: "flex", alignItems: "center", gap: 10, textDecoration: "none" }}>
        {/* Modern logo: gradient square with letter "З" + clean wordmark */}
        <span style={{
          width: 36, height: 36, borderRadius: 10,
          background: "linear-gradient(135deg, #16a34a 0%, #0d9488 100%)",
          display: "inline-flex", alignItems: "center", justifyContent: "center",
          color: "white", fontWeight: 800, fontSize: 18,
          boxShadow: "0 2px 8px rgba(13, 148, 136, 0.3)",
        }}>
          З
        </span>
        <span style={{ display: "flex", flexDirection: "column", lineHeight: 1 }}>
          <span style={{ fontSize: 17, fontWeight: 800, letterSpacing: "-0.02em", color: "var(--text)" }}>
            земля<span style={{ color: "#16a34a" }}>.online</span>
          </span>
          <span style={{ fontSize: 10, color: "var(--text-3)", marginTop: 2, letterSpacing: "0.05em", textTransform: "uppercase" }}>
            аукционы земли РФ
          </span>
        </span>
      </Link>

      <nav className="header-nav">
        {nav.map((n) => (
          <Link key={n.href} href={n.href} className={pathname === n.href ? "active" : ""}>
            <span style={{ marginRight: 6 }}>{n.icon}</span>{n.label}
          </Link>
        ))}
      </nav>

      {/* Burger — только на мобиле */}
      <button
        className="header-burger"
        onClick={() => setMobileOpen((v) => !v)}
        aria-label="Меню"
        style={{
          display: "none", border: "none", background: "transparent",
          fontSize: 22, padding: "4px 10px", cursor: "pointer",
          color: "var(--text-2)",
        }}
      >
        {mobileOpen ? "✕" : "☰"}
      </button>

      {/* Мобильное меню — выпадает поверх */}
      {mobileOpen && (
        <div
          className="header-mobile-menu"
          onClick={() => setMobileOpen(false)}
          style={{
            position: "fixed", top: 56, left: 0, right: 0, bottom: 0,
            background: "rgba(0,0,0,0.4)", zIndex: 999,
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: "var(--surface)", borderTop: "1px solid var(--border)",
              padding: 16, display: "flex", flexDirection: "column", gap: 4,
            }}
          >
            {nav.map((n) => (
              <Link
                key={n.href}
                href={n.href}
                onClick={() => setMobileOpen(false)}
                style={{
                  padding: "12px 14px", borderRadius: 8,
                  textDecoration: "none",
                  color: pathname === n.href ? "var(--primary)" : "var(--text-2)",
                  fontWeight: pathname === n.href ? 600 : 400,
                  background: pathname === n.href ? "var(--surface-2)" : "transparent",
                }}
              >
                <span style={{ marginRight: 10 }}>{n.icon}</span>{n.label}
              </Link>
            ))}
            {compareIds.length > 0 && (
              <Link
                href={`/compare?ids=${compareIds.join(",")}`}
                onClick={() => setMobileOpen(false)}
                style={{ padding: "12px 14px", borderRadius: 8, color: "var(--primary)", textDecoration: "none" }}
              >
                ⚖ Сравнение ({compareIds.length})
              </Link>
            )}
          </div>
        </div>
      )}

      <div className="header-actions">
        {compareIds.length > 0 && (
          <Link
            href={`/compare?ids=${compareIds.join(",")}`}
            className="btn btn-secondary btn-sm"
            title="Сравнение участков"
          >
            ⚖ {compareIds.length}
          </Link>
        )}
        {user ? (
          <>
            <span className="badge badge-blue">{PLAN_LABEL[user.subscription_plan] || user.subscription_plan}</span>
            <Link href="/dashboard" className="btn btn-secondary btn-sm">Кабинет</Link>
            <button className="btn btn-ghost btn-sm" onClick={logout}>Выйти</button>
          </>
        ) : (
          <>
            <Link href="/login" className="btn btn-secondary btn-sm">Войти</Link>
            <Link href="/register" className="btn btn-primary btn-sm">Регистрация</Link>
          </>
        )}
      </div>
    </header>
  );
}
