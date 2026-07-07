/**
 * Merge Tailwind class names, filtering falsy values.
 * Lightweight alternative to clsx + tailwind-merge for our use case.
 */
export function cn(...classes: (string | undefined | null | false)[]): string {
  return classes.filter(Boolean).join(' ');
}

/**
 * Return the URL only if it uses a safe scheme (http/https), otherwise a
 * harmless fallback. Source URLs come from scraped web pages, so a malicious
 * page could plant `javascript:`/`data:` hrefs that React does NOT sanitize in
 * a raw <a href>. Use this everywhere a scraped/user-derived URL becomes an href.
 */
export function safeHref(url: string | null | undefined, fallback = '#'): string {
  if (!url) return fallback;
  const trimmed = url.trim();
  // Allow only absolute http(s). Reject javascript:, data:, vbscript:, blob:, etc.
  return /^https?:\/\//i.test(trimmed) ? trimmed : fallback;
}
