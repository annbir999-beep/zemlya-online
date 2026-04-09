import type { Metadata } from "next";
import "./globals.css";
import Header from "@/components/Header";

export const metadata: Metadata = {
  title: "Земля.ПРО — агрегатор земельных аукционов",
  description: "Найдите земельный участок на аукционе по всей России. Карта, фильтры, AI-оценка, алерты.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body>
        <div className="app-layout">
          <Header />
          <main className="main-content">{children}</main>
        </div>
      </body>
    </html>
  );
}
