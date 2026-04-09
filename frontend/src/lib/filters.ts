// Все доступные фильтры и их метаданные

export const LAND_PURPOSES = [
  { value: "izhs", label: "ИЖС" },
  { value: "snt", label: "СНТ / Дача" },
  { value: "lpkh", label: "ЛПХ" },
  { value: "agricultural", label: "Сельскохозяйственное" },
  { value: "commercial", label: "Коммерческое" },
  { value: "industrial", label: "Промышленное" },
  { value: "forest", label: "Лесной фонд" },
  { value: "water", label: "Водный фонд" },
  { value: "special", label: "Спец. назначения" },
  { value: "other", label: "Иное" },
];

export const AUCTION_TYPES = [
  { value: "sale", label: "Продажа" },
  { value: "rent", label: "Аренда" },
  { value: "priv", label: "Приватизация" },
];

export const LOT_STATUSES = [
  { value: "active", label: "Активные торги" },
  { value: "upcoming", label: "Скоро" },
  { value: "completed", label: "Завершённые" },
  { value: "cancelled", label: "Отменённые" },
];

export const SOURCES = [
  { value: "torgi_gov", label: "torgi.gov" },
  { value: "avito", label: "Авито" },
  { value: "cian", label: "ЦИАН" },
];

export const SORT_OPTIONS = [
  { value: "auction_end_date:asc", label: "По дате торгов (ближайшие)" },
  { value: "price:asc", label: "Цена: по возрастанию" },
  { value: "price:desc", label: "Цена: по убыванию" },
  { value: "area:asc", label: "Площадь: по возрастанию" },
  { value: "area:desc", label: "Площадь: по убыванию" },
  { value: "published_at:desc", label: "Новые сначала" },
];

// Субъекты РФ (код -> название)
export const REGIONS: Record<string, string> = {
  "01": "Адыгея", "02": "Башкортостан", "03": "Бурятия", "04": "Алтай",
  "05": "Дагестан", "06": "Ингушетия", "07": "Кабардино-Балкария",
  "08": "Калмыкия", "09": "Карачаево-Черкесия", "10": "Карелия",
  "11": "Коми", "12": "Марий Эл", "13": "Мордовия", "14": "Саха (Якутия)",
  "15": "Северная Осетия", "16": "Татарстан", "17": "Тыва", "18": "Удмуртия",
  "19": "Хакасия", "20": "Чечня", "21": "Чувашия",
  "22": "Алтайский край", "23": "Краснодарский край", "24": "Красноярский край",
  "25": "Приморский край", "26": "Ставропольский край", "27": "Хабаровский край",
  "28": "Амурская", "29": "Архангельская", "30": "Астраханская",
  "31": "Белгородская", "32": "Брянская", "33": "Владимирская",
  "34": "Волгоградская", "35": "Вологодская", "36": "Воронежская",
  "37": "Ивановская", "38": "Иркутская", "39": "Калининградская",
  "40": "Калужская", "41": "Камчатский край", "42": "Кемеровская",
  "43": "Кировская", "44": "Костромская", "45": "Курганская",
  "46": "Курская", "47": "Ленинградская", "48": "Липецкая",
  "49": "Магаданская", "50": "Московская", "51": "Мурманская",
  "52": "Нижегородская", "53": "Новгородская", "54": "Новосибирская",
  "55": "Омская", "56": "Оренбургская", "57": "Орловская",
  "58": "Пензенская", "59": "Пермский край", "60": "Псковская",
  "61": "Ростовская", "62": "Рязанская", "63": "Самарская",
  "64": "Саратовская", "65": "Сахалинская", "66": "Свердловская",
  "67": "Смоленская", "68": "Тамбовская", "69": "Тверская",
  "70": "Томская", "71": "Тульская", "72": "Тюменская",
  "73": "Ульяновская", "74": "Челябинская", "75": "Забайкальский край",
  "76": "Ярославская", "77": "Москва", "78": "Санкт-Петербург",
  "79": "Еврейская АО", "83": "Ненецкий АО", "86": "Ханты-Мансийский АО",
  "87": "Чукотский АО", "89": "Ямало-Ненецкий АО",
};

