import Cookies from "js-cookie";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

// Обмен refresh-токена на свежую пару. true — успех, токены обновлены.
async function tryRefresh(): Promise<boolean> {
  const rt = Cookies.get("refresh_token");
  if (!rt) return false;
  try {
    const res = await fetch(
      `${API_URL}/api/users/refresh?refresh_token=${encodeURIComponent(rt)}`,
      { method: "POST" },
    );
    if (!res.ok) return false;
    const data = await res.json();
    // Cookie живёт 30 дней; JWT внутри истекает через 12ч и обновляется этим же flow.
    Cookies.set("access_token", data.access_token, { expires: 30 });
    Cookies.set("refresh_token", data.refresh_token, { expires: 30 });
    return true;
  } catch {
    return false;
  }
}

async function request<T>(path: string, options: RequestInit = {}, _retried = false): Promise<T> {
  const token = Cookies.get("access_token");
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });

  if (res.status === 401) {
    // Истёк access-токен — пробуем обновить через refresh и повторить запрос один раз.
    if (!_retried && await tryRefresh()) {
      return request<T>(path, options, true);
    }
    Cookies.remove("access_token");
    Cookies.remove("refresh_token");
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      window.location.href = "/login";
    }
    throw new Error("Сессия истекла, войдите снова");
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Ошибка запроса");
  }

  // 204 No Content / пустое тело — нельзя звать .json(), кинет SyntaxError.
  // Возвращаем undefined как T — вызвавший код всё равно ничего не ожидает (DELETE и т.п.).
  if (res.status === 204 || res.headers.get("content-length") === "0") {
    return undefined as T;
  }
  return res.json();
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};

// Типы
export interface LotListItem {
  id: number;
  external_id: string;
  title: string;
  cadastral_number?: string;
  start_price?: number;
  area_sqm?: number;
  area_ha?: number;
  land_purpose?: string;
  auction_type?: string;
  status: string;
  region_code?: string;
  region_name?: string;
  address?: string;
  auction_end_date?: string;
  submission_start?: string;
  submission_end?: string;
  cadastral_cost?: number;
  pct_price_to_cadastral?: number;
  vri_tg?: string;
  lat?: number;
  lng?: number;
  source: string;
  lot_url?: string;
  score?: number;
  market_price_sqm?: number;
  discount_to_market_pct?: number;
  score_badges?: string[];
  nearest_city_name?: string;
  nearest_city_distance_km?: number;
  nearest_city_population?: number;
  communications?: {
    electricity?: boolean;
    gas?: boolean;
    water?: boolean;
    sewage?: boolean;
    road?: "asphalt" | "gravel" | "none";
    internet?: boolean;
  };
  tor_zone?: TorZone | null;
}

export interface ContractTermsData {
  assignment?: "forbidden" | "with_notice" | "with_consent" | "allowed";
  sublease?: "forbidden" | "with_consent" | "allowed";
  lease_term_years?: number;
  penalty_pct?: number;
  development_deadline_years?: number;
  has_strict_termination?: boolean;
}

export interface LotDetail extends LotListItem {
  description?: string;
  deposit?: number;
  deposit_pct?: number;
  final_price?: number;
  price_per_sqm?: number;
  organizer_name?: string;
  submission_deadline?: string;
  submission_start?: string;
  submission_end?: string;
  auction_start_date?: string;
  notice_number?: string;
  cadastral_cost?: number;
  pct_price_to_cadastral?: number;
  area_sqm_kn?: number;
  area_discrepancy?: string;
  land_purpose_raw?: string;
  category_tg?: string;
  vri_tg?: string;
  rubric_tg?: number;
  category_kn?: string;
  vri_kn?: string;
  rubric_kn?: number;
  auction_form?: string;
  deal_type?: string;
  etp?: string;
  resale_type?: string;
  sublease_allowed?: boolean;
  assignment_allowed?: boolean;
  region_code?: string;
  published_at?: string;
  rosreestr_data?: Record<string, unknown>;
  ai_assessment?: AiAssessment;
  raw_data?: Record<string, unknown>;
  full_description?: string;
  technical_conditions?: string;
  contract_terms?: ContractTermsData;
}

export interface AiAssessment {
  score: number;
  price_estimate: { min: number; max: number; comment: string };
  pros: string[];
  cons: string[];
  risks: string[];
  summary: string;
  recommended_use: string;
  assessed_at: string;
}

export interface LotsResponse {
  items: LotListItem[];
  total: number;
  page: number;
  pages: number;
}

export interface UserProfile {
  id: number;
  email: string;
  name?: string;
  phone?: string;
  telegram_id?: string;
  subscription_plan: string;
  subscription_expires_at?: string;
  saved_filters_limit: number;
  notification_email: boolean;
  notification_telegram: boolean;
  is_verified: boolean;
  free_audits_left?: number;
  is_admin?: boolean;
}

export interface TorZone {
  type: "dv" | "monotown" | "sez";
  label: string;
  description: string;
}

export interface Alert {
  id: number;
  name: string;
  is_active: boolean;
  channel: string;
  filters: Record<string, unknown>;
  last_triggered_at?: string;
  created_at: string;
}
