/* Shared pixel pearl templates for local studio previews and map markers. */
(function(scope){
 'use strict';
 const defaults=Object.freeze({baseColor:'#000000',highlightColor:'#b0d8f0',secondaryColor:'#365576',twoTone:false,size:1,effect:'none',effectColor:'#88bbff',effectOpacity:.4,effectSize:28,pulseSpeed:1});
 const effects=Object.freeze([['none','无'],['glow','柔光'],['pulse','脉冲光圈'],['halcyon','赞美诗式光圈']].map(Object.freeze));
 const finite=(value,fallback)=>typeof value==='number'&&Number.isFinite(value)?value:fallback;
 const bounded=(value,min,max,fallback)=>Math.max(min,Math.min(max,finite(value,fallback)));
 const color=(value,fallback)=>typeof value==='string'&&/^#[a-f\d]{6}$/i.test(value)?value.toLowerCase():fallback;
 function defaultAppearance(){return {...defaults};}
 function normalizeAppearance(value){const a=value&&typeof value==='object'?value:{};return {
  baseColor:color(a.baseColor,defaults.baseColor),highlightColor:color(a.highlightColor,defaults.highlightColor),secondaryColor:color(a.secondaryColor,defaults.secondaryColor),
  twoTone:a.twoTone===true,size:bounded(a.size,.5,3,defaults.size),effect:effects.some(([name])=>name===a.effect)?a.effect:defaults.effect,
  effectColor:color(a.effectColor,defaults.effectColor),effectOpacity:bounded(a.effectOpacity,0,1,defaults.effectOpacity),effectSize:bounded(a.effectSize,5,120,defaults.effectSize),pulseSpeed:bounded(a.pulseSpeed,.1,4,defaults.pulseSpeed)
 };}
 function context(canvas){if(!canvas||typeof canvas.getContext!=='function')throw new TypeError('需要画布。');return canvas.getContext('2d');}
 // 9x9 UI silhouette follows the reference strip and Symbol_Pearl's opaque
 // steps. The in-world DataPearl body (JetFishEyeA) is a separate 6x6 sprite.
 const pearlMask=Object.freeze(['...###...','.#######.','.#######.','#########','#########','#########','.#######.','.#######.','...###...']);
 const pearlShade=Object.freeze(['...222...','.2555542.','.5444442.','254444432','254444432','234444332','.3443331.','.1333311.','...111...']);
 // Local, irregular pigment with discrete transition colors; never two halves.
 const pearlPigment=Object.freeze(['...000...','.0000000.','.0001100.','000122100','000134210','000244210','.0012210.','.0001000.','...000...']);
 // Symbol_Pearl's dark inner arc: right side, then a short lower-right turn.
 const mapShadow=Object.freeze(['.........','.........','.........','.......#.','.......#.','.......#.','......#..','...###...','.........']);
 const starMask=Object.freeze(['.#.','###','.#.']);
 const channels=hex=>[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16));
 function mix(a,b,amount){return a.map((value,i)=>Math.round(value+(b[i]-value)*amount));}
 function pearlPixels(appearance,options={}){
  const a=normalizeAppearance(appearance),marker=options.variant==='map',width=11,height=11,data=new Uint8ClampedArray(width*height*4),base=channels(a.baseColor),secondary=channels(a.secondaryColor),highlight=channels(a.highlightColor);
  const put=(x,y,rgb)=>data.set([...rgb,255],(y*width+x)*4);
  for(let y=0;y<9;y++)for(let x=0;x<9;x++){
   if(pearlMask[y][x]!== '#')continue;
   const weight=a.twoTone?Number(pearlPigment[y][x])*.25:0,tone=weight?mix(base,secondary,weight):base,shade=pearlShade[y][x];
   let rgb=shade==='1'?mix(tone,[8,11,17],.62):shade==='2'?mix(tone,[170,184,198],.24):shade==='3'?mix(tone,[10,14,22],.25):shade==='5'?mix(tone,[224,235,247],.22):tone;
   if(marker)rgb=mapShadow[y][x]==='#'?mix(tone,[8,11,17],.55):tone;
   put(x+1,y+1,rgb);
  }
  if(!marker)for(let y=0;y<3;y++)for(let x=0;x<3;x++)if(starMask[y][x]==='#')put(x+3,y+2,highlight);
  return {width,height,data};
 }
 function paintPixels(ctx,sprite,left,top,size){
  for(let y=0;y<sprite.height;y++)for(let x=0;x<sprite.width;x++){
   const i=(y*sprite.width+x)*4;if(!sprite.data[i+3])continue;
   ctx.fillStyle=`rgb(${sprite.data[i]},${sprite.data[i+1]},${sprite.data[i+2]})`;
   ctx.fillRect(left+x*size,top+y*size,size,size);
  }
 }
 // CreatorDataPearl.Update/DrawSprites runs at 40 ticks per second. Preview
 // the same expanding/fading ring; halcyon adds a beat only while playing.
 function effectFrame(appearance,time=0,options={}){
  const a=normalizeAppearance(appearance),tick=Math.max(0,finite(time,0))/25,phase=(tick*a.pulseSpeed/100)%1;
  const pulse=.5+.5*Math.sin(tick*.05*a.pulseSpeed);
  const beat=a.effect==='halcyon'&&appearance?.music===true&&options.halcyonPlaying===true?.5+.5*Math.sin(Math.floor(tick)*.06):0;
  return {phase,beat,glowAlpha:a.effect==='none'?0:a.effectOpacity*(a.effect==='glow'?1:.55+.45*pulse),ringVisible:a.effect==='pulse'||a.effect==='halcyon',ringScale:a.effectSize*(.55+phase+beat*.1)/8,ringAlpha:a.effectOpacity*(1-phase)};
 }
 function pearl(canvas,appearance,options={}){
  const ctx=context(canvas);if(!ctx)return false;
  const a=normalizeAppearance(appearance),width=canvas.width,height=canvas.height;if(!(width>0&&height>0))return false;
  const time=finite(options?.time,0),frame=effectFrame(appearance,time,options),radius=23*a.size,reach=a.effectSize*1.35,extent=a.effect!=='none'&&a.effectOpacity>0?Math.max(radius+.65,reach*1.65+1.3):radius+.65;
  const scale=options?.tight===true?Math.min(width,height)/(2*extent+8):Math.min(width,height)/160;
  const w=width/scale,h=height/scale,x=w/2,y=h/2-(options?.tight===true?0:8);
  ctx.save();ctx.setTransform(1,0,0,1,0,0);ctx.clearRect(0,0,width,height);ctx.globalAlpha=1;ctx.globalCompositeOperation='source-over';ctx.scale(scale,scale);
  if(a.effect!=='none'){
   const gradient=ctx.createRadialGradient(x,y,0,x,y,reach);gradient.addColorStop(0,a.effectColor);gradient.addColorStop(1,a.effectColor+'00');
   ctx.globalAlpha=frame.glowAlpha;ctx.fillStyle=gradient;ctx.fillRect(0,0,w,h);
   if(frame.ringVisible){ctx.globalAlpha=frame.ringAlpha;ctx.strokeStyle=a.effectColor;ctx.lineWidth=1.3;ctx.beginPath();ctx.arc(x,y,frame.ringScale*8*1.35,0,Math.PI*2);ctx.stroke();}
   ctx.globalAlpha=1;
  }
  // Paint on the actual canvas grid, independently of the effect transform.
  // Every body/highlight edge is an integer pixel; no canvas circle or clip.
  ctx.setTransform(1,0,0,1,0,0);ctx.imageSmoothingEnabled=false;
  const sprite=pearlPixels(a),pixel=Math.max(1,Math.min(Math.round(radius*2*scale/9),Math.floor(Math.min(width,height)/11))),left=Math.round(x*scale-sprite.width*pixel/2),top=Math.round(y*scale-sprite.height*pixel/2);
  paintPixels(ctx,sprite,left,top,pixel);ctx.restore();return true;
 }
 function pearlMarker(canvas,appearance,options={}){
  const ctx=context(canvas);if(!ctx||!(canvas.width>0&&canvas.height>0))return false;
  const sprite=pearlPixels(appearance,{variant:'map'}),pixel=Math.max(1,Math.floor(Math.min(canvas.width,canvas.height)/11)),left=Math.floor((canvas.width-sprite.width*pixel)/2),top=Math.floor((canvas.height-sprite.height*pixel)/2);
  ctx.save();ctx.setTransform(1,0,0,1,0,0);ctx.clearRect(0,0,canvas.width,canvas.height);ctx.globalAlpha=1;ctx.globalCompositeOperation='source-over';ctx.imageSmoothingEnabled=false;paintPixels(ctx,sprite,left,top,pixel);ctx.restore();return true;
 }
 // Draw a pearl into a shared preview without clearing or resetting its transform.
 // Accessory diameters remain in the existing puppet coordinate system.
 const stampCache=new Map();
 function drawAt(ctx,x,y,diameter,appearance,options={}){
  if(!ctx||!Number.isFinite(diameter)||diameter<=0)return false;
  const a=normalizeAppearance(appearance),variant=options.variant==='map'?'map':'detail';
  const key=JSON.stringify([a.baseColor,a.highlightColor,a.secondaryColor,a.twoTone,variant]);
  let stamp=stampCache.get(key);
  if(!stamp){
   const sprite=pearlPixels(a,{variant});
   stamp=typeof scope.OffscreenCanvas==='function'?new scope.OffscreenCanvas(11,11):scope.document.createElement('canvas');
   stamp.width=stamp.height=11;
   const paint=stamp.getContext('2d'),pixels=paint.createImageData(11,11);pixels.data.set(sprite.data);paint.putImageData(pixels,0,0);
   if(stampCache.size>=128)stampCache.delete(stampCache.keys().next().value);
   stampCache.set(key,stamp);
  }
  const extent=diameter*11/9;
  ctx.save();ctx.imageSmoothingEnabled=false;ctx.drawImage(stamp,Math.round(x-extent/2),Math.round(y-extent/2),extent,extent);ctx.restore();return true;
 }
 function accessoryAppearance(style){
  const base=color(style?.color,'#c5d6ce'),light='#'+channels(base).map(v=>Math.min(255,Math.round(v*.65+127.5)).toString(16).padStart(2,'0')).join('');
  return {baseColor:base,highlightColor:style?.dual?color(style.highlight,light):light,twoTone:false};
 }
 const api=Object.freeze({pearl,pearlMarker,pearlPixels,drawAt,accessoryAppearance,effectFrame,normalizeAppearance,defaultAppearance});
 if(typeof module!=='undefined'&&module.exports)module.exports=api;else scope.MIPearlIcons=api;
})(typeof window!=='undefined'?window:globalThis);
