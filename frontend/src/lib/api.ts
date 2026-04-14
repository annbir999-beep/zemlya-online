import Cookies from "js-cookie";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = Cookies.get("access_token");
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });

  if (res.status === 401) {
    Cookies.remove("access_token");
    window.location.href = "/login";
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Ошибка запроса");
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
