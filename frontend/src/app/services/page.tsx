"use client";
import { useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";

/* Раздел «Услуги» — сопровождение земельных торгов под ключ.
   Пакеты: А (под ключ, за 1 лот), Б (ДВ/Арктический гектар), В (инвесторам, 4 варианта). */

const card: React.CSSProperties = {
  background: "var(--surface)", border: "1px solid var(--border)",
  borderRadius: 14, padding: 24,
};

function ServicesInner() {
  const params = useSearchParams();
  const lotId = params.get("lot");
  const [form, setForm] = useState({ name: "", contact: "", package: lotId ? "lot" : "turnkey", comment: "" });
  const [sent, setSent] = useState(false);
  const [sending, setSending] = useState(false);
  const [err, setErr] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr("");
    if (form.name.trim().length < 2 || form.contact.trim().length < 5) {
      setErr("Заполните имя и контакт (телефон или @telegram)");
      return;
    }
    setSending(true);
    try {
      await api.post("/api/services/lead", {
        ...form,
        lot_id: lotId ? Number(lotId) : null,
      });
      setSent(true);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка отправки — напишите нам в Telegram @torgi_zemli");
    } finally {
      setSending(false);
    }
  };

  const scrollToForm = (pkg: string) => {
    setForm(f => ({ ...f, package: pkg }));
    document.getElementById("request-form")?.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <div style={{ flex: 1, overflow: "auto" }}>
      <div style={{ maxWidth: 960, margin: "0 auto", padding: "40px 24px 80px" }}>

        {/* Hero */}
        <div style={{ textAlign: "center", marginBottom: 48 }}>
          <h1 style={{ fontSize: 34, fontWeight: 800, marginBottom: 12 }}>
            Земельные торги — <span style={{ color: "var(--primary)" }}>под ключ</span>
          </h1>
          <p style={{ fontSize: 16, color: "var(--text-2)", maxWidth: 640, margin: "0 auto", lineHeight: 1.6 }}>
            Мы находим участки в 2–10 раз дешевле рынка, проверяем юридически,
            участвуем в торгах и доводим до регистрации. Вы получаете результат —
            мы берём на себя процесс.
          </p>
          <div style={{ marginTop: 20 }}>
            <button className="btn btn-primary" onClick={() => scrollToForm("turnkey")} style={{ padding: "12px 28px", fontSize: 15 }}>
              🤝 Оставить заявку
            </button>
          </div>
        </div>

        {/* Пакет А */}
        <div style={{ ...card, marginBottom: 20, borderColor: "var(--primary)" }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap", marginBottom: 8 }}>
            <h2 style={{ fontSize: 22, fontWeight: 700, margin: 0 }}>🏆 Участие в торгах под ключ</h2>
            <span className="badge badge-blue">за 1 лот</span>
          </div>
          <p style={{ color: "var(--text-2)", fontSize: 14, lineHeight: 1.65, marginBottom: 14 }}>
            Полный цикл: подбор лота под вашу задачу (скоринг + AI-аудит платформы) → юридическая
            проверка (выписки, обременения, ВРИ, договор) → выпуск ЭЦП и аккредитация на ЭТП →
            стратегия и участие в аукционе → подписание договора и регистрация права.
          </p>
          <ul style={{ fontSize: 14, color: "var(--text-2)", lineHeight: 1.9, margin: "0 0 16px 18px", padding: 0 }}>
            <li>Фикс за сопровождение одного лота + процент от достигнутой экономии к рыночной цене</li>
            <li>Экономию считаем по данным платформы (медианы ЦИАН/Авито) — прозрачно, в договоре</li>
            <li>Не выиграли торги — возвращаем половину фикса</li>
          </ul>
          <button className="btn btn-primary btn-sm" onClick={() => scrollToForm("turnkey")}>Обсудить мой случай →</button>
        </div>

        {/* Пакет Б */}
        <div style={{ ...card, marginBottom: 20 }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap", marginBottom: 8 }}>
            <h2 style={{ fontSize: 22, fontWeight: 700, margin: 0 }}>🌲 Дальневосточный и Арктический гектар</h2>
            <span className="badge badge-green">бесплатная земля от государства</span>
          </div>
          <p style={{ color: "var(--text-2)", fontSize: 14, lineHeight: 1.65, marginBottom: 14 }}>
            1 га на человека (до 5 га на семью) — бесплатно. Но большинство заявок буксует из-за ошибок:
            неверный контур, пересечение с лесфондом, слабый план освоения. Мы делаем правильно с первого раза.
          </p>
          <ul style={{ fontSize: 14, color: "var(--text-2)", lineHeight: 1.9, margin: "0 0 16px 18px", padding: 0 }}>
            <li>Проверка участка до подачи: кадастр, ограничения, коммуникации, «что рядом»</li>
            <li>Отрисовка контура и подача заявления на НаДальнийВосток.РФ</li>
            <li>Обязательный план освоения — составим под вашу цель (дом, ферма, туризм, бизнес)</li>
            <li>Через 4,5 года — сопровождение оформления в собственность или аренду</li>
          </ul>
          <button className="btn btn-secondary btn-sm" onClick={() => scrollToForm("hectare")}>Получить гектар без ошибок →</button>
        </div>

        {/* Пакет В — инвесторам */}
        <div style={{ ...card, marginBottom: 20, background: "linear-gradient(135deg, var(--surface), rgba(202,138,4,0.06))" }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap", marginBottom: 8 }}>
            <h2 style={{ fontSize: 22, fontWeight: 700, margin: 0 }}>💼 Инвесторам</h2>
            <span className="badge" style={{ background: "#fef3c7", color: "#92400e" }}>земля с торгов в 2+ раза ниже рынка</span>
          </div>
          <p style={{ color: "var(--text-2)", fontSize: 14, lineHeight: 1.65, marginBottom: 18 }}>
            Мы находим ликвидные участки на торгах по всей России с дисконтом к рынку и зарабатываем
            на их перепродаже вместе с вами. География — вся РФ; выбираем не «где хочется», а где
            математика сделки сильнее. Четыре формата сотрудничества:
          </p>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 14, marginBottom: 16 }}>
            <div style={{ border: "1px solid var(--border)", borderRadius: 10, padding: 16 }}>
              <div style={{ fontWeight: 700, marginBottom: 6 }}>1 · Партнёрство 50/50</div>
              <div style={{ fontSize: 13, color: "var(--text-2)", lineHeight: 1.6 }}>
                Чистая прибыль сделки (за вычетом расходов) делится пополам. Команда делает всё под ключ —
                от анализа и осмотра лота до реализации. Без гарантированной доходности, но с чёткой
                финмоделью и ориентирами по срокам. Лоты от 3 млн ₽. Оформление на инвестора.
              </div>
            </div>
            <div style={{ border: "1px solid var(--border)", borderRadius: 10, padding: 16 }}>
              <div style={{ fontWeight: 700, marginBottom: 6 }}>2 · Фиксированная доходность</div>
              <div style={{ fontSize: 13, color: "var(--text-2)", lineHeight: 1.6 }}>
                Целевая ставка оговаривается по каждому лоту (ориентир — до 30% годовых) через
                краудлендинговую платформу. Низкий порог входа — от 10–100 тыс ₽. Чёткий срок выхода,
                обеспечение — сам участок (обременение через платформу до реализации).
              </div>
            </div>
            <div style={{ border: "1px solid var(--border)", borderRadius: 10, padding: 16 }}>
              <div style={{ fontWeight: 700, marginBottom: 6 }}>3 · Покупка за агентское вознаграждение</div>
              <div style={{ fontSize: 13, color: "var(--text-2)", lineHeight: 1.6 }}>
                Мы находим и выигрываем лот для вас — вознаграждение сразу. Вся прибыль сделки ваша:
                продавайте сами, оставьте себе или поручите реализацию нам. Лоты от 3 млн ₽.
                Оформление на инвестора.
              </div>
            </div>
            <div style={{ border: "1px solid var(--border)", borderRadius: 10, padding: 16 }}>
              <div style={{ fontWeight: 700, marginBottom: 6 }}>4 · Гектар как актив (ДВГ/АГ)</div>
              <div style={{ fontSize: 13, color: "var(--text-2)", lineHeight: 1.6 }}>
                Оформление бесплатных гектаров по госпрограммам под инвестиционные цели —
                туризм, глэмпинг, фермерство. Это не торги: вход — только стоимость нашего сопровождения.
              </div>
            </div>
          </div>

          <button className="btn btn-primary btn-sm" onClick={() => scrollToForm("investor")}>Обсудить инвестиции →</button>
          <p style={{ fontSize: 11, color: "var(--text-3)", marginTop: 12, lineHeight: 1.5 }}>
            Информация не является публичной офертой и индивидуальной инвестиционной рекомендацией.
            Условия каждой сделки фиксируются договором.
          </p>
        </div>

        {/* Форма заявки */}
        <div id="request-form" style={{ ...card, borderColor: "var(--primary)" }}>
          <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 6 }}>Оставить заявку</h2>
          <p style={{ fontSize: 13, color: "var(--text-3)", marginBottom: 18 }}>
            Ответим в течение рабочего дня в Telegram или по телефону.
            {lotId && <> Заявка привязана к <a href={`/lots/${lotId}`}>лоту #{lotId}</a>.</>}
          </p>

          {sent ? (
            <div style={{ padding: 24, textAlign: "center", background: "#dcfce7", borderRadius: 10, color: "#166534", fontWeight: 600 }}>
              ✅ Заявка отправлена! Свяжемся с вами в ближайшее время.
            </div>
          ) : (
            <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 12, maxWidth: 480 }}>
              <select
                className="input"
                value={form.package}
                onChange={e => setForm(f => ({ ...f, package: e.target.value }))}
                style={{ padding: "10px 12px", borderRadius: 8, border: "1px solid var(--border)", background: "var(--surface)", color: "var(--text)" }}
              >
                <option value="turnkey">Участие в торгах под ключ</option>
                <option value="hectare">ДВ/Арктический гектар</option>
                <option value="investor">Инвестору</option>
                {lotId && <option value="lot">По лоту #{lotId}</option>}
              </select>
              <input
                className="input" placeholder="Ваше имя"
                value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                style={{ padding: "10px 12px", borderRadius: 8, border: "1px solid var(--border)", background: "var(--surface)", color: "var(--text)" }}
              />
              <input
                className="input" placeholder="Телефон или @telegram"
                value={form.contact} onChange={e => setForm(f => ({ ...f, contact: e.target.value }))}
                style={{ padding: "10px 12px", borderRadius: 8, border: "1px solid var(--border)", background: "var(--surface)", color: "var(--text)" }}
              />
              <textarea
                className="input" placeholder="Коротко о задаче (необязательно)"
                value={form.comment} onChange={e => setForm(f => ({ ...f, comment: e.target.value }))}
                rows={3}
                style={{ padding: "10px 12px", borderRadius: 8, border: "1px solid var(--border)", background: "var(--surface)", color: "var(--text)", resize: "vertical" }}
              />
              {err && <div style={{ color: "#dc2626", fontSize: 13 }}>{err}</div>}
              <button type="submit" className="btn btn-primary" disabled={sending} style={{ padding: "12px" }}>
                {sending ? "Отправка..." : "Отправить заявку"}
              </button>
              <p style={{ fontSize: 11, color: "var(--text-3)", margin: 0 }}>
                Нажимая кнопку, вы соглашаетесь с <a href="/privacy">политикой конфиденциальности</a>.
              </p>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}

export default function ServicesPage() {
  return (
    <Suspense fallback={<div style={{ padding: 40, textAlign: "center", color: "var(--text-3)" }}>Загрузка...</div>}>
      <ServicesInner />
    </Suspense>
  );
}
