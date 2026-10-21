'use strict';
const wardrobeOrder=['back','legs','body','neck','gown','sleeves','collar','shawl1','shawl2','shawl3','shawl4','shawl5','frontL','frontR','necklaces','head'];
const wardrobeNames={back:'后围巾',legs:'腿部',body:'身体',neck:'脖子（衣料下方）',gown:'长袍',sleeves:'袖子',collar:'领子',frontL:'左前围巾',frontR:'右前围巾',necklaces:'项链',head:'头部与面部'};
for(let i=1;i<=5;i++)wardrobeNames['shawl'+i]='披肩第 '+i+' 层';
function garmentDefault(id){let right=id==='frontR';return {id,enabled:false,type:'cloth',width:10,length:27,topWidth:5,anchor:'shoulders',anchor2:'shoulders',u:right?1:0,v:0,u2:right?1:0,v2:0,x:0,y:0,x2:0,y2:0,midX:0,midY:0,sag:2,roundness:.65,elasticity:.65,gravity:1,fringe:false,fringeLength:5,fringeColor:'#bbc4c7',topColor:'#303a40',middleColor:'#667079',bottomColor:'#abb5bc',grain:.1,mirror:false,lockGown:false,rigidRotation:0,bindRow:0,canvasWidth:64,canvasHeight:96};}
function garmentPieces(d){return [...(d.frontPanels||[]),...(d.shawls||[]),...(d.accessories||[])];}
function garmentFind(d,key){return garmentPieces(d).find(x=>x.id===key);}
function wardrobeInit(p){
 let d=p.design;d.layers??={};d.layers.body??=true;d.layers.neck??=d.layers.head??true;d.sleeveMapping??='strip';d.armShadowStrength??=.35;d.sleeveSymmetry??=true;d.sleeveLeftEnabled??=true;d.sleeveRightEnabled??=true;
 for(let k of ['TopColor','MiddleColor','BottomColor','Grain'])d['sleeveRight'+k]??=d['sleeve'+k];
 d.frontSymmetry??=true;d.frontPanels??=[garmentDefault('frontL'),garmentDefault('frontR')];
 d.shawlCount??=0;d.shawls??=Array.from({length:5},(_,i)=>({...garmentDefault('shawl'+(i+1)),anchor:'sleeveL',anchor2:'sleeveR',u:.5,u2:.5,width:23,length:10+i*2,topWidth:0,sag:3,midY:-1,roundness:.9}));
 d.accessories??=[];d.renderOrder??=[...wardrobeOrder];
 for(let [k,v] of Object.entries({straightLegs:false,thighLength:10,shinLength:13,legWidth:2.5,kneeSize:3,legElasticity:.7,legSymmetry:true,legSpacing:6,legLeftOffset:0,legRightOffset:0}))d[k]??=v;
 for(const k of legParameterKeys)d[rightLegKey(k)]??=d[k];
 for(let a of garmentPieces(d))Object.assign(a,{...garmentDefault(a.id),...a});
 for(let key of Object.keys(dimensions))if(/^(front|shawl|custom)/.test(key))delete dimensions[key];
 Object.assign(dimensions,{sleeveR:[32,64],legThigh:[24,48],legKnee:[24,24],legShin:[24,48],legThighR:[24,48],legKneeR:[24,24],legShinR:[24,48]});
 for(let a of garmentPieces(d))dimensions[a.id]=[a.canvasWidth,a.canvasHeight];
 for(let id of [...wardrobeOrder,...d.accessories.map(a=>a.id)])if(!d.renderOrder.includes(id))d.renderOrder.push(id);
}
function wardrobeColors(key){let d=project.design,a=garmentFind(d,key);if(a)return [[a.topColor,a.middleColor,a.bottomColor],a.grain];if(key.startsWith('leg'))return [[d.headColor,d.headColor,d.headColor],0];if(key==='sleeveR')return [['TopColor','MiddleColor','BottomColor'].map(k=>d['sleeveRight'+k]),d.sleeveRightGrain];return null;}
function wardrobeTargets(){let sel=$('target');for(let opt of [...sel.options])if(opt.dataset.wardrobe)opt.remove();sel.querySelector('[value="sleeve"]').textContent='左袖';
 for(let key of Object.keys(dimensions)){if(['sleeveR',...legTextureKeys].includes(key)||/^(front|shawl|custom)/.test(key)){let a=garmentFind(project.design,key),opt=new Option(({sleeveR:'右袖',legThigh:'左大腿',legKnee:'左膝关节',legShin:'左小腿',legThighR:'右大腿',legKneeR:'右膝关节',legShinR:'右小腿'})[key]||wardrobeNames[key]||a?.name||key,key);opt.dataset.wardrobe='1';if(a?.name&&!wardrobeNames[key])MI18n.content(opt);sel.add(opt);}}
 const options=new Map([...sel.options].map(o=>[o.value,o]));sel.replaceChildren();
 const sets=[['头部',['forehead','face','earL','earR','antennaL','antennaR']],['身体',legTextureKeys],['服装',['gown','sleeve','sleeveR','collar','frontL','frontR','shawl1','shawl2','shawl3','shawl4','shawl5','scarf']],['自定义配件',project.design.accessories.map(a=>a.id)]];
 for(const [name,keys] of sets){const group=document.createElement('optgroup');group.label=name;for(const key of keys){const option=options.get(key);if(option){group.append(option);options.delete(key);}}if(group.children.length)sel.append(group);}for(const option of options.values())sel.add(option);
 if(!dimensions[target])target='gown';sel.value=target;
}
function garmentField(host,obj,key,label,kind,min,max,step,after){let row=document.createElement('label');row.className='field';let span=document.createElement('span');span.textContent=label;let input=document.createElement(kind==='select'?'select':'input');input.setAttribute('aria-label',label);input.dataset.wardrobeKey=key;
 if(kind==='select'){for(let [k,v] of Object.entries(min))input.add(new Option(v,k));input.value=obj[key];}else {input.type=kind;if(kind==='range'||kind==='number'){input.min=min;input.max=max;input.step=step||1;}if(kind==='checkbox')input.checked=!!obj[key];else input.value=obj[key];}
 let out=document.createElement('output');if(kind==='range')out.textContent=obj[key];input.oninput=run(()=>{const before=obj[key];try{obj[key]=kind==='checkbox'?input.checked:(['number','range'].includes(kind)||kind==='select'&&typeof obj[key]==='number')?+input.value:input.value;out.textContent=kind==='range'?input.value:'';after?.();syncSettingDependencies();changed();}catch(error){try{obj[key]=before;}catch{}if(kind==='checkbox')input.checked=!!obj[key];else input.value=obj[key];out.textContent=kind==='range'?input.value:'';throw error;}});row.append(span,input);if(kind==='range')row.append(out);host.append(row);return input;}
