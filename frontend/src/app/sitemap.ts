import type { MetadataRoute } from "next";

const SITE = "https://torgi-zemli.ru";
const BACKEND_URL = process.env.BACKEND_URL || "http://backend:8000";

// Генерим на запрос, а не на билде: при сборке контейнер не видит backend,
// и регионы/блог не попали бы в карту. Краулеры дёргают sitemap редко.
export const dynamic = "force-dynamic";

async function safeGet(path: string): Promise<{ items?: unknown[] } | null> {
  try {
    const r = await fetch(`${BACKEND_URL}${path}`, { next: { revalidate: 3600 } });
    if (!r.ok) return null;
    return await r.json();
  } catch {
    return null;
  }
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const now = new Date();

  const staticRoutes = [
    "", "/lots", "/zemelnye-torgi", "/blog", "/checklist",
    "/pricing", "/faq", "/strategies", "/ai-picks", "/analytics",
  ].map((p) => ({ url: `${SITE}${p}`, lastModified: now, changeFrequency: "daily" as const, priority: p === "" ? 1 : 0.7 }));

  const regionsData = await safeGet("/api/seo/regions");
  const regions = (regionsData?.items || []).map((r) => {
    const it = r as { slug: string };
    return { url: `${SITE}/zemelnye-torgi/${it.slug}`, lastModified: now, changeFrequency: "daily" as const, priority: 0.6 };
  });

  const blogData = await safeGet("/api/blog?per_page=100");
  const posts = (blogData?.items || []).map((p) => {
    const it = p as { slug: string };
    return { url: `${SITE}/blog/${it.slug}`, lastModified: now, changeFrequency: "weekly" as const, priority: 0.6 };
  });

  return [...staticRoutes, ...regions, ...posts];
}
