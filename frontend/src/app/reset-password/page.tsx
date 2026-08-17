"use client";
import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { api, setTokens } from "@/lib/api";

function ResetForm() {
  const router = useRouter();
  const params = useSearchParams();
  const token = params.get("token") || "";

  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (password.length < 8) {
      setError("Пароль должен быть не короче 8 символов");
      return;
    }
    if (password !== repeat) {
      setError("Пароли не совпадают");
      return;
    }
    setLoading(true);
    try {
      const res = await api.post<{ access_token: string; refresh_token: string }>(
        "/api/users/reset-password",
        { token, password },
      );
      // Бэкенд сразу возвращает пару токенов — логинимся, чтобы не вводить пароль дважды.
      setTokens(res.access_token, res.refresh_token);
      router.push("/dashboard");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}>
      <div style={{ width: "100%", maxWidth: 400, background: "var(--surface)", padding: 32, borderRadius: 12, boxShadow: "var(--shadow-md)" }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 10 }}>Новый пароль</h1>

        {!token ? (
          <>
            <p style={{ fontSize: 14, color: "var(--text-2)", lineHeight: 1.6, marginBottom: 20 }}>
              Ссылка неполная — в ней нет кода подтверждения. Запросите письмо заново.
            </p>
            <Link href="/forgot-password" className="btn btn-primary" style={{ display: "block", textAlign: "center" }}>
              Запросить ссылку
            </Link>
          </>
        ) : (
          <>
            <p style={{ fontSize: 14, color: "var(--text-2)", lineHeight: 1.6, marginBottom: 20 }}>
              Придумайте новый пароль — минимум 8 символов.
            </p>
            <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <div>
                <label style={{ fontSize: 13, fontWeight: 500, display: "block", marginBottom: 6 }}>Новый пароль</label>
                <input
                  className="input"
                  type="password"
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </div>
              <div>
                <label style={{ fontSize: 13, fontWeight: 500, display: "block", marginBottom: 6 }}>Ещё раз</label>
                <input
                  className="input"
                  type="password"
                  autoComplete="new-password"
                  value={repeat}
                  onChange={(e) => setRepeat(e.target.value)}
                  required
                />
              </div>

              {error && (
                <div style={{ background: "#fee2e2", color: "#dc2626", padding: "8px 12px", borderRadius: 6, fontSize: 13 }}>
                  {error}
                </div>
              )}

              <button className="btn btn-primary" type="submit" disabled={loading}>
                {loading ? "Сохраняем..." : "Сохранить и войти"}
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense>
      <ResetForm />
    </Suspense>
  );
}
