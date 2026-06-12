import { notFound } from "next/navigation";
import ArticleLayout from "@/components/ArticleLayout";

export const revalidate = 300;

const BACKEND_URL = process.env.BACKEND_URL || "http://backend:8000";

type Post = {
  slug: string;
  title: string;
  excerpt: string | null;
  body_html: string;
  reading_minutes: number | null;
  published_at: string | null;
};

async function fetchPost(slug: string): Promise<Post | null> {
  try {
    const res = await fetch(`${BACKEND_URL}/api/blog/${encodeURIComponent(slug)}`, {
      next: { revalidate: 300 },
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const post = await fetchPost(slug);
  if (!post) return { title: "Статья не найдена — Земля.ОНЛАЙН" };
  return {
    title: `${post.title} — Земля.ОНЛАЙН`,
    description: post.excerpt || undefined,
  };
}

export default async function Page({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const post = await fetchPost(slug);
  if (!post) notFound();

  return (
    <ArticleLayout
      title={post.title}
      date={post.published_at ? post.published_at.slice(0, 10) : ""}
      minutes={post.reading_minutes || 5}
      description={post.excerpt || ""}
    >
      {/* HTML генерируется бэкендом из markdown статьи, прошедшей ручное одобрение */}
      <div dangerouslySetInnerHTML={{ __html: post.body_html }} />
    </ArticleLayout>
  );
}
