'use strict';
const data=JSON.parse(document.getElementById('data').textContent);
const $=id=>document.getElementById(id), ns='http://www.w3.org/2000/svg';
const current=data.canvas, viewport=$('viewport');
let scale=1, width=1040, height=1;
function svg(tag,attrs,text){const e=document.createElementNS(ns,tag);for(const [k,v]of Object.entries(attrs))e.setAttribute(k,v);if(text)e.textContent=text;return e;}
function showDetail(n){$('detail-title').textContent=n.title;$('detail-formula').textContent=n.lines;$('detail-text').textContent=n.detail;const cited=(n.sources||[n.source]).map(id=>data.sources.find(s=>s.id===id)).filter(Boolean);$('source').textContent=cited.length?cited.map(s=>s.locator+'\n\n'+(s.excerpt||'分享副本未附原始摘录。')).join('\n\n———\n\n'):'未附来源';neighbours(n);select(n.id);document.dispatchEvent(new CustomEvent('flow:node-selected',{detail:{id:n.id}}));const d=$('detail');if(!d.open)d.showModal();d.scrollTop=0;}
// Previous and next steps come only from drawn edges, so walking them follows the authored flow.
function neighbours(n){
 const byId=id=>current.nodes.find(x=>x.id===id);
 const list=(box,edges,end,empty)=>{box.replaceChildren();if(!edges.length){const p=document.createElement('p');p.className='link-empty';p.textContent=empty;box.append(p);return;}
  for(const e of edges){const target=byId(e[end]);if(!target)continue;const b=document.createElement('button');b.type='button';b.className='step-link';b.dataset.node=target.id;
   if(e.label){const tag=document.createElement('span');tag.className='step-label';tag.textContent=e.label;b.append(tag);}
   const t=document.createElement('span');t.textContent=target.title;b.append(t);
   b.addEventListener('click',()=>{showDetail(target);centerOn($(target.id));});box.append(b);}};
 list($('detail-from'),current.edges.filter(e=>e.b===n.id),'a','这是流程起点');
 list($('detail-to'),current.edges.filter(e=>e.a===n.id),'b','流程到这里结束');
}
function zoom(value,center=true){const old=scale, x=(viewport.scrollLeft+viewport.clientWidth/2)/old,y=(viewport.scrollTop+viewport.clientHeight/2)/old;const minimum=Math.min(.1,(viewport.clientWidth-24)/width,(viewport.clientHeight-24)/height);scale=Math.max(minimum,Math.min(2,value));$('canvas').style.transform=`scale(${scale})`;$('stage').style.width=width*scale+'px';$('stage').style.height=height*scale+'px';$('zoom-value').textContent=(scale<.01?(scale*100).toFixed(2):Math.round(scale*100))+'%';if(center){viewport.scrollLeft=x*scale-viewport.clientWidth/2;viewport.scrollTop=y*scale-viewport.clientHeight/2;}}
function fit(){matchPinned=false;zoom(Math.min(1,(viewport.clientWidth-24)/width,(viewport.clientHeight-24)/height),false);viewport.scrollLeft=0;viewport.scrollTop=0;}
// Open at a size people can read: whole width, starting from the first step.
// A very wide flow on a phone stays legible and scrolls sideways instead.
function readable(){matchPinned=false;zoom(Math.min(1,Math.max(.55,(viewport.clientWidth-24)/width)),false);viewport.scrollLeft=0;viewport.scrollTop=0;}
function box(ids){const root=$('canvas').getBoundingClientRect();const rs=ids.map(id=>$(id)).filter(Boolean).map(el=>el.getBoundingClientRect());
 if(!rs.length)return null;const x=Math.min(...rs.map(r=>r.left)),y=Math.min(...rs.map(r=>r.top)),r=Math.max(...rs.map(r=>r.right)),b=Math.max(...rs.map(r=>r.bottom));
 return {x:(x-root.left)/scale,y:(y-root.top)/scale,w:(r-x)/scale,h:(b-y)/scale};}
