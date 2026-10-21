'use strict';
const $=id=>document.getElementById(id),api=async(path,data)=>{await MI18n.ready;let r=await fetch('/api/'+path,data===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});let j=await r.json();if(!r.ok)throw Error(MI18n.error(j,r.statusText));return j;};
const headTexture=key=>key.startsWith('antenna')||key.startsWith('ear');
const dimensions={earL:[24,32],earR:[24,32],forehead:[32,32],face:[32,32],antennaL:[24,48],antennaR:[24,48],gown:[64,96],sleeve:[32,64],collar:[32,16],scarf:[64,96]};
let loading=false,creatingProject=false,savingProject=false,project,projectAssociation,projects=[],preset,canvases={},target='forehead',activeLayer=1,undo=[],redo=[],dirty=false,guide=true,control={mode:'silent',behavior:'work',paused:false,hasMark:true,rearGlow:true,lightning:true,pearls:true,glyphs:true,palettePreview:-1},images=new Map();
let loadVersion=0,listVersion=0,editVersion=0,savePending=0,applyingProject=false,restoringHistory=false,changingProject=false,saveQueue=Promise.resolve(),committedDimensions=structuredClone(dimensions);
const pc=$('paint').getContext('2d');let vc=$('puppet').getContext('2d');
const workspace=IteratorWorkspace.mount({render:()=>render(),fitPreview:()=>fitPreviewToModel()});
function notice(s,bad=false){$('notice').textContent=s;$('notice').dataset.kind=bad?'error':'success';$('notice').hidden=!s;$('notice').style.color=bad?'#ffb4a7':'#c8d9cf';}
function refreshProjectIdentity(){if(!project||!projectAssociation)return;const a=projectAssociation;MI18n.content($('identity'));$('identity').textContent=MI18n.t('project.identity.rooms',{id:project.projectId,ai:a.ai,entry:a.entry})+(a.linked?' · '+a.owner:'');}
function run(fn){return async(...args)=>{try{return await fn(...args);}catch(e){notice(e.message,true);console.error(e);}};}
function canvas(w,h){let c=document.createElement('canvas');c.width=w;c.height=h;return c;}
function imageOf(src){if(!src)return null;if(!images.has(src)){let im=new Image();im.onload=render;im.src=src;images.set(src,im);}let im=images.get(src);return im.complete&&im.naturalWidth?im:null;}
function markDirty(){dirty=true;editVersion++;notice('');syncProjectSelection();window.MIUndo?.changed();}
function changed(){markDirty();HeadSegments.syncTexture(target);render();}
function acceptSavedFields(saved){
 // These fields are owned by independent studios and protected by server._save.
 // Keep appearance edits made while the request was pending in this page.
 for(const key of ['dialogue','dialogueRevision','overseer','overseerRevision','roomBinding']){if(Object.hasOwn(saved,key))project[key]=structuredClone(saved[key]);else delete project[key];}
 project.updatedAt=saved.updatedAt;
}
function syncProjectSelection(){if(!project)return;const select=$('projects');let option=[...select.options].find(item=>item.value===project.projectId);if(!option){option=document.createElement('option');option.value=project.projectId;select.append(option);}MI18n.content(option);option.textContent=project.name;select.value=project.projectId;}
function syncProjectControls(){const busy=loading||creatingProject||savingProject||applyingProject||restoringHistory||changingProject||historyBusy||!!window.MIUndo?.busy||!!window.MIProjectActions?.busy;for(const id of ['projects','new','import','save','apply','history','export','editEntry','editAI','syncEntry','syncAI'])$(id).disabled=busy;window.MIProjectActions?.refresh();}
function snapshot(){return canvases[target][activeLayer].toDataURL();}
function paintHistorySnapshot(key=target,layer=activeLayer){
 return PaintLayers.snapshot(key,layer);
}
function checkpoint(){undo.push(paintHistorySnapshot());if(undo.length>60)undo.shift();redo=[];}
async function restore(entry){PaintLayers.requireHistory(entry);if(entry.sleeves){restoreSleeveMapping(entry);return;}if(entry.stack){await PaintLayers.restore(entry);target=entry.target;activeLayer=Math.min(entry.layer,canvases[target].length-1);if(entry.selectedTarget)target=PuppetArms.select(entry.selectedTarget);buildSettings();updateTarget();changed();return;}target=entry.target;activeLayer=entry.layer;$('target').value=target;
 const layers=entry.handTexture?entry.layers.map((l,i)=>[i,l.png]):[[activeLayer,entry.png]];
 for(const [i,png] of layers){let im=new Image();im.src=png;await im.decode();let c=canvases[target][i],ctx=c.getContext('2d');ctx.clearRect(0,0,c.width,c.height);ctx.drawImage(im,0,0);}
 if(entry.handTexture){project.textures[target].layers=structuredClone(entry.layers);project.textures[target].editableBase=entry.editableBase;const a=project.design.puppetArms[+target.slice(-1)];a.handTextureEnabled=entry.handTextureEnabled;a.handTextureTint=entry.handTextureTint;buildSettings();}
 if(entry.selectedTarget)target=PuppetArms.select(entry.selectedTarget);updateTarget();changed();}
