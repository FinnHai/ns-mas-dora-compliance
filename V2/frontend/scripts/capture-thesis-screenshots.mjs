/**
 * Erzeugt PNGs für die BA (KG-Auditor-Tabelle, Human-Review-Gate).
 * Voraussetzung: Vite-Dev-Server läuft (npm run dev), Port 5173.
 * Nutzt die statische Fixture ?fixture=thesis-s2-hitl (kein Backend nötig).
 *
 * Ausführung: npx playwright install chromium (einmalig)
 *             npm run capture-thesis-screenshots
 */
import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const thesisFigures = path.resolve(__dirname, '../../../Projekt Latex BA/figures');
const baseUrl = process.env.THESIS_SCREENSHOT_URL ?? 'http://localhost:5173/ns-mas?fixture=thesis-s2-hitl';

async function main() {
  fs.mkdirSync(thesisFigures, { recursive: true });

  const browser = await chromium.launch();
  const page = await browser.newPage({
    viewport: { width: 1280, height: 900 },
    deviceScaleFactor: 2,
  });

  try {
    await page.goto(baseUrl, { waitUntil: 'networkidle', timeout: 60_000 });
    await page.waitForSelector('[data-screenshot="kg-auditor"]', { timeout: 30_000 });

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
