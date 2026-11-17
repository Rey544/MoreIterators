'use strict';
(()=>{
 if(window.MIStudioPageSession)return;
 window.MIStudioPageSession=true;
 const url='/api/studio-session';
 let id='',sequence=0,closed=true,timer=0,enabled=true;
 const token=()=>Array.from(crypto.getRandomValues(new Uint8Array(16)),value=>value.toString(16).padStart(2,'0')).join('');
 function send(event,beacon=false){
  if(!enabled)return;
  const body=JSON.stringify({event,id,sequence:++sequence});
  if(beacon){
   try{if(navigator.sendBeacon(url,new Blob([body],{type:'application/json'})))return;}catch{}
  }
  fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body,keepalive:true}).then(response=>{
   if(response.status===404){enabled=false;clearInterval(timer);}
  }).catch(()=>{});
 }
 function open(){
  if(!closed)return;
  id=token();sequence=0;closed=false;send('open');
  clearInterval(timer);timer=setInterval(()=>{if(!closed)send('open');},30000);
 }
 window.addEventListener('pagehide',()=>{
  if(closed)return;
  closed=true;clearInterval(timer);send('close',true);
 });
 window.addEventListener('pageshow',open);
 document.addEventListener('visibilitychange',()=>{if(!document.hidden&&!closed)send('open');});
 open();
})();
document.addEventListener('DOMContentLoaded',()=>{
 const nodes=document.querySelectorAll('#saveState,#notice,#status,#overseerState');
 const update=node=>{
  const state=node.dataset.state||'',text=node.textContent||'';
  const failed=node.dataset.kind==='error'||node.getAttribute('role')==='alert'||node.classList.contains('error')||/失败|错误|冲突|failed|error|conflict/i.test(text);
  const unsaved=!failed&&(/^(unsaved|dirty)$/.test(state)||/^(有未保存修改|尚未保存|未保存修改|Unsaved changes|Not saved)(\s|[·：:]|$)/i.test(text.trim()));
  if(node.classList.contains('mi-unsaved')!==unsaved)node.classList.toggle('mi-unsaved',unsaved);
 };
 for(const node of nodes){update(node);new MutationObserver(()=>update(node)).observe(node,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['data-state','data-kind','role','class']});}
});
