"use client";
import { useState, useEffect } from "react";
import { isAuthenticated } from "@/lib/auth";
import { api } from "@/lib/api";

const PERIOD_LABELS: Record<string, string> = {
  "1": "1 мес", "3": "3 мес", "12": "12 мес",
};

interface Plan {
  id: string;
  name: string;
  tagline?: string;
  price?: number;
  prices?: Record<string, number>;
  price_from?: number;
  filters_limit?: number;
  popular?: boolean;
  one_time?: boolean;
  contact_only?: boolean;
  audience?: "physical" | "smb" | "enterprise";
  features: string[];
}

interface Extra {
  id: string;
  name: string;
  price: number;
  description: string;
}

interface PlansResponse {
  plans: Plan[];
  extras?: Extra[];
}

const PLAN_COLORS: Record<string, { from: string; to: string; light: string }> = {
  free:        { from: "#64748b", to: "#475569", light: "#f1f5f9" },
  audit_lot:   { from: "#0ea5e9", to: "#0284c7", light: "#e0f2fe" },
  pro:         { from: "#16a34a", to: "#0d9488", light: "#dcfce7" },
  buro:        { from: "#dc2626", to: "#ea580c", light: "#fef3c7" },
  buro_plus:   { from: "#7c3aed", to: "#9333ea", light: "#ede9fe" },
  enterprise:  { from: "#1e293b", to: "#0f172a", light: "#e2e8f0" },
};

const fmtPrice = (n: number) => `${n.toLocaleString("ru")} ₽`;

