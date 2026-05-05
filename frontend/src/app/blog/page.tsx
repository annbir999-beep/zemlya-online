import Link from "next/link";

export const metadata = {
  title: "Блог | Земля.ОНЛАЙН — практика покупки земли с торгов",
  description: "Юридические и инвестиционные руководства по земельным аукционам torgi.gov: ст. 39.18 ЗК РФ, документация лота, выкуп КФХ.",
};

const ARTICLES = [
  {
    slug: "dokumentaciya-lota-torgi-gov",
    title: "Как читать документацию лота torgi.gov.ru",
    excerpt: "Извещение, проект договора, ТУ и схема расположения — что искать в каждом документе и как не упустить риски.",
    minutes: 8,
    date: "2026-05-04",
  },
  {
    slug: "statya-39-18-zk-rf-praktika",
    title: "Статья 39.18 ЗК РФ на практике: получить землю без торгов",
    excerpt: "Механизм заявки на участок без аукциона: сроки, документы, типичные отказы муниципалитетов и как их обходить.",
    minutes: 10,
    date: "2026-05-04",
  },
  {
    slug: "oshibki-pri-vykupe-kfh",
    title: "5 ошибок при выкупе земель К(Ф)Х по 39.3 ЗК РФ",
    excerpt: "Срок аренды, нецелевое использование, региональные коэффициенты — где обычно проваливаются заявки на выкуп.",
    minutes: 7,
    date: "2026-05-04",
  },
];

export default function BlogIndex() {
  return (
    <div style={{ flex: 1, overflow: "auto", padding: "32px 20px", maxWidth: 880, margin: "0 auto", width: "100%" }}>
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 32, fontWeight: 700, marginBottom: 8 }}>Блог</h1>
        <p style={{ color: "var(--text-3)", fontSize: 15, lineHeight: 1.5 }}>
          Юридические и инвестиционные руководства по земельным аукционам:
          как читать документы, получить землю без торгов, избежать частых ошибок при выкупе.
        </p>
      </div>
      <div style={{ display: "grid", gap: 14 }}>
        {ARTICLES.map((a) => (
          <Link
            key={a.slug}
            href={`/blog/${a.slug}`}
            style={{
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: 12,
              padding: 20,
              textDecoration: "none",
              color: "inherit",
              display: "block",
              transition: "border-color .15s",
            }}
          >
            <div style={{ fontSize: 11, color: "var(--text-3)", marginBottom: 6 }}>
              {new Date(a.date).toLocaleDateString("ru", { day: "2-digit", month: "long", year: "numeric" })} · {a.minutes} мин чтения
            </div>
            <div style={{ fontSize: 19, fontWeight: 600, marginBottom: 6 }}>{a.title}</div>
            <div style={{ fontSize: 14, color: "var(--text-3)", lineHeight: 1.5 }}>{a.excerpt}</div>
          </Link>
        ))}
      </div>
    </div>
  );
}
