import Link from "next/link";

export default function Footer() {
  return (
    <footer className="site-footer">
      <div className="site-footer-inner">
        <div className="site-footer-copy">
          © 2026 Торги Земли · ИП Бирюкова А.И. · ИНН 753611302731
        </div>
        <div className="site-footer-links">
          <Link href="/faq">FAQ и контакты</Link>
          <Link href="/oferta">Публичная оферта</Link>
          <Link href="/privacy">Политика конфиденциальности</Link>
          <Link href="/blog">Блог</Link>
          <Link href="/zemelnye-torgi">Торги по регионам</Link>
          <Link href="/checklist">Чеклист 12 проверок</Link>
          <a href="mailto:info@torgi-zemli.ru">info@torgi-zemli.ru</a>
        </div>
      </div>
    </footer>
  );
}
