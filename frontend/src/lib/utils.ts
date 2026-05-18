/**
 * Merge Tailwind class names, filtering falsy values.
 * Lightweight alternative to clsx + tailwind-merge for our use case.
 */
export function cn(...classes: (string | undefined | null | false)[]): string {
  return classes.filter(Boolean).join(' ');
}
