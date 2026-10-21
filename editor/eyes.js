'use strict';
const Eyes=(()=>{
 const max=16,tr=(key,args)=>MI18n.t('eyes35.'+key,args);
 function defaults(i){return {id:'eye-'+(i+1),enabled:true,sourceSide:i%2,offsetX:0,offsetY:0,scale:1,color:'',textureEnabled:false,textureTint:false,texturePng:'',textureMirrorX:false,mirrorOf:''};}
 function custom(d){return Array.isArray(d.eyes)&&d.eyes.length>0;}
 // A mirrored eye keeps its own identity and visibility. Its partner supplies
 // geometry and material; the source side remains the opposite animated eye.
 function resolved(list,index){
  const own=list[index];if(!own)return null;
  const source=own.mirrorOf&&list.find(x=>x.id===own.mirrorOf);
  if(!source||source===own||source.mirrorOf)return {...own};
  return {...source,id:own.id,enabled:own.enabled,sourceSide:source.sourceSide===1?0:1,offsetX:-(source.offsetX||0),textureMirrorX:!source.textureMirrorX,mirrorOf:own.mirrorOf};
 }
 function setProperty(list,index,key,value){
  const own=list[index],source=own.mirrorOf&&list.find(x=>x.id===own.mirrorOf);
  if(key==='id'||key==='mirrorOf')return;
  const linked=source&&source!==own&&!source.mirrorOf&&key!=='enabled',dest=linked?source:own;
  dest[key]=linked&&key==='offsetX'?-value:linked&&key==='sourceSide'?(value===1?0:1):linked&&key==='textureMirrorX'?!value:value;
 }
 function proxyFor(list,index,d){
  const proxy={};
  for(const key of Object.keys(defaults(0)))Object.defineProperty(proxy,key,{enumerable:true,get:()=>key==='color'?resolved(list,index).color||d.eyeColor:resolved(list,index)[key],set:value=>setProperty(list,index,key,value)});
  Object.defineProperty(proxy,'inheritColor',{enumerable:true,get:()=>!resolved(list,index).color,set:value=>setProperty(list,index,'color',value?'':resolved(list,index).color||d.eyeColor)});
  return proxy;
 }
 function detach(list,index){const spec=resolved(list,index);Object.assign(list[index],spec,{mirrorOf:''});}
 function mirrorCopy(list,from,to){
  const source=resolved(list,from),dest=list[to];
  detach(list,from);
  Object.assign(dest,source,{id:dest.id,enabled:dest.enabled,sourceSide:source.sourceSide===1?0:1,offsetX:-(source.offsetX||0),textureMirrorX:!source.textureMirrorX,mirrorOf:''});
 }
 function parts(parts,d){
  if(!custom(d))return parts;
  const result=[],sources=[parts.find(p=>p.kind==='eye0'),parts.find(p=>p.kind==='eye1')];let added=false;
  for(const part of parts){if(!part.kind.startsWith('eye')){result.push(part);continue;}if(added)continue;added=true;
   for(let index=0;index<Math.min(max,d.eyes.length);index++){const spec=resolved(d.eyes,index),source=sources[spec.sourceSide===1?1:0];if(source)result.push({...source,kind:'eye'+index,eyeSpec:spec});}
  }return result;
 }
 function geometry(part,d,baseSize,legacy=false,baseSpacing=3.2){
  const spec=part.eyeSpec,xy=part.xy.slice(),cx=xy.filter((_,i)=>i%2===0).reduce((a,b)=>a+b,0)/(xy.length/2),cy=xy.filter((_,i)=>i%2===1).reduce((a,b)=>a+b,0)/(xy.length/2);
  const side=spec?spec.sourceSide:(part.kind==='eye0'?0:1),x=legacy?cx+(side===0?-1:1)*(d.eyeSpacing-baseSpacing):(side===0?-d.eyeSpacing:d.eyeSpacing),y=legacy?cy:1,scale=d.eyeSize/baseSize*(spec?.scale??1);
  for(let i=0;i<xy.length;i+=2){xy[i]=x+(xy[i]-cx)*scale+(spec?.offsetX||0);xy[i+1]=y+(xy[i+1]-cy)*scale-(spec?.offsetY||0);}
  const png=spec?.textureEnabled&&spec.texturePng?spec.texturePng:part.png;
  const color=spec?.textureEnabled&&spec.texturePng&&!spec.textureTint?'#ffffff':spec?.color||d.eyeColor;
  return {xy,png,color,texture:!!(spec?.textureEnabled&&spec.texturePng),flip:!!spec?.textureMirrorX,visible:d.layers.eyes!==false&&spec?.enabled!==false};
 }
 function image(eye){
  if(!eye.png)return null;
  if(!eye.texture)return tintImage(eye.png,eye.color);
  const source=imageOf(eye.png);if(!source)return null;
  if(eye.color==='#ffffff'&&!eye.flip)return source;
  const result=canvas(source.width,source.height),ctx=result.getContext('2d');
  if(eye.flip){ctx.translate(result.width,0);ctx.scale(-1,1);}ctx.drawImage(source,0,0);
  if(eye.color!=='#ffffff'){
   // Multiply RGB while retaining the imported alpha, as FSprite does in game.
   ctx.globalCompositeOperation='multiply';ctx.fillStyle=eye.color;ctx.fillRect(0,0,result.width,result.height);
   ctx.globalCompositeOperation='destination-in';ctx.drawImage(source,0,0);
  }return result;
 }
 function settings(host,d){
  const owner=project,version=loadVersion;
  const section=garmentSection(host,tr('title'));section.dataset.sectionId='eyes';
  settingsLayerSwitch(section,d,'eyes',tr('allEnabled'));
  const body=settingDependency(section,()=>d.layers.eyes!==false);
  garmentField(body,d,'eyeColor',tr('sharedColor'),'color');
  garmentField(body,d,'eyeSpacing',tr('spacing'),'range',1,6,.1);
  garmentField(body,d,'eyeSize',tr('size'),'range',.5,3,.05);
  // Merely opening settings does not create eyes or change an old project.
  const list=custom(d)?d.eyes:[defaults(0),{...defaults(1),mirrorOf:'eye-1'}];
  const controls=[],thumbnails=[];
  const commit=()=>{d.eyes=list;for(const {input,proxy,key,kind} of controls){if(kind==='checkbox')input.checked=!!proxy[key];else input.value=proxy[key];if(kind==='range'){const output=input.closest?.('.field')?.querySelector('output');if(output)output.textContent=proxy[key];}}for(const {image,index} of thumbnails)image.style.transform=resolved(list,index).textureMirrorX?'scaleX(-1)':'';};
  const refresh=()=>{commit();changed();buildSettings();};
  function eyeRow(parent,index,label){
   const spec=list[index],row=garmentSection(parent,label);row.dataset.sectionId=spec.id;
   garmentField(row,spec,'enabled',tr('enabled'),'checkbox',null,null,null,commit);
   const edits=settingDependency(row,()=>spec.enabled!==false),proxy=proxyFor(list,index,d);
   if(spec.mirrorOf)garmentButton(edits,tr('independent'),()=>{detach(list,index);refresh();});
   const field=(host,key,label,kind,min,max,step)=>{const input=garmentField(host,proxy,key,label,kind,min,max,step,()=>{commit();if(key==='sourceSide')buildSettings();});controls.push({input,proxy,key,kind});return input;};
   field(edits,'sourceSide',tr('source'),'select',{0:tr('left'),1:tr('right')});
   for(const [key,label,min,max,step] of [['offsetX','x',-40,40,.1],['offsetY','y',-40,40,.1],['scale','scale',.1,8,.05]])field(edits,key,tr(label),'range',min,max,step);
   field(edits,'inheritColor',tr('inherit'),'checkbox');
   field(settingDependency(edits,()=>!proxy.inheritColor),'color',tr('color'),'color');
   field(edits,'textureEnabled',tr('texture'),'checkbox');
   const texture=settingDependency(edits,()=>proxy.textureEnabled);
   field(texture,'textureTint',tr('tint'),'checkbox');
   field(texture,'textureMirrorX',tr('flip'),'checkbox');
   const input=document.createElement('input');input.type='file';input.accept='image/png';input.hidden=true;texture.append(input);
   garmentButton(texture,tr('import'),()=>input.click());
   input.onchange=run(async()=>{
    const file=input.files?.[0];if(!file)return;
    try{
     if(file.size>1100000)throw Error(tr('invalid'));
     const png=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(Error(tr('invalid')));reader.readAsDataURL(file);});
     if(!png.startsWith('data:image/png;base64,'))throw Error(tr('invalid'));
     const image=new Image();image.src=png;await image.decode();if(project!==owner||loadVersion!==version)throw Error(MI18n.text('项目已切换，请重新导入。'));if(image.width>256||image.height>256)throw Error(tr('invalid'));
     proxy.texturePng=png;proxy.textureEnabled=true;proxy.textureMirrorX=false;refresh();
    }finally{input.value='';}
   });
   if(proxy.texturePng){const image=thumbnail(texture,proxy,label);thumbnails.push({image,index});garmentButton(texture,tr('clear'),()=>{proxy.texturePng='';refresh();});}
  }
  function pair(start,count,number){
   const end=Math.min(start+count,list.length),original=start===0;
   const block=garmentSection(body,original?tr('original'):count===1?tr('extraEye',{index:start-1,side:tr(resolved(list,start).sourceSide===1?'right':'left')}):tr('extraPair',{index:number}));block.dataset.sectionId=original?'originalEyes':'pair-'+list[start].id;
   if(end-start===2){
    const state={sync:list[start+1].mirrorOf===list[start].id};
    garmentField(block,state,'sync',tr('sync'),'checkbox',null,null,null,()=>{
     if(state.sync){detach(list,start);list[start+1].mirrorOf=list[start].id;}else detach(list,start+1);
     refresh();
    });
    const actions=document.createElement('div');actions.className='setting-actions';block.append(actions);
    garmentButton(actions,tr('copyRight'),()=>{mirrorCopy(list,start,start+1);refresh();});
    garmentButton(actions,tr('copyLeft'),()=>{mirrorCopy(list,start+1,start);refresh();});
   }
   for(let i=start;i<end;i++)eyeRow(block,i,original?(resolved(list,i).sourceSide===0?tr('originalLeft'):tr('originalRight')):tr('extraEye',{index:i-1,side:tr(resolved(list,i).sourceSide===1?'right':'left')}));
   if(!original)garmentButton(block,end-start===2?tr('removePair'):tr('remove'),()=>{
    const removed=new Set(list.slice(start,end).map(x=>x.id));
    for(let i=0;i<list.length;i++)if(removed.has(list[i].mirrorOf))detach(list,i);
    list.splice(start,end-start);refresh();
   });
  }
  for(let i=0,number=0;i<list.length;number++){
   const count=i===0?Math.min(2,list.length):(i+1<list.length&&(list[i+1].mirrorOf===list[i].id||(!list[i+1].mirrorOf&&list[i].sourceSide===0&&list[i+1].sourceSide===1))?2:1);
   pair(i,count,number);i+=count;
  }
  const add=garmentButton(body,tr('addPair'),()=>{
   if(list.length>max-2)return;
   if(list.length===1)list.push({...defaults(1),enabled:false});
   const left={...defaults(0),id:'eye-'+crypto.randomUUID().replaceAll('-','').slice(0,16),offsetY:3*Math.max(1,Math.ceil(list.length/2))};
   const right={...left,id:'eye-'+crypto.randomUUID().replaceAll('-','').slice(0,16),sourceSide:1,mirrorOf:left.id,textureMirrorX:true};
   list.push(left,right);refresh();
  });add.disabled=list.length>max-2;
  if(custom(d))garmentButton(body,tr('reset'),()=>{d.eyes=[];changed();buildSettings();});
 }
 function thumbnail(host,spec,label){
  const preview=document.createElement('img');preview.className='part-texture-preview eye-texture-preview';preview.src=spec.texturePng;preview.alt=label;preview.width=48;preview.height=48;
  preview.style.cssText='object-fit:contain;image-rendering:pixelated'+(spec.textureMirrorX?';transform:scaleX(-1)':'');host.append(preview);return preview;
 }
 return {defaults,custom,resolved,setProperty,proxyFor,detach,mirrorCopy,parts,geometry,image,settings,max};
})();
