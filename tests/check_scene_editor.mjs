import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {fileURLToPath,pathToFileURL} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),out=path.resolve(root,'../evidence/scene-assets-20261109/browser');
fs.mkdirSync(out,{recursive:true});
const html=`<!doctype html><meta charset="utf-8"><style>body{background:#121212;color:#ddd;font:14px sans-serif;margin:20px}main{max-width:760px;margin:auto}button,input,select{background:#171717;border:1px solid #555;border-radius:5px;color:#ddd}button{cursor:pointer}button:disabled{opacity:.4}h2{font-size:17px}summary{cursor:pointer}input[type=checkbox]{accent-color:#ccc}</style><link rel="stylesheet" href="${pathToFileURL(path.join(root,'editor/scene-assets.css'))}"><main><h2>封面与场景</h2><div id="host"></div></main><script src="${pathToFileURL(path.join(root,'editor/scene-assets.js'))}"></script><script>
const api=MIExportScene,host=document.querySelector('#host');let changes=0,cropped=null;
api.mount(host,{onChange:()=>changes++,onCoverChange:value=>cropped=value});
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const assert=(condition,message)=>{if(!condition)throw Error(message);checks.push(message);};const checks=[];
const button=label=>[...host.querySelectorAll('button')].find(el=>el.textContent===label);
function fixturePNG(name,color,width=100,height=80){const canvas=document.createElement('canvas');canvas.width=width;canvas.height=height;const c=canvas.getContext('2d');c.fillStyle=color;c.fillRect(0,0,width,height);return canvas.toDataURL('image/png');}
async function pngFile(name,uri,relative){const file=new File([await(await fetch(uri)).blob()],name,{type:'image/png'});if(relative)Object.defineProperty(file,'webkitRelativePath',{value:relative});return file;}
function jsonFile(name,value){return new File([JSON.stringify(value)],name,{type:'application/json'});}
function field(label){return [...host.querySelectorAll('.mi-scene-fields label')].find(el=>el.firstChild?.textContent===label)?.querySelector('input,select');}
function change(el,value){el.value=value;el.dispatchEvent(new Event('change',{bubbles:true}));}
window.runSceneTests=async()=>{
 const red=fixturePNG('red','#c44'),green=fixturePNG('green','#4c6',100,160),blue=fixturePNG('blue','#46c',130,80);
 const native={id:'Imported',scene_folder:'scenes/demo',idle_depths:[2.8,3.5],select_menu_pos:[-10,100],glow_pos:[730,335],images:[{name:'red',pos:[100,30],depth:4,shader:'Basic'},{name:'green',pos:[110,40],depth:2,shader:'Normal'}]};
 const files=[jsonFile('scene.json',native),await pngFile('red.png',red,'demo/scenes/demo/red.png'),await pngFile('green.png',green,'demo/scenes/demo/green.png')];
 await api.importFiles(files);let scene=api.serialize().scenes[0];assert(scene.images.map(x=>x.name).join(',')==='red,green','Native import preserves layer order');assert(scene.images[0].pos.join(',')==='100,30'&&scene.select_menu_pos.join(',')==='-10,100','Native import preserves bottom-left position and selection offset');
 assert(api.previewLayers(scene,{x:1,y:-1})[0].x===70&&api.previewLayers(scene,{x:1,y:-1})[0].y===150,'Preview uses native camera offset and depth');
 assert(api.dimensions(scene.images[1],{width:100,height:160}).height===80,'Native depth texture preview uses color half');
 assert(api.previewLayers(scene,{},true).length===2,'Flat mode falls back to normal layers when no flat-only layer exists');
 const sample=JSON.parse(JSON.stringify(scene));sample.images.push({...sample.images[0],name:'flat',depth:-1,flatmode:true});assert(api.previewLayers(sample,{x:0,y:0},true).map(x=>x.image.name).join(',')==='flat','Flat mode selects explicit flat-only layer');assert(api.previewLayers(sample,{x:0,y:0},false).length===2,'Regular mode excludes explicit flat-only layer');
 await wait(80);const canvas=host.querySelector('.mi-scene-editor>canvas'),rect=canvas.getBoundingClientRect();assert(Math.abs(rect.width/rect.height-1366/768)<.01,'Canvas CSS and pointer coordinate ratios match');
 const before=[...scene.images[1].pos];canvas.dispatchEvent(new PointerEvent('pointerdown',{clientX:rect.left+50,clientY:rect.top+50,pointerId:1}));canvas.dispatchEvent(new PointerEvent('pointermove',{clientX:rect.left+50+rect.width/1366*20,clientY:rect.top+50+rect.height/768*10,pointerId:1}));canvas.dispatchEvent(new PointerEvent('pointerup',{pointerId:1}));scene=api.serialize().scenes[0];assert(scene.images[1].pos[0]===before[0]+20&&scene.images[1].pos[1]===before[1]-10,'Canvas drag updates bottom-left coordinates');
 change(field('深度'),'4.5');assert(api.serialize().scenes[0].images[1].depth===4.5,'Depth edits save without reordering');button('后移').click();assert(api.serialize().scenes[0].images[0].name==='green','Layer ordering changes independently of depth');
 const replace=host.querySelector('.mi-scene-properties input[type=file]'),transfer=new DataTransfer();transfer.items.add(await pngFile('blue.png',blue));replace.files=transfer.files;replace.dispatchEvent(new Event('change'));await wait(50);assert(api.serialize().scenes[0].images[0].png===blue,'Replace PNG preserves layer and animation-independent fields');
 await api.addFiles([await pngFile('red.png',red)]);assert(api.serialize().scenes[0].images[2].name==='red_2','Added PNG avoids duplicate layer names');button('删除图层').click();assert(api.serialize().scenes[0].images.length===2,'Delete removes selected layer only');
 const saved=api.serialize();api.reset(null);assert(api.serialize()===null,'Reset clears export draft only');api.reset(saved);assert(JSON.stringify(api.serialize())===JSON.stringify(saved),'Scene draft reset round-trip preserves settings');
 const original=JSON.stringify(api.serialize());let rejected=false;try{await api.importFiles([jsonFile('scene.json',native)]);}catch{rejected=true;}assert(rejected&&JSON.stringify(api.serialize())===original,'Missing PNG import leaves prior draft intact');
 rejected=false;try{await api.parseSceneFiles([jsonFile('bad.json',{...native,images:[{name:'../bad',pos:[0,0]}]})]);}catch{rejected=true;}assert(rejected,'Traversal scene asset path is rejected');
 const allKinds=['select_menu_scene','select_menu_scene_ascended','sleep_scene','death_scene','starve_scene'];const exported={features:{}},allFiles=[];for(const kind of allKinds){const id='MI_abc_'+kind;exported.features[kind]=id;allFiles.push(jsonFile(id+'.json',{id,scene_folder:'scenes/'+kind,idle_depths:[2.8],images:[{name:'red',pos:[0,0],depth:2.8,shader:'Basic'}]}),await pngFile('red.png',red,'mod/scenes/'+kind+'/red.png'));}allFiles.push(jsonFile('slugcat.json',exported));const all=await api.parseSceneFiles(allFiles);assert(all.length===5&&all.map(s=>s.kind).join(',')===allKinds.join(','),'Native campaign bindings import all five scene kinds');
 api.setEnabled(false);assert(host.querySelector('.mi-scene-editor').hidden,'Scene controls hide for other export formats');api.setEnabled(true);
 const cover=fixturePNG('cover','#a4c',1200,800);api.setCover(cover);await wait(40);host.querySelector('.mi-cover-edit').open=true;const range=host.querySelector('input[type=range]');range.value=2;range.dispatchEvent(new Event('input'));button('应用裁剪').click();await wait(50);assert(cropped&&cropped.startsWith('data:image/png;base64,'),'Cover crop returns PNG through existing cover callback');const image=new Image();image.src=cropped;await image.decode();assert(image.width===800&&image.height===800,'Cover crop keeps source resolution up to 1024');
 api.reset(saved,cover);host.querySelector('.mi-cover-edit').open=false;await wait(80);assert(changes>5,'Editing notifies export persistence owner');return {checks:checks.length,passed:checks,scene:api.serialize()};
};
</script>`;
const target=path.join(out,'preview.html');fs.writeFileSync(target,html);
const profile=fs.mkdtempSync(path.join(out,'profile-'));const browser=spawn('C:/Program Files/Google/Chrome/Application/chrome.exe',['--headless','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-background-networking','--remote-debugging-address=127.0.0.1','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:['ignore','ignore','pipe']});
let stderr='',socket;browser.stderr.on('data',chunk=>stderr+=chunk);const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
try{
 const file=path.join(profile,'DevToolsActivePort');for(let i=0;i<200&&!fs.existsSync(file);i++)await sleep(50);if(!fs.existsSync(file))throw Error(stderr);
 const port=fs.readFileSync(file,'utf8').split(/\r?\n/)[0],pages=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();socket=new WebSocket(pages.find(page=>page.type==='page').webSocketDebuggerUrl);await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
 let serial=0;const pending=new Map();socket.onmessage=event=>{const data=JSON.parse(event.data);if(data.id){const item=pending.get(data.id);pending.delete(data.id);if(data.error)item.reject(Error(JSON.stringify(data.error)));else item.resolve(data.result);}};
 const call=(method,params={})=>new Promise((resolve,reject)=>{const id=++serial;pending.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params}));});
 const evaluate=async expression=>{const result=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(result.exceptionDetails)throw Error(result.exceptionDetails.exception?.description||JSON.stringify(result.exceptionDetails));return result.result.value;};
 await call('Page.enable');await call('Emulation.setDeviceMetricsOverride',{width:1100,height:1000,deviceScaleFactor:1,mobile:false});await call('Page.navigate',{url:pathToFileURL(target).href});for(let i=0;i<100&&!(await evaluate('typeof window.runSceneTests==="function"'));i++)await sleep(30);
 const result=await evaluate('runSceneTests()');delete result.scene;fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(result,null,2));
 for(const width of [1100,500]){await call('Emulation.setDeviceMetricsOverride',{width,height:1100,deviceScaleFactor:1,mobile:false});await sleep(100);const shot=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});fs.writeFileSync(path.join(out,'preview-'+width+'.png'),Buffer.from(shot.data,'base64'));const overflow=await evaluate('document.documentElement.scrollWidth>innerWidth');if(overflow)throw Error('Horizontal overflow at width '+width);}
 console.log(JSON.stringify(result,null,2));
}finally{socket?.close();browser.kill();await sleep(400);if(path.dirname(fs.realpathSync(profile))===fs.realpathSync(out))try{fs.rmSync(profile,{recursive:true,force:true});}catch{}}
