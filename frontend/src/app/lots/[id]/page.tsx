"use client";
import { useEffect, useState, use, useRef } from "react";
import { useRouter } from "next/navigation";
import { api, LotDetail, AiAssessment } from "@/lib/api";
import { getMe } from "@/lib/auth";
import type { UserProfile } from "@/lib/api";
import { RegionInfo, RegionData } from "@/components/RegionInfo";
import { ScoreCircle, ScoreBadges, DiscountTag } from "@/components/ScoreBadge";
import { LocationCard, CommsCard, SimilarHistoryCard } from "@/components/LocationComms";
import { ContractTerms, FullDescription } from "@/components/ContractTerms";
import NearbyFeaturesCard, { type NearbyFeatures } from "@/components/NearbyFeatures";
import OrganizerContactsCard, { type OrganizerContacts } from "@/components/OrganizerContacts";
import RoiCalculator from "@/components/RoiCalculator";
import LockedBlock from "@/components/LockedBlock";
import { planRank, RANK_PRO, RANK_INVESTOR } from "@/lib/plan";
import { compare } from "@/lib/compare";
import { useCompareIds } from "@/lib/useCompare";

function MiniMap({ lat, lng, title }: { lat: number; lng: number; title?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    if ((ref.current as unknown as Record<string,unknown>)._leaflet_id) return;
    const link = document.createElement("link");
    link.rel = "stylesheet"; link.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
    if (!document.getElementById("leaflet-css")) { link.id = "leaflet-css"; document.head.appendChild(link); }
    import("leaflet").then(mod => {
      const L = mod.default;
      if (!ref.current || (ref.current as unknown as Record<string,unknown>)._leaflet_id) return;
      const map = L.map(ref.current, { center: [lat, lng], zoom: 13, zoomControl: true });
      // Схема (яркий OSM, русские подписи) + спутник с переключателем
      const schema = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '© OpenStreetMap', maxZoom: 19,
      }).addTo(map);
      const satellite = L.tileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        { attribution: '© Esri', maxZoom: 19 },
      );
      L.control.layers({ "Схема": schema, "Спутник": satellite }, {}, { position: "topright" }).addTo(map);
      L.marker([lat, lng]).addTo(map).bindPopup(title || "Участок").openPopup();
    });
    return () => {
      if (ref.current && (ref.current as unknown as Record<string,unknown>)._leaflet_id) {
        // eslint-disable-next-line react-hooks/exhaustive-deps
        (ref.current as unknown as { _leaflet?: { remove: () => void } })._leaflet?.remove?.();
      }
    };
  }, [lat, lng, title]);
  return <div ref={ref} style={{ width: "100%", height: 220 }} />;
}

const PURPOSE_LABEL: Record<string, string> = {
  izhs: "ИЖС", snt: "СНТ", lpkh: "ЛПХ", agricultural: "Сельхоз",
  commercial: "Коммерция", industrial: "Промышленность",
  forest: "Лесной фонд", water: "Водный фонд", special: "Спец.", other: "Иное",
};
const STATUS_CONFIG: Record<string, { label: string; cls: string }> = {
  active: { label: "Торги идут", cls: "badge-green" },
  upcoming: { label: "Скоро", cls: "badge-blue" },
  completed: { label: "Завершены", cls: "badge-gray" },
  cancelled: { label: "Отменены", cls: "badge-red" },
};
const AUCTION_FORM_LABEL: Record<string, string> = {
  auction: "Аукцион", tender: "Конкурс", public: "Публичное предложение", without: "Без торгов",
};
const DEAL_TYPE_LABEL: Record<string, string> = {
  ownership: "В собственность", lease: "В аренду",
  free_use: "Безвозмездное пользование", operational: "Оперативное управление",
};
const RESALE_LABEL: Record<string, string> = {
  yes: "Можно", no: "Нельзя",
  with_notice: "Можно уведомив", with_approval: "Можно согласовав",
};
const DISCREPANCY_LABEL: Record<string, { label: string; cls: string }> = {
  match: { label: "Совпадает", cls: "badge-green" },
  minor: { label: "Расхождение < 10%", cls: "badge-orange" },
  major: { label: "Расхождение > 10%", cls: "badge-red" },
  no_kn: { label: "Нет данных КН", cls: "badge-gray" },
};

