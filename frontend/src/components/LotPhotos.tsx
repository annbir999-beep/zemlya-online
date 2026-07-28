"use client";
import { useState } from "react";

/**
 * Фото участка из извещения torgi.gov.
 *
 * Картинки есть почти у каждого лота: у части это фото с земли, у большинства —
 * спутниковый снимок с обведённой границей из кадастра. Отдаёт их наш бэкенд
 * (/api/lots/{id}/photo/{idx}) — напрямую на torgi.gov ходить нельзя, их файл-стор
 * доступен не отовсюду.
 *
 * Битые индексы прячем: у лота может быть заявлено 3 картинки, а по одной из них
 * файл-стор отдаст 404 — пустая рамка выглядит хуже, чем её отсутствие.
 */
export default function LotPhotos({ lotId, count }: { lotId: number; count: number }) {
  const [active, setActive] = useState(0);
  const [broken, setBroken] = useState<Set<number>>(new Set());
  const [zoom, setZoom] = useState(false);

  const alive = Array.from({ length: count }, (_, i) => i).filter((i) => !broken.has(i));
  if (alive.length === 0) return null;

  const current = alive.includes(active) ? active : alive[0];
  const src = (i: number) => `/api/lots/${lotId}/photo/${i}`;
  const markBroken = (i: number) =>
    setBroken((prev) => new Set(prev).add(i));

  return (
    <div style={{ marginBottom: 24 }}>
      {/* Ширина ограничена: исходники из извещения мелкие (от 480 px по ширине),
          на всю колонку они растягиваются в мыло. */}
      <div
        onClick={() => setZoom(true)}
        style={{
          position: "relative", width: "100%", maxWidth: 640, aspectRatio: "16 / 10",
          background: "var(--surface-2, #eef3f2)", border: "1px solid var(--border)",
          borderRadius: 12, overflow: "hidden", cursor: "zoom-in",
        }}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={src(current)}
          alt={`Фото участка ${current + 1}`}
          loading="lazy"
          onError={() => markBroken(current)}
          // contain, а не cover: у большинства лотов это спутниковый снимок с
          // обведённой границей — обрезка может срезать сам контур участка.
          style={{ width: "100%", height: "100%", objectFit: "contain", display: "block" }}
        />
        <div style={{
          position: "absolute", left: 10, bottom: 10, padding: "4px 10px",
          background: "rgba(17,34,32,0.72)", color: "#fff", fontSize: 12,
          borderRadius: 999, backdropFilter: "blur(4px)",
        }}>
          Фото из извещения · {alive.indexOf(current) + 1} из {alive.length}
        </div>
      </div>

      {alive.length > 1 && (
        <div style={{ display: "flex", gap: 8, marginTop: 8, overflowX: "auto", paddingBottom: 4 }}>
          {alive.map((i) => (
            <button
              key={i}
              onClick={() => setActive(i)}
              aria-label={`Фото ${i + 1}`}
              style={{
                flex: "0 0 auto", width: 84, height: 60, padding: 0, borderRadius: 8,
                overflow: "hidden", cursor: "pointer", background: "none",
                border: i === current ? "2px solid var(--primary)" : "1px solid var(--border)",
              }}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={src(i)} alt="" loading="lazy" onError={() => markBroken(i)}
                style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
              />
            </button>
          ))}
        </div>
      )}

      {zoom && (
        <div
          onClick={() => setZoom(false)}
          style={{
            position: "fixed", inset: 0, zIndex: 1000, cursor: "zoom-out",
            background: "rgba(0,0,0,0.86)", display: "flex",
            alignItems: "center", justifyContent: "center", padding: 24,
          }}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={src(current)}
            alt={`Фото участка ${current + 1}`}
            style={{ maxWidth: "100%", maxHeight: "100%", objectFit: "contain" }}
          />
        </div>
      )}
    </div>
  );
}