function show(area,minimum=.45){if(!area)return;matchPinned=false;
 zoom(Math.max(Math.min(minimum,1),Math.min(1,(viewport.clientWidth-48)/area.w,(viewport.clientHeight-48)/area.h)),false);
 viewport.scrollLeft=Math.max(0,(area.x+area.w/2)*scale-viewport.clientWidth/2);
 viewport.scrollTop=Math.max(0,area.h*scale>viewport.clientHeight-48?area.y*scale-44:(area.y+area.h/2)*scale-viewport.clientHeight/2);}
function centerOn(el){if(!el)return;if(scale<.6)zoom(Math.min(1,(viewport.clientWidth-24)/width),false);show(box([el.id]),scale);}
viewport.addEventListener('wheel',event=>{
 if(!event.ctrlKey||!event.deltaY)return;
 event.preventDefault();
 matchPinned=false;
 const before=$('canvas').getBoundingClientRect(),x=(event.clientX-before.left)/scale,y=(event.clientY-before.top)/scale;
 const delta=event.deltaY*(event.deltaMode===1?16:event.deltaMode===2?viewport.clientHeight:1);
 zoom(scale*Math.exp(-Math.max(-300,Math.min(300,delta))*.002),false);
 const after=$('canvas').getBoundingClientRect();
 viewport.scrollLeft+=after.left+x*scale-event.clientX;
 viewport.scrollTop+=after.top+y*scale-event.clientY;
},{passive:false});
function clearRoute(points,obstacles){
 return points.slice(1).every((b,i)=>{const a=points[i];return obstacles.every(r=>{
  const left=r.x-5,right=r.x+r.w+5,top=r.y-5,bottom=r.y+r.h+5;
  if(Math.abs(a[0]-b[0])<.01)return a[0]<=left||a[0]>=right||Math.max(a[1],b[1])<=top||Math.min(a[1],b[1])>=bottom;
  return a[1]<=top||a[1]>=bottom||Math.max(a[0],b[0])<=left||Math.min(a[0],b[0])>=right;
 });});
}
function detour(a,b,rects,obstacles){
 // Grid row gaps and column gutters are free corridors even for uneven nodes.
 const startY=Math.max(...rects.filter(r=>r.row===a.row).map(r=>r.y+r.h))+20;
 const endY=Math.min(...rects.filter(r=>r.row===b.row).map(r=>r.y))-20;
 const ax=a.x+a.w/2,bx=b.x+b.w/2;
 const lanes=[20,width-20,...rects.flatMap(r=>[r.x-45,r.x+r.w+45])]
  .filter(x=>x>=15&&x<=width-15).sort((x,y)=>(Math.abs(x-ax)+Math.abs(x-bx))-(Math.abs(y-ax)+Math.abs(y-bx)));
 for(const x of lanes){const points=[[ax,a.y+a.h],[ax,startY],[x,startY],[x,endY],[bx,endY],[bx,b.y-2]];if(clearRoute(points,obstacles))return points;}
 throw new Error('No clear route; revise node placement.');
}
function draw(){
 const root=$('canvas').getBoundingClientRect(),layer=$('edges');layer.replaceChildren();
 const defs=svg('defs',{});for(const [id,color]of [['arrow','#638296'],['amber-arrow','#b17b24'],['active-arrow','#216e65'],['route-arrow','#b37d18']]){const m=svg('marker',{id,viewBox:'0 0 10 10',refX:9,refY:5,markerWidth:7,markerHeight:7,orient:'auto'});m.append(svg('path',{d:'M 0 0 L 10 5 L 0 10 z',fill:color}));defs.append(m);}layer.append(defs);
 const rects=current.nodes.map(n=>{const r=$(n.id).getBoundingClientRect();return {id:n.id,row:n.row,x:(r.left-root.left)/scale,y:(r.top-root.top)/scale,w:r.width/scale,h:r.height/scale};});
 for(const e of current.edges){const a=rects.find(r=>r.id===e.a),b=rects.find(r=>r.id===e.b);let points,lx,ly,anchor=e.route==='bypass'||e.route==='outer'?'end':'middle';const ax=a.x+a.w/2,ay=a.y+a.h,bx=b.x+b.w/2;
  if(e.route==='bypass'||e.route==='outer'){const x=width-(e.route==='bypass'?35:70);points=[[a.x+a.w,a.y+a.h/2],[x,a.y+a.h/2],[x,b.y+b.h/2],[b.x+b.w+2,b.y+b.h/2]];lx=x-8;ly=a.y+a.h/2-13;
  }else if(a.row===b.row&&b.x>a.x){points=[[a.x+a.w,a.y+a.h/2],[b.x-2,b.y+b.h/2]];lx=(a.x+a.w+b.x)/2;ly=a.y+a.h/2-10;
  }else if(Math.abs(a.x-b.x)<1&&b.y>ay){points=[[ax,ay],[ax,b.y-2]];lx=ax+8;ly=b.y-12;anchor='start';
  }else{const mid=(ay+b.y)/2;points=[[ax,ay],[ax,mid],[bx,mid],[bx,b.y-2]];
   // Branches that fan out downward share the first segment; label each one on its own drop.
   lx=bx+8;ly=(mid+b.y)/2+4;anchor='start';}
  const obstacles=rects.filter(r=>r.id!==e.a&&r.id!==e.b);
  if(!clearRoute(points,obstacles)){
   points=detour(a,b,rects,obstacles);
   const segments=points.slice(1).map((p,i)=>[points[i],p]).filter(([p,q])=>p[1]===q[1]).sort(([p,q],[r,s])=>Math.abs(s[0]-r[0])-Math.abs(q[0]-p[0]));
   const [p,q]=segments[0];lx=(p[0]+q[0])/2;ly=p[1]-8;anchor='middle';
  }
  const path=points.map((p,i)=>(i?'L':'M')+' '+p.join(' ')).join(' ');
  layer.append(svg('path',{d:path,fill:'none',stroke:e.route==='bypass'?'#b17b24':'#638296','stroke-width':1.8,'marker-end':`url(#${e.route==='bypass'?'amber-arrow':'arrow'})`,'data-from':e.a,'data-to':e.b}));
  if(e.label){const t=svg('text',{x:lx,y:ly,'text-anchor':anchor,class:'edge-label '+(e.route||'normal'),'data-from':e.a,'data-to':e.b},e.label);layer.append(t);const r=t.getBBox();layer.insertBefore(svg('rect',{x:r.x-5,y:r.y-3,width:r.width+10,height:r.height+6,rx:4,fill:'#fff','data-from':e.a,'data-to':e.b}),t);}
 }
 // Section titles sit just above each section's first row.
 if(sections.length>1)for(const section of sections){const r=rects.filter(x=>section.nodes.includes(x.id));if(!r.length)continue;
  const x=Math.min(...r.map(v=>v.x)),y=Math.min(...r.map(v=>v.y));const t=svg('text',{x:x+12,y:y-12,class:'section-label'},section.title);layer.append(t);
  const b=t.getBBox();layer.insertBefore(svg('rect',{x:x,y:b.y-4,width:b.width+24,height:b.height+8,rx:5,class:'section-tag'}),t);}
 paint();
}
$('graph-title').textContent='完整流程';$('graph-note').textContent='拖动空白处移动，Ctrl+滚轮缩放，按 / 查找。点节点看上一步、下一步和出处。';
const sections=(current.sections||[]).filter(s=>s.nodes&&s.nodes.length);
let selected=null,route=null;
function select(id){selected=id;paint();}
function paint(){
 const on=route?new Set(route.path):null,pairs=route?new Set(route.path.slice(1).map((b,i)=>route.path[i]+'>'+b)):null;
 for(const n of current.nodes){const el=$(n.id);if(!el)continue;el.classList.toggle('selected',n.id===selected);el.classList.toggle('dim',!!on&&!on.has(n.id));el.classList.toggle('on-route',!!on&&on.has(n.id));
  const steps=route?route.path.map((id,i)=>id===n.id?i+1:0).filter(Boolean):[];if(steps.length)el.dataset.step=steps.join('、');else delete el.dataset.step;}
 for(const el of $('edges').querySelectorAll('[data-from]')){const a=el.dataset.from,b=el.dataset.to;
  const active=!!selected&&(a===selected||b===selected),onRoute=!!pairs&&pairs.has(a+'>'+b);
  el.classList.toggle('edge-active',active);el.classList.toggle('edge-route',onRoute);el.classList.toggle('edge-dim',!!pairs&&!onRoute);
  if(el.tagName==='path'){el.dataset.marker??=el.getAttribute('marker-end');el.setAttribute('marker-end',onRoute?'url(#route-arrow)':active?'url(#active-arrow)':el.dataset.marker);}}
}
function showRoute(index){const ex=(data.examples||[])[index];if(!ex||!Array.isArray(ex.path))return;route={path:ex.path.filter(id=>$(id))};
 $('route-title').textContent=ex.title;$('route-bar').hidden=false;paint();$('diagram').scrollIntoView({block:'start'});show(box(route.path));$(route.path[0])?.focus({preventScroll:true});}
