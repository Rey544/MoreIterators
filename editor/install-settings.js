'use strict';
(()=>{
 let dialog, title, status, close, entries={}, busy=false;
 const tr=key=>MI18n.t('paths.'+key);
 function element(tag,text,cls){const value=document.createElement(tag);if(text!==undefined)value.textContent=text;if(cls)value.className=cls;return value;}
 function render(){
  title.textContent=tr('title');close.textContent=tr('close');
  for(const [kind,row] of Object.entries(entries)){
   row.label.textContent=tr(kind);row.button.textContent=tr('choose');
   row.button.setAttribute('aria-label',tr('choose')+' '+tr(kind));
   row.button.disabled=busy;row.path.textContent=row.value?.found?row.value.path:tr('missing');
   row.path.title=row.value?.found?row.value.path:'';
  }
 }
 function fill(data){for(const kind of Object.keys(entries))entries[kind].value=data[kind];render();}
 async function select(kind){
  busy=true;status.textContent='';render();
  try{
   const response=await fetch('/api/install-paths/select',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind})});
   const data=await response.json();if(!response.ok)throw Error(MI18n.error(data,response.statusText));
   if(!data.cancelled)fill(data);
  }catch(error){status.textContent=error.message;}
  finally{busy=false;render();}
 }
 function mount(){
  if(dialog)return;
  dialog=MI18n.content(element('dialog',undefined,'mi-about mi-install-settings'));dialog.id='miInstallSettings';dialog.setAttribute('aria-labelledby','miPathsTitle');
  const head=element('div',undefined,'mi-about-heading');title=element('h2');title.id='miPathsTitle';head.append(title);
  const body=element('div',undefined,'mi-paths-body');
  for(const kind of ['game','rained']){
   const row=element('div',undefined,'mi-path-row'),label=element('span',undefined,'mi-path-label'),path=element('span',undefined,'mi-path-value'),button=element('button');
   button.type='button';button.onclick=()=>select(kind);row.append(label,path,button);body.append(row);entries[kind]={label,path,button};
  }
  status=element('p',undefined,'mi-path-status');status.setAttribute('role','status');body.append(status);
  const actions=element('div',undefined,'mi-about-actions');close=element('button');close.type='button';close.onclick=()=>dialog.close();actions.append(close);
  dialog.append(head,body,actions);document.body.append(dialog);render();
 }
 async function open(){
  await MI18n.ready;mount();if(!dialog.open)dialog.showModal();status.textContent='';busy=true;render();
  try{const response=await fetch('/api/install-paths',{cache:'no-store'});const data=await response.json();if(!response.ok)throw Error(MI18n.error(data,response.statusText));fill(data);}
  catch(error){status.textContent=error.message;}
  finally{busy=false;render();}
 }
 window.MIInstallSettings={open};
 window.addEventListener('mi-language-change',()=>{if(dialog)render();});
})();
