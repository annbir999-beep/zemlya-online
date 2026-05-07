"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, UserProfile } from "@/lib/api";
import { getMe } from "@/lib/auth";

interface Stats {
  users: {
    total: number;
    paying: number;
    new_7d: number;
    by_plan: Record<string, number>;
    conversion_pct: number;
  };
  revenue: { total: number; last_30d: number };
  subscriptions: { succeeded: number; pending: number };
}

interface AdminUser {
  id: number;
  email: string;
  name?: string;
  plan: string;
  expires_at?: string;
  free_audits_left: number;
  is_admin: boolean;
  is_active: boolean;
  telegram_id?: string;
  created_at?: string;
}

interface Promo {
  id: number;
  code: string;
  discount_pct?: number;
  discount_fixed?: number;
  max_uses?: number;
  used_count: number;
  valid_until?: string;
  plan_filter?: string;
  new_users_only: boolean;
  is_active: boolean;
  description?: string;
}

interface AdminSub {
  id: number;
  user_id: number;
  user_email: string;
  plan: string;
  amount: number;
  months: number;
  status: string;
  created_at?: string;
  paid_at?: string;
}

const fmt = (n: number) => n.toLocaleString("ru");
const fmtDate = (iso?: string | null) => iso ? new Date(iso).toLocaleString("ru") : "—";

export default function AdminPage() {
  const router = useRouter();
  const [me, setMe] = useState<UserProfile | null>(null);
  const [tab, setTab] = useState<"stats" | "users" | "promos" | "subs">("stats");

  useEffect(() => {
    getMe().then((u) => {
      if (!u) { router.push("/login"); return; }
      if (!u.is_admin) { router.push("/"); return; }
      setMe(u);
    });
  }, [router]);

  if (!me) return <div style={{ padding: 40, textAlign: "center", color: "var(--text-3)" }}>Загрузка...</div>;
  if (!me.is_admin) return null;

  return (
    <div style={{ flex: 1, overflow: "auto", padding: "24px 20px", maxWidth: 1280, margin: "0 auto", width: "100%" }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 16 }}>👑 Админка</h1>

      <div style={{ display: "flex", gap: 4, borderBottom: "1px solid var(--border)", marginBottom: 20 }}>
        {([
          ["stats", "Сводка"],
          ["users", "Пользователи"],
          ["promos", "Промокоды"],
          ["subs", "Платежи"],
        ] as const).map(([k, label]) => (
          <button
            key={k}
            className="btn btn-ghost"
            style={{
              borderRadius: "6px 6px 0 0",
              borderBottom: tab === k ? "2px solid var(--primary)" : "2px solid transparent",
              color: tab === k ? "var(--primary)" : "var(--text-2)",
              fontWeight: tab === k ? 600 : 400,
            }}
            onClick={() => setTab(k)}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "stats" && <StatsTab />}
      {tab === "users" && <UsersTab />}
      {tab === "promos" && <PromosTab />}
      {tab === "subs" && <SubsTab />}
    </div>
  );
}

function StatsTab() {
  const [stats, setStats] = useState<Stats | null>(null);
  useEffect(() => {
    api.get<Stats>("/api/admin/stats").then(setStats);
  }, []);
  if (!stats) return <div style={{ color: "var(--text-3)" }}>Загрузка...</div>;

  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
      <Card label="Всего пользователей" value={fmt(stats.users.total)} />
      <Card label="Платящих" value={fmt(stats.users.paying)} note={`${stats.users.conversion_pct}% конверсия`} />
      <Card label="Новых за 7 дней" value={`+${fmt(stats.users.new_7d)}`} accent />
      <Card label="Выручка всего" value={`${fmt(stats.revenue.total)} ₽`} />
      <Card label="Выручка за 30 дней" value={`${fmt(stats.revenue.last_30d)} ₽`} accent />
      <Card label="Платежей" value={`${fmt(stats.subscriptions.succeeded)} / ${fmt(stats.subscriptions.pending)} pending`} />
      <div style={{ gridColumn: "1 / -1", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 10, padding: 16 }}>
        <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>Распределение по тарифам</div>
        {Object.entries(stats.users.by_plan).map(([plan, cnt]) => (
          <div key={plan} style={{ display: "flex", justifyContent: "space-between", padding: "4px 0", fontSize: 13, borderBottom: "1px dashed var(--border)" }}>
            <span>{plan}</span>
            <b>{fmt(cnt)}</b>
          </div>
        ))}
      </div>
    </div>
  );
}

