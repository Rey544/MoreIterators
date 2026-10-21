'use strict';
const PaintLayers=(()=>{
 const MAX=32,uid=()=>globalThis.crypto?.randomUUID?.()||'layer-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2);
 const text=s=>MI18n.text(s),hardware=key=>key.startsWith('antenna')||key.startsWith('ear');
 function baseProtected(key){return !hardware(key)&&(fabricKey(key)||/^puppetHand[0-3]$/.test(key));}
 function surface(layer,index,layers){return ['inner','outer'].includes(layer.surface)?layer.surface:layers.length===4||index===0?'inner':'outer';}
 function normalize(texture,key){
  const layers=texture.layers,oldHardware=hardware(key)&&layers.length===4&&!layers.some(l=>l.surface);
  for(const [index,layer] of layers.entries()){layer.id||=uid();layer.locked??=false;layer.visible??=true;layer.opacity??=1;if(hardware(key))layer.surface??=oldHardware||index===0?'inner':'outer';}
  return texture;
 }
 function blank(key){return {symmetry:key==='collar',layers:Array.from({length:4},(_,index)=>({id:uid(),name:index?MI18n.t('default.layer_texture',{index}):MI18n.t('default.layer_base'),png:'',visible:true,locked:false,opacity:1,...(hardware(key)?{surface:index?'outer':'inner'}:{})}))};}
 function selected(key=target,index=activeLayer){return project.textures[key]?.layers[index];}
 function requireIdle(){if(typeof historyBusy!=='undefined'&&historyBusy)throw Error(text('请等待撤销完成。'));}
 function requireWritableTexture(key){if(project.textures[key]?.layers.some(layer=>layer.locked))throw Error(text('目标贴图含锁定图层，请先解锁。'));}
 function requireEditable(key=target,index=activeLayer){
  requireIdle();const layer=selected(key,index);if(!layer)throw Error(text('请选择图层'));if(layer.locked)throw Error(text('当前图层已锁定，请先解锁。'));
  if(hardware(key)&&project.editor?.headTextureMirror?.[HeadSegments.prefix(key)])requireWritableTexture(key.slice(0,-1)+(key.endsWith('L')?'R':'L'));
  return layer;
 }
 function requireBaseInitialization(key){
  if(/^puppetHand[0-3]$/.test(key)&&!project.textures[key].editableBase)requireEditable(key,0);
 }
 async function prepareMetadata(key,id){
  const owner=project;let index=project.textures[key]?.layers.findIndex(l=>l.id===id)??-1;
  if(index<0)throw Error(text('请选择图层'));
  if(/^puppetHand[0-3]$/.test(key)&&!project.textures[key].editableBase){
   requireBaseInitialization(key);if(!await HandTextureBase.prepare(key))throw Error(MI18n.t('hand.textureLoading'));
   if(project!==owner)throw Error(text('项目已切换，请重试。'));
   index=project.textures[key]?.layers.findIndex(l=>l.id===id)??-1;if(index<0)throw Error(text('请选择图层'));
   requireBaseInitialization(key);if(!HandTextureBase.ensure(key))throw Error(MI18n.t('hand.textureLoading'));
  }
  return project.textures[key].layers[index];
 }
 function layerName(layer,index,key){
  if(baseProtected(key)&&index===0)return MI18n.t('default.layer_base');
  if(hardware(key)&&!layer.customName&&['内层（后）','外层（前）','Inner (back)','Outer (front)','Inner layer (back)','Outer layer (front)'].includes(layer.name))return MI18n.t(index?'default.layer_texture':'default.layer_base',{index});
  return HeadSegments.layerLabel(layer,index,false);
 }
 function indices(texture,key){const order=texture.layers.map((_,i)=>i);return hardware(key)?order.filter(i=>surface(texture.layers[i],i,texture.layers)==='inner').concat(order.filter(i=>surface(texture.layers[i],i,texture.layers)==='outer')):order;}
 function snapshot(key=target,index=activeLayer){const tex=project.textures[key],entry={target:key,selectedTarget:PuppetArms.selectedTarget(key),layer:index,stack:true,texture:{...structuredClone(tex),layers:tex.layers.map((layer,i)=>({...layer,png:canvases[key][i].toDataURL()}))}};if(/^puppetHand[0-3]$/.test(key)){const arm=project.design.puppetArms[+key.slice(-1)];entry.handSettings={handTextureEnabled:arm.handTextureEnabled,handTextureTint:arm.handTextureTint};}return entry;}
 function requireHistory(entry){
  const targets=entry.sleeves?Object.keys(entry.textures):[entry.target];
  for(const key of targets){const current=project.textures[key];if(!current)throw Error(text('贴图已不存在'));
   const old=entry.sleeves?entry.textures[key]:entry.texture;
   for(const [i,layer] of current.layers.entries()){if(!layer.locked)continue;
    if(!old)throw Error(text('撤销涉及锁定图层，请先解锁。'));
    const oldIndex=old.layers.findIndex(l=>l.id===layer.id),previous=old.layers[oldIndex];
    const png=entry.sleeves?entry.canvases[key][oldIndex]?.toDataURL():previous?.png;
    if(!previous||png!==canvases[key][i].toDataURL()||previous.surface!==layer.surface||previous.opacity!==layer.opacity||i===0&&current.editableBase!==old.editableBase)throw Error(text('撤销涉及锁定图层，请先解锁。'));
   }
   if(hardware(key)&&project.editor?.headTextureMirror?.[HeadSegments.prefix(key)]&&project.textures[key.slice(0,-1)+(key.endsWith('L')?'R':'L')]?.layers.some(l=>l.locked))throw Error(text('目标贴图含锁定图层，请先解锁。'));
  }
 }
 function preserveLocks(key,texture){const locks=new Map(project.textures[key].layers.map(l=>[l.id,l.locked]));for(const layer of texture.layers)if(locks.has(layer.id))layer.locked=locks.get(layer.id);return texture;}
 async function restore(entry){
  requireHistory(entry);const owner=project,key=entry.target,tex=structuredClone(entry.texture),buffers=[];
  for(const layer of tex.layers){const c=canvas(...dimensions[key]);if(layer.png){const image=new Image();image.src=layer.png;await image.decode();c.getContext('2d').drawImage(image,0,0);}buffers.push(c);}
  // Recheck after decoding so a lock changed during an async restore is respected.
  if(project!==owner)throw Error(text('项目已切换，请重试。'));
  requireHistory(entry);preserveLocks(key,tex);
  project.textures[key]=tex;canvases[key]=buffers;if(entry.handSettings)Object.assign(project.design.puppetArms[+key.slice(-1)],entry.handSettings);
 }
 function append(key=target,withHistory=true){requireIdle();if(hardware(key)&&project.editor?.headTextureMirror?.[HeadSegments.prefix(key)])requireWritableTexture(key.slice(0,-1)+(key.endsWith('L')?'R':'L'));const tex=project.textures[key];if(tex.layers.length>=MAX)throw Error(text('最多 32 个图层'));if(withHistory)checkpoint();const index=tex.layers.length,l={id:uid(),name:MI18n.t('default.layer_texture',{index}),png:'',visible:true,locked:false,opacity:1};if(hardware(key))l.surface=surface(tex.layers[activeLayer]||tex.layers[0],activeLayer,tex.layers);tex.layers.push(l);canvases[key].push(canvas(...dimensions[key]));return index;}
 function remove(){const tex=project.textures[target];requireEditable();if(tex.layers.length===1||baseProtected(target)&&activeLayer===0)return;checkpoint();tex.layers.splice(activeLayer,1);canvases[target].splice(activeLayer,1);activeLayer=Math.min(activeLayer,tex.layers.length-1);updateTarget();changed();}
 function copyTexture(from,to,mirror=true){
  if(!canvases[from]||!canvases[to]||from===to)return;
  requireWritableTexture(to);const source=project.textures[from],dest={...structuredClone(source),layers:[]},buffers=[];
  for(const [i,layer] of source.layers.entries()){const c=canvas(...dimensions[to]),ctx=c.getContext('2d');ctx.imageSmoothingEnabled=false;ctx.save();if(mirror){ctx.translate(c.width,0);ctx.scale(-1,1);}ctx.drawImage(canvases[from][i],0,0,c.width,c.height);ctx.restore();dest.layers.push({...layer,id:uid(),locked:false,png:c.toDataURL()});buffers.push(c);}
  project.textures[to]=dest;canvases[to]=buffers;
 }
 const icons={eye:'<path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',hidden:'<path d="m3 3 18 18M10 6.2c.7-.1 1.3-.2 2-.2 6.5 0 10 6 10 6a19 19 0 0 1-3.4 3.8M6.4 7.6A20 20 0 0 0 2 12s3.5 6 10 6c1.6 0 3-.4 4.3-.9"/>',lock:'<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',unlock:'<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 7.5-2"/>'};
 function iconButton(kind,label){const button=document.createElement('button');button.type='button';button.title=label;button.setAttribute('aria-label',label);button.innerHTML='<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+icons[kind]+'</svg>';return button;}
 function render(list,key=target){
  const tex=project.textures[key];list.replaceChildren();for(const index of indices(tex,key).reverse()){const layer=tex.layers[index],name=layerName(layer,index,key),row=document.createElement('div');row.className='layer'+(index===activeLayer?' active':'');row.dataset.layerId=layer.id;
   const eye=iconButton(layer.visible?'eye':'hidden',text(layer.visible?'隐藏图层':'显示图层'));eye.className='layer-eye';eye.setAttribute('aria-pressed',String(layer.visible));eye.onclick=run(async()=>{stroke=null;const owner=project,current=await prepareMetadata(key,layer.id);if(project!==owner||!project.textures[key]?.layers.includes(current))throw Error(text('项目或贴图已改变，请重试。'));current.visible=!current.visible;PuppetArms.textureChanged(key);updateTarget();changed();});
   const lock=iconButton(layer.locked?'lock':'unlock',text(layer.locked?'解锁图层':'锁定图层'));lock.className='layer-lock';lock.setAttribute('aria-pressed',String(layer.locked));lock.onclick=()=>{stroke=null;layer.locked=!layer.locked;updateTarget();markDirty();renderPaintOnly();};
   const select=document.createElement('button');select.className='layer-name';select.textContent=name;MI18n.content(select);select.onclick=()=>{stroke=null;activeLayer=index;updateTarget();};
   const opacity=document.createElement('input');opacity.type='range';opacity.className='layer-opacity';opacity.min=0;opacity.max=1;opacity.step=.05;opacity.value=layer.opacity;opacity.disabled=layer.locked;opacity.setAttribute('aria-label',MI18n.t('head28.opacity',{name}));opacity.oninput=run(async()=>{requireEditable(key,index);const value=Number(opacity.value),current=await prepareMetadata(key,layer.id),at=project.textures[key].layers.indexOf(current);requireEditable(key,at);current.opacity=value;PuppetArms.textureChanged(key);changed();});row.append(eye,lock,select,opacity);
   list.append(row);
  }
  let hint=$('layerMaskHint');if(!hint){hint=document.createElement('p');hint.id='layerMaskHint';hint.className='layer-mask-hint';list.before(hint);}hint.hidden=!hardware(key);if(hardware(key)){const selected=tex.layers[activeLayer];hint.textContent=MI18n.t('paint.maskHint',{mask:MI18n.t(surface(selected||tex.layers[0],activeLayer,tex.layers)==='inner'?'paint.innerMask':'paint.outerMask')});}
  if($('layerAdd')){$('layerAdd').disabled=tex.layers.length>=MAX;$('layerAdd').onclick=run(()=>{stroke=null;activeLayer=append();updateTarget();changed();});}
  if($('layerDelete')){$('layerDelete').disabled=tex.layers.length<=1||selected()?.locked||baseProtected(key)&&activeLayer===0;$('layerDelete').onclick=run(remove);}
 }
 function renderPaintOnly(){if(typeof globalThis.requestAnimationFrame==='function')requestAnimationFrame(()=>{drawPaint();});}
 return {MAX,blank,normalize,surface,indices,baseProtected,requireEditable,requireBaseInitialization,requireWritableTexture,requireHistory,preserveLocks,snapshot,restore,append,remove,copyTexture,render};
})();