function serialize(){for(let [key,arr] of Object.entries(canvases)){let t=project.textures[key];arr.forEach((c,i)=>t.layers[i].png=c.toDataURL());}project.editor.target=PuppetArms.selectedTarget(target);project.editor.layer=activeLayer;return project;}
async function load(p,view=null){
 if(!p||typeof p!=='object'||!p.projectId)throw Error(MI18n.t('project.lifecycle.unavailable'));
 if(typeof VoiceSettings!=='undefined')VoiceSettings.stopPreview?.();
 if(typeof VoiceSettings==='undefined'||typeof PaintLayers==='undefined')throw Error(MI18n.text('编辑器组件未加载，请按 Ctrl+F5 刷新页面后重试。'));
 const version=++loadVersion;loading=true;document.querySelector('main').inert=true;syncProjectControls();
 try{
  let next=structuredClone(p),nextCanvases={};next.design={rearGlowColor:'#98b4a5',rearGlowOpacity:.12,rearGlowRadius:250,rearGlowEnabled:true,earTint:false,earCustom:false,earInnerColor:'#9cafaa',earOuterColor:'#323e3d',roomBrightness:1,roomContrast:1,roomSaturation:1,capeLength:31,necklaceCount:0,necklaces:[],scarfShape:0,scarfTopWidth:10,scarfPanels:0,scarfLength:36,scarfWidth:36,scarfGap:.18,scarfLightness:.7,scarfFringe:false,scarfFringeLength:5,scarfTopColor:'#384845',scarfMiddleColor:'#688479',scarfBottomColor:'#b5c7bd',scarfGrain:.12,antennaTint:false,antennaInnerColor:'#9cafaa',antennaOuterColor:'#323e3d',neckLength:1,collarOffsetY:0,collarTopNotch:0,collarRoundness:.5,collarTaper:1,sleeveTopColor:'#813c46',sleeveMiddleColor:'#b68b8e',sleeveBottomColor:'#e0dfd8',sleeveGrain:.12,...next.design};next.textures??={};next.editor??={};
  HeadSegments.init(next);
  AudioSettings.init(next);
  VoiceSettings.init(next);
  wardrobeInit(next);
  PuppetArms.init(next);
  pearlAccessoriesInit(next);
  for(let [key,[w,h]] of Object.entries(dimensions)){
   let antenna=headTexture(key),tex=PaintLayers.normalize(next.textures[key]??=PaintLayers.blank(key),key);nextCanvases[key]=[];
   for(let layer of tex.layers){let c=canvas(w,h);if(layer.png){let im=new Image();im.src=layer.png;await im.decode();c.getContext('2d').drawImage(im,0,0,w,h);}nextCanvases[key].push(c);}
  }
  const association=await api('association?id='+encodeURIComponent(next.projectId)),nextLegacy=next.legacyOracle?await api('legacy-'+next.legacyOracle+'.json'):null;
  if(version!==loadVersion)return false;
  $('projectionStudio').href='/projections?project='+encodeURIComponent(next.projectId)+'&lang='+MI18n.locale;
  project=next;projectAssociation=association;legacyModel=nextLegacy;canvases=nextCanvases;committedDimensions=structuredClone(dimensions);PuppetArms.finishLoad();images.clear();$('projectName').value=project.name;refreshProjectIdentity();syncProjectSelection();target=PuppetArms.select(view?.target||project.editor.target||'forehead');activeLayer=view?.layer??project.editor.layer??1;if(view){const index=project.textures[target]?.layers.findIndex(layer=>layer.id===view.layerId);if(index>=0)activeLayer=index;}$('target').value=target;undo=[];redo=[];dirty=false;editVersion++;buildSettings();updateTarget();loadPreviewBackground();loadPreviewGuides();render();notice('');if(!view)focusVoiceSettings();window.MIUndo?.reset();return true;
 }catch(error){if(version!==loadVersion)return false;for(const key of Object.keys(dimensions))delete dimensions[key];Object.assign(dimensions,committedDimensions);syncProjectSelection();throw error;
 }finally{if(version===loadVersion){loading=false;document.querySelector('main').inert=changingProject||restoringHistory||historyBusy||!!window.MIProjectActions?.busy;syncProjectControls();render();}}
}
const sections=[
 ['head',[['headColor','肤色','color'],['eyeColor','眼睛','color'],['eyeSpacing','眼距',1,6,.1],['eyeSize','眼睛大小',.5,3,.05],['earBodyEnabled','启用耳机主体','bool'],['earWidth','耳机宽度',1,24,.1],['earHeight','耳机长度',2,40,.1],['earOffsetX','耳机左右位置',-8,40,.1],['earOffsetY','耳机上下位置',-80,80,.1],['metalColor','耳机底座','color'],['earCustom','使用自定义耳机形状','bool'],['antennaUpperEnabled','启用天线上段','bool'],['antennaHeight','天线上段长度',3,80,.1],['antennaWidth','天线上段宽度',.3,8,.1],['antennaSpread','天线上段间距',0,40,.1],['antennaOffsetY','天线上段上下位置',-40,80,.1],['antennaColor','默认天线渐变终点','color'],]],
 ['body',[['puppetScale','整体大小',.65,1.6,.01],['torsoLength','躯干比例',.7,1.4,.01],['neckLength','脖子长度',0,8,.1],['armLength','手臂长度',.7,1.4,.01]]],
 ['gown',[['robeLength','长袍长度',18,45,.1],['robeHemWidth','下摆宽度',.45,2.2,.01],['clothTopColor','上部配色','color'],['clothMiddleColor','中部配色','color'],['clothBottomColor','底部配色','color'],['clothGrain','底图颗粒',0,.4,.01],['hemProfile','下摆轮廓（11 个比例）','text']]],
 ['sleeveCollar',[['sleeveWidth','袖子宽度',2,8,.1],['sleeveOwn','袖子使用独立配色','bool'],['sleeveTopColor','袖子上部配色','color'],['sleeveMiddleColor','袖子中部配色','color'],['sleeveBottomColor','袖子底部配色','color'],['sleeveGrain','袖子底图颗粒',0,.4,.01],['collarColor','领子颜色','color'],['collarWidth','领子宽度',.5,1.8,.01],['collarOffsetY','领子上下位置',-8,8,.1],['collarHeight','领子上下长度',0,8,.1],['collarTopNotch','上沿向下凹',0,8,.1],['collarNotch','下沿向上凹',-4,4,.1],['collarRoundness','领口圆润度',0,1,.01],['collarTaper','上口收放',.5,1.5,.01]]],
 ['scarf',[['scarfPanels','围巾样式','select',{'0':'关闭','1':'单片','2':'双片'}],['scarfShape','下摆形状','select',{'0':'末端展开','1':'等宽长片'}],['scarfTopWidth','上端宽度',2,32,.1],['scarfLength','围巾长度',8,55,.1],['scarfWidth','末端宽度（展开时）',8,48,.1],['scarfGap','双片间隔',0,.7,.01],['scarfLightness','轻盈程度',0,1,.01],['scarfTopColor','围巾上部配色','color'],['scarfMiddleColor','围巾中部配色','color'],['scarfBottomColor','围巾底部配色','color'],['scarfGrain','围巾底图颗粒',0,.4,.01],['scarfFringe','末端流苏','bool'],['scarfFringeLength','流苏长度',0,12,.1]]],
 ['face',[['faceScale','额头素材缩放',.2,2,.05],['faceOffsetX','额头左右位置',-8,8,.1],['faceOffsetY','额头上下位置',-8,8,.1],['cheekScale','脸部素材缩放',.2,2,.05],['cheekOffsetX','脸部左右位置',-8,8,.1],['cheekOffsetY','脸部上下位置',-8,8,.1]]],
 ['hardware',[['armColor','支架主体','color'],['armShadowStrength','支架阴影强度',0,1,.01],['armJointColor','关节球','color'],['cableColorA','细连接节','color'],['cableColorB','粗连接节','color'],['headCableRed','头后线 A','color'],['headCableBlue','头后线 B','color']]],
 ['rearGlow',[['rearGlowEnabled','显示背后柔光','bool'],['rearGlowColor','柔光颜色','color'],['rearGlowOpacity','柔光强度',0,1,.01],['rearGlowRadius','柔光范围',20,600,1]]],
 ['room',[['roomBrightness','房间亮度',.25,2,.01],['roomContrast','房间对比度',.25,2,.01],['roomSaturation','房间饱和度',0,2,.01],['roomWorkColor','工作主题色','color'],['roomReceptionColor','接待主题色','color'],['roomTransition','过渡秒数',.2,15,.1],['haloColor','演算环颜色','color'],['haloOpacity','演算环透明度',0,1,.01],['haloScale','演算环大小',.3,2,.01]]],
 ['workPearls',[['pearlCount','数量',0,80,1],['pearlColor1','配色 1','color'],['pearlColor2','配色 2','color'],['pearlColor3','配色 3','color'],['pearlColor4','配色 4','color'],['pearlGlyphColor','统一文字颜色','color'],['pearlGlyphOpacity','文字透明度',0,1,.01],['pearlGlyph1','符号 1',0,13,1],['pearlGlyph2','符号 2',0,13,1],['pearlGlyph3','符号 3',0,13,1],['pearlGlyph4','符号 4',0,13,1],['pearlClusterX','堆积点 1 室内左右',0,1,.01],['pearlClusterY','堆积点 1 室内高度',0,1,.01],['pearlCluster2X','堆积点 2 室内左右',0,1,.01],['pearlCluster2Y','堆积点 2 室内高度',0,1,.01],['pearlScatter','离散程度',0,3,.05],['pearlFixedCount','工作时固定数量',0,40,1]]],
 ['dialogue',[['firstDialogue','有印记 · 初次进入','text'],['repeatDialogue','有印记 · 再次进入','text'],['unmarkedDialogue','无印记 · 符号占位','text']]]
];
function buildSettings(){
 const host=$('groups'),opened=captureSettingsOpen(host),d=project.design;host.replaceChildren();settingsConditions=[];
 const buckets={};for(const [id,name] of [['head','头部'],['body','身体'],['clothes','服装'],['extras','配饰与自定义'],['room','演算室'],['layers','图层与显示']]){
  buckets[id]=garmentSection(host,name);buckets[id].classList.add('settings-category');buckets[id].open=id==='clothes';
 }
 const fields=name=>sections.find(s=>s[0]===name)[1];
 function group(parent,title,defs,layer){
  const section=garmentSection(parent,title);let content=section;
  if(layer){settingsLayerSwitch(section,d,layer,'启用'+title);content=settingDependency(section,()=>d.layers[layer]!==false);}
  for(const [key,label,min,max,step] of defs){
   const type=min==='bool'?'checkbox':min==='color'?'color':min==='text'?'text':min==='select'?'select':'range';
   const el=garmentField(content,d,key,label,type,min==='select'?max:min,max,step);el.dataset.key=key;
  }
  return section;
 }
 const head=fields('head');
 group(buckets.head,'肤色',head.filter(f=>f[0]==='headColor'));
 Eyes.settings(buckets.head,d);
 const ear=group(buckets.head,'耳机',[],'ears');
 const antenna=group(buckets.head,'天线',[],'antenna');
 HeadSegments.settings({antenna,ear},d);
 group(buckets.head,'面部纹案',fields('face'),'face');
 if(!project.legacyOracle)group(buckets.body,'比例与连接',fields('body').filter(f=>f[0]!=='armLength'));
 group(buckets.clothes,'长袍',fields('gown').filter(f=>!project.legacyOracle||f[0]!=='hemProfile'),'robe');
 const collar=group(buckets.clothes,'领子',fields('sleeveCollar').filter(f=>f[0].startsWith('collar')),'collar');
 if(!project.legacyOracle){
  const scarf=garmentSection(buckets.clothes,'后围巾');
  const defs=fields('scarf');garmentField(scarf,d,'scarfPanels','围巾样式','select',defs[0][3]);
  const body=settingDependency(scarf,()=>d.scarfPanels>0);
  for(const [key,label,min,max,step] of defs.slice(1))garmentField(body,d,key,label,min==='bool'?'checkbox':min==='color'?'color':min==='select'?'select':'range',min==='select'?max:min,max,step);
  settingsFieldDependencies(body,['scarfGap'],()=>d.scarfPanels===2);
  settingsFieldDependencies(body,['scarfWidth'],()=>d.scarfShape===0);
  settingsFieldDependencies(body,['scarfFringeLength'],()=>d.scarfFringe);
 }
 wardrobeSettings(buckets,d);PuppetArms.settings(buckets,d);HeadSegments.targets();
 const order=['长袍','袖子','领子','前围巾下摆','披肩','后围巾'];
 for(const title of order){const el=[...buckets.clothes.children].find(e=>e.dataset.sectionId===settingSectionId(title));if(el)buckets.clothes.append(el);}
 buildNecklaceSettings(buckets.extras,d,changed);
 buildPearlAccessorySettings(buckets.extras,d,changed);
 const necklace=$('necklaceSettings');if(necklace){necklace.querySelector('summary').textContent='珍珠项链';necklace.dataset.sectionId='necklaces';buckets.extras.prepend(necklace);buckets.extras.prepend(buckets.extras.querySelector(':scope > summary'));}
 if(project.legacyOracle==='ir'){const ir=garmentSection(buckets.extras,'IR cloak');garmentField(ir,d,'capeLength','cloak 长度','range',20,55,.1);}
 AudioSettings.settings(buckets.room,d);
 VoiceSettings.settings(buckets.room,d,{getProject:()=>project,changed:changed,rebuild:buildSettings});
 const room=group(buckets.room,'房间配色',fields('room').filter(f=>!f[0].startsWith('halo')));
 group(buckets.room,'演算环',fields('room').filter(f=>f[0].startsWith('halo')),'halo');
 const glow=garmentSection(buckets.room,'背后柔光');garmentField(glow,d,'rearGlowEnabled','启用背后柔光','checkbox');
 const glowBody=settingDependency(glow,()=>d.rearGlowEnabled);for(const [key,label,min,max,step] of fields('rearGlow').slice(1))garmentField(glowBody,d,key,label,min==='color'?'color':'range',min,max,step);
 const hardware=fields('hardware');group(buckets.extras,'机械支架',hardware.filter(f=>f[0].startsWith('arm')),'mechanicalArm');group(buckets.extras,'脐带线',hardware.filter(f=>!f[0].startsWith('arm')),'cables');
 for(const title of ['机械支架','脐带线','珍珠项链','IR cloak','自定义插件']){const el=[...buckets.extras.children].find(e=>e.dataset.sectionId===settingSectionId(title));if(el)buckets.extras.append(el);}
 const pearls=group(buckets.room,'工作珍珠',fields('workPearls'));
 settingsFieldDependencies(pearls,fields('workPearls').slice(1).map(f=>f[0]),()=>d.pearlCount>0);
 settingsNote(settingDependency(pearls,()=>d.pearlCount>0),'位置以演算室内部可活动区域为范围，0 和 1 分别对应两侧边缘。');
 const display=garmentSection(buckets.layers,'身体显隐');for(const [key,label] of [['head','圆形头部'],['body','躯干'],['neck','脖子'],['feet','腿与脚']])settingsLayerSwitch(display,d,key,label);
 buildGradientSettings(buckets,d);
 restoreSettingsOpen(host,opened);syncSettingDependencies();
 host.oninput=host.onchange=syncSettingDependencies;
}
function composite(key,baseOnly=false){let [w,h]=dimensions[key],c=canvas(w,h),ctx=c.getContext('2d');project.textures[key].layers.forEach((l,i)=>{if(l.visible&&(!baseOnly||i===0)){ctx.globalAlpha=l.opacity;ctx.drawImage(canvases[key][i],0,0);}});return c;}
function updateTarget(){if(typeof PaintTargets!=='undefined'&&!PaintTargets.sync(false)){render();return;}$('target').value=PuppetArms.selectedTarget(target);activeLayer=Math.min(activeLayer,canvases[target].length-1);$('antennaShape').hidden=!headTexture(target);$('mirrorAntenna').hidden=!headTexture(target)&&!['sleeve','sleeveR'].includes(target);$('mirrorAntenna').textContent=MI18n.t(['sleeve','sleeveR'].includes(target)?'head28.copySleeve':'head28.mirrorOther');$('baseGradient').hidden=headTexture(target);let [w,h]=dimensions[target];workspace.setPaintTarget(PuppetArms.selectedTarget(target),w,h);$('symmetry').checked=project.textures[target].symmetry;PaintLayers.render($('layerList'));render();}
function drawPaint(){if(typeof PaintTargets!=='undefined'&&!PaintTargets.hasActive()){pc.clearRect(0,0,$('paint').width,$('paint').height);return;}const viewTarget=PuppetArms.selectedTarget(target);let [w,h]=dimensions[target],sx=$('paint').width/w,sy=$('paint').height/h;pc.imageSmoothingEnabled=false;pc.clearRect(0,0,$('paint').width,$('paint').height);for(let y=0;y<h;y+=4)for(let x=0;x<w;x+=4){pc.fillStyle=(x/4+y/4)%2?'#3c3f43':'#484b4f';pc.fillRect(x*sx,y*sy,4*sx,4*sy);}if($('meshGuide').checked&&(target==='face'||target==='forehead')){pc.save();pc.scale(sx,sy);pc.fillStyle=project.design.headColor;pc.globalAlpha=.65;pc.beginPath();pc.ellipse(16,16,8,8,0,0,7);pc.fill();pc.fillStyle=project.design.eyeColor;pc.fillRect(11,16,2,2);pc.fillRect(19,16,2,2);let other=composite(target==='face'?'forehead':'face');pc.drawImage(other,0,0);pc.restore();}pc.drawImage(materialPreview(viewTarget),0,0,$('paint').width,$('paint').height);
 if($('meshGuide').checked){pc.strokeStyle=referenceColor('55');pc.lineWidth=1;let div=['gown','scarf'].includes(target)?10:target==='collar'?12:8;pc.beginPath();for(let i=1;i<div;i++){pc.moveTo(i/div*$('paint').width,0);pc.lineTo(i/div*$('paint').width,$('paint').height);pc.moveTo(0,i/div*$('paint').height);pc.lineTo($('paint').width,i/div*$('paint').height);}pc.stroke();pc.strokeStyle=referenceColor('cc');pc.beginPath();pc.moveTo($('paint').width/2,0);pc.lineTo($('paint').width/2,$('paint').height);pc.stroke();if(['sleeve','sleeveR','puppetSleeve2','puppetSleeve3'].includes(viewTarget)&&project.design.sleeveMapping==='front')drawSleeveGuide(pc,$('paint').width,$('paint').height,viewTarget==='sleeveR'||viewTarget==='puppetSleeve3');}}
