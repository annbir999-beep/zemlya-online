"use client";

export interface RegionData {
  land_buyout?: {
    name?: string;
    direct_3918?: number | string | null;   // ст.39.18 — прямой выкуп с торгов
    house_3920?: number | string | null;    // ст.39.20 — после постройки дома (ИЖС/ЛПХ/сад)
    other_3920?: number | string | null;    // ст.39.20 — иные случаи (коммерч/СХ)
    rev?: string;
  } | null;
  agro_buyout?: { pct: number | null; name?: string; moratorium_until?: string; scale?: string; note?: string } | null;
  kfh_house_allowed?: boolean | null;
  redistribution?: { pct: number | null; name?: string; rate_text?: string } | null;
  verified_through: string;
}

function fmtPct(d?: { pct: number | null; rate_text?: string; scale?: string } | null): string {
  if (!d) return "—";
  if (d.rate_text) return d.rate_text;
  if (d.pct == null) return "не определено";
  const base = `${d.pct}%`;
  return d.scale ? `${base} (${d.scale})` : base;
}

function fmtBuyout(v?: number | string | null): { text: string; isLow: boolean } {
  if (v == null) return { text: "—", isLow: false };
  if (typeof v === "number") {
    return { text: `${v}%`, isLow: v <= 15 };
  }
  // строка: "x10НС", "формула", "50% / 100%" и т.п.
  return { text: String(v), isLow: false };
}

function buyoutCalc(v: number | string | null | undefined, cadastralCost?: number | null): number | null {
  if (typeof v === "number" && cadastralCost) {
    return Math.round((cadastralCost * v) / 100);
  }
  return null;
}

