"use client";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";

interface RoiResponse {
  inputs: {
    house_area_sqm: number;
    sell_price_per_sqm: number;
    finish_level: string;
  };
  build: {
    base_cost_per_sqm: number;
    regional_cost_per_sqm: number;
    total_cost: number;
    region_coefficient: number;
    finish_level: string;
  };
  land_price: number;
  total_investment: number;
  expected_revenue: number;
  expected_profit: number;
  roi_pct: number;
  payback_years: number | null;
}

const FINISH_LABELS: Record<string, string> = {
  rough: "Черновая",
  mid: "Чистовая",
  premium: "Под ключ",
};

const fmt = (v: number) => Math.round(v).toLocaleString("ru");

export default function RoiCalculator({ lotId }: { lotId: number }) {
  const [houseArea, setHouseArea] = useState(120);
  const [sellPrice, setSellPrice] = useState(80000);
  const [finishLevel, setFinishLevel] = useState<"rough" | "mid" | "premium">("mid");
  const [data, setData] = useState<RoiResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => {
      setLoading(true);
      api
        .get<RoiResponse>(
          `/api/lots/${lotId}/roi?house_area_sqm=${houseArea}&sell_price_per_sqm=${sellPrice}&finish_level=${finishLevel}`,
        )
        .then(setData)
        .finally(() => setLoading(false));
    }, 250);
    return () => clearTimeout(t);
  }, [lotId, houseArea, sellPrice, finishLevel]);

  const profitColor = !data
    ? "var(--text-3)"
    : data.expected_profit > 0
      ? "#16a34a"
      : "#dc2626";

  return (
    <div style={{
      background: "var(--surface)", border: "1px solid var(--border)",
      borderRadius: 12, padding: 16,
    }}>
      <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 12 }}>
        🧮 Калькулятор окупаемости (каркасный дом)
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <div>
          <Label>Площадь дома: <b>{houseArea} м²</b></Label>
          <input
            type="range"
            min={40}
            max={300}
            step={10}
            value={houseArea}
            onChange={(e) => setHouseArea(Number(e.target.value))}
            style={{ width: "100%" }}
          />
        </div>

        <div>
          <Label>Уровень отделки</Label>
          <div style={{ display: "flex", gap: 6 }}>
            {(["rough", "mid", "premium"] as const).map((lv) => (
              <button
                key={lv}
                type="button"
                onClick={() => setFinishLevel(lv)}
                className="btn btn-sm"
                style={{
                  background: finishLevel === lv ? "var(--primary)" : "var(--surface-2)",
                  color: finishLevel === lv ? "white" : "var(--text-2)",
                  fontSize: 12, flex: 1,
                }}
              >
                {FINISH_LABELS[lv]}
              </button>
            ))}
          </div>
        </div>

        <div>
          <Label>Цена продажи готового дома: <b>{fmt(sellPrice)} ₽/м²</b></Label>
          <input
            type="range"
            min={30000}
            max={250000}
            step={5000}
            value={sellPrice}
            onChange={(e) => setSellPrice(Number(e.target.value))}
            style={{ width: "100%" }}
          />
        </div>
      </div>

      {data && (
        <div style={{ marginTop: 16, padding: 12, background: "var(--surface-2)", borderRadius: 8 }}>
          <Row label="Стоимость участка" value={`${fmt(data.land_price)} ₽`} />
          <Row
            label={`Постройка (${fmt(data.build.regional_cost_per_sqm)} ₽/м²${
              data.build.region_coefficient !== 1 ? `, коэф. ${data.build.region_coefficient}` : ""
            })`}
            value={`${fmt(data.build.total_cost)} ₽`}
          />
          <Row
            label="Всего вложений"
            value={`${fmt(data.total_investment)} ₽`}
            bold
          />
          <hr style={{ border: "none", borderTop: "1px solid var(--border)", margin: "8px 0" }} />
          <Row label="Выручка от продажи" value={`${fmt(data.expected_revenue)} ₽`} />
          <Row
            label="Прибыль"
            value={`${data.expected_profit >= 0 ? "+" : ""}${fmt(data.expected_profit)} ₽`}
            color={profitColor}
            bold
          />
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 10 }}>
            <span style={{ fontSize: 12, color: "var(--text-3)" }}>ROI</span>
            <span style={{ fontWeight: 700, fontSize: 18, color: profitColor }}>
              {data.roi_pct >= 0 ? "+" : ""}{data.roi_pct}%
            </span>
          </div>
          {data.payback_years && data.payback_years < 100 && (
            <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4 }}>
              <span style={{ fontSize: 12, color: "var(--text-3)" }}>Окупаемость</span>
              <span style={{ fontSize: 13, fontWeight: 600 }}>
                {data.payback_years.toFixed(1)} лет
              </span>
            </div>
          )}
        </div>
      )}

      {loading && (
        <div style={{ fontSize: 11, color: "var(--text-3)", marginTop: 6, textAlign: "right" }}>
          Расчёт...
        </div>
      )}

      <div style={{ fontSize: 11, color: "var(--text-3)", marginTop: 10, lineHeight: 1.5 }}>
        💡 Базовая цена каркасника по РФ — 35–75 тыс. ₽/м² в зависимости от
        отделки. Для региона учитывается коэффициент логистики и ставок бригад.
        Расчёт ориентировочный, без учёта подключения газа/центральной канализации,
        ландшафта и налоговых платежей.
      </div>
    </div>
  );
}

function Label({ children }: { children: React.ReactNode }) {
  return <div style={{ fontSize: 12, color: "var(--text-3)", marginBottom: 4 }}>{children}</div>;
}

function Row({
  label, value, bold, color,
}: { label: string; value: string; bold?: boolean; color?: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 4 }}>
      <span style={{ color: "var(--text-3)", flex: 1, paddingRight: 12 }}>{label}</span>
      <span style={{ fontWeight: bold ? 700 : 500, color: color || "inherit" }}>{value}</span>
    </div>
  );
}
