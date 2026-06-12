// Sentry в браузере (ошибки клиентских компонентов, фетчей, рендера).
// Файл подхватывается Next 15.3+ нативно, без webpack-плагина Sentry.
import * as Sentry from "@sentry/nextjs";

const SENTRY_DSN = "https://2422e7bca6ae16fa7bce96de65dc5a26@o4511554564063232.ingest.de.sentry.io/4511554591588432";

if (process.env.NODE_ENV === "production") {
  Sentry.init({
    dsn: SENTRY_DSN,
    environment: "production",
    tracesSampleRate: 0.05,
    sendDefaultPii: false,
  });
}

export const onRouterTransitionStart = Sentry.captureRouterTransitionStart;
