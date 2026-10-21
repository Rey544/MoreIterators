'use strict';
const HeadSegments=(()=>{
 const materialPrefixes=['antenna','antennaLower','ear','earDecoration'];
 const tr=(key,args)=>MI18n.t('head28.'+key,args);
 const specs=[{prefix:'antennaLower',title:'天线下段',width:2.4,height:10,spread:8.2,y:0,size:[24,48]},
              {prefix:'earDecoration',title:'耳机下段装饰',width:3,height:10,spread:8,y:-9,size:[24,32]}];
 const limits={antennaHeight:[3,80],antennaWidth:[.3,8],antennaSpread:[0,40],antennaOffsetY:[-40,80],earWidth:[1,24],earHeight:[2,40],earOffsetX:[-8,40],earOffsetY:[-80,80]};
 function prefix(key){return key.startsWith('antennaLower')?'antennaLower':key.startsWith('earDecoration')?'earDecoration':key.startsWith('ear')?'ear':'antenna';}
 function init(p){
  p.editor??={};p.editor.headTextureMirror??={};
  p.design.antennaUpperEnabled??=true;p.design.earBodyEnabled??=true;
  for(const s of specs){const defaults={Enabled:false,Custom:false,Tint:false,Color:'#334542',InnerColor:'#9cafaa',OuterColor:'#323e3d',Width:s.width,Height:s.height,Spread:s.spread,OffsetY:s.y};
   for(const [suffix,value] of Object.entries(defaults))p.design[s.prefix+suffix]??=value;
   for(const side of ['L','R'])dimensions[s.prefix+side]=s.size;
  }
  for(const part of materialPrefixes)for(const layer of ['Inner','Outer']){p.design[part+layer+'Mode']||=p.design[part+'Tint']?'solid':'original';p.design[part+layer+'EndColor']??=p.design[part+layer+'Color']||(layer==='Inner'?'#9cafaa':'#323e3d');p.design[part+layer+'Direction']??='vertical';}
 }
 function targets(){
  const select=$('target'),group=select.querySelector('[value="antennaL"]')?.parentElement||select;
  for(const part of materialPrefixes)for(const side of ['L','R']){const key=part+side;let option=select.querySelector('[value="'+key+'"]');if(!option){option=new Option('',key);group.append(option);}option.textContent=tr('partSide',{part:tr(part),side:tr(side==='L'?'left':'right')});}
  for(const part of ['ear','earDecoration','antenna','antennaLower'])for(const side of ['L','R'])group.append(select.querySelector('[value="'+part+side+'"]'));
 }
 function materialSettings(host,d,part){
  for(const layer of ['Inner','Outer']){
   const section=garmentSection(host,MI18n.t(layer==='Inner'?'paint.innerMask':'paint.outerMask'));section.dataset.sectionId=part+'-'+layer;
   const modes={original:tr('original'),solid:tr('solid'),gradient:tr('gradient')};
   garmentField(section,d,part+layer+'Mode',tr('material'),'select',modes);
   const color=settingDependency(section,()=>d[part+layer+'Mode']!=='original');
   garmentField(color,d,part+layer+'Color',tr('color'),'color');
   const gradient=settingDependency(color,()=>d[part+layer+'Mode']==='gradient');
   garmentField(gradient,d,part+layer+'EndColor',tr('endColor'),'color');
   garmentField(gradient,d,part+layer+'Direction',tr('direction'),'select',{'vertical':tr('down'),'vertical-reverse':tr('up'),'horizontal':tr('rightward'),'horizontal-reverse':tr('leftward')});
  }
 }
 function settings(parent,d){
  const tx=key=>MI18n.t('head36.'+key);
  const pieces=[
   {part:'ear',owner:'ear',title:tx('earBody'),enabled:'earBodyEnabled',geometry:[['earWidth','width',1,24],['earHeight','length',2,40],['earOffsetX','spread',-8,40],['earOffsetY','offsetY',-80,80]]},
   {part:'earDecoration',owner:'ear',title:tr('earDecoration'),enabled:'earDecorationEnabled'},
   {part:'antenna',owner:'antenna',title:tx('upper'),enabled:'antennaUpperEnabled',geometry:[['antennaWidth','width',.3,8],['antennaHeight','length',3,80],['antennaSpread','spread',0,40],['antennaOffsetY','offsetY',-40,80]]},
   {part:'antennaLower',owner:'antenna',title:tx('lower'),enabled:'antennaLowerEnabled'}
  ];
  for(const piece of pieces){
   const {part,owner}=piece,host=settingDependency(parent[owner],()=>d.layers[owner==='ear'?'ears':'antenna']!==false);
   const group=garmentSection(host,piece.title);group.dataset.sectionId=part+'-piece';garmentField(group,d,piece.enabled,tr('enabled'),'checkbox');
   const body=settingDependency(group,()=>d[piece.enabled]);
   const geometry=garmentSection(body,tx('geometry'));
   const defs=piece.geometry||[['Width','width',.2,24],['Height','length',.2,40],['Spread','spread',0,40],['OffsetY','offsetY',-80,40]].map(([key,...rest])=>[part+key,...rest]);
   for(const [key,label,min,max] of defs){if(project.legacyOracle&&key==='antennaOffsetY')continue;garmentField(geometry,d,key,tr(label),'range',min,max,.1);}
   const look=garmentSection(body,tx('appearance'));
   if(part==='antenna')garmentField(look,d,'antennaColor',tx('defaultTip'),'color');
   else garmentField(look,d,part==='ear'?'metalColor':part+'Color',tx('baseColor'),'color');
   if(part!=='antenna')garmentField(look,d,part+'Custom',tx('customTexture'),'checkbox');
   const materials=part==='antenna'?look:settingDependency(look,()=>d[part+'Custom']);
   materialSettings(materials,d,part);
   const textures=garmentSection(body,tx('textures'));
   garmentField(textures,project.editor.headTextureMirror,part,tx('syncTextures'),'checkbox',null,null,null,()=>{if(project.editor.headTextureMirror[part])copyTexture(part+'L',part+'R');});
   garmentButton(textures,tr('paintLeft'),()=>garmentPaint(part+'L'));garmentButton(textures,tr('paintRight'),()=>garmentPaint(part+'R'));
   garmentButton(textures,tx('copyLeft'),()=>{copyTexture(part+'L',part+'R');changed();});
   garmentButton(textures,tx('copyRight'),()=>{copyTexture(part+'R',part+'L');changed();});
  }
 }
 function copyTexture(from,to){
  if(typeof PaintLayers!=='undefined'){PaintLayers.copyTexture(from,to);project.textures[to].custom=project.textures[from].custom;return;}
  if(!canvases[from]||!canvases[to])return;
  canvases[from].forEach((c,i)=>{const dest=canvases[to][i],ctx=dest.getContext('2d');ctx.clearRect(0,0,dest.width,dest.height);ctx.save();ctx.translate(dest.width,0);ctx.scale(-1,1);ctx.drawImage(c,0,0,dest.width,dest.height);ctx.restore();Object.assign(project.textures[to].layers[i],{visible:project.textures[from].layers[i].visible,opacity:project.textures[from].layers[i].opacity});});
  project.textures[to].custom=project.textures[from].custom;
 }
 function syncTexture(key){if(!key||!headTexture(key)||!project?.editor?.headTextureMirror?.[prefix(key)])return;const other=key.slice(0,-1)+(key.endsWith('L')?'R':'L');try{copyTexture(key,other);}catch(error){notice(error.message,true);}}
 function recolor(ctx,w,h,d,key,index){
  const part=prefix(key),layer=index?'Outer':'Inner',mode=d[part+layer+'Mode']||(d[part+'Tint']?'solid':'original');if(mode==='original')return;
  const rgb=c=>c.match(/[a-f\d]{2}/gi).map(x=>parseInt(x,16));
  const color=d[part+layer+'Color']||(index?'#323e3d':'#9cafaa'),start=rgb(color),end=rgb(d[part+layer+'EndColor']||color),direction=d[part+layer+'Direction']||'vertical';
  const image=ctx.getImageData(0,0,w,h),horizontal=direction.startsWith('horizontal'),extent=horizontal?w:h;
  for(let y=0;y<h;y++)for(let x=0;x<w;x++){let t=(horizontal?x:y)/Math.max(1,extent-1);if(direction.endsWith('-reverse'))t=1-t;if(mode==='solid')t=0;for(let c=0;c<3;c++)image.data[(y*w+x)*4+c]=Math.round(start[c]+(end[c]-start[c])*t);}
  ctx.putImageData(image,0,0);
 }
 function layerLabel(layer,index,hardware){
  const name=String(layer.name??'');if(layer.customName===true)return name;
  const key=hardware?(index?'default.layer_outer':'default.layer_inner'):(index?'default.layer_texture':'default.layer_base');
  const defaults=hardware?(index?['外层（前）','Outer (front)','Outer layer (front)']:['内层（后）','Inner (back)','Inner layer (back)']):index?['纹理 '+index,'纹理'+index,'Texture '+index]:['底图','Base image','Base layer'];
  return !name||defaults.includes(name)?MI18n.t(key,{index}):name;
 }
 function markCustom(key){const p=prefix(key);if(p!=='antenna'){project.design[p+'Custom']=true;const input=document.querySelector('[data-wardrobe-key="'+p+'Custom"]');if(input)input.checked=true;}if(project.textures[key])project.textures[key].custom=true;syncSettingDependencies();}
 function draw(ctx,d,material){
  for(const s of specs){if(!d[s.prefix+'Enabled']||d.layers[s.prefix==='antennaLower'?'antenna':'ears']===false)continue;
   for(const side of [-1,1]){const width=d[s.prefix+'Width'],height=d[s.prefix+'Height'],x=side*d[s.prefix+'Spread']-width/2,y=-d[s.prefix+'OffsetY']-height/2;
    if(d[s.prefix+'Custom'])ctx.drawImage(material(s.prefix+(side<0?'L':'R')),x,y,width,height);
    else{ctx.fillStyle=d[s.prefix+'Color'];ctx.fillRect(x,y,width,height);}
   }
  }
 }
 function anchors(d,head=[0,0],material){
  const result={},scale=d.puppetScale||1;
  function rectangle(key,cx,cy,w,h){result[key]={sample:(u,v)=>[head[0]+(cx+(u-.5)*w)*scale,head[1]+(cy+(v-.5)*h)*scale]};}
  for(const side of [-1,1]){const suffix=side<0?'L':'R';rectangle('ear'+suffix,side*(8+d.earOffsetX),-.5-d.earOffsetY,d.earWidth,d.earHeight);
   const texture=material?.('antenna'+suffix),painted=texture?.getContext('2d').getImageData(0,0,texture.width,texture.height).data.some((v,i)=>i%4===3&&v);
   if(painted)rectangle('antennaUpper'+suffix,side*d.antennaSpread,-2-d.antennaOffsetY-d.antennaHeight/2,d.antennaWidth*4,d.antennaHeight+4);
   else result['antennaUpper'+suffix]={sample:(u,v)=>{const t=1-Math.max(0,Math.min(1,v)),segment=Math.min(7,Math.floor(t*8)),width=d.antennaWidth*(segment>=5&&segment%2===1?.48:1);return [head[0]+(side*(d.antennaSpread+t*.8)+(u*2-1)*width)*scale,head[1]+(-2-d.antennaOffsetY-t*d.antennaHeight)*scale];}};
   result['antenna'+suffix]=result['antennaUpper'+suffix];
   for(const s of specs)rectangle(s.prefix+suffix,side*d[s.prefix+'Spread'],-d[s.prefix+'OffsetY'],d[s.prefix+'Width'],d[s.prefix+'Height']);
  }
  return result;
 }
 return {specs,limits,prefix,init,targets,settings,markCustom,draw,anchors,recolor,layerLabel,copyTexture,syncTexture};
})();
