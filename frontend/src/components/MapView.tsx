"use client";
import { useEffect, useRef } from "react";

interface MapPoint {
  id: number;
  lat: number;
  lng: number;
  price?: number;
  area?: number;
}

interface Props {
  points: MapPoint[];
  selectedId?: number;
  onLotClick: (id: number) => void;
}

function loadCss(href: string, id: string) {
  if (typeof document === "undefined" || document.getElementById(id)) return;
  const l = document.createElement("link");
  l.id = id; l.rel = "stylesheet"; l.href = href;
  document.head.appendChild(l);
}

export default function MapView({ points, selectedId, onLotClick }: Props) {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<unknown>(null);
  const layerRef = useRef<unknown>(null);

  useEffect(() => {
    if (!mapRef.current) return;
    if ((mapRef.current as Record<string, unknown>)._leaflet_id) return;

    loadCss("https://unpkg.com/leaflet@1.9.4/dist/leaflet.css", "leaflet-css");

    import("leaflet").then((mod) => {
      const L = mod.default;

      if (!mapRef.current) return;
      if ((mapRef.current as Record<string, unknown>)._leaflet_id) return;

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
      const icon = L.divIcon({
        className: "",
        html: `<div style="width:${isSelected ? 14 : 10}px;height:${isSelected ? 14 : 10}px;background:${isSelected ? "#dc2626" : "#2563eb"};border:2px solid #fff;border-radius:50%;box-shadow:0 1px 3px rgba(0,0,0,.3);cursor:pointer"></div>`,
        iconSize: [isSelected ? 14 : 10, isSelected ? 14 : 10],
        iconAnchor: [isSelected ? 7 : 5, isSelected ? 7 : 5],
      });

      const priceStr = p.price
        ? p.price >= 1_000_000 ? `${(p.price / 1_000_000).toFixed(1)} млн ₽` : `${(p.price / 1_000).toFixed(0)} тыс. ₽`
        : "—";
      const areaStr = p.area
        ? p.area >= 10_000 ? `${(p.area / 10_000).toFixed(2)} га` : `${p.area.toLocaleString("ru")} кв.м`
        : "";

      L.marker([p.lat, p.lng], { icon }).bindPopup(`
        <div style="min-width:160px">
          <div style="font-weight:600;font-size:14px;margin-bottom:4px">${priceStr}</div>
          ${areaStr ? `<div style="font-size:12px;color:#64748b">${areaStr}</div>` : ""}
          <button onclick="window.__onLotClick(${p.id})" style="margin-top:8px;padding:4px 10px;background:#2563eb;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:12px;width:100%">Подробнее</button>
        </div>
      `).addTo(layer);
    });

    (window as Record<string, unknown>).__onLotClick = onLotClick;
  }, [points, selectedId, onLotClick]);

  return <div ref={mapRef} style={{ width: "100%", height: "100%" }} />;
}