function triangle(ctx,im,xy,uv){let [x0,y0,x1,y1,x2,y2]=xy,[u0,v0,u1,v1,u2,v2]=uv;u0*=im.width;u1*=im.width;u2*=im.width;v0*=im.height;v1*=im.height;v2*=im.height;let den=u0*(v1-v2)+u1*(v2-v0)+u2*(v0-v1);if(Math.abs(den)<1e-8)return;let a=(x0*(v1-v2)+x1*(v2-v0)+x2*(v0-v1))/den,b=(y0*(v1-v2)+y1*(v2-v0)+y2*(v0-v1))/den,c=(x0*(u2-u1)+x1*(u0-u2)+x2*(u1-u0))/den,d=(y0*(u2-u1)+y1*(u0-u2)+y2*(u1-u0))/den,e=(x0*(u1*v2-u2*v1)+x1*(u2*v0-u0*v2)+x2*(u0*v1-u1*v0))/den,f=(y0*(u1*v2-u2*v1)+y1*(u2*v0-u0*v2)+y2*(u0*v1-u1*v0))/den;ctx.save();ctx.beginPath();let mx=(x0+x1+x2)/3,my=(y0+y1+y2)/3;let ext=(x,y)=>{let n=Math.hypot(x-mx,y-my)||1;return [x+(x-mx)/n*.16,y+(y-my)/n*.16];};ctx.moveTo(...ext(x0,y0));ctx.lineTo(...ext(x1,y1));ctx.lineTo(...ext(x2,y2));ctx.closePath();ctx.clip();ctx.transform(a,b,c,d,e,f);ctx.drawImage(im,0,0);ctx.restore();}
function tintImage(src,color){let im=imageOf(src);if(!im)return null;let c=canvas(im.width,im.height),ctx=c.getContext('2d');ctx.drawImage(im,0,0);ctx.globalCompositeOperation='source-in';ctx.fillStyle=color;ctx.fillRect(0,0,c.width,c.height);return c;}
function meshDraw(part,points,im,color,uv){let t=part.triangles;vc.fillStyle=color;vc.globalAlpha=part.alpha??1;for(let i=0;i<t.length;i+=3){let ids=t.slice(i,i+3),xy=ids.flatMap(k=>points.slice(k*2,k*2+2));if(im&&uv)triangle(vc,im,xy,ids.flatMap(k=>uv.slice(k*2,k*2+2)));else{vc.beginPath();vc.moveTo(xy[0],xy[1]);vc.lineTo(xy[2],xy[3]);vc.lineTo(xy[4],xy[5]);vc.fill();}}vc.globalAlpha=1;}
function proceduralCloth(key){
 let [w,h]=dimensions[key],c=canvas(w,h),ctx=c.getContext('2d'),d=project.design,own=key==='sleeve'&&d.sleeveOwn,prefix=key==='scarf'?'scarf':own?'sleeve':'cloth';
 let config=wardrobeColors(key);let colors=['TopColor','MiddleColor','BottomColor'].map(k=>(d[prefix+k]||d['cloth'+k]).match(/\w\w/g).map(x=>parseInt(x,16))),grain=d[prefix+'Grain']??d.clothGrain,im=ctx.createImageData(w,h);if(config){colors=config[0].map(c=>c.match(/\w\w/g).map(x=>parseInt(x,16)));grain=config[1];}
 for(let y=0;y<h;y++){let t=y/(h-1),a=t<.58?colors[0]:colors[1],b=t<.58?colors[1]:colors[2],f=t<.58?t/.58:(t-.58)/.42;
  if(project.legacyOracle&&!config){let tt=t;if(key==='sleeve')tt*=.65;if(project.legacyOracle==='cf'){a=colors[0];b=colors[2];f=tt*tt;}else{a=tt<.68?colors[0]:colors[1];b=tt<.68?colors[1]:colors[2];f=Math.max(0,Math.min(1,tt<.68?(tt-.42)/.26:(tt-.68)/.32));f=f*f*(3-2*f);}}
  for(let x=0;x<w;x++){let i=(y*w+x)*4,noise=((i*16807%127)/127-.5)*grain*130;for(let j=0;j<3;j++)im.data[i+j]=Math.max(0,Math.min(255,Math.floor(a[j]+(b[j]-a[j])*f+noise+.5)));im.data[i+3]=255;}}
 ctx.putImageData(im,0,0);return c;
}
const fabricKey=key=>['gown','sleeve','sleeveR','collar','scarf'].includes(key)||/^(front|shawl|custom|leg|puppetSleeve)/.test(key);
function clothBase(key){let tex=project.textures[key];if(tex.layers[0]?.visible===false)return canvas(...dimensions[key]);if(tex.editableBase||garmentFind(project.design,key)?.type==='rigid')return composite(key,true);let c;if(key==='collar'){c=canvas(...dimensions[key]);let ctx=c.getContext('2d');ctx.fillStyle=project.design.collarColor;ctx.fillRect(0,0,c.width,c.height);}else c=proceduralCloth(key);let ctx=c.getContext('2d');ctx.drawImage(canvases[key][0],0,0);const opacity=tex.layers[0]?.opacity??1;if(opacity<1){ctx.globalCompositeOperation='destination-in';ctx.fillStyle='rgba(0,0,0,'+opacity+')';ctx.fillRect(0,0,c.width,c.height);ctx.globalCompositeOperation='source-over';}return c;}
function patternComposite(key){let c=canvas(...dimensions[key]),ctx=c.getContext('2d');project.textures[key].layers.forEach((l,i)=>{if(i>0&&l.visible){ctx.globalAlpha=l.opacity;ctx.drawImage(canvases[key][i],0,0);}});return c;}
function clothPreview(key){let c=clothBase(key);c.getContext('2d').drawImage(patternComposite(key),0,0);return c;}
function editableBase(){if(activeLayer!==0||!fabricKey(target)||project.textures[target].editableBase)return;PaintLayers.requireEditable(target,0);let base=clothBase(target),c=canvases[target][0];c.getContext('2d').clearRect(0,0,c.width,c.height);c.getContext('2d').drawImage(base,0,0);project.textures[target].editableBase=true;project.textures[target].layers[0].opacity=1;}

