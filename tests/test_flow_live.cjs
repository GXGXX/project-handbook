// Explicit opt-in smoke test: uses the local Codex model on the sanitized damage demo.
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');

(async () => {
  const url = process.env.FLOW_LIVE_URL;
  if (!url || !/^http:\/\/127\.0\.0\.1:\d+$/.test(url)) throw new Error('Set FLOW_LIVE_URL to the sanitized demo connection for this opt-in model test.');
  const output = path.resolve(process.argv[2] || 'dist/live-qa-check');
  fs.mkdirSync(output, {recursive: true});
  const browser = await chromium.launch({headless: true, executablePath: process.env.BROWSER_EXECUTABLE || undefined});
  const page = await browser.newPage({viewport: {width: 1520, height: 1100}, acceptDownloads: true});
  const errors = [];
  page.on('pageerror', error => errors.push(String(error)));
  await page.addInitScript(() => {
    const fetch = window.fetch;
    window.__flowSmoke = {};
    window.fetch = async (...args) => {
      const response = await fetch(...args);
      const endpoint = String(args[0]).split('/').at(-1);
      if (['ask', 'compile'].includes(endpoint)) {
        response.clone().text().then(text => {
          window.__flowSmoke[endpoint] = text.trim().split('\n').map(line => JSON.parse(line));
        }).catch(error => { window.__flowSmoke[endpoint] = [{type: 'error', message: String(error)}]; });
      }
      return response;
    };
  });
  page.setDefaultTimeout(15000);
  try {
    await page.goto(url);
    await page.locator('#search').fill('固定值');
    assert.notEqual(await page.locator('#search-count').textContent(), '0/0');
    await page.locator('#fixed-value').click();
    await page.locator('.flow-qa-ask-node').click();
    await page.locator('.flow-qa-draft').fill('只按这张教学图回答：固定伤害 500，护盾 100，血量充足，实际扣血为什么是 400 而不是把之前的 1600 加进去？用三句话说明。');
    await page.locator('.flow-qa-send').click();
    await page.waitForFunction(() => window.__flowSmoke.ask, null, {timeout: 300000});
    const events = await page.evaluate(() => window.__flowSmoke.ask);
    assert.equal(events.at(-1).type, 'done', JSON.stringify(events.at(-1)));
    assert(events.some(event => event.type === 'delta'));
    assert(events.at(-1).entry.answer.includes('400'));
    assert.equal(events.at(-1).entry.node_id, 'fixed-value');
    const entryId = events.at(-1).entry.id;
    await page.locator(`[data-entry-id="${entryId}"] .flow-qa-pick`).click();
    await page.locator(`[data-entry-id="${entryId}"] .flow-qa-pick`).click();
    await page.locator('#zoom-fit').click();
    await page.locator('#diagram').screenshot({path: path.join(output, 'damage-qa.png')});
    console.log('PASS real Codex: streamed node-context answer contains the verified teaching result 400.');

    if (process.env.FLOW_LIVE_ANSWER_ONLY !== '1') {
      await page.locator('.flow-qa-compile').click();
      await page.waitForFunction(() => window.__flowSmoke.compile, null, {timeout: 300000});
      const compiledEvents = await page.evaluate(() => window.__flowSmoke.compile);
      assert.equal(compiledEvents.at(-1).type, 'compiled', JSON.stringify(compiledEvents.at(-1)));
      const revised = await page.request.get(url + compiledEvents.at(-1).url);
      assert(revised.ok());
      const revisedHtml = await revised.text();
      assert(!revisedHtml.includes('"runtime":'));
      fs.writeFileSync(path.join(output, 'revised-handbook.html'), revisedHtml);
      console.log('PASS real Codex: selected-answer revision generated and validated as a new offline version.');
    }

    const downloadPromise = page.waitForEvent('download');
    await page.locator('.flow-qa-export').click();
    const download = await downloadPromise;
    const offline = path.join(output, 'handbook-share.html');
    await download.saveAs(offline);
    const html = fs.readFileSync(offline, 'utf8');
    assert(!html.includes('"runtime":'));
    const offlinePage = await browser.newPage({viewport: {width: 1440, height: 1100}, offline: true});
    const network = [];
    offlinePage.on('request', request => {if (/^https?:/.test(request.url())) network.push(request.url());});
    await offlinePage.goto(pathToFileURL(offline).href);
    await offlinePage.locator('.flow-qa-toggle').click();
    assert((await offlinePage.locator('.flow-qa-answer').textContent()).includes('400'));
    assert.equal(await offlinePage.locator('.flow-qa-answer').innerHTML(),
      await page.locator(`[data-entry-id="${entryId}"] .flow-qa-answer`).innerHTML(),
      'Offline export preserves formatted answer content');
    assert(await offlinePage.locator('.flow-qa-send').isDisabled());
    assert.equal(await offlinePage.locator('.node').count(), 11);
    assert.deepEqual(network, []);
    await offlinePage.close();
    console.log('PASS offline sharing: selected answer, all nodes, disabled live send, zero network requests.');

    for (const [selector, filename] of [['.flow-qa-png-full', 'handbook-full.png']]) {
      const imagePromise = page.waitForEvent('download');
      await page.locator(selector).click();
      const image = await imagePromise;
      const target = path.join(output, filename);
      await image.saveAs(target);
      const pixels = await page.evaluate(async data => {
        const image = new Image(); image.src = data; await image.decode();
        const canvas = document.createElement('canvas'); canvas.width = image.width; canvas.height = image.height;
        const context = canvas.getContext('2d'); context.drawImage(image, 0, 0);
        const values = context.getImageData(0, 0, canvas.width, canvas.height).data;
        let colored = 0;
        for (let i = 0; i < values.length; i += 16) if (Math.min(values[i], values[i + 1], values[i + 2]) < 200 && values[i + 3]) colored++;
        return {width: image.width, height: image.height, colored};
      }, 'data:image/png;base64,' + fs.readFileSync(target).toString('base64'));
      assert(pixels.width > 200 && pixels.height > 200 && pixels.colored > 1000, JSON.stringify(pixels));
    }
    await page.reload();
    await page.locator('.flow-qa-toggle').click();
    await page.waitForFunction(id => !!document.querySelector(`[data-entry-id="${id}"]`), entryId);
    await page.setViewportSize({width: 390, height: 844});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    await page.screenshot({path: path.join(output, 'damage-qa-mobile.png')});
    assert.deepEqual(errors, []);
    console.log('PASS full PNG nonblank, history reload, narrow layout, no JavaScript errors.');
    if (process.env.FLOW_LIVE_LOOKUP === '1') {
      // The opt-in server must allow a synthetic combat.lua with followup_delay_ms = 75.
      await page.evaluate(() => {delete window.__flowSmoke.ask;});
      await page.locator('.flow-qa-draft').fill('源码中 combat.followup_delay_ms 的真实值是多少？这不在教学图里，请查所提供目录，给出文件和行号，不要猜。');
      await page.locator('.flow-qa-send').click();
      await page.waitForFunction(() => window.__flowSmoke.ask, null, {timeout: 300000});
      const lookup = await page.evaluate(() => window.__flowSmoke.ask);
      assert.equal(lookup.at(-1).type, 'done', JSON.stringify(lookup.at(-1)));
      assert(lookup.some(event => event.type === 'status'), 'Missing evidence must trigger source lookup');
      assert(lookup.at(-1).entry.answer.includes('75') && lookup.at(-1).entry.answer.includes('combat.lua'));
      console.log('PASS real missing-evidence fallback: bounded host lookup supplied combat.lua and value 75.');
    }
  } finally {
    await browser.close();
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
