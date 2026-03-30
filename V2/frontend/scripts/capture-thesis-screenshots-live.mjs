/**
 * Screenshots aus einem echten Pipeline-Lauf (FastAPI + Neo4j + LLM).
 * Voraussetzungen: Vite auf 5173, Backend auf 8000 (Proxy), funktionierende .env.
 *
 * npm run capture-thesis-screenshots:live
 */
import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const thesisFigures = path.resolve(__dirname, '../../../Projekt Latex BA/figures');
const frontUrl = process.env.THESIS_LIVE_URL ?? 'http://localhost:5173/ns-mas';
const pipelineTimeoutMs = Number(process.env.THESIS_PIPELINE_TIMEOUT_MS ?? 720_000);

async function captureClip(page, thesisFigures) {
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
}

async function main() {
  fs.mkdirSync(thesisFigures, { recursive: true });

  const browser = await chromium.launch();
  const page = await browser.newPage({
    viewport: { width: 1280, height: 900 },
    deviceScaleFactor: 2,
  });

  try {
    await page.goto(frontUrl, { waitUntil: 'networkidle', timeout: 60_000 });
    await page.getByRole('button', { name: 'Eval S2 (Bundesbank / Lazarus)' }).click();
    await page.getByRole('button', { name: 'Pipeline starten' }).click();

    console.log('Warte auf Human Review (echter Pipeline-Lauf, bis zu', Math.round(pipelineTimeoutMs / 60_000), 'Min)…');
    await page.waitForSelector('[data-screenshot="kg-auditor"]', { timeout: pipelineTimeoutMs });

    const outValidation = path.join(thesisFigures, 'screenshot_validierung.png');
    await page.locator('[data-screenshot="kg-auditor"]').screenshot({ path: outValidation });
    console.log('OK:', outValidation);

    await captureClip(page, thesisFigures);
  } finally {
    await browser.close();
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
