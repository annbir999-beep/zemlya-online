"use client";
import { useEffect } from "react";

/**
 * Один раз при заходе пользователя на сайт сохраняет utm_source/utm_campaign
 * в sessionStorage. При регистрации эти значения подмешиваются в payload —
 * это позволяет атрибутировать конверсию даже если пользователь сначала
 * почитал блог/тарифы, а потом зарегистрировался.
 */
export default function UtmCapture() {
  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const src = params.get("utm_source");
    const camp = params.get("utm_campaign");
    if (src && !sessionStorage.getItem("utm_source")) {
      sessionStorage.setItem("utm_source", src);
    }
    if (camp && !sessionStorage.getItem("utm_campaign")) {
      sessionStorage.setItem("utm_campaign", camp);
    }
  }, []);
  return null;
}
