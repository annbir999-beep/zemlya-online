/**
 * Официальные аккаунты «Торги Земли» — единый источник правды.
 *
 * Используется в футере (ссылки) и в schema.org Organization → sameAs (layout.tsx):
 * связка sameAs нужна поисковикам, чтобы склеить сайт с профилями в соцсетях.
 * Список сверен с подключёнными аккаунтами в Postmypost (проект 351004).
 */
export const SOCIAL_LINKS: { name: string; url: string }[] = [
  { name: "Telegram", url: "https://t.me/torgi_zemli" },
  { name: "VK", url: "https://vk.com/public240105342" },
  { name: "YouTube", url: "https://youtube.com/channel/UCej045eSV8VJjK6Om9XXWzA" },
  { name: "Instagram", url: "https://instagram.com/torgi.zemli" },
  { name: "Одноклассники", url: "https://ok.ru/group/70000053744179" },
  { name: "Rutube", url: "https://rutube.ru/channel/79750749/" },
  { name: "TikTok", url: "https://tiktok.com/@torgi.zemli" },
  { name: "Max", url: "https://max.ru/id753611302731_biz" },
];

export const CONTACT_EMAIL = "info@torgi-zemli.ru";
export const CONTACT_TELEGRAM = "https://t.me/torgi_zemli";