function exitRoute(){if(!route)return;route=null;$('route-bar').hidden=true;paint();}
// Example i is the i-th example block; exported copies may strip data attributes.
document.querySelectorAll('details.example').forEach((d,i)=>d.querySelector('.show-route')?.addEventListener('click',()=>showRoute(i)));
$('route-clear').addEventListener('click',exitRoute);
// An exported copy is a snapshot of this page; start it without the reader's temporary state.
$('route-bar').hidden=true;$('section-jump').querySelectorAll('button').forEach(b=>b.remove());$('section-jump').hidden=true;
if(sections.length>1){const bar=$('section-jump');bar.hidden=false;for(const section of sections){const b=document.createElement('button');b.type='button';b.textContent=section.title;b.title='跳到这一段';
 b.addEventListener('click',()=>{const area=box(section.nodes);if(!area)return;matchPinned=false;zoom(Math.min(1,(viewport.clientWidth-24)/width),false);viewport.scrollLeft=0;viewport.scrollTop=Math.max(0,(area.y-44)*scale);});bar.append(b);}}
document.addEventListener('keydown',e=>{const typing=/^(input|textarea|select)$/i.test(e.target.tagName)||e.target.isContentEditable;
 if(e.key==='/'&&!typing&&!e.ctrlKey&&!e.metaKey&&!e.altKey&&!$('detail').open){e.preventDefault();search.focus();search.select();}
 else if(e.key==='Escape'&&!typing&&!$('detail').open&&route)exitRoute();});
