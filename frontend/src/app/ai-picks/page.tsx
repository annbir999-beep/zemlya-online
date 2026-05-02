"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

interface AIBlock {
  score?: number;
  best_strategy?: string;
  summary?: string;
  recommended_use?: string;
  price_estimate?: { min?: number; max?: number; comment?: string };
  pros?: string[];
  assessed_at?: string;
}

interface AIPick {
  id: number;
  title?: string;
  start_price?: number;
  area_sqm?: number;
  region_name?: string;
  score?: number;
  discount_to_market_pct?: number;
  ai: AIBlock;
}

interface Response {
  items: AIPick[];
  total: number;
  page: number;
  pages: number;
}

const fmtPrice = (v?: number) =>
  v != null ? `${Math.round(v).toLocaleString("ru")} ₽` : "—";

const fmtArea = (v?: number) => {
  if (v == null) return "—";
  return v >= 10000 ? `${(v / 10000).toFixed(2)} га` : `${Math.round(v).toLocaleString("ru")} м²`;
};

export default function AIPicksPage() {
  const [data, setData] = useState<Response | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api
      .get<Response>(`/api/lots/ai-picks?page=${page}&per_page=20`)
      .then(setData)
      .finally(() => setLoading(false));
  }, [page]);

  return (
    <div style={{ flex: 1, overflow: "auto", padding: "32px 24px", maxWidth: 1100, margin: "0 auto", width: "100%" }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 6 }}>🔥 ИИ-разборы лотов</h1>
      <p style={{ color: "var(--text-3)", fontSize: 14, marginBottom: 24 }}>
        Топ участков с готовым анализом от Claude — стратегия заработка, плюсы/минусы, оценка рынка.
        Обновляется каждую ночь, всё открывается мгновенно.
      </p>

      {loading && !data && <div style={{ color: "var(--text-3)" }}>Загрузка...</div>}

      {data && data.items.length === 0 && (
        <div style={{ padding: 40, textAlign: "center", color: "var(--text-3)", background: "var(--surface)", borderRadius: 10, border: "1px solid var(--border)" }}>
          Пока нет готовых разборов. Они появятся после первого ночного прогона (06:30 МСК).
        </div>
      )}

      <div style={{ display: "grid", gap: 14 }}>
        {data?.items.map((lot) => (
          <Link
            key={lot.id}
            href={`/lots/${lot.id}`}
            style={{
              background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12,
              padding: 18, textDecoration: "none", color: "inherit", display: "block",
              transition: "border-color .15s",
            }}
          >
            <div style={{ display: "flex", gap: 12, alignItems: "flex-start", marginBottom: 10, flexWrap: "wrap" }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 4, wordBreak: "break-word" }}>
                  {lot.title || `Лот #${lot.id}`}
                </div>
                <div style={{ fontSize: 13, color: "var(--text-3)" }}>
                  {lot.region_name && <span>📍 {lot.region_name}</span>}
                  {lot.area_sqm && <span>  ·  📐 {fmtArea(lot.area_sqm)}</span>}
                  {lot.start_price && <span>  ·  💰 {fmtPrice(lot.start_price)}</span>}
                </div>
              </div>
              <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
                {lot.ai?.score != null && (
                  <span className="badge" style={{
                    background: "linear-gradient(135deg, var(--primary), #7c3aed)",
                    color: "white", fontWeight: 600,
                  }}>
                    🤖 {lot.ai.score}/10
                  </span>
                )}
                {lot.discount_to_market_pct != null && lot.discount_to_market_pct > 0 && (
                  <span className="badge badge-green">−{Math.round(lot.discount_to_market_pct)}% к рынку</span>
                )}
              </div>
            </div>

            {lot.ai?.best_strategy && (
              <div style={{ fontSize: 13, color: "var(--text-2)", marginBottom: 6 }}>
                <b>Стратегия:</b> {lot.ai.best_strategy}
              </div>
            )}

            {lot.ai?.summary && (
              <div style={{
                fontSize: 13, color: "var(--text-2)", lineHeight: 1.5,
                background: "var(--surface-2)", borderRadius: 8, padding: "10px 12px",
                marginBottom: 8,
              }}>
                {lot.ai.summary}
              </div>
            )}

            {lot.ai?.pros && lot.ai.pros.length > 0 && (
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {lot.ai.pros.slice(0, 3).map((p, i) => (
                  <span
                    key={i}
                    style={{
                      fontSize: 12, color: "var(--success, #16a34a)",
                      background: "rgba(22,163,74,.08)", padding: "3px 8px", borderRadius: 6,
                    }}
                  >
                    ✓ {p}
                  </span>
                ))}
              </div>
            )}
          </Link>
        ))}
      </div>

      {data && data.pages > 1 && (
        <div style={{ display: "flex", justifyContent: "center", gap: 8, marginTop: 24 }}>
          <button
            className="btn btn-secondary btn-sm"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            ← Назад
          </button>
          <span style={{ alignSelf: "center", color: "var(--text-3)", fontSize: 13 }}>
            {page} / {data.pages}
          </span>
          <button
            className="btn btn-secondary btn-sm"
            disabled={page >= data.pages}
            onClick={() => setPage((p) => p + 1)}
          >
            Вперёд →
          </button>
        </div>
      )}
    </div>
  );
}
