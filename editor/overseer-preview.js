'use strict';
const MIOverseerPreview=(()=>{
 const mix=(a,b,t)=>a+(b-a)*t;
 const point=(a,b,c,d,t)=>a.map((v,i)=>v*(1-t)**3+3*b[i]*t*(1-t)**2+3*c[i]*t*t*(1-t)+d[i]*t**3);
 // Fully extended OverseerGraphics.DrawPosOfSegment / RadOfSegment.
 const radius=(f,length=70)=>5*(1-Math.pow(f,mix(1.75,.35,Math.max(0,Math.min(1,(length-20)/70)))));
 function geometry(time=0){
  const head=[71+Math.sin(time*.8)*1.5,21+Math.sin(time*.65)*1.2],root=[24,64],direction=[.84,-.14],rootDir=[.22,-1];
  const length=Math.hypot(head[0]-root[0],head[1]-root[1]),reach=Math.max(40,length*.85);
  const a=head,b=head.map((v,i)=>v-direction[i]*15),c=root.map((v,i)=>v+rootDir[i]*reach);
  return {head,root,direction,segments:Array.from({length:41},(_,i)=>({p:point(a,b,c,root,i/40),r:radius(i/40,length),f:i/40}))};
 }
 function color(colors,t){const hex=c=>c.match(/\w\w/g).map(v=>parseInt(v,16)),a=hex(colors[0]),b=hex(colors.at(-1));return 'rgb('+a.map((v,i)=>Math.round(mix(v,b[i],t))).join(',')+')';}
 function draw(canvas,settings,time=0){
  const pixel=document.createElement('canvas');pixel.width=110;pixel.height=75;
  const c=pixel.getContext('2d'),g=geometry(time),palette=settings.bodyColors,tip=settings.tipColors;
  c.fillStyle='#161819';c.fillRect(0,0,110,75);c.strokeStyle='#414446';c.lineWidth=1;
  c.beginPath();c.moveTo(8,65);c.lineTo(102,65);c.stroke();
  c.save();c.globalAlpha=settings.enabled?1:.45;
  const halo=c.createRadialGradient(...g.head,1,...g.head,17);halo.addColorStop(0,color(palette,1).replace('rgb(','rgba(').replace(')',',.22)'));halo.addColorStop(1,'#00000000');c.fillStyle=halo;c.fillRect(g.head[0]-18,g.head[1]-18,36,36);
  for(let i=g.segments.length-1;i>0;i--){const a=g.segments[i],b=g.segments[i-1],dx=b.p[0]-a.p[0],dy=b.p[1]-a.p[1],length=Math.hypot(dx,dy)||1,n=[-dy/length,dx/length];
   c.fillStyle=color(palette,1-(a.f+b.f)/2);c.beginPath();c.moveTo(a.p[0]+n[0]*a.r,a.p[1]+n[1]*a.r);c.lineTo(a.p[0]-n[0]*a.r,a.p[1]-n[1]*a.r);c.lineTo(b.p[0]-n[0]*b.r,b.p[1]-n[1]*b.r);c.lineTo(b.p[0]+n[0]*b.r,b.p[1]+n[1]*b.r);c.fill();}
  const attachment=g.segments[12].p;
  for(let k=0;k<4;k++){
   let previous=attachment;const angle=-2.4+k*.92,reach=20+k%2*8;
   for(let i=1;i<=22;i++){const t=i/22,p=[attachment[0]+Math.cos(angle)*reach*t+Math.sin(t*5+time*.7+k)*t*3,attachment[1]+Math.sin(angle)*reach*t+Math.sin(t*4+time*.6+k)*t*3];c.strokeStyle=color(tip,t);c.lineWidth=i===22?1.3:.65;c.beginPath();c.moveTo(...previous);c.lineTo(...p);c.stroke();previous=p;}
  }
  c.fillStyle=color(palette,1);c.beginPath();c.ellipse(...g.head,5,5.7,0,0,Math.PI*2);c.fill();
  const look=[g.direction[0],g.direction[1]],eye=g.head.map((v,i)=>v+look[i]*4);
  c.save();c.translate(...eye);c.rotate(Math.atan2(look[1],look[0]));c.fillStyle=settings.eyeWhite;c.beginPath();c.ellipse(0,0,2.35,3.5,0,0,Math.PI*2);c.fill();c.globalAlpha*=.25;c.fillStyle=color(palette,1);c.beginPath();c.ellipse(-.9,0,1.8,2.6,0,0,Math.PI*2);c.fill();c.globalAlpha=settings.enabled?1:.45;c.fillStyle=settings.eyePupil;c.fillRect(.5,-.5,1,1);c.restore();c.restore();
  const out=canvas.getContext('2d');out.clearRect(0,0,canvas.width,canvas.height);out.imageSmoothingEnabled=false;const scale=Math.min(canvas.width/110,canvas.height/75),w=110*scale,h=75*scale;out.drawImage(pixel,(canvas.width-w)/2,(canvas.height-h)/2,w,h);
 }
 return {geometry,radius,draw};
})();
if(typeof module!=='undefined')module.exports=MIOverseerPreview;
