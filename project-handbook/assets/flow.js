'use strict';
const data=JSON.parse(document.getElementById('data').textContent);
const $=id=>document.getElementById(id), ns='http://www.w3.org/2000/svg';
const current=data.canvas, viewport=$('viewport');
let scale=1, width=1040, height=1;
function svg(tag,attrs,text){const e=document.createElementNS(ns,tag);for(const [k,v]of Object.entries(attrs))e.setAttribute(k,v);if(text)e.textContent=text;return e;}
function showDetail(n){$('detail-title').textContent=n.title;$('detail-formula').textContent=n.lines;$('detail-text').textContent=n.detail;const source=data.sources.find(s=>s.id===n.source);$('source').textContent=source?source.locator+'\n\n'+(source.excerpt||'分享副本未附原始摘录。'):'未附来源';document.dispatchEvent(new CustomEvent('flow:node-selected',{detail:{id:n.id}}));$('detail').showModal();}
function zoom(value,center=true){const old=scale, x=(viewport.scrollLeft+viewport.clientWidth/2)/old,y=(viewport.scrollTop+viewport.clientHeight/2)/old;const minimum=Math.min(.1,(viewport.clientWidth-24)/width,(viewport.clientHeight-24)/height);scale=Math.max(minimum,Math.min(2,value));$('canvas').style.transform=`scale(${scale})`;$('stage').style.width=width*scale+'px';$('stage').style.height=height*scale+'px';$('zoom-value').textContent=(scale<.01?(scale*100).toFixed(2):Math.round(scale*100))+'%';if(center){viewport.scrollLeft=x*scale-viewport.clientWidth/2;viewport.scrollTop=y*scale-viewport.clientHeight/2;}}
function fit(){matchPinned=false;zoom(Math.min(1,(viewport.clientWidth-24)/width,(viewport.clientHeight-24)/height),false);viewport.scrollLeft=0;viewport.scrollTop=0;}
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
 const defs=svg('defs',{});for(const [id,color]of [['arrow','#638296'],['amber-arrow','#b17b24']]){const m=svg('marker',{id,viewBox:'0 0 10 10',refX:9,refY:5,markerWidth:7,markerHeight:7,orient:'auto'});m.append(svg('path',{d:'M 0 0 L 10 5 L 0 10 z',fill:color}));defs.append(m);}layer.append(defs);
 const rects=current.nodes.map(n=>{const r=$(n.id).getBoundingClientRect();return {id:n.id,row:n.row,x:(r.left-root.left)/scale,y:(r.top-root.top)/scale,w:r.width/scale,h:r.height/scale};});
 for(const e of current.edges){const a=rects.find(r=>r.id===e.a),b=rects.find(r=>r.id===e.b);let points,lx,ly,anchor=e.route==='bypass'||e.route==='outer'?'end':'middle';const ax=a.x+a.w/2,ay=a.y+a.h,bx=b.x+b.w/2;
  if(e.route==='bypass'||e.route==='outer'){const x=width-(e.route==='bypass'?35:70);points=[[a.x+a.w,a.y+a.h/2],[x,a.y+a.h/2],[x,b.y+b.h/2],[b.x+b.w+2,b.y+b.h/2]];lx=x-8;ly=a.y+a.h/2-13;
  }else if(a.row===b.row&&b.x>a.x){points=[[a.x+a.w,a.y+a.h/2],[b.x-2,b.y+b.h/2]];lx=(a.x+a.w+b.x)/2;ly=a.y+a.h/2-10;
  }else if(Math.abs(a.x-b.x)<1&&b.y>ay){points=[[ax,ay],[ax,b.y-2]];lx=ax+16;ly=(ay+b.y)/2+4;
  }else{const mid=(ay+b.y)/2;points=[[ax,ay],[ax,mid],[bx,mid],[bx,b.y-2]];lx=ax+20;ly=ay+22;}
  const obstacles=rects.filter(r=>r.id!==e.a&&r.id!==e.b);
  if(!clearRoute(points,obstacles)){
   points=detour(a,b,rects,obstacles);
   const segments=points.slice(1).map((p,i)=>[points[i],p]).filter(([p,q])=>p[1]===q[1]).sort(([p,q],[r,s])=>Math.abs(s[0]-r[0])-Math.abs(q[0]-p[0]));
   const [p,q]=segments[0];lx=(p[0]+q[0])/2;ly=p[1]-8;anchor='middle';
  }
  const path=points.map((p,i)=>(i?'L':'M')+' '+p.join(' ')).join(' ');
  layer.append(svg('path',{d:path,fill:'none',stroke:e.route==='bypass'?'#b17b24':'#638296','stroke-width':1.8,'marker-end':`url(#${e.route==='bypass'?'amber-arrow':'arrow'})`,'data-from':e.a,'data-to':e.b}));
  if(e.label){const t=svg('text',{x:lx,y:ly,'text-anchor':anchor,class:'edge-label '+(e.route||'normal')},e.label);layer.append(t);const r=t.getBBox();layer.insertBefore(svg('rect',{x:r.x-5,y:r.y-3,width:r.width+10,height:r.height+6,rx:4,fill:'#fff'}),t);}
 }
}
$('graph-title').textContent='完整流程';$('graph-note').textContent='拖动空白处移动；Ctrl+滚轮缩放。点节点看细节，需要追问时点问答。';
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
window.addEventListener('resize',layout);layout();document.fonts.ready.then(()=>{layout();if(matchIndex<0)fit();});
