"use client";
import { useEffect, useRef } from "react";

interface MapPoint {
  id: number;
  lat: number;
  lng: number;
  price?: number;
  area?: number;
  area_kn?: number;
  purpose?: string;
  rubric_tg?: number;
  pct?: number;
  cadastral_cost?: number;
  cadastral_number?: string;
  auction_form?: string;
  deal_type?: string;
  resale_type?: string;
  etp?: string;
  category_kn?: string;
  vri_kn?: string;
  category_tg?: string;
  vri_tg?: string;
  submission_end?: string;
  auction_end_date?: string;
  lot_url?: string;
  region_name?: string;
  notice_number?: string;
}

// Цвет и эмодзи по категории назначения
function getPurposeStyle(purpose?: string): { color: string; emoji: string } {
  switch (purpose) {
    case "izhs":         return { color: "#16a34a", emoji: "🏠" }; // насыщенный зелёный
    case "snt":          return { color: "#f59e0b", emoji: "🌿" }; // янтарный — отличается от ИЖС
    case "lpkh":         return { color: "#84cc16", emoji: "🌾" }; // лайм
    case "agricultural": return { color: "#a16207", emoji: "🌾" }; // коричнево-золотой
    case "commercial":   return { color: "#dc2626", emoji: "🏪" }; // красный
    case "industrial":   return { color: "#7c3aed", emoji: "🏭" }; // фиолетовый
    case "forest":       return { color: "#047857", emoji: "🌲" }; // тёмно-зелёный (лес)
    case "water":        return { color: "#0284c7", emoji: "💧" }; // синий
    case "special":      return { color: "#be185d", emoji: "⚠️" }; // малиновый
    default:             return { color: "#94a3b8", emoji: "📍" }; // светло-серый
  }
}

interface Props {
  points: MapPoint[];
  selectedId?: number;
  onLotClick?: (id: number) => void;
}

function loadCss(href: string, id: string) {
  if (typeof document === "undefined" || document.getElementById(id)) return;
  const l = document.createElement("link");
  l.id = id; l.rel = "stylesheet"; l.href = href;
  document.head.appendChild(l);
}