export default function PricingPage() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [extras, setExtras] = useState<Extra[]>([]);
  const [periods, setPeriods] = useState<Record<string, string>>({
    pro: "1", buro: "3", buro_plus: "12",
  });
  const [loading, setLoading] = useState<string | null>(null);
  const [showEnterpriseForm, setShowEnterpriseForm] = useState(false);
  const [promoCode, setPromoCode] = useState("");
  const [promoStatus, setPromoStatus] = useState<{ ok: boolean; message: string } | null>(null);

  const validatePromo = async () => {
    setPromoStatus(null);
    if (!promoCode.trim()) return;
    try {
      const r = await api.post<{ valid: boolean; discount_pct?: number; discount_fixed?: number; description?: string }>(
        "/api/payments/promo/validate", { code: promoCode.trim() },
      );
      const sale = r.discount_pct ? `−${r.discount_pct}%` : r.discount_fixed ? `−${r.discount_fixed} ₽` : "";
      setPromoStatus({ ok: true, message: `Применится скидка ${sale}${r.description ? ` (${r.description})` : ""}` });
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Ошибка";
      setPromoStatus({ ok: false, message: msg });
    }
  };

  useEffect(() => {
    api.get<PlansResponse>("/api/payments/plans").then((d) => {
      setPlans(d.plans || []);
      setExtras(d.extras || []);
    });
  }, []);

  const buy = async (plan: Plan, lotId?: number) => {
    if (!isAuthenticated()) {
      window.location.href = `/login?next=${encodeURIComponent("/pricing")}`;
      return;
    }
    setLoading(plan.id);
    try {
      const months = plan.one_time ? 0 : Number(periods[plan.id] || 1);
      const r = await api.post<{ confirmation_url: string }>("/api/payments/create", {
        plan: plan.id,
        months,
        return_url: `${window.location.origin}/dashboard`,
        lot_id: lotId,
        promo_code: promoCode.trim() || undefined,
      });
      window.location.href = r.confirmation_url;
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Ошибка платежа";
      alert(msg);
    } finally {
      setLoading(null);
    }
  };

  return (
    <div style={{ flex: 1, overflow: "auto", padding: "32px 20px", maxWidth: 1280, margin: "0 auto", width: "100%" }}>
      <div style={{ textAlign: "center", marginBottom: 24 }}>
        <h1 style={{ fontSize: 32, fontWeight: 700, marginBottom: 8 }}>Тарифы</h1>
        <p style={{ color: "var(--text-3)", fontSize: 15, maxWidth: 640, margin: "0 auto", lineHeight: 1.5 }}>
          От разового AI-аудита за 490 ₽ до Enterprise с SLA. Подписка отменяется в один клик, разовые продукты — без обязательств.
        </p>
      </div>

      {/* Промокод */}
      <div style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: 10,
        padding: "12px 16px",
        marginBottom: 20,
        maxWidth: 480,
        margin: "0 auto 20px",
        display: "flex",
        gap: 8,
        alignItems: "center",
      }}>
        <span style={{ fontSize: 13, color: "var(--text-3)", whiteSpace: "nowrap" }}>🎫 Промокод:</span>
        <input
          className="input"
          placeholder="например, FIRST50"
          value={promoCode}
          onChange={(e) => { setPromoCode(e.target.value); setPromoStatus(null); }}
          style={{ flex: 1, fontSize: 13 }}
        />
        <button className="btn btn-secondary btn-sm" onClick={validatePromo} disabled={!promoCode.trim()}>
          Проверить
        </button>
      </div>
      {promoStatus && (
        <div style={{
          maxWidth: 480, margin: "-10px auto 20px",
          padding: "8px 14px", borderRadius: 8, fontSize: 13, textAlign: "center",
          background: promoStatus.ok ? "#dcfce7" : "#fee2e2",
          color: promoStatus.ok ? "#15803d" : "#991b1b",
        }}>
          {promoStatus.message}
        </div>
      )}

      {/* Главные подписочные планы */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
        gap: 16,
        marginBottom: 40,
      }}>
        {plans.map((plan) => (
          <PlanCard
            key={plan.id}
            plan={plan}
            period={periods[plan.id]}
            setPeriod={(p) => setPeriods((s) => ({ ...s, [plan.id]: p }))}
            onBuy={() => {
              if (plan.contact_only) setShowEnterpriseForm(true);
              else buy(plan);
            }}
            loading={loading === plan.id}
          />
        ))}
      </div>

      {/* Разовые продукты */}
      {extras.length > 0 && (
        <div style={{ marginBottom: 40 }}>
          <h2 style={{ fontSize: 20, fontWeight: 600, marginBottom: 16, textAlign: "center" }}>Разовые услуги</h2>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16, maxWidth: 800, margin: "0 auto" }}>
            {extras.map((ex) => (
              <div key={ex.id} style={{
                background: "var(--surface)",
                border: "1px solid var(--border)",
                borderRadius: 12, padding: 20,
              }}>
                <div style={{ fontWeight: 600, fontSize: 16, marginBottom: 8 }}>{ex.name}</div>
                <div style={{ fontSize: 24, fontWeight: 700, color: "var(--primary)", marginBottom: 6 }}>
                  {fmtPrice(ex.price)}
                </div>
                <div style={{ fontSize: 13, color: "var(--text-3)", lineHeight: 1.5 }}>{ex.description}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Сравнение по аудиториям */}
      <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: 20, marginBottom: 40 }}>
        <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 14 }}>Какой тариф подойдёт?</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 16 }}>
          <Audience
            icon="👤"
            title="Частное лицо"
            text="Покупаете участок для себя или инвестиции. Нужны разовые проверки или несколько фильтров."
            recommended="Аудит лота 490 ₽ или Pro"
          />
          <Audience
            icon="🏢"
            title="Риелтор / малый девелопер"
            text="Работаете с клиентами по земле, нужна полная аналитика, preDD договоров, контакты администраций."
            recommended="Бюро или Бюро+"
          />
          <Audience
            icon="🏛"
            title="Корпорация"
            text="Девелопер федерального уровня, юрфирма, инвестфонд. Нужны API, SLA, NDA, персональная команда."
            recommended="Enterprise (по запросу)"
          />
        </div>
      </div>

      {showEnterpriseForm && <EnterpriseModal onClose={() => setShowEnterpriseForm(false)} />}
    </div>
  );
}

