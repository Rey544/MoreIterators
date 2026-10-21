/* Document history shared by all editors. Server revisions are owned by adapters. */
'use strict';
(function(root){
 function createHistory({limit=60,maxBytes=32*1024*1024,now=()=>Date.now(),changed=()=>{}}={}){
  let adapter=null,current=null,restoring=false,pending=false,context=null,interaction=0;
  const documents=new Map(),clone=value=>JSON.parse(JSON.stringify(value));
  const key=()=>String(adapter?.key?.()||'');
  function read(){const data=clone(adapter.capture());return {data,json:JSON.stringify(data),group:null,time:now()};}
  function trim(state){let bytes=state.entries.reduce((n,e)=>n+e.json.length*2,0);while(state.entries.length>2&&(state.entries.length>limit+1||bytes>maxBytes)){bytes-=state.entries.shift().json.length*2;state.index--;}}
  function reset(){if(restoring||!adapter||!key())return;const id=key(),entry=read(),previous=documents.get(id);current=previous&&previous.entries[previous.index]?.json===entry.json?previous:{id,entries:[entry],index:0};documents.set(id,current);pending=false;context=null;changed();}
  function flush(){
   if(!pending||restoring||!adapter)return;pending=false;
   if(!current||current.id!==key()){reset();return;}
   const entry=read(),last=current.entries[current.index];if(entry.json===last.json)return;
   entry.group=context&&now()-context.time<1200?context.id:null;
   const merge=entry.group&&current.index>0&&current.index===current.entries.length-1&&last.group===entry.group&&entry.time-last.time<900;
   current.entries.splice(current.index+1);
   if(merge)current.entries[current.index]=entry;else{current.entries.push(entry);current.index++;}
   trim(current);changed();
  }
  function notify(){if(restoring||!adapter||!key())return;pending=true;queueMicrotask(flush);}
  function rebase(){if(restoring||!adapter)return;flush();if(!current||current.id!==key()){reset();return;}const entry=read();current.entries[current.index]=entry;trim(current);changed();}
  async function step(direction){
   if(restoring||!adapter||adapter.busy?.())return false;flush();
   if(!current||current.id!==key())return false;
   const next=current.index+(direction<0?-1:1);if(next<0||next>=current.entries.length)return false;
   const state=current,id=key(),before=clone(state.entries[state.index].data);restoring=true;context=null;changed();
   try{await adapter.restore(clone(state.entries[next].data));if(id!==key())throw Error(root.MI18n?.t('undo.documentChanged')||'The edited document changed during undo.');state.index=next;state.entries[next]={...read(),group:null};return true;}
   catch(error){if(id===key()){try{await adapter.restore(before);}catch(rollbackError){adapter.onError?.(rollbackError);}}adapter.onError?.(error);return false;}
   finally{restoring=false;pending=false;changed();}
  }
  return {register(value){adapter=value;current=null;pending=false;},reset,rebase,changed:notify,flush,step,undo:()=>step(-1),redo:()=>step(1),
   group(id){if(id==null){interaction++;context=null;}else context={id:interaction+':'+id,time:now()};},
   get restoring(){return restoring;},get busy(){return restoring;},
   get state(){return {undo:!!current&&current.index>0,redo:!!current&&current.index<current.entries.length-1,busy:restoring};}};
 }
 if(typeof module!=='undefined')module.exports={createHistory};
 if(!root.document)return;
 const document=root.document,ids=new WeakMap(),tracked=new WeakSet();let serial=0,eventTarget=null;
 const field=node=>node?.matches?.('input:not([type=button]):not([type=submit]),textarea,[contenteditable=true]');
 const engine=createHistory({changed:()=>{
  document.dispatchEvent(new CustomEvent('mi-undo-state',{detail:engine.state}));
  for(const [id,enabled] of [['undo',engine.state.undo],['redo',engine.state.redo],['editorUndo',engine.state.undo],['editorRedo',engine.state.redo]]){const button=document.getElementById(id);if(button)button.disabled=!enabled||engine.busy;}
 }});
 const notify=engine.changed;engine.changed=()=>{if(eventTarget&&field(eventTarget))tracked.add(eventTarget);notify();};
 document.addEventListener('input',event=>{eventTarget=event.target;if(!ids.has(eventTarget))ids.set(eventTarget,++serial);engine.group('field-'+ids.get(eventTarget));},true);
 document.addEventListener('click',event=>{if(!field(event.target)){engine.flush();engine.group(null);eventTarget=null;}},true);
 document.addEventListener('focusout',()=>{engine.flush();engine.group(null);eventTarget=null;},true);
 document.addEventListener('keydown',event=>{
  if(!(event.ctrlKey||event.metaKey)||event.altKey||event.repeat||event.isComposing||document.querySelector('dialog[open]'))return;
  const key=event.key.toLowerCase();if(key!=='z'&&key!=='y')return;
  if(field(event.target)&&!tracked.has(event.target))return;
  event.preventDefault();event.stopImmediatePropagation();engine.step(key==='z'&&!event.shiftKey?-1:1);
 },true);
 root.MIUndo=engine;
})(typeof window==='undefined'?globalThis:window);
