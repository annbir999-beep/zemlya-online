import Cookies from "js-cookie";
import { api, UserProfile } from "./api";

export async function login(email: string, password: string): Promise<void> {
  const form = new URLSearchParams();
  form.append("username", email);
  form.append("password", password);

  const res = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL}/api/users/token`,
    { method: "POST", body: form }
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Неверный email или пароль");
  }
  const data = await res.json();
  // Cookie живёт 30 дней; JWT внутри истекает через 12ч и продлевается авто-refresh'ем в api.ts.
  Cookies.set("access_token", data.access_token, { expires: 30 });
  Cookies.set("refresh_token", data.refresh_token, { expires: 30 });
}

export async function register(email: string, password: string, name?: string): Promise<void> {
  // Захватываем UTM из URL — для аналитики откуда пришёл пользователь
  let utm_source: string | undefined;
  let utm_campaign: string | undefined;
  let referral_code: string | undefined;
  if (typeof window !== "undefined") {
    const params = new URLSearchParams(window.location.search);
    utm_source = params.get("utm_source") || undefined;
    utm_campaign = params.get("utm_campaign") || undefined;
    referral_code = params.get("ref") || undefined;
    if (!utm_source) utm_source = sessionStorage.getItem("utm_source") || undefined;
    if (!utm_campaign) utm_campaign = sessionStorage.getItem("utm_campaign") || undefined;
    if (!referral_code) referral_code = sessionStorage.getItem("ref") || undefined;
  }
  const res = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL}/api/users/register`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, name, utm_source, utm_campaign, referral_code }),
    }
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Ошибка регистрации");
  }
  const data = await res.json();
  // Cookie живёт 30 дней; JWT внутри истекает через 12ч и продлевается авто-refresh'ем в api.ts.
  Cookies.set("access_token", data.access_token, { expires: 30 });
  Cookies.set("refresh_token", data.refresh_token, { expires: 30 });
}

export function logout(): void {
  Cookies.remove("access_token");
  Cookies.remove("refresh_token");
  window.location.href = "/";
}

export function isAuthenticated(): boolean {
  return !!Cookies.get("access_token");
}

export async function getMe(): Promise<UserProfile | null> {
  if (!isAuthenticated()) return null;
  try {
    return await api.get<UserProfile>("/api/users/me");
  } catch {
    return null;
  }
}