function antennaComposite(key){let c=canvas(...dimensions[key]),ctx=c.getContext('2d'),tex=project.textures[key];for(const surface of ['inner','outer']){let part=canvas(...dimensions[key]),p=part.getContext('2d');tex.layers.forEach((l,i)=>{if(l.visible&&PaintLayers.surface(l,i,tex.layers)===surface){p.globalAlpha=l.opacity;p.drawImage(canvases[key][i],0,0);}});HeadSegments.recolor(p,part.width,part.height,project.design,key,surface==='outer'?1:0);ctx.drawImage(part,0,0);}return c;}
function materialPreview(key){if(/^puppetHand[0-3]$/.test(key))return PuppetArms.handMaterial(key);if(['sleeve','sleeveR','puppetSleeve2','puppetSleeve3'].includes(key))return PuppetArms.sleeveAppearance(project.design,key==='sleeve'?0:key==='sleeveR'?1:+key.slice(-1));if(headTexture(key))return antennaComposite(key);if(fabricKey(key))return clothPreview(key);return composite(key);}
function collarShape(left,right,d){let n=13,xy=[],uv=[],triangles=[],mid=left.map((v,i)=>(v+right[i])/2);
 for(let x=0;x<n;x++)for(let y=0;y<n;y++){let u=x/(n-1),v=y/(n-1),shape=(1-Math.abs(2*u-1))*(1-d.collarRoundness)+Math.sin(Math.PI*u)**2*d.collarRoundness;
 let lower=d.collarNotch*shape,upper=Math.max(lower+.1,d.collarHeight-d.collarTopNotch*shape),rounding=1-d.collarRoundness*.12*(1-Math.sqrt(Math.max(0,1-(2*v-1)**2))),width=d.collarWidth*(d.collarTaper+(1-d.collarTaper)*v)*rounding;
 xy.push(mid[0]+(left[0]+(right[0]-left[0])*u-mid[0])*width,mid[1]+(left[1]+(right[1]-left[1])*u-mid[1])*width-d.collarOffsetY-(upper+(lower-upper)*v));uv.push(u,v);
 if(x<n-1&&y<n-1){let i=x*n+y;triangles.push(i,i+n,i+1,i+1,i+n,i+n+1);}}
 return {xy,uv,triangles};
}
function drawScarf(map,parts,d){
 if(!d.scarfPanels)return;let robe=parts.find(p=>p.kind==='robe');if(!robe)return;
 let dim=Math.sqrt(robe.xy.length/2),ends=[[robe.xy[0],robe.xy[1]],[robe.xy[(dim-1)*dim*2],robe.xy[(dim-1)*dim*2+1]]].sort((a,b)=>a[0]-b[0]),[left,right]=ends,mid=left.map((v,i)=>(v+right[i])/2),im=clothPreview('scarf');
 for(let panel=0;panel<d.scarfPanels;panel++){
  let u0=d.scarfPanels===1?0:panel===0?0:.5+d.scarfGap*.5,u1=d.scarfPanels===1?1:panel===0?.5-d.scarfGap*.5:1,xy=[],uv=[],triangles=[];
  // Offline rest pose, same seam, physical dimensions and UV division as the game.
  let a=map(left[0]+(right[0]-left[0])*u0,left[1]+(right[1]-left[1])*u0,true),b=map(left[0]+(right[0]-left[0])*u1,left[1]+(right[1]-left[1])*u1,true),cx=(a[0]+b[0])/2,topWidth=d.scarfTopWidth*(u1-u0)*d.puppetScale;a[0]=cx-topWidth/2;b[0]=cx+topWidth/2;
  for(let x=0;x<11;x++)for(let y=0;y<11;y++){let u=x/10,v=y/10,topX=a[0]+(b[0]-a[0])*u,bottomX=d.scarfShape===1?topX:mid[0]*d.puppetScale+(u0+(u1-u0)*u-.5)*d.scarfWidth*d.puppetScale;xy.push(topX+(bottomX-topX)*v,a[1]+(b[1]-a[1])*u+d.scarfLength*d.puppetScale*v);uv.push(d.scarfPanels===1?u:(panel+u)*.5,v);if(x<10&&y<10){let i=x*11+y;triangles.push(i,i+11,i+1,i+1,i+11,i+12);}}
  meshDraw({triangles},xy,im,d.scarfTopColor,uv);
  if(d.scarfFringe){vc.strokeStyle=d.scarfBottomColor;vc.lineWidth=.64*d.puppetScale;for(let x=0;x<11;x++){let i=(x*11+10)*2,amount=.55+((x*37+panel*17)%13)/20;vc.beginPath();vc.moveTo(xy[i],xy[i+1]);vc.lineTo(xy[i],xy[i+1]+d.scarfFringeLength*amount*d.puppetScale);vc.stroke();}}
 }
}
function drawPuppet(view){if(project.legacyOracle&&legacyModel){drawLegacyPuppet(view);return;}let z=workspace.beginPreview(vc,view);if(!preset)return;let d=project.design;vc.imageSmoothingEnabled=false;if(guide){vc.strokeStyle=referenceColor('99');vc.lineWidth=1/z;vc.beginPath();vc.moveTo(-55,0);vc.lineTo(55,0);vc.moveTo(0,-30);vc.lineTo(0,75);vc.stroke();}
 let map=(x,y,body=false)=>[x*d.puppetScale,((y>7?7+(y-7)*d.torsoLength:y)+(body?d.neckLength-2:0))*d.puppetScale],parts=Eyes.parts(preset.parts,d),base=preset.design;let robe=clothPreview('gown'),sleeve=clothPreview('sleeve'),collarAnchors=(()=>{let r=parts.find(p=>p.kind==='robe'),n=Math.sqrt(r.xy.length/2);return [[r.xy[(n-1)*n*2],r.xy[(n-1)*n*2+1]],[r.xy[0],r.xy[1]]];})(),collarDrawn=false,queue=previewLayerQueue(d);
 function drawCollar(){if(collarDrawn||!d.layers.collar||d.collarHeight<=.01||!collarAnchors)return;collarDrawn=true;let shape=collarShape(...collarAnchors,d),xy=shape.xy.map((v,i)=>v);for(let i=0;i<xy.length;i+=2)[xy[i],xy[i+1]]=map(xy[i],xy[i+1],true);meshDraw(shape,xy,materialPreview('collar'),d.collarColor,shape.uv);}
 queue.add('back',()=>drawScarf(map,parts,d));let wardrobeAnchors={shoulders:collarAnchors.map(p=>map(...p,true)),head:[map(-5,0),map(5,0)],body:[map(-4,12,true),map(4,12,true)],gown:collarAnchors.map(p=>map(...p,true)),collar:collarAnchors.map(p=>map(...p,true)),sleeveL:[map(-6,12,true),map(-3,12,true)],sleeveR:[map(3,12,true),map(6,12,true)],handL:[map(-10,25,true),map(-8,25,true)],handR:[map(8,25,true),map(10,25,true)]};Object.assign(wardrobeAnchors,HeadSegments.anchors(d,map(0,0),antennaComposite));queue.add('legs',()=>wardrobeLegPreview(vc,d,map));
 parts=[...parts.filter(p=>p.kind==='body'||p.kind==='neck'),...parts.filter(p=>!['body','neck'].includes(p.kind))];
 for(let p of parts){if(PuppetArms.customized(d)&&['hand','sleeve'].includes(p.kind))continue;let kind=p.kind,show=kind==='neck'?d.layers.neck:kind==='body'?d.layers.body!==false:kind==='head'?d.layers.head:kind.startsWith('eye')?d.layers.eyes:kind==='robe'?d.layers.robe:kind==='sleeve'?d.layers.sleeves:kind==='hand'?d.layers.hands:kind==='foot'?d.layers.feet:false;let xy=p.xy.slice(),uv=p.uv,im=null,color=d.headColor;
  if(kind==='neck'){let body=parts.find(v=>v.kind==='body'),chestY=body.xy.filter((_,i)=>i%2).reduce((a,b)=>a+b,0)/(body.xy.length/2);xy=[-1.5,0,1.5,0,1.5,chestY,-1.5,chestY];}
  if(kind==='robe'){let n=Math.sqrt(xy.length/2);collarAnchors=[[xy[(n-1)*n*2],xy[(n-1)*n*2+1]],[xy[0],xy[1]]];uv=Array.from({length:xy.length},(_,i)=>i%2?Math.floor(i/2)%n/(n-1):1-Math.floor(i/2/n)/(n-1));let prof=d.hemProfile.split(',').map(Number);for(let row=0;row<n;row++){let mid=(xy[row*2]+xy[((n-1)*n+row)*2])/2;for(let col=0;col<n;col++){let i=(col*n+row)*2,t=row/(n-1),factor=1+(d.robeHemWidth-1)*(t*t*(3-2*t));xy[i]=mid+(xy[i]-mid)*factor;let top=xy[col*n*2+1];xy[i+1]=top+(xy[i+1]-top)*d.robeLength/29*(1+((prof[col]||1)-1)*t*t);}}im=robe;color=d.clothTopColor;}
  if(kind==='sleeve'){let screenLeft=xy.filter((_,i)=>i%2===0).reduce((a,b)=>a+b,0)<0;show=show&&(screenLeft?d.sleeveLeftEnabled:d.sleeveRightEnabled);for(let i=0;i<xy.length;i+=4){let mx=(xy[i]+xy[i+2])/2,my=(xy[i+1]+xy[i+3])/2;xy[i]=mx+(xy[i]-mx)*d.sleeveWidth/4;xy[i+1]=my+(xy[i+1]-my)*d.sleeveWidth/4;xy[i+2]=mx+(xy[i+2]-mx)*d.sleeveWidth/4;xy[i+3]=my+(xy[i+3]-my)*d.sleeveWidth/4;}let side=xy.reduce((a,v,i)=>a+(i%2?0:v),0)<0?-1:1;for(let i=0;i<xy.length;i+=2){xy[i]=side*4+(xy[i]-side*4)*d.armLength;xy[i+1]=12+(xy[i+1]-12)*d.armLength;}uv=Array.from({length:xy.length},(_,i)=>{let k=Math.floor(i/2);return i%2?Math.floor(k/2)/(xy.length/4-1):(side>0?1-k%2:k%2);});if(d.sleeveMapping==='front')uv=sleeveFrontUV(side>0);im=sleeveMaterial(side<0?'sleeve':'sleeveR');color=d.clothTopColor;}
  if(kind==='hand'){let side=xy[0]<0?-1:1;for(let i=0;i<xy.length;i+=2){xy[i]=side*4+(xy[i]-side*4)*d.armLength;xy[i+1]=12+(xy[i+1]-12)*d.armLength;}}
  if(kind==='foot'&&d.straightLegs)continue;if(kind==='foot'){let side=xy.filter((_,i)=>i%2===0).reduce((a,b)=>a+b,0)>0?1:0,len=legValue(d,side,'legLength');for(let i=0;i<xy.length;i+=2){xy[i]=xy[i]*len+legShift(d,side);xy[i+1]=12+(xy[i+1]-12)*len;}}
  if(kind.startsWith('eye')){const eye=Eyes.geometry(p,d,base.eyeSize);xy=eye.xy;color=eye.color;show=eye.visible;if(eye.png){im=Eyes.image(eye);uv=[0,0,1,0,1,1,0,1];}}
  if(!im&&p.png){im=tintImage(p.png,color);uv=[0,0,1,0,1,1,0,1];}for(let i=0;i<xy.length;i+=2)[xy[i],xy[i+1]]=map(xy[i],xy[i+1],kind==='neck'?xy[i+1]>0:['body','robe','sleeve','hand','foot'].includes(kind));if(kind==='robe'){wardrobeAnchors.gownMesh=xy.slice();wardrobeAnchors.gown=wardrobeNativeAnchor(xy);}
  else if(kind==='sleeve'||kind==='hand'||kind==='foot'){const side=xy.filter((_,i)=>i%2===0).reduce((a,b)=>a+b,0)<0?'L':'R',key=(kind==='foot'?'leg':kind)+side;if(kind==='hand'||xy.length>8||!wardrobeAnchors[key])wardrobeAnchors[key]=wardrobeNativeAnchor(xy,xy.length>8?'strip':'bounds');}
  else if((kind==='head'||kind==='body')&&!wardrobeAnchors[kind]?.sample)wardrobeAnchors[kind]=wardrobeNativeAnchor(xy,'bounds');else if(kind==='neck')wardrobeAnchors.neck=wardrobeNativeAnchor(xy,'bounds');
  if(show){let group=kind==='robe'?'gown':['sleeve','hand'].includes(kind)?'sleeves':kind==='foot'?'legs':kind.startsWith('eye')?'head':kind;queue.add(group,()=>meshDraw(p,xy,im,color,uv));}
 }

 if(PuppetArms.customized(d))PuppetArms.preview(parts,d,map,queue,wardrobeAnchors);
 const collarBinding=collarShape(...collarAnchors,d).xy;for(let i=0;i<collarBinding.length;i+=2)[collarBinding[i],collarBinding[i+1]]=map(collarBinding[i],collarBinding[i+1],true);wardrobeAnchors.collar=wardrobeNativeAnchor(collarBinding);
 if(d.straightLegs)Object.assign(wardrobeAnchors,wardrobeStraightLegAnchors(d,map));
 queue.add('collar',drawCollar);queue.add('necklaces',()=>drawNecklaces(vc,d,collarAnchors.map(p=>map(...p,true)),guide));wardrobePreview(vc,d,wardrobeAnchors,queue);
 queue.add('head',()=>{vc.save();vc.scale(d.puppetScale,d.puppetScale);for(let side of [-1,1]){if(d.layers.ears&&d.earBodyEnabled){if(d.earCustom)vc.drawImage(antennaComposite(side<0?'earL':'earR'),side*(8+d.earOffsetX)-d.earWidth/2,-.5-d.earOffsetY-d.earHeight/2,d.earWidth,d.earHeight);else{vc.fillStyle=d.metalColor;vc.fillRect(side*(8+d.earOffsetX)-d.earWidth/2,-.5-d.earOffsetY-d.earHeight/2,d.earWidth,d.earHeight);}}if(d.layers.antenna&&d.antennaUpperEnabled){let c=antennaComposite(side<0?'antennaL':'antennaR'),has=c.getContext('2d').getImageData(0,0,c.width,c.height).data.some((v,i)=>i%4===3&&v);if(has)vc.drawImage(c,side*d.antennaSpread-d.antennaWidth*2,-4-d.antennaOffsetY-d.antennaHeight,d.antennaWidth*4,d.antennaHeight+4);else{let grad=vc.createLinearGradient(0,0,0,-d.antennaHeight);grad.addColorStop(0,d.metalColor);grad.addColorStop(1,d.antennaColor);vc.strokeStyle=grad;vc.lineWidth=d.antennaWidth*2;vc.beginPath();vc.moveTo(side*d.antennaSpread,-2-d.antennaOffsetY);vc.lineTo(side*(d.antennaSpread+.8),-2-d.antennaHeight-d.antennaOffsetY);vc.stroke();}}}
 if(d.layers.face){vc.drawImage(composite('forehead'),-12*d.faceScale+d.faceOffsetX,-12*d.faceScale-d.faceOffsetY,24*d.faceScale,24*d.faceScale);vc.drawImage(composite('face'),-12*d.cheekScale+d.cheekOffsetX,-12*d.cheekScale-d.cheekOffsetY,24*d.cheekScale,24*d.cheekScale);}HeadSegments.draw(vc,d,antennaComposite);vc.restore();});queue.draw();vc.setTransform(1,0,0,1,0,0);}
