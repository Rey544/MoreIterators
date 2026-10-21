'use strict';
const PuppetArms=(()=>{
 const text=(zh,en)=>MI18n.locale==='en'?en:zh;
 const defaults=i=>({enabled:i<2,sleeveEnabled:true,handOwnColor:false,handColor:'#a6aaa9',handTextureEnabled:false,handTextureTint:false,sleeveTextureEnabled:true,sleeveOwnColor:false,sleeveOwnTexture:false,sleeveColor:'#b68b8e',lengthScale:1,widthScale:1,handSize:1,shoulderX:0,shoulderY:i>=2?-8:0,sleeveRootX:0,sleeveRootY:0,handPng:'',sleeveBasePng:'',sleevePng:''});
 const pairKey=i=>i<2?'puppetArmSymmetry':'puppetExtraArmSymmetry';
 const mirrored=(d,i)=>i%2===1&&d[pairKey(i)];
 const sleeveFields=['widthScale','sleeveRootX','sleeveRootY','sleeveOwnColor','sleeveColor','sleeveTextureEnabled','sleeveOwnTexture','sleeveBasePng','sleevePng'];
 const sleevePairKey=i=>i<2?'sleeveSymmetry':'puppetExtraSleeveSymmetry';
 const sleeveMirrored=(d,i)=>i%2===1&&(d.puppetSleeveSyncSeparated?d[sleevePairKey(i)]:d[pairKey(i)]);
 const sleeveKey=i=>i<2?(i?'sleeveR':'sleeve'):'puppetSleeve'+i;
 const sleeveTarget=key=>['sleeve','sleeveR','puppetSleeve2','puppetSleeve3'].includes(key);
 const sideTarget=key=>sleeveTarget(key)||/^puppetHand[0-3]$/.test(key);
 let selectedSide=null;
 function resolved(d,i){const mirror=mirrored(d,i),sm=sleeveMirrored(d,i),a={...defaults(i),...d.puppetArms[mirror?i-1:i]},own=d.puppetArms[i],sleeve={...defaults(i),...d.puppetArms[sm?i-1:i]};a.handTextureTint=d.puppetArms[mirror?i-1:i].handTextureTint??d.puppetArms[mirror?i-1:i].handOwnColor??false;for(const key of sleeveFields)a[key]=sleeve[key];a.enabled=own.enabled;a.sleeveEnabled=own.sleeveEnabled;if(mirror)a.shoulderX*=-1;if(sm)a.sleeveRootX*=-1;return a;}
 function init(p){const d=p.design;d.puppetArmSymmetry??=true;d.puppetExtraArmSymmetry??=true;d.puppetSleeveSyncSeparated??=false;d.puppetExtraSleeveSymmetry??=d.puppetExtraArmSymmetry;d.puppetArms=Array.from({length:4},(_,i)=>({...defaults(i),...d.puppetArms?.[i],handTextureTint:d.puppetArms?.[i]?.handTextureTint??d.puppetArms?.[i]?.handOwnColor??false}));for(let i=0;i<4;i++)dimensions['puppetHand'+i]=[32,32];for(let i=2;i<4;i++)dimensions['puppetSleeve'+i]=[32,64];}
 function name(i){return [text('原版左手','Original left hand'),text('原版右手','Original right hand'),text('新增左手','Added left hand'),text('新增右手','Added right hand')][i];}
 function copyTexture(from,to,mirror=true){if(typeof PaintLayers!=='undefined'){PaintLayers.copyTexture(from,to,mirror);return;}if(!canvases[from]||!canvases[to])return;canvases[from].forEach((source,i)=>{const dest=canvases[to][i],ctx=dest.getContext('2d');ctx.clearRect(0,0,dest.width,dest.height);ctx.save();ctx.imageSmoothingEnabled=false;if(mirror){ctx.translate(dest.width,0);ctx.scale(-1,1);}ctx.drawImage(source,0,0,dest.width,dest.height);ctx.restore();Object.assign(project.textures[to].layers[i],{visible:project.textures[from].layers[i].visible,opacity:project.textures[from].layers[i].opacity});});project.textures[to].editableBase=project.textures[from].editableBase;}
 function copySleeveColors(d,from,to){const source=from===0?(d.sleeveOwn?'sleeve':'cloth'):'sleeveRight',dest=to===0?'sleeve':'sleeveRight';for(const suffix of ['TopColor','MiddleColor','BottomColor','Grain'])d[dest+suffix]=d[source+suffix];if(to===0)d.sleeveOwn=true;}
 function copySide(d,from,to,geometry=true,material=true){
  if(typeof PaintLayers!=='undefined'){if(geometry)PaintLayers.requireWritableTexture('puppetHand'+to);if(material&&!d.puppetSleeveSyncSeparated)PaintLayers.requireWritableTexture(sleeveKey(to));}
  if(geometry){const a=resolved(d,from),own=d.puppetArms[to];a.enabled=own.enabled;a.sleeveEnabled=own.sleeveEnabled;a.shoulderX*=-1;a.sleeveRootX*=-1;if(d.puppetSleeveSyncSeparated)for(const key of sleeveFields)a[key]=own[key];d.puppetArms[to]=a;copyTexture('puppetHand'+(mirrored(d,from)?from-1:from),'puppetHand'+to,!mirrored(d,from));}
  if(d.puppetSleeveSyncSeparated)return;
  if(material){if(from<2){copySleeveColors(d,from,to);copyTexture(sleeveKey(from),sleeveKey(to));}else if(resolved(d,from).sleeveOwnTexture){copyTexture(sleeveKey(mirrored(d,from)?from-1:from),sleeveKey(to),!mirrored(d,from));}else{
   // Freeze the inherited source when unlinking. Otherwise the new right sleeve
   // unexpectedly switches to an unrelated independently painted original right sleeve.
   const sourceSide=mirrored(d,from)?0:from%2,source=sleeveMaterial(sourceSide?'sleeveR':'sleeve'),key=sleeveKey(to),tex=project.textures[key];
   if(canvases[key]&&tex){canvases[key].forEach((c,index)=>{const ctx=c.getContext('2d');ctx.clearRect(0,0,c.width,c.height);if(index===0){ctx.save();ctx.imageSmoothingEnabled=false;ctx.translate(c.width,0);ctx.scale(-1,1);ctx.drawImage(source,0,0,c.width,c.height);ctx.restore();}tex.layers[index].visible=true;tex.layers[index].opacity=1;});tex.editableBase=true;d.puppetArms[to].sleeveOwnTexture=true;}
  }}
 }
 function sleeveLayers(d,index){
  const a=resolved(d,index),sm=sleeveMirrored(d,index),own=index>=2&&a.sleeveOwnTexture;
  const side=index>=2&&sm?0:index%2,key=own?sleeveKey(sm?index-1:index):side&&d.sleeveSymmetry?'sleeve':side?'sleeveR':'sleeve';
  let base=clothBase(key),ink=patternComposite(key);const flipped=own?sm:(side===1&&d.sleeveSymmetry)!==(index>=2&&sm);
  if(flipped){base=flip(base);ink=flip(ink);}return {base,ink};
 }
 function writeSleeve(index,layers,mirroredCopy=false){
  const key=sleeveKey(index),tex=project.textures[key];if(!canvases[key]||!tex)return;if(typeof PaintLayers!=='undefined'){PaintLayers.requireWritableTexture(key);if(tex.layers.length===1)PaintLayers.append(key,false);}
  canvases[key].forEach((c,i)=>{const ctx=c.getContext('2d');ctx.clearRect(0,0,c.width,c.height);if(i<2){ctx.save();ctx.imageSmoothingEnabled=false;if(mirroredCopy){ctx.translate(c.width,0);ctx.scale(-1,1);}ctx.drawImage(i?layers.ink:layers.base,0,0,c.width,c.height);ctx.restore();}tex.layers[i].visible=true;tex.layers[i].opacity=1;});tex.editableBase=true;
  if(index>=2)project.design.puppetArms[index].sleeveOwnTexture=true;
 }
 function finishLoad(){
  const d=project.design;
  if(!d.puppetSleeveSyncSeparated){
   const right=resolved(d,1),oldMaterialSync=d.sleeveSymmetry,oldShapeSync=d.puppetArmSymmetry;
   const freeze=oldMaterialSync&&!oldShapeSync&&canvases.sleeve?sleeveLayers(d,1):null;
   for(const key of sleeveFields)d.puppetArms[1][key]=right[key];
   d.sleeveSymmetry=oldMaterialSync&&oldShapeSync;d.puppetExtraSleeveSymmetry=d.puppetExtraArmSymmetry;d.puppetSleeveSyncSeparated=true;
   if(freeze)writeSleeve(1,freeze);
  }
  for(let i=0;i<2;i++){const key=i?'sleeveRightEnabled':'sleeveLeftEnabled';d.puppetArms[i].sleeveEnabled=d.puppetArms[i].sleeveEnabled&&d[key]!==false;d[key]=true;}
 }
 function setSync(d,pair,enabled){const selection=currentSelection(),left=pair*2,key=pairKey(left);if(!enabled&&d[key])copySide(d,left,left+1);if(enabled&&!d[key]&&selection==='puppetHand'+(left+1))copySide(d,left+1,left);d[key]=enabled;if(!d.puppetSleeveSyncSeparated&&!pair)d.sleeveSymmetry=enabled;restoreSelection(selection);}
 function setSleeveSync(d,pair,enabled){
  const selection=currentSelection(),left=pair*2,right=left+1,key=sleevePairKey(left);
  if(!enabled&&d[key]){if(typeof PaintLayers!=='undefined')PaintLayers.requireWritableTexture(sleeveKey(right));const value=resolved(d,right),layers=canvases[sleeveKey(left)]?sleeveLayers(d,right):null;d[key]=false;for(const field of sleeveFields)d.puppetArms[right][field]=value[field];if(layers)writeSleeve(right,layers);}
  // When linking from the right editor, keep its artwork as the source of the new pair.
  if(enabled&&!d[key]&&selection===sleeveKey(right)){if(typeof PaintLayers!=='undefined')PaintLayers.requireWritableTexture(sleeveKey(left));const value=resolved(d,right),layers=canvases[sleeveKey(right)]?sleeveLayers(d,right):null;for(const field of sleeveFields)d.puppetArms[left][field]=value[field];d.puppetArms[left].sleeveRootX*=-1;if(layers)writeSleeve(left,layers,true);}
  d[key]=enabled;
  restoreSelection(selection);
 }
 function copySleeve(d,from,to,full=true){
  const value=resolved(d,from),layers=sleeveLayers(d,from),dest=sleeveMirrored(d,to)?to-1:to,flipCopy=from%2!==dest%2;if(typeof PaintLayers!=='undefined')PaintLayers.requireWritableTexture(sleeveKey(dest));
  if(full){for(const key of sleeveFields)d.puppetArms[dest][key]=value[key];if(flipCopy)d.puppetArms[dest].sleeveRootX*=-1;}
  writeSleeve(dest,layers,flipCopy);if(!full)d.puppetArms[dest].sleeveTextureEnabled=true;
 }
 function editModel(d,i){return new Proxy({}, {get(_,key){return resolved(d,i)[key];},set(_,key,value){const own=['enabled','sleeveEnabled'].includes(key),mirror=sleeveFields.includes(key)?sleeveMirrored(d,i):mirrored(d,i),index=own?i:mirror?i-1:i;d.puppetArms[index][key]=!own&&mirror&&['shoulderX','sleeveRootX'].includes(key)?-value:value;return true;}});}
 function refreshFields(){for(const refresh of fieldRefresh)refresh();}
 let fieldRefresh=[];
 function field(host,obj,key,label,kind,min,max,step){const input=garmentField(host,obj,key,label,kind,min,max,step,refreshFields);fieldRefresh.push(()=>{if(document.activeElement===input)return;if(kind==='checkbox')input.checked=!!obj[key];else input.value=obj[key];const out=input.parentElement.querySelector('output');if(out)out.textContent=obj[key];});return input;}
 function targets(){const sel=$('target');sel.querySelectorAll('[data-puppet-arms]').forEach(x=>x.remove());const group=document.createElement('optgroup');group.label=text('手掌与新增袖子','Hands and added sleeves');group.dataset.puppetArms='1';for(let i=0;i<4;i++){const option=new Option(name(i),'puppetHand'+i);option.dataset.puppetArms='1';group.append(option);}for(let i=2;i<4;i++){const option=new Option(i===2?text('新增左袖','Added left sleeve'):text('新增右袖','Added right sleeve'),'puppetSleeve'+i);option.dataset.puppetArms='1';group.append(option);}sel.append(group);sel.value=selectedTarget(target);}
 function canonical(key){const d=project.design,match=/^puppet(Hand|Sleeve)([0-3])$/.exec(key);if(match&&(match[1]==='Sleeve'?sleeveMirrored(d,+match[2]):mirrored(d,+match[2])))return 'puppet'+match[1]+(+match[2]-1);if(key==='sleeveR'&&d.sleeveSymmetry)return 'sleeve';return key;}
 function select(key){selectedSide=sideTarget(key)?key:null;return canonical(key);}
 function selectedTarget(key){return selectedSide&&canonical(selectedSide)===key?selectedSide:key;}
 function currentSelection(){return typeof target==='string'?selectedTarget(target):null;}
 function restoreSelection(key){if(key===null||typeof target==='undefined')return;target=canonical(key);selectedSide=sideTarget(key)?key:null;if(typeof updateTarget==='function')updateTarget();}
 function paintMirrored(key){return sideTarget(selectedTarget(key))&&selectedTarget(key)!==key;}
 function paintX(x,width,key){return paintMirrored(key)?width-1-x:x;}
 function drawImported(ctx,image,key,width,height){ctx.save();ctx.imageSmoothingEnabled=false;if(paintMirrored(key)){ctx.translate(width,0);ctx.scale(-1,1);}ctx.drawImage(image,0,0,width,height);ctx.restore();}
 function textureChanged(key,imported=false){const d=project.design,match=/^puppet(Hand|Sleeve)([0-3])$/.exec(canonical(key));if(match){const i=+match[2],a=d.puppetArms[i];if(match[1]==='Hand'){a.handTextureEnabled=true;if(imported)a.handTextureTint=false;}else{a.sleeveOwnTexture=true;a.sleeveTextureEnabled=true;}}else if(key==='sleeve'||key==='sleeveR'){const i=key==='sleeveR'&&!d.sleeveSymmetry?1:0;d.puppetArms[i].sleeveTextureEnabled=true;}refreshFields();syncSettingDependencies();}
 function paint(key){garmentPaint(select(key));}
 async function importTexture(file,key){
  if(!file)return;if(file.size>5*1024*1024)throw Error(text('图片不能超过 5 MB','Image must be 5 MB or smaller'));
  const owner=project,requestedKey=key,resolvedKey=canonical(key);if(typeof PaintLayers!=='undefined'){if(project.textures[resolvedKey].layers.length>1)PaintLayers.requireEditable(resolvedKey,1);PaintLayers.requireBaseInitialization(resolvedKey);}
  const url=URL.createObjectURL(file);let im=new Image();try{im.src=url;await im.decode();if(project!==owner)throw Error(text('项目已切换，请重新导入。','Project changed; import again.'));if(!im.naturalWidth||!im.naturalHeight)throw Error(text('图片无法读取','Cannot read this image'));if(canonical(requestedKey)!==resolvedKey)throw Error(text('贴图同步设置已改变，请重新导入。','Texture linking changed; import again.'));if(typeof HandTextureBase!=='undefined'&&!await HandTextureBase.prepare(resolvedKey))throw Error(MI18n.t('hand.textureLoading'));if(project!==owner||canonical(requestedKey)!==resolvedKey)throw Error(text('项目或贴图已改变，请重新导入。','Project or texture changed; import again.'));if(typeof PaintLayers!=='undefined'){if(project.textures[resolvedKey].layers.length>1)PaintLayers.requireEditable(resolvedKey,1);PaintLayers.requireBaseInitialization(resolvedKey);}key=select(requestedKey);target=key;activeLayer=1;$('target').value=selectedTarget(key);checkpoint();if(project.textures[key].layers.length===1)PaintLayers.append(key,false);if(typeof HandTextureBase!=='undefined')HandTextureBase.ensure(key);textureChanged(key,true);const c=canvases[key][1],ctx=c.getContext('2d');ctx.clearRect(0,0,c.width,c.height);drawImported(ctx,im,key,c.width,c.height);project.textures[key].layers[1].visible=true;project.textures[key].layers[1].opacity=1;updateTarget();buildSettings();changed();}finally{URL.revokeObjectURL(url);}
 }
 function textureControls(host,key){
  const controls=document.createElement('div');controls.className='part-texture-actions';host.append(controls);
  garmentButton(controls,text('编辑贴图','Edit texture'),()=>paint(key));const upload=document.createElement('input');upload.type='file';upload.accept='image/png,image/jpeg,image/webp';upload.hidden=true;upload.onchange=run(async()=>{await importTexture(upload.files[0],key);upload.value='';});controls.append(upload);garmentButton(controls,text('导入图片','Import image'),()=>upload.click());
  const thumb=canvas(48,64);thumb.className='part-texture-preview';thumb.setAttribute('aria-label',text('贴图预览','Texture preview'));
  const redraw=()=>{const ctx=thumb.getContext('2d');ctx.clearRect(0,0,thumb.width,thumb.height);ctx.imageSmoothingEnabled=false;const src=key.startsWith('puppetHand')?handMaterial(key):sleeveAppearance(project.design,key==='sleeve'?0:key==='sleeveR'?1:+key.slice(-1));const scale=Math.min(thumb.width/src.width,thumb.height/src.height),w=src.width*scale,h=src.height*scale;ctx.drawImage(src,(thumb.width-w)/2,(thumb.height-h)/2,w,h);};
  redraw();fieldRefresh.push(redraw);controls.prepend(thumb);
 }
 function settings(buckets,d){
  fieldRefresh=[];const host=garmentSection(buckets.body,text('手臂与袖子','Arms and sleeves'));host.dataset.sectionId='puppetArms';
  settingsLayerSwitch(host,d,'hands',text('显示手掌','Show hands'));settingsLayerSwitch(host,d,'sleeves',text('显示袖子','Show sleeves'));
  field(host,d,'armLength',text('总体手臂长度','Overall arm length'),'range',.7,1.4,.01);field(host,d,'sleeveWidth',text('总体袖子宽度','Overall sleeve width'),'range',2,8,.1);
  if(d.sleeveMapping!=='front')garmentButton(host,text('转换为正面贴图','Convert sleeve textures to front view'),convertSleevesToFront);
  for(let pair=0;pair<2;pair++){
   const section=garmentSection(host,pair?text('新增手臂','Added arms'):text('原版手臂','Original arms'));section.dataset.sectionId='armPair'+pair;
   const sync={};Object.defineProperty(sync,'enabled',{get:()=>d[pairKey(pair*2)],set:value=>setSync(d,pair,value)});
   garmentField(section,sync,'enabled',text('手臂与手掌左右镜像同步','Mirror arms and hands'),'checkbox',null,null,null,buildSettings);
   const sleeveSync={};Object.defineProperty(sleeveSync,'enabled',{get:()=>d[sleevePairKey(pair*2)],set:value=>setSleeveSync(d,pair,value)});
   garmentField(section,sleeveSync,'enabled',text('袖子左右镜像同步','Mirror sleeves'),'checkbox',null,null,null,buildSettings);
   for(let i=pair*2;i<pair*2+2;i++){
    const a=editModel(d,i),row=garmentSection(section,i%2?text('右手','Right hand'):text('左手','Left hand'));row.dataset.sectionId='puppetArm'+i;
    field(row,a,'enabled',text('启用这只手臂','Enable this arm'),'checkbox');const body=settingDependency(row,()=>d.puppetArms[i].enabled);
    const shape=garmentSection(body,text('位置与形状','Position and shape'));
    for(const [key,zh,en,lo,hi,step] of [['shoulderX','肩部左右偏移','Shoulder horizontal offset',-40,40,.25],['shoulderY','肩部上下偏移','Shoulder vertical offset',-40,40,.25],['lengthScale','手臂长度比例','Arm length scale',.25,2.5,.01]])field(shape,a,key,text(zh,en),'range',lo,hi,step);
    const hand=garmentSection(body,text('手掌','Hand'));field(hand,a,'handSize',text('手掌大小','Hand size'),'range',.25,3,.01);
    field(hand,a,'handOwnColor',text('独立手掌颜色','Custom hand color'),'checkbox');const hc=settingDependency(hand,()=>a.handOwnColor);field(hc,a,'handColor',text('颜色','Color'),'color');field(hand,a,'handTextureEnabled',text('使用贴图','Use texture'),'checkbox');const ht=settingDependency(hand,()=>a.handTextureEnabled);field(ht,a,'handTextureTint',text('用手掌颜色染色贴图','Tint texture with hand color'),'checkbox');textureControls(hand,'puppetHand'+i);
    const sleeve=garmentSection(body,text('袖子','Sleeve'));field(sleeve,a,'sleeveEnabled',text('启用这侧袖子','Enable this sleeve'),'checkbox');const sb=settingDependency(sleeve,()=>d.puppetArms[i].sleeveEnabled);
    for(const [key,zh,en,lo,hi,step] of [['sleeveRootX','肩部缝线左右偏移','Shoulder seam horizontal offset',-40,40,.25],['sleeveRootY','肩部缝线上下偏移','Shoulder seam vertical offset',-40,40,.25],['widthScale','袖子宽度比例','Sleeve width scale',.25,3,.01]])field(sb,a,key,text(zh,en),'range',lo,hi,step);
    field(sb,a,'sleeveOwnColor',text('整体染色','Tint sleeve'),'checkbox');const tint=settingDependency(sb,()=>a.sleeveOwnColor);field(tint,a,'sleeveColor',text('染色颜色','Tint color'),'color');
    if(i<2){const palette=garmentSection(sb,text('底色','Base colors'));const index=sleeveMirrored(d,i)?0:i,prefix=index?'sleeveRight':'sleeve';if(!index)field(palette,d,'sleeveOwn',text('独立底色','Custom base colors'),'checkbox');const colors=settingDependency(palette,()=>index===1||d.sleeveOwn);for(const [suffix,zh,en] of [['TopColor','上部','Top'],['MiddleColor','中部','Middle'],['BottomColor','末端','End']])field(colors,d,prefix+suffix,text(zh,en),'color');field(colors,d,prefix+'Grain',text('颗粒','Grain'),'range',0,.4,.01);}
    field(sb,a,'sleeveTextureEnabled',text('显示袖子材质','Show sleeve material'),'checkbox');if(i>=2)field(sb,a,'sleeveOwnTexture',text('使用独立贴图','Use independent texture'),'checkbox');textureControls(sb,sleeveKey(i));
    const copies=document.createElement('div');copies.className='setting-actions';sb.append(copies);const destination=document.createElement('select');destination.setAttribute('aria-label',text('复制袖子到','Copy sleeve to'));const destinations=new Set();
    for(let j=0;j<4;j++){const canonical=sleeveMirrored(d,j)?j-1:j;if(canonical===(sleeveMirrored(d,i)?i-1:i)||destinations.has(canonical))continue;destinations.add(canonical);const paired=d[sleevePairKey(j)];destination.append(new Option((j<2?text('原版','Original'):text('新增','Added'))+(paired?text('两侧袖子',' both sleeves'):j%2?text('右袖',' right sleeve'):text('左袖',' left sleeve')),String(canonical)));}
    const preferred=i<2?2:0;if(destinations.has(preferred))destination.value=String(preferred);copies.append(destination);
    const duplicate=full=>{checkpoint();copySleeve(d,i,+destination.value,full);buildSettings();changed();};garmentButton(copies,text('只复制贴图','Copy texture only'),()=>duplicate(false));garmentButton(copies,text('复制整套袖子','Copy complete sleeve'),()=>duplicate(true));
    const copy=settingDependency(body,()=>!d[pairKey(i)]);garmentButton(copy,text('镜像复制手臂与手掌到另一侧','Mirror arm and hand to other side'),()=>{checkpoint();copySide(d,i,i%2?i-1:i+1);buildSettings();changed();});
   }
  }
  targets();
 }
 function customized(d){if(!d.puppetArms)return false;return d.puppetArms.some((_,i)=>{const a=resolved(d,i);if(i>=2)return a.enabled;return !a.enabled||!a.sleeveEnabled||a.handOwnColor||a.handTextureEnabled||a.sleeveOwnColor||!a.sleeveTextureEnabled||['lengthScale','widthScale','handSize'].some(k=>a[k]!==1)||['shoulderX','shoulderY','sleeveRootX','sleeveRootY'].some(k=>a[k]!==0);});}
 function move(point,root,a,scale,t=null){return [root[0]+(point[0]-root[0])*a.lengthScale+a.shoulderX*scale+(t===null?0:a.sleeveRootX*scale*(1-t)),root[1]+(point[1]-root[1])*a.lengthScale-a.shoulderY*scale-(t===null?0:a.sleeveRootY*scale*(1-t))];}
 function tint(src,color){if(!color)return src;const c=canvas(src.width,src.height),ctx=c.getContext('2d');ctx.drawImage(src,0,0);ctx.globalCompositeOperation='multiply';ctx.fillStyle=color;ctx.fillRect(0,0,c.width,c.height);ctx.globalCompositeOperation='destination-in';ctx.drawImage(src,0,0);return c;}
 function flip(src){const c=canvas(src.width,src.height),ctx=c.getContext('2d');ctx.save();ctx.translate(src.width,0);ctx.scale(-1,1);ctx.drawImage(src,0,0);ctx.restore();return c;}
 // This is the same composed artwork and multiplicative color used in game.
 // It is shared by the paint canvas, small thumbnail, and puppet preview.
 function handMaterial(key){const index=+key.slice(-1),d=project.design,a=resolved(d,index),mirror=mirrored(d,index),canonical='puppetHand'+(mirror?index-1:index);let source=typeof HandTextureBase!=='undefined'?HandTextureBase.source(canonical):composite(canonical);if(a.handTextureTint)source=tint(source,a.handOwnColor?a.handColor:d.headColor);return mirror?flip(source):source;}
 function sleeveAppearance(d,index){
  const a=resolved(d,index);let material;
  if(a.sleeveTextureEnabled){const layers=sleeveLayers(d,index);material=layers.base;material.getContext('2d').drawImage(layers.ink,0,0);if(a.sleeveOwnColor)material=tint(material,a.sleeveColor);}
  else{material=canvas(32,64);const ctx=material.getContext('2d'),gradient=ctx.createLinearGradient(0,0,0,64);gradient.addColorStop(0,a.sleeveOwnColor?a.sleeveColor:d.clothTopColor);gradient.addColorStop(1,a.sleeveOwnColor?a.sleeveColor:d.clothBottomColor);ctx.fillStyle=gradient;ctx.fillRect(0,0,32,64);}
  return material;
 }
 function shape(part,d,index,map,legacy=false){
  const a=resolved(d,index),side=index%2?1:-1,kind=part.kind,xy=part.xy.slice();
  if(!legacy){if(kind==='sleeve')for(let i=0;i<xy.length;i+=4){let cx=(xy[i]+xy[i+2])*.5,cy=(xy[i+1]+xy[i+3])*.5;for(let k=0;k<4;k+=2){xy[i+k]=cx+(xy[i+k]-cx)*d.sleeveWidth/4;xy[i+k+1]=cy+(xy[i+k+1]-cy)*d.sleeveWidth/4;}}for(let i=0;i<xy.length;i+=2){xy[i]=side*4+(xy[i]-side*4)*d.armLength;xy[i+1]=12+(xy[i+1]-12)*d.armLength;}}
  for(let i=0;i<xy.length;i+=2)[xy[i],xy[i+1]]=map(xy[i],xy[i+1],true);
  return {xy,a};
 }
 function preview(parts,d,map,queue,anchors,legacy=false){
  const sides=[0,1].map(side=>Object.fromEntries(['hand','sleeve'].map(kind=>[kind,parts.find(p=>p.kind===kind&&(p.xy.filter((_,i)=>i%2===0).reduce((a,b)=>a+b,0)>0)===(side===1))])));
  for(const index of [2,3,0,1]){
   const side=index%2,source=sides[side],a=resolved(d,index);if(!a.enabled||!source.sleeve||!source.hand)continue;
   const raw=shape(source.sleeve,d,index,map,legacy).xy,root=[(raw[4]+raw[6])*.5,(raw[5]+raw[7])*.5],xy=raw.slice();
   for(let v=0;v<xy.length;v+=4){const center=[(raw[v]+raw[v+2])*.5,(raw[v+1]+raw[v+3])*.5],t=Math.floor(v/8)/(raw.length/8-1);for(let k=0;k<4;k+=2){const pt=[center[0]+(raw[v+k]-center[0])*a.widthScale,center[1]+(raw[v+k+1]-center[1])*a.widthScale];[xy[v+k],xy[v+k+1]]=move(pt,root,a,d.puppetScale,t);}}
   const material=sleeveAppearance(d,index),uv=d.sleeveMapping==='front'?sleeveFrontUV(side===1):Array.from({length:xy.length},(_,i)=>i%2?Math.floor(i/4)/(xy.length/4-1):side?1-Math.floor(i/2)%2:Math.floor(i/2)%2);
   if(d.layers.sleeves&&a.sleeveEnabled&&(index>=2||(side?d.sleeveRightEnabled:d.sleeveLeftEnabled)))queue.add('sleeves',()=>meshDraw(source.sleeve,xy,material,d.clothTopColor,uv));
   if(index<2)anchors['sleeve'+(side?'R':'L')]=wardrobeNativeAnchor(xy,'strip');
   const hand=shape(source.hand,d,index,map,legacy).xy,center=[hand.filter((_,i)=>i%2===0).reduce((a,b)=>a+b,0)/(hand.length/2),hand.filter((_,i)=>i%2).reduce((a,b)=>a+b,0)/(hand.length/2)],hp=move(center,root,a,d.puppetScale),hxy=[];
   for(let i=0;i<hand.length;i+=2)hxy.push(hp[0]+(hand[i]-center[0])*a.handSize,hp[1]+(hand[i+1]-center[1])*a.handSize);
   let im=a.handTextureEnabled?handMaterial('puppetHand'+index):source.hand.png?tintImage(source.hand.png,a.handOwnColor?a.handColor:d.headColor):null;
   if(d.layers.hands)queue.add('sleeves',()=>meshDraw(source.hand,hxy,im,a.handOwnColor?a.handColor:d.headColor,[0,0,1,0,1,1,0,1]));
   if(index<2)anchors['hand'+(side?'R':'L')]=wardrobeNativeAnchor(hxy,'bounds');
  }
 }
 return {defaults,init,finishLoad,settings,targets,canonical,select,selectedTarget,paintMirrored,paintX,drawImported,textureChanged,refreshFields,handMaterial,sleeveAppearance,importTexture,resolved,editModel,setSync,setSleeveSync,sleeveMirrored,sleeveLayers,copySide,copySleeve,customized,shape,move,preview};
})();




