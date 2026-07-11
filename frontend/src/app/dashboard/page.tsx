"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { api, UserProfile, Alert } from "@/lib/api";
import { getMe, logout } from "@/lib/auth";
import TelegramConnect from "@/components/TelegramConnect";
import ReferralCard from "@/components/ReferralCard";
import CreateAlertModal from "@/components/CreateAlertModal";

const PLAN_LABEL: Record<string, string> = {
  free: "Бесплатный", personal: "Личный", investor: "Инвестор", expert: "Эксперт", landlord: "Лендлорд",
};
const CHANNEL_LABEL: Record<string, string> = { email: "Email", telegram: "Telegram", both: "Email + Telegram" };

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<UserProfile | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [tab, setTab] = useState<"profile" | "alerts" | "history" | "views" | "purchases" | "audits">("profile");
  const [savedLots, setSavedLots] = useState<{ id: number; title: string; start_price?: number; status: string }[]>([]);
  const [views, setViews] = useState<{ id: number; title: string; region_name?: string; start_price?: number; area_sqm?: number; status?: string; score?: number; viewed_at?: string }[]>([]);
  const [purchases, setPurchases] = useState<{ id: number; plan: string; amount: number; currency?: string; months?: number; status: string; created_at?: string; paid_at?: string }[]>([]);
  const [audits, setAudits] = useState<{ lot_id: number; title: string; region_name?: string; start_price?: number; status?: string; audited_at?: string; ai_score?: number; ai_strategy?: string }[]>([]);
  const [auditsLeft, setAuditsLeft] = useState<number>(0);
  const [showCreateAlert, setShowCreateAlert] = useState(false);

  const reloadAlerts = () =>
    api
      .get<Alert[] | { items: Alert[] }>("/api/alerts")
      .then((d) => setAlerts(Array.isArray(d) ? d : (d?.items ?? [])));

  useEffect(() => {
    getMe().then((u) => {
      if (!u) { router.push("/login"); return; }
      setUser(u);
    });
    api.get<Alert[] | { items: Alert[] }>("/api/alerts").then((d) => setAlerts(Array.isArray(d) ? d : (d?.items ?? [])));
    api.get<typeof savedLots | { items: typeof savedLots }>("/api/users/saved-lots").then((d) => setSavedLots(Array.isArray(d) ? d : (d?.items ?? [])));
    api.get<{ items: typeof views }>("/api/users/views").then((d) => setViews(d?.items ?? []));
    api.get<{ items: typeof purchases }>("/api/users/subscriptions").then((d) => setPurchases(d?.items ?? []));
    api.get<{ items: typeof audits; audits_left: number }>("/api/ai/my-audits")
      .then((d) => { setAudits(d?.items ?? []); setAuditsLeft(d?.audits_left ?? 0); })
      .catch(() => {});
  }, [router]);

  const toggleAlert = async (id: number) => {
    const data = await api.patch<{ id: number; is_active: boolean }>(`/api/alerts/${id}/toggle`, {});
    setAlerts((prev) => prev.map((a) => a.id === id ? { ...a, is_active: data.is_active } : a));
  };

  const deleteAlert = async (id: number) => {
    if (!confirm("Удалить фильтр?")) return;
    await api.delete(`/api/alerts/${id}`);
    setAlerts((prev) => prev.filter((a) => a.id !== id));
  };

  const sendTestNotification = async (id: number) => {
    try {
      const r = await api.post<{ sent_email: boolean; sent_telegram: boolean; lots_count: number }>(
        `/api/alerts/${id}/test`, {},
      );
      const channels = [r.sent_email && "email", r.sent_telegram && "Telegram"].filter(Boolean).join(" + ");
      alert(`✅ Отправлено по ${channels} (${r.lots_count} лота для примера). Проверь почту/чат.`);
    } catch (e) {
      alert(e instanceof Error ? `Ошибка: ${e.message}` : "Ошибка отправки");
    }
  };

  if (!user) return <div style={{ padding: 40, textAlign: "center", color: "var(--text-3)" }}>Загрузка...</div>;

  return (
    <div style={{ flex: 1, overflow: "auto", padding: "32px 24px", maxWidth: 900, margin: "0 auto", width: "100%" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 28 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700 }}>Личный кабинет</h1>
        <button className="btn btn-ghost btn-sm" onClick={logout}>Выйти</button>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 4, borderBottom: "1px solid var(--border)", marginBottom: 24 }}>
        {(["profile", "alerts", "history", "views", "purchases", "audits"] as const).map((t) => (
          <button
            key={t}
            className="btn btn-ghost"
            style={{
              borderRadius: "6px 6px 0 0",
              borderBottom: tab === t ? "2px solid var(--primary)" : "2px solid transparent",
              color: tab === t ? "var(--primary)" : "var(--text-2)",
              fontWeight: tab === t ? 600 : 400,
            }}
            onClick={() => setTab(t)}
          >
            {{ profile: "Профиль", alerts: `Фильтры (${alerts.length})`, history: `Избранное (${savedLots.length})`, views: `История (${views.length})`, purchases: `Покупки (${purchases.length})`, audits: `AI-аудиты (${audits.length})` }[t]}
          </button>
        ))}
      </div>

      {/* Profile tab */}
      {tab === "profile" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 10, padding: 20 }}>
            <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
              <div>
                <div style={{ fontSize: 12, color: "var(--text-3)", marginBottom: 2 }}>Email</div>
                <div style={{ fontWeight: 500 }}>{user.email}</div>
              </div>
              <div>
                <div style={{ fontSize: 12, color: "var(--text-3)", marginBottom: 2 }}>Имя</div>
                <div style={{ fontWeight: 500 }}>{user.name || "—"}</div>
              </div>
              <div>
                <div style={{ fontSize: 12, color: "var(--text-3)", marginBottom: 2 }}>Тариф</div>
                <span className="badge badge-blue">{PLAN_LABEL[user.subscription_plan]}</span>
              </div>
              {user.subscription_expires_at && (
                <div>
                  <div style={{ fontSize: 12, color: "var(--text-3)", marginBottom: 2 }}>Действует до</div>
                  <div>{new Date(user.subscription_expires_at).toLocaleDateString("ru")}</div>
                </div>
              )}
            </div>
            <div style={{ marginTop: 16 }}>
              <a href="/pricing" className="btn btn-primary btn-sm">Улучшить тариф</a>
            </div>
          </div>
          <TelegramConnect />
          <ReferralCard />
        </div>
      )}

      {/* Alerts tab */}
      {tab === "alerts" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <span style={{ fontSize: 13, color: "var(--text-2)" }}>
              Использовано {alerts.length} из {user.saved_filters_limit}
            </span>
            <button className="btn btn-primary btn-sm" onClick={() => setShowCreateAlert(true)}>
              + Создать фильтр
            </button>
          </div>

          {alerts.length === 0 && (
            <div style={{ padding: 32, textAlign: "center", color: "var(--text-3)", background: "var(--surface)", borderRadius: 10, border: "1px solid var(--border)" }}>
              Нет сохранённых фильтров.<br />
              Нажмите «+ Создать фильтр» — пришлём уведомление о новых участках по вашим критериям.
            </div>
          )}

          {alerts.map((alert) => (
            <div key={alert.id} style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 10, padding: 16 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                <span style={{ fontWeight: 600, flex: 1 }}>{alert.name}</span>
                <span className={`badge ${alert.is_active ? "badge-green" : "badge-gray"}`}>
                  {alert.is_active ? "Активен" : "Пауза"}
                </span>
                <span className="badge badge-blue">{CHANNEL_LABEL[alert.channel]}</span>
              </div>
              {alert.last_triggered_at && (
                <div style={{ fontSize: 12, color: "var(--text-3)", marginBottom: 8 }}>
                  Последнее срабатывание: {new Date(alert.last_triggered_at).toLocaleString("ru")}
                </div>
              )}
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button className="btn btn-primary btn-sm" onClick={() => sendTestNotification(alert.id)}>
                  📨 Тест
                </button>
                <button className="btn btn-secondary btn-sm" onClick={() => toggleAlert(alert.id)}>
                  {alert.is_active ? "Приостановить" : "Возобновить"}
                </button>
                <button className="btn btn-ghost btn-sm" style={{ color: "var(--danger)" }} onClick={() => deleteAlert(alert.id)}>
                  Удалить
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Saved lots tab */}
      {tab === "history" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {savedLots.length === 0 && (
            <div style={{ padding: 32, textAlign: "center", color: "var(--text-3)", background: "var(--surface)", borderRadius: 10, border: "1px solid var(--border)" }}>
              Нет избранных участков.
            </div>
          )}
          {savedLots.map((lot) => (
            <div key={lot.id} style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 10, padding: 14, display: "flex", gap: 12, alignItems: "center" }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 500, fontSize: 14 }}>{lot.title || `Лот #${lot.id}`}</div>
                {lot.start_price && (
                  <div style={{ fontSize: 13, color: "var(--primary)", fontWeight: 600 }}>
                    {lot.start_price.toLocaleString("ru")} ₽
                  </div>
                )}
              </div>
              <a href={`/lots/${lot.id}`} className="btn btn-secondary btn-sm">Открыть</a>
            </div>
          ))}
        </div>
      )}

      {/* Views history tab */}
      {tab === "views" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {views.length === 0 && (
            <div style={{ padding: 32, textAlign: "center", color: "var(--text-3)", background: "var(--surface)", borderRadius: 10, border: "1px solid var(--border)" }}>
              Здесь появятся участки, которые вы просматриваете.
            </div>
          )}
          {views.map((lot) => (
            <a
              key={lot.id}
              href={`/lots/${lot.id}`}
              style={{
                background: "var(--surface)", border: "1px solid var(--border)",
                borderRadius: 10, padding: 14, textDecoration: "none", color: "inherit",
                display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap",
              }}
            >
              {lot.score != null && (
                <span className="badge" style={{
                  background: "linear-gradient(135deg, var(--primary), #0d9488)",
                  color: "white", fontWeight: 700,
                }}>
                  {lot.score}
                </span>
              )}
              <div style={{ flex: 1, minWidth: 180 }}>
                <div style={{ fontWeight: 500, fontSize: 14, marginBottom: 2 }}>
                  {lot.title || `Лот #${lot.id}`}
                </div>
                <div style={{ fontSize: 12, color: "var(--text-3)" }}>
                  {lot.region_name && <span>{lot.region_name}</span>}
                  {lot.start_price && <span>  ·  {lot.start_price.toLocaleString("ru")} ₽</span>}
                  {lot.area_sqm && <span>  ·  {lot.area_sqm.toLocaleString("ru")} м²</span>}
                </div>
              </div>
              {lot.viewed_at && (
                <span style={{ fontSize: 11, color: "var(--text-3)", flexShrink: 0 }}>
                  {new Date(lot.viewed_at).toLocaleString("ru", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}
                </span>
              )}
            </a>
          ))}
        </div>
      )}

      {/* Purchases tab */}
      {tab === "purchases" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {purchases.length === 0 && (
            <div style={{ padding: 32, textAlign: "center", color: "var(--text-3)", background: "var(--surface)", borderRadius: 10, border: "1px solid var(--border)" }}>
              Здесь появятся ваши покупки: подписки и разовые аудиты.
            </div>
          )}
          {purchases.map((p) => {
            const planLabel: Record<string, string> = {
              audit_lot: "AI-аудит лота",
              predd: "preDD аудит договора",
              pro: "Подписка Pro",
              investor: "Подписка Инвестор",
              buro: "Подписка Бюро",
              buro_plus: "Подписка Бюро+",
            };
            const statusLabel: Record<string, { text: string; color: string }> = {
              succeeded: { text: "Оплачено", color: "#16a34a" },
              pending: { text: "В ожидании", color: "#ca8a04" },
              cancelled: { text: "Отменено", color: "#94a3b8" },
            };
            const st = statusLabel[p.status] || { text: p.status, color: "#64748b" };
            return (
              <div key={p.id} style={{
                background: "var(--surface)", border: "1px solid var(--border)",
                borderRadius: 10, padding: 14,
                display: "flex", gap: 14, alignItems: "center", flexWrap: "wrap",
              }}>
                <div style={{ flex: 1, minWidth: 180 }}>
                  <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 2 }}>
                    {planLabel[p.plan] || p.plan}
                    {p.months && p.months > 0 && <span style={{ fontWeight: 400, color: "var(--text-3)" }}> · {p.months} мес.</span>}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--text-3)" }}>
                    {p.created_at && <span>Создан: {new Date(p.created_at).toLocaleString("ru", { day: "2-digit", month: "2-digit", year: "2-digit" })}</span>}
                    {p.paid_at && <span>  ·  Оплачен: {new Date(p.paid_at).toLocaleString("ru", { day: "2-digit", month: "2-digit", year: "2-digit" })}</span>}
                  </div>
                </div>
                <div style={{ fontWeight: 700, fontSize: 15 }}>
                  {p.amount.toLocaleString("ru")} ₽
                </div>
                <span style={{
                  fontSize: 11, fontWeight: 600,
                  padding: "3px 10px", borderRadius: 12,
                  background: st.color + "20", color: st.color, flexShrink: 0,
                }}>
                  {st.text}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* AI audits tab */}
      {tab === "audits" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
            <span style={{ fontSize: 13, color: "var(--text-2)" }}>
              Осталось аудитов: <b style={{ color: "var(--primary)" }}>{auditsLeft}</b>
            </span>
            <a href="/pricing" className="btn btn-ghost btn-sm">Пополнить</a>
          </div>
          {audits.length === 0 && (
            <div style={{ padding: 32, textAlign: "center", color: "var(--text-3)", background: "var(--surface)", borderRadius: 10, border: "1px solid var(--border)" }}>
              Здесь появятся лоты, которые вы проверили AI-аудитом.<br />
              Оценка каждого проверенного лота остаётся доступной вам навсегда.
            </div>
          )}
          {audits.map((a) => (
            <a key={a.lot_id} href={`/lots/${a.lot_id}`} style={{
              background: "var(--surface)", border: "1px solid var(--border)",
              borderRadius: 10, padding: 14, textDecoration: "none", color: "var(--text)",
              display: "flex", gap: 14, alignItems: "center", flexWrap: "wrap",
            }}>
              <div style={{ flex: 1, minWidth: 200 }}>
                <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 420 }}>
                  {a.title || `Лот #${a.lot_id}`}
                </div>
                <div style={{ fontSize: 12, color: "var(--text-3)" }}>
                  {a.region_name || ""}
                  {a.audited_at && ` · аудит ${new Date(a.audited_at).toLocaleDateString("ru")}`}
                  {a.status === "completed" && " · торги завершены"}
                </div>
              </div>
              {a.start_price != null && (
                <div style={{ fontWeight: 700, fontSize: 14 }}>
                  {a.start_price >= 1_000_000 ? `${(a.start_price / 1_000_000).toFixed(2)} млн ₽` : `${Math.round(a.start_price / 1000)} тыс ₽`}
                </div>
              )}
              {a.ai_score != null && (
                <span style={{
                  fontSize: 12, fontWeight: 700, padding: "4px 10px", borderRadius: 12, flexShrink: 0,
                  background: a.ai_score >= 70 ? "#dcfce7" : a.ai_score >= 40 ? "#fef9c3" : "#fee2e2",
                  color: a.ai_score >= 70 ? "#166534" : a.ai_score >= 40 ? "#854d0e" : "#991b1b",
                }}>
                  AI: {a.ai_score}
                </span>
              )}
              {a.ai_strategy && (
                <span style={{ fontSize: 11, color: "var(--text-3)", flexShrink: 0 }}>{a.ai_strategy}</span>
              )}
            </a>
          ))}
        </div>
      )}

      {showCreateAlert && (
        <CreateAlertModal
          hasTelegram={!!user.telegram_id}
          plan={user.subscription_plan}
          onClose={() => setShowCreateAlert(false)}
          onCreated={async () => {
            setShowCreateAlert(false);
            await reloadAlerts();
          }}
        />
      )}
    </div>
  );
}
