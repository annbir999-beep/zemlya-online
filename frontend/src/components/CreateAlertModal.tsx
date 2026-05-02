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

export default function CreateAlertModal({ hasTelegram, onCreated, onClose }: Props) {
  const [name, setName] = useState("");
  const [regionSearch, setRegionSearch] = useState("");
  const [regions, setRegions] = useState<string[]>([]);
  const [priceMin, setPriceMin] = useState("");
  const [priceMax, setPriceMax] = useState("");
  const [areaMin, setAreaMin] = useState("");
  const [areaMax, setAreaMax] = useState("");
  const [purposes, setPurposes] = useState<string[]>([]);
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
    try {
      await api.post("/api/alerts", {
        name: name.trim(),
        channel,
        filters: {
          region_codes: regions.length ? regions : undefined,
          price_min: priceMin ? Number(priceMin) : undefined,
          price_max: priceMax ? Number(priceMax) : undefined,
          area_min: areaMin ? Number(areaMin) : undefined,
          area_max: areaMax ? Number(areaMax) : undefined,
          land_purposes: purposes.length ? purposes : undefined,
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