function PlanCard({
  plan, period, setPeriod, onBuy, loading,
}: {
  plan: Plan;
  period?: string;
  setPeriod: (p: string) => void;
  onBuy: () => void;
  loading: boolean;
}) {
  const colors = PLAN_COLORS[plan.id] || PLAN_COLORS.free;
  const isFree = plan.id === "free";
  const isOneTime = plan.one_time;
  const isContact = plan.contact_only;

  let priceBlock: React.ReactNode;
  if (isFree) {
    priceBlock = <div style={{ fontSize: 32, fontWeight: 800 }}>Бесплатно</div>;
  } else if (isContact) {
    priceBlock = (
      <div>
        <div style={{ fontSize: 14, color: "var(--text-3)" }}>от</div>
        <div style={{ fontSize: 28, fontWeight: 800 }}>{fmtPrice(plan.price_from || 0)}</div>
        <div style={{ fontSize: 12, color: "var(--text-3)" }}>в месяц, обсуждается</div>
      </div>
    );
  } else if (isOneTime) {
    priceBlock = (
      <div>
        <div style={{ fontSize: 28, fontWeight: 800 }}>{fmtPrice(plan.price || 0)}</div>
        <div style={{ fontSize: 12, color: "var(--text-3)" }}>разово</div>
      </div>
    );
  } else if (plan.prices) {
    const cur = period || "1";
    const total = plan.prices[cur] || 0;
    const monthly = total / Number(cur);
    const baseMonthly = (plan.prices["1"] || 0);
    const saved = baseMonthly * Number(cur) - total;
    priceBlock = (
      <div>
        <div style={{ fontSize: 28, fontWeight: 800 }}>
          {fmtPrice(Math.round(monthly))}
          <span style={{ fontSize: 13, fontWeight: 500, color: "var(--text-3)", marginLeft: 6 }}>/мес</span>
        </div>
        <div style={{ fontSize: 12, color: "var(--text-3)", marginTop: 4 }}>
          {cur === "1"
            ? "ежемесячно"
            : `${fmtPrice(total)} разово за ${PERIOD_LABELS[cur]}`}
          {saved > 0 && (
            <span style={{ color: colors.from, fontWeight: 600, marginLeft: 6 }}>
              · экономия {fmtPrice(saved)}
            </span>
          )}
        </div>
      </div>
    );
  }

  return (
    <div style={{
      background: "var(--surface)",
      border: plan.popular ? `2px solid ${colors.from}` : "1px solid var(--border)",
      borderRadius: 14,
      padding: 22,
      position: "relative",
      display: "flex",
      flexDirection: "column",
      gap: 14,
    }}>
      {plan.popular && (
        <div style={{
          position: "absolute", top: -12, right: 16,
          background: `linear-gradient(135deg, ${colors.from}, ${colors.to})`,
          color: "white", fontSize: 11, fontWeight: 700,
          padding: "4px 10px", borderRadius: 12,
          letterSpacing: 0.5,
        }}>
          ПОПУЛЯРНО
        </div>
      )}

      <div>
        <div style={{ fontSize: 18, fontWeight: 700 }}>{plan.name}</div>
        {plan.tagline && (
          <div style={{ fontSize: 12, color: "var(--text-3)", marginTop: 2 }}>{plan.tagline}</div>
        )}
      </div>

      <div>{priceBlock}</div>

      {plan.prices && !isFree && !isOneTime && !isContact && (
        <div style={{ display: "flex", gap: 4 }}>
          {Object.keys(plan.prices).map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className="btn btn-sm"
              style={{
                flex: 1,
                background: period === p ? colors.from : "var(--surface-2)",
                color: period === p ? "white" : "var(--text-2)",
                fontSize: 11, padding: "4px 6px",
              }}
            >
              {PERIOD_LABELS[p]}
            </button>
          ))}
        </div>
      )}

      <ul style={{ listStyle: "none", padding: 0, margin: 0, fontSize: 13, lineHeight: 1.55, flex: 1 }}>
        {plan.features.map((f, i) => (
          <li key={i} style={{ display: "flex", gap: 8, marginBottom: 6, alignItems: "flex-start" }}>
            <span style={{ color: colors.from, marginTop: 2 }}>✓</span>
            <span style={{ color: "var(--text-2)" }}>{f}</span>
          </li>
        ))}
      </ul>

      <button
        onClick={onBuy}
        disabled={loading || isFree}
        className="btn"
        style={{
          background: isFree
            ? "var(--surface-2)"
            : `linear-gradient(135deg, ${colors.from}, ${colors.to})`,
          color: isFree ? "var(--text-3)" : "white",
          fontWeight: 600,
          padding: "10px 16px",
          cursor: isFree ? "default" : "pointer",
          opacity: loading ? 0.6 : 1,
        }}
      >
        {loading
          ? "Загрузка..."
          : isFree
            ? "Активен по умолчанию"
            : isContact
              ? "Связаться"
              : isOneTime
                ? "Купить разово"
                : "Оформить подписку"}
      </button>
    </div>
  );
}

