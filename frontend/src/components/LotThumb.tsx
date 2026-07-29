"use client";
import { useState } from "react";

/**
 * Превью участка в карточке каталога.
 *
 * Картинка своя — из извещения torgi.gov, отдаётся нашим эндпоинтом в ширине
 * 320 px (около 16 КБ). Просить полный размер здесь нельзя: на странице два
 * десятка карточек, и оригиналы из извещений бывают по 5-6 МБ.
 *
 * Пока не загрузилась — держим место фоном, иначе карточки прыгают при
 * дозагрузке и по списку невозможно попасть мышью.
 */
export default function LotThumb({ lotId, size = 64 }: { lotId: number; size?: number }) {
  const [broken, setBroken] = useState(false);
  if (broken) return null;

  return (
    <div
      style={{
        flex: `0 0 ${size}px`, width: size, height: size, borderRadius: 8,
        overflow: "hidden", background: "var(--surface-2, #eef3f2)",
        border: "1px solid var(--border)",
      }}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        // cached=1 — каталог берёт только прогретое и никогда не заказывает
        // закачку: двадцать промахов на страницу = двадцать оригиналов по
        // 5-6 МБ разом, а torgi.gov на такую пачку отвечает 503.
        src={`/api/lots/${lotId}/photo/0?w=320&cached=1`}
        alt=""
        loading="lazy"
        onError={() => setBroken(true)}
        style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
      />
    </div>
  );
}
