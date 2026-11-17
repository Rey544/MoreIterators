'use strict';
const PreviewSelection=(()=>{
 const preference='moreiterators.previewSelection.v1';
 let records=[],active=false,owner=null,hover=null,selected=null,pointer=null,lastClick=null,frame=0,mask=null,hoverLayer=null,nameTip=null,showNames=true,alphaCache=new Map(),color='#8fc9ff';
 try{const saved=JSON.parse(localStorage.getItem(preference)||'{}');if(/^#[0-9a-f]{6}$/i.test(saved.color))color=saved.color;showNames=saved.showNames!==false;}catch{}
 function savePreferences(){try{localStorage.setItem(preference,JSON.stringify({color,showNames}));}catch{}}
 function hideName(){if(nameTip)nameTip.hidden=true;}
 function barycentric(point,xy){
  const [x,y]=point,[ax,ay,bx,by,cx,cy]=xy,det=(by-cy)*(ax-cx)+(cx-bx)*(ay-cy);
  if(Math.abs(det)<1e-8)return null;
  const a=((by-cy)*(x-cx)+(cx-bx)*(y-cy))/det,b=((cy-ay)*(x-cx)+(ax-cx)*(y-cy))/det,c=1-a-b;
  return a>=-1e-7&&b>=-1e-7&&c>=-1e-7?[a,b,c]:null;
 }
 function transformed(points,m){const result=[];for(let i=0;i<points.length;i+=2)result.push(m.a*points[i]+m.c*points[i+1]+m.e,m.b*points[i]+m.d*points[i+1]+m.f);return result;}
 function alphaAt(image,u,v){
  if(!image)return true;
  let data=alphaCache.get(image);
  if(!data){try{const w=image.naturalWidth||image.width,h=image.naturalHeight||image.height;if(!w||!h)return false;const c=document.createElement('canvas');c.width=w;c.height=h;const ctx=c.getContext('2d',{willReadFrequently:true});ctx.drawImage(image,0,0);data={w,h,pixels:ctx.getImageData(0,0,w,h).data};alphaCache.set(image,data);}catch{return false;}}
  const x=Math.max(0,Math.min(data.w-1,Math.floor(u*data.w))),y=Math.max(0,Math.min(data.h-1,Math.floor(v*data.h)));
  return data.pixels[(y*data.w+x)*4+3]>8;
 }
 function hit(record,point,sample=alphaAt){
  if(record.alpha<=0||point[0]<record.bounds[0]||point[0]>record.bounds[2]||point[1]<record.bounds[1]||point[1]>record.bounds[3])return false;
  for(let i=record.triangles.length-3;i>=0;i-=3){const ids=record.triangles.slice(i,i+3),weights=barycentric(point,ids.flatMap(k=>record.points.slice(k*2,k*2+2)));if(!weights)continue;
   if(!record.image||!record.uv)return true;
   const uv=[0,1].map(axis=>ids.reduce((sum,k,j)=>sum+record.uv[k*2+axis]*weights[j],0));if(sample(record.image,...uv))return true;
  }return false;
 }
 function hits(point,items=records,sample=alphaAt){const result=[];for(let i=items.length-1;i>=0;i--){const record=items[i];if(!result.includes(record.key)&&hit(record,point,sample))result.push(record.key);}return result;}
 function cycle(keys,point,previous,now){
  if(!keys.length)return {key:null,click:null};
  const again=previous&&now-previous.time<1600&&Math.hypot(point[0]-previous.point[0],point[1]-previous.point[1])<=4&&keys.join('\n')===previous.keys.join('\n');
  const index=again?(previous.index+1)%keys.length:0;
  return {key:keys[index],click:{keys:[...keys],point:[...point],index,time:now}};
 }
 function begin(ctx,disabled=false){
  if(hoverLayer)hoverLayer.hidden=true;
  hideName();
  active=!disabled;records=[];alphaCache=new Map();
  const current=typeof project==='undefined'?null:project;
  if(owner!==current){owner=current;hover=null;selected=null;lastClick=null;pointer=null;}
  if(!active)return;
 }
 function mesh(key,part,points,image,uv,ctx){
  if(!active||!key||!part?.triangles?.length||(part.alpha??1)<=0)return;
  const mapped=transformed(points,ctx.getTransform()),xs=mapped.filter((_,i)=>i%2===0),ys=mapped.filter((_,i)=>i%2===1);
  if(!mapped.every(Number.isFinite))return;
  records.push({key,points:mapped,triangles:[...part.triangles],image:image||null,uv:uv?[...uv]:null,alpha:part.alpha??1,bounds:[Math.min(...xs),Math.min(...ys),Math.max(...xs),Math.max(...ys)]});
 }
 function rect(key,image,x,y,w,h,ctx){mesh(key,{triangles:[0,1,2,0,2,3]},[x,y,x+w,y,x+w,y+h,x,y+h],image,[0,0,1,0,1,1,0,1],ctx);}
 function line(key,a,b,width,ctx){const dx=b[0]-a[0],dy=b[1]-a[1],length=Math.hypot(dx,dy);if(!length)return;const x=-dy/length*width/2,y=dx/length*width/2;mesh(key,{triangles:[0,1,2,0,2,3]},[a[0]+x,a[1]+y,b[0]+x,b[1]+y,b[0]-x,b[1]-y,a[0]-x,a[1]-y],null,null,ctx);}
 function ellipse(key,x,y,r,ctx){const points=[x,y],triangles=[];for(let i=0;i<=24;i++)points.push(x+Math.cos(i*Math.PI/12)*r,y+Math.sin(i*Math.PI/12)*r);for(let i=1;i<=24;i++)triangles.push(0,i,i+1);mesh(key,{triangles},points,null,null,ctx);}
 function canvasPoint(event,canvas){const r=canvas.getBoundingClientRect();return [(event.clientX-r.left)*canvas.width/r.width,(event.clientY-r.top)*canvas.height/r.height];}
 function schedule(){if(frame||typeof requestAnimationFrame==='undefined')return;frame=requestAnimationFrame(()=>{frame=0;if(typeof drawPuppet==='function'&&typeof loading!=='undefined'&&!loading)drawPuppet();});}
 function move(event){pointer={clientX:event.clientX,clientY:event.clientY};schedule();}
 function leave(){pointer=null;hover=null;if(hoverLayer)hoverLayer.hidden=true;hideName();schedule();}
 function cancel(){lastClick=null;leave();}
 function clear(){selected=null;cancel();}
 function select(key){selected=key;lastClick=null;schedule();}
 function click(event){
  if(typeof project==='undefined'||loading||changingProject)return;
  const canvas=document.getElementById('puppet'),point=canvasPoint(event,canvas),result=cycle(hits(point),[event.clientX,event.clientY],lastClick,performance.now());
  selected=result.key;lastClick=result.click;pointer={clientX:event.clientX,clientY:event.clientY};
  if(selected){
   if(typeof PaintTargets!=='undefined'&&PaintTargets.available(selected)){stroke=null;target=PuppetArms.select(selected);if(target==='frontR'&&project.design.frontSymmetry)target='frontL';activeLayer=Math.min(activeLayer,canvases[target].length-1);updateTarget();}
   PaintTargets.locateSettings(selected);
  }schedule();
 }
 function drawRecord(ctx,record){
  ctx.globalAlpha=record.alpha;
  for(let i=0;i<record.triangles.length;i+=3){const ids=record.triangles.slice(i,i+3),xy=ids.flatMap(k=>record.points.slice(k*2,k*2+2));
   if(record.image&&record.uv)triangle(ctx,record.image,xy,ids.flatMap(k=>record.uv.slice(k*2,k*2+2)));
   else{ctx.beginPath();ctx.moveTo(xy[0],xy[1]);ctx.lineTo(xy[2],xy[3]);ctx.lineTo(xy[4],xy[5]);ctx.closePath();ctx.fill();}
  }ctx.globalAlpha=1;
 }
 function overlay(ctx,key,opacity){
  if(!key)return;if(!mask)mask=document.createElement('canvas');if(mask.width!==ctx.canvas.width)mask.width=ctx.canvas.width;if(mask.height!==ctx.canvas.height)mask.height=ctx.canvas.height;
  const paint=mask.getContext('2d');paint.setTransform(1,0,0,1,0,0);paint.clearRect(0,0,mask.width,mask.height);paint.fillStyle='#ffffff';paint.imageSmoothingEnabled=true;paint.imageSmoothingQuality='high';
  for(const record of records)if(record.key===key)drawRecord(paint,record);
  paint.globalCompositeOperation='source-in';paint.fillStyle=color;paint.fillRect(0,0,mask.width,mask.height);paint.globalCompositeOperation='source-over';
  ctx.save();ctx.setTransform(1,0,0,1,0,0);ctx.globalAlpha=opacity;ctx.shadowBlur=0;ctx.drawImage(mask,0,0);ctx.restore();
 }
 function highlightStyle(){return {color,outlineColor:'#'+color.slice(1).match(/../g).map(v=>Math.round(parseInt(v,16)*.6+255*.4).toString(16).padStart(2,'0')).join(''),selectedOpacity:.3,hoverOpacity:.2,outlineWidth:2,outlineBlur:.2};}
 function paintOutline(paint,source,dx=1,dy=1){
  const style=highlightStyle();paint.save();paint.filter='blur('+(style.outlineBlur*Math.max(dx,dy))+'px)';
  for(let i=0;i<8;i++){const angle=i*Math.PI/4;paint.drawImage(source,style.outlineWidth*Math.cos(angle)*dx,style.outlineWidth*Math.sin(angle)*dy);}
  paint.filter='none';paint.globalCompositeOperation='destination-out';for(let i=0;i<4;i++)paint.drawImage(source,0,0);
  paint.globalCompositeOperation='source-in';paint.fillStyle=style.outlineColor;paint.fillRect(0,0,paint.canvas.width,paint.canvas.height);paint.restore();
 }
 function outline(ctx){
  const host=ctx.canvas.parentElement;if(!host||host.id!=='previewStage'||!mask)return;
  if(!hoverLayer){hoverLayer=document.createElement('canvas');hoverLayer.className='preview-hover-outline';hoverLayer.setAttribute('aria-hidden','true');host.append(hoverLayer);}
  if(hoverLayer.width!==mask.width)hoverLayer.width=mask.width;if(hoverLayer.height!==mask.height)hoverLayer.height=mask.height;
  const paint=hoverLayer.getContext('2d'),bounds=ctx.canvas.getBoundingClientRect();
  paint.clearRect(0,0,hoverLayer.width,hoverLayer.height);
  paintOutline(paint,mask,mask.width/Math.max(1,bounds.width),mask.height/Math.max(1,bounds.height));hoverLayer.hidden=false;
 }
 function updateName(){
  if(!showNames||!pointer||!hover||typeof PaintTargets==='undefined'){hideName();return;}
  const name=PaintTargets.label?.(hover);if(!name){hideName();return;}
  if(!nameTip){nameTip=document.createElement('span');nameTip.id='previewPartName';nameTip.className='mi-link-tooltip mi-preview-name';nameTip.setAttribute('role','tooltip');MI18n.content(nameTip);document.body.append(nameTip);}
  nameTip.textContent=name;nameTip.hidden=false;
  const bounds=nameTip.getBoundingClientRect(),width=document.documentElement.clientWidth,height=document.documentElement.clientHeight;
  nameTip.style.left=Math.max(8,Math.min(pointer.clientX+14,width-bounds.width-8))+'px';
  nameTip.style.top=Math.max(8,pointer.clientY+20+bounds.height>height-8?pointer.clientY-bounds.height-12:pointer.clientY+20)+'px';
 }
 function end(ctx){
  if(!active)return;
  if(selected&&!records.some(record=>record.key===selected)){selected=null;lastClick=null;}
  const keys=pointer?hits(canvasPoint(pointer,ctx.canvas)):[];
  hover=keys[0]||null;
  if(lastClick&&selected&&keys.includes(selected)&&pointer&&Math.hypot(pointer.clientX-lastClick.point[0],pointer.clientY-lastClick.point[1])<=4)hover=selected;
  if(!ctx.canvas.classList.contains('panning'))ctx.canvas.style.cursor=hover?'pointer':'grab';
  if(selected)overlay(ctx,selected,.3);if(hover){overlay(ctx,hover,hover===selected?0:.2);outline(ctx);}updateName();
 }
 function mountPreferences(host){
  if(!host||host.querySelector('[data-preview-highlight]'))return;
  const row=document.createElement('label'),label=document.createElement('span'),input=document.createElement('input');row.className='field';label.dataset.i18n='previewSelection.color';label.textContent=MI18n.t('previewSelection.color');input.type='color';input.value=color;input.dataset.previewHighlight='true';input.setAttribute('aria-label',label.textContent);input.oninput=()=>{color=input.value;savePreferences();schedule();window.dispatchEvent(new Event('mi-preview-highlight-change'));};row.append(label,input);host.append(row);
  const namesRow=document.createElement('label'),namesLabel=document.createElement('span'),namesInput=document.createElement('input');namesRow.className='field';namesLabel.dataset.i18n='previewSelection.names';namesInput.type='checkbox';namesInput.checked=showNames;namesInput.dataset.previewNames='true';namesInput.onchange=()=>{showNames=namesInput.checked;savePreferences();updateName();};namesRow.append(namesLabel,namesInput);host.append(namesRow);
  const translate=()=>{label.textContent=MI18n.t('previewSelection.color');input.setAttribute('aria-label',label.textContent);namesLabel.textContent=MI18n.t('previewSelection.names');namesInput.setAttribute('aria-label',namesLabel.textContent);updateName();};translate();
  document.getElementById('puppet')?.addEventListener('contextmenu',event=>{event.preventDefault();if(!hits(canvasPoint(event,event.currentTarget)).length)clear();});
  window.addEventListener('scroll',hideName,true);window.addEventListener('blur',leave);
  window.addEventListener('mi-language-change',translate);MI18n.ready.then(translate);
 }
 return {begin,end,mesh,rect,line,ellipse,move,leave,cancel,clear,click,select,mountPreferences,barycentric,transformed,hit,hits,cycle,highlightStyle,paintOutline};
})();
if(typeof module!=='undefined'&&module.exports)module.exports=PreviewSelection;
