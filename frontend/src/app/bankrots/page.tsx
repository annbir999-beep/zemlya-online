"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import type { LotsResponse } from "@/lib/api";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

type Tab = "all" | "sale" | "rent";

function fmtPrice(n?: number) {
  if (!n) return "—";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)} млн ₽`;
  return `${(n / 1_000).toFixed(0)} тыс. ₽`;
}

function fmtArea(sqm?: number) {
  if (!sqm) return "—";
  if (sqm >= 10_000) return `${(sqm / 10_000).toFixed(2)} га`;
  return `${sqm.toLocaleString("ru")} м²`;
}

function fmtDate(iso?: string) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("ru", { day: "2-digit", month: "2-digit", year: "2-digit" });
}

export default function BankrotsPage() {
  const [tab, setTab] = useState<Tab>("all");
  const [data, setData] = useState<LotsResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    const qs = new URLSearchParams({
      is_bankruptcy: "true",
      status: "active",
      sort_by: "score",
      sort_order: "desc",
      per_page: "30",
    });
    if (tab === "sale") qs.append("auction_type", "sale");
    if (tab === "rent") qs.append("auction_type", "rent");
    fetch(`${API}/api/lots?${qs}`)
      .then((r) => r.json())
      .then((d) => setData(d))
      .finally(() => setLoading(false));
  }, [tab]);

  const tabs: { v: Tab; l: string }[] = [
    { v: "all", l: "Все" },
    { v: "sale", l: "Покупка" },
    { v: "rent", l: "Аренда" },
  ];

  return (
    <div style={{ flex: 1, overflow: "auto", padding: "24px 20px", maxWidth: 1000, margin: "0 auto", width: "100%" }}>
      <h1 style={{ fontSize: 26, fontWeight: 700, marginBottom: 8 }}>🔨 Имущество банкротов</h1>
      <p style={{ color: "var(--text-3)", fontSize: 14, marginBottom: 20, lineHeight: 1.6 }}>
        Земельные участки от арбитражных управляющих и конкурсных производств — банкротное имущество физлиц и компаний.
        Реализуется с дисконтом 30-70% от рыночной цены: первые торги по оценочной стоимости, затем повторные с понижением,
        затем публичное предложение (цена опускается по графику). Подходит для флипа и быстрой сдачи в аренду.
      </p>

      <div style={{
        background: "linear-gradient(135deg, #fef3c7 0%, #fde68a 100%)",
        border: "1px solid #fcd34d", borderRadius: 10, padding: 14,
        marginBottom: 20, fontSize: 13, lineHeight: 1.55, color: "#78350f",
      }}>
        <div style={{ fontWeight: 700, marginBottom: 6 }}>💡 Как покупать на банкротных торгах</div>
        <ol style={{ margin: 0, paddingLeft: 18 }}>
          <li>Зарегистрироваться на ЭТП (РТС-тендер, Сбер-АСТ, B2B-Center, М-ЕТС) — обычно бесплатно</li>
          <li>Внести задаток (5-20% от стартовой цены) — возвращается при проигрыше</li>
          <li>Подать заявку до окончания приёма — на этапе аукциона или публичного предложения</li>
          <li>Самые выгодные цены — на этапе публичного предложения, когда цена снижается ежедневно</li>
        </ol>
      </div>

      <div style={{ display: "flex", gap: 6, marginBottom: 16, flexWrap: "wrap" }}>
        {tabs.map((t) => (
          <button
            key={t.v}
            onClick={() => setTab(t.v)}
            className={tab === t.v ? "btn btn-primary btn-sm" : "btn btn-secondary btn-sm"}
            style={{ minWidth: 90 }}
          >
            {t.l}
          </button>
        ))}
      </div>

      {loading && (
        <div style={{ padding: 20, textAlign: "center", color: "var(--text-3)" }}>
          Загружаем...
        </div>
      )}

      {!loading && data && data.total === 0 && (
        <div style={{
          padding: 24, textAlign: "center", color: "var(--text-3)",
          background: "var(--surface)", border: "1px dashed var(--border)", borderRadius: 12,
        }}>
          <div style={{ fontSize: 16, fontWeight: 600, color: "var(--text-2)", marginBottom: 6 }}>
            Пока нет активных банкротных лотов{tab !== "all" ? " по этому фильтру" : ""}
          </div>
          <div style={{ fontSize: 13, lineHeight: 1.5 }}>
            Мы парсим torgi.gov и выделяем лоты от арбитражных управляющих по ключевым словам.
            Скоро добавим парсинг bankrot.fedresurs.ru и федеральных ЭТП (РТС-тендер, Сбер-АСТ).
          </div>
        </div>
      )}

      {!loading && data && data.total > 0 && (
        <>
          <div style={{ fontSize: 13, color: "var(--text-3)", marginBottom: 12 }}>
            Найдено: <b style={{ color: "var(--text)" }}>{data.total}</b>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 10 }}>
            {data.items.map((lot) => (
              <Link
                key={lot.id}
                href={`/lots/${lot.id}`}
                style={{
                  display: "block", padding: 14,
                  border: "1px solid var(--border)", borderRadius: 10,
                  textDecoration: "none", color: "var(--text)",
                  background: "var(--surface)",
                  transition: "background 0.15s",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginBottom: 6 }}>
                  <div style={{ fontWeight: 600, fontSize: 14, flex: 1 }}>
                    {lot.title || `Лот #${lot.id}`}
                  </div>
                  {lot.score != null && (
                    <span style={{
                      background: lot.score >= 60 ? "#16a34a" : "#64748b",
                      color: "white", padding: "2px 8px", borderRadius: 10, fontSize: 11, fontWeight: 700,
                    }}>
                      {lot.score}
                    </span>
                  )}
                </div>
                {lot.address && (
                  <div style={{ fontSize: 12, color: "var(--text-2)", marginBottom: 6 }}>📍 {lot.address}</div>
                )}
                <div style={{ display: "flex", gap: 14, fontSize: 12, color: "var(--text-3)", flexWrap: "wrap" }}>
                  <span><b style={{ color: "var(--text)" }}>{fmtPrice(lot.start_price)}</b></span>
                  <span>{fmtArea(lot.area_sqm)}</span>
                  {lot.submission_end && <span>до {fmtDate(lot.submission_end)}</span>}
                  {lot.discount_to_market_pct != null && lot.discount_to_market_pct > 0 && (
                    <span style={{ color: "#16a34a", fontWeight: 600 }}>
                      −{Math.round(lot.discount_to_market_pct)}% к рынку
                    </span>
                  )}
                </div>
              </Link>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