export function RegionInfo({ data, regionName, cadastralCost }: {
  data: RegionData | null;
  regionName?: string;
  cadastralCost?: number | null;
}) {
  if (!data) return null;
  const lb = data.land_buyout;
  const ab = data.agro_buyout;
  const re = data.redistribution;
  const kfh = data.kfh_house_allowed;
  const moratorium = ab?.moratorium_until;

  const direct = fmtBuyout(lb?.direct_3918);
  const house = fmtBuyout(lb?.house_3920);
  const other = fmtBuyout(lb?.other_3920);
  const directCalc = buyoutCalc(lb?.direct_3918, cadastralCost);
  const houseCalc = buyoutCalc(lb?.house_3920, cadastralCost);
  const otherCalc = buyoutCalc(lb?.other_3920, cadastralCost);

  const agroCalc = (ab?.pct != null && cadastralCost) ? Math.round(cadastralCost * ab.pct / 100) : null;
  const redistribCalc = (re?.pct != null && cadastralCost) ? Math.round(cadastralCost * re.pct / 100) : null;

  const cell = (val: { text: string; isLow: boolean }, calc?: number | null) => (
    <td style={{ padding: "10px 16px", fontSize: 13 }}>
      <b style={{ color: val.isLow ? "#0d9488" : "var(--text)" }}>{val.text}</b>
      {calc != null && (
        <span style={{ color: "var(--text-3)", marginLeft: 6, fontSize: 12 }}>
          ≈ {calc.toLocaleString("ru")} ₽
        </span>
      )}
    </td>
  );

  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, overflow: "hidden" }}>
      <div style={{ padding: "14px 16px", fontWeight: 700, fontSize: 15, borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", gap: 8 }}>
        Региональные особенности
        {regionName && <span style={{ fontSize: 12, fontWeight: 400, color: "var(--text-3)" }}>{regionName}</span>}
      </div>

      {/* Блок 1: Цена выкупа — три сценария */}
      <div style={{ padding: "10px 16px 6px", fontSize: 12, fontWeight: 600, color: "var(--text-2)", background: "var(--surface-2)" }}>
        Цена выкупа земельного участка
      </div>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <tbody>
          <tr>
            <td style={{ padding: "10px 16px", color: "var(--text-3)", fontSize: 12, width: "45%", verticalAlign: "top" }}>
              <div>Прямой выкуп с торгов</div>
              <div style={{ fontSize: 10, color: "var(--text-3)", opacity: 0.7 }}>(ст. 39.18 ЗК)</div>
            </td>
            {cell(direct, directCalc)}
          </tr>
          <tr style={{ background: "var(--surface-2)" }}>
            <td style={{ padding: "10px 16px", color: "var(--text-3)", fontSize: 12, verticalAlign: "top" }}>
              <div>После постройки дома (ИЖС/ЛПХ/сад)</div>
              <div style={{ fontSize: 10, color: "var(--text-3)", opacity: 0.7 }}>(ст. 39.20 ЗК)</div>
            </td>
            {cell(house, houseCalc)}
          </tr>
          <tr>
            <td style={{ padding: "10px 16px", color: "var(--text-3)", fontSize: 12, verticalAlign: "top" }}>
              <div>Иные случаи (коммерческий, СХ)</div>
              <div style={{ fontSize: 10, color: "var(--text-3)", opacity: 0.7 }}>(ст. 39.20 ЗК)</div>
            </td>
            {cell(other, otherCalc)}
          </tr>
        </tbody>
      </table>

      {/* Блок 2: Сельхоз-аренда + КФХ-дом + перераспределение */}
      <div style={{ padding: "10px 16px 6px", fontSize: 12, fontWeight: 600, color: "var(--text-2)", background: "var(--surface-2)", borderTop: "1px solid var(--border)" }}>
        Дополнительно
      </div>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <tbody>
          {ab && (
            <tr>
              <td style={{ padding: "10px 16px", color: "var(--text-3)", fontSize: 13, width: "45%" }}>
                Выкуп с/х после 3 лет аренды
              </td>
              <td style={{ padding: "10px 16px", fontSize: 13 }}>
                <b style={{ color: ab.pct != null && ab.pct <= 15 ? "#0d9488" : "var(--text)" }}>{fmtPct(ab)}</b>
                {agroCalc != null && (
                  <span style={{ color: "var(--text-3)", marginLeft: 6, fontSize: 12 }}>
                    ≈ {agroCalc.toLocaleString("ru")} ₽
                  </span>
                )}
                {moratorium && (
                  <div style={{ color: "#dc2626", fontSize: 11, marginTop: 2 }}>
                    Мораторий до {new Date(moratorium).toLocaleDateString("ru")}
                  </div>
                )}
              </td>
            </tr>
          )}
          <tr style={{ background: "var(--surface-2)" }}>
            <td style={{ padding: "10px 16px", color: "var(--text-3)", fontSize: 13 }}>
              Жилой дом КФХ на сельхозке
            </td>
            <td style={{ padding: "10px 16px", fontSize: 13 }}>
              {kfh === true ? <span style={{ color: "#16a34a", fontWeight: 600 }}>Можно</span> :
               kfh === false ? <span style={{ color: "#dc2626", fontWeight: 600 }}>Нельзя</span> :
               kfh === null ? <span style={{ color: "#ca8a04", fontWeight: 600 }}>Частично — зависит от района</span> :
               <span style={{ color: "var(--text-3)" }}>—</span>}
            </td>
          </tr>
          {re && (
            <tr>
              <td style={{ padding: "10px 16px", color: "var(--text-3)", fontSize: 13 }}>
                Перераспределение участка
              </td>
              <td style={{ padding: "10px 16px", fontSize: 13 }}>
                <b>{fmtPct(re)}</b>
                {redistribCalc != null && cadastralCost && (
                  <span style={{ color: "var(--text-3)", marginLeft: 6, fontSize: 12 }}>
                    ≈ {redistribCalc.toLocaleString("ru")} ₽ за такую же доп. площадь
                  </span>
                )}
              </td>
            </tr>
          )}
        </tbody>
      </table>

      <div style={{ padding: "8px 16px", fontSize: 11, color: "var(--text-3)", borderTop: "1px solid var(--border)", background: "var(--surface-2)" }}>
        Данные актуальны на {data.verified_through}. Источник: pro-zemli.ru (Борис Филимонов). Перед сделкой проверьте актуальные региональные постановления.
        {lb?.rev && <span> Ред. документа: {new Date(lb.rev).toLocaleDateString("ru")}.</span>}
      </div>
    </div>
  );
}
