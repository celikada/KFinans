// Generates PWA icons from the KFinans brand logo.
//
// Source: public/images/kfinans-logo.png (1254x1254, white background, navy "K" monogram).
// Output: public/icons/{icon-192,icon-512,maskable-512,apple-touch-icon-180}.png
//
// Re-run with:  node scripts/generate-pwa-icons.mjs
//
// The brand logo already sits on a white field, so the regular (non-maskable)
// icons use it as-is. The maskable icon adds extra safe-zone padding (logo at
// ~72% of the canvas) on a solid white background so platform masks (circle /
// squircle) never clip the monogram.

import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { mkdir } from "node:fs/promises";
import sharp from "sharp";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");
const source = join(root, "public", "images", "kfinans-logo.png");
const outDir = join(root, "public", "icons");

// White matches the logo's own background for a seamless look.
const BACKGROUND = { r: 255, g: 255, b: 255, alpha: 1 };

async function renderPlain(size, outFile) {
  await sharp(source)
    .resize(size, size, { fit: "contain", background: BACKGROUND })
    .flatten({ background: BACKGROUND })
    .png()
    .toFile(join(outDir, outFile));
}

async function renderMaskable(size, outFile) {
  // Safe zone: keep the logo within the inner ~72% so masks never clip it.
  const inner = Math.round(size * 0.72);
  const logo = await sharp(source)
    .resize(inner, inner, { fit: "contain", background: BACKGROUND })
    .flatten({ background: BACKGROUND })
    .toBuffer();

  await sharp({
    create: {
      width: size,
      height: size,
      channels: 4,
      background: BACKGROUND,
    },
  })
    .composite([{ input: logo, gravity: "center" }])
    .png()
    .toFile(join(outDir, outFile));
}

async function main() {
  await mkdir(outDir, { recursive: true });
  await renderPlain(192, "icon-192.png");
  await renderPlain(512, "icon-512.png");
  await renderPlain(180, "apple-touch-icon-180.png");
  await renderMaskable(512, "maskable-512.png");
  console.log("PWA icons written to public/icons/");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
