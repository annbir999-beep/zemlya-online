import type { Metadata } from "next";
import ChecklistForm from "./ChecklistForm";

export const metadata: Metadata = {
  title: "Чеклист: 12 проверок участка перед торгами — Торги Земли",
  description:
    "Бесплатный чеклист: 12 проверок земельного участка перед аукционом. ВРИ, площадь ЕГРН, ЗОУИТ, переуступка по ст.22 ЗК, техусловия. Скачайте PDF на почту.",
};

const PREVIEW_ITEMS = [
  "ВРИ против вашей цели — подходит ли разрешённое использование под застройку",
  "Расхождение площади ЕГРН и объявления — сколько земли вы реально получаете",
  "ЗОУИТ и обременения — охранные зоны, сервитуты, аресты",
  "Переуступка и субаренда по ст.22 ЗК РФ — можно ли передать права",
  "Технические условия — подключение электричества, газа, воды",
];

export default function ChecklistPage() {
  return (
    <div style={{ flex: 1, display: "flex", justifyContent: "center", padding: 24 }}>
      <div style={{ width: "100%", maxWidth: 560 }}>
        {/* Шапка с бренд-градиентом */}
        <div
          style={{
            background: "linear-gradient(135deg, #16a34a, #0d9488)",
            color: "#fff",
            padding: "32px 28px",
            borderRadius: "12px 12px 0 0",
          }}
        >
          <h1 style={{ fontSize: 26, fontWeight: 700, lineHeight: 1.25, margin: 0 }}>
            Чеклист: 12 проверок участка перед торгами
          </h1>
          <p style={{ fontSize: 15, lineHeight: 1.5, marginTop: 12, marginBottom: 0, opacity: 0.95 }}>
            Большинство дорогих ошибок на торгах — это пропущенный пункт проверки. Один лист, по
            которому вы пройдёте лот за 10 минут и не купите проблему.
          </p>
        </div>

        {/* Тело карточки */}
        <div
          style={{
            background: "var(--surface)",
            padding: "28px",
            borderRadius: "0 0 12px 12px",
            boxShadow: "var(--shadow-md)",
            display: "flex",
            flexDirection: "column",
            gap: 24,
          }}
        >
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-2)", marginBottom: 12 }}>
              Что внутри (5 из 12 пунктов):
            </div>
            <ul style={{ margin: 0, paddingLeft: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 10 }}>
              {PREVIEW_ITEMS.map((item) => (
                <li key={item} style={{ display: "flex", gap: 10, fontSize: 14, lineHeight: 1.5, color: "var(--text)" }}>
                  <span style={{ color: "#16a34a", fontWeight: 700, flexShrink: 0 }}>✓</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>

          <ChecklistForm />
        </div>
      </div>
    </div>
  );
}
