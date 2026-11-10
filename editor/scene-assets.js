'use strict';
(root=>{
 const SCHEMA='moreiterators.export-scenes.v1';
 const kinds={select_menu_scene:'角色选择',select_menu_scene_ascended:'升天后选择',sleep_scene:'休眠',death_scene:'死亡',starve_scene:'饥饿'};
 const shaders=['Basic','Normal','Lighten','LightEdges','Rain','Overlay','SoftLight','Multiply'];
 const clone=value=>JSON.parse(JSON.stringify(value));
 const text=value=>root.MI18n?.text(value)??value;
 const fresh=kind=>({kind,images:[],idle_depths:[2.8]});
 const dimensions=(image,size)=>({width:size.width,height:image.depth!==-1&&!['Basic','Rain'].includes(image.shader)?size.height/2:size.height});
 function previewLayers(scene,camera={x:0,y:0},flat=false){
  const flatOnly=flat&&scene.images.some(image=>image.flatmode);
  const offset=scene.kind.startsWith('select_menu_scene')?(scene.select_menu_pos||[0,0]):[0,0];
  return scene.images.map((image,index)=>({image,index,x:image.pos[0]+offset[0]-(image.depth===-1?0:camera.x*80/image.depth),y:image.pos[1]+offset[1]-(image.depth===-1?0:camera.y*80/image.depth)})).filter(item=>!!item.image.flatmode===flatOnly);
 }
 function moveLayer(scene,index,direction){const next=index+direction;if(next<0||next>=scene.images.length)return index;[scene.images[index],scene.images[next]]=[scene.images[next],scene.images[index]];return next;}
 const fileData=file=>new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(Error(text('无法读取图片')));reader.readAsDataURL(file);});
 const safePath=value=>typeof value==='string'&&value.length>0&&!value.includes('\\')&&!value.startsWith('/')&&!value.split('/').some(p=>!p||p==='.'||p==='..'||/[<>:"|?*\u0000-\u001f]/.test(p));
 const pngBytes=uri=>Math.max(0,((uri?.split(',')[1]?.length||0)*3/4)-(uri?.endsWith('==')?2:uri?.endsWith('=')?1:0));
 const totalBytes=values=>values.reduce((total,scene)=>total+scene.images.reduce((sum,image)=>sum+pngBytes(image.png),0),0);
 function checkScenes(values){
  if(!Array.isArray(values)||values.length>5)throw Error(text('场景配置格式无效'));const used=new Set();
  for(const scene of values){
   if(!Object.hasOwn(kinds,scene.kind)||used.has(scene.kind)||!Array.isArray(scene.images)||!scene.images.length||scene.images.length>32)throw Error(text('场景用途无效或重复'));used.add(scene.kind);
   if(!Array.isArray(scene.idle_depths)||!scene.idle_depths.length||scene.idle_depths.some(n=>!Number.isFinite(n)||n<.1||n>50))throw Error(text('请设置场景聚焦深度'));
   for(const key of ['glow_pos','mark_pos','select_menu_pos'])if(Object.hasOwn(scene,key)&&(!Array.isArray(scene[key])||scene[key].length!==2||scene[key].some(n=>!Number.isFinite(n)||Math.abs(n)>8192)))throw Error(text('场景位置必须包含 X 和 Y'));
   if(Object.hasOwn(scene,'slugcat_depth')&&(!Number.isFinite(scene.slugcat_depth)||scene.slugcat_depth<.1||scene.slugcat_depth>50))throw Error(text('场景数值超出范围'));
   if(Object.hasOwn(scene,'dream_override')&&typeof scene.dream_override!=='boolean')throw Error(text('场景梦境设置无效'));
   const names=new Set();for(const image of scene.images){if(!safePath(image.name)||names.has(image.name.toLowerCase())||!Array.isArray(image.pos)||image.pos.length!==2||image.pos.some(n=>!Number.isFinite(n)||Math.abs(n)>8192)||!Number.isFinite(image.depth)||image.depth!==-1&&(image.depth<.1||image.depth>50)||!shaders.includes(image.shader)||typeof image.flatmode!=='boolean'||typeof image.png!=='string'||!image.png.startsWith('data:image/png;base64,'))throw Error(text('场景图层格式无效'));names.add(image.name.toLowerCase());if(pngBytes(image.png)>12*1024*1024)throw Error(text('场景图层需要 PNG 图片，最大 12 MB'));}
  }
  if(totalBytes(values)>64*1024*1024)throw Error(text('场景图片总大小超过限制'));return values;
 }
 async function parseSceneFiles(files,currentKind='select_menu_scene'){
  const documents=[],assets=new Map();let bytes=0;
  for(const file of files){
   const name=(file.webkitRelativePath||file.name).replaceAll('\\','/');if(!safePath(name))throw Error(text('场景图片路径无效'));
   bytes+=file.size;if(bytes>64*1024*1024)throw Error(text('场景图片总大小超过限制'));
   if(/\.json$/i.test(name)){if(file.size>16*1024*1024)throw Error(text('场景配置格式无效'));documents.push(JSON.parse((await file.text()).replace(/^\uFEFF/,'')));}
   else if(/\.png$/i.test(name)){if(file.size>12*1024*1024)throw Error(text('场景图层需要 PNG 图片，最大 12 MB'));const key=name.toLowerCase();if(assets.has(key))throw Error(text('场景 PNG 文件名重复'));assets.set(key,await readPNG(file));}
  }
  const editable=documents.find(doc=>doc.schema===SCHEMA);if(editable)return checkScenes(clone(editable.scenes));
  const scenes=documents.filter(doc=>Array.isArray(doc.images)),bindings=new Map();
  for(const doc of documents)for(const kind of Object.keys(kinds))if(doc.features?.[kind])bindings.set(doc.features[kind],kind);
  if(!scenes.length)throw Error(text('请同时选择场景 JSON 和 PNG'));
  const found=[];
  for(const doc of scenes){
   const kind=bindings.get(doc.id)||Object.keys(kinds).find(k=>String(doc.id).endsWith('_'+k))||(scenes.length===1?currentKind:null);
   if(!kind||found.some(scene=>scene.kind===kind))throw Error(text('场景用途无效或重复'));
   const scene={kind,images:[],idle_depths:clone(doc.idle_depths??[])};
   for(const key of ['glow_pos','mark_pos','select_menu_pos','slugcat_depth','dream_override'])if(Object.hasOwn(doc,key))scene[key]=clone(doc[key]);
   for(const layer of doc.images){
    if(!safePath(layer.name)||(doc.scene_folder&&!safePath(doc.scene_folder)))throw Error(text('场景图片路径无效'));
    const full=((doc.scene_folder?doc.scene_folder+'/':'')+layer.name+'.png').toLowerCase(),short=(layer.name+'.png').toLowerCase();
    let matches=[...assets].filter(([path])=>path===full||path.endsWith('/'+full));if(!matches.length)matches=[...assets].filter(([path])=>path===short||path.endsWith('/'+short));
    if(matches.length!==1)throw Error(text('缺少图片或存在同名图片：')+layer.name+'.png');
    scene.images.push({name:layer.name,png:matches[0][1],pos:clone(layer.pos),depth:layer.depth??-1,shader:layer.shader??'Normal',flatmode:layer.flatmode??false});
   }
   found.push(scene);
  }
  return checkScenes(found);
 }
 let node,options={},scenes={},kind='select_menu_scene',selected=-1,enabled=true,cover='',coverImage=null,coverZoom=1,coverX=.5,coverY=.5;
 let view,canvas,list,fields,status,kindInput,flatInput,coverBox,coverCanvas,coverRange,sizeLabel,camera={x:0,y:0},drag=null,raf=0,generation=0;
 const imageCache=new Map();
 function current(){return scenes[kind]||(scenes[kind]=fresh(kind));}
 function element(tag,attrs={},label){const result=document.createElement(tag);for(const [key,value] of Object.entries(attrs)){if(key==='class')result.className=value;else if(key==='type')result.type=value;else result.setAttribute(key,value);}if(label!==undefined)result.textContent=text(label);return result;}
 function button(label,handler){const result=element('button',{type:'button'},label);result.onclick=handler;return result;}
 function changed(){options.onChange?.();schedule();}
 function error(cause){status.textContent=cause.message||String(cause);}
 const run=fn=>async event=>{status.textContent='';try{await fn(event);}catch(cause){error(cause);}};
 function input(label,value,apply,{type='number',step='any',min,max}={}){const wrap=element('label',{},label),control=element('input',{type});control.value=value;if(type==='number'){control.step=step;if(min!==undefined)control.min=min;if(max!==undefined)control.max=max;}control.onchange=run(()=>{const result=type==='number'?Number(control.value):control.value;if(type==='number'&&(!Number.isFinite(result)||control.value===''))throw Error(text('场景数值超出范围'));apply(result);changed();});wrap.append(control);return wrap;}
 function choice(label,value,values,apply){const wrap=element('label',{},label),control=element('select');for(const [key,title] of values){const option=element('option',{value:key},title);control.append(option);}control.value=value;control.onchange=()=>{apply(control.value);changed();};wrap.append(control);return wrap;}
 function imageFor(uri){if(imageCache.has(uri))return imageCache.get(uri);const image=new Image();const token=generation;image.onload=()=>{if(token===generation)schedule();};image.onerror=()=>error(Error(text('无法读取图片')));image.src=uri;imageCache.set(uri,image);return image;}
 function schedule(){if(!canvas||raf)return;raf=requestAnimationFrame(()=>{raf=0;draw();});}
 function draw(){
  const context=canvas.getContext('2d');context.clearRect(0,0,1366,768);context.fillStyle='#171717';context.fillRect(0,0,1366,768);
  for(const item of previewLayers(current(),camera,flatInput.checked)){
   const image=imageFor(item.image.png);if(!image.complete||!image.naturalWidth)continue;
   const size=dimensions(item.image,{width:image.naturalWidth,height:image.naturalHeight}),top=768-item.y-size.height;
   context.drawImage(image,0,0,size.width,size.height,item.x,top,size.width,size.height);
   if(item.index===selected){context.save();context.strokeStyle='#ddd';context.lineWidth=2;context.setLineDash([8,6]);context.strokeRect(item.x,top,size.width,size.height);context.restore();}
  }
 }
 function drawFields(){
  fields.replaceChildren();const scene=current(),image=scene.images[selected];if(!image)return;
  const row=element('div',{class:'mi-scene-fields'});
  row.append(input('图层名称',image.name,v=>{image.name=v;drawList();},{type:'text'}),input('横向',image.pos[0],v=>image.pos[0]=v),input('纵向',image.pos[1],v=>image.pos[1]=v),input('深度',image.depth,v=>{if(v!==-1&&(v<.1||v>50))throw Error(text('深度使用 -1 或 0.1 至 50'));image.depth=v;}));
  row.append(choice('着色器',image.shader,shaders.map(s=>[s,s]),v=>image.shader=v));
  const flat=element('label',{class:'mi-scene-check'}),check=element('input',{type:'checkbox'});check.checked=image.flatmode;check.onchange=()=>{image.flatmode=check.checked;changed();};flat.append(check,element('span',{},'仅平面模式'));row.append(flat);
  const replaceFile=element('input',{type:'file',accept:'image/png',hidden:''});replaceFile.onchange=run(async()=>{const file=replaceFile.files[0];if(!file)return;image.png=await readPNG(file);changed();replaceFile.value='';});
  const actions=element('div',{class:'mi-scene-actions'});actions.append(button('替换图片',()=>replaceFile.click()),button('前移',()=>{selected=moveLayer(scene,selected,1);drawList();drawFields();changed();}),button('后移',()=>{selected=moveLayer(scene,selected,-1);drawList();drawFields();changed();}),button('删除图层',()=>{scene.images.splice(selected,1);selected=Math.min(selected,scene.images.length-1);render();changed();}),replaceFile);
  actions.children[1].disabled=selected===scene.images.length-1;actions.children[2].disabled=selected===0;
  fields.append(row,actions);
 }
 function drawList(){list.replaceChildren();current().images.forEach((image,index)=>{const entry=button('',()=>{selected=index;drawList();drawFields();schedule();});entry.textContent=image.name;entry.className='mi-scene-layer'+(index===selected?' selected':'');entry.setAttribute('aria-pressed',String(index===selected));entry.setAttribute('data-i18n-content','');list.prepend(entry);});}
 function render(){drawList();drawFields();if(sizeLabel)sizeLabel.textContent=(totalBytes(Object.values(scenes))/1024/1024).toFixed(1)+' / 64 MB';schedule();}
 async function readPNG(file){if(file.size>12*1024*1024)throw Error(text('场景图层需要 PNG 图片，最大 12 MB'));const signature=new Uint8Array(await file.slice(0,8).arrayBuffer());if(signature.length!==8||[137,80,78,71,13,10,26,10].some((value,index)=>signature[index]!==value))throw Error(text('场景图层需要 PNG 图片，最大 12 MB'));const uri=await fileData(new Blob([file],{type:'image/png'}));const image=new Image();image.src=uri;await image.decode();if(image.naturalWidth>4096||image.naturalHeight>4096)throw Error(text('场景 PNG 无效或尺寸超过 4096'));return uri;}
 async function addFiles(files){
  const scene=current();if(scene.images.length+files.length>32)throw Error(text('每个场景需要 1 至 32 个图层'));
  const added=[];for(const file of files){const png=await readPNG(file);let name=file.name.replace(/\.png$/i,'').replace(/[<>:"|?*\\/]/g,'_')||'layer',base=name,n=2;while([...scene.images,...added].some(image=>image.name.toLowerCase()===name.toLowerCase()))name=base+'_'+n++;added.push({name,png,pos:[0,0],depth:2.8,shader:'Basic',flatmode:false});}
  if(totalBytes(Object.values(scenes))+totalBytes([{images:added}])>64*1024*1024)throw Error(text('场景图片总大小超过限制'));scene.images.push(...added);selected=scene.images.length-1;render();changed();
 }
 async function importFiles(files){const imported=await parseSceneFiles(files,kind),next={...scenes};for(const scene of imported)next[scene.kind]=scene;checkScenes(Object.values(next).filter(scene=>scene.images.length));scenes=next;kind=imported[0].kind;kindInput.value=kind;selected=current().images.length-1;refreshAdvanced();render();changed();}
 function advanced(){
  const details=element('details',{class:'mi-scene-advanced'});details.append(element('summary',{},'场景设置'));const body=element('div',{class:'mi-scene-fields'});
  body.append(input('聚焦深度',current().idle_depths.join(', '),v=>{const values=v.split(/[,，\s]+/).filter(Boolean).map(Number);if(!values.length||values.some(n=>!Number.isFinite(n)||n<.1||n>50))throw Error(text('请设置场景聚焦深度'));current().idle_depths=values;},{type:'text'}));
  if(kind.startsWith('select_menu_scene')){
   for(const [key,label] of [['select_menu_pos','选角偏移'],['glow_pos','柔光位置'],['mark_pos','印记位置']]){
    const wrap=element('div',{class:'mi-scene-position'}),check=element('input',{type:'checkbox'}),title=element('label',{class:'mi-scene-check'});check.checked=Object.hasOwn(current(),key);title.append(check,element('span',{},label));wrap.append(title);
    const controls=element('div',{class:'mi-scene-pair'}),point=[...(current()[key]||[0,0])];controls.hidden=!check.checked;
    controls.append(input('横向',point[0],v=>{point[0]=v;current()[key][0]=v;}),input('纵向',point[1],v=>{point[1]=v;current()[key][1]=v;}));check.onchange=()=>{if(check.checked)current()[key]=[...point];else delete current()[key];controls.hidden=!check.checked;changed();};wrap.append(controls);body.append(wrap);
   }
   body.append(input('角色深度',current().slugcat_depth??2.8,v=>{if(v<.1||v>50)throw Error(text('场景数值超出范围'));current().slugcat_depth=v;}));
  }
  details.append(body);return details;
 }
 function drawCover(target=coverCanvas){if(!target||!coverImage)return;const c=target.getContext('2d');c.clearRect(0,0,target.width,target.height);const side=Math.min(coverImage.naturalWidth,coverImage.naturalHeight)/coverZoom;const x=(coverImage.naturalWidth-side)*coverX,y=(coverImage.naturalHeight-side)*coverY;c.drawImage(coverImage,x,y,side,side,0,0,target.width,target.height);}
 function setCover(value){cover=value||'';coverImage=null;if(!coverBox)return;coverBox.hidden=!cover;coverZoom=1;coverX=coverY=.5;coverRange.value=1;if(!cover)return;const image=new Image(),expected=cover;image.onload=()=>{if(cover!==expected)return;coverImage=image;drawCover();};image.onerror=()=>error(Error(text('无法读取图片')));image.src=cover;}
 function mount(container,callbacks={}){
  node=container;options=callbacks;node.replaceChildren();node.classList.add('mi-export-scene');
  status=element('div',{class:'mi-scene-error',role:'status'});
  coverBox=element('details',{class:'mi-cover-edit',hidden:''});coverBox.append(element('summary',{},'裁剪封面'));coverCanvas=element('canvas',{width:512,height:512,'aria-label':text('封面预览')});coverRange=element('input',{type:'range',min:1,max:5,step:.01,'aria-label':text('缩放')});coverRange.value=1;coverRange.oninput=()=>{coverZoom=Number(coverRange.value);drawCover();};
  let coverDrag=null;coverCanvas.onpointerdown=e=>{coverDrag={x:e.clientX,y:e.clientY,cx:coverX,cy:coverY};coverCanvas.setPointerCapture(e.pointerId);};coverCanvas.onpointermove=e=>{if(!coverDrag||!coverImage)return;const rect=coverCanvas.getBoundingClientRect(),side=Math.min(coverImage.naturalWidth,coverImage.naturalHeight)/coverZoom;coverX=Math.max(0,Math.min(1,coverDrag.cx-(e.clientX-coverDrag.x)/rect.width*side/Math.max(1,coverImage.naturalWidth-side)));coverY=Math.max(0,Math.min(1,coverDrag.cy-(e.clientY-coverDrag.y)/rect.height*side/Math.max(1,coverImage.naturalHeight-side)));drawCover();};coverCanvas.onpointerup=coverCanvas.onpointercancel=()=>coverDrag=null;
  const coverTools=element('div',{class:'mi-scene-actions'});coverTools.append(coverRange,button('应用裁剪',()=>{if(!coverImage)return;const output=document.createElement('canvas');output.width=output.height=Math.min(1024,Math.min(coverImage.naturalWidth,coverImage.naturalHeight));drawCover(output);const result=output.toDataURL('image/png');options.onCoverChange?.(result);setCover(result);changed();}),button('重置裁剪',()=>{coverZoom=1;coverX=coverY=.5;coverRange.value=1;drawCover();}));coverBox.append(coverCanvas,coverTools);
  view=element('div',{class:'mi-scene-editor'});const toolbar=element('div',{class:'mi-scene-toolbar'});kindInput=element('select',{'aria-label':text('场景用途')});for(const [value,title] of Object.entries(kinds))kindInput.append(element('option',{value},title));kindInput.onchange=()=>{kind=kindInput.value;selected=current().images.length-1;camera={x:0,y:0};refreshAdvanced();render();};
  const add=element('input',{type:'file',accept:'image/png',multiple:'',hidden:''});add.onchange=run(async()=>{await addFiles([...add.files]);add.value='';});const imports=element('input',{type:'file',accept:'.json,image/png',multiple:'',hidden:''});imports.onchange=run(async()=>{await importFiles([...imports.files]);imports.value='';});const folder=element('input',{type:'file',webkitdirectory:'',multiple:'',hidden:''});folder.onchange=run(async()=>{await importFiles([...folder.files]);folder.value='';});
  toolbar.append(kindInput,button('导入场景',()=>imports.click()),button('导入文件夹',()=>folder.click()),imports,folder);
  canvas=element('canvas',{width:1366,height:768,'aria-label':text('场景预览')});canvas.onpointerdown=e=>{const image=current().images[selected];if(!image)return;drag={x:e.clientX,y:e.clientY,pos:[...image.pos],image};canvas.setPointerCapture(e.pointerId);};canvas.onpointermove=e=>{const rect=canvas.getBoundingClientRect();if(drag){drag.image.pos=[Math.round(drag.pos[0]+(e.clientX-drag.x)*1366/rect.width),Math.round(drag.pos[1]-(e.clientY-drag.y)*768/rect.height)];schedule();}else{camera={x:((e.clientX-rect.left)/rect.width-.5)*2,y:(.5-(e.clientY-rect.top)/rect.height)*2};schedule();}};canvas.onpointerup=canvas.onpointercancel=()=>{if(drag){drag=null;drawFields();changed();}};canvas.onpointerleave=()=>{if(!drag){camera={x:0,y:0};schedule();}};
  const previewBar=element('div',{class:'mi-scene-preview-bar'});flatInput=element('input',{type:'checkbox'});flatInput.onchange=schedule;const flatLabel=element('label',{class:'mi-scene-check'});flatLabel.append(flatInput,element('span',{},'平面模式'));sizeLabel=element('span',{'data-i18n-content':'',title:text('单张 PNG 最大 12 MB')});previewBar.append(element('span',{},'布局与视差预览'),sizeLabel,flatLabel);
  list=element('div',{class:'mi-scene-layers'});fields=element('div',{class:'mi-scene-properties'});const edit=element('div',{class:'mi-scene-edit-grid'});edit.append(list,fields);
  const layers=element('section',{class:'mi-scene-layer-editor'}),heading=element('div',{class:'mi-scene-layer-heading'});heading.append(element('h3',{'data-i18n':'sceneHierarchy.layers'},'图层'),button('添加图层',()=>add.click()));layers.append(heading,edit,add);
  view.append(toolbar,element('div',{class:'mi-scene-advanced-host'}),canvas,previewBar,layers);node.append(coverBox,view,status);setCover(cover);refreshAdvanced();render();setEnabled(enabled);
 }
 function refreshAdvanced(){const host=view?.querySelector('.mi-scene-advanced-host');if(host){const open=host.querySelector('details')?.open??false;const settings=advanced();settings.open=open;host.replaceChildren(settings);}}
 function reset(value=null,thumbnail=''){generation++;imageCache.clear();scenes={};for(const scene of value?.scenes||[])if(Object.hasOwn(kinds,scene.kind))scenes[scene.kind]=clone(scene);kind=Object.keys(scenes)[0]||'select_menu_scene';selected=current().images.length-1;camera={x:0,y:0};if(kindInput)kindInput.value=kind;if(status)status.textContent='';setCover(thumbnail);if(view){refreshAdvanced();render();}}
 function serialize(){const values=Object.keys(kinds).map(key=>scenes[key]).filter(scene=>scene?.images.length);return values.length?{schema:SCHEMA,scenes:clone(values)}:null;}
 function setEnabled(value){enabled=!!value;if(view)view.hidden=!enabled;}
 const api={mount,reset,serialize,setCover,setEnabled,parseSceneFiles,previewLayers,dimensions,moveLayer,importFiles,addFiles};root.MIExportScene=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(globalThis);
