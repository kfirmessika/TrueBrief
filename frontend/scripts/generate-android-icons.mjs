// Stamp the TrueBrief brand icon into the Capacitor Android project
// (all mipmap densities + adaptive foreground + splash background color).
// Run: node scripts/generate-android-icons.mjs   (from frontend/)
import sharp from 'sharp';
import { writeFileSync, existsSync } from 'fs';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const res = join(dirname(fileURLToPath(import.meta.url)), '..', 'android', 'app', 'src', 'main', 'res');
if (!existsSync(res)) {
  console.error('android project not found — run `npx cap add android` first');
  process.exit(1);
}

const BRAND = '#4B52E2';
const bolt = (pad, bg = BRAND, rounded = true) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
  ${bg ? `<rect width="24" height="24" rx="${rounded ? 5.2 : 0}" fill="${bg}"/>` : ''}
  <g transform="translate(${12 - 12 * pad}, ${12 - 12 * pad}) scale(${pad})">
    <path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z" fill="#ffffff" transform="translate(0.5,0)"/>
  </g>
</svg>`;

// Legacy launcher icons (full-bleed rounded square)
const legacy = { 'mipmap-mdpi': 48, 'mipmap-hdpi': 72, 'mipmap-xhdpi': 96, 'mipmap-xxhdpi': 144, 'mipmap-xxxhdpi': 192 };
// Adaptive foreground: 108dp canvas, artwork inside the middle ~66dp safe zone
const adaptive = { 'mipmap-mdpi': 108, 'mipmap-hdpi': 162, 'mipmap-xhdpi': 216, 'mipmap-xxhdpi': 324, 'mipmap-xxxhdpi': 432 };

for (const [dir, size] of Object.entries(legacy)) {
  await sharp(Buffer.from(bolt(0.72))).resize(size, size).png().toFile(join(res, dir, 'ic_launcher.png'));
  await sharp(Buffer.from(bolt(0.72))).resize(size, size).png().toFile(join(res, dir, 'ic_launcher_round.png'));
}
for (const [dir, size] of Object.entries(adaptive)) {
  // transparent background — the adaptive <background> layer supplies the color
  await sharp(Buffer.from(bolt(0.38, null))).resize(size, size).png().toFile(join(res, dir, 'ic_launcher_foreground.png'));
}

// Adaptive background + splash color = brand
writeFileSync(join(res, 'values', 'ic_launcher_background.xml'),
  `<?xml version="1.0" encoding="utf-8"?>\n<resources>\n    <color name="ic_launcher_background">${BRAND}</color>\n</resources>\n`);

console.log('Android icons stamped (legacy + adaptive + background color).');