function fmt(n?: number) {
  if (!n) return "—";
  return n.toLocaleString("ru");
}
function fmtPrice(n?: number) {
  if (!n) return "—";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)} млн ₽`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)} тыс. ₽`;
  return `${fmt(n)} ₽`;
}
function fmtArea(sqm?: number) {
  if (!sqm) return "—";
  if (sqm >= 10_000) return `${(sqm / 10_000).toFixed(4)} га (${fmt(sqm)} кв.м)`;
  return `${fmt(sqm)} кв.м`;
}
function fmtDate(iso?: string) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("ru", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function Row({ label, value, highlight }: { label: string; value: React.ReactNode; highlight?: boolean }) {
  // Скрываем строку если значение пустое (null/undefined/пустая строка/"—")
  if (value == null || value === "" || value === "—") return null;
  return (
    <tr style={{ background: highlight ? "var(--primary-light)" : "transparent" }}>
      <td style={{ padding: "9px 14px", fontSize: 13, color: "var(--text-2)", width: "40%", borderBottom: "1px solid var(--border)", fontWeight: 500 }}>
        {label}
      </td>
      <td style={{ padding: "9px 14px", fontSize: 13, color: "var(--text)", borderBottom: "1px solid var(--border)", wordBreak: "break-word" }}>
        {value}
      </td>
    </tr>
  );
}

function ScoreBadge({ score }: { score: number }) {
  const cls = score >= 7 ? "score-high" : score >= 4 ? "score-mid" : "score-low";
  return <div className={`score-ring ${cls}`}>{score}</div>;
}

function AiPanel({ lotId, user }: { lotId: number; user: UserProfile | null }) {
  const [assessment, setAssessment] = useState<AiAssessment | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get<{ assessment: AiAssessment | null }>(`/api/ai/assess/${lotId}`)
      .then(d => setAssessment(d.assessment))
      .catch(() => {});
  }, [lotId]);

  // Открыто для всех залогиненных пользователей (на время beta)
  const canRequest = !!user;

  const request = async () => {
    setLoading(true); setError("");
    try {
      const d = await api.post<{ assessment: AiAssessment }>(`/api/ai/assess/${lotId}`, {});
      setAssessment(d.assessment);
    } catch (e) {
      const raw = (e as Error).message || "";
      // Бэкенд для сбоя AI отдаёт 503 с понятным текстом — показываем его.
      // Для совсем непонятных ошибок — fallback на общий текст.
      const friendly = raw.length > 5 && raw.length < 300
        ? raw
        : "AI-оценка временно недоступна. Попробуйте позже.";
      setError(friendly);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: 20 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
        <span style={{ fontSize: 20 }}>🤖</span>
        <h2 style={{ fontSize: 16, fontWeight: 700, margin: 0 }}>AI-оценка участка</h2>
        {assessment && <ScoreBadge score={assessment.score} />}
      </div>

      {assessment ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <p style={{ fontSize: 14, color: "var(--text)", lineHeight: 1.6, margin: 0 }}>
            {assessment.summary}
          </p>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div style={{ background: "#dcfce7", borderRadius: 8, padding: 12 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: "#16a34a", marginBottom: 6 }}>Плюсы</div>
              {assessment.pros.map((p, i) => (
                <div key={i} style={{ fontSize: 13, color: "#166534", marginBottom: 3 }}>✓ {p}</div>
              ))}
            </div>
            <div style={{ background: "#fee2e2", borderRadius: 8, padding: 12 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: "#dc2626", marginBottom: 6 }}>Минусы и риски</div>
              {[...assessment.cons, ...assessment.risks].map((c, i) => (
                <div key={i} style={{ fontSize: 13, color: "#991b1b", marginBottom: 3 }}>✕ {c}</div>
              ))}
            </div>
          </div>
          <div style={{ background: "var(--surface-2)", borderRadius: 8, padding: 12 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-2)", marginBottom: 6 }}>Оценка рыночной стоимости</div>
            <div style={{ fontSize: 15, fontWeight: 700, color: "var(--primary)" }}>
              {fmtPrice(assessment.price_estimate.min)} — {fmtPrice(assessment.price_estimate.max)}
            </div>
            <div style={{ fontSize: 12, color: "var(--text-3)", marginTop: 4 }}>{assessment.price_estimate.comment}</div>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <span style={{ fontSize: 12, color: "var(--text-3)" }}>
              Рекомендуется: <b style={{ color: "var(--text)" }}>{assessment.recommended_use}</b>
            </span>
            <span style={{ fontSize: 11, color: "var(--text-3)", marginLeft: "auto" }}>
              Оценено: {fmtDate(assessment.assessed_at)}
            </span>
            <button className="btn btn-secondary btn-sm" onClick={request} disabled={loading || !canRequest}>
              Обновить оценку
            </button>
          </div>
        </div>
      ) : (
        <div style={{ textAlign: "center", padding: "20px 0" }}>
          {canRequest ? (
            <>
              <p style={{ color: "var(--text-2)", fontSize: 14, marginBottom: 12 }}>
                Оценка ещё не запрошена. Claude проанализирует участок и даст инвестиционное заключение.
              </p>
              {error && <div style={{ color: "var(--danger)", fontSize: 13, marginBottom: 10 }}>{error}</div>}
              <button className="btn btn-primary" onClick={request} disabled={loading}>
                {loading ? "Анализируем..." : "Запросить AI-оценку"}
              </button>
            </>
          ) : (
            <>
              <p style={{ color: "var(--text-2)", fontSize: 14, marginBottom: 12 }}>
                Войдите в аккаунт, чтобы получить AI-оценку лота
              </p>
              <a href="/login" className="btn btn-primary">Войти →</a>
            </>
          )}
        </div>
      )}
    </div>
  );
}