function fitPreviewToModel(){
 if(!project||loading)return;
 // Measure the existing renderer at a fixed scale; fitting never edits the model.
 const measured=canvas(2048,2048),context=measured.getContext('2d'),original=vc,originalGuide=guide;
 try{
  vc=context;guide=false;drawPuppet({width:2048,height:2048,zoom:2,center:{x:0,y:0},dpr:1});
  const pixels=context.getImageData(0,0,2048,2048).data;let left=2048,top=2048,right=-1,bottom=-1;
  for(let y=0;y<2048;y++)for(let x=0;x<2048;x++)if(pixels[(y*2048+x)*4+3]){left=Math.min(left,x);right=Math.max(right,x);top=Math.min(top,y);bottom=Math.max(bottom,y);}
  const bounds=right>=left?{x:(left-1024)/2,y:(top-1024)/2,width:(right-left+1)/2,height:(bottom-top+1)/2}:{x:-55,y:-40,width:110,height:125};
  vc=original;guide=originalGuide;workspace.fitPreview(bounds);
 }catch(e){notice('无法适合当前人偶视图：'+e.message,true);}finally{vc=original;guide=originalGuide;render();}
}
function render(){if(!project||loading)return;let earToggle=document.querySelector('[data-key="earCustom"]');if(earToggle)earToggle.checked=!!project.design.earCustom;drawPaint();drawPuppet();}
$('size').addEventListener('input',()=>$('sizeValue').value=$('size').value);
$('strength').addEventListener('input',()=>$('strengthValue').value=Math.round(Number($('strength').value)*100)+'%');
let stroke=null;
function pos(e){let r=$('paint').getBoundingClientRect(),[w,h]=dimensions[target];return [PuppetArms.paintX(Math.floor((e.clientX-r.left)/r.width*w),w,target),Math.floor((e.clientY-r.top)/r.height*h)];}
// Clip the path, not the pointer: clamping an outside pointer to an edge leaves
// a stationary rounded mark and joins unrelated outside movements along it.
function clipPaintSegment(from,to,r=0){
 const [w,h]=dimensions[target],delta=[to[0]-from[0],to[1]-from[1]],lower=[-r,-r],upper=[w-1+r,h-1+r];let first=0,last=1;
 for(let axis=0;axis<2;axis++){
  if(!Number.isFinite(from[axis])||!Number.isFinite(to[axis]))return null;
  if(delta[axis]===0){if(from[axis]<lower[axis]||from[axis]>upper[axis])return null;continue;}
  let a=(lower[axis]-from[axis])/delta[axis],b=(upper[axis]-from[axis])/delta[axis];if(a>b)[a,b]=[b,a];first=Math.max(first,a);last=Math.min(last,b);if(first>last)return null;
 }
 return [from.map((v,i)=>v+delta[i]*first),from.map((v,i)=>v+delta[i]*last)];
}
function initializePaintStroke(){
 if(!stroke)return false;if(stroke.original)return true;
 PaintLayers.requireBaseInitialization(target);checkpoint();editableBase();
 if(!HandTextureBase.ensure(target)){undo.pop();stroke=null;notice(MI18n.t('hand.textureLoading'),true);return false;}
 if(headTexture(target))HeadSegments.markCustom(target);
 const c=canvases[target][activeLayer];stroke.original=c.getContext('2d').getImageData(0,0,c.width,c.height);return true;
}
function dab(x,y){PaintLayers.requireEditable();if(!stroke)return;let c=canvases[target][activeLayer],ctx=c.getContext('2d'),r=stroke.size/2,tool=stroke.tool,alpha=stroke.alpha,mask=new Map();
 for(let yy=Math.floor(y-r);yy<=y+r;yy++)for(let xx=Math.floor(x-r);xx<=x+r;xx++){let dist=Math.hypot(xx-x,yy-y);if(dist>r)continue;let a=alpha*(tool==='spray'?Math.max(0,1-dist/r):1);if(a<=0)continue;for(let px of stroke.symmetry?[xx,c.width-1-xx]:[xx]){if(px<0||px>=c.width||yy<0||yy>=c.height)continue;let k=yy*c.width+px;if(tool==='grain'){const seed=yy*c.width+(stroke.symmetry?Math.min(px,c.width-1-px):px);if(!stroke.grain.has(seed))stroke.grain.set(seed,Math.random()<=.3);if(!stroke.grain.get(seed))continue;}mask.set(k,Math.max(mask.get(k)||0,a));}}
 if(!mask.size||!initializePaintStroke())return;
 // Restore each touched pixel from the start of this gesture, then apply its
 // greatest coverage once. Lingering, overlaps and mirrored dabs cannot build opacity.
 ctx.globalCompositeOperation=tool==='erase'?'destination-out':'source-over';ctx.fillStyle=stroke.color;for(let [k,a] of mask){if(a<=(stroke.coverage.get(k)||0))continue;stroke.coverage.set(k,a);const px=k%c.width,py=Math.floor(k/c.width);ctx.putImageData(stroke.original,0,0,px,py,1,1);ctx.globalAlpha=a;ctx.fillRect(px,py,1,1);}ctx.globalAlpha=1;ctx.globalCompositeOperation='source-over';}
