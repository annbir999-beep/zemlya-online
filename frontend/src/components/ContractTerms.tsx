"use client";
import { useState } from "react";

export interface ContractData {
  assignment?: "forbidden" | "with_notice" | "with_consent" | "allowed";
  sublease?: "forbidden" | "with_consent" | "allowed";
  lease_term_years?: number;
  penalty_pct?: number;
  development_deadline_years?: number;
  has_strict_termination?: boolean;
}

const ASSIGN_CFG: Record<string, { label: string; color: string; bg: string }> = {
  forbidden:    { label: "Цессия запрещена",                           color: "#991b1b", bg: "#fee2e2" },
  with_notice:  { label: "Можно с уведомлением арендодателя",           color: "#15803d", bg: "#dcfce7" },
  with_consent: { label: "Только с письменным согласием арендодателя",  color: "#854d0e", bg: "#fef3c7" },
  allowed:      { label: "Цессия разрешена без условий",                color: "#166534", bg: "#dcfce7" },
};
const SUB_CFG: Record<string, { label: string; color: string; bg: string }> = {
  forbidden:    { label: "Субаренда запрещена",                  color: "#991b1b", bg: "#fee2e2" },
  with_consent: { label: "Субаренда — с согласия арендодателя",  color: "#854d0e", bg: "#fef3c7" },
  allowed:      { label: "Субаренда разрешена",                  color: "#166534", bg: "#dcfce7" },
};

export function ContractTerms({ data }: { data: ContractData | null }) {
  if (!data || Object.keys(data).length === 0) return null;
  const a = data.assignment ? ASSIGN_CFG[data.assignment] : null;
  const s = data.sublease ? SUB_CFG[data.sublease] : null;

  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: 16, marginBottom: 16 }}>
      <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 10, display: "flex", alignItems: "center", gap: 6 }}>
        📋 Условия договора <span style={{ fontSize: 11, fontWeight: 400, color: "var(--text-3)" }}>(из проекта договора в PDF)</span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8, fontSize: 13 }}>
        {a && (
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ background: a.bg, color: a.color, padding: "3px 10px", borderRadius: 6, fontWeight: 600 }}>
              🔁 {a.label}
            </span>
          </div>
        )}
        {s && (
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ background: s.bg, color: s.color, padding: "3px 10px", borderRadius: 6, fontWeight: 600 }}>
              🏢 {s.label}
            </span>
          </div>
        )}
        {data.lease_term_years != null && (
          <div style={{ color: "var(--text-2)" }}>
            ⏳ <b>Срок аренды:</b> {data.lease_term_years} лет
          </div>
        )}
        {data.penalty_pct != null && (
          <div style={{ color: "var(--text-2)" }}>
            💸 <b>Штрафные пени:</b> {data.penalty_pct}% (за день просрочки)
          </div>
        )}
        {data.development_deadline_years != null && (
          <div style={{ color: "var(--text-2)" }}>
            🏗 <b>Срок начала освоения:</b> {data.development_deadline_years} лет с момента договора
          </div>
        )}
        {data.has_strict_termination && (
          <div style={{ color: "#991b1b", fontSize: 12 }}>
            ⚠️ В договоре прописаны строгие условия одностороннего расторжения за нарушения
          </div>
        )}
      </div>
      <div style={{ marginTop: 10, fontSize: 11, color: "var(--text-3)" }}>
        Парсинг автоматический по тексту проекта договора. Перед сделкой обязательно прочитайте оригинал!
      </div>
    </div>
  );
}

export function FullDescription({ text }: { text?: string | null }) {
  const [expanded, setExpanded] = useState(false);
  if (!text || text.length < 100) return null;
  const preview = text.slice(0, 400);
  const isLong = text.length > 400;

  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: 16, marginBottom: 16 }}>
      <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 8, display: "flex", alignItems: "center", gap: 6 }}>
        📄 Полное описание <span style={{ fontSize: 11, fontWeight: 400, color: "var(--text-3)" }}>(из извещения PDF)</span>
      </div>
      <div style={{ fontSize: 13, color: "var(--text-2)", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
        {expanded ? text : preview}{!expanded && isLong && "..."}
      </div>
      {isLong && (
        <button
          onClick={() => setExpanded(!expanded)}
          style={{ marginTop: 8, background: "transparent", border: "none", color: "var(--primary)", cursor: "pointer", fontSize: 13, padding: 0 }}
        >
          {expanded ? "Свернуть" : `Развернуть (всего ${text.length.toLocaleString("ru")} символов)`}
        </button>
      )}
    </div>
  );
}
