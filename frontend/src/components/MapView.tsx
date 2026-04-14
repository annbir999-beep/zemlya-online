"use client";
import { useEffect, useRef } from "react";

interface MapPoint {
  id: number;
  lat: number;
  lng: number;
  price?: number;
  area?: number;
  purpose?: string;
  rubric_tg?: number;
  pct?: number;
}

// Цвет и эмодзи по категории назначения
function getPurposeStyle(purpose?: string): { color: string; emoji: string } {
  switch (purpose) {
    case "izhs":         return { color: "#16a34a", emoji: "🏠" };
    case "snt":          return { color: "#65a30d", emoji: "🌿" };
    case "lpkh":         return { color: "#84cc16", emoji: "🌾" };
    case "agricultural": return { color: "#ca8a04", emoji: "🌾" };
    case "commercial":   return { color: "#dc2626", emoji: "🏪" };
    case "industrial":   return { color: "#7c3aed", emoji: "🏭" };
    case "forest":       return { color: "#15803d", emoji: "🌲" };
    case "water":        return { color: "#0284c7", emoji: "💧" };
    case "special":      return { color: "#9f1239", emoji: "⚠️" };
    default:             return { color: "#2563eb", emoji: "📍" };
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

      const priceStr = p.price
        ? p.price >= 1_000_000 ? `${(p.price / 1_000_000).toFixed(1)} млн ₽` : `${(p.price / 1_000).toFixed(0)} тыс. ₽`
        : "—";
      const areaStr = p.area
        ? p.area >= 10_000 ? `${(p.area / 10_000).toFixed(2)} га` : `${p.area.toLocaleString("ru")} кв.м`
        : "";
      const pctStr = p.pct ? `НЦ/КС: <b style="color:${p.pct < 50 ? "#16a34a" : "#64748b"}">${p.pct.toFixed(1)}%</b>` : "";

      L.marker([p.lat, p.lng], { icon }).bindPopup(`
        <div style="min-width:170px">
          <div style="font-weight:600;font-size:14px;margin-bottom:4px">${priceStr}</div>
          ${areaStr ? `<div style="font-size:12px;color:#64748b;margin-bottom:2px">${areaStr}</div>` : ""}
          ${pctStr ? `<div style="font-size:12px;margin-bottom:4px">${pctStr}</div>` : ""}
          <a href="/lots/${p.id}" style="display:block;margin-top:6px;padding:4px 10px;background:#2563eb;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:12px;width:100%;text-align:center;text-decoration:none;box-sizing:border-box">Подробнее →</a>
        </div>
      `).addTo(layer);
    });
  }, [points, selectedId]);

  return <div ref={mapRef} style={{ width: "100%", height: "100%" }} />;
}
