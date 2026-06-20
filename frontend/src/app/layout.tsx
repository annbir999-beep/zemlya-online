import type { Metadata } from "next";
import "./globals.css";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import UtmCapture from "@/components/UtmCapture";
import HeroBar from "@/components/HeroBar";

export const metadata: Metadata = {
  metadataBase: new URL("https://torgi-zemli.ru"),
  title: "Торги Земли — агрегатор земельных аукционов",
  description: "Найдите земельный участок на аукционе по всей России. Карта, фильтры, AI-оценка, алерты.",
  icons: { icon: "/favicon.svg" },
  // Подтверждение владения для поисковиков (мета-тег в <head>)
  verification: {
    yandex: "4fbf65c871dcd342",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body>
        <div className="app-layout">
          <UtmCapture />
          <HeroBar />
          <Header />
          <main className="main-content">{children}</main>
          <Footer />
        </div>
      </body>
    </html>
  );
}
