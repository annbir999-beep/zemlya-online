import Link from "next/link";

export default function Footer() {
  return (
    <footer style={{
      borderTop: "1px solid var(--border)",
      padding: "20px 24px",
      background: "var(--surface)",
      fontSize: 12,
      color: "var(--text-3)",
      lineHeight: 1.6,
    }}>
      <div style={{
        maxWidth: 1280, margin: "0 auto",
        display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 16,
      }}>
        <div>
          © 2026 Земля.ОНЛАЙН · ИП Бирюкова А.И. · ИНН 753611302731
        </div>
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
          <Link href="/oferta" style={{ color: "var(--text-3)", textDecoration: "none" }}>
            Публичная оферта
          </Link>
          <Link href="/privacy" style={{ color: "var(--text-3)", textDecoration: "none" }}>
            Политика конфиденциальности
          </Link>
          <Link href="/blog" style={{ color: "var(--text-3)", textDecoration: "none" }}>
            Блог
          </Link>
          <a href="mailto:anna@xn--e1adnd0h.online" style={{ color: "var(--text-3)", textDecoration: "none" }}>
            anna@земля.online
          </a>
        </div>
      </div>
    </footer>
  );
}
