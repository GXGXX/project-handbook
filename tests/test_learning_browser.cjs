// Real-browser smoke test, including a moved standalone file with networking disabled.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { pathToFileURL } = require('url');
const assert = require('assert');

(async () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'learning-portable-'));
  const portable = path.join(tmp, 'renamed.html');
  fs.copyFileSync(process.argv[2], portable);
  const browser = await chromium.launch({ headless: true, executablePath: process.env.BROWSER_EXECUTABLE || undefined });
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, offline: true });
    const page = await context.newPage();
    const errors = [], requests = [];
    page.on('pageerror', error => errors.push(String(error)));
    page.on('request', req => { if (/^https?:/.test(req.url())) requests.push(req.url()); });
    await page.goto(pathToFileURL(portable).href);
    const count = await page.locator('[data-step]').count();
    assert(count >= 1);
    await page.locator('#guide-start').click();
    assert.equal(await page.locator('.walk-step.active').count(), 1);
    assert.equal(await page.locator('.component.active').count(), 1);
    assert.equal(await page.locator('#guide-progress').textContent(), '1 / ' + count);
    assert(await page.locator('#guide-prev').isDisabled());
    for (let i = 1; i < count; i++) await page.locator('#guide-next').click();
    assert(await page.locator('#guide-next').isDisabled());
    await page.locator('#guide-prev').click();
    await page.locator('#guide-reset').click();
    assert.equal(await page.locator('.walk-step.active').count(), 0);
    await page.locator('#learning-search').fill('unlock_level');
    assert(await page.locator('#search-results a').count() > 0);
    await page.locator('#search-results a').first().click();
    await page.locator('#learning-search').fill('no-such-term-0000');
    assert((await page.locator('#search-status').textContent()).includes('没有匹配'));
    await page.locator('#learning-search').fill('');
    assert(await page.locator('#search-results').isHidden());
    const reference = page.locator('#answer a[href^="#evidence-"]').first();
    const target = await reference.getAttribute('href');
    await reference.click();
    assert(await page.locator(target).evaluate(el => el.open));
    await page.locator(target + ' [data-evidence-back]').click();
    assert(await reference.evaluate(el => el === document.activeElement));
    await page.locator('.example summary').first().click();
    await page.locator('.example[open] a[href^="#step-"]').first().click();
    assert.equal(await page.locator('.walk-step.active').count(), 1);
    await page.locator('#theme-toggle').click();
    assert.equal(await page.locator('html').getAttribute('data-theme'), 'dark');
    await page.locator('#theme-toggle').click();
    await page.goto(pathToFileURL(portable).href + '#evidence-rules');
    assert(await page.locator('#evidence-rules').evaluate(el => el.open));
    if (process.env.SCREENSHOT_DIR) {
      fs.mkdirSync(process.env.SCREENSHOT_DIR, { recursive: true });
      await page.goto(pathToFileURL(portable).href);
      await page.screenshot({ path: path.join(process.env.SCREENSHOT_DIR, 'desktop.png'), fullPage: false });
      await page.locator('#overview').scrollIntoViewIfNeeded();
      await page.screenshot({ path: path.join(process.env.SCREENSHOT_DIR, 'overview.png') });
    }
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(pathToFileURL(portable).href);
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'mobile overflow');
    await page.locator('#guide-start').click();
    assert.equal(await page.locator('.walk-step.active').count(), 1);
    if (process.env.SCREENSHOT_DIR) await page.screenshot({ path: path.join(process.env.SCREENSHOT_DIR, 'mobile.png') });
    assert.deepEqual(errors, []);
    assert.deepEqual(requests, []);
    console.log('PASS: standalone offline, guide, deep links, evidence return, examples, alias search, theme, mobile, no browser errors');
  } finally {
    await browser.close();
    // Leave only a tiny moved fixture in the system temp directory; no source files touched.
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
