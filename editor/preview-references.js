'use strict';
const PreviewReferences=(()=>{
 const stage=document.getElementById('previewStage'),puppet=document.getElementById('puppet'),actions=document.querySelector('.preview-actions');
 if(!stage||!puppet||!actions)return {sync(){}};
 const tr=(key,params)=>MI18n.t('previewReferences.'+key,params),clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
 const button=document.createElement('button'),input=document.createElement('input'),back=document.createElement('div'),front=document.createElement('div'),indicator=document.createElement('span');
 button.id='addPreviewReference';button.type='button';button.dataset.i18n='previewReferences.add';input.type='file';input.accept='image/png,image/jpeg,image/webp,image/gif,image/bmp';input.multiple=true;input.hidden=true;
 back.className='preview-reference-layer reference-back';front.className='preview-reference-layer reference-front';indicator.className='preview-reference-axis';indicator.hidden=true;indicator.setAttribute('aria-hidden','true');
 stage.tabIndex=0;stage.prepend(back);stage.append(front,indicator);actions.append(button,input);
 let owner=null,generation=0,items=[],selected=null,hover=null,loaded=false,adding=false,database=null,writing=Promise.resolve(),moving=null,pointer=null,menu=null,suppressContext=0,fileOwner=null,referencePointer=null,highlightMask=null;
 const elements=new Map(),masks=new Map();
 function current(){return window.MIStudioPage?.projectId?.()||null;}
 function busy(){return window.MIStudioPage?.isBusy?.()??true;}
 function fail(key){window.MIStudioPage?.error?.(tr(key));}
 function db(){
  if(database)return database;
  database=new Promise((resolve,reject)=>{
   const request=indexedDB.open('moreiterators.previewReferences.v1',1);
   request.onupgradeneeded=()=>{const value=request.result;if(!value.objectStoreNames.contains('projects'))value.createObjectStore('projects');};
   request.onsuccess=()=>{const value=request.result;value.onversionchange=()=>{value.close();database=null;};resolve(value);};
   request.onerror=()=>reject(request.error);request.onblocked=()=>reject(Error('blocked'));
  }).catch(error=>{database=null;throw error;});return database;
 }
 async function read(id){const value=await db();return new Promise((resolve,reject)=>{const tx=value.transaction('projects','readonly'),request=tx.objectStore('projects').get(id);request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);tx.onabort=()=>reject(tx.error);});}
 async function write(id,data){const value=await db();return new Promise((resolve,reject)=>{const tx=value.transaction('projects','readwrite');tx.objectStore('projects').put(data,id);tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error);});}
 function snapshot(){return {version:1,items:items.map(({id,name,blob,width,height,x,y,z,scale,rotation,opacity,front})=>({id,name,blob,width,height,x,y,z,scale,rotation,opacity,front}))};}
 function save(){
  if(!loaded||!owner)return Promise.resolve();const id=owner,data=snapshot();
  writing=writing.catch(()=>{}).then(()=>write(id,data));writing.catch(()=>{if(owner===id)fail('saveFailed');});return writing;
 }
 function release(){for(const item of items)URL.revokeObjectURL(item.url);items=[];elements.clear();masks.clear();highlightMask=null;back.replaceChildren();front.replaceChildren();selected=null;hover=null;}
 function valid(raw){
  if(!raw||typeof raw.id!=='string'||typeof raw.name!=='string'||!(raw.blob instanceof Blob)||!['width','height','x','y','z','opacity'].every(key=>Number.isFinite(raw[key])))return false;
  return raw.width>0&&raw.height>0&&raw.width<=8192&&raw.height<=8192&&raw.blob.size<=24*1024*1024&&(raw.scale===undefined||Number.isFinite(raw.scale))&&(raw.rotation===undefined||Number.isFinite(raw.rotation));
 }
 function visibleRect(item){
  const box=stage.getBoundingClientRect(),depth=600/(600-item.z),base=Math.min(box.width*.42,box.height*.65*item.width/item.height),w=base*depth*item.scale,h=w*item.height/item.width,cx=box.left+box.width*(.5+item.x),cy=box.top+box.height*(.5+item.y);
  return {left:cx-w/2,top:cy-h/2,width:w,height:h,cx,cy,angle:item.rotation*Math.PI/180};
 }
 function cacheMask(item,image){
  if(masks.has(item.id)||!items.includes(item)||!image.naturalWidth||!image.naturalHeight)return;
  try{
   const ratio=Math.min(1,1024/Math.max(image.naturalWidth,image.naturalHeight)),canvas=document.createElement('canvas');canvas.width=Math.max(1,Math.round(image.naturalWidth*ratio));canvas.height=Math.max(1,Math.round(image.naturalHeight*ratio));
   const paint=canvas.getContext('2d',{willReadFrequently:true});paint.drawImage(image,0,0,canvas.width,canvas.height);
   const pixels=paint.getImageData(0,0,canvas.width,canvas.height),alpha=new Uint8Array(canvas.width*canvas.height);for(let i=0;i<alpha.length;i++){alpha[i]=pixels.data[i*4+3];pixels.data[i*4]=pixels.data[i*4+1]=pixels.data[i*4+2]=255;}paint.putImageData(pixels,0,0);masks.set(item.id,{canvas,alpha,width:canvas.width,height:canvas.height});render();
  }catch{masks.set(item.id,null);}
 }
 function createElement(item){
  const holder=document.createElement('span'),image=document.createElement('img');holder.className='preview-reference';holder.dataset.referenceId=item.id;image.onload=()=>cacheMask(item,image);image.src=item.url;image.alt=item.name;image.draggable=false;MI18n.content(image);holder.append(image);elements.set(item.id,holder);(item.front?front:back).append(holder);return holder;
 }
 function paintHighlight(item,holder,rect,box){
  const active=selected===item.id,over=hover===item.id,cached=masks.get(item.id),style=typeof PreviewSelection==='undefined'?null:PreviewSelection.highlightStyle?.();
  let fill=holder.querySelector('.reference-highlight-fill'),outline=holder.querySelector('.reference-highlight-outline');
  if(!active&&!over){fill?.remove();outline?.remove();return;}if(!cached||!style){if(fill)fill.hidden=true;if(outline)outline.hidden=true;return;}
  if(!fill){fill=document.createElement('canvas');outline=document.createElement('canvas');fill.className='reference-highlight-fill';outline.className='reference-highlight-outline';for(const layer of [fill,outline]){layer.setAttribute('aria-hidden','true');holder.append(layer);}}
  const ratio=Math.min(2,window.devicePixelRatio||1,4096/Math.max(1,box.width,box.height)),width=Math.max(1,Math.round(box.width*ratio)),height=Math.max(1,Math.round(box.height*ratio)),dx=width/Math.max(1,box.width),dy=height/Math.max(1,box.height);
  if(!highlightMask)highlightMask=document.createElement('canvas');if(highlightMask.width!==width)highlightMask.width=width;if(highlightMask.height!==height)highlightMask.height=height;
  const paint=highlightMask.getContext('2d');paint.clearRect(0,0,width,height);paint.save();paint.scale(dx,dy);paint.translate(rect.cx-box.left,rect.cy-box.top);paint.rotate(rect.angle);paint.imageSmoothingEnabled=true;paint.imageSmoothingQuality='high';paint.drawImage(cached.canvas,-rect.width/2,-rect.height/2,rect.width,rect.height);paint.restore();paint.globalCompositeOperation='source-in';paint.fillStyle=style.color;paint.fillRect(0,0,width,height);paint.globalCompositeOperation='source-over';
  for(const layer of [fill,outline]){if(layer.width!==width)layer.width=width;if(layer.height!==height)layer.height=height;layer.style.left=(box.left-rect.left)+'px';layer.style.top=(box.top-rect.top)+'px';layer.style.width=box.width+'px';layer.style.height=box.height+'px';layer.getContext('2d').clearRect(0,0,width,height);}
  const fillPaint=fill.getContext('2d');fillPaint.save();fillPaint.globalAlpha=active?style.selectedOpacity:style.hoverOpacity;fillPaint.drawImage(highlightMask,0,0);fillPaint.restore();fill.hidden=false;outline.hidden=!over;if(over)PreviewSelection.paintOutline(outline.getContext('2d'),highlightMask,dx,dy);
 }
 function render(){
  const box=stage.getBoundingClientRect();
  for(const item of items){const holder=elements.get(item.id)||createElement(item),rect=visibleRect(item),layer=item.front?front:back;
   layer.append(holder);
   holder.style.left=(rect.left-box.left)+'px';holder.style.top=(rect.top-box.top)+'px';holder.style.width=rect.width+'px';holder.style.height=rect.height+'px';holder.classList.toggle('selected',selected===item.id);holder.classList.toggle('hovered',hover===item.id);holder.firstElementChild.style.opacity=String(item.opacity);holder.firstElementChild.style.transform='rotate('+item.rotation+'deg)';paintHighlight(item,holder,rect,box);
  }
  indicator.hidden=!moving||moving.drag;
  if(moving&&!moving.drag){indicator.textContent='G'+(moving.axis?' '+moving.axis.toUpperCase():'')+(moving.number?' '+moving.number:'');indicator.dataset.axis=moving.axis||'';}
 }
 function closeMenu(){menu?.remove();menu=null;}
 function endMove(commit){
  if(!moving)return;const state=moving,item=items.find(row=>row.id===state.id);moving=null;
  const captured=referencePointer;referencePointer=null;if(captured!==null&&stage.hasPointerCapture(captured))stage.releasePointerCapture(captured);
  if(item&&!commit)Object.assign(item,state.original);
  render();if(commit)save();
 }
 async function load(id,token){
  try{
   await writing.catch(()=>{});const data=await read(id);
   if(owner!==id||generation!==token)return;
   if(data&& (data.version!==1||!Array.isArray(data.items)||!data.items.every(valid)))throw Error('invalid');
   items=(data?.items||[]).map(row=>({...row,x:clamp(row.x,-10,10),y:clamp(row.y,-10,10),z:clamp(row.z,-1800,480),scale:clamp(row.scale??1,.1,4),rotation:clamp(row.rotation??0,-180,180),opacity:clamp(row.opacity,0,1),front:row.front===true,url:URL.createObjectURL(row.blob)}));
   selected=items.find(item=>item.opacity===0)?.id||null;loaded=true;render();refreshButton();
  }catch{if(owner===id&&generation===token){loaded=false;refreshButton();fail('loadFailed');}}
 }
 function refreshButton(){button.textContent=tr('add');button.disabled=!owner||!loaded||busy()||adding;}
 function sync(){
  const id=current(),blocked=busy();
  back.hidden=front.hidden=blocked;refreshButton();
  if(blocked){hover=null;endMove(false);closeMenu();render();return;}
  if(id===owner)return;
  generation++;endMove(false);closeMenu();release();owner=id;loaded=false;refreshButton();
  if(id)load(id,generation);
 }
 function select(id){selected=id;closeMenu();if(id){if(typeof PreviewSelection!=='undefined')PreviewSelection.clear?.();stage.focus({preventScroll:true});}render();}
 function contains(item,x,y){
  if(item.opacity===0&&selected!==item.id)return false;const r=visibleRect(item),dx=x-r.cx,dy=y-r.cy,c=Math.cos(r.angle),s=Math.sin(r.angle),u=(c*dx+s*dy)/r.width+.5,v=(-s*dx+c*dy)/r.height+.5;if(u<0||u>=1||v<0||v>=1)return false;
  const cached=masks.get(item.id);if(!cached)return false;return cached.alpha[(Math.floor(v*cached.height)*cached.width+Math.floor(u*cached.width))]>8;
 }
 function setHover(id){if(hover===id)return;hover=id;if(id&&typeof PreviewSelection!=='undefined')PreviewSelection.leave();render();}
 function hit(event){
  if(!loaded||busy())return null;
  const candidates=[...items].reverse(),foreground=candidates.find(item=>item.front&&contains(item,event.clientX,event.clientY));if(foreground)return foreground;
  const box=puppet.getBoundingClientRect(),point=[(event.clientX-box.left)*puppet.width/Math.max(1,box.width),(event.clientY-box.top)*puppet.height/Math.max(1,box.height)];
  if(typeof PreviewSelection!=='undefined'&&PreviewSelection.hits(point).length)return null;
  return candidates.find(item=>!item.front&&contains(item,event.clientX,event.clientY))||null;
 }
 function consume(event){event.preventDefault();event.stopImmediatePropagation();}
 function updateMove(event){
  if(!moving)return;const item=items.find(row=>row.id===moving.id);if(!item||owner!==moving.owner||busy()){endMove(false);return;}
  pointer={x:event.clientX,y:event.clientY};const rect=stage.getBoundingClientRect(),dx=pointer.x-moving.start.x,dy=pointer.y-moving.start.y,n=Number(moving.number),numeric=moving.number!==''&&Number.isFinite(n),base=moving.original;
  item.x=base.x;item.y=base.y;item.z=base.z;
  if(moving.axis==='z')item.z=clamp(base.z+(numeric?n:-dy),-1800,480);
  else if(moving.axis==='x')item.x=clamp(base.x+(numeric?n:dx)/Math.max(1,rect.width),-10,10);
  else if(moving.axis==='y')item.y=clamp(base.y+(numeric?-n:dy)/Math.max(1,rect.height),-10,10);
  else{item.x=clamp(base.x+dx/Math.max(1,rect.width),-10,10);item.y=clamp(base.y+dy/Math.max(1,rect.height),-10,10);}
  hover=pointer.x>=rect.left&&pointer.x<=rect.right&&pointer.y>=rect.top&&pointer.y<=rect.bottom&&contains(item,pointer.x,pointer.y)?item.id:null;
  render();
 }
 function startMove(drag=false){
  const item=items.find(row=>row.id===selected);if(!item||busy())return;
  const rect=visibleRect(item);closeMenu();moving={id:item.id,owner,start:pointer||{x:rect.left+rect.width/2,y:rect.top+rect.height/2},original:{x:item.x,y:item.y,z:item.z},axis:null,number:'',drag};render();
 }
 function adjustment(item,key,min,max,unit,value,apply){
  const row=document.createElement('div'),caption=document.createElement('span'),range=document.createElement('input'),amount=document.createElement('input'),field=document.createElement('span'),suffix=document.createElement('span');row.className='reference-adjustment';caption.textContent=tr(key);range.type='range';amount.type='number';field.className='reference-adjustment-value';suffix.textContent=unit;
  for(const control of [range,amount]){control.min=min;control.max=max;control.step=1;control.value=Math.round(value);control.setAttribute('aria-label',tr(key));control.oninput=()=>{if(owner!==current()||!items.includes(item)||busy()||control.value==='')return;const n=Number(control.value);if(!Number.isFinite(n))return;const next=clamp(n,min,max);range.value=String(next);if(control===range)amount.value=range.value;apply(next);render();};control.onchange=()=>{if(owner!==current()||!items.includes(item)||busy())return;amount.value=range.value;apply(Number(range.value));render();save();};}
  field.append(amount,suffix);row.append(caption,field,range);return row;
 }
 function menuAt(event,item){
  select(item.id);menu=document.createElement('div');menu.className='preview-reference-menu';menu.setAttribute('role','menu');
  for(const [key,value] of [['front',true],['back',false]]){const control=document.createElement('button');control.type='button';control.textContent=tr(key);control.setAttribute('role','menuitemradio');control.setAttribute('aria-checked',String(item.front===value));control.onclick=()=>{if(owner!==current())return;item.front=value;render();save();closeMenu();stage.focus({preventScroll:true});};menu.append(control);}
  const label=document.createElement('label'),caption=document.createElement('span'),range=document.createElement('input'),amount=document.createElement('output');label.className='reference-opacity';caption.textContent=tr('opacity');range.type='range';range.min=0;range.max=100;range.step=1;range.value=Math.round(item.opacity*100);range.setAttribute('aria-label',tr('opacity'));amount.value=range.value+'%';range.oninput=()=>{if(owner!==current())return;item.opacity=Number(range.value)/100;amount.value=range.value+'%';render();};range.onchange=save;label.append(caption,range,amount);menu.append(label);
  menu.append(adjustment(item,'size',10,400,'%',item.scale*100,value=>{item.scale=value/100;}),adjustment(item,'rotation',-180,180,'°',item.rotation,value=>{item.rotation=value;}));
  const reset=document.createElement('button');reset.type='button';reset.textContent=tr('reset');reset.setAttribute('role','menuitem');reset.onclick=()=>{if(owner!==current()||busy())return;Object.assign(item,{x:-.25,y:0,z:0,scale:1,rotation:0,opacity:1,front:false});hover=null;closeMenu();render();save();stage.focus({preventScroll:true});};menu.append(reset);
  const remove=document.createElement('button');remove.type='button';remove.textContent=tr('remove');remove.setAttribute('role','menuitem');remove.onclick=()=>{if(owner!==current())return;items=items.filter(row=>row!==item);elements.get(item.id)?.remove();elements.delete(item.id);masks.delete(item.id);URL.revokeObjectURL(item.url);selected=null;if(hover===item.id)hover=null;closeMenu();render();save();stage.focus({preventScroll:true});};menu.append(remove);
  document.body.append(menu);const box=menu.getBoundingClientRect();menu.style.left=clamp(event.clientX,6,Math.max(6,innerWidth-box.width-6))+'px';menu.style.top=clamp(event.clientY,6,Math.max(6,innerHeight-box.height-6))+'px';menu.firstElementChild.focus({preventScroll:true});
 }
 async function decode(file){
  if(!/^image\/(png|jpeg|webp|gif|bmp)$/.test(file.type))throw Error('invalidImage');if(file.size>24*1024*1024)throw Error('tooLarge');
  const url=URL.createObjectURL(file),image=new Image();image.src=url;
  try{await image.decode();if(!image.naturalWidth||!image.naturalHeight||image.naturalWidth>8192||image.naturalHeight>8192)throw Error('tooLarge');return {url,width:image.naturalWidth,height:image.naturalHeight};}catch(error){URL.revokeObjectURL(url);throw error.message==='tooLarge'?error:Error('invalidImage');}
 }
 button.onclick=()=>{if(button.disabled)return;fileOwner={id:owner,token:generation};input.value='';input.click();};
 input.onchange=async()=>{
  const claim=fileOwner,files=[...input.files];if(!claim||!files.length||owner!==claim.id||generation!==claim.token)return;
  adding=true;refreshButton();
  try{for(const file of files){const image=await decode(file);if(owner!==claim.id||generation!==claim.token||current()!==claim.id){URL.revokeObjectURL(image.url);return;}const item={id:crypto.randomUUID(),name:file.name,blob:file,...image,x:-.25,y:0,z:0,scale:1,rotation:0,opacity:1,front:false};items.push(item);select(item.id);await save();}}
  catch(error){if(owner===claim.id)fail(['invalidImage','tooLarge'].includes(error.message)?error.message:'saveFailed');}
  finally{adding=false;refreshButton();input.value='';}
 };
 stage.addEventListener('pointerdown',event=>{
  if(event.button!==0&&event.button!==2)return;if(event.button===2)suppressContext=0;pointer={x:event.clientX,y:event.clientY};const item=hit(event);
  if(item){consume(event);hover=item.id;select(item.id);if(event.button===0){startMove(true);referencePointer=event.pointerId;stage.setPointerCapture(event.pointerId);}}else{hover=null;if(selected){selected=null;closeMenu();}render();}
 },true);
 stage.addEventListener('pointermove',event=>{if(moving)return;if(referencePointer===event.pointerId){consume(event);return;}pointer={x:event.clientX,y:event.clientY};if(event.buttons)return;const item=hit(event);setHover(item?.id||null);if(item){event.stopImmediatePropagation();puppet.style.cursor='pointer';}},true);
 stage.addEventListener('pointerleave',()=>{setHover(null);});
 for(const type of ['pointerup','pointercancel','lostpointercapture'])stage.addEventListener(type,event=>{if(referencePointer!==event.pointerId)return;consume(event);if(type==='pointerup'&&event.button===0){updateMove(event);endMove(true);}else endMove(false);},true);
 stage.addEventListener('contextmenu',event=>{
  if(performance.now()<suppressContext){suppressContext=0;consume(event);return;}
  const item=hit(event);if(!item){setHover(null);return;}consume(event);setHover(null);menuAt(event,item);
 },true);
 document.addEventListener('pointermove',event=>{if(!moving||moving.drag&&event.pointerId!==referencePointer)return;consume(event);updateMove(event);},true);
 document.addEventListener('pointerdown',event=>{
  if(moving){consume(event);if(moving.drag&&event.pointerId!==referencePointer)return;if(event.button===0)endMove(true);else if(event.button===2){endMove(false);suppressContext=performance.now()+700;}return;}
  if(menu?.contains(event.target))return;closeMenu();if(!stage.contains(event.target)&&event.target!==button&&(selected||hover)){selected=null;hover=null;render();}
 },true);
 function typing(event){const node=event.target;return event.isComposing||node?.closest?.('input,textarea,select,[contenteditable=true],[role=textbox]')||document.querySelector('dialog[open]');}
 document.addEventListener('keydown',event=>{
  if(typing(event)||event.ctrlKey||event.metaKey||event.altKey)return;
  const key=event.key.toLowerCase();
  if(moving){
   if(key==='escape'){consume(event);endMove(false);return;}if(key==='enter'){consume(event);endMove(true);return;}
   if(moving.drag){if(['g','x','y','z'].includes(key))consume(event);return;}
   if(['x','y','z'].includes(key)){consume(event);if(event.repeat)return;moving.axis=moving.axis===key?null:key;moving.number='';updateMove({clientX:pointer?.x??moving.start.x,clientY:pointer?.y??moving.start.y});return;}
   if(moving.axis&&(/^[0-9.\-]$/.test(key)||key==='backspace')){consume(event);if(key==='.'&&moving.number.includes('.'))return;moving.number=key==='backspace'?moving.number.slice(0,-1):key==='-'?(moving.number.startsWith('-')?moving.number.slice(1):'-'+moving.number):moving.number+key;updateMove({clientX:pointer?.x??moving.start.x,clientY:pointer?.y??moving.start.y});return;}
   if(key==='g')consume(event);return;
  }
  if(key==='g'&&selected&&!event.repeat){consume(event);startMove();}
  else if(key==='escape'&&(menu||selected)){consume(event);closeMenu();select(null);}
 },true);
 document.addEventListener('wheel',event=>{if(moving)consume(event);},{capture:true,passive:false});
 window.addEventListener('blur',()=>{endMove(false);closeMenu();setHover(null);});document.addEventListener('pointercancel',event=>{if(!moving?.drag||event.pointerId===referencePointer)endMove(false);},true);window.addEventListener('resize',()=>{endMove(false);closeMenu();render();});
 window.addEventListener('mi-language-change',()=>{refreshButton();closeMenu();});
 window.addEventListener('mi-preview-highlight-change',render);
 document.addEventListener('mi-undo-state',sync);
 const observer=new MutationObserver(sync),main=document.querySelector('main'),projects=document.getElementById('projects');if(main)observer.observe(main,{attributes:true,attributeFilter:['inert']});if(projects)observer.observe(projects,{childList:true,subtree:true});
 new ResizeObserver(render).observe(stage);document.addEventListener('DOMContentLoaded',sync);MI18n.ready.then(()=>{refreshButton();sync();});sync();
 return {sync};
})();
