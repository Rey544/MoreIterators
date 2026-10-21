'use strict';
function pearlAccessoryDefault(index=1){return {id:'pearlAccessory:'+index,name:'',anchor:'head',stringColor:'#737e78',enabled:true,pearls:5,hangingChains:1,horizontalChains:1,colorMode:0,u:.5,v:.5,x:0,y:0,rotation:0,width:14,length:18,sag:4,thickness:.4,size:2.2,softness:.7,gravity:1,primary:necklacePearl(),alternate:necklacePearl('#354d45','#d2ebe2',true),beads:[],children:[]};}
function pearlAccessoryBead(){return {...necklacePearl(),chain:-1,position:.5};}
function pearlAccessoryChild(){return {name:'',png:'',color:'#ffffff',enabled:true,bead:0,x:0,y:0,width:5,height:8,rotation:0};}
function pearlAccessoryFind(d,id){return (d.pearlAccessories||[]).find(a=>a.id===id);}
function pearlAccessoriesInit(p){
 p.design.pearlAccessories??=[];p.design.renderOrder??=[];
 for(const a of p.design.pearlAccessories){Object.assign(a,{...pearlAccessoryDefault(),...a});a.beads??=[];a.children??=[];if(!p.design.renderOrder.includes(a.id))p.design.renderOrder.push(a.id);}
}
function pearlAccessoryTopology(d){
 const points=[],links=[],chains=[],pins=[];const node=p=>(points.push(p),points.length-1),join=(a,b)=>{if(a!==b)links.push([a,b]);};
 const path=(first,end,steps,final=-1)=>{const chain=[first],start=points[first];for(let j=1;j<=steps;j++){const index=j===steps&&final>=0?final:node(start.map((v,k)=>v+(end[k]-v)*j/steps));join(chain.at(-1),index);chain.push(index);}return chain;};
 let previous=null;
 for(let row=0;row<d.horizontalChains;row++){
  const current=[],top=-d.length*.55*row/Math.max(1,d.horizontalChains-1);
  for(let j=0;j<13;j++){const u=j/12;current.push(node([(u-.5)*d.width,top-4*d.sag*u*(1-u)]));if(j)join(current[j-1],current[j]);}
  chains.push(current);if(previous){path(previous[0],points[current[0]],4,current[0]);path(previous[12],points[current[12]],4,current[12]);}else pins.push(current[0],current[12]);previous=current;
 }
 let root=-1;if(!d.horizontalChains){root=node([0,0]);pins.push(root);}
 for(let c=0;c<d.hangingChains;c++){const t=(c+1)/(d.hangingChains+1),start=previous?previous[Math.round(t*12)]:root,p=points[start];chains.push(path(start,[p[0]+(previous?0:(t-.5)*d.width),p[1]-d.length*(.72+(c*7%5)*.07)],10));}
 if(!chains.length&&d.pearls)chains.push(path(root,[0,-d.length],10));
 const candidates=[...new Set(chains.flat())].filter(i=>!pins.includes(i)),beads=[],used=new Set();
 for(let i=0;i<d.pearls&&candidates.length;i++){
  const bead=d.beads[i],chain=bead?.chain>=0?chains[bead.chain]:null;
  let index=chain?chain[Math.min(chain.length-(pins.includes(chain.at(-1))?2:1),Math.max(1,Math.round(bead.position*(chain.length-1))))]:candidates[Math.min(candidates.length-1,Math.floor((i+.5)*candidates.length/d.pearls))];
  if(used.has(index)){const start=Math.max(0,candidates.indexOf(index));for(let j=1;j<=candidates.length;j++){const next=candidates[(start+j)%candidates.length];if(!used.has(next)){index=next;break;}}}
  beads.push(index);used.add(index);
 }
 return {points,links,chains,pins,beads};
}
const pearlChildImages=new Map();
function pearlChildImage(png){if(!png)return null;if(!pearlChildImages.has(png)){const image=new Image();image.onload=()=>{if(typeof render==='function')render();};image.src=png;pearlChildImages.set(png,image);}const image=pearlChildImages.get(png);return image.complete&&image.naturalWidth?image:null;}
function pearlAccessoriesPreview(ctx,d,anchors,queue){
 for(const a of d.pearlAccessories||[]){if(!a.enabled)continue;const graph=pearlAccessoryTopology(a),origin=wardrobeAnchorPoint(anchors,a.anchor,a.u,a.v),scale=d.puppetScale,angle=a.rotation*Math.PI/180;
  const left=wardrobeAnchorPoint(anchors,a.anchor,Math.max(0,a.u-.01),a.v),right=wardrobeAnchorPoint(anchors,a.anchor,Math.min(1,a.u+.01),a.v),top=wardrobeAnchorPoint(anchors,a.anchor,a.u,Math.max(0,a.v-.01)),bottom=wardrobeAnchorPoint(anchors,a.anchor,a.u,Math.min(1,a.v+.01));
  const length=Math.hypot(right[0]-left[0],right[1]-left[1]),baseRight=length>1e-5?right.map((v,i)=>(v-left[i])/length):[1,0];let baseUp=[-baseRight[1],baseRight[0]];const wantedUp=top.map((v,i)=>v-bottom[i]);if(Math.hypot(...wantedUp)<1e-5)wantedUp[1]=-1;if(baseUp[0]*wantedUp[0]+baseUp[1]*wantedUp[1]<0)baseUp=baseUp.map(v=>-v);
  const localRight=baseRight.map((v,i)=>v*Math.cos(angle)-baseUp[i]*Math.sin(angle)),localUp=baseUp.map((v,i)=>v*Math.cos(angle)+baseRight[i]*Math.sin(angle));
  const map=p=>[origin[0]+(a.x+localRight[0]*p[0]+localUp[0]*p[1])*scale,origin[1]+(-a.y+localRight[1]*p[0]+localUp[1]*p[1])*scale];
  queue.add(a.id,()=>{
   ctx.save();ctx.strokeStyle=a.stringColor;ctx.lineWidth=a.thickness*scale;ctx.lineCap='round';ctx.beginPath();if(a.horizontalChains||a.hangingChains)for(const [i,j] of graph.links){ctx.moveTo(...map(graph.points[i]));ctx.lineTo(...map(graph.points[j]));}ctx.stroke();
   graph.beads.forEach((index,i)=>{const bead=a.beads[i],style=a.colorMode===2&&bead?bead:a.colorMode===1&&i%2?a.alternate:a.primary,diameter=(bead?.size||a.size)*scale,p=map(graph.points[index]);MIPearlIcons.drawAt(ctx,p[0],p[1],diameter,MIPearlIcons.accessoryAppearance(style));});
   for(const child of a.children){if(!child.enabled)continue;const image=pearlChildImage(child.png);if(!image)continue;const p=graph.beads.length?graph.points[graph.beads[Math.min(child.bead,graph.beads.length-1)]]:[0,0],at=map([p[0]+child.x,p[1]+child.y]);ctx.save();ctx.translate(...at);ctx.rotate(Math.atan2(localRight[1],localRight[0])+child.rotation*Math.PI/180);let tinted=image;
    if(child.color!=='#ffffff'){const canvas=document.createElement('canvas');canvas.width=image.naturalWidth;canvas.height=image.naturalHeight;const paint=canvas.getContext('2d');paint.drawImage(image,0,0);paint.globalCompositeOperation='multiply';paint.fillStyle=child.color;paint.fillRect(0,0,canvas.width,canvas.height);paint.globalCompositeOperation='destination-in';paint.drawImage(image,0,0);tinted=canvas;}
    ctx.drawImage(tinted,-child.width*scale/2,-child.height*scale/2,child.width*scale,child.height*scale);ctx.restore();
   }ctx.restore();
  });
 }
}
async function pearlAccessoryImport(value){
 if(value?.schema!=='moreiterators.pearl-accessory.v1'||!value.accessory||typeof value.accessory!=='object')throw Error('请选择珍珠组合文件');
 const pick=(seed,source)=>Object.fromEntries(Object.entries(seed).map(([k,v])=>[k,source[k]===undefined?structuredClone(v):structuredClone(source[k])]));
 const a=pick(pearlAccessoryDefault(),value.accessory);a.anchor='head';
 const number=(o,k,min,max,integer=false)=>{if(typeof o[k]!=='number'||!Number.isFinite(o[k])||o[k]<min||o[k]>max||integer&&!Number.isInteger(o[k]))throw Error('珍珠组合参数无效');};
 const color=value=>{if(typeof value!=='string'||!/^#[a-f0-9]{6}$/i.test(value))throw Error('珍珠组合颜色格式错误');};
 const palette=p=>{if(!p||typeof p!=='object'||typeof p.dual!=='boolean')throw Error('珍珠组合颜色格式错误');color(p.color);color(p.highlight);number(p,'size',0,6);};
 if(typeof a.enabled!=='boolean'||typeof a.name!=='string'||a.name.length>60)throw Error('珍珠组合参数无效');
 for(const [k,min,max] of [['pearls',0,10],['horizontalChains',0,5],['hangingChains',0,5],['colorMode',0,2]])number(a,k,min,max,true);
 for(const [k,min,max] of [['u',0,1],['v',0,1],['x',-200,200],['y',-200,200],['rotation',-180,180],['width',.5,120],['length',.5,160],['sag',0,60],['thickness',.1,3],['size',.6,6],['softness',0,1],['gravity',0,3]])number(a,k,min,max);
 color(a.stringColor);palette(a.primary);palette(a.alternate);a.primary=pick(necklacePearl(),a.primary);a.alternate=pick(necklacePearl(),a.alternate);
 if(!Array.isArray(a.beads)||a.beads.length>10||!Array.isArray(a.children)||a.children.length>8)throw Error('珍珠组合参数无效');
 a.beads=a.beads.map(b=>{if(!b||typeof b!=='object')throw Error('珍珠组合参数无效');b=pick(pearlAccessoryBead(),b);palette(b);number(b,'chain',-1,9,true);number(b,'position',0,1);return b;});
 a.children=await Promise.all(a.children.map(async c=>{if(!c||typeof c!=='object')throw Error('珍珠组合参数无效');c=pick(pearlAccessoryChild(),c);if(typeof c.name!=='string'||c.name.length>60||typeof c.enabled!=='boolean')throw Error('珍珠组合参数无效');for(const [k,min,max] of [['x',-80,80],['y',-80,80],['width',.1,120],['height',.1,120],['rotation',-180,180]])number(c,k,min,max);number(c,'bead',0,9,true);color(c.color);if(typeof c.png!=='string'||c.png.length>6e6)throw Error('子配件只支持 PNG');if(c.png){if(!c.png.startsWith('data:image/png;base64,'))throw Error('子配件只支持 PNG');const image=new Image();image.src=c.png;await image.decode();if(image.naturalWidth>1024||image.naturalHeight>1024)throw Error('子配件 PNG 损坏或超过 1024 × 1024');}return c;}));
 return a;
}
function buildPearlAccessorySettings(host,d,changed){
 const owner=project,version=loadVersion,checkOwner=()=>{if(project!==owner||loadVersion!==version)throw Error(MI18n.text('项目已切换，请重新导入。'));};
 const root=garmentSection(host,'珍珠组合');root.dataset.sectionId='pearlAccessories';
 const field=(host,obj,key,label,type,min,max,step,after)=>garmentField(host,obj,key,label,type,min,max,step,after);
 const button=(host,text,action)=>garmentButton(host,text,action);
 const add=()=>{if(d.pearlAccessories.length>=8)throw Error('珍珠组合最多 8 组');let n=1;while(pearlAccessoryFind(d,'pearlAccessory:'+n))n++;const item=pearlAccessoryDefault(n);d.pearlAccessories.push(item);d.renderOrder.push(item.id);return item;};
 const refresh=()=>{buildSettings();changed();};
 button(root,'新增珍珠组合',()=>{add();refresh();});
 const input=document.createElement('input');input.type='file';input.accept='application/json,.json';input.hidden=true;root.append(input);
 button(root,'导入珍珠组合',()=>input.click());input.onchange=()=>run(async()=>{const file=input.files[0];if(!file)return;const value=await pearlAccessoryImport(JSON.parse(await file.text()));checkOwner();const item=add(),id=item.id;Object.assign(item,value,{id});refresh();})();
 for(const a of d.pearlAccessories){
  const section=garmentSection(root,a.name||a.id);section.dataset.sectionId=a.id;MI18n.content(section.querySelector('summary'));field(section,a,'enabled','启用珍珠组合','checkbox');const body=settingDependency(section,()=>a.enabled);
  field(body,a,'name','组合名称','text');
  const binding=garmentSection(body,'绑定位置');field(binding,a,'anchor','绑定部位','select',wardrobeAnchorOptions(d,a.id));
  for(const [key,label,min,max] of [['u','横向位置',0,1],['v','纵向位置',0,1],['x','左右偏移',-200,200],['y','上下偏移',-200,200],['rotation','旋转角度',-180,180]])field(binding,a,key,label,'range',min,max,.1);
  const shape=garmentSection(body,'链条与珍珠');
  for(const [key,label,max] of [['pearls','珍珠数量',10],['horizontalChains','横向链数量',5],['hangingChains','下垂链数量',5]])field(shape,a,key,label,'range',0,max,1,()=>refreshBeads());
  for(const [key,label,min,max,step] of [['width','组合宽度',.5,120,.1],['length','组合长度',.5,160,.1],['sag','横向链下垂',0,60,.1],['thickness','线的粗细',.1,3,.05],['size','珍珠直径',.6,6,.1],['softness','柔软与弹性',0,1,.01],['gravity','重力影响',0,3,.01]])field(shape,a,key,label,'range',min,max,step);
  field(shape,a,'stringColor','线的颜色','color');
  const paint=garmentSection(body,'珍珠颜色');const paintBody=document.createElement('div');
  function colors(host,value,label){const part=garmentSection(host,label);field(part,value,'dual','双色高光','checkbox');field(part,value,'color','主体色','color');const highlight=settingDependency(part,()=>value.dual);field(highlight,value,'highlight','高光色','color');}
  function refreshColors(){paintBody.replaceChildren();if(a.colorMode!==2)colors(paintBody,a.primary,'主体配色');if(a.colorMode===1)colors(paintBody,a.alternate,'间隔配色');}
  field(paint,a,'colorMode','配色方式','select',{0:'整组一致',1:'交替配色',2:'逐颗设置'},null,null,refreshColors);paint.append(paintBody);refreshColors();
  const beadSection=garmentSection(body,'单颗珍珠');const beadBody=document.createElement('div');beadSection.append(beadBody);
  function refreshBeads(){
   beadBody.replaceChildren();for(let i=0;i<a.pearls;i++)a.beads[i]??=pearlAccessoryBead();if(!a.pearls)return;
   const select=document.createElement('select');select.setAttribute('aria-label','选择珍珠');for(let i=0;i<a.pearls;i++)select.add(new Option(String(i+1),i));const controls=document.createElement('div');beadBody.append(select,controls);
   function show(){controls.replaceChildren();const b=a.beads[+select.value];field(controls,b,'size','直径（0 跟随组合）','range',0,6,.1);button(controls,'复制大小',()=>{necklaceSizeClipboard=b.size||a.size;});button(controls,'粘贴大小',()=>{if(necklaceSizeClipboard===null)return;b.size=necklaceSizeClipboard;show();changed();});field(controls,b,'chain','所在链（-1 自动）','range',-1,Math.max(0,a.horizontalChains+a.hangingChains-1),1);field(controls,b,'position','链上位置','range',0,1,.01);const ownColors=settingDependency(controls,()=>a.colorMode===2);colors(ownColors,b,'单颗配色');}
   select.onchange=show;show();
  }refreshBeads();
  const childSection=garmentSection(body,'子配件');button(childSection,'添加子配件',()=>{if(a.children.length>=8)throw Error('珍珠组合最多 8 个子配件');a.children.push(pearlAccessoryChild());refresh();});
  for(const c of a.children){
   const part=garmentSection(childSection,c.name||'子配件');if(c.name)MI18n.content(part.querySelector('summary'));field(part,c,'enabled','启用子配件','checkbox');const childBody=settingDependency(part,()=>c.enabled);field(childBody,c,'name','子配件名称','text');
   const imageInput=document.createElement('input');imageInput.type='file';imageInput.accept='image/png,.png';imageInput.hidden=true;childBody.append(imageInput);button(childBody,'导入 PNG 贴图',()=>imageInput.click());imageInput.onchange=()=>run(async()=>{const file=imageInput.files[0];if(!file)return;if(file.size>4_500_000)throw Error('子配件只支持 PNG');const png=await new Promise((ok,no)=>{const reader=new FileReader();reader.onload=()=>ok(reader.result);reader.onerror=no;reader.readAsDataURL(file);});const image=new Image();image.src=png;await image.decode();checkOwner();if(!png.startsWith('data:image/png;base64,')||image.naturalWidth>1024||image.naturalHeight>1024)throw Error('子配件 PNG 损坏或超过 1024 × 1024');c.png=png;changed();})();
   field(childBody,c,'bead','绑定珍珠（从 0 起）','range',0,Math.max(0,a.pearls-1),1);
   for(const [key,label,min,max] of [['x','左右偏移',-80,80],['y','上下偏移',-80,80],['width','宽度',.1,120],['height','高度',.1,120],['rotation','旋转角度',-180,180]])field(childBody,c,key,label,'range',min,max,.1);
   field(childBody,c,'color','子配件颜色','color');button(part,'删除子配件',()=>{if(!confirm(MI18n.text('删除这个子配件？')))return;a.children=a.children.filter(x=>x!==c);refresh();});
  }
  button(section,'保存组合文件',()=>{const payload={schema:'moreiterators.pearl-accessory.v1',accessory:structuredClone(a)},url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json'})),link=document.createElement('a');link.href=url;link.download=(a.name||a.id.replace(':','-'))+'.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
  button(section,'删除珍珠组合',()=>{if(!confirm(MI18n.text('删除这个珍珠组合？')))return;d.pearlAccessories=d.pearlAccessories.filter(x=>x!==a);d.renderOrder=d.renderOrder.filter(x=>x!==a.id);refresh();});
 }
}
