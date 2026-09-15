// Executes the shipped browser script with a minimal DOM; no external packages.
const fs=require('fs'), vm=require('vm'), assert=require('assert');
class El {
 constructor(){this.value='';this.textContent='';this.children=[];this.listeners={};this.style={};this.disabled=false;this.checked=false;}
 addEventListener(e,f){(this.listeners[e]??=[]).push(f);}
  appendChild(n){n.parentNode=this;this.children.push(n);return n;}
  removeChild(n){this.children=this.children.filter(c=>c!==n);n.parentNode=null;return n;}
 setAttribute(k,v){this[k]=v;}
 focus(){} select(){} scrollIntoView(){}
 fire(e){for(const f of this.listeners[e]||[])f({preventDefault(){},target:this});}
 set innerHTML(v){this.children=[];this._html=v;} get innerHTML(){return this._html||'';}
 get options(){return this.children;}
}
function setup(storage, options={}){
  const ids={}; for(const id of ['chat-panel','chat-config','search-data','chat-messages','chat-form','chat-input','chat-send','chat-status','chat-mode','chat-endpoint','chat-model','chat-key-wrap','chat-api-key','chat-clear','chat-answer-mode','chat-export','chat-consent','chat-fetch-models','chat-fetch-note','chat-settings'])ids[id]=new El();
  ids['chat-config'].textContent=JSON.stringify({book_id:options.book||'fixture',mode:'relay',endpoint:'/api/chat',current_page:'pages/rules.html',max_history:0});
   ids['search-data'].textContent=JSON.stringify([{title:'等级开放条件',url:'pages/rules.html#open',text:'unlock_level = 10'}]); ids['chat-answer-mode'].value='evidence';
  ids['chat-fetch-note'].hidden=true;
  const docListeners={};const windowListeners={};let calls=0; const fetches=[];
  const sandbox={document:{title:'规则',getElementById:id=>ids[id]||null,createElement:()=>new El(),addEventListener:(e,f)=>{docListeners[e]=f;}},window:{location:{protocol:options.protocol||'http:'},HANDBOOK_BASE:'../',addEventListener:(e,f)=>{windowListeners[e]=f;}},sessionStorage:{getItem:k=>storage[k],setItem:(k,v)=>storage[k]=v},navigator:{},console,AbortController,setTimeout,clearTimeout,fetch:(url,opts)=>{calls++;fetches.push(String(url)); if(!options.failFetch && (String(url).includes('/api/models')||/\/models$/.test(String(url)))) return Promise.resolve({ok:true,status:200,text:()=>Promise.resolve(JSON.stringify({data:[{id:'gpt-test'}]}))}); return Promise.reject(Error('Failed to fetch'));}};
 vm.runInNewContext(fs.readFileSync('project-handbook/assets/chat.js','utf8'),sandbox);
 return {ids,docListeners,windowListeners,calls:()=>calls,fetches};
}
(async()=>{
  const storage={};let app=setup(storage);app.ids['chat-input'].value='等级开放';app.ids['chat-form'].fire('submit');
 assert.equal(app.calls(),0,'evidence mode must not send data');
  assert(app.ids['chat-messages'].children.some(b=>b.children.some(t=>t.textContent.includes('unlock_level = 10'))));
 app.ids['chat-input'].value='未发送草稿';app.ids['chat-input'].fire('input');app.windowListeners.pagehide();
 app=setup(storage);assert.equal(app.ids['chat-input'].value,'未发送草稿');assert(app.ids['chat-messages'].children.length>=2);
 const other=setup(storage,{book:'other'});assert.equal(other.ids['chat-input'].value,'');
   app.ids['chat-answer-mode'].value='model';app.ids['chat-consent'].checked=false;app.ids['chat-model'].value='';app.ids['chat-input'].value='等级开放';app.ids['chat-form'].fire('submit');await new Promise(r=>setImmediate(r));
   assert.equal(app.calls(),0,'missing model means no network');assert.equal(app.ids['chat-input'].value,'等级开放','failed question restored');
  assert(app.ids['chat-consent'].checked,'consent stays on without showing a checkbox');
  app.ids['chat-api-key'].value='DO-NOT-STORE';app.ids['chat-fetch-models'].fire('click');await new Promise(r=>setImmediate(r));
  assert.equal(app.ids['chat-model'].value,'gpt-test');assert(app.fetches.some(u=>u.includes('/api/models')));
  assert(String(app.ids['chat-fetch-note'].textContent).includes('已获取'));
   const fileApp=setup({}, {protocol:'file:',failFetch:true});fileApp.ids['chat-answer-mode'].value='model';fileApp.ids['chat-endpoint'].value='https://api.example/v1';fileApp.ids['chat-api-key'].value='k';fileApp.ids['chat-fetch-models'].fire('click');await new Promise(r=>setImmediate(r));
    assert(String(fileApp.ids['chat-fetch-note'].textContent).includes('chat_server.py')||String(fileApp.ids['chat-status'].textContent).includes('chat_server.py'));
   const proxyApp=setup({});proxyApp.ids['chat-answer-mode'].value='model';proxyApp.ids['chat-endpoint'].value='https://api.example/v1';proxyApp.ids['chat-api-key'].value='k';proxyApp.ids['chat-fetch-models'].fire('click');await new Promise(r=>setImmediate(r));
   assert(proxyApp.fetches.some(u=>u.includes('/api/models')));
   assert.equal(proxyApp.ids['chat-model'].value,'gpt-test');
  app.ids['chat-model'].value='gpt-test';app.ids['chat-form'].fire('submit');
  assert(app.ids['chat-messages'].children.some(b=>b.className==='chat-bubble pending'));
  assert.equal(app.ids['chat-send'].textContent,'回答中…');
  await new Promise(r=>setImmediate(r));
   assert.equal(app.calls(),2);assert.equal(app.ids['chat-input'].value,'等级开放');assert(!JSON.stringify(storage).includes('DO-NOT-STORE'));
  assert(!app.ids['chat-messages'].children.some(b=>b.className==='chat-bubble pending'));
 app.ids['chat-clear'].fire('click');app.windowListeners.pagehide();const cleared=setup(storage);assert.equal(cleared.ids['chat-input'].value,'');
   const pendingStorage={};const pending=setup(pendingStorage);pending.ids['chat-answer-mode'].value='model';pending.ids['chat-model'].value='gpt-test';pending.ids['chat-input'].value='等级开放';pending.ids['chat-form'].fire('submit');pending.windowListeners.pagehide();
  const resumed=setup(pendingStorage);assert.equal(resumed.ids['chat-input'].value,'等级开放','navigation during request must retain question');
 assert(resumed.ids['chat-messages'].children.some(b=>b.children.some(t=>t.textContent.includes('中断'))),'interrupted request needs recovery guidance');
  console.log('PASS: evidence, scoped continuity, draft, auto-consent, pending status, failure restore, no key storage, clear');
})().catch(e=>{console.error(e);process.exitCode=1;});
