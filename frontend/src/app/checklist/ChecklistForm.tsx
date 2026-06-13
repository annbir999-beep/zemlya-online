"use client";
import { useState } from "react";
import { api } from "@/lib/api";

interface ChecklistResponse {
  ok: boolean;
  email_sent: boolean;
  download_url: string;
}

// Простая клиентская валидация — отсекает явный мусор, серьёзную проверку делает бэкенд.
function isValidEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

// utm атрибутируем так же, как UtmCapture: сначала query-параметры текущего URL,
// потом сохранённые ранее значения из sessionStorage (юзер мог зайти с utm, погулять
// по сайту и вернуться на лендинг чеклиста уже без меток в адресе).
function readUtm(): { utm_source?: string; utm_campaign?: string } {
  if (typeof window === "undefined") return {};
  const params = new URLSearchParams(window.location.search);
  const src = params.get("utm_source") || sessionStorage.getItem("utm_source") || undefined;
  const camp = params.get("utm_campaign") || sessionStorage.getItem("utm_campaign") || undefined;
  const out: { utm_source?: string; utm_campaign?: string } = {};
  if (src) out.utm_source = src;
  if (camp) out.utm_campaign = camp;
  return out;
}

export default function ChecklistForm() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [sentTo, setSentTo] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = email.trim();
    if (!isValidEmail(trimmed)) {
      setError("Введите корректный email");
      return;
    }
    setError("");
    setLoading(true);
    try {
      await api.post<ChecklistResponse>("/api/leads/checklist", {
        email: trimmed,
        ...readUtm(),
      });
      setSentTo(trimmed);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  if (sentTo) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <div style={{ background: "#dcfce7", color: "#15803d", padding: "14px 16px", borderRadius: 8, fontSize: 14, lineHeight: 1.5 }}>
          Чеклист отправлен на {sentTo}. Проверьте почту (и папку «Спам»).
        </div>
        <a
          className="btn btn-primary"
          href="/api/leads/checklist.pdf"
          target="_blank"
          rel="noopener noreferrer"
          style={{ textAlign: "center" }}
        >
          Скачать сейчас
        </a>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <input
        className="input"
        type="email"
        autoComplete="email"
        placeholder="Ваш email"
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
        {loading ? "Отправляем…" : "Получить чеклист"}
      </button>

      <p style={{ fontSize: 12, color: "var(--text-3)", textAlign: "center", margin: 0 }}>
        Отправим PDF на почту. Без спама — только по делу.
      </p>
    </form>
  );
}
