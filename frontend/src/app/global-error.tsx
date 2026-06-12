"use client";

// Глобальный обработчик ошибок App Router: рендерится вместо корневого layout
// при падении рендера, поэтому содержит собственные <html>/<body>.
import * as Sentry from "@sentry/nextjs";
import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return (
    <html lang="ru">
      <body style={{ fontFamily: "system-ui, sans-serif", padding: 40, textAlign: "center" }}>
        <h2>Что-то пошло не так</h2>
        <p style={{ color: "#666" }}>Ошибка уже отправлена разработчикам.</p>
        <button
          onClick={() => reset()}
          style={{ marginTop: 16, padding: "8px 20px", cursor: "pointer" }}
        >
          Попробовать снова
        </button>
      </body>
    </html>
  );
}