function UsersTab() {
  const [items, setItems] = useState<AdminUser[]>([]);
  const [q, setQ] = useState("");
  const [editing, setEditing] = useState<AdminUser | null>(null);

  const load = () =>
    api.get<{ items: AdminUser[] }>(`/api/admin/users?q=${encodeURIComponent(q)}&per_page=50`).then((d) => setItems(d.items));

  useEffect(() => { load(); }, []);

  return (
    <div>
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <input className="input" placeholder="Email или имя..." value={q} onChange={(e) => setQ(e.target.value)} style={{ maxWidth: 320 }} />
        <button className="btn btn-secondary btn-sm" onClick={load}>Найти</button>
      </div>
      <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 10, overflow: "hidden" }}>
        <table style={{ width: "100%", fontSize: 13, borderCollapse: "collapse" }}>
          <thead style={{ background: "var(--surface-2)" }}>
            <tr>
              <Th>ID</Th><Th>Email</Th><Th>План</Th><Th>До</Th><Th>Audits</Th><Th>TG</Th><Th>Создан</Th><Th></Th>
            </tr>
          </thead>
          <tbody>
            {items.map((u) => (
              <tr key={u.id} style={{ borderTop: "1px solid var(--border)" }}>
                <Td>{u.id}</Td>
                <Td>{u.email}{u.is_admin && <span style={{ marginLeft: 6, fontSize: 10, background: "#dc2626", color: "white", padding: "1px 5px", borderRadius: 3 }}>ADMIN</span>}</Td>
                <Td>{u.plan}</Td>
                <Td>{u.expires_at ? new Date(u.expires_at).toLocaleDateString("ru") : "—"}</Td>
                <Td>{u.free_audits_left}</Td>
                <Td>{u.telegram_id ? "✓" : "—"}</Td>
                <Td>{u.created_at ? new Date(u.created_at).toLocaleDateString("ru") : "—"}</Td>
                <Td><button className="btn btn-ghost btn-sm" onClick={() => setEditing(u)}>Изменить</button></Td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {editing && <UserEditModal user={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />}
    </div>
  );
}

function UserEditModal({ user, onClose, onSaved }: { user: AdminUser; onClose: () => void; onSaved: () => void }) {
  const [plan, setPlan] = useState(user.plan);
  const [months, setMonths] = useState("1");
  const [audits, setAudits] = useState("0");
  const [isAdmin, setIsAdmin] = useState(user.is_admin);
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      await api.patch(`/api/admin/users/${user.id}`, {
        plan,
        plan_months: plan !== "free" ? Number(months) : undefined,
        free_audits_add: Number(audits) || undefined,
        is_admin: isAdmin,
      });
      onSaved();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Ошибка");
    } finally { setSaving(false); }
  };

  return (
    <Modal onClose={onClose}>
      <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 12 }}>Изменить: {user.email}</h2>
      <Field label="План">
        <select className="select" value={plan} onChange={(e) => setPlan(e.target.value)}>
          {["free", "pro", "buro", "buro_plus", "enterprise"].map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
      </Field>
      {plan !== "free" && (
        <Field label="Период (мес) — продлевает от текущей даты окончания">
          <select className="select" value={months} onChange={(e) => setMonths(e.target.value)}>
            <option value="1">1 мес</option>
            <option value="3">3 мес</option>
            <option value="12">12 мес</option>
          </select>
        </Field>
      )}
      <Field label="+ к бесплатным аудитам">
        <input className="input" type="number" value={audits} onChange={(e) => setAudits(e.target.value)} />
      </Field>
      <Field label="">
        <label style={{ display: "flex", gap: 8, fontSize: 13 }}>
          <input type="checkbox" checked={isAdmin} onChange={(e) => setIsAdmin(e.target.checked)} />
          Админ
        </label>
      </Field>
      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 14 }}>
        <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
        <button className="btn btn-primary" onClick={save} disabled={saving}>{saving ? "..." : "Сохранить"}</button>
      </div>
    </Modal>
  );
}

