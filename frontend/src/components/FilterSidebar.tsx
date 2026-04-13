"use client";
import { useState, useEffect } from "react";
import {
  AUCTION_TYPES, LOT_STATUSES, SOURCES, SORT_OPTIONS, REGIONS, FiltersState,
} from "@/lib/filters";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

interface Rubric { id: number; name: string; icon: string }
interface RubricSection { id: string; name: string }

const AUCTION_FORMS = [
  { value: "auction", label: "Аукцион" },
  { value: "tender", label: "Конкурс" },
  { value: "public", label: "Публичное предложение" },
  { value: "without", label: "Без торгов" },
];

const DEAL_TYPES = [
  { value: "ownership", label: "В собственность" },
  { value: "lease", label: "В аренду" },
  { value: "free_use", label: "Безвозмездное пользование" },
  { value: "operational", label: "Оперативное управление" },
];

const RESALE_TYPES = [
  { value: "yes", label: "Можно" },
  { value: "with_notice", label: "Можно уведомив" },
  { value: "with_approval", label: "Можно согласовав" },
  { value: "no", label: "Нельзя" },
];

const AREA_DISCREPANCY = [
  { value: "match", label: "Площадь совпадает" },
  { value: "minor", label: "Расхождение < 10%" },
  { value: "major", label: "Расхождение > 10%" },
  { value: "no_kn", label: "Нет данных КН" },
];

interface Props {
  filters: FiltersState;
  onChange: (f: FiltersState) => void;
  onReset: () => void;
}

// Аккордеон-секция фильтров
function Section({ title, children, defaultOpen = false }: { title: string; children: React.ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div style={{ borderBottom: "1px solid var(--border)" }}>
      <button
        className="btn btn-ghost"
        style={{ width: "100%", justifyContent: "space-between", padding: "10px 0", fontWeight: 600, fontSize: 13, borderRadius: 0 }}
        onClick={() => setOpen(o => !o)}
      >
        {title}
        <span style={{ color: "var(--text-3)", fontSize: 11 }}>{open ? "▲" : "▼"}</span>
      </button>
      {open && <div style={{ paddingBottom: 12, display: "flex", flexDirection: "column", gap: 8 }}>{children}</div>}
    </div>
  );
}

function CheckGroup({ items, selected, onToggle }: {
  items: { value: string; label: string }[];
  selected: string[];
  onToggle: (v: string) => void;
}) {
  return (
    <div className="checkbox-group">
      {items.map(item => (
        <label key={item.value} className="checkbox-item">
          <input type="checkbox" checked={selected.includes(item.value)} onChange={() => onToggle(item.value)} />
          {item.label}
        </label>
      ))}
    </div>
  );
}

function RangeInput({ labelMin, labelMax, min, max, onMin, onMax }: {
  labelMin?: string; labelMax?: string;
  min?: number; max?: number;
  onMin: (v?: number) => void;
  onMax: (v?: number) => void;
}) {
  return (
    <div className="input-range-group">
      <input className="input" type="number" placeholder={labelMin || "от"}
        value={min ?? ""} onChange={e => onMin(e.target.value ? Number(e.target.value) : undefined)} />
      <span className="input-range-sep">—</span>
      <input className="input" type="number" placeholder={labelMax || "до"}
        value={max ?? ""} onChange={e => onMax(e.target.value ? Number(e.target.value) : undefined)} />
    </div>
  );
}