export interface FiltersState {
  status?: string;
  region?: string[];
  // Цена
  price_min?: number;
  price_max?: number;
  // Кадастровая стоимость
  cadastral_cost_min?: number;
  cadastral_cost_max?: number;
  // % НЦ/КС
  pct_cadastral_min?: number;
  pct_cadastral_max?: number;
  // Задаток
  deposit_min?: number;
  deposit_max?: number;
  deposit_pct_min?: number;
  deposit_pct_max?: number;
  // Площадь [TG]
  area_min?: number;
  area_max?: number;
  // Площадь [КН]
  area_kn_min?: number;
  area_kn_max?: number;
  area_discrepancy?: string[];
  // Назначение
  purpose?: string[];
  rubric_tg?: number[];
  rubric_kn?: number[];
  // Торги
  auction_type?: string[];
  auction_form?: string[];
  deal_type?: string[];
  etp?: string[];
  resale_type?: string[];
  // Источник
  source?: string[];
  // Поиск
  cadastral?: string;
  notice_number?: string;
  // Даты заявок
  submission_start_from?: string;
  submission_start_to?: string;
  submission_end_from?: string;
  submission_end_to?: string;
  // Сортировка и пагинация
  sort_by?: string;
  sort_order?: string;
  page?: number;
}

export function filtersToQueryString(f: FiltersState & { per_page?: number }): string {
  const params = new URLSearchParams();
  if (f.status) params.set("status", f.status);
  if (f.region?.length) f.region.forEach((r) => params.append("region", r));
  // Цена
  if (f.price_min != null) params.set("price_min", String(f.price_min));
  if (f.price_max != null) params.set("price_max", String(f.price_max));
  // Кадастровая стоимость
  if (f.cadastral_cost_min != null) params.set("cadastral_cost_min", String(f.cadastral_cost_min));
  if (f.cadastral_cost_max != null) params.set("cadastral_cost_max", String(f.cadastral_cost_max));
  // % НЦ/КС
  if (f.pct_cadastral_min != null) params.set("pct_cadastral_min", String(f.pct_cadastral_min));
  if (f.pct_cadastral_max != null) params.set("pct_cadastral_max", String(f.pct_cadastral_max));
  // Задаток
  if (f.deposit_min != null) params.set("deposit_min", String(f.deposit_min));
  if (f.deposit_max != null) params.set("deposit_max", String(f.deposit_max));
  if (f.deposit_pct_min != null) params.set("deposit_pct_min", String(f.deposit_pct_min));
  if (f.deposit_pct_max != null) params.set("deposit_pct_max", String(f.deposit_pct_max));
  // Площадь
  if (f.area_min != null) params.set("area_min", String(f.area_min));
  if (f.area_max != null) params.set("area_max", String(f.area_max));
  if (f.area_kn_min != null) params.set("area_kn_min", String(f.area_kn_min));
  if (f.area_kn_max != null) params.set("area_kn_max", String(f.area_kn_max));
  if (f.area_discrepancy?.length) f.area_discrepancy.forEach(v => params.append("area_discrepancy", v));
  // Назначение
  if (f.purpose?.length) f.purpose.forEach((p) => params.append("purpose", p));
  if (f.rubric_tg?.length) f.rubric_tg.forEach(r => params.append("rubric_tg", String(r)));
  if (f.rubric_kn?.length) f.rubric_kn.forEach(r => params.append("rubric_kn", String(r)));
  // Торги
  if (f.auction_type?.length) f.auction_type.forEach((t) => params.append("auction_type", t));
  if (f.auction_form?.length) f.auction_form.forEach((t) => params.append("auction_form", t));
  if (f.deal_type?.length) f.deal_type.forEach((t) => params.append("deal_type", t));
  if (f.etp?.length) f.etp.forEach(e => params.append("etp", e));
  if (f.resale_type?.length) f.resale_type.forEach(r => params.append("resale_type", r));
  // Источник и поиск
  if (f.source?.length) f.source.forEach((s) => params.append("source", s));
  if (f.cadastral) params.set("cadastral", f.cadastral);
  if (f.notice_number) params.set("notice_number", f.notice_number);
  // Даты заявок
  if (f.submission_start_from) params.set("submission_start_from", f.submission_start_from);
  if (f.submission_start_to) params.set("submission_start_to", f.submission_start_to);
  if (f.submission_end_from) params.set("submission_end_from", f.submission_end_from);
  if (f.submission_end_to) params.set("submission_end_to", f.submission_end_to);
  // Сортировка и пагинация
  if (f.sort_by) params.set("sort_by", f.sort_by);
  if (f.sort_order) params.set("sort_order", f.sort_order);
  if (f.page) params.set("page", String(f.page));
  if (f.per_page) params.set("per_page", String(f.per_page));
  return params.toString();
}
