import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import http from 'node:http';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const editor=fileURLToPath(new URL('../editor/',import.meta.url));
const output=path.resolve(editor,'../../evidence/export-ui');fs.mkdirSync(output,{recursive:true});
const temporary=fs.mkdtempSync(path.join(os.tmpdir(),'mi-export-validation-')),profile=path.join(temporary,'profile');
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms)),calls=[],errors=[],screenshots=[],passed=[];
const project={projectId:'fixture',name:'Original project',editor:{externalRoomTools:true},design:{region:'PL',room:'PL_AI',authored:'unchanged'}};
const original=JSON.stringify(project),defaults={id:'fixture.mod',name:'Fixture',authors:'Fixture author',version:'0.4.1',projects:['fixture'],parts:['appearance','textures','room','dialogue'],format:'project',scope:'project',extraRooms:[],startRoom:'PL_AI',region:'PL',pearlCollectionId:'original-pearls',scene:{schema:'moreiterators.scene-assets.v1',scenes:[{kind:'select_menu_scene',name:'Original scene',images:[]}]},broadcasts:false,pearls:false,workPearls:false,projections:false};
let preferences=structuredClone(defaults),failRooms=false,failRegion=false,regionBlocker='',gateRegion=false,releaseRegion=null;
const fixture=`let project=${original},projects=[project];const serialize=()=>structuredClone(project);async function save(){};window.fixtureErrors=[];function run(fn){return async(...args)=>{try{return await fn(...args)}catch(error){fixtureErrors.push(error.message)}}}const api=async(path,data)=>{const response=await fetch('/api/'+path,data===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}),value=await response.json();if(!response.ok)throw Error(value.message||'Fixture failure');return value};window.MIExportScene={mount(){},reset(){},serialize(){throw Error('Unchanged scene was serialized')},setEnabled(){}};`;
const json=(res,value,status=200)=>{res.writeHead(status,{'content-type':'application/json; charset=utf-8'});res.end(JSON.stringify(value));};
const server=http.createServer(async(req,res)=>{try{
 const url=new URL(req.url,'http://fixture.invalid');
 if(url.pathname.startsWith('/api/')){
  let raw='';for await(const chunk of req)raw+=chunk;const data=raw?JSON.parse(raw):null;calls.push({path:url.pathname,data});
  if(url.pathname==='/api/export-settings'){if(data)preferences=structuredClone(data);return json(res,data?{ok:true}:preferences);}
  if(url.pathname==='/api/pearl-projects')return json(res,{projects:[{id:'original-pearls',name:'Original pearls'}],activeId:'original-pearls'});
  if(url.pathname==='/api/project-package-rooms')return failRooms?json(res,{message:'Read failed'},500):json(res,{projectId:'fixture',extraRooms:[],rooms:[{name:'PL_AI',region:'PL',kind:'ai',required:true,available:true},{name:'PL_ENTRY',region:'PL',kind:'entry',required:true,available:true}]});
  if(url.pathname==='/api/region-package-choices')return json(res,{regions:[{code:'PL',available:true}]});
  if(url.pathname==='/api/region-package-inspect'){if(gateRegion)await new Promise(resolve=>releaseRegion=resolve);return failRegion?json(res,{message:'Read failed'},500):json(res,{ok:!regionBlocker,rooms:['PL_AI','PL_ENTRY'],blockers:regionBlocker?[regionBlocker]:[],dependencies:[]});}
  if(url.pathname==='/api/export-room-check')return json(res,{snapshotToken:'snapshot',requiresChoices:false,rooms:[],assets:[],parameterConflicts:[],issues:[]});
  if(url.pathname==='/api/export'||url.pathname.startsWith('/api/export-'))return json(res,{url:'/fixture.zip'});
  throw Error('Unexpected API '+url.pathname);
 }
 if(url.pathname==='/favicon.ico'){res.writeHead(204);return res.end();}
 if(url.pathname==='/fixture.zip'){res.writeHead(200,{'content-type':'application/zip'});return res.end(Buffer.from('504b0506000000000000000000000000000000000000','hex'));}
 const resource=url.pathname==='/'?'index.html':decodeURIComponent(url.pathname).slice(1),file=path.resolve(editor,resource);
 if(!file.startsWith(path.resolve(editor)+path.sep)||!fs.existsSync(file)){res.writeHead(404);return res.end();}
 let content=fs.readFileSync(file);if(resource==='index.html')content=content.toString().replace(/<script\b[^>]*src="([^"]+)"[^>]*><\/script>/g,(whole,src)=>src==='/i18n.js'?whole:'').replace('</body>','<script>'+fixture+'</script><script src="/standalone.js"></script></body>');
 res.writeHead(200,{'content-type':({'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json'})[path.extname(file)]||'application/octet-stream'});res.end(content);
 }catch(error){errors.push(error.stack);json(res,{message:error.message},500);}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const origin='http://127.0.0.1:'+server.address().port;
const browser=spawn(process.env.MI_TEST_CHROME||'C:/Program Files/Google/Chrome/Application/chrome.exe',['--headless','--disable-gpu','--no-first-run','--disable-background-networking','--remote-debugging-address=127.0.0.1','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:'ignore'});
let socket,closeBrowser;
try{
 const portFile=path.join(profile,'DevToolsActivePort');for(let index=0;index<200&&!fs.existsSync(portFile);index++)await sleep(25);
 const port=fs.readFileSync(portFile,'utf8').split(/\r?\n/)[0],tabs=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();socket=new WebSocket(tabs.find(tab=>tab.type==='page').webSocketDebuggerUrl);await new Promise(resolve=>socket.onopen=resolve);
 let id=0;const pending=new Map();socket.onmessage=event=>{const value=JSON.parse(event.data);if(value.id){const task=pending.get(value.id);pending.delete(value.id);value.error?task.reject(Error(JSON.stringify(value.error))):task.resolve(value.result)}else if(value.method==='Runtime.exceptionThrown')errors.push(value.params.exceptionDetails.exception?.description||value.params.exceptionDetails.text);};
 const call=(method,params={})=>new Promise((resolve,reject)=>{const serial=++id;pending.set(serial,{resolve,reject});socket.send(JSON.stringify({id:serial,method,params}));});closeBrowser=()=>call('Browser.close');
 const evaluate=async expression=>{const result=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(result.exceptionDetails)throw Error(result.exceptionDetails.exception?.description||result.exceptionDetails.text);return result.result.value;};
 const until=async expression=>{for(let index=0;index<200;index++){if(await evaluate(expression))return;await sleep(20)}throw Error('Timed out: '+expression);};
 const click=selector=>evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`);
 const status=()=>evaluate(`document.getElementById('pack-status').textContent`),disabled=()=>evaluate(`document.getElementById('pack-build').disabled`);
 const requestCount=()=>calls.filter(call=>call.path.startsWith('/api/export')).length;
 const closed=async()=>{await click('[data-export-close]');await until(`!document.getElementById('exportDialog').open`);};
 const open=async(options={})=>{if(await evaluate(`document.getElementById('exportDialog').open`))await closed();preferences={...structuredClone(defaults),...options};await click('#export');await until(`document.getElementById('exportDialog').open&&!document.getElementById('exportDialog').inert`);};
 const invalidClick=async(pattern,focus)=>{assert.equal(await disabled(),false,'Invalid choices disabled the action');const before=requestCount();await click('#pack-build');assert.match(await status(),pattern);assert.equal(requestCount(),before,'Invalid click made an export/settings request');if(focus)assert.equal(await evaluate(focus),true,'Validation focused the wrong field');assert.equal(await evaluate(`document.getElementById('export-formatNote').hidden`),true);};
 const screenshot=async(name)=>{const result=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});const file=path.join(output,name);fs.writeFileSync(file,Buffer.from(result.data,'base64'));screenshots.push(file);};
 await call('Runtime.enable');await call('Page.enable');await call('Emulation.setDeviceMetricsOverride',{width:1100,height:900,deviceScaleFactor:1,mobile:false});await call('Page.navigate',{url:origin+'/?lang=zh-CN'});await until(`window.MI18n&&document.getElementById('export')?.onclick`);
 await open({format:'assets',parts:[]});await invalidClick(/请选择至少一项导出内容/,`document.activeElement.value==='appearance'`);assert.equal(await evaluate(`document.querySelectorAll('[name=part]:checked').length`),0);passed.push('Empty asset selection focuses content without writes or coercion');
 await open({projects:[]});await invalidClick(/请选择要导出的作品/,`document.activeElement.closest('#pack-projects')!==null`);passed.push('No project selection');
 await open({projects:['missing-project'],extraRooms:['PL_REMOVED'],startRoom:'PL_REMOVED',pearlCollectionId:'missing-pearls'});await invalidClick(/missing-project/,`document.activeElement.value==='missing-project'`);passed.push('Unavailable remembered project retained');
 await open({broadcasts:true});await click('#pack-build');await until(`document.querySelector('#pack-status a')`);assert.equal(calls.filter(call=>call.path==='/api/export-project-package').at(-1).data.broadcasts,true);assert.equal(await evaluate(`document.getElementById('pack-broadcasts').checked`),true);passed.push('Project ZIP includes selected linked broadcasts');
 await open({format:'mod',pearls:true,pearlCollectionId:'missing-pearls'});await invalidClick(/珍珠项目/,`document.activeElement.id==='pack-pearlCollection'&&document.getElementById('export-associated').open`);assert.equal(await evaluate(`document.getElementById('pack-pearlCollection').value`),'missing-pearls');await screenshot('export-missing-pearl-zh-CN.png');passed.push('Unavailable pearl collection retained and focused');
 await open({format:'playable',startRoom:'PL_REMOVED'});await invalidClick(/起始房间/,`document.activeElement.id==='export-startRoom'`);assert.equal(await evaluate(`document.getElementById('export-startRoom').value`),'PL_REMOVED');passed.push('Unavailable remembered start room retained');
 await open({scope:'region',format:'project'});assert.equal(await evaluate(`document.querySelector('[name=exportFormat]:checked').value`),'region');passed.push('Legacy mismatched region format normalizes to Region ZIP');
 await open({scope:'region',format:'region',region:'REMOVED'});await invalidClick(/可用的区域/,`document.activeElement.id==='export-region'`);assert.equal(await evaluate(`document.getElementById('export-region').value`),'REMOVED');passed.push('Unavailable remembered region retained');
 regionBlocker='PL_AI 缺少房间文件。';await open({scope:'region',format:'region'});await invalidClick(/PL_AI 缺少房间文件/,`document.activeElement.id==='export-regionSummary'`);assert.equal(await evaluate(`document.getElementById('export-regionSummary').textContent.includes('缺少房间文件')`),false);regionBlocker='';passed.push('One region blocker, one status owner');
 failRegion=true;await open({scope:'region',format:'region'});assert.equal(await disabled(),false);assert.equal(await evaluate(`document.getElementById('pack-build').textContent`),'重新检查');assert.match(await status(),/区域检查失败/);const beforeRetry=requestCount();failRegion=false;gateRegion=true;await click('#pack-build');await until(`document.getElementById('exportDialog').getAttribute('aria-busy')==='true'`);assert.equal(await disabled(),true);assert.equal(await evaluate(`document.getElementById('pack-build').textContent`),'正在读取区域…');await click('#pack-build');assert.equal(requestCount(),beforeRetry);gateRegion=false;releaseRegion();await until(`!document.getElementById('pack-build').disabled`);assert.equal(requestCount(),beforeRetry,'Retry unexpectedly saved settings or exported');assert.equal(await status(),'');assert.equal(await evaluate(`document.getElementById('pack-build').textContent`),'导出');passed.push('Region failure recovers with explicit read-only retry; busy only during fetch');
 failRooms=true;await open();assert.equal(await disabled(),false);assert.match(await status(),/房间检查失败/);const beforeRoomRetry=requestCount();failRooms=false;await click('#pack-build');await until(`!document.getElementById('pack-build').disabled`);assert.equal(requestCount(),beforeRoomRetry);passed.push('Room read failure retries without exporting');
 await open({format:'assets',parts:['textures'],extraRooms:['PL_REMOVED']});await click('#pack-build');await until(`document.querySelector('#pack-status a')`);assert.equal(calls.at(-1).path,'/api/export');passed.push('Remembered unselected room does not block assets');
 await open({projects:[]});await evaluate(`MI18n.setLocale('en')`);await invalidClick(/Select.*project/i,`document.activeElement.closest('#pack-projects')!==null`);await call('Emulation.setDeviceMetricsOverride',{width:420,height:900,deviceScaleFactor:1,mobile:false});await evaluate(`document.getElementById('pack-status').scrollIntoView({block:'center'})`);await screenshot('export-missing-parts-en-420.png');assert.equal(await evaluate(`document.getElementById('exportDialog').scrollWidth<=document.getElementById('exportDialog').clientWidth+1`),true);passed.push('English validation and narrow layout');
 assert.equal(await evaluate('JSON.stringify(project)'),original);assert.deepEqual(errors,[]);assert.deepEqual(await evaluate('fixtureErrors'),[]);passed.push('Raw project and authored scene unchanged');
 const result={ok:true,checks:passed,requests:calls.length,screenshots};fs.writeFileSync(path.join(output,'export-validation-results.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
}finally{
 if(closeBrowser)await Promise.race([closeBrowser().catch(()=>{}),sleep(2000)]);socket?.close();browser.kill();await new Promise(resolve=>server.close(resolve));await sleep(600);
 const resolved=path.resolve(temporary);if(path.dirname(resolved)!==path.resolve(os.tmpdir())||!path.basename(resolved).startsWith('mi-export-validation-'))throw Error('Unexpected temporary path');fs.rmSync(resolved,{recursive:true,force:true,maxRetries:10,retryDelay:200});
}
