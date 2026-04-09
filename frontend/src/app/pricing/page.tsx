"use client";
import { useState, useEffect } from "react";
import { isAuthenticated } from "@/lib/auth";
import { api } from "@/lib/api";

const PERIOD_LABELS: Record<string, string> = {
  "1": "1 месяц", "3": "3 месяца", "12": "12 месяцев",
};

interface FeatureRow { name: string; value: boolean | string }
interface Plan {
  id: string;
  name: string;
  price?: number;
  prices?: Record<string, number>;
  filters_limit: number;
  popular?: boolean;
  features: string[];
  features_matrix?: FeatureRow[];
}

const PLAN_COLORS: Record<string, string> = {
  free: "#64748b",
  personal: "#0891b2",
  expert: "#2563eb",
  landlord: "#7c3aed",
};

function FeatureValue({ val }: { val: boolean | string }) {
  if (val === true) return <span style={{ color: "#16a34a", fontSize: 18 }}>✓</span>;
  if (val === false) return <span style={{ color: "#cbd5e1", fontSize: 16 }}>—</span>;
  return <span style={{ fontSize: 13, color: "#475569" }}>{val}</span>;
}

export default function PricingPage() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [periods, setPeriods] = useState<Record<string, string>>({
    personal: "1", expert: "3", landlord: "12",
  });
  const [loading, setLoading] = useState<string | null>(null);
  const [view, setView] = useState<"cards" | "table">("cards");

  useEffect(() => {
    api.get<{ plans: Plan[] }>("/api/payments/plans").then((d) => setPlans(d.plans));
  }, []);

  const handleBuy = async (plan: Plan, months: string) => {
    if (!isAuthenticated()) { window.location.href = "/login?redirect=/pricing"; return; }
    setLoading(`${plan.id}-${months}`);
    try {
      const data = await api.post<{ confirmation_url: string }>("/api/payments/create", {
        plan: plan.id, months: Number(months),
        return_url: window.location.origin + "/dashboard",
      });
      window.location.href = data.confirmation_url;
    } catch (e) { alert((e as Error).message); }
    finally { setLoading(null); }
  };

  // Собираем все строки матрицы из первого нефри плана
  const matrixRows = plans.find(p => p.features_matrix)?.features_matrix?.map(f => f.name) || [];

  return (
    <div style={{ flex: 1, overflow: "auto", background: "var(--bg)" }}>
      <div style={{ maxWidth: 1100, margin: "0 auto", padding: "40px 24px" }}>
        <h1 style={{ textAlign: "center", fontSize: 30, fontWeight: 700, marginBottom: 8 }}>
          Тарифные планы
        </h1>
        <p style={{ textAlign: "center", color: "var(--text-2)", marginBottom: 28 }}>
          Оплата через ЮКассу. Отмена в любой момент.
        </p>

        {/* View toggle */}
        <div style={{ display: "flex", justifyContent: "center", marginBottom: 32 }}>
          <div className="view-toggle">
            <button className={view === "cards" ? "active" : ""} onClick={() => setView("cards")}>
              Карточки
            </button>
            <button className={view === "table" ? "active" : ""} onClick={() => setView("table")}>
              Сравнение
            </button>
          </div>
        </div>

        {/* ── Cards view ── */}
        {view === "cards" && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(230px, 1fr))", gap: 20 }}>
            {plans.map((plan) => {
              const isFree = plan.id === "free";
              const period = periods[plan.id] || "1";
              const price = plan.prices ? plan.prices[period] : plan.price;
              const color = PLAN_COLORS[plan.id] || "#2563eb";

              return (
                <div key={plan.id} style={{
                  background: "var(--surface)",
                  border: plan.popular ? `2px solid ${color}` : "1px solid var(--border)",
                  borderRadius: 14,
                  overflow: "hidden",
                  boxShadow: plan.popular ? "var(--shadow-md)" : "var(--shadow)",
                  display: "flex",
                  flexDirection: "column",
                  position: "relative",
                }}>
                  {plan.popular && (
                    <div style={{
                      background: color, color: "#fff",
                      textAlign: "center", padding: "4px 0",
                      fontSize: 12, fontWeight: 600,
                    }}>
                      Популярный
                    </div>
                  )}

                  {/* Plan header */}
                  <div style={{ background: color, padding: "20px 20px 16px", color: "#fff" }}>
                    <div style={{ fontSize: 20, fontWeight: 700, marginBottom: 2 }}>{plan.name}</div>
                    <div style={{ fontSize: 12, opacity: 0.8 }}>
                      {isFree ? "Всегда бесплатно" : `До ${plan.filters_limit} сохранённых фильтров`}
                    </div>
                  </div>

                  <div style={{ padding: 20, flex: 1, display: "flex", flexDirection: "column", gap: 16 }}>
                    {/* Period selector */}
                    {plan.prices && (
                      <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                        {Object.keys(plan.prices).map((m) => (
                          <button key={m}
                            className={`btn btn-sm ${period === m ? "btn-primary" : "btn-secondary"}`}
                            onClick={() => setPeriods(p => ({ ...p, [plan.id]: m }))}
                          >
                            {m} мес.
                          </button>
                        ))}
                      </div>
                    )}

                    {/* Price */}
                    <div>
                      {isFree ? (
                        <div style={{ fontSize: 30, fontWeight: 800, color }}>Бесплатно</div>
                      ) : (
                        <>
                          <div style={{ fontSize: 30, fontWeight: 800, color }}>
                            {price?.toLocaleString("ru")} ₽
                          </div>
                          <div style={{ fontSize: 12, color: "var(--text-3)" }}>
                            {PERIOD_LABELS[period]}
                            {price && Number(period) > 1 && (
                              <span> · {Math.round(price / Number(period)).toLocaleString("ru")} ₽/мес</span>
                            )}
                          </div>
                        </>
                      )}
                    </div>

                    {/* Features */}
                    <ul style={{ listStyle: "none", flex: 1, display: "flex", flexDirection: "column", gap: 6 }}>
                      {plan.features.map((f, i) => (
                        <li key={i} style={{ fontSize: 13, color: "var(--text-2)", display: "flex", gap: 8 }}>
                          <span style={{ color: color, flexShrink: 0 }}>✓</span> {f}
                        </li>
                      ))}
                    </ul>

                    {/* CTA */}
                    {isFree ? (
                      <button className="btn btn-secondary" style={{ width: "100%" }} disabled>
                        Текущий план
                      </button>
                    ) : (
                      <button
                        className="btn btn-primary"
                        style={{ width: "100%", background: color, borderColor: color }}
                        disabled={loading === `${plan.id}-${period}`}
                        onClick={() => handleBuy(plan, period)}
                      >
                        {loading === `${plan.id}-${period}` ? "Перенаправление..." : "Купить →"}
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* ── Table view (comparison matrix) ── */}
        {view === "table" && plans.length > 0 && (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", background: "var(--surface)", borderRadius: 12, overflow: "hidden", boxShadow: "var(--shadow)" }}>
              <thead>
                <tr>
                  <th style={{ padding: "16px 20px", textAlign: "left", fontWeight: 600, fontSize: 14, borderBottom: "2px solid var(--border)", width: "35%", color: "var(--text-2)" }}>
                    Функция
                  </th>
                  {plans.map(p => (
                    <th key={p.id} style={{
                      padding: "16px 12px", textAlign: "center",
                      fontWeight: 700, fontSize: 15,
                      borderBottom: "2px solid var(--border)",
                      color: PLAN_COLORS[p.id],
                      background: p.popular ? "#eff6ff" : "transparent",
                    }}>
                      {p.name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {/* Цена */}
                <tr style={{ background: "var(--surface-2)" }}>
                  <td style={{ padding: "12px 20px", fontSize: 13, fontWeight: 600, color: "var(--text-2)" }}>
                    Цена
                  </td>
                  {plans.map(p => {
                    const isFree = p.id === "free";
                    const period = periods[p.id] || "1";
                    const price = p.prices ? p.prices[period] : p.price;
                    return (
                      <td key={p.id} style={{ padding: "12px 12px", textAlign: "center", background: p.popular ? "#eff6ff" : "transparent" }}>
                        {isFree ? (
                          <span style={{ fontWeight: 700, color: PLAN_COLORS[p.id] }}>0 ₽</span>
                        ) : (
                          <div>
                            <div style={{ fontWeight: 700, color: PLAN_COLORS[p.id] }}>
                              {price?.toLocaleString("ru")} ₽
                            </div>
                            <div style={{ fontSize: 11, color: "var(--text-3)" }}>
                              {PERIOD_LABELS[period]}
                            </div>
                            {p.prices && (
                              <div style={{ display: "flex", gap: 3, justifyContent: "center", marginTop: 4, flexWrap: "wrap" }}>
                                {Object.keys(p.prices).map(m => (
                                  <button key={m}
                                    style={{
                                      padding: "1px 6px", fontSize: 11, borderRadius: 4, cursor: "pointer",
                                      background: period === m ? PLAN_COLORS[p.id] : "transparent",
                                      color: period === m ? "#fff" : "var(--text-3)",
                                      border: `1px solid ${period === m ? PLAN_COLORS[p.id] : "var(--border)"}`,
                                    }}
                                    onClick={() => setPeriods(pr => ({ ...pr, [p.id]: m }))}
                                  >
                                    {m}м
                                  </button>
                                ))}
                              </div>
                            )}
                          </div>
                        )}
                      </td>
                    );
                  })}
                </tr>

                {/* Feature rows */}
                {matrixRows.map((rowName, i) => (
                  <tr key={rowName} style={{ background: i % 2 === 0 ? "var(--surface)" : "var(--surface-2)" }}>
                    <td style={{ padding: "12px 20px", fontSize: 13, color: "var(--text)" }}>
                      {rowName}
                    </td>
                    {plans.map(p => {
                      const feat = p.features_matrix?.find(f => f.name === rowName);
                      return (
                        <td key={p.id} style={{
                          padding: "12px 12px", textAlign: "center",
                          background: p.popular ? "#eff6ff" : "transparent",
                        }}>
                          {feat ? <FeatureValue val={feat.value} /> : <span style={{ color: "#cbd5e1" }}>—</span>}
                        </td>
                      );
                    })}
                  </tr>
                ))}

                {/* CTA row */}
                <tr>
                  <td style={{ padding: "16px 20px", fontWeight: 600, fontSize: 13 }}>
                    Оформить
                  </td>
                  {plans.map(p => {
                    const isFree = p.id === "free";
                    const period = periods[p.id] || "1";
                    return (
                      <td key={p.id} style={{ padding: "16px 12px", textAlign: "center", background: p.popular ? "#eff6ff" : "transparent" }}>
                        {isFree ? (
                          <span style={{ fontSize: 13, color: "var(--text-3)" }}>Всегда доступно</span>
                        ) : (
                          <button
                            className="btn btn-primary btn-sm"
                            style={{ background: PLAN_COLORS[p.id] }}
                            disabled={loading === `${p.id}-${period}`}
                            onClick={() => handleBuy(p, period)}
                          >
                            Купить
                          </button>
                        )}
                      </td>
                    );
                  })}
                </tr>
              </tbody>
            </table>
          </div>
        )}

        <p style={{ textAlign: "center", color: "var(--text-3)", fontSize: 12, marginTop: 32 }}>
          Оплата через ЮКассу. При вопросах —{" "}
          <a href="mailto:support@zemlya.pro">support@zemlya.pro</a>
        </p>
      </div>
    </div>
  );
}
