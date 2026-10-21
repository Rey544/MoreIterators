'use strict';
(function(root,factory){
 const api=factory();
 if(typeof module==='object'&&module.exports)module.exports=api;
 else root.IteratorWorkspace=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
 const MIN={left:240,preview:320,right:300},GUTTERS=24;
 const clamp=(value,min,max)=>Math.max(min,Math.min(max,value));
 const finite=(value,fallback)=>Number.isFinite(Number(value))?Number(value):fallback;
 function columns(width,left=280,right=520){
  const available=Math.max(width-GUTTERS,MIN.left+MIN.preview+MIN.right);
  left=Math.max(MIN.left,finite(left,280));right=Math.max(MIN.right,finite(right,520));
  const extra=left-MIN.left+right-MIN.right,budget=available-MIN.left-MIN.preview-MIN.right;
  if(extra>budget){const ratio=budget/extra;left=MIN.left+(left-MIN.left)*ratio;right=MIN.right+(right-MIN.right)*ratio;}
  return {left,preview:available-left-right,right};
 }
 function fitZoom(width,height,bounds,padding=24,min=.25,max=20){
  return clamp(Math.min(Math.max(1,width-2*padding)/Math.max(1,bounds.width),Math.max(1,height-2*padding)/Math.max(1,bounds.height)),min,max);
 }
 function layerWidth(width,wanted=128){return clamp(finite(wanted,128),96,Math.max(96,Math.min(320,width-212)));}
 function transform(width,height,zoom,center,dpr=1){
  return [zoom*dpr,0,0,zoom*dpr,(width/2-center.x*zoom)*dpr,(height/2-center.y*zoom)*dpr];
 }
 function stateFrom(value){
  value=value&&typeof value==='object'?value:{};
  return {left:Math.max(MIN.left,finite(value.left,280)),right:Math.max(MIN.right,finite(value.right,520)),
   preview:{zoom:clamp(finite(value.preview?.zoom,5),.25,20),center:{x:finite(value.preview?.center?.x,0),y:finite(value.preview?.center?.y,25)}},
   paintZoom:clamp(finite(value.paintZoom,8),.25,32),layers:clamp(finite(value.layers,128),96,320),height:value.height?clamp(finite(value.height,800),600,1800):0};
 }
 function mount({render,fitPreview}){
  const byId=id=>document.getElementById(id),main=byId('workspace'),previewStage=byId('previewStage'),paintStage=byId('paintViewport'),surface=byId('paintSurface'),puppet=byId('puppet'),paint=byId('paint');
  const key='mi.appearance.workspace.v1';let saved;
  try{saved=JSON.parse(localStorage.getItem(key)||'null');}catch{}
  const state=stateFrom(saved);let size={width:580,height:600,dpr:1},paintTarget=null,paintSize=[32,32],paintCenter={x:16,y:16},layout,frame=0,expectedScroll=null;
  const persist=()=>{try{localStorage.setItem(key,JSON.stringify(state));}catch{}};
  function localizedLabels(){
   const text=value=>globalThis.MI18n?.text(value)||value;
   for(const [id,label] of [['previewHeightDivider','上下拖动调整工作区高度'],['paintHeightDivider','上下拖动调整画布高度']]){
    const bar=byId(id);if(!bar)continue;
    bar.setAttribute('aria-label',text(label));bar.setAttribute('title',text('上下拖动调整高度 · 双击恢复'));
   }
  }
  function zoomLabels(){
   byId('zoom').value=state.preview.zoom;byId('paintZoom').value=state.paintZoom;
   if(document.activeElement!==byId('zoomValue'))byId('zoomValue').value=Math.round(state.preview.zoom*100);
   if(document.activeElement!==byId('paintZoomValue'))byId('paintZoomValue').value=Math.round(state.paintZoom*100);
   byId('zoomOut').disabled=state.preview.zoom<=.25;byId('zoomIn').disabled=state.preview.zoom>=20;
   byId('paintZoomOut').disabled=state.paintZoom<=.25;byId('paintZoomIn').disabled=state.paintZoom>=32;
  }
  function updatePaint(){
   const [w,h]=paintSize,z=state.paintZoom,dpr=Math.min(2,window.devicePixelRatio||1),width=w*z,height=h*z;
   // CSS min-size centers small images. Intrinsic image bounds never feed back
   // into the viewport measurement (especially around scrollbar thresholds).
   surface.style.width=Math.ceil(width+32)+'px';surface.style.height=Math.ceil(height+32)+'px';
   paint.style.width=width+'px';paint.style.height=height+'px';
   const pixelsW=Math.max(1,Math.round(width*dpr)),pixelsH=Math.max(1,Math.round(height*dpr));
   if(paint.width!==pixelsW)paint.width=pixelsW;if(paint.height!==pixelsH)paint.height=pixelsH;
   const surfaceWidth=surface.clientWidth,surfaceHeight=surface.clientHeight;
   paintStage.scrollLeft=(surfaceWidth-width)/2+paintCenter.x*z-paintStage.clientWidth/2;
   paintStage.scrollTop=(surfaceHeight-height)/2+paintCenter.y*z-paintStage.clientHeight/2;
   // Scroll events may arrive after the next animation frame. Match the actual
   // clamped position instead of resetting a one-frame suppression flag.
   expectedScroll={left:paintStage.scrollLeft,top:paintStage.scrollTop};
  }
  function heightFor(divider){
   if(state.height)return state.height;
   // On stacked layouts the document contains several panels; dragging one
   // canvas must start at that panel's height, not their combined height.
   return window.innerWidth<=1050?(divider?.closest('section')?.clientHeight||main.clientHeight):main.clientHeight;
  }
  function refresh(){
   frame=0;
   localizedLabels();
   main.style.setProperty('--workspace-top',main.offsetTop+'px');
   main.style.setProperty('--workspace-height',state.height?state.height+'px':'calc(100dvh - var(--workspace-top,75px) - var(--workspace-bottom-gap,10px))');
   for(const id of ['previewHeightDivider','paintHeightDivider']){const bar=byId(id);if(bar){bar.setAttribute('aria-valuemin',600);bar.setAttribute('aria-valuemax',1800);bar.setAttribute('aria-valuenow',Math.round(heightFor(bar)));}}
   layout=columns(main.clientWidth-24,state.left,state.right);
   main.style.setProperty('--settings-width',layout.left+'px');main.style.setProperty('--paint-width',layout.right+'px');
   for(const [id,value,max] of [['settingsDivider',layout.left,layout.left+layout.preview-MIN.preview],['paintDivider',layout.right,layout.right+layout.preview-MIN.preview]]){
    const bar=byId(id),count=Math.round(value);bar.setAttribute('aria-valuenow',count);bar.setAttribute('aria-valuemax',Math.round(max));bar.setAttribute('aria-valuetext',globalThis.MI18n?.t('unit.pixels',{count})||count+' 像素');
   }
   const split=byId('paintPanel').querySelector('.paint-split'),layerBar=byId('layersDivider');
   if(layerBar){const current=layerWidth(split.clientWidth,state.layers);split.style.setProperty('--paint-layers-width',current+'px');layerBar.setAttribute('aria-valuenow',Math.round(current));layerBar.setAttribute('aria-valuemax',Math.round(layerWidth(split.clientWidth,320)));layerBar.setAttribute('aria-valuetext',globalThis.MI18n?.t('unit.pixels',{count:Math.round(current)})||Math.round(current)+' 像素');}
   size={width:previewStage.clientWidth,height:previewStage.clientHeight,dpr:Math.min(2,window.devicePixelRatio||1)};
   const width=Math.max(1,Math.round(size.width*size.dpr)),height=Math.max(1,Math.round(size.height*size.dpr));
   if(puppet.width!==width)puppet.width=width;if(puppet.height!==height)puppet.height=height;
   updatePaint();render();
  }
  function schedule(){if(!frame)frame=requestAnimationFrame(refresh);}
  function resizeSide(side,value){
   if(!layout)return;
   state.left=layout.left;state.right=layout.right;
   state[side]=clamp(value,MIN[side],layout[side]+layout.preview-MIN.preview);
   refresh();persist();
  }
  for(const [id,side,direction] of [['settingsDivider','left',1],['paintDivider','right',-1]]){
   const divider=byId(id);let drag=null;
   divider.addEventListener('pointerdown',e=>{if(e.button!==0)return;e.preventDefault();drag={x:e.clientX,width:layout[side]};divider.setPointerCapture(e.pointerId);document.body.classList.add('resizing-workspace');});
   divider.addEventListener('pointermove',e=>{if(drag)resizeSide(side,drag.width+(e.clientX-drag.x)*direction);});
   const end=()=>{drag=null;document.body.classList.remove('resizing-workspace');};
   divider.addEventListener('pointerup',end);divider.addEventListener('pointercancel',end);divider.addEventListener('lostpointercapture',end);
   divider.addEventListener('keydown',e=>{
    const step=e.shiftKey?48:16;
    if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();resizeSide(side,layout[side]+(e.key==='ArrowRight'?step:-step)*direction);}
    else if(e.key==='Home'||e.key==='End'){e.preventDefault();resizeSide(side,e.key==='Home'?MIN[side]:Infinity);}
   });
   divider.addEventListener('dblclick',()=>resizeSide(side,side==='left'?280:520));
  }
  const layerBar=byId('layersDivider');
  if(layerBar){
   const split=byId('paintPanel').querySelector('.paint-split');let drag=null;
   const resize=value=>{state.layers=layerWidth(split.clientWidth,value);refresh();persist();};
   layerBar.addEventListener('pointerdown',event=>{if(event.button!==0)return;event.preventDefault();drag={x:event.clientX,width:layerWidth(split.clientWidth,state.layers)};layerBar.setPointerCapture(event.pointerId);document.body.classList.add('resizing-workspace');});
   layerBar.addEventListener('pointermove',event=>{if(drag)resize(drag.width+drag.x-event.clientX);});
   const end=()=>{drag=null;document.body.classList.remove('resizing-workspace');};for(const event of ['pointerup','pointercancel','lostpointercapture'])layerBar.addEventListener(event,end);
   layerBar.addEventListener('keydown',event=>{const step=event.shiftKey?48:16,current=layerWidth(split.clientWidth,state.layers);if(event.key==='ArrowLeft'||event.key==='ArrowRight'){event.preventDefault();resize(current+(event.key==='ArrowLeft'?step:-step));}else if(event.key==='Home'||event.key==='End'){event.preventDefault();resize(event.key==='Home'?96:320);}});
   layerBar.addEventListener('dblclick',()=>resize(128));
  }
  function resizeHeight(value){state.height=clamp(finite(value,800),600,1800);persist();schedule();}
  for(const id of ['previewHeightDivider','paintHeightDivider']){
   const divider=byId(id);if(!divider)continue;let drag=null;
   divider.addEventListener('pointerdown',e=>{if(e.button!==0)return;e.preventDefault();drag={y:e.clientY,height:heightFor(divider)};divider.setPointerCapture(e.pointerId);document.body.classList.add('resizing-workspace-height');});
   divider.addEventListener('pointermove',e=>{if(drag)resizeHeight(drag.height+e.clientY-drag.y);});
   const end=()=>{drag=null;document.body.classList.remove('resizing-workspace-height');};
   for(const event of ['pointerup','pointercancel','lostpointercapture'])divider.addEventListener(event,end);
   divider.addEventListener('keydown',e=>{if(e.key==='ArrowUp'||e.key==='ArrowDown'){e.preventDefault();resizeHeight(heightFor(divider)+(e.key==='ArrowDown'?1:-1)*(e.shiftKey?80:24));}else if(e.key==='Home'){e.preventDefault();state.height=0;persist();schedule();}});
   divider.addEventListener('dblclick',()=>{state.height=0;persist();schedule();});
  }
  function setPreviewZoom(value){state.preview.zoom=Math.round(clamp(finite(value,5),.25,20)*100)/100;zoomLabels();persist();render();}
  function setPaintZoom(value){state.paintZoom=Math.round(clamp(finite(value,8),.25,32)*100)/100;zoomLabels();updatePaint();persist();render();}
  for(const [id,setter,max] of [['zoomValue',setPreviewZoom,2000],['paintZoomValue',setPaintZoom,3200]]){
   const input=byId(id);
   input.addEventListener('input',()=>{const value=Number(input.value);if(input.value!==''&&value>=25&&value<=max)setter(value/100);});
   input.addEventListener('change',()=>{const value=input.value===''?100:clamp(finite(input.value,100),25,max);setter(value/100);input.value=Math.round(value);});
  }
  byId('zoom').addEventListener('input',e=>setPreviewZoom(e.target.value));
  byId('zoomOut').onclick=()=>setPreviewZoom(state.preview.zoom/1.25);byId('zoomIn').onclick=()=>setPreviewZoom(state.preview.zoom*1.25);
  byId('fitPreview').onclick=()=>fitPreview();
  byId('paintZoom').addEventListener('input',e=>setPaintZoom(e.target.value));
  byId('paintZoomOut').onclick=()=>setPaintZoom(state.paintZoom/1.25);byId('paintZoomIn').onclick=()=>setPaintZoom(state.paintZoom*1.25);
  paintStage.addEventListener('scroll',()=>{
   if(expectedScroll&&Math.abs(paintStage.scrollLeft-expectedScroll.left)<1&&Math.abs(paintStage.scrollTop-expectedScroll.top)<1)return;
   expectedScroll=null;
   const rect=paint.getBoundingClientRect(),viewport=paintStage.getBoundingClientRect();
   paintCenter={x:(viewport.left+paintStage.clientLeft+paintStage.clientWidth/2-rect.left)/state.paintZoom,y:(viewport.top+paintStage.clientTop+paintStage.clientHeight/2-rect.top)/state.paintZoom};
  });
  let paintPan=null;paintStage.style.touchAction='none';
  paintStage.addEventListener('pointerdown',e=>{if(e.button!==1&&e.button!==2||typeof stroke!=='undefined'&&stroke)return;e.preventDefault();paintPan={pointer:e.pointerId,x:e.clientX,y:e.clientY,left:paintStage.scrollLeft,top:paintStage.scrollTop};paintStage.setPointerCapture(e.pointerId);});
  paintStage.addEventListener('pointermove',e=>{if(!paintPan||e.pointerId!==paintPan.pointer)return;paintStage.scrollLeft=paintPan.left+paintPan.x-e.clientX;paintStage.scrollTop=paintPan.top+paintPan.y-e.clientY;});
  const endPaintPan=e=>{if(paintPan&&e.pointerId===paintPan.pointer)paintPan=null;};
  for(const type of ['pointerup','pointercancel','lostpointercapture'])paintStage.addEventListener(type,endPaintPan);
  paintStage.addEventListener('contextmenu',e=>e.preventDefault());
  let pan=null;
  puppet.addEventListener('pointerdown',e=>{if(e.button!==0&&e.button!==1)return;e.preventDefault();pan={x:e.clientX,y:e.clientY,center:{...state.preview.center}};puppet.setPointerCapture(e.pointerId);puppet.classList.add('panning');});
  puppet.addEventListener('pointermove',e=>{if(!pan)return;state.preview.center={x:pan.center.x-(e.clientX-pan.x)/state.preview.zoom,y:pan.center.y-(e.clientY-pan.y)/state.preview.zoom};render();});
  const endPan=()=>{if(pan)persist();pan=null;puppet.classList.remove('panning');};
  puppet.addEventListener('pointerup',endPan);puppet.addEventListener('pointercancel',endPan);puppet.addEventListener('lostpointercapture',endPan);
  puppet.addEventListener('wheel',e=>{if(!e.ctrlKey&&!e.metaKey)return;e.preventDefault();setPreviewZoom(state.preview.zoom*Math.exp(-e.deltaY*.002));},{passive:false});
  const observer=new ResizeObserver(schedule);for(const el of [main,previewStage,paintStage,document.querySelector('header'),byId('notice')])observer.observe(el);
  window.addEventListener('resize',schedule);window.addEventListener('mi-language-change',schedule);zoomLabels();schedule();
  return {
   beginPreview(ctx,override){const view=override||{...size,...state.preview};ctx.setTransform(1,0,0,1,0,0);ctx.clearRect(0,0,ctx.canvas.width,ctx.canvas.height);ctx.setTransform(...transform(view.width,view.height,view.zoom,view.center,view.dpr));return view.zoom;},
   setPaintTarget(key,w,h){if(key!==paintTarget){paintTarget=key;paintCenter={x:w/2,y:h/2};}paintSize=[w,h];updatePaint();},
   capturePaintView(){return {target:paintTarget,center:{...paintCenter}};},
   restorePaintView(view){if(view?.target===paintTarget){paintCenter={...view.center};updatePaint();}},
   fitPreview(bounds){state.preview.center={x:bounds.x+bounds.width/2,y:bounds.y+bounds.height/2};setPreviewZoom(fitZoom(size.width,size.height,bounds));},
   refresh:schedule
  };
 }
 return {MIN,GUTTERS,columns,fitZoom,transform,stateFrom,layerWidth,mount};
});
