import Link from "next/link";
import { SOCIAL_LINKS, CONTACT_EMAIL } from "@/lib/social";

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
          <Link href="/obuchenie">Обучение</Link>
          <Link href="/blog">Блог</Link>
          <Link href="/zemelnye-torgi">Торги по регионам</Link>
          <Link href="/checklist">Чеклист 12 проверок</Link>
          <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>
        </div>
      </div>
      <div className="site-footer-inner site-footer-social">
        <span className="site-footer-social-label">Мы в соцсетях:</span>
        {SOCIAL_LINKS.map((s) => (
          <a key={s.name} href={s.url} target="_blank" rel="me noopener noreferrer">
            {s.name}
          </a>
        ))}
      </div>
    </footer>
  );
}
