"use client";
import { useState, useEffect } from "react";
import { isAuthenticated } from "@/lib/auth";
import { api, UserProfile } from "@/lib/api";
import { getMe } from "@/lib/auth";

// torgi.gov.ru формат: /new/public/lots/lot/{ID}/(lotInfo:info)?fromRec=...
// Также поддерживаем старый /lotcards/{ID}.
// ID — цифры с возможным суффиксом _N (например 22000175410000000063_1).
const TORGI_RE = /(?:lots\/lot\/|lotcards\/(?:lot\/)?)(\d+(?:_\d+)?)/;

export default function AuditLotPage() {
  const [url, setUrl] = useState("");
  const [resolving, setResolving] = useState(false);
  const [resolvedLot, setResolvedLot] = useState<{ id: number; title?: string; address?: string; price?: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [acceptedOferta, setAcceptedOferta] = useState(false);
  const [user, setUser] = useState<UserProfile | null>(null);
  useEffect(() => { getMe().then(setUser); }, []);
  const hasFreeAudit = (user?.free_audits_left || 0) > 0;

  const resolveLot = async () => {
    setError(null);
    setResolvedLot(null);
    const trimmed = url.trim();
    if (!trimmed) {
      setError("Вставьте ссылку на лот torgi.gov.ru");
      return;
    }
    setResolving(true);
    try {
      const m = trimmed.match(TORGI_RE);
      if (!m) {
        setError("Не удалось распознать ссылку. Скопируйте URL вида torgi.gov.ru/new/public/lots/lot/{ID}/...");
        return;
      }
      try {
        // fetch=true — если лота нет в нашей БД, бэкенд скачает его с torgi.gov на лету
        const r = await api.get<{ id: number; title?: string; address?: string; start_price?: number }>(
          `/api/lots/by-external/torgi_${m[1]}?fetch=true`,
        );
        setResolvedLot({ id: r.id, title: r.title, address: r.address, price: r.start_price });
      } catch (apiErr) {
        const msg = apiErr instanceof Error ? apiErr.message : "";
        if (msg.includes("torgi.gov") || msg.includes("на torgi")) {
          setError("Лот не найден на torgi.gov. Проверьте ссылку — возможно лот удалён или ID неверный.");
        } else if (msg.includes("не найден")) {
          setError("Лот не найден. Если ссылка свежая, напишите @ZemlyaOnlineBot — добавим вручную.");
        } else {
          setError("Ошибка соединения. Попробуйте позже.");
        }
      }
    } finally {
      setResolving(false);
    }
  };

  const buy = async () => {
    if (!isAuthenticated()) {
      window.location.href = `/login?next=${encodeURIComponent("/audit-lot")}`;
      return;
    }
    if (!resolvedLot) return;
    if (!acceptedOferta) {
      setError("Согласитесь с условиями оферты, чтобы продолжить");
      return;
    }
    try {
      const r = await api.post<{ confirmation_url: string }>("/api/payments/create", {
        plan: "audit_lot",
        months: 0,
        return_url: `${window.location.origin}/lots/${resolvedLot.id}`,
        lot_id: resolvedLot.id,
      });
      window.location.href = r.confirmation_url;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка платежа");
    }
  };

  return (
    <div style={{ flex: 1, overflow: "auto", padding: "32px 20px", maxWidth: 760, margin: "0 auto", width: "100%" }}>
      <div style={{ textAlign: "center", marginBottom: 28 }}>
        <h1 style={{ fontSize: 32, fontWeight: 700, marginBottom: 8 }}>AI-аудит лота за 490 ₽</h1>
        <p style={{ color: "var(--text-3)", fontSize: 15, lineHeight: 1.5 }}>
          Вставьте ссылку на интересующий лот с torgi.gov.ru — мы выполним полный AI-разбор и пришлём PDF-отчёт.
          Без подписки, без обязательств.
        </p>
      </div>

      {hasFreeAudit && (
        <div style={{
          background: "linear-gradient(135deg,#16a34a,#0d9488)",
          color: "white", padding: "14px 18px", borderRadius: 12,
          marginBottom: 16, textAlign: "center",
        }}>
          <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 2 }}>
            🎁 Ваш первый аудит — бесплатно
          </div>
          <div style={{ fontSize: 12, opacity: 0.9 }}>
            На счету: {user?.free_audits_left} разовых аудитов. Расходуются только на ваши действия.
          </div>
        </div>
      )}

      <div style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: 14,
        padding: 22,
        marginBottom: 20,
      }}>
        <div style={{ fontSize: 13, color: "var(--text-3)", marginBottom: 6 }}>
          Ссылка на лот torgi.gov.ru
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <input
            className="input"
            placeholder="https://torgi.gov.ru/new/public/lots/lot/..."
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            style={{ flex: 1 }}
          />
          <button
            className="btn btn-primary"
            onClick={resolveLot}
            disabled={resolving}
          >
            {resolving ? "..." : "Найти"}
          </button>
        </div>

        {error && (
          <div style={{
            marginTop: 12, padding: 12,
            background: "#fef2f2", color: "#991b1b",
            border: "1px solid #fecaca", borderRadius: 8,
            fontSize: 13, lineHeight: 1.5,
          }}>
            {error}
          </div>
        )}

        {resolvedLot && (
          <div style={{
            marginTop: 16, padding: 16,
            background: "var(--surface-2)", borderRadius: 10,
          }}>
            <div style={{ fontSize: 12, color: "var(--text-3)", marginBottom: 4 }}>Найден лот</div>
            <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 4 }}>
              {resolvedLot.title || `Лот #${resolvedLot.id}`}
            </div>
            {resolvedLot.address && (
              <div style={{ fontSize: 13, color: "var(--text-2)", marginBottom: 4 }}>📍 {resolvedLot.address}</div>
            )}
            {resolvedLot.price && (
              <div style={{ fontSize: 14, fontWeight: 600, color: "var(--primary)" }}>
                Начальная цена: {resolvedLot.price.toLocaleString("ru")} ₽
              </div>
            )}
            <label style={{ display: "flex", gap: 8, alignItems: "flex-start", marginTop: 14, fontSize: 12, color: "var(--text-2)", cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={acceptedOferta}
                onChange={(e) => setAcceptedOferta(e.target.checked)}
                style={{ marginTop: 3 }}
              />
              <span>
                Согласен с <a href="/oferta" target="_blank" rel="noreferrer" style={{ color: "var(--primary)" }}>публичной офертой</a> и
                {" "}<a href="/privacy" target="_blank" rel="noreferrer" style={{ color: "var(--primary)" }}>политикой конфиденциальности</a>
              </span>
            </label>
            {hasFreeAudit ? (
              <button
                className="btn btn-primary"
                onClick={() => window.location.href = `/lots/${resolvedLot?.id}`}
                disabled={!acceptedOferta}
                style={{ marginTop: 10, width: "100%", fontSize: 15, padding: "12px 16px", opacity: acceptedOferta ? 1 : 0.5, background: "linear-gradient(135deg,#16a34a,#0d9488)" }}
              >
                🎁 Получить аудит бесплатно →
              </button>
            ) : (
              <button
                className="btn btn-primary"
                onClick={buy}
                disabled={!acceptedOferta}
                style={{ marginTop: 10, width: "100%", fontSize: 15, padding: "12px 16px", opacity: acceptedOferta ? 1 : 0.5 }}
              >
                Купить аудит за 490 ₽ →
              </button>
            )}
          </div>
        )}
      </div>

      {/* Что входит */}
      <div style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: 14, padding: 22,
      }}>
        <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 14 }}>Что входит в аудит</h2>
        <ul style={{ listStyle: "none", padding: 0, fontSize: 14, lineHeight: 1.7 }}>
          {[
            "🏛 Юридический анализ: ВРИ, обременения, ЗОУИТ — со ссылками на нормы ЗК РФ",
            "📜 Разбор проекта договора: переуступка, субаренда, штрафы, скрытые риски",
            "💰 Сравнение с рынком: медиана ЦИАН + Авито по региону, дисконт",
            "🌳 Что рядом: водоёмы, лес, трасса, ж/д (из OpenStreetMap)",
            "🏘 Контакты администрации (отдел земельных отношений)",
            "📊 Калькулятор окупаемости каркасного дома по региону",
            "📄 PDF-отчёт для скачивания и сохранения",
          ].map((f, i) => (
            <li key={i} style={{ marginBottom: 8 }}>{f}</li>
          ))}
        </ul>

        <div style={{
          marginTop: 16, padding: 14,
          background: "linear-gradient(135deg, #16a34a, #0d9488)",
          borderRadius: 10, color: "white",
        }}>
          <div style={{ fontWeight: 600, marginBottom: 4 }}>💡 Совет</div>
          <div style={{ fontSize: 13, lineHeight: 1.5 }}>
            Если планируете покупать 5+ лотов в месяц — выгоднее <a href="/pricing" style={{ color: "white", textDecoration: "underline" }}>тариф Pro</a> за 2 900 ₽/мес: 30 аудитов + контакты + сравнение.
          </div>
        </div>
      </div>
    </div>
  );
}