const settingSectionIds={头部:'head',身体:'body',服装:'clothes','配饰与自定义':'extras',演算室:'room','图层与显示':'layers',长袍:'gown',袖子:'sleeves',领子:'collar','前围巾下摆':'frontPanels',披肩:'shawls',后围巾:'scarf','配饰 · 后围巾':'scarf',珍珠项链:'necklaces',机械支架:'mechanicalArm',脐带线:'cables',自定义插件:'accessories','IR cloak':'irCloak'};
function settingSectionId(identity){return settingSectionIds[identity]||'section-'+Array.from(String(identity),ch=>ch.codePointAt(0).toString(16)).join('-');}
function garmentSection(host,title){let d=document.createElement('details');d.dataset.sectionId=settingSectionId(title);let s=document.createElement('summary');s.textContent=title;d.append(s);host.append(d);return d;}
function garmentButton(host,text,fn){let b=document.createElement('button');b.textContent=text;b.onclick=run(fn);host.append(b);return b;}
function garmentPaint(key){target=key;activeLayer=1;$('target').value=key;updateTarget();$('paint').scrollIntoView({block:'center'});}
function copyGarmentTexture(from,to,mirror=true){if(typeof PaintLayers!=='undefined'){PaintLayers.copyTexture(from,to,mirror);changed();return;}canvases[from].forEach((c,i)=>{let dest=canvases[to][i],ctx=dest.getContext('2d');ctx.clearRect(0,0,dest.width,dest.height);ctx.save();if(mirror){ctx.translate(dest.width,0);ctx.scale(-1,1);}ctx.drawImage(c,0,0,dest.width,dest.height);ctx.restore();Object.assign(project.textures[to].layers[i],{visible:project.textures[from].layers[i].visible,opacity:project.textures[from].layers[i].opacity});});project.textures[to].editableBase=project.textures[from].editableBase;changed();}
function sleeveMaterial(key){if(key==='sleeveR'&&project.design.sleeveSymmetry){let src=clothPreview('sleeve'),c=canvas(src.width,src.height),ctx=c.getContext('2d');ctx.translate(c.width,0);ctx.scale(-1,1);ctx.drawImage(src,0,0);return c;}return clothPreview(key);}
let settingsConditions=[],layerOrderView=null;
function referenceColor(alpha=""){return (project.editor?.guideColor||"#ffffff")+alpha;}
function layerIsEnabled(d,id){
 const l=d.layers||{};if(id==="back")return d.scarfPanels>0;if(id==="legs")return l.feet!==false;if(id==="body")return l.body!==false;if(id==="neck")return l.neck!==false;
 if(id==="gown")return l.robe!==false;if(id==="sleeves")return (l.sleeves!==false&&(d.sleeveLeftEnabled!==false||d.sleeveRightEnabled!==false))||l.hands!==false;
 if(id==="collar")return l.collar!==false&&d.collarHeight>0;if(id==="necklaces")return d.necklaceCount>0;
 if(id==="head")return ["head","eyes","face","ears","antenna"].some(k=>l[k]!==false);
 if(id.startsWith("pearlAccessory:"))return !!(typeof pearlAccessoryFind==='function'&&pearlAccessoryFind(d,id)?.enabled);
 if(id.startsWith("shawl"))return +id.slice(5)<=d.shawlCount;return !!garmentFind(d,id)?.enabled;
}
function syncLayerOrder(){if(!layerOrderView)return;const {host,d,note}=layerOrderView;let count=0;for(const row of host.querySelectorAll("[data-render-layer]")){const id=row.dataset.renderLayer;row.hidden=!layerIsEnabled(d,id);if(!row.hidden){const a=garmentFind(d,id)||(typeof pearlAccessoryFind==='function'?pearlAccessoryFind(d,id):null);row.textContent=(++count)+". "+(row.draggable?"↕ ":"· ")+(id==="sleeves"&&!d.layers.sleeves?"手":wardrobeNames[id]||a?.name||id);}}note.textContent=MI18n.t('layer.order.directionCount',{count});}
function settingDependency(host,test){const body=document.createElement('div');body.className='setting-dependents';host.append(body);settingsConditions.push({body,test});return body;}
function syncSettingDependencies(){for(const {body,test} of settingsConditions){const enabled=!!test();body.hidden=!enabled;body.inert=!enabled;}syncLayerOrder();if(typeof PaintTargets!=='undefined')PaintTargets.sync();}
function settingsFieldDependencies(host,keys,test){const rows=[...host.querySelectorAll('.field')].filter(row=>keys.includes(row.querySelector('input,select,textarea')?.dataset.wardrobeKey));if(!rows.length)return;const body=settingDependency(host,test);rows[0].before(body);for(const row of rows)body.append(row);}
function settingsLayerSwitch(host,d,key,label){const input=garmentField(host,d.layers,key,label,'checkbox',null,null,null,()=>{$('groups').querySelectorAll('[data-layer="'+key+'"]').forEach(x=>x.checked=d.layers[key]);});input.dataset.layer=key;input.closest('.field').classList.add('enable-field');return input;}
function settingsPath(node,host){const parts=[];for(let p=node;p&&p!==host;p=p.parentElement)if(p.tagName==='DETAILS')parts.unshift(p.dataset.sectionId||p.id||'section-'+Array.from(p.parentElement.children).indexOf(p));return parts.join('/');}
function captureSettingsOpen(host){return new Map([...host.querySelectorAll('details')].map(e=>[settingsPath(e,host),e.open]));}
function restoreSettingsOpen(host,state){for(const e of host.querySelectorAll('details')){const key=settingsPath(e,host);if(state.has(key))e.open=state.get(key);}}
function settingsNote(host,text){const p=document.createElement('p');p.className='hint';p.textContent=text;host.append(p);return p;}
function wardrobeSettings(buckets,d){
 wardrobeTargets();
 const front=garmentSection(buckets.clothes,'前围巾下摆');garmentField(front,d,'frontSymmetry','左右同步','checkbox');
 for(const a of d.frontPanels){const sub=garmentSection(front,a.id==='frontL'?'左片':'右片');sub.dataset.paintTarget=a.id;garmentField(sub,a,'enabled','启用'+(a.id==='frontL'?'左片':'右片'),'checkbox');const body=settingDependency(sub,()=>a.enabled);
  if(a.id==='frontR'){const inherited=settingDependency(body,()=>d.frontSymmetry);garmentButton(inherited,'改为独立编辑右片',()=>{d.frontSymmetry=false;buildSettings();changed();});}
  const edits=settingDependency(body,()=>a.id==='frontL'||!d.frontSymmetry);garmentField(edits,a,'lockGown','包裹内部长袍','checkbox');garmentControls(edits,a,false);
 }
 const shawls=garmentSection(buckets.clothes,'披肩');garmentField(shawls,d,'shawlCount','启用层数','select',{0:'关闭',1:'1 层',2:'2 层',3:'3 层',4:'4 层',5:'5 层'});
 const shawlBody=settingDependency(shawls,()=>d.shawlCount>0);
 for(let i=0;i<5;i++){const holder=settingDependency(shawlBody,()=>i<d.shawlCount);const sub=garmentSection(holder,'第 '+(i+1)+' 层披肩');sub.dataset.paintTarget=d.shawls[i].id;garmentControls(sub,d.shawls[i],true);}
 const legs=garmentSection(buckets.body,'腿部');
 garmentField(legs,d,'legSpacing','左右腿间距','range',0,30,.1);
 garmentField(legs,d,'legSymmetry','左右腿对称','checkbox');
 garmentField(legs,d,'straightLegs','替换为三段式直腿','checkbox');
 for(const [side,label] of [[0,'左'],[1,'右']]){
  const holder=settingDependency(legs,()=>side===0||!d.legSymmetry),sub=garmentSection(holder,label+'腿');
  garmentField(sub,d,side===0?'legLeftOffset':'legRightOffset',label+'腿左右偏移','range',-15,15,.1);
  const native=settingDependency(sub,()=>!d.straightLegs);
  garmentField(native,d,side===0?'legLength':'rightLegLength',label+'腿长度','range',.7,1.4,.01);
  const custom=settingDependency(sub,()=>d.straightLegs);
  for(const [k,name,min,max,step] of [['thighLength','大腿长度',3,30,.1],['shinLength','小腿长度',3,36,.1],['legWidth','粗细',.5,10,.1],['kneeSize','膝关节大小',.5,12,.1],['legElasticity','弹性',0,1,.01]])garmentField(custom,d,side===0?k:rightLegKey(k),label+'腿'+name,'range',min,max,step);
  for(const [key,name] of [['legThigh','大腿'],['legKnee','膝关节'],['legShin','小腿']])garmentButton(custom,'绘制'+label+'腿'+name,()=>garmentPaint(key+(side?'R':'')));
  if(side===0)garmentButton(sub,'复制左腿到右腿',()=>{for(const k of legParameterKeys)d[rightLegKey(k)]=d[k];d.legRightOffset=-d.legLeftOffset;for(const k of ['legThigh','legKnee','legShin'])copyGarmentTexture(k,k+'R');d.legSymmetry=false;buildSettings();changed();});
 }
 const plugins=garmentSection(buckets.extras,'自定义插件');garmentButton(plugins,'新增配件',()=>{if(d.accessories.length>=12)throw Error('最多 12 个配件');const id=Array.from({length:12},(_,i)=>'custom'+(i+1)).find(x=>!d.accessories.some(a=>a.id===x));const a={...garmentDefault(id),enabled:true,name:MI18n.t('default.accessory_name',{index:id.slice(6)}),type:'rigid',anchor:'head',anchor2:'head',u:.3,u2:.7,width:12,length:14,topWidth:8};d.accessories.push(a);d.renderOrder.push(id);initGarmentCanvas(a);buildSettings();changed();});
 for(const a of d.accessories){const sub=garmentSection(plugins,a.name||a.id);sub.dataset.sectionId=a.id;MI18n.content(sub.querySelector('summary'));garmentField(sub,a,'enabled','启用配件','checkbox');const body=settingDependency(sub,()=>a.enabled);garmentField(body,a,'name','配件名称','text');garmentField(body,a,'type','配件类型','select',{cloth:'布料',rigid:'硬件'},null,null,buildSettings);garmentField(body,a,'mirror','以角色中轴镜像复制','checkbox');garmentControls(body,a,true,true);
  garmentButton(sub,'删除此配件',()=>{const bound=garmentPieces(d).filter(x=>x!==a&&(x.anchor===a.id||x.anchor2===a.id));const pearlBound=(d.pearlAccessories||[]).filter(x=>x.anchor===a.id);if(bound.length||pearlBound.length)throw Error('请先重新绑定引用此配件的项目');d.accessories=d.accessories.filter(x=>x!==a);d.renderOrder=d.renderOrder.filter(x=>x!==a.id);for(const x of garmentPieces(d)){if(x.anchor===a.id)x.anchor='shoulders';if(x.anchor2===a.id)x.anchor2='shoulders';}delete project.textures[a.id];delete canvases[a.id];delete dimensions[a.id];if(target===a.id)target='gown';buildSettings();updateTarget();changed();});
 }
 const layers=garmentSection(buckets.layers,'图层顺序');
 d.renderOrder=d.renderOrder.filter(id=>id!=='neck');d.renderOrder.splice(Math.min(...['gown','sleeves','collar','head','frontL','frontR','shawl1','shawl2','shawl3','shawl4','shawl5'].map(id=>d.renderOrder.indexOf(id)).filter(i=>i>=0)),0,'neck');
 layerOrderView={host:layers,d,note:settingsNote(layers,'')};let dragged=null;
 for(const id of d.renderOrder){const row=document.createElement('div');row.className='layer';row.dataset.renderLayer=id;if(id.startsWith('custom'))MI18n.content(row);row.draggable=/^(front|shawl|custom|pearlAccessory:)/.test(id);const a=garmentFind(d,id)||(typeof pearlAccessoryFind==='function'?pearlAccessoryFind(d,id):null);row.textContent=(d.renderOrder.indexOf(id)+1)+'. '+(row.draggable?'↕ ':'· ')+(wardrobeNames[id]||a?.name||id);row.ondragstart=e=>{dragged=id;e.dataTransfer.setData('text/plain',id);};row.ondragover=e=>e.preventDefault();row.ondrop=e=>{e.preventDefault();if(!dragged||dragged===id)return;d.renderOrder=d.renderOrder.filter(x=>x!==dragged);d.renderOrder.splice(d.renderOrder.indexOf(id),0,dragged);buildSettings();changed();};layers.append(row);}
}