export default function FilterSidebar({ filters, onChange, onReset }: Props) {
  const [regionSearch, setRegionSearch] = useState("");
  const [rubricSections, setRubricSections] = useState<RubricSection[]>([]);
  const [rubricsBySection, setRubricsBySection] = useState<Record<string, Rubric[]>>({});
  const [etpList, setEtpList] = useState<string[]>([]);

  useEffect(() => {
    fetch(`${API}/api/lots/rubrics/grouped`)
      .then(r => r.json())
      .then(d => {
        setRubricSections(d.sections || []);
        setRubricsBySection(d.rubrics_by_section || {});
      })
      .catch(() => {});

    fetch(`${API}/api/lots/etps`)
      .then(r => r.json())
      .then(d => setEtpList(d.etps || []))
      .catch(() => {});
  }, []);

  const set = (key: keyof FiltersState, value: unknown) =>
    onChange({ ...filters, [key]: value, page: 1 });

  const toggleArr = (key: keyof FiltersState, value: string) => {
    const cur = ((filters[key] as string[]) || []);
    const next = cur.includes(value) ? cur.filter(v => v !== value) : [...cur, value];
    set(key, next.length ? next : undefined);
  };

  const toggleRubric = (field: "rubric_tg" | "rubric_kn", id: number) => {
    const cur = ((filters[field] as number[]) || []);
    const next = cur.includes(id) ? cur.filter(v => v !== id) : [...cur, id];
    set(field, next.length ? next : undefined);
  };

  const filteredRegions = Object.entries(REGIONS).filter(([, name]) =>
    name.toLowerCase().includes(regionSearch.toLowerCase())
  );

  const sortValue = filters.sort_by ? `${filters.sort_by}:${filters.sort_order || "asc"}` : "auction_end_date:asc";

  return (
    <aside className="sidebar" style={{ padding: 0 }}>
      {/* Header */}
      <div style={{ padding: "12px 16px", display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--border)", flexShrink: 0 }}>
        <span style={{ fontWeight: 700, fontSize: 15 }}>Фильтры</span>
        <button className="btn btn-ghost btn-sm" onClick={onReset}>Сбросить всё</button>
      </div>

      <div style={{ overflowY: "auto", flex: 1, padding: "0 16px" }}>

        {/* Статус */}
        <Section title="Статус торгов" defaultOpen>
          <select className="select" value={filters.status || ""}
            onChange={e => set("status", e.target.value || undefined)}>
            <option value="">Все</option>
            {LOT_STATUSES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
        </Section>

        {/* Регион */}
        <Section title="Регион" defaultOpen>
          <input className="input" placeholder="Поиск региона..." value={regionSearch}
            onChange={e => setRegionSearch(e.target.value)} />
          <div className="checkbox-group" style={{ maxHeight: 160, overflowY: "auto" }}>
            {filteredRegions.map(([code, name]) => (
              <label key={code} className="checkbox-item">
                <input type="checkbox" checked={(filters.region || []).includes(code)}
                  onChange={() => toggleArr("region", code)} />
                {name}
              </label>
            ))}
          </div>
        </Section>

        {/* Начальная цена */}
        <Section title="Начальная цена, ₽" defaultOpen>
          <RangeInput
            min={filters.price_min} max={filters.price_max}
            onMin={v => set("price_min", v)} onMax={v => set("price_max", v)}
          />
        </Section>

        {/* % НЦ / КС */}
        <Section title="% НЦ / Кадастровая стоимость">
          <div style={{ fontSize: 12, color: "var(--text-3)", marginBottom: 4 }}>
            Соотношение начальной цены к кадастровой стоимости
          </div>
          <RangeInput
            labelMin="более %" labelMax="менее %"
            min={filters.pct_cadastral_min} max={filters.pct_cadastral_max}
            onMin={v => set("pct_cadastral_min", v)} onMax={v => set("pct_cadastral_max", v)}
          />
        </Section>

        {/* Кадастровая стоимость */}
        <Section title="Кадастровая стоимость, ₽">
          <RangeInput
            min={filters.cadastral_cost_min} max={filters.cadastral_cost_max}
            onMin={v => set("cadastral_cost_min", v)} onMax={v => set("cadastral_cost_max", v)}
          />
        </Section>

        {/* Задаток */}
        <Section title="Задаток">
          <div style={{ fontSize: 12, color: "var(--text-3)", marginBottom: 4 }}>В рублях</div>
          <RangeInput
            min={filters.deposit_min} max={filters.deposit_max}
            onMin={v => set("deposit_min", v)} onMax={v => set("deposit_max", v)}
          />
          <div style={{ fontSize: 12, color: "var(--text-3)", margin: "8px 0 4px" }}>В процентах от НЦ</div>
          <RangeInput
            labelMin="от %" labelMax="до %"
            min={filters.deposit_pct_min} max={filters.deposit_pct_max}
            onMin={v => set("deposit_pct_min", v)} onMax={v => set("deposit_pct_max", v)}
          />
        </Section>

        {/* Площадь TG */}
        <Section title="Площадь [TG], кв.м">
          <div style={{ fontSize: 12, color: "var(--text-3)", marginBottom: 4 }}>Данные torgi.gov</div>
          <RangeInput
            min={filters.area_min} max={filters.area_max}
            onMin={v => set("area_min", v)} onMax={v => set("area_max", v)}
          />
        </Section>

        {/* Площадь КН */}
        <Section title="Площадь [КН], кв.м">
          <div style={{ fontSize: 12, color: "var(--text-3)", marginBottom: 4 }}>Данные Росреестра</div>
          <RangeInput
            min={filters.area_kn_min} max={filters.area_kn_max}
            onMin={v => set("area_kn_min", v)} onMax={v => set("area_kn_max", v)}
          />
          <div style={{ marginTop: 6 }}>
            <CheckGroup items={AREA_DISCREPANCY}
              selected={(filters.area_discrepancy as string[]) || []}
              onToggle={v => toggleArr("area_discrepancy", v)} />
          </div>
        </Section>

        {/* Рубрики [TG] */}
        <Section title="Рубрика [TG]">
          <div style={{ fontSize: 12, color: "var(--text-3)", marginBottom: 6 }}>
            Нормализованный ВРИ по данным torgi.gov
          </div>
          {rubricSections.map(sec => {
            const items = rubricsBySection[sec.id] || [];
            if (!items.length) return null;
            return (
              <div key={sec.id}>
                <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: "0.04em", margin: "8px 0 4px" }}>
                  {sec.name}
                </div>
                <div className="checkbox-group">
                  {items.map(r => (
                    <label key={r.id} className="checkbox-item">
                      <input type="checkbox"
                        checked={((filters.rubric_tg as number[]) || []).includes(r.id)}
                        onChange={() => toggleRubric("rubric_tg", r.id)} />
                      <span>{r.icon}</span> {r.name}
                    </label>
                  ))}
                </div>
              </div>
            );
          })}
        </Section>

        {/* Рубрики [КН] */}
        <Section title="Рубрика [КН]">
          <div style={{ fontSize: 12, color: "var(--text-3)", marginBottom: 6 }}>
            Нормализованный ВРИ по данным Росреестра
          </div>
          {rubricSections.map(sec => {
            const items = rubricsBySection[sec.id] || [];
            if (!items.length) return null;
            return (
              <div key={sec.id}>
                <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: "0.04em", margin: "8px 0 4px" }}>
                  {sec.name}
                </div>
                <div className="checkbox-group">
                  {items.map(r => (
                    <label key={r.id} className="checkbox-item">
                      <input type="checkbox"
                        checked={((filters.rubric_kn as number[]) || []).includes(r.id)}
                        onChange={() => toggleRubric("rubric_kn", r.id)} />
                      <span>{r.icon}</span> {r.name}
                    </label>
                  ))}
                </div>
              </div>
            );
          })}
        </Section>

        {/* Вид торгов */}
        <Section title="Вид торгов">
          <CheckGroup items={AUCTION_TYPES}
            selected={(filters.auction_type as string[]) || []}
            onToggle={v => toggleArr("auction_type", v)} />
        </Section>

        {/* Вид сделки */}
        <Section title="Вид сделки">
          <CheckGroup items={DEAL_TYPES}
            selected={(filters.deal_type as string[]) || []}
            onToggle={v => toggleArr("deal_type", v)} />
        </Section>

        {/* Форма проведения */}
        <Section title="Форма проведения">
          <CheckGroup items={AUCTION_FORMS}
            selected={(filters.auction_form as string[]) || []}
            onToggle={v => toggleArr("auction_form", v)} />
        </Section>

        {/* Переуступка */}
        <Section title="Переуступка">
          <CheckGroup items={RESALE_TYPES}
            selected={(filters.resale_type as string[]) || []}
            onToggle={v => toggleArr("resale_type", v)} />
        </Section>

        {/* Даты подачи заявок */}
        <Section title="Даты подачи заявок">
          <div style={{ fontSize: 12, color: "var(--text-3)", marginBottom: 4 }}>Начало подачи заявок</div>
          <div className="input-range-group">
            <input className="input" type="date"
              value={(filters.submission_start_from as string) || ""}
              onChange={e => set("submission_start_from", e.target.value || undefined)} />
            <span className="input-range-sep">—</span>
            <input className="input" type="date"
              value={(filters.submission_start_to as string) || ""}
              onChange={e => set("submission_start_to", e.target.value || undefined)} />
          </div>
          <div style={{ fontSize: 12, color: "var(--text-3)", margin: "8px 0 4px" }}>Окончание подачи заявок</div>
          <div className="input-range-group">
            <input className="input" type="date"
              value={(filters.submission_end_from as string) || ""}
              onChange={e => set("submission_end_from", e.target.value || undefined)} />
            <span className="input-range-sep">—</span>
            <input className="input" type="date"
              value={(filters.submission_end_to as string) || ""}
              onChange={e => set("submission_end_to", e.target.value || undefined)} />
          </div>
        </Section>

        {/* ЭТП */}
        <Section title="ЭТП">
          {etpList.length > 0
            ? <CheckGroup
                items={etpList.map(e => ({ value: e, label: e }))}
                selected={(filters.etp as string[]) || []}
                onToggle={v => toggleArr("etp", v)}
              />
            : <div style={{ fontSize: 12, color: "var(--text-3)" }}>Загрузка...</div>
          }
        </Section>

        {/* Местоположение */}
        <Section title="Местоположение">
          <CheckGroup
            items={[
              { value: "with_coords", label: "Координаты определены" },
              { value: "no_coords", label: "Координаты не определены" },
            ]}
            selected={(filters.has_coords as string[]) || []}
            onToggle={v => toggleArr("has_coords", v)}
          />
        </Section>

        {/* Кадастровый номер */}
        <Section title="Кадастровый номер / Извещение">
          <input className="input" placeholder="77:01:0001001:123"
            value={(filters.cadastral as string) || ""}
            onChange={e => set("cadastral", e.target.value || undefined)} />
          <input className="input" placeholder="Номер извещения, лота"
            value={(filters.notice_number as string) || ""}
            onChange={e => set("notice_number", e.target.value || undefined)} />
        </Section>

        {/* Источник */}
        <Section title="Источник данных">
          <CheckGroup items={SOURCES}
            selected={(filters.source as string[]) || []}
            onToggle={v => toggleArr("source", v)} />
        </Section>

        {/* Сортировка */}
        <Section title="Сортировка">
          <select className="select" value={sortValue}
            onChange={e => {
              const [by, order] = e.target.value.split(":");
              onChange({ ...filters, sort_by: by, sort_order: order, page: 1 });
            }}>
            {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </Section>

      </div>
    </aside>
  );
}
