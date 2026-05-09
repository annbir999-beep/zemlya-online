"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

interface ReferralData {
  code: string;
  url: string;
  invited_count: number;
  invited_paying: number;
  free_audits_left: number;
}

export default function ReferralCard() {
  const [data, setData] = useState<ReferralData | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    api.get<ReferralData>("/api/users/referral").then(setData).catch(() => {});
  }, []);

  if (!data) return null;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(data.url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      alert("Не удалось скопировать. Выделите ссылку и нажмите Ctrl+C");
    }
  };

  const shareTelegram = () => {
    const text = `Земля.ОНЛАЙН — AI-аудит земельных лотов с torgi.gov. Регистрируйся по моей ссылке, и оба получим бесплатный аудит:`;
    const url = `https://t.me/share/url?url=${encodeURIComponent(data.url)}&text=${encodeURIComponent(text)}`;
    window.open(url, "_blank");
  };

  return (
    <div style={{
      background: "var(--surface)", border: "1px solid var(--border)",
      borderRadius: 12, padding: 20,
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12, gap: 12 }}>
        <div>
          <div style={{ fontWeight: 600, fontSize: 15 }}>🎁 Пригласить друга</div>
          <div style={{ fontSize: 13, color: "var(--text-3)", marginTop: 2 }}>
            +1 бесплатный AI-аудит вам обоим. Ещё +1 — когда друг сделает первую покупку.
          </div>
        </div>
        {data.invited_count > 0 && (
          <span className="badge badge-green" style={{ flexShrink: 0 }}>
            Приглашено: {data.invited_count}
          </span>
        )}
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
        <input
          className="input"
          readOnly
          value={data.url}
          onClick={(e) => (e.target as HTMLInputElement).select()}
          style={{ flex: 1, fontSize: 13 }}
        />
        <button className="btn btn-primary btn-sm" onClick={copy}>
          {copied ? "✓ Скопировано" : "Копировать"}
        </button>
      </div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
        <button className="btn btn-secondary btn-sm" onClick={shareTelegram}>
          ✈️ Поделиться в Telegram
        </button>
        <a
          href={`mailto:?subject=${encodeURIComponent("Земля.ОНЛАЙН — AI-аудит земельных лотов")}&body=${encodeURIComponent("Регистрируйся по моей ссылке, и оба получим бесплатный AI-аудит лота: " + data.url)}`}
          className="btn btn-secondary btn-sm"
        >
          📧 Email
        </a>
      </div>

      <div style={{ display: "flex", gap: 18, fontSize: 12, color: "var(--text-3)", marginTop: 10, paddingTop: 10, borderTop: "1px solid var(--border)" }}>
        <span>Ваш код: <code style={{ background: "var(--surface-2)", padding: "1px 6px", borderRadius: 3 }}>{data.code}</code></span>
        <span>Из них купили: <b>{data.invited_paying}</b></span>
        <span>Бесплатных аудитов: <b>{data.free_audits_left}</b></span>
      </div>
    </div>
  );
}