function initGarmentCanvas(a){dimensions[a.id]=[a.canvasWidth,a.canvasHeight];project.textures[a.id]={...PaintLayers.blank(a.id),editableBase:a.type==='rigid'};canvases[a.id]=Array.from({length:4},()=>canvas(a.canvasWidth,a.canvasHeight));}
function garmentControls(host,a,points,custom=false){
 const shape=garmentSection(host,custom&&a.type==='rigid'?'形状':'形状与下摆');
 for(const [k,label,min,max,step] of [['length','长度',1,120,.1],['width','宽度',.5,120,.1]])garmentField(shape,a,k,label,'range',min,max,step);
 const clothShape=settingDependency(shape,()=>!custom||a.type==='cloth');
 for(const [k,label,min,max,step] of [['topWidth','顶端宽度（0 跟随固定点）',0,80,.1],['sag','下摆下垂',-30,60,.1],['roundness','下摆平滑度',0,1,.01]])garmentField(clothShape,a,k,label,'range',min,max,step);
 if(custom){const rigidShape=settingDependency(shape,()=>a.type==='rigid');garmentField(rigidShape,a,'rigidRotation','旋转','range',-180,180,1);}
 if(points){const binding=garmentSection(host,'绑定位置'),anchors=wardrobeAnchorOptions(project.design,a.id);
  for(const [label,suffix] of [['左端',''],['右端','2']]){const end=garmentSection(binding,label);garmentField(end,a,'anchor'+suffix,label+'绑定图层','select',anchors,null,null,buildSettings);for(const [k,name,min,max] of [['u','横向位置',0,1],['v','纵向位置',0,1],['x','左右偏移',-80,80],['y','上下偏移',-80,80]])garmentField(end,a,k+suffix,label+name,'range',min,max,.1);}
  const middleHolder=settingDependency(binding,()=>!custom||a.type==='cloth'),middle=garmentSection(middleHolder,'中点');garmentField(middle,a,'midX','中点左右偏移','range',-40,40,.1);garmentField(middle,a,'midY','中点上下偏移','range',-40,40,.1);
 }
 const physicsHolder=settingDependency(host,()=>!custom||a.type==='cloth');const physics=garmentSection(physicsHolder,'重力与弹性');garmentField(physics,a,'elasticity','柔软与弹性','range',0,1,.01);garmentField(physics,a,'gravity','重力影响','range',0,3,.01);
 if(custom)garmentField(physics,a,'bindRow','绑定横排（0 顶部 / 10 底部）','range',0,10,1);
 const material=garmentSection(host,'颜色与贴图');for(const [k,label] of [['topColor','上端颜色'],['middleColor','中部颜色'],['bottomColor','末端颜色']])garmentField(material,a,k,label,'color');garmentField(material,a,'grain','颗粒感','range',0,.4,.01);garmentButton(material,'绘制此层贴图',()=>garmentPaint(a.id));
 const fringeHolder=settingDependency(host,()=>!custom||a.type==='cloth'),fringe=garmentSection(fringeHolder,'末端流苏');garmentField(fringe,a,'fringe','启用末端流苏','checkbox');const fringeBody=settingDependency(fringe,()=>a.fringe);garmentField(fringeBody,a,'fringeColor','流苏颜色','color');garmentField(fringeBody,a,'fringeLength','流苏长度','range',0,30,.1);
 if(custom){const sizeGroup=garmentSection(host,'画布尺寸'),size={width:a.canvasWidth,height:a.canvasHeight};garmentField(sizeGroup,size,'width','画布宽度','number',8,256,1);garmentField(sizeGroup,size,'height','画布高度','number',8,256,1);garmentButton(sizeGroup,'应用尺寸',()=>{if(!Number.isInteger(size.width)||!Number.isInteger(size.height)||size.width<8||size.width>256||size.height<8||size.height>256)throw Error('尺寸为 8–256 整数');PaintLayers.requireWritableTexture(a.id);canvases[a.id]=canvases[a.id].map(old=>{const c=canvas(size.width,size.height),ctx=c.getContext('2d');ctx.imageSmoothingEnabled=false;ctx.drawImage(old,0,0,c.width,c.height);return c;});a.canvasWidth=size.width;a.canvasHeight=size.height;dimensions[a.id]=[size.width,size.height];undo=[];redo=[];updateTarget();changed();});}
}