export default function MapView({ points, selectedId }: Props) {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<unknown>(null);
  const layerRef = useRef<unknown>(null);

  useEffect(() => {
    if (!mapRef.current) return;
    if ((mapRef.current as unknown as Record<string, unknown>)._leaflet_id) return;

    loadCss("https://unpkg.com/leaflet@1.9.4/dist/leaflet.css", "leaflet-css");

    import("leaflet").then((mod) => {
      const L = mod.default;

      if (!mapRef.current) return;
      if ((mapRef.current as unknown as Record<string, unknown>)._leaflet_id) return;

      const map = L.map(mapRef.current, {
        center: [61.5, 105.3],
        zoom: 4,
        zoomControl: true,
      });

      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '© <a href="https://openstreetmap.org">OpenStreetMap</a>',
        maxZoom: 19,
      }).addTo(map);

      const layer = L.layerGroup().addTo(map);
      mapInstanceRef.current = map;
      layerRef.current = { L, layer };
    });

    return () => {
      if (mapInstanceRef.current) {
        (mapInstanceRef.current as { remove: () => void }).remove();
        mapInstanceRef.current = null;
        layerRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    const ref = layerRef.current as { L: unknown; layer: unknown } | null;
    if (!ref) return;

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const L = ref.L as any;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const layer = ref.layer as any;

    layer.clearLayers();

    points.forEach((p) => {
      const isSelected = p.id === selectedId;
      const { color, emoji } = getPurposeStyle(p.purpose);
      const size = isSelected ? 22 : 16;
      const icon = L.divIcon({
        className: "",
        html: `<div style="width:${size}px;height:${size}px;background:${isSelected ? "#dc2626" : color};border:2px solid #fff;border-radius:50%;box-shadow:0 1px 4px rgba(0,0,0,.4);cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:${isSelected ? 12 : 9}px;line-height:1">${emoji}</div>`,
        iconSize: [size, size],
        iconAnchor: [size / 2, size / 2],
      });

      const fmt = (v?: number) => v ? (v >= 1_000_000 ? `${(v/1_000_000).toFixed(2)} млн ₽` : `${(v/1_000).toFixed(0)} тыс. ₽`) : "—";
      const fmtArea = (v?: number) => v ? (v >= 10_000 ? `${(v/10_000).toFixed(2)} га` : `${v.toLocaleString("ru")} кв.м`) : "—";
      const fmtDate = (s?: string) => s ? new Date(s).toLocaleDateString("ru", {day:"2-digit",month:"2-digit",year:"numeric"}) : "—";

      const DEAL: Record<string,string> = { ownership:"Продажа", lease:"Аренда", free_use:"Безвозмездное", operational:"Оперативное" };
      const FORM: Record<string,string> = { auction:"Электронный аукцион", tender:"Конкурс", public:"Публичное предложение", without:"Без торгов" };
      const RESALE: Record<string,string> = { yes:"Можно", with_notice:"Можно уведомив", with_approval:"Можно согласовав", no:"Нельзя" };

      // Числовой ID из НСПД — не показываем, только текстовые категории
      const cleanCat = (v?: string|null) => v && /^\d+$/.test(v.trim()) ? null : v;

      const row = (label: string, val?: string|null) =>
        val ? `<tr><td style="color:#94a3b8;padding:2px 8px 2px 0;font-size:11px;white-space:nowrap">${label}</td><td style="font-size:11px;padding:2px 0">${val}</td></tr>` : "";

      const pctColor = p.pct ? (p.pct < 50 ? "#16a34a" : p.pct < 100 ? "#64748b" : "#dc2626") : "#64748b";

      // Заголовок попапа: цена или площадь
      const header = p.price ? fmt(p.price) : (p.area ? fmtArea(p.area) : "Участок");

      L.marker([p.lat, p.lng], { icon }).bindPopup(`
        <div style="min-width:240px;max-width:300px;font-family:system-ui,sans-serif">
          <div style="font-weight:700;font-size:15px;margin-bottom:2px;color:#1e293b">${header}</div>
          ${p.region_name ? `<div style="font-size:11px;color:#64748b;margin-bottom:6px">${p.region_name}</div>` : ""}
          <table style="border-collapse:collapse;width:100%">
            ${row("Кадастровый №", p.cadastral_number)}
            ${row("Форма торгов", p.auction_form ? FORM[p.auction_form] || p.auction_form : null)}
            ${row("Вид сделки", p.deal_type ? DEAL[p.deal_type] || p.deal_type : null)}
            ${row("Категория земель", cleanCat(p.category_kn) || cleanCat(p.category_tg))}
            ${row("ВРИ", p.vri_kn || p.vri_tg)}
            ${row("Площадь", p.area_kn ? fmtArea(p.area_kn) : (p.area ? fmtArea(p.area) : null))}
            ${row("Кадастр. стоимость", p.cadastral_cost ? fmt(p.cadastral_cost) : null)}
            ${p.pct ? `<tr><td style="color:#94a3b8;padding:2px 8px 2px 0;font-size:11px">% НЦ/КС</td><td style="font-size:11px;padding:2px 0;font-weight:600;color:${pctColor}">${p.pct.toFixed(1)}%</td></tr>` : ""}
            ${row("Конец заявок", p.submission_end ? fmtDate(p.submission_end) : null)}
            ${row("Дата торгов", p.auction_end_date ? fmtDate(p.auction_end_date) : null)}
            ${row("Переуступка", p.resale_type ? RESALE[p.resale_type] : null)}
            ${p.etp && p.etp !== "отсутствует" ? row("ЭТП", p.etp) : ""}
          </table>
          <div style="margin-top:8px;display:flex;gap:6px">
            <a href="/lots/${p.id}" style="flex:1;padding:5px 8px;background:#2563eb;color:#fff;border-radius:6px;font-size:12px;text-align:center;text-decoration:none">Подробнее →</a>
            ${p.lot_url ? `<a href="${p.lot_url}" target="_blank" rel="noopener" style="flex:1;padding:5px 8px;background:#f1f5f9;color:#475569;border-radius:6px;font-size:12px;text-align:center;text-decoration:none">Оригинал ↗</a>` : ""}
          </div>
        </div>
      `, { maxWidth: 310 }).addTo(layer);
    });
  }, [points, selectedId]);

  return (
    <div style={{ position: "relative", width: "100%", height: "100%" }}>
      <div ref={mapRef} style={{ width: "100%", height: "100%" }} />
      {/* Легенда */}
      <div style={{
        position: "absolute", bottom: 28, right: 10, zIndex: 1000,
        background: "rgba(255,255,255,0.93)", borderRadius: 8,
        padding: "8px 12px", boxShadow: "0 1px 6px rgba(0,0,0,.2)",
        fontSize: 11, lineHeight: 1.8, pointerEvents: "none",
      }}>
        {[
          { emoji: "🏠", color: "#16a34a", label: "ИЖС" },
          { emoji: "🌿", color: "#f59e0b", label: "СНТ / Дача" },
          { emoji: "🌾", color: "#84cc16", label: "ЛПХ" },
          { emoji: "🌾", color: "#a16207", label: "Сельхоз" },
          { emoji: "🏪", color: "#dc2626", label: "Коммерческое" },
          { emoji: "🏭", color: "#7c3aed", label: "Промышленное" },
          { emoji: "🌲", color: "#047857", label: "Лесной фонд" },
          { emoji: "💧", color: "#0284c7", label: "Водный фонд" },
          { emoji: "📍", color: "#94a3b8", label: "Иное" },
        ].map(item => (
          <div key={item.label} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <div style={{ width: 14, height: 14, borderRadius: "50%", background: item.color, border: "2px solid #fff", boxShadow: "0 1px 3px rgba(0,0,0,.2)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 8, flexShrink: 0 }}>
              {item.emoji}
            </div>
            <span style={{ color: "#374151" }}>{item.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
