const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: process.env.BROWSER_EXECUTABLE || undefined });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1500 }, offline: true });
    const errors = [], network = [];
    page.on('pageerror', e => errors.push(String(e)));
    page.on('request', r => { if (/^https?:/.test(r.url())) network.push(r.url()); });
    await page.goto(pathToFileURL(path.resolve(process.argv[2])).href);
    await page.evaluate(() => document.fonts.ready);
    await page.locator('#zoom-fit').click();
    assert.equal(await page.locator('.node').count(), 11);
    assert.equal(await page.locator('#edges>path').count(), 12);
    assert.equal(await page.locator('[data-tab],#next,#review').count(), 0);
    const fit = await page.evaluate(() => {
      const v = document.getElementById('viewport').getBoundingClientRect();
      return [...document.querySelectorAll('.node')].every(n => {
        const r = n.getBoundingClientRect();
        return r.left >= v.left && r.right <= v.right && r.top >= v.top && r.bottom <= v.bottom;
      });
    });
    assert(fit, 'All damage nodes must fit in the canvas');
    if (process.argv[3]) {
      fs.mkdirSync(process.argv[3], { recursive: true });
      await page.locator('#diagram').screenshot({ path: path.join(process.argv[3], 'damage-flow.png') });
    }
    await page.locator('#zoom-reset').click();
    const collisions = await page.evaluate(() => {
      const hits = [];
      for (const e of document.querySelectorAll('#edges>path')) {
        for (let i = 3; i < e.getTotalLength() - 3; i += 4) {
          const p = e.getPointAtLength(i).matrixTransform(e.getScreenCTM());
          for (const n of document.querySelectorAll('.node')) {
            if (n.id === e.dataset.from || n.id === e.dataset.to) continue;
            const r = n.getBoundingClientRect();
            if (p.x > r.left + 1 && p.x < r.right - 1 && p.y > r.top + 1 && p.y < r.bottom - 1) hits.push(n.id);
          }
        }
      }
      return hits;
    });
    assert.deepEqual(collisions, []);
    await page.locator('#search').fill('固定值');
    assert.notEqual(await page.locator('#search-count').textContent(), '0/0');
    await page.locator('#fixed-value').click();
    assert(await page.locator('#detail').isVisible());
    assert((await page.locator('#detail-text').textContent()).includes('1600+500'));
    await page.locator('#detail details summary').click();
    assert((await page.locator('#source').textContent()).includes('非项目代码摘录'));
    if (process.argv[3]) await page.locator('#detail').screenshot({ path: path.join(process.argv[3], 'damage-detail.png') });
    await page.locator('.close').click();
    await page.locator('a[href="#examples"]').click();
    assert.equal(await page.locator('.example').count(), 3);
    await page.locator('.example summary').first().click();
    assert((await page.locator('.example').first().textContent()).includes('1500'));
    await page.setViewportSize({ width: 390, height: 844 });
    await page.locator('a[href="#diagram"]').click();
    await page.locator('#zoom-fit').click();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    assert.deepEqual(errors, []);
    assert.deepEqual(network, []);
    console.log('PASS: sanitized damage example, complete canvas, routes, details, examples, offline, mobile.');
  } finally {
    await browser.close();
  }
})().catch(e => { console.error(e); process.exit(1); });
