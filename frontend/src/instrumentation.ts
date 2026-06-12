// Sentry на серверной стороне Next.js (SSR, route handlers, server components).
// DSN захардкожен сознательно: он публичный по дизайну (уходит и в браузерный
// бандл), а build args в Docker усложнили бы сборку без выигрыша в безопасности.
import * as Sentry from "@sentry/nextjs";

const SENTRY_DSN = "https://2422e7bca6ae16fa7bce96de65dc5a26@o4511554564063232.ingest.de.sentry.io/4511554591588432";

export async function register() {
  if (process.env.NODE_ENV !== "production") return;
  if (process.env.NEXT_RUNTIME === "nodejs") {
    Sentry.init({
      dsn: SENTRY_DSN,
      environment: "production",
      tracesSampleRate: 0.05,
      sendDefaultPii: false,
    });
  }
}

export const onRequestError = Sentry.captureRequestError;
