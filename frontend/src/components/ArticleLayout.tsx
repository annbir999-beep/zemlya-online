import Link from "next/link";
import { ReactNode } from "react";

export default function ArticleLayout({
  title,
  date,
  minutes,
  description,
  children,
}: {
  title: string;
  date: string;
  minutes: number;
  description: string;
  children: ReactNode;
}) {
  return (
    <div style={{ flex: 1, overflow: "auto", padding: "32px 20px" }}>
      <article style={{ maxWidth: 720, margin: "0 auto", width: "100%" }}>
        <Link href="/blog" style={{ fontSize: 13, color: "var(--text-3)", textDecoration: "none" }}>
          ← Все статьи
        </Link>

        <h1 style={{ fontSize: 30, fontWeight: 700, marginTop: 16, marginBottom: 10, lineHeight: 1.2 }}>
          {title}
        </h1>
        <div style={{ fontSize: 12, color: "var(--text-3)", marginBottom: 6 }}>
          {new Date(date).toLocaleDateString("ru", { day: "2-digit", month: "long", year: "numeric" })} · {minutes} мин чтения
        </div>
        <p style={{ fontSize: 16, color: "var(--text-2)", marginBottom: 24, lineHeight: 1.6, fontStyle: "italic" }}>
          {description}
        </p>

        <div className="article-body" style={{ fontSize: 15, lineHeight: 1.7, color: "var(--text-1)" }}>
          {children}
        </div>

        <div style={{
          marginTop: 36, padding: 20,
          background: "linear-gradient(135deg, #16a34a, #0d9488)",
          color: "white", borderRadius: 14,
          textAlign: "center",
        }}>
          <div style={{ fontSize: 19, fontWeight: 700, marginBottom: 8 }}>
            Не разбирайтесь с лотом сами
          </div>
          <div style={{ fontSize: 14, opacity: 0.92, marginBottom: 14, lineHeight: 1.5 }}>
            Вставьте ссылку на лот torgi.gov — наш AI выдаст полный разбор за 490 ₽:
            ВРИ, обременения, ЗОУИТ, реальная цена, риски договора.
          </div>
          <Link
            href="/audit-lot"
            style={{
              display: "inline-block",
              background: "white",
              color: "#0d9488",
              padding: "10px 22px",
              borderRadius: 8,
              textDecoration: "none",
              fontWeight: 700,
              fontSize: 14,
            }}
          >
            Заказать AI-аудит за 490 ₽ →
          </Link>
        </div>

        <div style={{ marginTop: 32, paddingTop: 20, borderTop: "1px solid var(--border)" }}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 10 }}>Читайте также</div>
          <RelatedLinks />
        </div>
      </article>

      <style>{`
        .article-body h2 {
          font-size: 22px; font-weight: 700; margin-top: 28px; margin-bottom: 12px;
        }
        .article-body h3 {
          font-size: 17px; font-weight: 600; margin-top: 18px; margin-bottom: 8px;
        }
        .article-body p { margin-bottom: 14px; }
        .article-body ul, .article-body ol {
          margin: 12px 0 14px 22px;
        }
        .article-body li { margin-bottom: 6px; }
        .article-body strong { color: var(--text-1); font-weight: 700; }
        .article-body code {
          background: var(--surface-2); padding: 1px 6px; border-radius: 3px;
          font-size: 13px; font-family: 'JetBrains Mono', monospace;
        }
        .article-body blockquote {
          border-left: 3px solid var(--primary);
          padding: 8px 14px; margin: 14px 0;
          background: var(--surface-2); border-radius: 4px;
          color: var(--text-2); font-size: 14px;
        }
        .article-body .callout {
          background: var(--surface-2); border-radius: 8px;
          padding: 14px 16px; margin: 16px 0;
          border-left: 3px solid var(--primary);
          font-size: 14px;
        }
        .article-body .callout strong { display: block; margin-bottom: 4px; }
      `}</style>
    </div>
  );
}

function RelatedLinks() {
  const items = [
    { href: "/blog/dokumentaciya-lota-torgi-gov", title: "Как читать документацию лота torgi.gov.ru" },
    { href: "/blog/statya-39-18-zk-rf-praktika", title: "Ст. 39.18 ЗК РФ: получить землю без торгов" },
    { href: "/blog/oshibki-pri-vykupe-kfh", title: "5 ошибок при выкупе земель К(Ф)Х" },
  ];
  return (
    <div style={{ display: "grid", gap: 6 }}>
      {items.map((it) => (
        <Link key={it.href} href={it.href} style={{
          color: "var(--primary)", textDecoration: "none", fontSize: 14,
        }}>
          → {it.title}
        </Link>
      ))}
    </div>
  );
}
