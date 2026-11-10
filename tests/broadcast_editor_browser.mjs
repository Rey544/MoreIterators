                                                                       
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import http from 'node:http';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const testRoot=path.dirname(fileURLToPath(import.meta.url)),editor=path.resolve(testRoot,'../editor');
const output=path.resolve(testRoot,'../../evidence/broadcast-exchange-20261109');
const chrome=process.env.MI_TEST_CHROME||'C:/Program Files/Google/Chrome/Application/chrome.exe';
const temporary=fs.mkdtempSync(path.join(os.tmpdir(),'mi-broadcast-ui-')),profile=path.join(temporary,'profile'),downloads=path.join(temporary,'downloads');
fs.mkdirSync(output,{recursive:true});fs.mkdirSync(downloads);
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms)),clone=value=>structuredClone(value);
const style={font:'normal',size:1,speed:1,hold:2.5};
const fixture=(id,name,color,uid)=>({schema:'moreiterators.broadcast.v1',id,name,uid,revision:1,region:'SU',room:'SU_A01',x:.5,y:.5,style:clone(style),appearance:{baseColor:color},useCharacterColors:true,speakers:[{name:'Moon',aliases:['月'],color:'#44cc88'}],pages:[{lines:[{text:'Moon: 这里是隔离测试广播。',color:'#ffffff',...style},{text:'文本和图标分别保留各自的颜色。',color:'#ffffff',...style}]},{lines:[{text:'Moon: 第二页。',color:'#ffffff',...style}]}]});
let records=[fixture('B01','测试广播','#c9cccf','1'.repeat(32)),fixture('B02','另一广播','#bb7744','2'.repeat(32))],holdValidation=false,pendingValidations=[],savedPayloads=[],requests=[],checks=0;
const errors=[],downloadEvents=[],layout=[];
const check=(value,message)=>{checks++;if(!value)throw Error(message);};
const respond=(res,value,status=200)=>{res.writeHead(status,{'content-type':'application/json; charset=utf-8'});res.end(JSON.stringify(value));};
const staticTypes={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json; charset=utf-8','.woff2':'font/woff2','.png':'image/png','.svg':'image/svg+xml'};
const allowedScripts=new Set(['/i18n.js','/studio-undo.js','/broadcast-icons.js','/broadcast-exchange.js','/broadcasts.js']);
const server=http.createServer(async(req,res)=>{try{
 const url=new URL(req.url,'http://fixture.invalid');requests.push({method:req.method,path:url.pathname});
 if(url.pathname.startsWith('/api/')){
  let body='';for await(const chunk of req)body+=chunk;const value=body?JSON.parse(body):null;
  if(url.pathname==='/api/broadcasts')return respond(res,records);
  if(url.pathname==='/api/broadcast-rooms')return respond(res,[{region:'SU',room:'SU_A01'},{region:'SU',room:'SU_A02'}]);
  if(url.pathname==='/api/broadcast-room')return respond(res,{width:100,height:50,solids:[[0,0],[1,0],[2,0],[3,0],[4,0],[5,0]],cameras:[[0,0]]});
  if(url.pathname==='/api/broadcast-default')return respond(res,{...fixture('B03','新建广播','#c9cccf','3'.repeat(32)),revision:0});
  if(url.pathname==='/api/broadcast-save'){
   savedPayloads.push(clone(value));const stored={...value,revision:value.revision+1};const index=records.findIndex(p=>p.uid===stored.uid);if(index<0)records.push(clone(stored));else records[index]=clone(stored);return respond(res,{project:stored});
  }
  if(url.pathname==='/api/broadcast-import')return respond(res,{projects:value.projects||[value]});
  if(url.pathname==='/api/broadcast-validate'){
   if(holdValidation)return pendingValidations.push({res,value});
   return respond(res,value);
  }
  errors.push('Unexpected API request: '+url.pathname);return respond(res,{error:'Unexpected isolated route'},404);
 }
 if(url.pathname==='/favicon.ico'){res.writeHead(204);return res.end();}
 const resource=url.pathname==='/'?'/broadcasts.html':decodeURIComponent(url.pathname),file=path.resolve(editor,'.'+resource);
 if(!file.startsWith(editor+path.sep)||!fs.existsSync(file)||!fs.statSync(file).isFile()){res.writeHead(404);return res.end();}
 let data=fs.readFileSync(file);
 if(resource==='/broadcasts.html')data=Buffer.from(data.toString('utf8').replace(/<script\b[^>]*src="([^"]+)"[^>]*><\/script>/g,(whole,src)=>allowedScripts.has(src)?whole:''));
 res.writeHead(200,{'content-type':staticTypes[path.extname(file)]||'application/octet-stream','cache-control':'no-store'});res.end(data);
}catch(error){errors.push(error.stack);respond(res,{error:error.message},500);}});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const origin='http://127.0.0.1:'+server.address().port;
const browser=spawn(chrome,['--headless','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-background-timer-throttling','--remote-debugging-address=127.0.0.1','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:['ignore','ignore','pipe']});
let stderr='',socket;
browser.stderr.on('data',chunk=>stderr+=chunk);
try{
 const portFile=path.join(profile,'DevToolsActivePort');for(let i=0;i<200&&!fs.existsSync(portFile);i++)await sleep(50);if(!fs.existsSync(portFile))throw Error(stderr);
 const port=fs.readFileSync(portFile,'utf8').split(/\r?\n/)[0],pages=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();
 socket=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
 let serial=0;const pending=new Map();socket.onmessage=event=>{const data=JSON.parse(event.data);if(data.id){const item=pending.get(data.id);pending.delete(data.id);data.error?item.reject(Error(JSON.stringify(data.error))):item.resolve(data.result);}else if(data.method==='Runtime.exceptionThrown')errors.push(data.params.exceptionDetails.exception?.description||data.params.exceptionDetails.text);else if(data.method.startsWith('Browser.download'))downloadEvents.push({method:data.method,...data.params});};
 const call=(method,params={})=>new Promise((resolve,reject)=>{const id=++serial;pending.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params}));});
 const evaluate=async(expression)=>{const result=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(result.exceptionDetails)throw Error(result.exceptionDetails.exception?.description||JSON.stringify(result.exceptionDetails));return result.result.value;};
 const until=async(condition,label)=>{for(let i=0;i<200;i++){if(await condition())return;await sleep(15);}throw Error('Timed out: '+label);};
 const input=(selector,value,event='input')=>evaluate(`(()=>{const node=document.querySelector(${JSON.stringify(selector)});node.value=${JSON.stringify(value)};node.dispatchEvent(new Event(${JSON.stringify(event)},{bubbles:true}));})()`);
 const click=async selector=>{const box=await evaluate(`(()=>{const node=document.querySelector(${JSON.stringify(selector)});if(!node)throw Error('Missing click target');node.scrollIntoView({block:'center'});const r=node.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);await call('Input.dispatchMouseEvent',{type:'mouseMoved',...box});await call('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...box});await call('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...box});};
 const releaseValidation=()=>{for(const {res,value}of pendingValidations.splice(0))respond(res,value);holdValidation=false;};
 const fileInput=async(value,name)=>{const file=path.join(temporary,name);fs.writeFileSync(file,JSON.stringify(value));const {root}=await call('DOM.getDocument'),{nodeId}=await call('DOM.querySelector',{nodeId:root.nodeId,selector:'#file'});await call('DOM.setFileInputFiles',{nodeId,files:[file]});};
 const capture=async name=>{const image=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});const destination=path.join(output,name);fs.writeFileSync(destination,Buffer.from(image.data,'base64'));return destination;};
 await call('Runtime.enable');await call('Page.enable');await call('DOM.enable');await call('Browser.setDownloadBehavior',{behavior:'allow',downloadPath:downloads,eventsEnabled:true});
 await call('Emulation.setDeviceMetricsOverride',{width:1366,height:900,deviceScaleFactor:1,mobile:false});await call('Page.navigate',{url:origin+'/broadcasts.html?lang=zh-CN'});
 await until(()=>evaluate(`typeof project!=='undefined'&&!!project&&!loading&&document.querySelectorAll('.broadcast-card').length===2`),'initialization');
 await evaluate(`window.confirm=()=>true;window.__unhandled=[];window.addEventListener('unhandledrejection',event=>window.__unhandled.push(String(event.reason)));`);
 check(await evaluate(`!!MIUndo&&document.getElementById('iconColor').value==='#c9cccf'`),'Initial icon color or real undo unavailable');
 const colors=()=>evaluate(`(()=>{const sample=id=>{const c=typeof id==='string'?document.querySelector(id):id,bytes=c.getContext('2d').getImageData(0,0,c.width,c.height).data;for(let i=0;i<bytes.length;i+=4)if(bytes[i+3]===255)return Array.from(bytes.slice(i,i+4));return null;};return {editor:sample('#broadcastIcon'),card:sample('.broadcast-card[aria-current=true] canvas'),text:getComputedStyle(document.querySelector('#preview p')).color,speaker:document.querySelector('#speakers input[type=color]').value};})()`);
 const before=await colors();check(JSON.stringify(before.editor)==='[201,204,207,255]'&&JSON.stringify(before.card)===JSON.stringify(before.editor),'Native icon default pixels/card do not match');
 await input('#iconColor','#6a2fd4');await until(()=>evaluate('MIUndo.state.undo'),'color undo snapshot');const after=await colors();
 check(JSON.stringify(after.editor)==='[106,47,212,255]'&&JSON.stringify(after.card)===JSON.stringify(after.editor),'Changing icon color did not redraw editor and list icon');check(after.text===before.text&&after.speaker===before.speaker&&after.text==='rgb(68, 204, 136)','Icon color changed character/text color');
 check(await evaluate('MIUndo.undo()'),'Real MIUndo failed to undo icon color');await until(()=>evaluate(`document.getElementById('iconColor').value==='#c9cccf'`),'icon undo display');const undone=await colors();check(JSON.stringify(undone.editor)===JSON.stringify(before.editor)&&JSON.stringify(undone.card)===JSON.stringify(before.card),'Undo failed to redraw both icons');
 check(await evaluate('MIUndo.redo()'),'Real MIUndo failed to redo icon color');await until(()=>evaluate(`document.getElementById('iconColor').value==='#6a2fd4'`),'icon redo display');
 await input('#speakers input[type=color]','#1122cc');const speakerChanged=await colors();check(speakerChanged.text==='rgb(17, 34, 204)'&&JSON.stringify(speakerChanged.editor)==='[106,47,212,255]','Character color no longer changes independently of icon');
 await click('#save');await until(()=>savedPayloads.length===1,'save payload');await until(()=>evaluate('!saving'),'save completion');
 check(savedPayloads[0].appearance.baseColor==='#6a2fd4'&&savedPayloads[0].speakers[0].color==='#1122cc','Save payload lost icon or character color');check(savedPayloads[0].pages[0].lines[0].text===records[0].pages[0].lines[0].text,'Color edits altered authored text');
 async function exportFormat(format){
  await click('#broadcastMore summary');await click('#export');await until(()=>evaluate(`document.getElementById('exportPicker').open`),'export modal');await input('#exportFormat',format,'change');
  check(await evaluate(`document.getElementById('exchangeLimit').hidden===${format!=='rainoc'}`),'Export format explanation did not follow selection');const previous=downloadEvents.length;
  await click('#confirmExport');await until(()=>downloadEvents.slice(previous).some(e=>e.method==='Browser.downloadProgress'&&e.state==='completed'),'actual '+format+' download');
  const start=downloadEvents.slice(previous).find(e=>e.method==='Browser.downloadWillBegin'),file=path.join(downloads,start.suggestedFilename);await until(()=>fs.existsSync(file),'download file');check(start.url.startsWith('blob:'),'Export did not download its generated Blob');return {name:start.suggestedFilename,data:JSON.parse(fs.readFileSync(file,'utf8'))};
 }
 const mi=await exportFormat('mi');check(mi.name==='B01.json'&&mi.data.appearance.baseColor==='#6a2fd4'&&mi.data.pages.length===2&&mi.data.room==='SU_A01','MI JSON export lost editable settings');
 const rainoc=await exportFormat('rainoc'),rainocBroadcast=rainoc.data.project.documents.find(item=>item.kind==='broadcast'),rainocSpeaker=rainoc.data.project.documents.find(item=>item.kind==='character');
 check(rainoc.name==='B01-RainocTool.json'&&rainoc.data.format==='eoe-lore-project'&&rainocBroadcast.details.appearance.baseColor==='#6a2fd4','RainocTool JSON export lost document or icon color');check(rainocSpeaker.details.characterColor==='#1122cc'&&rainocBroadcast.content===mi.data.pages.flatMap(p=>p.lines.map(line=>line.text)).join('\n'),'RainocTool JSON export lost text/character color');
 const screenshots=[];
 for(const locale of ['zh-CN','en']){
  await evaluate(`MI18n.setLocale(${JSON.stringify(locale)},false)`);await sleep(60);
  for(const width of [1366,760,420]){
   await call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false});await evaluate('scrollTo(0,0)');await sleep(60);
   const sizes=await evaluate(`({viewport:innerWidth,scroll:document.documentElement.scrollWidth,body:document.body.scrollWidth,raw:/\b(?:broadcast\.(?:iconColor|editIconColor|export|exchangeLimit)|refine\.[a-z0-9]+)\b/.test(document.body.innerText),iconLabel:document.getElementById('iconColor').parentElement.textContent.trim(),broadcastName:document.getElementById('name').value})`);
   layout.push({locale,width,...sizes});check(sizes.scroll<=width&&sizes.body<=width,locale+' horizontal overflow at '+width+': '+JSON.stringify(sizes));check(!sizes.raw,'Raw localization key visible');check(sizes.iconLabel===(locale==='en'?'Document icon color':'文档图标颜色'),'New icon label did not translate');check(sizes.broadcastName==='测试广播','Language switch translated authored name');screenshots.push(await capture('broadcast-'+locale+'-'+width+'.png'));
  }
 }
 await call('Emulation.setDeviceMetricsOverride',{width:1366,height:900,deviceScaleFactor:1,mobile:false});await evaluate(`MI18n.setLocale('zh-CN',false)`);
 const single={...fixture('B03','导入单广播','#228855','4'.repeat(32)),revision:0};holdValidation=true;await fileInput(single,'single-mi.json');await until(()=>pendingValidations.length===1,'single import validation request');
 check(await evaluate(`document.getElementById('name').value==='测试广播'&&loading`),'Single import switched document before awaited validation');releaseValidation();await until(()=>evaluate(`document.getElementById('name').value==='导入单广播'&&!loading`),'single import finished');check(await evaluate(`project.appearance.baseColor==='#228855'&&dirty`),'Single validated import lost appearance/dirty state');
 const oneRainoc=clone(rainoc.data);oneRainoc.project.documents.find(item=>item.kind==='broadcast').title='导入 Rainoc 单广播';holdValidation=true;await fileInput(oneRainoc,'single-rainoc.json');await until(()=>pendingValidations.length===1,'single Rainoc validation');check(await evaluate(`document.getElementById('name').value==='导入单广播'`),'Single Rainoc import switched early');releaseValidation();await until(()=>evaluate(`document.getElementById('name').value==='导入 Rainoc 单广播'&&!loading`),'single Rainoc finished');
 const multiple=clone(rainoc.data),second=clone(rainocBroadcast);multiple.project.documents.find(item=>item.kind==='broadcast').title='选择第一广播';second.id='second-broadcast';second.title='选择第二广播';second.details.appearance.baseColor='#dd8833';multiple.project.documents.push(second);
 await fileInput(multiple,'multiple-rainoc.json');await until(()=>evaluate(`document.getElementById('importPicker').open&&!loading`),'multi chooser');check(await evaluate(`document.getElementById('name').value==='导入 Rainoc 单广播'&&document.getElementById('importChoice').options.length===2`),'Multiple import skipped choice or changed project');
 await input('#importChoice','1','change');holdValidation=true;await click('#confirmImport');await until(()=>pendingValidations.length===1,'chosen import validation');check(await evaluate(`document.getElementById('name').value==='导入 Rainoc 单广播'&&document.getElementById('importPicker').open&&document.getElementById('confirmImport').disabled`),'Multi import loaded before awaited validation');releaseValidation();await until(()=>evaluate(`document.getElementById('name').value==='选择第二广播'&&!loading&&!document.getElementById('importPicker').open`),'chosen import finished');check(await evaluate(`project.appearance.baseColor==='#dd8833'&&document.getElementById('iconColor').value==='#dd8833'`),'Selected imported icon was not rendered');
 const runtimeErrors=await evaluate('window.__unhandled');check(!errors.length&&!runtimeErrors.length,'Browser/server errors: '+JSON.stringify([...errors,...runtimeErrors]));
 const report={ok:true,checks,layout,screenshots,exports:{mi:mi.name,rainoc:rainoc.name},requests:requests.filter(item=>item.path.startsWith('/api/')),isolation:'Temporary Chrome profile; fixture-only loopback server; no live API, user data, or game access'};
 fs.writeFileSync(path.join(output,'browser-report.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
}catch(error){const report={ok:false,checks,error:error.stack,errors,layout};fs.writeFileSync(path.join(output,'browser-report.json'),JSON.stringify(report,null,2));console.error(JSON.stringify(report,null,2));process.exitCode=1;
}finally{for(const {res}of pendingValidations.splice(0))respond(res,{error:'test ended'},499);socket?.close();browser.kill();await new Promise(resolve=>server.close(resolve));await sleep(300);try{const clean=path.resolve(temporary);if(path.dirname(clean)!==path.resolve(os.tmpdir())||!path.basename(clean).startsWith('mi-broadcast-ui-'))throw Error('Unexpected temporary cleanup path');fs.rmSync(clean,{recursive:true,force:true});}catch{}}
