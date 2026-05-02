"use client";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";

interface TelegramStatus {
  linked: boolean;
  telegram_id?: string | null;
  notifications_enabled: boolean;
  bot_username?: string | null;
  site_url: string;
}

interface LinkCodeResponse {
  code: string;
  bot_username: string;
  deep_link: string;
  expires_in: number;
}

export default function TelegramConnect() {
  const [status, setStatus] = useState<TelegramStatus | null>(null);
  const [code, setCode] = useState<LinkCodeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = () =>
    api
      .get<TelegramStatus>("/api/telegram/status")
      .then(setStatus)
      .catch(() => setStatus(null));

  useEffect(() => {
    refresh();
  }, []);

  const generateCode = async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await api.post<LinkCodeResponse>("/api/telegram/link-code", {});
      setCode(r);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Ошибка";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const unlink = async () => {
    if (!confirm("Отвязать Telegram от аккаунта?")) return;
    setLoading(true);
    try {
      await api.delete("/api/telegram/unlink");
      setCode(null);
      await refresh();
    } finally {
      setLoading(false);
    }
  };

  if (!status) return null;

  return (
    <div
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: 10,
        padding: 20,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12, flexWrap: "wrap", gap: 12 }}>
        <div>
          <div style={{ fontWeight: 600, fontSize: 15 }}>Telegram-уведомления</div>
          <div style={{ fontSize: 13, color: "var(--text-3)", marginTop: 2 }}>
            Получай новые лоты по фильтрам прямо в мессенджере
          </div>
        </div>
        {status.linked ? (
          <span className="badge badge-green">Привязано</span>
        ) : (
          <span className="badge" style={{ background: "var(--surface-2)", color: "var(--text-3)" }}>Не привязано</span>
        )}
      </div>

      {status.linked && (
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <div style={{ fontSize: 13, color: "var(--text-2)" }}>
            ID чата: <code style={{ background: "var(--surface-2)", padding: "2px 6px", borderRadius: 4 }}>{status.telegram_id}</code>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={unlink} disabled={loading}>
            Отвязать
          </button>
        </div>
      )}

      {!status.linked && !code && (
        <button
          className="btn btn-primary btn-sm"
          onClick={generateCode}
          disabled={loading || !status.bot_username}
        >
          {loading ? "..." : "Привязать Telegram"}
        </button>
      )}

      {!status.linked && !status.bot_username && (
        <div style={{ fontSize: 12, color: "var(--text-3)", marginTop: 8 }}>
          Бот пока не настроен — обратитесь к администратору.
        </div>
      )}

      {code && (
        <div
          style={{
            marginTop: 12,
            padding: 14,
            background: "var(--surface-2)",
            borderRadius: 8,
            border: "1px solid var(--border)",
          }}
        >
          <div style={{ fontSize: 13, marginBottom: 10 }}>
            1. Откройте бота:{" "}
            <a href={code.deep_link} target="_blank" rel="noreferrer" style={{ color: "var(--primary)", fontWeight: 600 }}>
              @{code.bot_username}
            </a>
          </div>
          <div style={{ fontSize: 13, marginBottom: 10 }}>
            2. Нажмите <b>Start</b> или отправьте команду:
          </div>
          <div
            style={{
              fontFamily: "monospace",
              fontSize: 16,
              padding: "10px 14px",
              background: "var(--background)",
              borderRadius: 6,
              border: "1px dashed var(--border)",
              userSelect: "all",
              marginBottom: 10,
            }}
          >
            /link {code.code}
          </div>
          <div style={{ fontSize: 12, color: "var(--text-3)" }}>
            Код действует {Math.round(code.expires_in / 60)} минут. После привязки обновите страницу.
          </div>
          <button
            className="btn btn-ghost btn-sm"
            style={{ marginTop: 10 }}
            onClick={async () => {
              setCode(null);
              await refresh();
            }}
          >
            Я уже привязал — обновить статус
          </button>
        </div>
      )}
    </div>
  );
}
