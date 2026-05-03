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
  auction_start_date?: string;
  auction_end_date?: string;
  lot_url?: string;
  region_name?: string;
  notice_number?: string;
  score?: number;
  discount_to_market_pct?: number;
  score_badges?: string[];
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

interface HeatmapPoint {
  code: string;
  name: string;
  lat: number;
  lng: number;
  count: number;
  avg_discount_pct?: number | null;
  avg_score?: number | null;
  avg_price_per_sqm?: number | null;
}

interface Props {
  points: MapPoint[];
  selectedId?: number;
  onLotClick?: (id: number) => void;
  heatmap?: HeatmapPoint[];
  mode?: "points" | "heatmap";
}

function heatColor(discountPct?: number | null): string {
  if (discountPct == null) return "#94a3b8";
  if (discountPct >= 50) return "#dc2626";
  if (discountPct >= 25) return "#ea580c";
  if (discountPct >= 10) return "#ca8a04";
  return "#16a34a";
}

function loadCss(href: string, id: string) {
  if (typeof document === "undefined" || document.getElementById(id)) return;
  const l = document.createElement("link");
  l.id = id; l.rel = "stylesheet"; l.href = href;
  document.head.appendChild(l);
}

export default function MapView({ points, selectedId, heatmap, mode = "points" }: Props) {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<unknown>(null);
  const layerRef = useRef<unknown>(null);
  const heatLayerRef = useRef<unknown>(null);

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
      const heatLayer = L.layerGroup();
      mapInstanceRef.current = map;
      layerRef.current = { L, layer };
      heatLayerRef.current = { L, layer: heatLayer };
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

      // Скор-кружок и бейджи
      const scoreColor = p.score == null ? "#94a3b8" : (p.score >= 80 ? "#dc2626" : p.score >= 60 ? "#ea580c" : p.score >= 40 ? "#ca8a04" : p.score >= 20 ? "#65a30d" : "#94a3b8");
      const BADGE_LBL: Record<string, string> = { hot:"🔥", diamond:"💎", split:"📐", vri:"🌾", build:"🏗", commerce:"🏪", urgent:"⚡", rent:"🔁" };
      const scoreBlock = p.score != null ? `<div style="display:inline-flex;align-items:center;justify-content:center;width:32px;height:32px;border-radius:50%;background:${scoreColor}22;color:${scoreColor};font-weight:800;font-size:13px;margin-right:8px">${p.score}</div>` : "";
      const discountTag = p.discount_to_market_pct && p.discount_to_market_pct >= 5 ? `<span style="background:#dcfce7;color:#15803d;font-size:11px;font-weight:700;padding:2px 6px;border-radius:4px;margin-left:6px">−${Math.round(p.discount_to_market_pct)}% к рынку</span>` : "";
      const badgesBlock = p.score_badges && p.score_badges.length ? `<div style="margin-bottom:6px;display:flex;gap:4px;flex-wrap:wrap">${p.score_badges.slice(0,4).map(b => BADGE_LBL[b] ? `<span style="background:#f1f5f9;font-size:14px;padding:1px 5px;border-radius:4px" title="${b}">${BADGE_LBL[b]}</span>` : "").join("")}</div>` : "";

      L.marker([p.lat, p.lng], { icon }).bindPopup(`
        <div style="min-width:240px;max-width:300px;font-family:system-ui,sans-serif">
          <div style="display:flex;align-items:center;margin-bottom:2px">
            ${scoreBlock}
            <div style="flex:1;min-width:0">
              <div style="font-weight:700;font-size:15px;color:#1e293b">${header}${discountTag}</div>
              ${p.region_name ? `<div style="font-size:11px;color:#64748b">${p.region_name}</div>` : ""}
            </div>
          </div>
          ${badgesBlock}
          <table style="border-collapse:collapse;width:100%">
            ${row("Кадастровый №", p.cadastral_number)}
            ${row("Форма торгов", p.auction_form ? FORM[p.auction_form] || p.auction_form : null)}
            ${row("Вид сделки", p.deal_type ? DEAL[p.deal_type] || p.deal_type : null)}
            ${row("Категория земель", cleanCat(p.category_kn) || cleanCat(p.category_tg))}
            ${row("ВРИ", p.vri_kn || p.vri_tg)}
            ${row("Площадь", p.area_kn ? fmtArea(p.area_kn) : (p.area ? fmtArea(p.area) : null))}
            ${row("Кадастр. стоимость", p.cadastral_cost ? fmt(p.cadastral_cost) : null)}
            ${p.pct ? `<tr><td style="color:#94a3b8;padding:2px 8px 2px 0;font-size:11px">% НЦ/КС</td><td style="font-size:11px;padding:2px 0;font-weight:600;color:${pctColor}">${p.pct.toFixed(1)}%</td></tr>` : ""}
            ${row("Срок подачи заявок", p.submission_end ? fmtDate(p.submission_end) : null)}
            ${row("Дата проведения торгов", p.auction_start_date ? fmtDate(p.auction_start_date) : null)}
            ${row("Переуступка", p.resale_type ? RESALE[p.resale_type] : null)}
            ${p.etp && p.etp !== "отсутствует" ? row("ЭТП", p.etp) : ""}
          </table>
          <div style="margin-top:8px;display:flex;gap:6px">
            <a href="/lots/${p.id}" target="_blank" rel="noopener" style="flex:1;padding:5px 8px;background:#2563eb;color:#fff;border-radius:6px;font-size:12px;text-align:center;text-decoration:none">Подробнее →</a>
            ${p.lot_url ? `<a href="${p.lot_url}" target="_blank" rel="noopener" style="flex:1;padding:5px 8px;background:#f1f5f9;color:#475569;border-radius:6px;font-size:12px;text-align:center;text-decoration:none">Оригинал ↗</a>` : ""}
          </div>
        </div>
      `, { maxWidth: 310 }).addTo(layer);
    });
  }, [points, selectedId]);

  // Heatmap layer — отрисовка кругов по регионам
  useEffect(() => {
    const ref = heatLayerRef.current as { L: unknown; layer: unknown } | null;
    const map = mapInstanceRef.current as { addLayer: (l: unknown) => void; removeLayer: (l: unknown) => void } | null;
    const pointsRef = layerRef.current as { layer: unknown } | null;
    if (!ref || !map) return;

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const L = ref.L as any;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const heatLayer = ref.layer as any;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const pointsLayer = pointsRef?.layer as any;

    heatLayer.clearLayers();

    if (mode === "heatmap" && heatmap) {
      // Скрываем слой точек, показываем heatmap
      if (pointsLayer) (map as { removeLayer: (l: unknown) => void }).removeLayer(pointsLayer);
      (map as { addLayer: (l: unknown) => void }).addLayer(heatLayer);

      const maxCount = Math.max(...heatmap.map((h) => h.count), 1);
      heatmap.forEach((h) => {
        const radius = Math.max(8, Math.sqrt(h.count / maxCount) * 60);  // 8..60 px
        const color = heatColor(h.avg_discount_pct);
        const fmtNum = (v?: number | null) => v == null ? "—" : Math.round(v).toLocaleString("ru");
        L.circleMarker([h.lat, h.lng], {
          radius,
          color: "#fff",
          weight: 1.5,
          fillColor: color,
          fillOpacity: 0.55,
        })
          .bindTooltip(`<b>${h.name || h.code}</b><br>${h.count} лотов`, { direction: "top", offset: [0, -radius] })
          .bindPopup(`
            <div style="min-width:200px;font-family:system-ui,sans-serif">
              <div style="font-weight:700;font-size:14px;margin-bottom:6px">${h.name || h.code}</div>
              <table style="border-collapse:collapse;width:100%;font-size:12px">
                <tr><td style="color:#64748b;padding:2px 8px 2px 0">Активных лотов</td><td style="font-weight:600">${h.count}</td></tr>
                <tr><td style="color:#64748b;padding:2px 8px 2px 0">Средний дисконт</td><td style="font-weight:600;color:${color}">${h.avg_discount_pct != null ? h.avg_discount_pct.toFixed(1) + "%" : "—"}</td></tr>
                <tr><td style="color:#64748b;padding:2px 8px 2px 0">Средний score</td><td>${h.avg_score != null ? Math.round(h.avg_score) : "—"}</td></tr>
                <tr><td style="color:#64748b;padding:2px 8px 2px 0">Цена за м²</td><td>${fmtNum(h.avg_price_per_sqm)} ₽</td></tr>
              </table>
              <a href="/lots?region=${h.code}" style="display:block;margin-top:8px;padding:5px 8px;background:#2563eb;color:#fff;border-radius:6px;font-size:12px;text-align:center;text-decoration:none">Открыть в каталоге →</a>
            </div>
          `, { maxWidth: 260 })
          .addTo(heatLayer);
      });
    } else {
      // Показываем точки, скрываем heatmap
      (map as { removeLayer: (l: unknown) => void }).removeLayer(heatLayer);
      if (pointsLayer) (map as { addLayer: (l: unknown) => void }).addLayer(pointsLayer);
    }
  }, [heatmap, mode]);

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
        {(mode === "heatmap" ? [
          { emoji: "●", color: "#dc2626", label: "Дисконт ≥50%" },
          { emoji: "●", color: "#ea580c", label: "Дисконт 25-50%" },
          { emoji: "●", color: "#ca8a04", label: "Дисконт 10-25%" },
          { emoji: "●", color: "#16a34a", label: "Дисконт <10%" },
          { emoji: "●", color: "#94a3b8", label: "Нет данных" },
        ] : [
          { emoji: "🏠", color: "#16a34a", label: "ИЖС" },
          { emoji: "🌿", color: "#f59e0b", label: "СНТ / Дача" },
          { emoji: "🌾", color: "#84cc16", label: "ЛПХ" },
          { emoji: "🌾", color: "#a16207", label: "Сельхоз" },
          { emoji: "🏪", color: "#dc2626", label: "Коммерческое" },
          { emoji: "🏭", color: "#7c3aed", label: "Промышленное" },
          { emoji: "🌲", color: "#047857", label: "Лесной фонд" },
          { emoji: "💧", color: "#0284c7", label: "Водный фонд" },
          { emoji: "📍", color: "#94a3b8", label: "Иное" },
        ]).map(item => (
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