function PromosTab() {
  const [items, setItems] = useState<Promo[]>([]);
  const [creating, setCreating] = useState(false);
  const load = () => api.get<{ items: Promo[] }>("/api/admin/promos").then((d) => setItems(d.items));
  useEffect(() => { load(); }, []);

  const toggleActive = async (p: Promo) => {
    await api.patch(`/api/admin/promos/${p.id}`, { is_active: !p.is_active });
    load();
  };

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <button className="btn btn-primary btn-sm" onClick={() => setCreating(true)}>+ Создать промокод</button>
      </div>
      <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 10, overflow: "auto" }}>
        <table style={{ width: "100%", fontSize: 13, borderCollapse: "collapse", minWidth: 800 }}>
          <thead style={{ background: "var(--surface-2)" }}>
            <tr>
              <Th>Код</Th><Th>Скидка</Th><Th>Использовано</Th><Th>Лимит</Th><Th>План</Th><Th>Только новые</Th><Th>Активен</Th><Th>Описание</Th>
            </tr>
          </thead>
          <tbody>
            {items.map((p) => (
              <tr key={p.id} style={{ borderTop: "1px solid var(--border)" }}>
                <Td><code>{p.code}</code></Td>
                <Td>{p.discount_pct ? `${p.discount_pct}%` : `${p.discount_fixed}₽`}</Td>
                <Td>{p.used_count}</Td>
                <Td>{p.max_uses ?? "∞"}</Td>
                <Td>{p.plan_filter ?? "всё"}</Td>
                <Td>{p.new_users_only ? "✓" : "—"}</Td>
                <Td>
                  <button className="btn btn-ghost btn-sm" onClick={() => toggleActive(p)}>
                    {p.is_active ? "✓" : "✗"}
                  </button>
                </Td>
                <Td style={{ fontSize: 11, color: "var(--text-3)" }}>{p.description}</Td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {creating && <PromoCreateModal onClose={() => setCreating(false)} onSaved={() => { setCreating(false); load(); }} />}
    </div>
  );
}

function PromoCreateModal({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [code, setCode] = useState("");
  const [discountPct, setDiscountPct] = useState("");
  const [discountFixed, setDiscountFixed] = useState("");
  const [maxUses, setMaxUses] = useState("");
  const [planFilter, setPlanFilter] = useState("");
  const [newOnly, setNewOnly] = useState(false);
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);

  const save = async () => {
    if (!code.trim() || (!discountPct && !discountFixed)) {
      alert("Укажите код и скидку (% или фикс)");
      return;
    }
    setSaving(true);
    try {
      await api.post("/api/admin/promos", {
        code: code.trim(),
        discount_pct: discountPct ? Number(discountPct) : undefined,
        discount_fixed: discountFixed ? Number(discountFixed) : undefined,
        max_uses: maxUses ? Number(maxUses) : undefined,
        plan_filter: planFilter || undefined,
        new_users_only: newOnly,
        description: description || undefined,
      });
      onSaved();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Ошибка");
    } finally { setSaving(false); }
  };

  return (
    <Modal onClose={onClose}>
      <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 12 }}>Новый промокод</h2>
      <Field label="Код"><input className="input" value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} placeholder="FIRST50" /></Field>
      <Field label="Скидка %"><input className="input" type="number" value={discountPct} onChange={(e) => { setDiscountPct(e.target.value); if (e.target.value) setDiscountFixed(""); }} placeholder="50" /></Field>
      <Field label="ИЛИ скидка фикс. ₽"><input className="input" type="number" value={discountFixed} onChange={(e) => { setDiscountFixed(e.target.value); if (e.target.value) setDiscountPct(""); }} placeholder="200" /></Field>
      <Field label="Лимит использований (пусто = ∞)"><input className="input" type="number" value={maxUses} onChange={(e) => setMaxUses(e.target.value)} /></Field>
      <Field label="Только для тарифа (пусто = на всё)">
        <select className="select" value={planFilter} onChange={(e) => setPlanFilter(e.target.value)}>
          <option value="">— любой —</option>
          <option value="audit_lot">audit_lot (490₽)</option>
          <option value="pro">pro</option>
          <option value="buro">buro</option>
          <option value="buro_plus">buro_plus</option>
          <option value="predd">predd</option>
        </select>
      </Field>
      <Field label="">
        <label style={{ display: "flex", gap: 8, fontSize: 13 }}>
          <input type="checkbox" checked={newOnly} onChange={(e) => setNewOnly(e.target.checked)} />
          Только для новых пользователей
        </label>
      </Field>
      <Field label="Описание (для админа)"><input className="input" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Канал XYZ, дата запуска..." /></Field>
      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 14 }}>
        <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
        <button className="btn btn-primary" onClick={save} disabled={saving}>{saving ? "..." : "Создать"}</button>
      </div>
    </Modal>
  );
}