function Audience({ icon, title, text, recommended }: { icon: string; title: string; text: string; recommended: string }) {
  return (
    <div>
      <div style={{ fontSize: 28, marginBottom: 8 }}>{icon}</div>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>{title}</div>
      <div style={{ fontSize: 13, color: "var(--text-3)", lineHeight: 1.5, marginBottom: 8 }}>{text}</div>
      <div style={{ fontSize: 13, fontWeight: 600, color: "var(--primary)" }}>→ {recommended}</div>
    </div>
  );
}

function EnterpriseModal({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState("");
  const [company, setCompany] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [users, setUsers] = useState<string>("");
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const submit = async () => {
    if (!name || !company || !email) {
      alert("Заполните имя, компанию и email");
      return;
    }
    setSubmitting(true);
    try {
      await api.post("/api/payments/enterprise/request", {
        name, company, email,
        phone: phone || undefined,
        estimated_users: users ? Number(users) : undefined,
        comment: comment || undefined,
      });
      setSubmitted(true);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Ошибка отправки");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div onClick={onClose} style={{
      position: "fixed", inset: 0, background: "rgba(0,0,0,0.55)",
      display: "flex", alignItems: "center", justifyContent: "center",
      zIndex: 1000, padding: 20,
    }}>
      <div onClick={(e) => e.stopPropagation()} style={{
        background: "var(--surface)", borderRadius: 14,
        width: "100%", maxWidth: 520, padding: 28,
        border: "1px solid var(--border)",
      }}>
        {submitted ? (
          <div style={{ textAlign: "center", padding: 20 }}>
            <div style={{ fontSize: 48, marginBottom: 12 }}>✅</div>
            <div style={{ fontSize: 18, fontWeight: 600, marginBottom: 8 }}>Заявка принята</div>
            <div style={{ fontSize: 14, color: "var(--text-3)", marginBottom: 20 }}>
              Свяжемся с вами в течение 24 часов на email <b>{email}</b>
            </div>
            <button onClick={onClose} className="btn btn-primary">Закрыть</button>
          </div>
        ) : (
          <>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
              <h2 style={{ fontSize: 20, fontWeight: 700 }}>Заявка на Enterprise</h2>
              <button onClick={onClose} className="btn btn-ghost btn-sm">✕</button>
            </div>
            <div style={{ fontSize: 13, color: "var(--text-3)", marginBottom: 16, lineHeight: 1.5 }}>
              Расскажите коротко о компании — мы свяжемся в течение суток для обсуждения условий, SLA и кастомизации.
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <input className="input" placeholder="Ваше имя *" value={name} onChange={(e) => setName(e.target.value)} />
              <input className="input" placeholder="Компания *" value={company} onChange={(e) => setCompany(e.target.value)} />
              <input className="input" placeholder="Email *" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
              <input className="input" placeholder="Телефон (необязательно)" value={phone} onChange={(e) => setPhone(e.target.value)} />
              <input className="input" placeholder="Сколько сотрудников будет работать" type="number" value={users} onChange={(e) => setUsers(e.target.value)} />
              <textarea
                className="input"
                placeholder="Комментарий: специфика, регионы, объём задач"
                rows={3}
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                style={{ resize: "vertical" }}
              />
              <button className="btn btn-primary" onClick={submit} disabled={submitting}>
                {submitting ? "Отправка..." : "Отправить заявку"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
