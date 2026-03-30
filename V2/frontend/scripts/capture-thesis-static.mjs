/**
 * Screenshots ohne laufenden Dev-Server: statische HTML mit gleichen CSS-Variablen.
 * node scripts/capture-thesis-static.mjs
 */
import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';
import os from 'os';
import { fileURLToPath, pathToFileURL } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const htmlPath = path.join(__dirname, 'thesis-screenshot-static.html');
const thesisFigures = path.resolve(__dirname, '../../../Projekt Latex BA/figures');
const fileUrl = pathToFileURL(htmlPath).href;

function playwrightChromiumPath() {
  const base = path.join(os.homedir(), 'Library/Caches/ms-playwright');
  if (!fs.existsSync(base)) return undefined;
  const dirs = fs.readdirSync(base).filter((d) => d.startsWith('chromium-'));
  if (dirs.length === 0) return undefined;
  dirs.sort();
  const latest = dirs[dirs.length - 1];
  const mac = path.join(base, latest, 'chrome-mac-arm64', 'Google Chrome for Testing.app', 'Contents', 'MacOS', 'Google Chrome for Testing');
  if (fs.existsSync(mac)) return mac;
  const macX64 = path.join(base, latest, 'chrome-mac', 'Google Chrome for Testing.app', 'Contents', 'MacOS', 'Google Chrome for Testing');
  return fs.existsSync(macX64) ? macX64 : undefined;
}

async function main() {
  if (!fs.existsSync(htmlPath)) {
    throw new Error('Fehlt: ' + htmlPath);
  }
  fs.mkdirSync(thesisFigures, { recursive: true });

  const exe = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || playwrightChromiumPath();
  const browser = await chromium.launch(
    exe ? { executablePath: exe, headless: true } : { headless: true }
  );
  const page = await browser.newPage({
    viewport: { width: 1280, height: 1200 },
    deviceScaleFactor: 2,
  });

  try {
    await page.goto(fileUrl, { waitUntil: 'load', timeout: 30_000 });
    await page.waitForSelector('[data-screenshot="kg-auditor"]', { timeout: 15_000 });

    const outValidation = path.join(thesisFigures, 'screenshot_validierung.png');
    await page.locator('[data-screenshot="kg-auditor"]').screenshot({ path: outValidation });
    console.log('OK:', outValidation);

    await page.locator('[data-screenshot="hitl-review"]').scrollIntoViewIfNeeded();

    const clip = await page.evaluate(() => {
      const top = document.querySelector('[data-screenshot="hitl-review"]');
      const bot = document.querySelector('[data-screenshot="hitl-actions"]');
      if (!top || !bot) return null;
      const r1 = top.getBoundingClientRect();
      const r2 = bot.getBoundingClientRect();
      const pad = 12;
      const left = Math.min(r1.left, r2.left) - pad;
      const topY = Math.min(r1.top, r2.top) - pad;
      const right = Math.max(r1.right, r2.right) + pad;
      const bottom = Math.max(r1.bottom, r2.bottom) + pad;
      return {
        x: Math.max(0, Math.floor(left)),
        y: Math.max(0, Math.floor(topY)),
        width: Math.ceil(right - left),
        height: Math.ceil(bottom - topY),
      };
    });

    if (!clip || clip.width < 50 || clip.height < 50) {
      throw new Error('Konnte Clip für Human-Review-Screenshot nicht berechnen.');
    }

    const outHitl = path.join(thesisFigures, 'screenshot_human_review.png');
    await page.screenshot({ path: outHitl, clip });
    console.log('OK:', outHitl);
  } finally {
    await browser.close();
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