const columns=Math.max(...current.nodes.map(n=>n.col))+1;
width=40+columns*380+(columns-1)*90+140;
$('canvas').style.width=width+'px';$('nodes').style.gridTemplateColumns=`repeat(${columns},380px)`;
for(const n of current.nodes){const b=document.createElement('button');b.id=n.id;b.className='node '+n.kind;b.style.gridRow=n.row+1;b.style.gridColumn=n.col+1;const t=document.createElement('strong');t.textContent=n.title;const l=document.createElement('span');l.textContent=n.lines;b.append(t,l);b.addEventListener('click',()=>showDetail(n));$('nodes').append(b);}
function layout(){height=$('canvas').offsetHeight;zoom(scale,false);draw();if(matchPinned)centerMatch();}
$('zoom-in').addEventListener('click',()=>zoom(scale*1.2));$('zoom-out').addEventListener('click',()=>zoom(scale/1.2));$('zoom-reset').addEventListener('click',()=>zoom(1));$('zoom-fit').addEventListener('click',fit);
const search=$('search');
let matches=[],matchIndex=-1,composing=false,matchPinned=false;
for(const id of ['zoom-in','zoom-out','zoom-reset'])$(id).addEventListener('click',()=>{matchPinned=false;});
$('search-count').style.width=Math.max(5,String(current.nodes.length).length*2+1)+'ch';
function centerMatch(){
 const node=matches[matchIndex];if(!node)return;
 const v=viewport.getBoundingClientRect(),top=v.top+viewport.clientTop;
 const visibleTop=Math.max(0,top),visibleHeight=Math.min(window.innerHeight,top+viewport.clientHeight)-visibleTop;
 const viewHeight=visibleHeight>64?visibleHeight:viewport.clientHeight,offset=visibleHeight>64?visibleTop-top:0;
 zoom(Math.min(1,(viewport.clientWidth-32)/node.offsetWidth,(viewHeight-32)/node.offsetHeight),false);
 const r=node.getBoundingClientRect();
 const targetTop=Math.max(0,viewport.scrollTop+r.top-top-offset-(viewHeight-r.height)/2);
 // Leave enough scroll room to show late matches above the browser's bottom edge.
 $('stage').style.height=Math.max(height*scale,targetTop+viewport.clientHeight)+'px';
 viewport.scrollLeft+=r.left-v.left-viewport.clientLeft-(viewport.clientWidth-r.width)/2;
 viewport.scrollTop=targetTop;
}
function updateCurrentMatch(center=true){
 for(const [i,node]of matches.entries())node.classList.toggle('current-match',i===matchIndex);
 $('search-count').textContent=(matchIndex+1)+'/'+matches.length;
 $('search-prev').disabled=$('search-next').disabled=!matches.length;
 if(center){matchPinned=matches.length>0;if(matches.length)centerMatch();else zoom(scale,false);}
}
function updateMatches(event){
 const q=search.value.trim().toLowerCase();matches=[];
 for(const n of current.nodes){const node=$(n.id),matched=!!q&&(n.title+n.lines+n.detail).toLowerCase().includes(q);node.classList.toggle('match',matched);node.classList.remove('current-match');if(matched)matches.push(node);}
 matchIndex=matches.length?0:-1;updateCurrentMatch(!composing&&!event?.isComposing);
}
function moveMatch(direction){if(!matches.length||composing)return;matchIndex=(matchIndex+direction+matches.length)%matches.length;updateCurrentMatch();}
search.addEventListener('input',updateMatches);
search.addEventListener('compositionstart',()=>{composing=true;});
search.addEventListener('compositionend',()=>{composing=false;updateMatches();});
search.addEventListener('keydown',event=>{
 if(event.key!=='Enter'||event.isComposing||composing||event.keyCode===229)return;
 event.preventDefault();moveMatch(event.shiftKey?-1:1);
});
$('search-prev').addEventListener('click',()=>moveMatch(-1));
$('search-next').addEventListener('click',()=>moveMatch(1));
updateMatches();
let drag=null;
viewport.addEventListener('pointerdown',e=>{if(e.target.closest('button')||e.button!==0||e.pointerType==='touch')return;matchPinned=false;drag={x:e.clientX,y:e.clientY,left:viewport.scrollLeft,top:viewport.scrollTop};viewport.setPointerCapture(e.pointerId);viewport.classList.add('dragging');});
viewport.addEventListener('pointermove',e=>{if(!drag)return;viewport.scrollLeft=drag.left+drag.x-e.clientX;viewport.scrollTop=drag.top+drag.y-e.clientY;});
function endDrag(){drag=null;viewport.classList.remove('dragging');}viewport.addEventListener('pointerup',endDrag);viewport.addEventListener('pointercancel',endDrag);
function activateNavigation(item){document.querySelectorAll('nav a').forEach(el=>{el.classList.toggle('nav-active',el===item);if(el===item)el.setAttribute('aria-current','location');else el.removeAttribute('aria-current');});}
document.querySelectorAll('nav a').forEach(el=>el.addEventListener('click',()=>activateNavigation(el)));
window.addEventListener('resize',layout);layout();document.fonts.ready.then(()=>{layout();if(matchIndex<0)readable();});
