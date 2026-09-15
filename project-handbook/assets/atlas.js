(function(){
'use strict';
const mapTimers=typeof WeakMap==='function'?new WeakMap():null;
function pathIds(stage){return (stage.getAttribute('data-map-path')||'').split(',').filter(Boolean);}
function focusNode(stage,id){
 const hasCard=!!(id && stage.querySelector('[data-map-card="'+id+'"]'));
 const target=hasCard?id:'_default';
 stage.setAttribute('data-map-focus',id||'');
 stage.querySelectorAll('[data-map-card]').forEach(function(card){card.hidden=card.getAttribute('data-map-card')!==target;});
 stage.querySelectorAll('.map-node').forEach(function(node){node.classList.toggle('is-focus',!!id && node.getAttribute('data-map-id')===id);});
}
function setLens(stage,lens){
 stage.setAttribute('data-lens',lens);
 stage.querySelectorAll('[data-map-lens]').forEach(function(btn){btn.setAttribute('aria-pressed',String(btn.getAttribute('data-map-lens')===lens));});
}
function stopPlay(stage){
 const timer=mapTimers&&mapTimers.get(stage);
 if(timer){clearInterval(timer);mapTimers.delete(stage);}
 const play=stage.querySelector('[data-map-play]');
 if(play)play.setAttribute('aria-pressed','false');
}
function playPath(stage){
 const ids=pathIds(stage);
 if(!ids.length)return;
 stopPlay(stage);
 setLens(stage,'route');
 let index=0;
 focusNode(stage,ids[0]);
 const play=stage.querySelector('[data-map-play]');
 if(play)play.setAttribute('aria-pressed','true');
 const reduced=window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches;
 if(reduced || ids.length===1){if(play)play.setAttribute('aria-pressed','false');return;}
 const timer=setInterval(function(){
  index+=1;
  if(index>=ids.length){stopPlay(stage);return;}
  focusNode(stage,ids[index]);
 },900);
 if(mapTimers)mapTimers.set(stage,timer);
}
function setupMaps(){
 document.querySelectorAll('[data-map-stage]').forEach(function(stage){
  const initial=stage.getAttribute('data-map-focus')||'';
  focusNode(stage,initial);
  setLens(stage,stage.getAttribute('data-lens')||'domains');
 });
}
function setFlowLane(stage,id){
 if(!id)return;
 stage.querySelectorAll('[data-flow-lane]').forEach(function(btn){btn.setAttribute('aria-pressed',String(btn.getAttribute('data-flow-lane')===id));});
 stage.querySelectorAll('[data-flow-panel]').forEach(function(panel){panel.hidden=panel.getAttribute('data-flow-panel')!==id;});
}
function setupFlows(){
 document.querySelectorAll('[data-flow-stage]').forEach(function(stage){
  let current=null;
  stage.querySelectorAll('[data-flow-lane]').forEach(function(btn){
   if(!current || btn.getAttribute('aria-pressed')==='true') current=btn;
  });
  if(current)setFlowLane(stage,current.getAttribute('data-flow-lane'));
 });
}
function revealHash(){
 const id=decodeURIComponent(location.hash.slice(1));
 const target=document.getElementById(id); if(!target)return;
 const node=target.closest('.flow-node'); if(node)node.hidden=false;
}
 document.addEventListener('click',function(event){
 const lens=event.target.closest('[data-map-lens]');
 if(lens){const stage=lens.closest('[data-map-stage]');if(stage){stopPlay(stage);setLens(stage,lens.getAttribute('data-map-lens'));}}
 const play=event.target.closest('[data-map-play]');
 if(play){const stage=play.closest('[data-map-stage]');if(stage)playPath(stage);}
 const mapNode=event.target.closest('[data-map-id]');
 if(mapNode){const stage=mapNode.closest('[data-map-stage]');if(stage){stopPlay(stage);focusNode(stage,mapNode.getAttribute('data-map-id'));}}
 const lane=event.target.closest('[data-flow-lane]');
 if(lane){const stage=lane.closest('[data-flow-stage]');if(stage)setFlowLane(stage,lane.getAttribute('data-flow-lane'));}
 const filter=event.target.closest('[data-filter]');
 const branch=event.target.closest('[data-branch]');
 if(branch){const group=branch.closest('.branch-group');group.querySelectorAll('[data-branch]').forEach(b=>b.setAttribute('aria-pressed',String(b===branch)));group.querySelectorAll('[data-branch-panel]').forEach(p=>p.hidden=p.dataset.branchPanel!==branch.dataset.branch);}
 if(filter){
  document.querySelectorAll('[data-filter]').forEach(b=>b.setAttribute('aria-pressed',String(b===filter)));
  document.querySelectorAll('.flow-node').forEach(n=>n.hidden=filter.dataset.filter!=='all'&&n.dataset.kind!==filter.dataset.filter);
 }
 const copy=event.target.closest('[data-copy]');
 if(copy){
  if(navigator.clipboard)navigator.clipboard.writeText(copy.dataset.copy).then(()=>{copy.textContent='已复制来源位置';}).catch(()=>{copy.textContent='无法复制，请选中上方来源位置手动复制';});
  else copy.textContent='请选中上方来源位置手动复制';
 }
});
document.addEventListener('keydown',function(event){
 if(event.key!=='Enter' && event.key!==' ')return;
 const mapNode=event.target.closest('[data-map-id]');
 if(!mapNode)return;
 event.preventDefault();
 const stage=mapNode.closest('[data-map-stage]');
 if(stage){stopPlay(stage);focusNode(stage,mapNode.getAttribute('data-map-id'));}
});
 setupMaps();
 setupFlows();
 function applyReturnFrom(){
 const params=new URLSearchParams(location.search);
 const from=params.get('from')||'';
 const match=/^([a-z][a-z0-9-]{0,44})\.([a-z][a-z0-9-]{0,44})$/.exec(from);
 const flowMatch=/^flow\./.exec(from);
 document.querySelectorAll('.return-flow').forEach(function(link){link.hidden=!flowMatch;});
 document.querySelectorAll('.return-topic:not(.return-flow)').forEach(function(link){link.hidden=!!flowMatch;});
 if(!match && !flowMatch)return;
 const href=match ? match[1]+'.html#'+match[2] : '';
 document.querySelectorAll('[data-return]').forEach(function(link){
   if(link.getAttribute('data-return')===from || link.classList.contains('return-topic')){
    if(href)link.setAttribute('href',href);
    if(link.classList.contains('return-topic')){
     const label=document.querySelector('[data-return="'+from+'"]:not(.return-topic)');
     link.textContent=label ? '← 返回专题：'+label.textContent.replace(/\s*→\s*$/,'') : '← 返回来时的专题';
    }
   }
  });
 }
 window.addEventListener('hashchange',revealHash);revealHash();applyReturnFrom();
})();
