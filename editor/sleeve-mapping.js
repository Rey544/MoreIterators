'use strict';
// A fixed front bind pose, rather than a camera-space projection updated each frame.
function sleeveFrontUV(right=false){
 const xy=preset.parts.find(p=>p.kind==='sleeve').xy,x=xy.filter((_,i)=>!(i%2)),y=xy.filter((_,i)=>i%2);
 const x0=Math.min(...x),y0=Math.min(...y),w=Math.max(...x)-x0,h=Math.max(...y)-y0;
 return xy.map((v,i)=>i%2?(v-y0)/h:right?1-(v-x0)/w:(v-x0)/w);
}
function sleeveTextureKeys(){return ['sleeve','sleeveR','puppetSleeve2','puppetSleeve3'].filter(k=>canvases[k]);}
function sleeveMappingSnapshot(){return {sleeves:true,mapping:project.design.sleeveMapping,textures:Object.fromEntries(sleeveTextureKeys().map(k=>[k,structuredClone(project.textures[k])])),canvases:Object.fromEntries(sleeveTextureKeys().map(k=>[k,canvases[k].map(src=>{const c=canvas(src.width,src.height);c.getContext('2d').drawImage(src,0,0);return c;})]))};}
function restoreSleeveMapping(entry){if(typeof PaintLayers!=='undefined')PaintLayers.requireHistory(entry);project.design.sleeveMapping=entry.mapping;for(const k of Object.keys(entry.canvases)){project.textures[k]=typeof PaintLayers!=='undefined'?PaintLayers.preserveLocks(k,structuredClone(entry.textures[k])):structuredClone(entry.textures[k]);canvases[k]=entry.canvases[k].map(src=>{const c=canvas(src.width,src.height);c.getContext('2d').drawImage(src,0,0);return c;});}buildSettings();updateTarget();changed();}
function reprojectSleeve(source,uv,old,triangles){
 const w=source.width,h=source.height,out=canvas(w,h),ctx=out.getContext('2d'),image=ctx.createImageData(w,h),pixels=source.getContext('2d').getImageData(0,0,w,h).data;
 const faces=[];
 for(let i=0;i<triangles.length;i+=3){const ids=triangles.slice(i,i+3),p=ids.map(k=>[uv[k*2]*w,uv[k*2+1]*h]);faces.push({ids,p});}
 for(let y=0;y<h;y++)for(let x=0;x<w;x++){
  const px=x+.5,py=y+.5;let nearest=Infinity,sample=null;
  for(const {ids,p} of faces){
   const [a,b,c]=p,den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1]);if(Math.abs(den)<1e-8)continue;
   const wa=((b[1]-c[1])*(px-c[0])+(c[0]-b[0])*(py-c[1]))/den,wb=((c[1]-a[1])*(px-c[0])+(a[0]-c[0])*(py-c[1]))/den;
   let weights=[wa,wb,1-wa-wb],distance=0;
   if(weights.some(v=>v<0)){
    distance=Infinity;
    for(let edge=0;edge<3;edge++){const j=(edge+1)%3,A=p[edge],B=p[j],dx=B[0]-A[0],dy=B[1]-A[1],len=dx*dx+dy*dy,t=len?Math.max(0,Math.min(1,((px-A[0])*dx+(py-A[1])*dy)/len)):0,ds=(px-A[0]-t*dx)**2+(py-A[1]-t*dy)**2;if(ds<distance){distance=ds;weights=[0,0,0];weights[edge]=1-t;weights[j]=t;}}
   }
   if(distance<=nearest){nearest=distance;sample=[0,0];for(let j=0;j<3;j++){sample[0]+=old[ids[j]*2]*weights[j];sample[1]+=old[ids[j]*2+1]*weights[j];}}
  }
  // One texel of edge bleed prevents unpainted UV-edge seams; source transparency is retained.
  if(nearest>1||!sample)continue;const sx=Math.max(0,Math.min(w-1,Math.floor(sample[0]*w))),sy=Math.max(0,Math.min(h-1,Math.floor(sample[1]*h))),from=(sy*w+sx)*4,to=(y*w+x)*4;
  for(let j=0;j<4;j++)image.data[to+j]=pixels[from+j];
 }
 ctx.putImageData(image,0,0);return out;
}
function convertSleevesToFront(){
 if(project.design.sleeveMapping==='front')return;
 if(typeof PaintLayers!=='undefined')for(const key of sleeveTextureKeys())PaintLayers.requireWritableTexture(key);
 undo.push(sleeveMappingSnapshot());if(undo.length>60)undo.shift();redo=[];
 const triangles=preset.parts.find(p=>p.kind==='sleeve').triangles;
 for(const key of sleeveTextureKeys()){
  const right=key==='sleeveR'||key==='puppetSleeve3',uv=sleeveFrontUV(right),count=uv.length/2;
  const old=Array.from({length:uv.length},(_,i)=>i%2?Math.floor(i/4)/(count/2-1):right?1-Math.floor(i/2)%2:Math.floor(i/2)%2);
  const tex=project.textures[key],procedural=!tex.editableBase;
  const sources=canvases[key].slice();if(procedural)sources[0]=clothBase(key);
  canvases[key]=sources.map(source=>reprojectSleeve(source,uv,old,triangles));
  tex.editableBase=true;if(procedural){tex.layers[0].visible=true;tex.layers[0].opacity=1;}
 }
 project.design.sleeveMapping='front';buildSettings();updateTarget();changed();notice('已转换为正面绘制 · Ctrl+Z 可撤销');
}
function drawSleeveGuide(ctx,w,h,right){
 const uv=sleeveFrontUV(right),n=uv.length/2,outline=[];
 for(let i=0;i<n;i+=2)outline.push(i);for(let i=n-1;i>=1;i-=2)outline.push(i);
 ctx.save();ctx.lineWidth=1.5;ctx.strokeStyle=referenceColor();ctx.beginPath();outline.forEach((i,j)=>ctx[j?'lineTo':'moveTo'](uv[i*2]*w,uv[i*2+1]*h));ctx.closePath();ctx.stroke();ctx.restore();
}

