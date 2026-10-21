'use strict';
const gradientChannels={armGradient:['armColor','支架渐变'],cableThinGradient:['cableColorA','细连接节渐变'],cableThickGradient:['cableColorB','粗连接节渐变'],headCableAGradient:['headCableRed','头后线 A 渐变'],headCableBGradient:['headCableBlue','头后线 B 渐变']};
function gradientDefaults(d){
 for(const [key,[solid]] of Object.entries(gradientChannels))d[key]??={enabled:false,stops:[{position:0,color:d[solid]},{position:1,color:d[solid]}]};
 d.roomGradient??={enabled:false,direction:'radial',opacity:.18,ramp:{enabled:true,stops:[{position:0,color:d.roomWorkColor},{position:1,color:d.roomWorkColor}]},corners:[]};
 d.roomGradient.renderMode??='lighting';
 for(let i=0;i<4;i++)d.roomGradient.corners[i]??={enabled:false,color:'#ffffff',opacity:.18,radius:.5};
}
function gradientSample(ramp,f,solid='#ffffff'){
 if(!ramp?.enabled||!ramp.stops?.length)return solid;
 const stops=[...ramp.stops].sort((a,b)=>a.position-b.position);let a=stops[0],b=stops.at(-1);
 for(const s of stops){if(s.position<=f)a=s;if(s.position>=f){b=s;break;}}
 const mix=b.position===a.position?0:Math.max(0,Math.min(1,(f-a.position)/(b.position-a.position)));
 const rgb=c=>c.match(/\w\w/g).map(h=>parseInt(h,16));const x=rgb(a.color),y=rgb(b.color);
 return '#'+x.map((v,i)=>Math.round(v+(y[i]-v)*mix).toString(16).padStart(2,'0')).join('');
}
function buildGradientSettings(buckets,d){
 gradientDefaults(d);
 function rampFields(host,ramp,solid,optional=true){
  if(optional)garmentField(host,ramp,'enabled','启用渐变','checkbox');
  const body=optional?settingDependency(host,()=>ramp.enabled):host;
  let rows=document.createElement('div');body.append(rows);
  function rebuild(){rows.replaceChildren();ramp.stops.forEach((stop,i)=>{const box=garmentSection(rows,MI18n.t('gradient.stop',{index:i+1}));
    garmentField(box,stop,'color','颜色','color');
    const input=garmentField(box,stop,'position','位置','range',0,1,.01);
    input.addEventListener('change',()=>{ramp.stops.sort((a,b)=>a.position-b.position);rebuild();});
    garmentButton(box,'删除色标',()=>{ramp.stops.splice(i,1);rebuild();changed();});
   });}
  garmentButton(body,'添加色标',()=>{if(ramp.stops.length>=5)return;let positions=[0,...ramp.stops.map(s=>s.position),1].sort((a,b)=>a-b),i=0;for(let j=1;j<positions.length-1;j++)if(positions[j+1]-positions[j]>positions[i+1]-positions[i])i=j;let position=ramp.stops.length?(positions[i]+positions[i+1])/2:0;ramp.stops.push({position,color:gradientSample(ramp,position,solid)});ramp.stops.sort((a,b)=>a.position-b.position);rebuild();changed();});rebuild();
 }
 const arm=buckets.extras.querySelector('[data-section-id="mechanicalArm"]'),cables=buckets.extras.querySelector('[data-section-id="cables"]');
 for(const [key,[solid,title]] of Object.entries(gradientChannels))rampFields(garmentSection(key==='armGradient'?arm:cables,title),d[key],d[solid]);
 const section=garmentSection(buckets.room,MI18n.t('gradient.roomLighting')),r=d.roomGradient;
 garmentField(section,r,'renderMode',MI18n.t('gradient.renderMode'),'select',{lighting:MI18n.t('gradient.nativeLight'),overlay:MI18n.t('gradient.overlay')});
 garmentField(section,r,'enabled','启用房间渐变','checkbox');const body=settingDependency(section,()=>r.enabled);
 garmentField(body,r,'direction','渐变方向','select',{radial:'内侧 → 外侧',horizontal:'左 → 右',vertical:'上 → 下'});
 garmentField(body,r,'opacity','光晕强度','range',0,1,.01);r.ramp.enabled=true;rampFields(body,r.ramp,d.roomWorkColor,false);
 for(const [i,label] of ['左上角','右上角','左下角','右下角'].entries()){
  const c=r.corners[i],sub=garmentSection(section,label);garmentField(sub,c,'enabled','启用角落光晕','checkbox');const body=settingDependency(sub,()=>c.enabled);
  garmentField(body,c,'color','颜色','color');garmentField(body,c,'opacity','光晕强度','range',0,1,.01);garmentField(body,c,'radius','扩散范围','range',.05,2,.01);
 }
 const preview=document.createElement('canvas');preview.width=240;preview.height=180;preview.className='room-gradient-preview';preview.style='width:100%;height:auto;display:block;border:1px solid var(--mi-line,#666)';preview.setAttribute('aria-label',MI18n.t('gradient.preview'));section.append(preview);
 function renderGlow(){const c=preview.getContext('2d'),image=c.createImageData(240,180),hex=v=>v.match(/\w\w/g).map(n=>parseInt(n,16));
  for(let y=0;y<180;y++)for(let x=0;x<240;x++){const u=x/239,v=y/179,f=r.direction==='horizontal'?u:r.direction==='vertical'?v:Math.min(1,Math.hypot((u-.5)*2,(v-.5)*2)),grid=x%24<1||y%24<1?20:40;
   let result=[grid,grid,grid];
   const blend=(rgb,alpha,distance,radius)=>{if(r.renderMode==='lighting'){const peak=Math.max(...rgb)/255;if(!peak)return;const q=Math.min(1,distance/radius);alpha*=peak*Math.pow(1-q*q,3.5)*.65;rgb=rgb.map(n=>n/peak);}result=result.map((n,j)=>n*(1-alpha)+rgb[j]*alpha);};
   if(r.enabled)blend(hex(gradientSample(r.ramp,f,'#ffffff')),r.opacity,Math.hypot(x-119.5,y-89.5),Math.hypot(240,180)*.7);
   for(let i=0;i<4;i++){const k=r.corners[i];if(!k.enabled)continue;const distance=Math.hypot(x-(i%2)*239,y-Math.floor(i/2)*179),alpha=r.renderMode==='lighting'?k.opacity:k.opacity*Math.exp(-((u-i%2)**2+(v-Math.floor(i/2))**2)/k.radius**2);blend(hex(k.color),alpha,distance,k.radius*240);}
   const offset=(y*240+x)*4;for(let j=0;j<3;j++)image.data[offset+j]=result[j];image.data[offset+3]=255;
  }c.putImageData(image,0,0);}
 section.addEventListener('input',renderGlow);section.addEventListener('click',()=>requestAnimationFrame(renderGlow));renderGlow();
}
