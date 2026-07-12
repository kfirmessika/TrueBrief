// Generate all PWA / mobile icons from one inline SVG using sharp.
// Run: node scripts/generate-icons.mjs   (from frontend/)
import sharp from 'sharp';
import { mkdirSync } from 'fs';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..', 'public');
mkdirSync(root, { recursive: true });

// Brand mark: lucide "zap" bolt, white on the landing-page brand color.
// viewBox 24; bolt path from lucide. Padding via nested transform.
const icon = (bg, pad) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
  <rect width="24" height="24" rx="5.2" fill="${bg}"/>
  <g transform="translate(${12 - 12 * pad}, ${12 - 12 * pad}) scale(${pad})">
    <path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z" fill="#ffffff" transform="translate(0.5,0)"/>
  </g>
</svg>`;

// oklch(0.55 0.22 264) ≈ #4B52E2 (landing brand); solid hex for max compatibility.
const BRAND = '#4B52E2';

const jobs = [
  // [file, size, padScale, background]
  ['icon-192.png', 192, 0.72, BRAND],
  ['icon-512.png', 512, 0.72, BRAND],
  // maskable: safe zone = inner 80% — shrink the mark further.
  ['icon-512-maskable.png', 512, 0.55, BRAND],
  ['apple-touch-icon.png', 180, 0.72, BRAND],
  ['badge-72.png', 72, 0.9, '#000000'], // Android notification badge: white-on-transparent preferred; keep simple solid
];

for (const [file, size, pad, bg] of jobs) {
  const svg = icon(bg, pad);
  await sharp(Buffer.from(svg)).resize(size, size).png().toFile(join(root, file));
  console.log('wrote', file, `${size}x${size}`);
}
console.log('done');
