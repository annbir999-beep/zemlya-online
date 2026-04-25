"use client";
import { useEffect, useState, use, useRef } from "react";
import { useRouter } from "next/navigation";
import { api, LotDetail, AiAssessment } from "@/lib/api";
import { getMe } from "@/lib/auth";
import type { UserProfile } from "@/lib/api";
import { RegionInfo, RegionData } from "@/components/RegionInfo";
import { ScoreCircle, ScoreBadges, DiscountTag } from "@/components/ScoreBadge";

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
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19 }).addTo(map);
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
  return (
    <tr style={{ background: highlight ? "var(--primary-light)" : "transparent" }}>
      <td style={{ padding: "9px 14px", fontSize: 13, color: "var(--text-2)", width: "40%", borderBottom: "1px solid var(--border)", fontWeight: 500 }}>
        {label}
      </td>
      <td style={{ padding: "9px 14px", fontSize: 13, color: "var(--text)", borderBottom: "1px solid var(--border)" }}>
        {value ?? "—"}
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

  const canRequest = user && ["expert", "landlord"].includes(user.subscription_plan);

  const request = async () => {
    setLoading(true); setError("");
    try {
      const d = await api.post<{ assessment: AiAssessment }>(`/api/ai/assess/${lotId}`, {});
      setAssessment(d.assessment);
    } catch (e) {
      setError((e as Error).message);
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
                AI-оценка доступна на тарифах <b>Эксперт</b> и <b>Лендлорд</b>
              </p>
              <a href="/pricing" className="btn btn-primary">Улучшить тариф →</a>
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

  useEffect(() => {
    Promise.all([
      api.get<LotDetail>(`/api/lots/${id}`),
      getMe(),
    ]).then(([l, u]) => {
      setLot(l);
      setUser(u);
      api.get<MarketLot[]>(`/api/lots/${id}/market`).then(setMarket).catch(() => {});
      // Региональные особенности — выкуп / стройка КФХ / перераспределение
      const regionCode = (l as { region_code?: string }).region_code || "";
      if (regionCode) {
        api.get<RegionData>(`/api/lots/region-data/${regionCode}`).then(setRegionData).catch(() => {});
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
            <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 8, lineHeight: 1.3 }}>
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

        {/* Key metrics */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 12, marginBottom: 24 }}>
          {[
            { label: "Начальная цена", value: fmtPrice(lot.start_price), accent: true },
            { label: "Площадь [TG]", value: fmtArea(lot.area_sqm) },
            { label: "Площадь [КН]", value: fmtArea(lot.area_sqm_kn) },
            { label: "Задаток", value: lot.deposit ? `${fmtPrice(lot.deposit)}${lot.deposit_pct ? ` (${lot.deposit_pct}%)` : ""}` : "—" },
            { label: "Кадастровая стоимость", value: fmtPrice(lot.cadastral_cost) },
            { label: "% НЦ / КС", value: lot.pct_price_to_cadastral ? `${lot.pct_price_to_cadastral.toFixed(1)}%` : "—" },
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

        <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: 20 }}>
          {/* Left column */}
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

            {/* AI Assessment */}
            <AiPanel lotId={Number(id)} user={user} />

            {/* Основные данные торгов */}
            <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, overflow: "hidden" }}>
              <div style={{ padding: "14px 16px", fontWeight: 700, fontSize: 15, borderBottom: "1px solid var(--border)" }}>
                Данные торгов
              </div>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
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
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
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
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <tbody>
                  <Row label="Категория [КН]" value={lot.category_kn} />
                  <Row label="ВРИ [КН]" value={lot.vri_kn} />
                  <Row label="Площадь [КН]" value={fmtArea(lot.area_sqm_kn)} />
                  <Row label="Сравн. площади TG↔КН" value={discrepancy ? <span className={`badge ${discrepancy.cls}`}>{discrepancy.label}</span> : null} />
                  <Row label="Кадастровая стоимость" value={lot.cadastral_cost ? `${fmtPrice(lot.cadastral_cost)}` : null} />
                </tbody>
              </table>
            </div>

            {/* Региональные особенности (выкуп, КФХ-дом, перераспределение) */}
            <RegionInfo data={regionData} regionName={lot.region_name} cadastralCost={lot.cadastral_cost} />

            {/* Описание */}
            {lot.description && (
              <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: 20 }}>
                <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 10 }}>Описание лота</div>
                <p style={{ fontSize: 13, color: "var(--text-2)", lineHeight: 1.7, margin: 0, whiteSpace: "pre-wrap" }}>
                  {lot.description}
                </p>
              </div>
            )}

            {/* Сравнение с рынком */}
            {market.length > 0 && (
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
            )}
          </div>

          {/* Right column — mini map + actions */}
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
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
              <button className={`btn ${saved ? "btn-secondary" : "btn-secondary"}`} style={{ width: "100%" }} onClick={toggleSave}>
                {saved ? "★ Убрать из избранного" : "☆ Добавить в избранное"}
              </button>
              <a href={`/compare?ids=${lot.id}`} className="btn btn-secondary" style={{ width: "100%" }}>
                Добавить к сравнению
              </a>
            </div>

            {/* Price analysis */}
            <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: 16 }}>
              <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 12 }}>Анализ цены</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {[
                  { label: "Начальная цена", value: fmtPrice(lot.start_price) },
                  { label: "Цена за кв.м", value: lot.price_per_sqm ? `${fmtPrice(lot.price_per_sqm)}/м²` : "—" },
                  { label: "Кадастровая стоимость", value: fmtPrice(lot.cadastral_cost) },
                  { label: "НЦ / КС", value: lot.pct_price_to_cadastral ? `${lot.pct_price_to_cadastral.toFixed(1)}%` : "—", highlight: true },
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
