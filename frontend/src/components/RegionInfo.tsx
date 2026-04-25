"use client";

export interface RegionData {
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

export function RegionInfo({ data, regionName, cadastralCost }: {
  data: RegionData | null;
  regionName?: string;
  cadastralCost?: number | null;
}) {
  if (!data) return null;
  const ab = data.agro_buyout;
  const re = data.redistribution;
  const kfh = data.kfh_house_allowed;
  const moratorium = ab?.moratorium_until;

  // Калькуляция выкупа в рублях, если есть КС и %
  const buyoutCalc = (ab?.pct != null && cadastralCost) ? Math.round(cadastralCost * ab.pct / 100) : null;
  const redistribCalc = (re?.pct != null && cadastralCost) ? Math.round(cadastralCost * re.pct / 100) : null;

  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, overflow: "hidden" }}>
      <div style={{ padding: "14px 16px", fontWeight: 700, fontSize: 15, borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", gap: 8 }}>
        Региональные особенности
        {regionName && <span style={{ fontSize: 12, fontWeight: 400, color: "var(--text-3)" }}>{regionName}</span>}
      </div>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <tbody>
          <tr>
            <td style={{ padding: "10px 16px", color: "var(--text-3)", fontSize: 13, width: "45%" }}>
              Выкуп с/х после 3 лет аренды
            </td>
            <td style={{ padding: "10px 16px", fontSize: 13 }}>
              <b style={{ color: ab?.pct != null && ab.pct <= 15 ? "#0d9488" : "var(--text)" }}>
                {fmtPct(ab)}
              </b>
              {buyoutCalc != null && (
                <span style={{ color: "var(--text-3)", marginLeft: 6 }}>
                  ≈ {buyoutCalc.toLocaleString("ru")} ₽
                </span>
              )}
              {moratorium && (
                <div style={{ color: "#dc2626", fontSize: 11, marginTop: 2 }}>
                  Мораторий до {new Date(moratorium).toLocaleDateString("ru")}
                </div>
              )}
            </td>
          </tr>
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
          <tr>
            <td style={{ padding: "10px 16px", color: "var(--text-3)", fontSize: 13 }}>
              Перераспределение участка
            </td>
            <td style={{ padding: "10px 16px", fontSize: 13 }}>
              <b>{fmtPct(re)}</b>
              {redistribCalc != null && cadastralCost && (
                <span style={{ color: "var(--text-3)", marginLeft: 6 }}>
                  ≈ {redistribCalc.toLocaleString("ru")} ₽ за такую же доп. площадь
                </span>
              )}
            </td>
          </tr>
        </tbody>
      </table>
      <div style={{ padding: "8px 16px", fontSize: 11, color: "var(--text-3)", borderTop: "1px solid var(--border)", background: "var(--surface-2)" }}>
        Данные актуальны на {data.verified_through}. Источник: pro-zemli.ru. Перед сделкой проверьте актуальные региональные постановления.
      </div>
    </div>
  );
}
