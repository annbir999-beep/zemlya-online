import type { Metadata } from "next";
import "./globals.css";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import UtmCapture from "@/components/UtmCapture";

export const metadata: Metadata = {
  title: "Земля.ОНЛАЙН — агрегатор земельных аукционов",
  description: "Найдите земельный участок на аукционе по всей России. Карта, фильтры, AI-оценка, алерты.",
  icons: { icon: "/favicon.svg" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body>
        <div className="app-layout">
          <UtmCapture />
          <Header />
          <main className="main-content">{children}</main>
          <Footer />
        </div>
      </body>
    </html>
  );
}
