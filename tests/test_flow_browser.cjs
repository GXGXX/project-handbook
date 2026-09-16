const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('assert'),fs=require('fs'),path=require('path');
const {pathToFileURL}=require('url');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.BROWSER_EXECUTABLE||undefined});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1250},offline:true});
  const errors=[],requests=[];page.on('pageerror',e=>errors.push(String(e)));page.on('request',r=>{if(/^https?:/.test(r.url()))requests.push(r.url());});
  await page.goto(pathToFileURL(path.resolve(process.argv[2])).href);await page.evaluate(()=>document.fonts.ready);await page.waitForTimeout(150);
  assert.equal(await page.locator('[data-tab],#next,#review').count(),0);
  assert.equal(await page.locator('.node').count(),10);
  assert.equal(await page.locator('#edges>path').count(),9);
  assert.equal(await page.locator('path[data-from="pay"][data-to="callback"]').count(),1);
  const fitBounds=await page.evaluate(()=>{const v=document.getElementById('viewport').getBoundingClientRect();return [...document.querySelectorAll('.node')].every(n=>{const r=n.getBoundingClientRect();return r.left>=v.left&&r.top>=v.top&&r.right<=v.right&&r.bottom<=v.bottom;});});assert(fitBounds,'fit should contain every node');
  const before=await page.locator('#zoom-value').textContent();await page.locator('#zoom-in').click();assert.notEqual(await page.locator('#zoom-value').textContent(),before);await page.locator('#zoom-reset').click();assert.equal(await page.locator('#zoom-value').textContent(),'100%');
  const collisions=await page.evaluate(()=>{const found=[];for(const p of document.querySelectorAll('#edges>path')){for(let i=4;i<p.getTotalLength()-4;i+=5){const xy=p.getPointAtLength(i).matrixTransform(p.getScreenCTM());for(const n of document.querySelectorAll('.node')){if(n.id===p.dataset.from||n.id===p.dataset.to)continue;const r=n.getBoundingClientRect();if(xy.x>r.left+1&&xy.x<r.right-1&&xy.y>r.top+1&&xy.y<r.bottom-1)found.push(n.id);}}}return found;});assert.deepEqual(collisions,[]);
  await page.locator('#search').fill('金额');await page.locator('#locate').click();assert(await page.locator('.node.match').count()>=1);await page.locator('#created').click();assert(await page.locator('#detail').isVisible());assert((await page.locator('#source').textContent()).includes('合成'));assert((await page.locator('#detail-text').textContent()).includes('100'));
  if(process.argv[3]){fs.mkdirSync(process.argv[3],{recursive:true});await page.screenshot({path:path.join(process.argv[3],'payment-detail.png')});}await page.locator('.close').click();
  // Search spans all sections, not just the first one.
  await page.locator('#search').fill('幂等');await page.locator('#locate').click();await page.locator('#duplicate').click();assert((await page.locator('#detail-title').textContent()).includes('已处理'));await page.locator('.close').click();
  await page.locator('#viewport').evaluate(e=>{e.scrollTop=0;e.scrollLeft=0;});const v=await page.locator('#viewport').boundingBox();await page.mouse.move(v.x+15,v.y+200);await page.mouse.down();await page.mouse.move(v.x+15,v.y+80,{steps:5});await page.mouse.up();assert(await page.locator('#viewport').evaluate(e=>e.scrollTop)>50,'drag should pan');
  await page.locator('a[href="#examples"]').click();assert.equal(await page.locator('nav [aria-current]').count(),1);assert.equal(await page.locator('a[href="#examples"]').evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(33, 110, 101)');await page.locator('.example summary').first().click();assert.notEqual(await page.locator('.example').first().getAttribute('open'),null);
  await page.locator('a[href="#diagram"]').click();await page.locator('#search').fill('');await page.locator('#zoom-fit').click();if(process.argv[3])await page.locator('#diagram').screenshot({path:path.join(process.argv[3],'payment-flow.png')});
  // A long workflow must still fit; a fixed minimum zoom silently clips it.
  await page.evaluate(()=>{document.getElementById('nodes').style.rowGap='1500px';window.dispatchEvent(new Event('resize'));});
  await page.locator('#zoom-fit').click();
  assert(await page.evaluate(()=>{const v=document.getElementById('viewport').getBoundingClientRect(),n=document.querySelector('.node:last-child').getBoundingClientRect();return n.bottom<=v.bottom;}),'long workflow fit clips last node');
  await page.evaluate(()=>{document.getElementById('nodes').style.rowGap='';window.dispatchEvent(new Event('resize'));});
  await page.setViewportSize({width:390,height:844});await page.locator('#zoom-fit').click();assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  assert.deepEqual(errors,[]);assert.deepEqual(requests,[]);console.log('PASS: entire canvas, explicit connection, zoom, fit, drag, global search, details, navigation, examples, offline, mobile, no node-edge collisions.');
  const base=fs.readFileSync(process.argv[2],'utf8');
  const node=(id,row,col=0)=>({id,row,col,title:id,lines:'',detail:'',kind:'process',source:'demo'});
  const fixtures=[
    {name:'multiple-entry-merge',nodes:[node('entryA',0),node('entryB',2),node('merged',4)],edges:[{a:'entryA',b:'merged',label:'A'},{a:'entryB',b:'merged',label:'B'}]},
    ...['outer','bypass'].map(route=>({name:'parallel-'+route,nodes:[node('leftA',0),node('leftB',2),node('rightA',0,2),node('rightB',2,2)],edges:[{a:'leftA',b:'leftB',route,label:'left'},{a:'rightA',b:'rightB',label:'right'}]}))
  ];
  for(const fixture of fixtures){
    const p=await browser.newPage({viewport:{width:1440,height:900},offline:true});
    p.on('pageerror',e=>errors.push(String(e)));
    const html=base.replace(/(<script type="application\/json" id="data">)([\s\S]*?)(<\/script>)/,(_,a,json,b)=>{const d=JSON.parse(json);d.canvas=fixture;return a+JSON.stringify(d)+b;});
    await p.setContent(html);await p.evaluate(()=>document.fonts.ready);await p.locator('#zoom-reset').click();
    const collisions=await p.evaluate(()=>{const found=[];for(const e of document.querySelectorAll('#edges>path'))for(let i=3;i<e.getTotalLength()-3;i+=3){const pt=e.getPointAtLength(i).matrixTransform(e.getScreenCTM());for(const n of document.querySelectorAll('.node')){if(n.id===e.dataset.from||n.id===e.dataset.to)continue;const r=n.getBoundingClientRect();if(pt.x>r.left+1&&pt.x<r.right-1&&pt.y>r.top+1&&pt.y<r.bottom-1)found.push(n.id);}}return found;});
    assert.deepEqual(collisions,[],fixture.name);
    await p.close();
  }
  assert.deepEqual(errors,[]);console.log('PASS: multi-entry merge and parallel outer/bypass routes.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