function paintStrokeGuard(event){if(!stroke||event?.pointerId!=null&&stroke.pointer!=null&&event.pointerId!==stroke.pointer)return false;if(stroke.owner!==project||stroke.key!==target||project.textures[target]?.layers[activeLayer]?.id!==stroke.layerId){stroke=null;return false;}try{PaintLayers.requireEditable();return true;}catch(error){stroke=null;throw error;}}
function drawPaintSegment(from,to){const segment=clipPaintSegment(from,to,stroke.size/2);if(!segment)return;const [a,b]=segment,dx=b[0]-a[0],dy=b[1]-a[1],n=Math.max(Math.ceil(Math.max(Math.abs(dx),Math.abs(dy))),1);for(let i=0;i<=n&&stroke;i++)dab(Math.round(a[0]+dx*i/n),Math.round(a[1]+dy*i/n));}
function previewLine(p){if(!paintStrokeGuard())return;if(stroke.original)canvases[target][activeLayer].getContext('2d').putImageData(stroke.original,0,0);stroke.coverage.clear();drawPaintSegment(stroke.start,p);}
function movePaintStroke(e){if(!paintStrokeGuard(e))return;const p=pos(e);if(stroke.tool==='gradient')stroke.touched||=!!clipPaintSegment(stroke.last,p);else if(stroke.tool==='line')previewLine(p);else drawPaintSegment(stroke.last,p);if(stroke)stroke.last=p;render();}
function finishPaintStroke(){if(!stroke)return;const edited=!!stroke.original;stroke=null;if(edited){PuppetArms.textureChanged(target);changed();}}
function paintSurfaceEvent(e){const area=$('paintViewport');if(!area||!e.target)return true;if(![area,$('paintSurface'),$('paint')].includes(e.target))return false;const r=area.getBoundingClientRect();return e.clientX>=r.left+area.clientLeft&&e.clientX<r.left+area.clientLeft+area.clientWidth&&e.clientY>=r.top+area.clientTop&&e.clientY<r.top+area.clientTop+area.clientHeight;}
$('paint').onpointerdown=run(e=>{if(e.button!==0||stroke||!paintSurfaceEvent(e)||typeof PaintTargets!=='undefined'&&!PaintTargets.hasActive())return;e.preventDefault();let layer=PaintLayers.requireEditable();if(!layer.visible||layer.opacity===0){notice('当前图层已隐藏或透明，请先打开图层显示和透明度。',true);return;}const start=pos(e);stroke={owner:project,key:target,layerId:layer.id,pointer:e.pointerId,start,last:start,tool:$('brush').value,size:+$('size').value,alpha:+$('strength').value,color:$('ink').value,secondary:$('ink2').value,symmetry:project.textures[target].symmetry,coverage:new Map(),grain:new Map(),original:null,touched:!!clipPaintSegment(start,start)};($('paintViewport')||$('paint')).setPointerCapture(e.pointerId);if(stroke.tool!=='gradient')dab(...start);render();});
$('paint').onpointermove=run(movePaintStroke);
$('paint').onpointerup=run(e=>{if(!paintStrokeGuard(e))return;movePaintStroke(e);if(!stroke)return;if(stroke.tool==='gradient'&&stroke.touched&&initializePaintStroke()){let c=canvases[target][activeLayer],ctx=c.getContext('2d'),p=pos(e),fill=canvas(c.width,c.height),fc=fill.getContext('2d');if(p[0]===stroke.start[0]&&p[1]===stroke.start[1])p[1]++;let g=fc.createLinearGradient(...stroke.start,...p);g.addColorStop(0,stroke.color);g.addColorStop(1,stroke.secondary);fc.fillStyle=g;fc.fillRect(0,0,c.width,c.height);if(stroke.symmetry){let original=canvas(c.width,c.height);original.getContext('2d').drawImage(fill,0,0);fc.save();fc.translate(c.width,0);fc.scale(-1,1);fc.drawImage(original,0,0,c.width/2,c.height,0,0,c.width/2,c.height);fc.restore();}ctx.globalAlpha=stroke.alpha;ctx.drawImage(fill,0,0);ctx.globalAlpha=1;}finishPaintStroke();});
$('paint').onpointercancel=run(e=>{if(paintStrokeGuard(e))finishPaintStroke();});
// Pointer capture belongs to the gray workspace, so an outside start and all
// later re-entries remain one clipped gesture. Canvas-origin events bubble once.
if($('paintViewport'))for(const kind of ['pointerdown','pointermove','pointerup','pointercancel'])$('paintViewport').addEventListener(kind,event=>{if(event.target!==$('paint'))$('paint')['on'+kind](event);});
$('target').onchange=()=>{stroke=null;target=PuppetArms.select($('target').value);if(target==='frontR'&&project.design.frontSymmetry)target='frontL';$('target').value=PuppetArms.selectedTarget(target);updateTarget();PaintTargets.locateSettings(PuppetArms.selectedTarget(target));};$('symmetry').onchange=()=>{project.textures[target].symmetry=$('symmetry').checked;changed();};$('meshGuide').onchange=render;
let historyBusy=false;
async function drawingHistory(back){if(window.MIUndo)return MIUndo.step(back?-1:1);if(historyBusy||loading||stroke)return;const source=back?undo:redo,dest=back?redo:undo;if(!source.length)return;historyBusy=true;try{const e=source[source.length-1];PaintLayers.requireHistory(e);const current=e.sleeves?sleeveMappingSnapshot():paintHistorySnapshot(e.target,e.layer);await restore(e);source.pop();dest.push(current);}finally{historyBusy=false;}}
$('undo').onclick=run(()=>drawingHistory(true));$('redo').onclick=run(()=>drawingHistory(false));
document.addEventListener('keydown',e=>{
 if(window.MIUndo)return;
 if(!(e.ctrlKey||e.metaKey)||e.altKey||e.repeat||document.querySelector('dialog[open]'))return;
 const el=e.target;if(el?.closest('textarea,[contenteditable="true"],input:not([type]),input[type="text"],input[type="number"],input[type="search"],input[type="url"],input[type="email"]'))return;
 const key=e.key.toLowerCase();if(key!=='z'&&key!=='y')return;e.preventDefault();run(()=>drawingHistory(key==='z'&&!e.shiftKey))();
});$('clear').onclick=run(()=>{PaintLayers.requireEditable();PaintLayers.requireBaseInitialization(target);checkpoint();editableBase();if(!HandTextureBase.ensure(target)){undo.pop();throw Error(MI18n.t('hand.textureLoading'));}let c=canvases[target][activeLayer];c.getContext('2d').clearRect(0,0,c.width,c.height);PuppetArms.textureChanged(target);changed();});
function gradientBase(key='gown'){PaintLayers.requireEditable(key,0);let c=canvases[key][0],ctx=c.getContext('2d');ctx.clearRect(0,0,c.width,c.height);ctx.drawImage(proceduralCloth(key),0,0);project.textures[key].editableBase=true;}
$('baseGradient').onclick=run(()=>{PaintLayers.requireEditable(target,0);activeLayer=0;checkpoint();if(fabricKey(target)&&target!=='collar')gradientBase(target);else{let c=canvases[target][0],ctx=c.getContext('2d');ctx.fillStyle=target==='collar'?project.design.collarColor:$('ink').value;ctx.fillRect(0,0,c.width,c.height);if(fabricKey(target)||/^puppetHand[0-3]$/.test(target))project.textures[target].editableBase=true;}PuppetArms.textureChanged(target);updateTarget();changed();});
$('antennaShape').onclick=run(()=>{if(!headTexture(target))return;PaintLayers.requireEditable();checkpoint();let c=canvases[target][activeLayer],ctx=c.getContext('2d'),inner=project.textures[target].layers[activeLayer].surface==='inner';ctx.clearRect(0,0,c.width,c.height);ctx.fillStyle='#ffffff';HeadSegments.markCustom(target);if(target.startsWith('ear')){if(inner){ctx.fillRect(3,1,18,30);}else{ctx.strokeStyle='#ffffff';ctx.lineWidth=2;ctx.strokeRect(1,1,22,30);}}else if(inner){ctx.fillRect(7,3,10,44);}else{ctx.fillRect(3,0,5,48);ctx.fillRect(3,0,18,4);ctx.fillRect(3,11,14,4);ctx.fillRect(3,22,11,4);}changed();});
$('mirrorAntenna').onclick=run(()=>{if(['sleeve','sleeveR'].includes(target)){const from=target==='sleeve'?0:1;PuppetArms.copySleeve(project.design,from,1-from,false);buildSettings();changed();return;}if(!headTexture(target))return notice('请先选择天线或耳机素材');let other=target.slice(0,-1)+(target.endsWith('L')?'R':'L');PaintLayers.requireWritableTexture(other);PaintLayers.copyTexture(target,other);HeadSegments.markCustom(target);HeadSegments.markCustom(other);changed();});
function download(content,type,name){let a=document.createElement('a'),url=URL.createObjectURL(new Blob([content],{type}));a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),5000);}
function choose(accept,fn){let i=$('fileInput');i.accept=accept;i.value='';i.onchange=run(async()=>{if(i.files[0])await fn(i.files[0]);});i.click();}
$('textureImport').onclick=run(()=>{const key=target,selection=PuppetArms.selectedTarget(key),layerId=project.textures[key].layers[activeLayer].id,owner=project;PaintLayers.requireEditable();PaintLayers.requireBaseInitialization(key);choose('image/png',async f=>{let im=new Image(),url=URL.createObjectURL(f);try{im.src=url;await im.decode();if(project!==owner)throw Error(MI18n.text('项目已切换，请重新导入。'));if(PuppetArms.canonical(selection)!==key)throw Error(MI18n.text('贴图同步设置已改变，请重新导入。'));let index=project.textures[key].layers.findIndex(layer=>layer.id===layerId);PaintLayers.requireEditable(key,index);PaintLayers.requireBaseInitialization(key);if(!await HandTextureBase.prepare(key))throw Error(MI18n.t('hand.textureLoading'));if(project!==owner)throw Error(MI18n.text('项目已切换，请重新导入。'));if(PuppetArms.canonical(selection)!==key)throw Error(MI18n.text('贴图同步设置已改变，请重新导入。'));index=project.textures[key].layers.findIndex(layer=>layer.id===layerId);PaintLayers.requireEditable(key,index);PaintLayers.requireBaseInitialization(key);if(/^puppetHand[0-3]$/.test(key)&&index===0&&project.textures[key].layers.length>1)PaintLayers.requireEditable(key,1);target=PuppetArms.select(selection);activeLayer=index;checkpoint();if(/^puppetHand[0-3]$/.test(key)&&index===0){index=project.textures[key].layers.length>1?1:PaintLayers.append(key,false);activeLayer=index;}editableBase();if(!HandTextureBase.ensure(key))throw Error(MI18n.t('hand.textureLoading'));PuppetArms.textureChanged(key,true);if(activeLayer===0&&fabricKey(key))project.textures[key].editableBase=true;let c=canvases[key][index],ctx=c.getContext('2d');ctx.imageSmoothingEnabled=false;ctx.clearRect(0,0,c.width,c.height);PuppetArms.drawImported(ctx,im,key,c.width,c.height);project.textures[key].layers[index].visible=true;project.textures[key].layers[index].opacity=1;if(headTexture(key))HeadSegments.markCustom(key);PuppetArms.textureChanged(key);updateTarget();changed();}finally{URL.revokeObjectURL(url);}});});
$('textureExport').onclick=()=>materialPreview(PuppetArms.selectedTarget(target)).toBlob(b=>download(b,'image/png',project.projectId+'-'+target+'.png'));
async function newProject(){creatingProject=true;syncProjectControls();try{await MI18n.ready;const value=await api('default');value.name=MI18n.t('default.project_name');return value;}finally{creatingProject=false;syncProjectControls();}}
async function listProjects(){const version=++listVersion,items=await api('projects');if(version!==listVersion)return;projects=items;let s=$('projects');s.replaceChildren();let first=document.createElement('option');first.value='';first.textContent='打开已保存项目';s.append(first);for(let fixed of [true,false]){let group=document.createElement('optgroup');group.label=fixed?'固定项目':'自建项目';for(let p of projects.filter(p=>!!p.fixedProject===fixed)){let o=document.createElement('option');o.value=p.projectId;o.textContent=p.name;MI18n.content(o);group.append(o);}if(group.children.length)s.append(group);}syncProjectSelection();}
function save(){
 if(loading)throw Error(MI18n.t('appearance.projectLoading'));
 const sent=structuredClone(serialize()),revision=editVersion,version=loadVersion;savePending++;savingProject=true;syncProjectControls();
 const task=saveQueue.catch(()=>{}).then(async()=>{const r=await api('save',sent);if(project.projectId===sent.projectId&&version===loadVersion){acceptSavedFields(r.project);if(revision===editVersion)dirty=false;}await listProjects();if(project.projectId===sent.projectId&&version===loadVersion)notice('已保存 '+r.project.name+' · '+r.project.updatedAt);return r;});saveQueue=task;
 return task.finally(()=>{savingProject=--savePending>0;syncProjectControls();});
}
function deploymentNotice(result){
 const state=result.activation?.state;
 const key=state==='needs-enable'?'appearance.apply.needsEnable':['enabled','not-required'].includes(state)?'appearance.apply.ready':'appearance.apply.unknown';
 return MI18n.t(key,{name:result.project.name});
}
async function apply(loud=true){
 if(loading||savingProject||applyingProject)throw Error(MI18n.t('appearance.projectLoading'));
 const sent=structuredClone(serialize()),revision=editVersion,version=loadVersion;applyingProject=true;syncProjectControls();
 try{const r=await api('deploy',sent);if(project.projectId===sent.projectId&&version===loadVersion){acceptSavedFields(r.project);if(revision===editVersion)dirty=false;}if(loud){await listProjects();if(project.projectId===sent.projectId&&version===loadVersion)notice(deploymentNotice(r));}return r;}finally{applyingProject=false;syncProjectControls();}
}
async function changeProject(next,{fresh=false}={}){
 if(changingProject)return;changingProject=true;document.querySelector('main').inert=true;syncProjectControls();
 try{if(dirty)await save();await load(await next());if(fresh)changed();}
 finally{changingProject=false;document.querySelector('main').inert=loading||restoringHistory||!!window.MIProjectActions?.busy;syncProjectSelection();syncProjectControls();}
}
$('projectName').oninput=()=>{project.name=$('projectName').value;changed();};$('projects').onchange=run(async()=>{const id=$('projects').value;if(id)await changeProject(()=>projects.find(x=>x.projectId===id));});
$('new').onclick=run(()=>changeProject(newProject,{fresh:true}));$('save').onclick=run(save);$('apply').onclick=run(()=>apply());$('import').onclick=()=>choose('.json',async f=>{let p=JSON.parse(await f.text());if(!['eoe.creator.v2','moreiterators.project.v1'].includes(p.schema))throw Error('请选择完整的编辑器项目 JSON。');await changeProject(async()=>{const result=await api('import-project',p);await listProjects();return result.project;});});
$('dialogueEditor').onclick=()=>window.MIStudioNavigation?.go('/dialogue',{newTab:true});
document.addEventListener('click',e=>{if(!e.target.closest('#otherStudios'))$('otherStudios').open=false;});
document.addEventListener('keydown',e=>{if(e.key==='Escape')$('otherStudios').open=false;});
$('export').onclick=()=>$('exportDialog').showModal();$('projectExport').onclick=run(async()=>{await save();download(JSON.stringify(serialize(),null,2),'application/json',project.projectId+'.json');});$('bundleExport').onclick=run(async()=>{let parts=[...document.querySelectorAll('[name=part]:checked')].map(i=>i.value);await save();let r=await api('export',{project:serialize(),parts});let a=document.createElement('a');a.href=r.url;a.download='';a.click();notice('已导出所选素材包。');});
$('history').onclick=run(async()=>{
 const owner=project.projectId,version=loadVersion,entries=await api('history?id='+encodeURIComponent(owner));if(project.projectId!==owner||version!==loadVersion)return;
 const host=$('historyList');host.replaceChildren();if(!entries.length){const empty=document.createElement('p');empty.textContent=MI18n.t('appearance.historyEmpty');host.append(empty);}
 for(const entry of entries){const row=document.createElement('div');row.className='history-entry';const label=MI18n.content(document.createElement('span')),time=document.createElement('time'),button=document.createElement('button');label.textContent=entry.project.name;const date=new Date(entry.project.updatedAt);time.textContent=Number.isNaN(date.valueOf())?entry.file.replace('.json',''):date.toLocaleString(MI18n.locale);button.textContent=MI18n.t('appearance.historyRestore');button.onclick=run(async()=>{if(restoringHistory)return;if(project.projectId!==owner)throw Error(MI18n.t('appearance.historyChanged'));restoringHistory=true;host.inert=true;document.querySelector('main').inert=true;syncProjectControls();try{if(dirty)await save();await load(entry.project);changed();const saved=await save();await load(saved.project);$('historyDialog').close();notice(MI18n.t('appearance.historyRestored'));}finally{restoringHistory=false;host.inert=false;document.querySelector('main').inert=loading||changingProject;syncProjectControls();}});row.append(label,time,button);host.append(row);}
 if(!$('historyDialog').open)$('historyDialog').showModal();
});

