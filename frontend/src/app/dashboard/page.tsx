"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { api, UserProfile, Alert } from "@/lib/api";
import { getMe, logout } from "@/lib/auth";
import TelegramConnect from "@/components/TelegramConnect";

const PLAN_LABEL: Record<string, string> = {
  free: "Бесплатный", personal: "Личный", expert: "Эксперт", landlord: "Лендлорд",
};
const CHANNEL_LABEL: Record<string, string> = { email: "Email", telegram: "Telegram", both: "Email + Telegram" };

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<UserProfile | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [tab, setTab] = useState<"profile" | "alerts" | "history">("profile");
  const [savedLots, setSavedLots] = useState<{ id: number; title: string; start_price?: number; status: string }[]>([]);

  useEffect(() => {
    getMe().then((u) => {
      if (!u) { router.push("/login"); return; }
      setUser(u);
    });
    api.get<Alert[] | { items: Alert[] }>("/api/alerts").then((d) => setAlerts(Array.isArray(d) ? d : (d?.items ?? [])));
    api.get<typeof savedLots | { items: typeof savedLots }>("/api/users/saved-lots").then((d) => setSavedLots(Array.isArray(d) ? d : (d?.items ?? [])));
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

  if (!user) return <div style={{ padding: 40, textAlign: "center", color: "var(--text-3)" }}>Загрузка...</div>;

  return (
    <div style={{ flex: 1, overflow: "auto", padding: "32px 24px", maxWidth: 900, margin: "0 auto", width: "100%" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 28 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700 }}>Личный кабинет</h1>
        <button className="btn btn-ghost btn-sm" onClick={logout}>Выйти</button>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 4, borderBottom: "1px solid var(--border)", marginBottom: 24 }}>
        {(["profile", "alerts", "history"] as const).map((t) => (
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
            {{ profile: "Профиль", alerts: `Фильтры (${alerts.length})`, history: "Избранное" }[t]}
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
        </div>
      )}

      {/* Alerts tab */}
      {tab === "alerts" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <span style={{ fontSize: 13, color: "var(--text-2)" }}>
              Использовано {alerts.length} из {user.saved_filters_limit}
            </span>
            <a href="/" className="btn btn-primary btn-sm">+ Создать фильтр</a>
          </div>

          {alerts.length === 0 && (
            <div style={{ padding: 32, textAlign: "center", color: "var(--text-3)", background: "var(--surface)", borderRadius: 10, border: "1px solid var(--border)" }}>
              Нет сохранённых фильтров.<br />
              Настройте поиск на карте и сохраните его — мы пришлём уведомление о новых участках.
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
              <div style={{ display: "flex", gap: 8 }}>
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
    </div>
  );
}
