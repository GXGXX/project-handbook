'use strict';
const data=JSON.parse(document.getElementById('data').textContent);
const $=id=>document.getElementById(id), ns='http://www.w3.org/2000/svg';
let current=data.graphs[0];
function svg(tag,attrs,text){const e=document.createElementNS(ns,tag);for(const [k,v]of Object.entries(attrs))e.setAttribute(k,v);if(text)e.textContent=text;return e}
function showDetail(n){$('detail-title').textContent=n.title;$('detail-formula').textContent=n.lines;$('detail-text').textContent=n.detail;const source=data.sources.find(s=>s.id===current.source);$('source').textContent=source?source.locator+'\n\n'+source.excerpt:'未附实现证据';$('detail').showModal()}
function draw(){
 const root=$('canvas').getBoundingClientRect(), layer=$('edges');layer.replaceChildren();
 const defs=svg('defs',{});for(const [id,color]of [['arrow','#638296'],['amber-arrow','#b17b24']]){const m=svg('marker',{id,viewBox:'0 0 10 10',refX:9,refY:5,markerWidth:7,markerHeight:7,orient:'auto-start-reverse'});m.append(svg('path',{d:'M 0 0 L 10 5 L 0 10 z',fill:color}));defs.append(m)}layer.append(defs);
 const bounds=id=>{const r=$(id).getBoundingClientRect();return {x:r.left-root.left,y:r.top-root.top,w:r.width,h:r.height}};
 for(const e of current.edges){const a=bounds(e.a),b=bounds(e.b);let path,lx,ly;const ax=a.x+a.w/2,ay=a.y+a.h,bx=b.x+b.w/2;
  if(e.route==='bypass'||e.route==='outer'){const x=e.route==='bypass'?995:945;path=`M ${a.x+a.w} ${a.y+a.h/2} H ${x} V ${b.y+b.h/2} H ${b.x+b.w+2}`;lx=x-8;ly=a.y+a.h/2-13;
  }else if(Math.abs(a.y+a.h/2-b.y-b.h/2)<5){path=`M ${a.x+a.w} ${a.y+a.h/2} H ${b.x-2}`;lx=(a.x+a.w+b.x)/2;ly=a.y+a.h/2-10;
  }else if(a.x===b.x){path=`M ${ax} ${ay} V ${b.y-2}`;lx=ax+16;ly=(ay+b.y)/2+4;
  }else{path=`M ${ax} ${ay} V ${b.y+b.h/2} H ${b.x+b.w+2}`;lx=ax+19;ly=ay+26;}
  layer.append(svg('path',{d:path,fill:'none',stroke:e.route==='bypass'?'#b17b24':'#638296','stroke-width':1.8,'marker-end':`url(#${e.route==='bypass'?'amber-arrow':'arrow'})`,'data-from':e.a,'data-to':e.b}));
  if(e.label){const t=svg('text',{x:lx,y:ly,'text-anchor':e.route==='bypass'||e.route==='outer'?'end':'middle',class:'edge-label '+e.route},e.label);layer.append(t);const r=t.getBBox();const bg=svg('rect',{x:r.x-5,y:r.y-3,width:r.width+10,height:r.height+6,rx:4,fill:'#fff'});layer.insertBefore(bg,t)}
 }
}
function select(id,scroll=false){current=data.graphs.find(g=>g.id===id);$('nodes').replaceChildren();$('graph-title').textContent=current.title;$('graph-note').textContent=current.note || '沿箭头阅读；点击节点查看公式与依据。';for(const n of current.nodes){const b=document.createElement('button');b.id=n.id;b.className='node '+n.kind;b.style.gridRow=n.row+1;b.style.gridColumn=n.col+1;const t=document.createElement('strong');t.textContent=n.title;const l=document.createElement('span');l.textContent=n.lines;b.append(t,l);b.addEventListener('click',()=>showDetail(n));$('nodes').append(b)}document.querySelectorAll('[data-tab]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.tab===id)));$('next').hidden=id===data.common;$('next').style.display=(!data.common || id===data.common)?'none':'block';$('search').value='';requestAnimationFrame(draw);if(scroll)$('diagram').scrollIntoView({behavior:'instant'})}
document.querySelectorAll('[data-tab]').forEach(b=>b.addEventListener('click',()=>select(b.dataset.tab,true)));
$('next').addEventListener('click',()=>select(data.common || data.graphs[0].id,true));
$('search').addEventListener('input',()=>{const q=$('search').value.trim().toLowerCase();for(const n of current.nodes)$(n.id).classList.toggle('match',!!q&&(n.title+n.lines+n.detail).toLowerCase().includes(q))});
window.addEventListener('resize',draw);select(data.graphs[0].id);document.fonts.ready.then(draw);

// Give section navigation the same exclusive active state as flow navigation.
function activateNavigation(item){
 document.querySelectorAll('nav button,nav a').forEach(el=>{
  const active=el===item;
  el.classList.toggle('nav-active',active);
  if(el.tagName==='BUTTON')el.setAttribute('aria-pressed',String(active));
  else if(active)el.setAttribute('aria-current','location');
  else el.removeAttribute('aria-current');
 });
}
document.querySelectorAll('nav button,nav a').forEach(el=>el.addEventListener('click',()=>activateNavigation(el)));
$('next').addEventListener('click',()=>activateNavigation(document.querySelector('[data-tab="'+(data.common || data.graphs[0].id)+'"]')));
