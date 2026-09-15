const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('assert');
const { pathToFileURL } = require('url');
const path = require('path');
const fs = require('fs');
(async () => {
  const browser = await chromium.launch({headless:true, executablePath:process.env.BROWSER_EXECUTABLE || undefined});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1100},offline:true});
    const errors=[], requests=[];
    page.on('pageerror', e=>errors.push(String(e)));
    page.on('request', r=>{if(/^https?:/.test(r.url())) requests.push(r.url());});
    await page.goto(pathToFileURL(path.resolve(process.argv[2])).href);
    assert.equal(await page.locator('#review, a[href="#review"]').count(),0);
    for(const id of ['order','payment']) {
      await page.locator(`[data-tab="${id}"]`).click();
      await page.waitForTimeout(100);
      assert.equal(await page.locator('nav [aria-pressed="true"]').count(),1);
      const geometry=await page.evaluate(()=>{
        const nodes=[...document.querySelectorAll('.node')];
        const paths=[...document.querySelectorAll('#edges>path')];
        const collisions=[];
        for(const p of paths){
          const s=p.ownerSVGElement.getBoundingClientRect();
          for(let i=3;i<p.getTotalLength()-3;i+=5){
            const pt=p.getPointAtLength(i);
            for(const n of nodes){
              if(n.id===p.dataset.from||n.id===p.dataset.to)continue;
              const r=n.getBoundingClientRect(),x=pt.x+s.left,y=pt.y+s.top;
              if(x>r.left+1&&x<r.right-1&&y>r.top+1&&y<r.bottom-1)collisions.push(n.id);
            }
          }
        }
        return {collisions, paths:paths.length,overflow:document.documentElement.scrollWidth>innerWidth};
      });
      assert.equal(geometry.paths,4);
      assert.deepEqual(geometry.collisions,[]);
      assert.equal(geometry.overflow,false);
    }
    await page.locator('a[href="#examples"]').click();
    assert.equal(await page.locator('nav [aria-pressed="true"]').count(),0);
    assert.equal(await page.locator('a[aria-current="location"]').count(),1);
    assert.equal(await page.locator('a[href="#examples"]').evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(33, 110, 101)');
    await page.locator('.example summary').first().click();
    assert.notEqual(await page.locator('.example').first().getAttribute('open'),null);
    await page.locator('[data-tab="order"]').click();
    assert.equal(await page.locator('nav a[aria-current]').count(),0);
    if(process.argv[3]){
      fs.mkdirSync(process.argv[3],{recursive:true});
      await page.evaluate(()=>window.scrollTo(0,0));
      await page.screenshot({path:path.join(process.argv[3],'payment-flow.png')});
    }
    await page.locator('#created').click();
    assert(await page.locator('#detail').isVisible());
    assert((await page.locator('#source').textContent()).includes('合成'));
    if(process.argv[3]) await page.screenshot({path:path.join(process.argv[3],'payment-detail.png')});
    await page.locator('.close').click();
    await page.locator('#search').fill('金额');
    assert(await page.locator('.match').count()>0);
    await page.locator('#next').click();
    assert.equal(await page.locator('[data-tab="payment"]').getAttribute('aria-pressed'),'true');
    await page.setViewportSize({width:390,height:844});
    await page.locator('[data-tab="order"]').click();
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    assert.deepEqual(errors,[]);assert.deepEqual(requests,[]);
    console.log('Flow browser checks passed: navigation, details, examples, search, routes, mobile, offline.');
  } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exit(1);});
