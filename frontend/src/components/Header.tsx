"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { getMe, logout } from "@/lib/auth";
import type { UserProfile } from "@/lib/api";

const PLAN_LABEL: Record<string, string> = {
  free: "Free", personal: "Личный", expert: "Эксперт", landlord: "Лендлорд",
};

export default function Header() {
  const pathname = usePathname();
  const [user, setUser] = useState<UserProfile | null>(null);

  useEffect(() => {
    getMe().then(setUser);
  }, []);

  const nav = [
    { href: "/", label: "Карта" },
    { href: "/lots", label: "Каталог" },
    { href: "/pricing", label: "Тарифы" },
  ];

  return (
    <header className="header">
      <Link href="/" className="header-logo">🌍 Земля.ПРО</Link>

      <nav className="header-nav">
        {nav.map((n) => (
          <Link key={n.href} href={n.href} className={pathname === n.href ? "active" : ""}>
            {n.label}
          </Link>
        ))}
      </nav>

      <div className="header-actions">
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
