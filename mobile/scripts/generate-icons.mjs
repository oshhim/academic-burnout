// Regenerates the app icon PNGs from the vector mark in src/brand/logo.ts.
// Run from mobile/:  npx tsx scripts/generate-icons.mjs
// Uses a locally installed Google Chrome (puppeteer-core) to rasterise the SVG.
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import puppeteer from 'puppeteer-core';

import { appIconSvg, auroraSvg, glassMarkSvg, markSvg } from '../src/brand/logo.ts';

const CHROME = process.env.CHROME_PATH ?? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
if (!existsSync(CHROME)) throw new Error(`Chrome not found at ${CHROME}; set CHROME_PATH.`);
const OUT = fileURLToPath(new URL('../assets/images/', import.meta.url));

const assets = [
  // iOS / general: full-bleed square (the OS rounds the corners).
  ['icon.png', 1024, appIconSvg({ scale: 0.64 })],
  // Android adaptive icon layers; the mark stays inside the 66% safe zone.
  ['android-icon-background.png', 512, auroraSvg()],
  ['android-icon-foreground.png', 512, glassMarkSvg({ scale: 0.5 })],
  ['android-icon-monochrome.png', 512, markSvg('#FFFFFF', { scale: 0.5 })],
  // Splash: glass mark on the dark splash background colour from app.json.
  ['splash-icon.png', 512, glassMarkSvg({ scale: 0.96 })],
  ['favicon.png', 48, appIconSvg({ radius: 22, scale: 0.7 })],
  // Rounded app icon for the READMEs (GitHub can't round images itself).
  ['../../docs/logo.png', 256, appIconSvg({ radius: 22, scale: 0.64 })],
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
await browser.close();