interface MarketLot {
  id: number;
  title?: string;
  start_price?: number;
  area_sqm?: number;
  price_per_sqm?: number;
  address?: string;
  lot_url?: string;
  source: string;
}

export default function LotDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [lot, setLot] = useState<LotDetail | null>(null);
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saved, setSaved] = useState(false);
  const [market, setMarket] = useState<MarketLot[]>([]);
  const [regionData, setRegionData] = useState<RegionData | null>(null);
  const compareIds = useCompareIds();
  const inCompare = compareIds.includes(parseInt(id));

  const toggleCompare = () => {
    const lotId = parseInt(id);
    const result = compare.toggle(lotId);
    if (result === null) {
      alert(`Можно сравнивать не более ${compare.MAX} участков. Уберите один и попробуйте снова.`);
    }
  };

  useEffect(() => {
    Promise.all([
      api.get<LotDetail>(`/api/lots/${id}`),
      getMe(),
    ]).then(([l, u]) => {
      setLot(l);
      setUser(u);
      // Логируем просмотр для авторизованных (бэк сам дедуплицирует за 60 мин)
      if (u) api.post(`/api/users/views/${id}`, {}).catch(() => {});
      // Премиум-данные (рынок, регион) тянем только для Pro+ — free не получает их
      // ни на экране, ни в Network. Заглушку рисуем по рангу ниже.
      if (planRank(u?.subscription_plan) >= RANK_PRO) {
        api.get<MarketLot[]>(`/api/lots/${id}/market`).then(setMarket).catch(() => {});
        const regionCode = (l as { region_code?: string }).region_code || "";
        if (regionCode) {
          api.get<RegionData>(`/api/lots/region-data/${regionCode}`).then(setRegionData).catch(() => {});
        }
      }
    }).catch(() => router.push("/lots"))
    .finally(() => setLoading(false));
  }, [id, router]);

  const toggleSave = async () => {
    if (!user) { router.push("/login"); return; }
    if (saved) {
      await api.delete(`/api/users/saved-lots/${id}`);
    } else {
      await api.post(`/api/users/saved-lots/${id}`, {});
    }
    setSaved(s => !s);
  };

  const isPaid = !!user && user.subscription_plan !== "free";
  const rank = planRank(user?.subscription_plan);

  const downloadPdf = async () => {
    if (!isPaid) { router.push("/pricing"); return; }
    try {
      const token = (await import("js-cookie")).default.get("access_token");
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? ""}/api/lots/${id}/report.pdf`,
        { headers: token ? { Authorization: `Bearer ${token}` } : {} },
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `lot-${id}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      alert("Не удалось скачать PDF. Попробуйте позже.");
    }
  };

  if (loading) return <div style={{ padding: 40, textAlign: "center", color: "var(--text-3)" }}>Загрузка...</div>;
  if (!lot) return null;

  const status = STATUS_CONFIG[lot.status] || { label: lot.status, cls: "badge-gray" };
  const discrepancy = lot.area_discrepancy ? DISCREPANCY_LABEL[lot.area_discrepancy] : null;

  return (
    <div style={{ flex: 1, overflow: "auto", background: "var(--bg)" }}>
      <div style={{ maxWidth: 1000, margin: "0 auto", padding: "28px 24px" }}>

        {/* Breadcrumb */}
        <div style={{ fontSize: 13, color: "var(--text-3)", marginBottom: 16 }}>
          <a href="/" style={{ color: "var(--text-3)" }}>Карта</a>
          {" / "}
          <a href="/lots" style={{ color: "var(--text-3)" }}>Каталог</a>
          {" / "}
          <span style={{ color: "var(--text-2)" }}>Лот #{lot.id}</span>
        </div>

        {/* Header */}
        <div style={{ display: "flex", gap: 12, alignItems: "flex-start", marginBottom: 20, flexWrap: "wrap" }}>
          <ScoreCircle score={lot.score} size={56} />
          <div style={{ flex: 1 }}>
            <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 8, lineHeight: 1.3, wordBreak: "break-word", overflowWrap: "anywhere" }}>
              {lot.title || "Земельный участок"}
            </h1>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 8 }}>
              <span className={`badge ${status.cls}`}>{status.label}</span>
              {lot.land_purpose && <span className="badge badge-gray">{PURPOSE_LABEL[lot.land_purpose] || lot.land_purpose}</span>}
              {lot.auction_type === "rent" && <span className="badge badge-orange">Аренда</span>}
              {lot.source === "torgi_gov" && <span className="badge badge-blue">torgi.gov</span>}
              {lot.source === "avito" && <span className="badge badge-orange">Авито</span>}
              {lot.source === "cian" && <span className="badge badge-green">ЦИАН</span>}
              <DiscountTag pct={lot.discount_to_market_pct} />
            </div>
            <ScoreBadges badges={lot.score_badges} max={6} />
          </div>
          <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
            <button
              onClick={downloadPdf}
              className="btn btn-sm btn-secondary"
              title={isPaid ? "Скачать отчёт по лоту в PDF" : "PDF-отчёт доступен с тарифа Pro"}
            >
              {isPaid ? "📄 PDF" : "🔒 PDF"}
            </button>
            <button className={`btn btn-sm ${saved ? "btn-primary" : "btn-secondary"}`} onClick={toggleSave}>
              {saved ? "★ В избранном" : "☆ В избранное"}
            </button>
            {lot.lot_url && (
              <a href={lot.lot_url} target="_blank" rel="noopener noreferrer" className="btn btn-secondary btn-sm">
                Оригинал ↗
              </a>
            )}
          </div>
        </div>

        {/* Внешние сервисы — НСПД, Авито, ЦИАН, Сообщить об ошибке */}
        <div style={{
          display: "flex", gap: 8, flexWrap: "wrap",
          padding: "10px 12px", marginBottom: 18,
          background: "var(--surface-2)", borderRadius: 10,
          border: "1px solid var(--border)", fontSize: 13,
        }}>
          <span style={{ color: "var(--text-3)", marginRight: 4, alignSelf: "center" }}>Открыть в:</span>
          {lot.cadastral_number && (
            <a
              href={`https://nspd.gov.ru/map?thematic=PKK&zoom=18&attributeFilter=%7B%22cadNum%22:%22${encodeURIComponent(lot.cadastral_number)}%22%7D`}
              target="_blank" rel="noopener noreferrer"
              style={{ color: "var(--primary)", textDecoration: "none", fontWeight: 500 }}
              title="Национальная система пространственных данных — карта Росреестра"
            >
              🌐 НСПД ↗
            </a>
          )}
          {lot.address && (
            <>
              <a
                href={`https://www.avito.ru/all/zemelnye_uchastki?q=${encodeURIComponent(lot.address)}`}
                target="_blank" rel="noopener noreferrer"
                style={{ color: "var(--primary)", textDecoration: "none", fontWeight: 500 }}
                title="Поиск похожих участков на Авито"
              >
                🏠 Авито ↗
              </a>
              <a
                href={`https://www.cian.ru/cat.php?deal_type=sale&offer_type=suburban&q=${encodeURIComponent(lot.address)}`}
                target="_blank" rel="noopener noreferrer"
                style={{ color: "var(--primary)", textDecoration: "none", fontWeight: 500 }}
                title="Поиск похожих участков на ЦИАН"
              >
                🏢 ЦИАН ↗
              </a>
            </>
          )}
          <a
            href={`https://t.me/ZemlyaOnlineBot?start=err_${id}`}
            target="_blank" rel="noopener noreferrer"
            style={{ color: "var(--text-3)", textDecoration: "none", marginLeft: "auto" }}
            title="Сообщить, что данные в лоте устарели или ошибочны"
          >
            ⚠️ Сообщить об ошибке
          </a>
        </div>

        {/* Key metrics */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 12, marginBottom: 24 }}>
          {[
            { label: "Начальная цена", value: fmtPrice(lot.start_price), accent: true },
            { label: "Площадь [TG]", value: fmtArea(lot.area_sqm) },
            { label: "Площадь [КН]", value: fmtArea(lot.area_sqm_kn) },
            { label: "Задаток", value: lot.deposit ? `${fmtPrice(lot.deposit)}${lot.deposit_pct ? ` (${lot.deposit_pct}%)` : ""}` : "—" },
            { label: "Кадастровая стоимость", value: fmtPrice(lot.cadastral_cost) },
            {
              label: "% НЦ / КС",
              value: rank >= RANK_INVESTOR
                ? (lot.pct_price_to_cadastral ? `${lot.pct_price_to_cadastral.toFixed(1)}%` : "—")
                : <a href="/pricing" style={{ fontSize: 13, color: "var(--text-3)", textDecoration: "none" }} title="Доступно с тарифа Инвестор">🔒 Инвестор</a>,
            },
            {
              label: "% КС / Рынок",
              value: rank >= RANK_INVESTOR
                ? ((lot.cadastral_cost && lot.market_price_sqm && lot.area_sqm)
                  ? `${((lot.cadastral_cost / (lot.market_price_sqm * lot.area_sqm)) * 100).toFixed(1)}%`
                  : "—")
                : <a href="/pricing" style={{ fontSize: 13, color: "var(--text-3)", textDecoration: "none" }} title="Доступно с тарифа Инвестор">🔒 Инвестор</a>,
            },
          ].map(m => (
            <div key={m.label} style={{
              background: "var(--surface)", border: m.accent ? "1px solid var(--primary)" : "1px solid var(--border)",
              borderRadius: 10, padding: "14px 16px",
            }}>
              <div style={{ fontSize: 11, color: "var(--text-3)", marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.04em" }}>{m.label}</div>
              <div style={{ fontSize: 17, fontWeight: 700, color: m.accent ? "var(--primary)" : "var(--text)" }}>{m.value}</div>
            </div>
          ))}
        </div>

        <div className="lot-detail-cols" style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) 340px", gap: 20 }}>
          {/* Left column */}
          <div style={{ display: "flex", flexDirection: "column", gap: 16, minWidth: 0 }}>

            {/* AI Assessment */}
            <AiPanel lotId={Number(id)} user={user} />

            {/* Основные данные торгов */}
            <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, overflow: "hidden" }}>
              <div style={{ padding: "14px 16px", fontWeight: 700, fontSize: 15, borderBottom: "1px solid var(--border)" }}>
                Данные торгов
              </div>
              <table style={{ width: "100%", borderCollapse: "collapse", tableLayout: "fixed" }}>
                <tbody>
                  <Row label="Вид торгов" value={lot.auction_type === "sale" ? "Продажа" : lot.auction_type === "rent" ? "Аренда" : "Приватизация"} />
                  <Row label="Форма проведения" value={lot.auction_form ? AUCTION_FORM_LABEL[lot.auction_form] : null} />
                  <Row label="Вид сделки" value={lot.deal_type ? DEAL_TYPE_LABEL[lot.deal_type] : null} />
                  <Row label="ЭТП" value={lot.etp} />
                  <Row label="Переуступка" value={lot.resale_type ? RESALE_LABEL[lot.resale_type] : null} />
                  {lot.sublease_allowed && <Row label="Субаренда" value={<span className="badge badge-green">Упоминается</span>} />}
                  {lot.assignment_allowed && <Row label="Переуступка (текст)" value={<span className="badge badge-green">Упоминается</span>} />}
                  <Row label="Организатор" value={lot.organizer_name} />
                  <Row label="Номер извещения/лота" value={lot.notice_number} />
                  <Row label="Начало приёма заявок" value={fmtDate(lot.submission_start)} />
                  <Row label="Срок подачи заявок" value={fmtDate(lot.submission_end)} highlight />
                  <Row label="Дата проведения торгов" value={fmtDate(lot.auction_start_date)} />
                </tbody>
              </table>
            </div>

            {/* Характеристики TG */}
            <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, overflow: "hidden" }}>
              <div style={{ padding: "14px 16px", fontWeight: 700, fontSize: 15, borderBottom: "1px solid var(--border)" }}>
                Характеристики участка <span style={{ color: "var(--text-3)", fontWeight: 400, fontSize: 13 }}>[TG] torgi.gov</span>
              </div>
              <table style={{ width: "100%", borderCollapse: "collapse", tableLayout: "fixed" }}>
                <tbody>
                  <Row label="Кадастровый номер" value={
                    lot.cadastral_number
                      ? <a href={`https://pkk.rosreestr.ru/#/search/${lot.cadastral_number}`} target="_blank" rel="noopener noreferrer">{lot.cadastral_number} ↗</a>
                      : null
                  } />
                  <Row label="Категория [TG]" value={lot.category_tg} />
                  <Row label="ВРИ [TG]" value={lot.vri_tg} />
                  <Row label="Площадь [TG]" value={fmtArea(lot.area_sqm)} />
                  <Row label="Адрес" value={lot.address} />
                  <Row label="Регион" value={lot.region_name} />
                </tbody>
              </table>
            </div>

            {/* Характеристики КН */}
            <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, overflow: "hidden" }}>
              <div style={{ padding: "14px 16px", fontWeight: 700, fontSize: 15, borderBottom: "1px solid var(--border)" }}>
                Характеристики участка <span style={{ color: "var(--text-3)", fontWeight: 400, fontSize: 13 }}>[КН] Росреестр</span>
              </div>
              <table style={{ width: "100%", borderCollapse: "collapse", tableLayout: "fixed" }}>
                <tbody>
                  <Row label="Категория [КН]" value={lot.category_kn} />
                  <Row label="ВРИ [КН]" value={lot.vri_kn} />
                  <Row label="Площадь [КН]" value={fmtArea(lot.area_sqm_kn)} />
                  <Row label="Сравн. площади TG↔КН" value={discrepancy ? <span className={`badge ${discrepancy.cls}`}>{discrepancy.label}</span> : null} />
                  <Row label="Кадастровая стоимость" value={lot.cadastral_cost ? `${fmtPrice(lot.cadastral_cost)}` : null} />
                </tbody>
              </table>
            </div>

            {/* Локация и ликвидность — Pro+ (зеркало замка фильтра на главной) */}
            {rank >= RANK_PRO ? (
              <LocationCard
                city={lot.nearest_city_name}
                distance={lot.nearest_city_distance_km}
                population={lot.nearest_city_population}
              />
            ) : (
              <LockedBlock
                title="Локация и ликвидность"
                planLabel="Pro"
                description="Ближайший город, расстояние до него и оценка ликвидности участка — сразу видно, легко ли будет продать или сдать землю."
              />
            )}

            {/* Коммуникации */}
            <CommsCard comms={lot.communications} />

            {/* Что рядом — водоёмы, лес, трассы, ж/д (из OSM) */}
            <NearbyFeaturesCard data={(lot as unknown as { nearby_features?: NearbyFeatures }).nearby_features} />

            {/* Контакты организатора (отдел земельных отношений) */}
            {rank >= RANK_PRO ? (
              <OrganizerContactsCard
                organizerName={lot.organizer_name}
                contacts={(lot as unknown as { organizer_contacts?: OrganizerContacts }).organizer_contacts}
              />
            ) : (
              <div style={{
                background: "var(--surface)", border: "1px solid var(--border)",
                borderRadius: 10, padding: 16, marginBottom: 12,
              }}>
                <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 6 }}>🔒 Контакты администрации</div>
                <div style={{ fontSize: 13, color: "var(--text-3)", marginBottom: 10, lineHeight: 1.5 }}>
                  Прямые телефоны и email отдела земельных отношений организатора торгов — доступны с тарифа <b>Pro</b> и выше.
                  Помогает уточнить детали лота до подачи заявки и избежать лишних подводных камней.
                </div>
                <a href="/pricing" className="btn btn-primary btn-sm" style={{ textDecoration: "none" }}>
                  ⚡ Перейти к тарифам
                </a>
              </div>
            )}

            {/* Калькулятор окупаемости — каркасный дом */}
            {rank >= RANK_PRO ? (
              <RoiCalculator lotId={Number(id)} />
            ) : (
              <LockedBlock
                title="Калькулятор окупаемости"
                planLabel="Pro"
                description="Расчёт ROI каркасного дома на участке: вложения, выручка от продажи, прибыль и срок окупаемости — под площадь и уровень отделки."
              />
            )}

            {/* Баннер снижения цены */}
            {(() => {
              const lp = lot as unknown as { last_price_drop_pct?: number; last_price_drop_at?: string };
              if (!lp.last_price_drop_pct || lp.last_price_drop_pct < 5) return null;
              const dropDate = lp.last_price_drop_at ? new Date(lp.last_price_drop_at) : null;
              const daysAgo = dropDate ? Math.floor((Date.now() - dropDate.getTime()) / 86400000) : null;
              return (
                <div style={{
                  background: "linear-gradient(135deg, #dc2626, #ea580c)",
                  color: "white", borderRadius: 12, padding: 16,
                }}>
                  <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 4 }}>
                    📉 Цена снижена на {Math.round(lp.last_price_drop_pct)}%
                  </div>
                  <div style={{ fontSize: 13, opacity: 0.9 }}>
                    {daysAgo === 0 ? "Сегодня" : daysAgo === 1 ? "Вчера" : `${daysAgo} дн. назад`}.
                    Это повторные торги — шанс взять дешевле обычной начальной цены.
                  </div>
                </div>
              );
            })()}

            {/* История похожих лотов */}
            {rank >= RANK_PRO ? (
              <SimilarHistoryCard lotId={Number(id)} />
            ) : (
              <LockedBlock
                title="История похожих лотов в регионе"
                planLabel="Pro"
                description="Завершённые торги по похожим участкам: медиана цены и стоимость за м² — реальный ориентир, за сколько уходят такие лоты."
              />
            )}

            {/* Региональные особенности (выкуп, КФХ-дом, перераспределение) */}
            {rank >= RANK_PRO ? (
              <RegionInfo data={regionData} regionName={lot.region_name} cadastralCost={lot.cadastral_cost} />
            ) : (
              <LockedBlock
                title="Региональные особенности"
                planLabel="Pro"
                description="Цена выкупа участка (ст. 39.18/39.20 ЗК), дом КФХ на сельхозземле, перераспределение площади — расчёт по вашему региону."
              />
            )}

            {/* ТОР/СЭЗ — налоговые льготы для резидентов */}
            {lot.tor_zone && (rank >= RANK_INVESTOR ? (
              <div style={{
                background: "var(--surface)", border: "1px solid var(--border)",
                borderRadius: 12, padding: 16,
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                  <span style={{
                    background: "linear-gradient(135deg,#7c3aed,#9333ea)",
                    color: "white", fontSize: 11, fontWeight: 700,
                    padding: "3px 8px", borderRadius: 4, letterSpacing: 0.5,
                  }}>
                    🏭 {lot.tor_zone.label}
                  </span>
                  <span style={{ fontWeight: 600, fontSize: 14 }}>
                    Зона налоговых льгот
                  </span>
                </div>
                <p style={{ fontSize: 13, color: "var(--text-2)", lineHeight: 1.55, margin: 0 }}>
                  {lot.tor_zone.description}
                </p>
                <p style={{ fontSize: 11, color: "var(--text-3)", marginTop: 8, lineHeight: 1.4 }}>
                  💡 Регистрация резидентом ТОР подаётся через Минвостокразвития (для ДФО)
                  или местную администрацию. Срок проверки заявки — до 30 дней.
                </p>
              </div>
            ) : (
              <LockedBlock
                title="Зона налоговых льгот (ТОР/СЭЗ)"
                planLabel="Инвестор"
                description="Участок в зоне с льготами для резидентов: налог на прибыль и имущество 0%, пониженные страховые, земля без торгов. Условия и порядок регистрации — на тарифе Инвестор."
              />
            ))}

            {/* Условия договора (из PDF) */}
            {lot.contract_terms ? (
              rank >= RANK_INVESTOR ? (
                <ContractTerms data={lot.contract_terms} />
              ) : (
                <LockedBlock
                  title="Условия договора (preDD)"
                  planLabel="Инвестор"
                  description="Разбор договора аренды из извещения: переуступка, субаренда, право выкупа, штрафы и обязательства арендатора — 11 проверок preDD."
                />
              )
            ) : null}

            {/* Полное описание из извещения (PDF) */}
            <FullDescription text={lot.full_description} />

            {/* Краткое описание лота (из API) */}
            {lot.description && !lot.full_description && (
              <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: 20 }}>
                <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 10 }}>Описание лота</div>
                <p style={{ fontSize: 13, color: "var(--text-2)", lineHeight: 1.7, margin: 0, whiteSpace: "pre-wrap" }}>
                  {lot.description}
                </p>
              </div>
            )}

            {/* Сравнение с рынком */}
            {rank >= RANK_PRO ? (
              market.length > 0 && (
              <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, overflow: "hidden" }}>
                <div style={{ padding: "14px 16px", fontWeight: 700, fontSize: 15, borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", gap: 8 }}>
                  Рыночные предложения
                  <span style={{ fontSize: 12, fontWeight: 400, color: "var(--text-3)" }}>похожие участки в регионе (ЦИАН, Авито)</span>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
                  {market.map((m, i) => (
                    <div key={m.id} style={{ padding: "10px 16px", borderBottom: i < market.length - 1 ? "1px solid var(--border)" : "none", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 13, fontWeight: 500, color: "var(--text)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                          {m.title || "Земельный участок"}
                        </div>
                        <div style={{ fontSize: 12, color: "var(--text-3)", marginTop: 2 }}>
                          {m.area_sqm ? fmtArea(m.area_sqm) : "—"}
                          {m.address ? ` · ${m.address.slice(0, 50)}` : ""}
                        </div>
                      </div>
                      <div style={{ textAlign: "right", flexShrink: 0 }}>
                        <div style={{ fontSize: 14, fontWeight: 700, color: "var(--text)" }}>{fmtPrice(m.start_price)}</div>
                        {m.price_per_sqm && <div style={{ fontSize: 11, color: "var(--text-3)" }}>{fmtPrice(m.price_per_sqm)}/м²</div>}
                        {m.lot_url && <a href={m.lot_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: 11, color: "var(--primary)" }}>{m.source === "avito" ? "Авито ↗" : "ЦИАН ↗"}</a>}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              )
            ) : (
              <LockedBlock
                title="Рыночные предложения"
                planLabel="Pro"
                description="Похожие участки в регионе на ЦИАН и Авито — прямое сравнение цены лота с рынком, чтобы увидеть реальный дисконт."
              />
            )}
          </div>

          {/* Right column — mini map + actions */}
          <div className="lot-detail-aside" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {/* Mini map */}
            {lot.lat && lot.lng && (
              <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, overflow: "hidden" }}>
                <div style={{ padding: "12px 16px", fontWeight: 600, fontSize: 14, borderBottom: "1px solid var(--border)" }}>
                  На карте
                </div>
                <MiniMap lat={lot.lat} lng={lot.lng} title={lot.title} />
                <div style={{ padding: "8px 16px", fontSize: 12, color: "var(--text-3)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span>{lot.lat.toFixed(6)}, {lot.lng.toFixed(6)}</span>
                  <a href={`https://pkk.rosreestr.ru/#/search/${lot.cadastral_number || `${lot.lat},${lot.lng}`}`} target="_blank" rel="noopener noreferrer" style={{ color: "var(--primary)", textDecoration: "none" }}>ПКК ↗</a>
                </div>
              </div>
            )}

            {/* Quick actions */}
            <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: 16, display: "flex", flexDirection: "column", gap: 8 }}>
              <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 4 }}>Действия</div>
              {lot.lot_url && (
                <a href={lot.lot_url} target="_blank" rel="noopener noreferrer" className="btn btn-primary" style={{ width: "100%" }}>
                  Подать заявку ↗
                </a>
              )}
              <a href={`/services?lot=${id}`} className="btn btn-secondary" style={{
                width: "100%",
                background: "linear-gradient(135deg, #f59e0b15, #f59e0b25)",
                border: "1px solid #f59e0b66", color: "var(--text)",
              }} title="Сопровождение торгов под ключ: проверим лот, подготовим документы, выиграем аукцион">
                🤝 Участвовать с нами
              </a>
              <button className={`btn ${saved ? "btn-secondary" : "btn-secondary"}`} style={{ width: "100%" }} onClick={toggleSave}>
                {saved ? "★ Убрать из избранного" : "☆ Добавить в избранное"}
              </button>
              <button
                className="btn btn-secondary"
                style={{ width: "100%" }}
                onClick={toggleCompare}
              >
                {inCompare ? "✓ В сравнении (убрать)" : `+ В сравнение${compareIds.length > 0 ? ` (${compareIds.length})` : ""}`}
              </button>
              {compareIds.length >= 2 && (
                <a href="/compare" className="btn btn-primary btn-sm" style={{ width: "100%" }}>
                  Открыть сравнение ({compareIds.length})
                </a>
              )}
            </div>

            {/* Price analysis */}
            <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: 16 }}>
              <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 12 }}>Анализ цены</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {[
                  { label: "Начальная цена", value: fmtPrice(lot.start_price) },
                  { label: "Цена за кв.м", value: lot.price_per_sqm ? `${fmtPrice(lot.price_per_sqm)}/м²` : "—" },
                  { label: "Кадастровая стоимость", value: fmtPrice(lot.cadastral_cost) },
                  { label: "НЦ / КС", value: rank >= RANK_INVESTOR ? (lot.pct_price_to_cadastral ? `${lot.pct_price_to_cadastral.toFixed(1)}%` : "—") : "🔒 Инвестор", highlight: true },
                  { label: "Задаток", value: lot.deposit ? fmtPrice(lot.deposit) : "—" },
                ].map(item => (
                  <div key={item.label} style={{
                    display: "flex", justifyContent: "space-between",
                    padding: "6px 8px", borderBottom: "1px solid var(--border)",
                    background: (item as { highlight?: boolean }).highlight ? "var(--primary-light)" : "transparent",
                    borderRadius: 4,
                  }}>
                    <span style={{ fontSize: 12, color: "var(--text-2)" }}>{item.label}</span>
                    <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text)" }}>{item.value}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
