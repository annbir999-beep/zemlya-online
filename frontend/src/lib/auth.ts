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
  Cookies.set("access_token", data.access_token, { expires: 1 });
  Cookies.set("refresh_token", data.refresh_token, { expires: 30 });
}

export async function register(email: string, password: string, name?: string): Promise<void> {
  const res = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL}/api/users/register`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, name }),
    }
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Ошибка регистрации");
  }
  const data = await res.json();
  Cookies.set("access_token", data.access_token, { expires: 1 });
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
