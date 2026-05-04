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

// На гос-аукционах земли встречаются только LEASE и OWNERSHIP — free_use/
// operational практически не публикуются, поэтому в UI скрыты, чтобы не давать
// 0 результатов. При появлении реальных лотов вернём пресеты.
const DEAL_TYPES = [
  { value: "ownership", label: "В собственность" },
  { value: "lease", label: "В аренду" },
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
  const [sectionList, setSectionList] = useState<string[]>([]);
  const [auctionTypeList, setAuctionTypeList] = useState<{ value: string; label: string }[]>([]);
  const [vriQuery, setVriQuery] = useState("");
  const [vriSuggestions, setVriSuggestions] = useState<string[]>([]);

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

    fetch(`${API}/api/lots/sections`)
      .then(r => r.json())
      .then(d => setSectionList(d.sections || []))
      .catch(() => {});

    fetch(`${API}/api/lots/categories`)
      .then(r => r.json())
      .then(d => {
        const AT_LABELS: Record<string, string> = {
          sale: "Продажа",
          rent: "Аренда",
          priv: "Приватизация",
        };
        setAuctionTypeList((d.auction_types || []).map((v: string) => ({
          value: v,
          label: AT_LABELS[v] || v,
        })));
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      fetch(`${API}/api/lots/vri-search?q=${encodeURIComponent(vriQuery)}`)
        .then(r => r.json())
        .then(d => setVriSuggestions(d.items || []))
        .catch(() => {});
    }, 300);
    return () => clearTimeout(timer);
  }, [vriQuery]);

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

  const sortValue = filters.sort_by ? `${filters.sort_by}:${filters.sort_order || "asc"}` : "submission_end:asc";

  return (
    <aside className="sidebar" style={{ padding: 0 }}>
      {/* Header */}
      <div style={{ padding: "12px 16px", display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--border)", flexShrink: 0 }}>
        <span style={{ fontWeight: 700, fontSize: 15 }}>Фильтры</span>
        <button className="btn btn-ghost btn-sm" onClick={onReset}>Сбросить всё</button>
      </div>

      <div style={{ overflowY: "auto", flex: 1, padding: "0 16px" }}>

        {/* Сортировка */}
        <Section title="Сортировка" defaultOpen>
          <select className="select" value={sortValue}
            onChange={e => {
              const [by, order] = e.target.value.split(":");
              onChange({ ...filters, sort_by: by, sort_order: order, page: 1 });
            }}>
            {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </Section>

        {/* Рентабельность 🔥 */}
        <Section title="🔥 Рентабельность" defaultOpen>
          <div style={{ fontSize: 12, color: "var(--text-3)", marginBottom: 6 }}>Минимальный скор (0-100)</div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 12 }}>
            {[null, 40, 60, 70, 80].map(v => (
              <button key={String(v)} className="btn btn-sm" style={{
                background: filters.score_min === v ? "var(--primary)" : "var(--surface-2)",
                color: filters.score_min === v ? "white" : "var(--text-2)",
                fontSize: 12, padding: "4px 10px",
              }} onClick={() => set("score_min", v ?? undefined)}>
                {v == null ? "Все" : `≥${v}`}
              </button>
            ))}
          </div>
          <div style={{ fontSize: 12, color: "var(--text-3)", marginBottom: 6 }}>Минимум бейджей</div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 12 }}>
            {[null, 1, 2, 3, 4].map(v => (
              <button key={String(v)} className="btn btn-sm" style={{
                background: filters.badges_min === v ? "var(--primary)" : "var(--surface-2)",
                color: filters.badges_min === v ? "white" : "var(--text-2)",
                fontSize: 12, padding: "4px 10px",
              }} onClick={() => set("badges_min", v ?? undefined)}>
                {v == null ? "Все" : `≥${v}`}
              </button>
            ))}
          </div>
          <div style={{ fontSize: 12, color: "var(--text-3)", marginBottom: 6 }}>Дисконт к рынку, %</div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {[null, 10, 25, 40, 50].map(v => (
              <button key={String(v)} className="btn btn-sm" style={{
                background: filters.discount_min === v ? "var(--primary)" : "var(--surface-2)",
                color: filters.discount_min === v ? "white" : "var(--text-2)",
                fontSize: 12, padding: "4px 10px",
              }} onClick={() => set("discount_min", v ?? undefined)}>
                {v == null ? "Все" : `${v}%+`}
              </button>
            ))}
          </div>
        </Section>

        {/* Ликвидность 💧 */}
        <Section title="💧 Ликвидность" defaultOpen>
          <div style={{ fontSize: 12, color: "var(--text-3)", marginBottom: 6 }}>
            По близости к крупному городу
          </div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {([
              { v: undefined, label: "Все" },
              { v: "high", label: "Высокая" },
              { v: "medium", label: "Средняя" },
              { v: "low", label: "Низкая" },
            ] as const).map(({ v, label }) => (
              <button key={String(v)} className="btn btn-sm" style={{
                background: filters.liquidity === v ? "var(--primary)" : "var(--surface-2)",
                color: filters.liquidity === v ? "white" : "var(--text-2)",
                fontSize: 12, padding: "4px 10px",
              }} onClick={() => set("liquidity", v)}>
                {label}
              </button>
            ))}
          </div>
          <div style={{ fontSize: 11, color: "var(--text-3)", marginTop: 6, lineHeight: 1.4 }}>
            Высокая: ≤30 км до города 500k+&nbsp;·&nbsp;
            Средняя: ≤100 км до города 100k+&nbsp;·&nbsp;
            Низкая: дальше 100 км или у малого города
          </div>
        </Section>

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

        {/* ВРИ [TG] */}
        <Section title="ВРИ [TG]">
          <div style={{ position: "relative" }}>
            <input
              className="input"
              placeholder="Поиск по виду разрешённого использования..."
              value={vriQuery}
              onChange={e => setVriQuery(e.target.value)}
            />
            {vriSuggestions.length > 0 && vriQuery && (
              <div style={{
                position: "absolute", top: "100%", left: 0, right: 0, zIndex: 10,
                background: "var(--surface)", border: "1px solid var(--border)",
                borderRadius: 6, maxHeight: 180, overflowY: "auto", boxShadow: "var(--shadow-md)"
              }}>
                {vriSuggestions.map(item => (
                  <div
                    key={item}
                    style={{ padding: "6px 10px", fontSize: 12, cursor: "pointer" }}
                    onMouseDown={() => {
                      const cur = (filters.vri_tg as string[]) || [];
                      if (!cur.includes(item)) set("vri_tg", [...cur, item]);
                      setVriQuery("");
                      setVriSuggestions([]);
                    }}
                  >
                    {item}
                  </div>
                ))}
              </div>
            )}
          </div>
          {/* Выбранные ВРИ */}
          {((filters.vri_tg as string[]) || []).map(v => (
            <div key={v} style={{
              display: "flex", alignItems: "center", gap: 6,
              background: "var(--primary-light, #eff6ff)", borderRadius: 4,
              padding: "3px 8px", fontSize: 12
            }}>
              <span style={{ flex: 1 }}>{v}</span>
              <button
                onClick={() => set("vri_tg", ((filters.vri_tg as string[]) || []).filter(x => x !== v))}
                style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-3)", fontSize: 14, lineHeight: 1 }}
              >×</button>
            </div>
          ))}
        </Section>

        {/* Раздел torgi.gov */}
        <Section title="Раздел торгов">
          {sectionList.length > 0
            ? <CheckGroup
                items={sectionList.map(s => ({ value: s, label: s }))}
                selected={(filters.section_tg as string[]) || []}
                onToggle={v => toggleArr("section_tg", v)}
              />
            : <div style={{ fontSize: 12, color: "var(--text-3)" }}>Загрузка...</div>
          }
        </Section>

        {/* Вид торгов */}
        <Section title="Вид торгов">
          <CheckGroup
            items={auctionTypeList.length ? auctionTypeList : AUCTION_TYPES}
            selected={(filters.auction_type as string[]) || []}
            onToggle={v => toggleArr("auction_type", v)}
          />
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

        {/* Переуступка / Субаренда — детектируется по тексту извещения и договора */}
        <Section title="Переуступка / Субаренда">
          <div style={{ fontSize: 12, color: "var(--text-3)", marginBottom: 6 }}>
            Найдено упоминание в тексте извещения или проекта договора
          </div>
          <label className="checkbox-item">
            <input type="checkbox"
              checked={filters.assignment_allowed === true}
              onChange={e => set("assignment_allowed", e.target.checked ? true : undefined)} />
            Переуступка упоминается
          </label>
          <label className="checkbox-item">
            <input type="checkbox"
              checked={filters.sublease_allowed === true}
              onChange={e => set("sublease_allowed", e.target.checked ? true : undefined)} />
            Субаренда упоминается
          </label>
          <div style={{ fontSize: 11, color: "var(--text-3)", marginTop: 4, fontStyle: "italic" }}>
            Поиск по словам: субаренд, переуступ, уступк, цессия
          </div>
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

      </div>
    </aside>
  );
}