// The offline renderer uses the same garment UV convention: top = bound seam.
const legParameterKeys=['legLength','thighLength','shinLength','legWidth','kneeSize','legElasticity'];
const legTextureKeys=['legThigh','legKnee','legShin','legThighR','legKneeR','legShinR'];
function rightLegKey(key){return 'right'+key[0].toUpperCase()+key.slice(1);}
function legValue(d,side,key){return side===1&&!d.legSymmetry?d[rightLegKey(key)]:d[key];}
function legShift(d,side){return (side?1:-1)*(d.legSpacing-6)/2+(side?(d.legSymmetry?-d.legLeftOffset:d.legRightOffset):d.legLeftOffset);}
function wardrobeLegPreview(ctx,d,map){
 if(!d.straightLegs||!d.layers.feet)return;
 const scale=d.puppetScale;
 for(let side=0;side<2;side++){
  const [x,y]=map((side?3:-3)+legShift(d,side),18,true),thigh=legValue(d,side,'thighLength'),shin=legValue(d,side,'shinLength'),width=legValue(d,side,'legWidth'),knee=legValue(d,side,'kneeSize');
  ctx.save();ctx.translate(x,y);if(side&&d.legSymmetry)ctx.scale(-1,1);
  const tex=key=>materialPreview(key+(side&&!d.legSymmetry?'R':''));
  ctx.drawImage(tex('legThigh'),-width*scale/2,0,width*scale,thigh*scale);
  ctx.drawImage(tex('legShin'),-width*scale/2,thigh*scale,width*scale,shin*scale);
  ctx.drawImage(tex('legKnee'),-knee*scale/2,(thigh-knee/2)*scale,knee*scale,knee*scale);ctx.restore();
 }
}
function previewLayerQueue(d){
 const order=[...new Set([...(d.renderOrder||wardrobeOrder),...wardrobeOrder,...garmentPieces(d).map(a=>a.id),...(d.pearlAccessories||[]).map(a=>a.id)])],commands=[];
 return {add(id,draw){commands.push({id,draw});},draw(){commands.sort((a,b)=>order.indexOf(a.id)-order.indexOf(b.id));for(const command of commands)command.draw();}};
}
const wardrobeFixedAnchors={head:'头部',body:'躯干',neck:'脖子',gown:'长袍网格',shoulders:'肩部',sleeveL:'左袖上端',sleeveR:'右袖上端',collar:'领子',handL:'左手',handR:'右手',legL:'左腿',legR:'右腿',earL:'左耳机',earR:'右耳机',earDecorationL:'左耳机下段装饰',earDecorationR:'右耳机下段装饰',antennaUpperL:'左天线上段',antennaUpperR:'右天线上段',antennaLowerL:'左天线下段',antennaLowerR:'右天线下段'};
function wardrobeAnchorOptions(d,excludeId){
 const anchors={...wardrobeFixedAnchors};
 function dependsOn(id,target,seen=new Set()){if(id===target)return true;if(seen.has(id))return false;seen.add(id);const piece=garmentFind(d,id);return !!piece&&(dependsOn(piece.anchor,target,seen)||dependsOn(piece.anchor2,target,seen));}
 for(const a of garmentPieces(d))if(!excludeId||!dependsOn(a.id,excludeId))anchors[a.id]=wardrobeNames[a.id]||a.name||a.id;
 return anchors;
}
function garmentBindingOrder(d){
 const result=[],visiting=new Set(),done=new Set(),pieces=garmentPieces(d),ids=new Set();
 for(const a of pieces){if(!a?.id||ids.has(a.id))throw Error('服装编号重复或次序错误');ids.add(a.id);}
 function visit(id){if(wardrobeFixedAnchors[id]||id==='antennaL'||id==='antennaR')return;const a=garmentFind(d,id);if(!a)throw Error('绑定图层不存在');if(done.has(id))return;if(visiting.has(id))throw Error('配件绑定形成循环');visiting.add(id);visit(a.anchor);visit(a.anchor2);visiting.delete(id);done.add(id);result.push(id);}
 for(const a of pieces)visit(a.id);return result;
}
function wardrobeGridPoint(xy,u,v){
 const n=Math.sqrt(xy.length/2),xx=Math.max(0,Math.min(1,u))*(n-1),yy=Math.max(0,Math.min(1,v))*(n-1),x=Math.min(n-2,Math.floor(xx)),y=Math.min(n-2,Math.floor(yy));
 const mix=(a,b,t)=>a+(b-a)*t;
 return [0,1].map(k=>mix(mix(xy[(x*n+y)*2+k],xy[((x+1)*n+y)*2+k],xx-x),mix(xy[(x*n+y+1)*2+k],xy[((x+1)*n+y+1)*2+k],xx-x),yy-y));
}
function wardrobeNativeAnchor(xy,type='grid'){
 const mix=(a,b,t)=>a+(b-a)*t;
 if(type==='strip')return {sample(u,v){const rows=xy.length/4,t=Math.max(0,Math.min(1,v))*(rows-1),row=Math.min(rows-2,Math.floor(t));return [0,1].map(k=>mix(mix(xy[row*4+k],xy[row*4+2+k],u),mix(xy[(row+1)*4+k],xy[(row+1)*4+2+k],u),t-row));}};
 if(type==='bounds'){const xs=xy.filter((_,i)=>i%2===0),ys=xy.filter((_,i)=>i%2===1),left=Math.min(...xs),right=Math.max(...xs),top=Math.min(...ys),bottom=Math.max(...ys);return {sample:(u,v)=>[mix(left,right,u),mix(top,bottom,v)]};}
 const n=Math.sqrt(xy.length/2),reverse=xy[(n-1)*n*2]<xy[0];return {sample:(u,v)=>wardrobeGridPoint(xy,reverse?1-u:u,v)};
}
function wardrobeStraightLegAnchors(d,map){
 const anchors={};for(let side=0;side<2;side++){const [x,y]=map((side?3:-3)+legShift(d,side),18,true),scale=d.puppetScale,width=legValue(d,side,'legWidth')*scale,len=(legValue(d,side,'thighLength')+legValue(d,side,'shinLength'))*scale;anchors[side?'legR':'legL']={sample:(u,v)=>[x+(u-.5)*width,y+v*len]};}return anchors;
}
function wardrobeAnchorPoint(anchors,id,u,v){
 const target=anchors[id];if(!target)throw Error('绑定图层不存在：'+id);
 if(typeof target.sample==='function')return target.sample(u,v);
 if(target.xy)return wardrobeGridPoint(target.xy,u,v);
 return [target[0][0]+(target[1][0]-target[0][0])*u,target[0][1]+(target[1][1]-target[0][1])*u+v*8];
}
function wardrobeAnchorFrame(anchors,id){
 const a=wardrobeAnchorPoint(anchors,id,0,.5),b=wardrobeAnchorPoint(anchors,id,1,.5),top=wardrobeAnchorPoint(anchors,id,.5,0),bottom=wardrobeAnchorPoint(anchors,id,.5,1);
 const len=Math.hypot(b[0]-a[0],b[1]-a[1]),right=len>.0001?[(b[0]-a[0])/len,(b[1]-a[1])/len]:[1,0];let down=[-right[1],right[0]];
 if(down[0]*(bottom[0]-top[0])+down[1]*(bottom[1]-top[1])<0)down=down.map(x=>-x);return {right,down};
}
function wardrobeRigidPoint(a,b,frame,d,scale,u,v){
 const angle=(d.rigidRotation||0)*Math.PI/180,c=Math.cos(angle),s=Math.sin(angle),r=frame.right,down=frame.down,axis=[r[0]*c-down[0]*s,r[1]*c-down[1]*s],vertical=[down[0]*c+r[0]*s,down[1]*c+r[1]*s];
 return [0,1].map(i=>(a[i]+b[i])/2+axis[i]*(u-.5)*d.width*scale+vertical[i]*v*d.length*scale);
}
function wardrobePreview(ctx,d,anchors,queue){
 // EOE's character-specific preview supplies a placement phase instead of a queue.
 if(typeof queue==='string'){const phase=queue,order=d.renderOrder||wardrobeOrder;queue={add(id,draw){const behind=order.indexOf(id)<order.indexOf('gown');if(behind===(phase==='back'))draw();}};}
 // Resolve attachment geometry first; drawing order must not change its position.
 for(let id of garmentBindingOrder(d)){let a=garmentFind(d,id);let enabled=id.startsWith('shawl')?+id.slice(5)<=d.shawlCount:a.enabled;
 if(id==='frontR'&&d.frontSymmetry)a={...d.frontPanels[0],id:'frontR',u:1,u2:1,enabled:a.enabled};
 let aa=wardrobeAnchorPoint(anchors,a.anchor,a.u,a.v),bb=wardrobeAnchorPoint(anchors,a.anchor2,a.u2,a.v2),scale=d.puppetScale,cloth=a.type==='cloth',frame=wardrobeAnchorFrame(anchors,a.anchor);
 aa=[aa[0]+a.x*scale,aa[1]-a.y*scale];bb=[bb[0]+a.x2*scale,bb[1]-a.y2*scale];if(cloth&&a.topWidth>0){let m=[(aa[0]+bb[0])/2,(aa[1]+bb[1])/2],len=Math.hypot(bb[0]-aa[0],bb[1]-aa[1]),axis=len>.001?[(bb[0]-aa[0])/len,(bb[1]-aa[1])/len]:[1,0];aa=m.map((v,i)=>v-axis[i]*a.topWidth*scale/2);bb=m.map((v,i)=>v+axis[i]*a.topWidth*scale/2);}
 let xy=[],uv=[],triangles=[],n=10,top=Math.hypot(bb[0]-aa[0],bb[1]-aa[1]);for(let x=0;x<=n;x++)for(let y=0;y<=n;y++){let u=x/n,v=(y-(cloth?(a.bindRow||0):0))/n,curve=(1-a.roundness)*(1-Math.abs(2*u-1))+a.roundness*Math.sin(Math.PI*u);if(cloth)xy.push(aa[0]+(bb[0]-aa[0])*u+(u-.5)*(a.width*scale-top)*v+a.midX*4*u*(1-u)*scale,aa[1]+(bb[1]-aa[1])*u+(a.length+a.sag*curve)*v*scale-a.midY*4*u*(1-u)*scale);else xy.push(...wardrobeRigidPoint(aa,bb,frame,a,scale,u,y/n));uv.push(u,y/n);if(x<n&&y<n){let k=x*(n+1)+y;triangles.push(k,k+1,k+n+1,k+1,k+n+2,k+n+1);}}
 anchors[id]={xy};if(!enabled)continue;
 if(cloth&&id.startsWith('front')&&a.lockGown&&anchors.gownMesh){let gm=anchors.gownMesh,gn=Math.sqrt(gm.length/2),side=id==='frontL'?0:1;for(let y=0;y<=n;y++){let gy=Math.min(gn-1,Math.round(y/n*(gn-1))),l=[gm[gy*2],gm[gy*2+1]],r=[gm[((gn-1)*gn+gy)*2],gm[((gn-1)*gn+gy)*2+1]];if(l[0]>r[0])[l,r]=[r,l];let mid=[(l[0]+r[0])/2,(l[1]+r[1])/2],outer=side?r:l;outer[0]+=(side?1:-1)*.6*scale;for(let x=0;x<=n;x++){let u=x/n,a0=side?mid:outer,b0=side?outer:mid,k=(x*(n+1)+y)*2;xy[k]=a0[0]+(b0[0]-a0[0])*u;xy[k+1]=a0[1]+(b0[1]-a0[1])*u;}}}
 queue.add(id,()=>{let key=id==='frontR'&&d.frontSymmetry?'frontL':id,im=materialPreview(key);if(id==='frontR'&&d.frontSymmetry){let flipped=canvas(im.width,im.height),cc=flipped.getContext('2d');cc.translate(im.width,0);cc.scale(-1,1);cc.drawImage(im,0,0);im=flipped;}function paint(points){for(let i=0;i<triangles.length;i+=3){let ids=triangles.slice(i,i+3);triangle(ctx,im,ids.flatMap(k=>points.slice(k*2,k*2+2)),ids.flatMap(k=>uv.slice(k*2,k*2+2)));}}paint(xy);if(a.mirror)paint(xy.map((v,i)=>i%2?v:-v));
 if(cloth&&a.fringe){ctx.strokeStyle=a.fringeColor;ctx.lineWidth=.6*scale;for(let x=0;x<=n;x++){let k=(x*(n+1)+n)*2;ctx.beginPath();ctx.moveTo(xy[k],xy[k+1]);ctx.lineTo(xy[k]+Math.sin(x*7)*scale,xy[k+1]+a.fringeLength*(.55+(x*37%13)/20)*scale);ctx.stroke();if(a.mirror){ctx.beginPath();ctx.moveTo(-xy[k],xy[k+1]);ctx.lineTo(-xy[k]-Math.sin(x*7)*scale,xy[k+1]+a.fringeLength*(.55+(x*37%13)/20)*scale);ctx.stroke();}}}
 });
 }
 if(typeof pearlAccessoriesPreview==='function')pearlAccessoriesPreview(ctx,d,anchors,queue);
}


