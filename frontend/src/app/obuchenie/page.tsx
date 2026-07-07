import type { Metadata } from "next";
import Link from "next/link";

/* Раздел «Обучение» — школа земельных торгов: 5 уроков от нуля до своего участка.
   Конспекты синхронизированы со сценариями видео-серии «Обучение-01…05»
   (marketing/video/education/goldwork-import-edu.json). Видео добавим по мере готовности. */

export const metadata: Metadata = {
  title: "Обучение земельным торгам — школа Торги Земли",
  description:
    "Бесплатный курс: как покупать землю на государственных аукционах. Что такое торги, как проверить участок, задаток, аукцион и что делать после победы.",
};

const card: React.CSSProperties = {
  background: "var(--surface)",
  border: "1px solid var(--border)",
  borderRadius: 14,
  padding: 24,
  marginBottom: 20,
};

const LESSONS = [
  {
    n: 1,
    title: "Что такое земельные торги",
    time: "3 мин",
    points: [
      "Государство и муниципалитеты продают и сдают в аренду землю через открытые аукционы — часто на 30–60% дешевле рынка.",
      "Основание — Земельный кодекс РФ (ст. 39.3, 39.6, 39.11–39.13): участки под ИЖС, ЛПХ, сельхоз и коммерцию.",
      "Кто предложил лучшую цену — тот и получает участок. Участвовать может любой гражданин РФ.",
      "Все лоты страны публикуются на torgi.gov — а мы собираем их на одной карте со скорингом выгодности.",
    ],
    cta: { href: "/", label: "Открыть карту лотов →" },
  },
  {
    n: 2,
    title: "Как проверить участок перед ставкой",
    time: "5 мин",
    points: [
      "Границы и вид разрешённого использования (ВРИ) — проверяются по кадастровому номеру на публичной кадастровой карте.",
      "Коммуникации: дорога, электричество, вода и газ рядом с участком — половина его реальной стоимости.",
      "Обременения, аресты, охранные зоны — смотрим выписку ЕГРН и документацию лота.",
      "AI-аудит платформы делает эти проверки за минуту и оценивает ликвидность участка.",
    ],
    cta: { href: "/audit-lot", label: "Попробовать AI-аудит →" },
  },
  {
    n: 3,
    title: "Задаток и подача заявки",
    time: "4 мин",
    points: [
      "Для участия вносится задаток — обычно 20–100% от начальной цены (указан в извещении лота).",
      "Заявка подаётся онлайн на электронной торговой площадке; понадобится электронная подпись.",
      "Не выиграли — задаток возвращается полностью в течение нескольких дней.",
      "Выиграли — задаток засчитывается в цену участка.",
    ],
    cta: { href: "/checklist", label: "Скачать чеклист 12 проверок →" },
  },
  {
    n: 4,
    title: "Как проходит аукцион",
    time: "4 мин",
    points: [
      "Аукцион идёт онлайн: участники повышают цену на фиксированный «шаг» (обычно 3% от начальной).",
      "Побеждает последняя ставка. Если заявился только один участник — договор заключают с ним по начальной цене.",
      "Держите стратегию: заранее определите максимум, выше которого не торгуетесь.",
      "Аренда с торгов тоже выгодна: через аренду ≥5 лет возможна переуступка (ст. 22 ЗК РФ).",
    ],
    cta: { href: "/strategies", label: "Стратегии заработка на земле →" },
  },
  {
    n: 5,
    title: "Выиграли: что дальше",
    time: "4 мин",
    points: [
      "Подписываете протокол и договор купли-продажи или аренды с администрацией.",
      "Дальше — межевание (если нужно), вынос границ в натуру и начало освоения.",
      "От первой ставки до старта стройки обычно проходит 1–2 месяца.",
      "Не хотите проходить путь сами — мы сопровождаем сделку под ключ.",
    ],
    cta: { href: "/services", label: "Сопровождение под ключ →" },
  },
];

export default function ObucheniePage() {
  return (
    <div style={{ flex: 1, overflow: "auto" }}>
      <div style={{ maxWidth: 860, margin: "0 auto", padding: "40px 24px 80px" }}>
        {/* Hero */}
        <div style={{ textAlign: "center", marginBottom: 40 }}>
          <h1 style={{ fontSize: 34, fontWeight: 800, marginBottom: 12 }}>
            Школа <span style={{ color: "var(--primary)" }}>земельных торгов</span>
          </h1>
          <p style={{ fontSize: 16, color: "var(--text-2)", maxWidth: 620, margin: "0 auto", lineHeight: 1.6 }}>
            Пять коротких уроков: от «что такое аукцион» до подписанного договора.
            Бесплатно, без воды — только то, что нужно для первой покупки земли у государства.
          </p>
        </div>

        {/* Уроки */}
        {LESSONS.map((l) => (
          <div key={l.n} style={card}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap", marginBottom: 10 }}>
              <span
                style={{
                  width: 34, height: 34, borderRadius: 10, background: "var(--primary-light)",
                  color: "var(--primary-hover)", display: "inline-flex", alignItems: "center",
                  justifyContent: "center", fontWeight: 800, fontSize: 15, flexShrink: 0,
                }}
              >
                {l.n}
              </span>
              <h2 style={{ fontSize: 21, fontWeight: 700, margin: 0 }}>{l.title}</h2>
              <span className="badge badge-gray">{l.time}</span>
              <span className="badge badge-blue">видеоурок</span>
            </div>
            <div style={{ display: "flex", gap: 20, flexWrap: "wrap", alignItems: "flex-start" }}>
              <video
                src={`/edu/edu-0${l.n}.mp4`}
                controls
                playsInline
                preload="metadata"
                style={{
                  width: 220, maxWidth: "100%", aspectRatio: "9 / 16", borderRadius: 12,
                  background: "#000", flexShrink: 0, border: "1px solid var(--border)",
                }}
              />
              <div style={{ flex: 1, minWidth: 240 }}>
                <ul style={{ fontSize: 14, color: "var(--text-2)", lineHeight: 1.85, margin: "0 0 14px 18px", padding: 0 }}>
                  {l.points.map((p, i) => (
                    <li key={i}>{p}</li>
                  ))}
                </ul>
                <Link href={l.cta.href} className="btn btn-secondary btn-sm">
                  {l.cta.label}
                </Link>
              </div>
            </div>
          </div>
        ))}

        {/* Финальный CTA */}
        <div style={{ ...card, textAlign: "center", borderColor: "var(--primary)", marginTop: 32 }}>
          <h2 style={{ fontSize: 22, fontWeight: 800, marginBottom: 8 }}>Готовы к первому участку?</h2>
          <p style={{ color: "var(--text-2)", fontSize: 14, marginBottom: 16, lineHeight: 1.6 }}>
            Зарегистрируйтесь — получите бесплатный AI-аудит лота и доступ к карте
            всех земельных аукционов России.
          </p>
          <div style={{ display: "flex", gap: 10, justifyContent: "center", flexWrap: "wrap" }}>
            <Link href="/register" className="btn btn-primary" style={{ padding: "11px 26px", fontSize: 15 }}>
              Начать бесплатно
            </Link>
            <Link href="/faq" className="btn btn-secondary" style={{ padding: "11px 26px", fontSize: 15 }}>
              Вопросы и ответы
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
