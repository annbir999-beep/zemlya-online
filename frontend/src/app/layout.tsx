import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";

// Manrope (variable, latin+cyrillic) — self-hosted, чтобы билд не зависел от Google Fonts
const manrope = localFont({
  src: "../fonts/Manrope-Variable.ttf",
  weight: "200 800",
  display: "swap",
  variable: "--font-sans",
});
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
    google: "4yVGqOhtVT0NwKeg5Umj3cx3hVd95POKTFKKqi83VcE",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru" className={manrope.variable}>
      <body className={manrope.className}>
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
