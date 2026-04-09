"use client";
import { useState, useCallback, useEffect } from "react";
import dynamic from "next/dynamic";
import FilterSidebar from "@/components/FilterSidebar";
import LotCard from "@/components/LotCard";
import { FiltersState, filtersToQueryString } from "@/lib/filters";
import type { LotListItem, LotsResponse } from "@/lib/api";

const MapView = dynamic(() => import("@/components/MapView"), { ssr: false });

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

const DEFAULT_FILTERS: FiltersState = { status: "active", sort_by: "auction_end_date", sort_order: "asc" };

export default function MapPage() {
  const [filters, setFilters] = useState<FiltersState>(DEFAULT_FILTERS);
  const [selectedLot, setSelectedLot] = useState<LotListItem | null>(null);
  const [sidebarLots, setSidebarLots] = useState<LotListItem[]>([]);
  const [mapPoints, setMapPoints] = useState<{ id: number; lat: number; lng: number; price?: number; area?: number; purpose?: string }[]>([]);
  const [compareIds, setCompareIds] = useState<number[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);

  // Загружаем лоты для каталога
  const loadLots = useCallback(async (f: FiltersState) => {
    setLoading(true);
    try {
      const qs = filtersToQueryString({ ...f, per_page: 30 } as FiltersState & { per_page: number });
      const res = await fetch(`${API}/api/lots?${qs}`);
      const data: LotsResponse = await res.json();
      setSidebarLots(data.items);
      setTotal(data.total);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  // Загружаем точки для карты
  const loadMapPoints = useCallback(async (f: FiltersState) => {
    try {
      const qs = filtersToQueryString(f);
      const res = await fetch(`${API}/api/lots/map?${qs}`);
      const data = await res.json();
      setMapPoints(data.points || []);
    } catch (e) {
      console.error(e);
    }
  }, []);

  useEffect(() => {
    loadLots(filters);
    loadMapPoints(filters);
  }, [filters, loadLots, loadMapPoints]);

  const handleFiltersChange = (f: FiltersState) => setFilters(f);
  const handleReset = () => setFilters(DEFAULT_FILTERS);

  const toggleCompare = (id: number) => {
    setCompareIds((prev) =>
      prev.includes(id)
        ? prev.filter((x) => x !== id)
        : prev.length < 5
        ? [...prev, id]
        : prev
    );
  };

  const handleMapLotClick = useCallback((id: number) => {
    const lot = sidebarLots.find((l) => l.id === id);
    if (lot) setSelectedLot(lot);
    else fetch(`${API}/api/lots/${id}`).then((r) => r.json()).then(setSelectedLot);
  }, [sidebarLots]);

  return (
    <>
      <FilterSidebar filters={filters} onChange={handleFiltersChange} onReset={handleReset} />

      {/* Карта */}
      <div className="map-container">
        <MapView points={mapPoints} selectedId={selectedLot?.id} onLotClick={handleMapLotClick} />

        {/* Панель выбранного лота поверх карты */}
        {selectedLot && (
          <div className="lot-detail">
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
              <span style={{ fontWeight: 600, fontSize: 15 }}>Выбранный участок</span>
              <button className="btn btn-ghost btn-sm" onClick={() => setSelectedLot(null)}>✕</button>
            </div>
            <LotCard
              lot={selectedLot}
              selected
              compareIds={compareIds}
              onSelect={() => {}}
              onToggleCompare={toggleCompare}
            />
          </div>
        )}
      </div>

      {/* Боковой каталог */}
      <aside className="catalog-panel">
        <div className="catalog-header">
          <span style={{ fontSize: 13, color: "var(--text-2)" }}>
            {loading ? "Загрузка..." : `${total.toLocaleString("ru")} участков`}
          </span>
        </div>
        <div className="catalog-scroll">
          {sidebarLots.map((lot) => (
            <LotCard
              key={lot.id}
              lot={lot}
              selected={selectedLot?.id === lot.id}
              compareIds={compareIds}
              onSelect={setSelectedLot}
              onToggleCompare={toggleCompare}
            />
          ))}
          {!loading && sidebarLots.length === 0 && (
            <div style={{ padding: 24, textAlign: "center", color: "var(--text-3)" }}>
              Ничего не найдено.<br />Попробуйте изменить фильтры.
            </div>
          )}
        </div>
      </aside>

      {/* Панель сравнения */}
      {compareIds.length > 0 && (
        <div className="compare-bar">
          <span style={{ fontSize: 13 }}>Сравниваю: {compareIds.length} участка</span>
          <a
            href={`/compare?ids=${compareIds.join(",")}`}
            className="btn btn-primary btn-sm"
          >
            Сравнить →
          </a>
          <button className="btn btn-ghost btn-sm" style={{ color: "#94a3b8" }} onClick={() => setCompareIds([])}>
            Очистить
          </button>
        </div>
      )}
    </>
  );
}