function SubsTab() {
  const [items, setItems] = useState<AdminSub[]>([]);
  const [status, setStatus] = useState<string>("");
  const load = () => api.get<{ items: AdminSub[] }>(`/api/admin/subscriptions?status=${status}&per_page=100`).then((d) => setItems(d.items));
  useEffect(() => { load(); }, [status]);

  return (
    <div>
      <div style={{ marginBottom: 12, display: "flex", gap: 6 }}>
        {[["", "Все"], ["succeeded", "Оплачены"], ["pending", "В ожидании"]].map(([v, l]) => (
          <button key={v} className="btn btn-sm" style={{ background: status === v ? "var(--primary)" : "var(--surface-2)", color: status === v ? "white" : "var(--text-2)" }} onClick={() => setStatus(v)}>{l}</button>
        ))}
      </div>
      <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 10, overflow: "auto" }}>
        <table style={{ width: "100%", fontSize: 13, borderCollapse: "collapse", minWidth: 700 }}>
          <thead style={{ background: "var(--surface-2)" }}>
            <tr>
              <Th>ID</Th><Th>Юзер</Th><Th>План</Th><Th>Сумма</Th><Th>Мес</Th><Th>Статус</Th><Th>Создан</Th><Th>Оплачен</Th>
            </tr>
          </thead>
          <tbody>
            {items.map((s) => (
              <tr key={s.id} style={{ borderTop: "1px solid var(--border)" }}>
                <Td>{s.id}</Td>
                <Td>{s.user_email}</Td>
                <Td>{s.plan}</Td>
                <Td>{fmt(s.amount)} ₽</Td>
                <Td>{s.months}</Td>
                <Td>
                  <span style={{
                    fontSize: 11, padding: "2px 6px", borderRadius: 3,
                    background: s.status === "succeeded" ? "#dcfce7" : s.status === "pending" ? "#fef3c7" : "#fee2e2",
                    color: s.status === "succeeded" ? "#15803d" : s.status === "pending" ? "#a16207" : "#991b1b",
                  }}>{s.status}</span>
                </Td>
                <Td style={{ fontSize: 11 }}>{fmtDate(s.created_at)}</Td>
                <Td style={{ fontSize: 11 }}>{fmtDate(s.paid_at)}</Td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── helpers ────────────────────────────────────────────────────────────────────

function Card({ label, value, note, accent }: { label: string; value: string; note?: string; accent?: boolean }) {
  return (
    <div style={{
      background: accent ? "linear-gradient(135deg,#16a34a,#0d9488)" : "var(--surface)",
      color: accent ? "white" : "inherit",
      border: accent ? "none" : "1px solid var(--border)",
      borderRadius: 10, padding: 14,
    }}>
      <div style={{ fontSize: 11, opacity: accent ? 0.85 : 0.6, marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700 }}>{value}</div>
      {note && <div style={{ fontSize: 11, opacity: 0.7, marginTop: 4 }}>{note}</div>}
    </div>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return <th style={{ padding: "8px 10px", textAlign: "left", fontSize: 11, color: "var(--text-3)", textTransform: "uppercase" }}>{children}</th>;
}

function Td({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return <td style={{ padding: "8px 10px", verticalAlign: "middle", ...style }}>{children}</td>;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 10 }}>
      {label && <div style={{ fontSize: 11, color: "var(--text-3)", marginBottom: 3 }}>{label}</div>}
      {children}
    </div>
  );
}

function Modal({ children, onClose }: { children: React.ReactNode; onClose: () => void }) {
  return (
    <div onClick={onClose} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000, padding: 20 }}>
      <div onClick={(e) => e.stopPropagation()} style={{ background: "var(--surface)", borderRadius: 12, padding: 22, maxWidth: 480, width: "100%", border: "1px solid var(--border)", maxHeight: "90vh", overflowY: "auto" }}>
        {children}
      </div>
    </div>
  );
}
