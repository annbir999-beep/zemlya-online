"use client";
import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await api.post("/api/users/forgot-password", { email });
      setSent(true);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}>
      <div style={{ width: "100%", maxWidth: 400, background: "var(--surface)", padding: 32, borderRadius: 12, boxShadow: "var(--shadow-md)" }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 10 }}>Забыли пароль?</h1>

        {sent ? (
          <>
            <p style={{ fontSize: 14, color: "var(--text-2)", lineHeight: 1.6, marginBottom: 20 }}>
              Если такой email зарегистрирован, письмо со ссылкой уже отправлено.
              Ссылка действует 60 минут. Не пришло за пару минут — загляните в «Спам».
            </p>
            <Link href="/login" className="btn btn-primary" style={{ display: "block", textAlign: "center" }}>
              Вернуться ко входу
            </Link>
          </>
        ) : (
          <>
            <p style={{ fontSize: 14, color: "var(--text-2)", lineHeight: 1.6, marginBottom: 20 }}>
              Укажите email, на который зарегистрирован аккаунт — пришлём ссылку для смены пароля.
            </p>
            <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <input
                className="input"
                type="email"
                autoComplete="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />

              {error && (
                <div style={{ background: "#fee2e2", color: "#dc2626", padding: "8px 12px", borderRadius: 6, fontSize: 13 }}>
                  {error}
                </div>
              )}

              <button className="btn btn-primary" type="submit" disabled={loading}>
                {loading ? "Отправляем..." : "Прислать ссылку"}
              </button>
            </form>
            <p style={{ marginTop: 20, textAlign: "center", fontSize: 13, color: "var(--text-2)" }}>
              Вспомнили пароль? <Link href="/login">Войти</Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
