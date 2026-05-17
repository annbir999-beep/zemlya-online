"use client";
import { useState, useMemo } from "react";
import { api } from "@/lib/api";
import { REGIONS, LAND_PURPOSES } from "@/lib/filters";

type Channel = "email" | "telegram" | "both";

interface Props {
  hasTelegram: boolean;
  onCreated: () => void;
  onClose: () => void;
}

const DEAL_TYPES = [
  { value: "ownership", label: "В собственность" },
  { value: "lease", label: "В аренду" },
  { value: "free_use", label: "Безвозмездное пользование" },
];
const AUCTION_TYPES = [
  { value: "sale", label: "Продажа" },
  { value: "rent", label: "Аренда" },
  { value: "priv", label: "Приватизация" },
];
const AUCTION_FORMS = [
  { value: "auction", label: "Аукцион" },
  { value: "tender", label: "Конкурс" },
  { value: "public", label: "Публичное предложение" },
  { value: "without", label: "Без торгов" },
];
const LIQUIDITY_OPTS = [
  { value: "", label: "Любая" },
  { value: "high", label: "Высокая (≤30 км до 500k+)" },
  { value: "medium", label: "Средняя (≤100 км до 100k+)" },
  { value: "low", label: "Низкая" },
];

export default function CreateAlertModal({ hasTelegram, onCreated, onClose }: Props) {
  const [name, setName] = useState("");
  const [regionSearch, setRegionSearch] = useState("");
  const [regions, setRegions] = useState<string[]>([]);
  const [priceMin, setPriceMin] = useState("");
  const [priceMax, setPriceMax] = useState("");
  const [areaMin, setAreaMin] = useState("");
  const [areaMax, setAreaMax] = useState("");
  const [purposes, setPurposes] = useState<string[]>([]);
  const [auctionTypes, setAuctionTypes] = useState<string[]>([]);
  const [dealTypes, setDealTypes] = useState<string[]>([]);
  const [auctionForms, setAuctionForms] = useState<string[]>([]);
  const [scoreMin, setScoreMin] = useState("");
  const [badgesMin, setBadgesMin] = useState("");
  const [discountMin, setDiscountMin] = useState("");
  const [priceDropMin, setPriceDropMin] = useState("");
  const [liquidity, setLiquidity] = useState("");
  const [pctCadastralMax, setPctCadastralMax] = useState("");
  const [cadToMarketMin, setCadToMarketMin] = useState("");
  const [cadToMarketMax, setCadToMarketMax] = useState("");
  const [cadCostMin, setCadCostMin] = useState("");
  const [cadCostMax, setCadCostMax] = useState("");
  const [depPctMin, setDepPctMin] = useState("");
  const [depPctMax, setDepPctMax] = useState("");
  const [subleaseOnly, setSubleaseOnly] = useState(false);
  const [assignmentOnly, setAssignmentOnly] = useState(false);
  const [channel, setChannel] = useState<Channel>(hasTelegram ? "both" : "email");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const filteredRegions = useMemo(() => {
    const q = regionSearch.toLowerCase().trim();
    return Object.entries(REGIONS).filter(([, name]) =>
      !q || name.toLowerCase().includes(q),
    );
  }, [regionSearch]);

  const toggleRegion = (code: string) =>
    setRegions((p) => (p.includes(code) ? p.filter((c) => c !== code) : [...p, code]));

  const togglePurpose = (val: string) =>
    setPurposes((p) => (p.includes(val) ? p.filter((c) => c !== val) : [...p, val]));

  const submit = async () => {
    setError(null);
    if (!name.trim()) {
      setError("Укажите название фильтра");
      return;
    }
    setSaving(true);
    const num = (s: string) => (s ? Number(s) : undefined);
    try {
      await api.post("/api/alerts", {
        name: name.trim(),
        channel,
        filters: {
          region_codes: regions.length ? regions : undefined,
          price_min: num(priceMin),
          price_max: num(priceMax),
          area_min: num(areaMin),
          area_max: num(areaMax),
          land_purposes: purposes.length ? purposes : undefined,
          auction_types: auctionTypes.length ? auctionTypes : undefined,
          deal_types: dealTypes.length ? dealTypes : undefined,
          auction_forms: auctionForms.length ? auctionForms : undefined,
          score_min: num(scoreMin),
          badges_min: num(badgesMin),
          discount_min: num(discountMin),
          price_drop_min: num(priceDropMin),
          liquidity: liquidity || undefined,
          pct_cadastral_max: num(pctCadastralMax),
          cadastral_to_market_min: num(cadToMarketMin),
          cadastral_to_market_max: num(cadToMarketMax),
          cadastral_cost_min: num(cadCostMin),
          cadastral_cost_max: num(cadCostMax),
          deposit_pct_min: num(depPctMin),
          deposit_pct_max: num(depPctMax),
          sublease_allowed: subleaseOnly ? true : undefined,
          assignment_allowed: assignmentOnly ? true : undefined,
        },
      });
      onCreated();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Ошибка сохранения");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)",
        display: "flex", alignItems: "center", justifyContent: "center",
        zIndex: 1000, padding: 20,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "var(--surface)", borderRadius: 12, width: "100%", maxWidth: 560,
          maxHeight: "90vh", overflowY: "auto", padding: 24,
          border: "1px solid var(--border)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <h2 style={{ fontSize: 18, fontWeight: 700 }}>Новый фильтр</h2>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>✕</button>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <Field label="Название">
            <input
              className="input"
              placeholder="Например: Подмосковье ИЖС до 5 млн"
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoFocus
            />
          </Field>

          <Field label="Регионы (если ничего — все)">
            <input
              className="input"
              placeholder="Поиск региона..."
              value={regionSearch}
              onChange={(e) => setRegionSearch(e.target.value)}
              style={{ marginBottom: 6 }}
            />
            <div style={{
              maxHeight: 140, overflowY: "auto", border: "1px solid var(--border)",
              borderRadius: 6, padding: 8,
            }}>
              {filteredRegions.map(([code, label]) => (
                <label key={code} style={{ display: "block", padding: "3px 0", fontSize: 13, cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={regions.includes(code)}
                    onChange={() => toggleRegion(code)}
                    style={{ marginRight: 6 }}
                  />
                  {label}
                </label>
              ))}
            </div>
            {regions.length > 0 && (
              <div style={{ fontSize: 12, color: "var(--text-3)", marginTop: 4 }}>
                Выбрано: {regions.length}
              </div>
            )}
          </Field>

          <Row>
            <Field label="Цена от, ₽">
              <input className="input" type="number" min={0} value={priceMin} onChange={(e) => setPriceMin(e.target.value)} />
            </Field>
            <Field label="Цена до, ₽">
              <input className="input" type="number" min={0} value={priceMax} onChange={(e) => setPriceMax(e.target.value)} />
            </Field>
          </Row>

          <Row>
            <Field label="Площадь от, м²">
              <input className="input" type="number" min={0} value={areaMin} onChange={(e) => setAreaMin(e.target.value)} />
            </Field>
            <Field label="Площадь до, м²">
              <input className="input" type="number" min={0} value={areaMax} onChange={(e) => setAreaMax(e.target.value)} />
            </Field>
          </Row>

          <Field label="Назначение">
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {LAND_PURPOSES.map((p) => (
                <button
                  key={p.value}
                  className="btn btn-sm"
                  type="button"
                  style={{
                    background: purposes.includes(p.value) ? "var(--primary)" : "var(--surface-2)",
                    color: purposes.includes(p.value) ? "white" : "var(--text-2)",
                    fontSize: 12,
                  }}
                  onClick={() => togglePurpose(p.value)}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </Field>

          {/* Скоринг и финансы */}
          <Row>
            <Field label="Минимальный score (0–100)">
              <input className="input" type="number" min={0} max={100} placeholder="напр. 70"
                value={scoreMin} onChange={e => setScoreMin(e.target.value)} />
            </Field>
            <Field label="Минимум бейджей">
              <input className="input" type="number" min={0} max={10} placeholder="напр. 2"
                value={badgesMin} onChange={e => setBadgesMin(e.target.value)} />
            </Field>
          </Row>

          <Row>
            <Field label="Дисконт к рынку от, %">
              <input className="input" type="number" min={0} max={99} placeholder="напр. 30"
                value={discountMin} onChange={e => setDiscountMin(e.target.value)} />
            </Field>
            <Field label="Снижение на повторных торгах от, %">
              <input className="input" type="number" min={0} max={99} placeholder="напр. 10"
                value={priceDropMin} onChange={e => setPriceDropMin(e.target.value)} />
            </Field>
          </Row>

          <Row>
            <Field label="% НЦ/КС не выше">
              <input className="input" type="number" min={0} max={500} placeholder="напр. 50"
                value={pctCadastralMax} onChange={e => setPctCadastralMax(e.target.value)} />
            </Field>
            <Field label="Ликвидность">
              <select className="select" value={liquidity} onChange={e => setLiquidity(e.target.value)}>
                {LIQUIDITY_OPTS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </Field>
          </Row>

          <Row>
            <Field label="КС/Рынок от, %">
              <input className="input" type="number" min={0} max={500} placeholder="напр. 80"
                value={cadToMarketMin} onChange={e => setCadToMarketMin(e.target.value)} />
            </Field>
            <Field label="КС/Рынок до, %">
              <input className="input" type="number" min={0} max={500} placeholder="напр. 100"
                value={cadToMarketMax} onChange={e => setCadToMarketMax(e.target.value)} />
            </Field>
          </Row>

          <Row>
            <Field label="Кадастр. стоимость от, ₽">
              <input className="input" type="number" min={0} value={cadCostMin}
                onChange={e => setCadCostMin(e.target.value)} />
            </Field>
            <Field label="Кадастр. стоимость до, ₽">
              <input className="input" type="number" min={0} value={cadCostMax}
                onChange={e => setCadCostMax(e.target.value)} />
            </Field>
          </Row>

          <Row>
            <Field label="Задаток от, %">
              <input className="input" type="number" min={0} max={100} value={depPctMin}
                onChange={e => setDepPctMin(e.target.value)} />
            </Field>
            <Field label="Задаток до, %">
              <input className="input" type="number" min={0} max={100} value={depPctMax}
                onChange={e => setDepPctMax(e.target.value)} />
            </Field>
          </Row>

          {/* Вид торгов и сделки */}
          <Field label="Вид сделки (что приобретается)">
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {DEAL_TYPES.map((t) => (
                <button key={t.value} type="button" className="btn btn-sm"
                  style={{
                    background: dealTypes.includes(t.value) ? "var(--primary)" : "var(--surface-2)",
                    color: dealTypes.includes(t.value) ? "white" : "var(--text-2)", fontSize: 12,
                  }}
                  onClick={() => setDealTypes(p => p.includes(t.value) ? p.filter(x => x !== t.value) : [...p, t.value])}
                >{t.label}</button>
              ))}
            </div>
          </Field>

          <Field label="Вид торгов (раздел)">
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {AUCTION_TYPES.map((t) => (
                <button key={t.value} type="button" className="btn btn-sm"
                  style={{
                    background: auctionTypes.includes(t.value) ? "var(--primary)" : "var(--surface-2)",
                    color: auctionTypes.includes(t.value) ? "white" : "var(--text-2)", fontSize: 12,
                  }}
                  onClick={() => setAuctionTypes(p => p.includes(t.value) ? p.filter(x => x !== t.value) : [...p, t.value])}
                >{t.label}</button>
              ))}
            </div>
          </Field>

          <Field label="Форма проведения">
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {AUCTION_FORMS.map((t) => (
                <button key={t.value} type="button" className="btn btn-sm"
                  style={{
                    background: auctionForms.includes(t.value) ? "var(--primary)" : "var(--surface-2)",
                    color: auctionForms.includes(t.value) ? "white" : "var(--text-2)", fontSize: 12,
                  }}
                  onClick={() => setAuctionForms(p => p.includes(t.value) ? p.filter(x => x !== t.value) : [...p, t.value])}
                >{t.label}</button>
              ))}
            </div>
          </Field>

          <Field label="Дополнительно">
            <label className="checkbox-item" style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}>
              <input type="checkbox" checked={subleaseOnly} onChange={e => setSubleaseOnly(e.target.checked)} />
              Только с разрешённой субарендой
            </label>
            <label className="checkbox-item" style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}>
              <input type="checkbox" checked={assignmentOnly} onChange={e => setAssignmentOnly(e.target.checked)} />
              Только с разрешённой переуступкой
            </label>
          </Field>

          <Field label="Куда присылать уведомления">
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {([
                { v: "email" as Channel, label: "📧 Email" },
                { v: "telegram" as Channel, label: hasTelegram ? "✈️ Telegram" : "✈️ Telegram (привяжите в профиле)" },
                { v: "both" as Channel, label: "Оба канала" },
              ]).map(({ v, label }) => (
                <button
                  key={v}
                  type="button"
                  className="btn btn-sm"
                  disabled={(v === "telegram" || v === "both") && !hasTelegram}
                  style={{
                    background: channel === v ? "var(--primary)" : "var(--surface-2)",
                    color: channel === v ? "white" : "var(--text-2)",
                    fontSize: 13,
                    opacity: (v === "telegram" || v === "both") && !hasTelegram ? 0.5 : 1,
                  }}
                  onClick={() => setChannel(v)}
                >
                  {label}
                </button>
              ))}
            </div>
          </Field>

          {error && <div style={{ color: "var(--danger)", fontSize: 13 }}>{error}</div>}

          <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 6 }}>
            <button className="btn btn-ghost" onClick={onClose} disabled={saving}>Отмена</button>
            <button className="btn btn-primary" onClick={submit} disabled={saving}>
              {saving ? "Сохранение..." : "Создать фильтр"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div style={{ fontSize: 12, color: "var(--text-3)", marginBottom: 4 }}>{label}</div>
      {children}
    </div>
  );
}

function Row({ children }: { children: React.ReactNode }) {
  return <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>{children}</div>;
}
