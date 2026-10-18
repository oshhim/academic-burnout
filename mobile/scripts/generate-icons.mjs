// Regenerates the app icon PNGs from the vector mark in src/brand/logo.ts.
// Run from mobile/:  npx tsx scripts/generate-icons.mjs
// Uses a locally installed Google Chrome (puppeteer-core) to rasterise the SVG.
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import puppeteer from 'puppeteer-core';

import { gradientMarkSvg, markSvg, tileSvg } from '../src/brand/logo.ts';

const CHROME = process.env.CHROME_PATH ?? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
if (!existsSync(CHROME)) throw new Error(`Chrome not found at ${CHROME}; set CHROME_PATH.`);
const OUT = fileURLToPath(new URL('../assets/images/', import.meta.url));
const GRADIENT = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#6366F1"/><stop offset="1" stop-color="#A855F7"/></linearGradient></defs><rect width="100" height="100" fill="url(#g)"/></svg>`;

const assets = [
  // iOS / general: full-bleed square (the OS rounds the corners).
  ['icon.png', 1024, tileSvg({ radius: 0, scale: 0.62 })],
  // Android adaptive icon layers; the mark stays inside the 66% safe zone.
  ['android-icon-background.png', 512, GRADIENT],
  ['android-icon-foreground.png', 512, markSvg('#FFFFFF', { scale: 0.5 })],
  ['android-icon-monochrome.png', 512, markSvg('#FFFFFF', { scale: 0.5 })],
  // Splash: lavender mark on the dark splash background colour from app.json.
  ['splash-icon.png', 512, markSvg('#C0C1FF', { scale: 1 })],
  ['favicon.png', 48, tileSvg({ radius: 22, scale: 0.74 })],
  // Transparent gradient mark for the READMEs (works on light and dark GitHub themes).
  ['../../docs/logo.png', 256, gradientMarkSvg({ scale: 1.12 })],
];

const browser = await puppeteer.launch({ executablePath: CHROME, headless: true });
const page = await browser.newPage();
for (const [name, size, svg] of assets) {
  await page.setViewport({ width: size, height: size, deviceScaleFactor: 1 });
  const sized = svg.replace(/<svg([^>]*?)(\swidth="[^"]*")?(\sheight="[^"]*")?(\s|>)/, `<svg$1 width="${size}" height="${size}"$4`);
  await page.setContent(`<html><body style="margin:0;background:transparent">${sized}</body></html>`);
  await page.screenshot({ path: OUT + name, omitBackground: true, clip: { x: 0, y: 0, width: size, height: size } });
  console.log(`wrote ${name.startsWith('../') ? name.replace('../../', '') : 'assets/images/' + name} (${size}px)`);
}
// README wordmark: logo and "EMPath+" aligned inside one image (GitHub strips image
// alignment attributes). Gradient text reads on both light and dark GitHub themes,
// so no theme switching is needed.
await page.setViewport({ width: 600, height: 200, deviceScaleFactor: 2 });
await page.setContent(`<html><body style="margin:0;background:transparent">
  <div id="w" style="display:inline-flex;align-items:center;gap:14px;padding:8px 6px">
    ${gradientMarkSvg({ size: 64, scale: 1.12 })}
    <span style="font:800 46px/1.15 -apple-system,'Segoe UI',Helvetica,Arial,sans-serif;letter-spacing:-0.5px;
      background:linear-gradient(135deg,#6366F1,#A855F7);-webkit-background-clip:text;background-clip:text;color:transparent">EMPath+</span>
  </div></body></html>`);
const box = await (await page.$('#w')).boundingBox();
await page.screenshot({ path: OUT + '../../docs/wordmark.png', omitBackground: true, clip: box });
console.log(`wrote docs/wordmark.png (${Math.round(box.width * 2)}x${Math.round(box.height * 2)}px)`);
await browser.close();