window.addEventListener('mi-language-change',()=>{if(project&&!loading){refreshProjectIdentity();buildSettings();updateTarget();}});
window.MIStudioPage={projectId:()=>window.MIProjectActions?.unavailable?null:project?.projectId,isBusy:()=>!project||loading||creatingProject||savingProject||applyingProject||restoringHistory||changingProject||historyBusy||!!window.MIUndo?.busy||!!window.MIProjectActions?.busy,
 saveBeforeNavigate:async()=>{if(project&&(dirty||!projects.some(item=>item.projectId===project.projectId)))await save();return !dirty;},error:message=>notice(message,true)};
function focusVoiceSettings(){
 if(location.hash!=='#iteratorVoice')return;
 requestAnimationFrame(()=>{
  const section=document.querySelector('[data-section-id="iteratorVoice"]');if(!section)return;
  for(let node=section;node;node=node.parentElement)if(node.tagName==='DETAILS')node.open=true;
  requestAnimationFrame(()=>{
   if(!section.isConnected)return;
   const summary=section.querySelector('summary')||section,settings=section.closest('#settings');
   if(settings&&/auto|scroll/.test(getComputedStyle(settings).overflowY)&&settings.scrollHeight>settings.clientHeight){settings.scrollTop+=summary.getBoundingClientRect().top-settings.getBoundingClientRect().top-12;}
   summary.focus({preventScroll:true});
   const headerBottom=Math.max(0,document.querySelector('.mi-topbar')?.getBoundingClientRect().bottom||0);
   window.scrollBy({top:summary.getBoundingClientRect().top-headerBottom-12,behavior:'instant'});
  });
 });
}
window.addEventListener('hashchange',focusVoiceSettings);
function appearanceHistoryData(){
 const p=serialize(),editor={...p.editor};delete editor.target;delete editor.layer;
 return {name:p.name,design:p.design,textures:p.textures,editor};
}
function appearanceView(){return {target:PuppetArms.selectedTarget(target),layer:activeLayer,layerId:project.textures[target]?.layers[activeLayer]?.id,
 paint:workspace.capturePaintView(),window:[scrollX,scrollY],scroll:['settings','paintPanel','paintLayers'].map(id=>[id,$(id).scrollLeft,$(id).scrollTop])};}
async function restoreAppearanceView(view){
 // Wait for the rebuilt settings and ResizeObserver to settle before restoring
 // scroll offsets. View state is deliberately independent of document history.
 await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
 workspace.restorePaintView(view.paint);
 for(const [id,left,top] of view.scroll){$(id).scrollLeft=left;$(id).scrollTop=top;}
 window.scrollTo(...view.window);
}
const paintDesignFlags=['earCustom','earDecorationCustom','antennaCustom','antennaLowerCustom'];
const paintArmFlags=['handTextureEnabled','handTextureTint','sleeveOwnTexture','sleeveTextureEnabled'];
function paintHistoryStructure(value){
 const data=structuredClone(value);
 for(const key of paintDesignFlags)delete data.design[key];
 for(const arm of data.design.puppetArms||[])for(const key of paintArmFlags)delete arm[key];
 for(const tex of Object.values(data.textures)){delete tex.editableBase;delete tex.custom;for(const layer of tex.layers){delete layer.png;delete layer.id;}}
 return JSON.stringify(data);
}
async function restorePaintPixels(value,current){
 if(paintHistoryStructure(value)!==paintHistoryStructure(current))return false;
 const buffers=[],selectedId=project.textures[target]?.layers[activeLayer]?.id;
 for(const [key,tex] of Object.entries(value.textures))for(const [i,layer] of tex.layers.entries()){
  if(layer.png===current.textures[key].layers[i].png)continue;
  const buffer=canvas(...dimensions[key]);if(layer.png){const im=new Image();im.src=layer.png;await im.decode();buffer.getContext('2d').drawImage(im,0,0,buffer.width,buffer.height);}buffers.push([key,i,buffer]);
 }
 // Decode first, then commit. A failed image never leaves half-restored artwork.
 for(const [key,i,buffer] of buffers){const c=canvases[key][i],ctx=c.getContext('2d');ctx.clearRect(0,0,c.width,c.height);ctx.drawImage(buffer,0,0);}
 const assign=(to,from,keys)=>{for(const key of keys){if(Object.hasOwn(from,key))to[key]=structuredClone(from[key]);else delete to[key];}};
 assign(project.design,value.design,paintDesignFlags);
 for(const [i,arm] of (value.design.puppetArms||[]).entries())assign(project.design.puppetArms[i],arm,paintArmFlags);
 let layersChanged=false;
 for(const [key,tex] of Object.entries(value.textures)){
  assign(project.textures[key],tex,['editableBase','custom']);
  for(const [i,layer] of tex.layers.entries()){const dest=project.textures[key].layers[i];if(key===target&&dest.id!==layer.id)layersChanged=true;assign(dest,layer,['png','id']);}
 }
 const selectedIndex=project.textures[target]?.layers.findIndex(layer=>layer.id===selectedId);if(selectedIndex>=0)activeLayer=selectedIndex;
 for(const key of paintDesignFlags){const input=document.querySelector('[data-wardrobe-key="'+key+'"]');if(input)input.checked=!!project.design[key];}
 PuppetArms.refreshFields();syncSettingDependencies();if(layersChanged)PaintLayers.render($('layerList'));render();return true;
}
async function restoreAppearanceHistory(value){
 const view=appearanceView(),main=document.querySelector('main'),wasInert=main.inert;
 historyBusy=true;main.inert=true;
 try{
  if(!await restorePaintPixels(value,appearanceHistoryData())){
   await load({...project,...value,editor:{...value.editor,target:view.target,layer:view.layer}},view);
   await restoreAppearanceView(view);
  }
  markDirty();
 }finally{historyBusy=false;main.inert=wasInert;syncProjectControls();}
}
window.MIUndo?.register({key:()=>project?.projectId,
 capture:appearanceHistoryData,
 busy:()=>!project||loading||creatingProject||savingProject||applyingProject||restoringHistory||changingProject||!!stroke||!!window.MIProjectActions?.busy,
 restore:restoreAppearanceHistory,
 onError:error=>notice(error.message,true)});
document.addEventListener('mi-undo-state',syncProjectControls);
window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});
document.addEventListener('DOMContentLoaded',run(async()=>{preset=await api('preset.json');control=await api('control');await listProjects();let params=new URLSearchParams(location.search),id=params.get('project')||params.get('projectId');let p=projects.find(p=>p.projectId===id)||projects[0]||await newProject();await load(p);if(!projects.length){await save();}render();}));



for(const [id,kind] of [['editEntry','entry'],['editAI','ai']])$(id).onclick=run(async()=>{await save();const r=await api('open-room',{projectId:project.projectId,kind});notice('已在 Rained 打开 '+r.room);});
for(const [id,kind] of [['syncEntry','entry'],['syncAI','ai']])$(id).onclick=run(async()=>{await save();const r=await api('sync-room',{projectId:project.projectId,kind});notice('已同步 '+r.room+' · '+r.cameras+' 个画面，并应用到游戏。');});
