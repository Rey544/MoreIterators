import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import http from 'node:http';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const editor=fileURLToPath(new URL('../editor/',import.meta.url));
const output=path.resolve(editor,'../../evidence/export-followup'),before=path.join(output,'before');fs.mkdirSync(output,{recursive:true});
const temporary=fs.mkdtempSync(path.join(os.tmpdir(),'mi-export-followup-')),profile=path.join(temporary,'profile');
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms)),calls=[],errors=[],screenshots=[],checks=[];
const project={projectId:'fixture',name:'测试作品',editor:{externalRoomTools:true},design:{region:'PL',room:'PL_AI',authored:'unchanged'}};
const original=JSON.stringify(project),defaults={id:'fixture.mod',name:'测试导出',authors:'原作者',version:'0.4.1',description:'',projects:['fixture'],parts:['appearance','textures','room','dialogue'],format:'mod',scope:'project',extraRooms:[],startRoom:'PL_AI',region:'PL',scene:null,dialogue:true,pearls:false,broadcasts:false,workPearls:false,projections:false};
let preferences=structuredClone(defaults),baseline=false,failPreferences=false,conflicts=false,snapshot=1,changedVersion=false,staleOnce=false;
const version=(id,origin)=>({id,origin,origins:[origin],complete:true,pairedSource:true,hash:id,cameraCount:1,modifiedAt:'2026-11-10T12:00:00Z'});
const report=()=>({snapshotToken:'snapshot-'+snapshot,requiresChoices:conflicts,issues:[],rooms:conflicts?[{projectId:'fixture',room:'PL_AI',renderVersions:[version('render-project','project'),version('render-installed','installed')],settingsVersions:[version('settings-project','project'),version(changedVersion?'settings-installed-v2':'settings-installed','installed')]}]:[],assets:conflicts?[{key:'palettes/palette9100.png',relative:'palettes/palette9100.png',projectId:'fixture',versions:[version('asset-project','project'),version('asset-installed','installed')]}]:[],parameterConflicts:conflicts?[{projectId:'fixture',room:'PL_AI',kind:'palette',settingsVersionIds:[changedVersion?'settings-installed-v2':'settings-installed']}]:[]});
const fixture=`let project=${original},projects=[project];const serialize=()=>structuredClone(project);async function save(){};window.fixtureErrors=[];function run(fn){return async(...args)=>{try{return await fn(...args)}catch(error){fixtureErrors.push({message:error.message,code:error.code})}}}function notice(message,bad){const node=document.getElementById('notice');node.textContent=message;node.hidden=false;node.dataset.kind=bad?'error':'success';}const api=async(path,data)=>{const response=await fetch('/api/'+path,data===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}),value=await response.json();if(!response.ok)throw Error(value.message||'Fixture failure');return value};window.MIExportScene={mount(){},reset(){},serialize(){return null},setEnabled(){},setCover(){}};`;
const json=(res,value,status=200)=>{res.writeHead(status,{'content-type':'application/json; charset=utf-8'});res.end(JSON.stringify(value));};
const server=http.createServer(async(req,res)=>{try{
 const url=new URL(req.url,'http://fixture.invalid');
 if(url.pathname.startsWith('/api/')){
  let raw='';for await(const chunk of req)raw+=chunk;const data=raw?JSON.parse(raw):null;calls.push({path:url.pathname,data});
  if(url.pathname==='/api/export-settings'){if(failPreferences)return json(res,{message:'Preference write failed'},500);if(data)preferences=structuredClone(data);return json(res,data?{ok:true}:preferences);}
  if(url.pathname==='/api/pearl-projects')return json(res,{projects:[],activeId:''});
  if(url.pathname==='/api/project-package-rooms')return json(res,{projectId:'fixture',extraRooms:[],rooms:[{name:'PL_AI',region:'PL',kind:'ai',required:true,available:true},{name:'PL_ENTRY',region:'PL',kind:'entry',required:true,available:true}]});
  if(url.pathname==='/api/export-room-check')return json(res,report());
  if(url.pathname==='/api/export-standalone'||url.pathname==='/api/export-playable'){
   if(!/^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)+$/.test(data.id))return json(res,{error:'Use a mod ID such as author.myiterator.'},400);
   if(staleOnce){staleOnce=false;snapshot++;changedVersion=true;return json(res,{code:'room_choices_stale',error:'Room files changed. Review the available versions again.'},409);}
   return json(res,{url:'/fixture.zip'});
  }
  throw Error('Unexpected API '+url.pathname);
 }
 if(url.pathname==='/favicon.ico'){res.writeHead(204);return res.end();}
 if(url.pathname==='/fixture.zip'){res.writeHead(200,{'content-type':'application/zip'});return res.end(Buffer.from('504b0506000000000000000000000000000000000000','hex'));}
 const resource=url.pathname==='/'?'index.html':decodeURIComponent(url.pathname).slice(1),file=path.resolve(editor,resource);
 if(!file.startsWith(path.resolve(editor)+path.sep)||!fs.existsSync(file)){res.writeHead(404);return res.end();}
 const baselineFile=path.join(before,resource);let content=fs.readFileSync(baseline&&['standalone.js','index.html','export-dialog.css'].includes(resource)&&fs.existsSync(baselineFile)?baselineFile:file);
 if(resource==='index.html')content=content.toString().replace(/<script\b[^>]*src="([^"]+)"[^>]*><\/script>/g,(whole,src)=>src==='/i18n.js'?whole:'').replace('</body>','<script>'+fixture+'</script><script src="/standalone.js"></script></body>');
 res.writeHead(200,{'content-type':({'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json'})[path.extname(file)]||'application/octet-stream','cache-control':'no-store'});res.end(content);
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
 const input=(selector,value)=>evaluate(`(()=>{const node=document.querySelector(${JSON.stringify(selector)});node.value=${JSON.stringify(value)};node.dispatchEvent(new Event('input',{bubbles:true}));node.dispatchEvent(new Event('change',{bubbles:true}));})()`);
 const open=async()=>{await click('#export');await until(`document.getElementById('exportDialog').open&&!document.getElementById('exportDialog').inert`);};
 const build=async()=>{await click('#pack-build');await until(`!document.getElementById('pack-build').disabled`);};
 const status=()=>evaluate(`document.getElementById('pack-status').textContent`);
 const screenshot=async name=>{await sleep(250);const result=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});const file=path.join(output,name);fs.writeFileSync(file,Buffer.from(result.data,'base64'));screenshots.push(file);};
 const navigate=async()=>{await call('Page.navigate',{url:origin+'/?lang=zh-CN&sample='+Date.now()});await until(`window.MI18n&&document.getElementById('export')?.onclick`);await open();};
 const choose=async()=>{for(const value of ['render-project','settings-installed','asset-installed'])await click('#export-roomVersions input[value="'+value+'"]');await input('#export-roomVersions select[data-policy]','room');};
 const selections=()=>evaluate(`({values:[...document.querySelectorAll('#export-roomVersions input:checked')].map(node=>node.value),policy:document.querySelector('#export-roomVersions select[data-policy]')?.value})`);
 await call('Runtime.enable');await call('Page.enable');await call('Emulation.setDeviceMetricsOverride',{width:1100,height:1100,deviceScaleFactor:1,mobile:false});
 if(fs.existsSync(path.join(before,'standalone.js'))){
  baseline=true;preferences={...structuredClone(defaults),id:'Invalid ID'};await navigate();await build();assert.equal(await evaluate(`document.getElementById('pack-metadata').open`),false);await screenshot('before-metadata-error-zh-CN.png');
  preferences=structuredClone(defaults);conflicts=true;await navigate();await build();await choose();await input('#pack-authors','修改后的作者');assert.equal(await evaluate(`document.getElementById('export-roomVersions').hidden`),true);await evaluate(`document.getElementById('pack-metadata').open=true`);await screenshot('before-author-change-zh-CN.png');checks.push('Baseline reproduces hidden metadata error and lost room selections');
 }
 baseline=false;conflicts=false;preferences={...structuredClone(defaults),id:'Invalid ID'};await navigate();
 const attempts=calls.filter(call=>call.path==='/api/export-standalone').length;await build();assert.equal(calls.filter(call=>call.path==='/api/export-standalone').length,attempts);assert.equal(await evaluate(`document.getElementById('pack-id').checkVisibility()&&document.activeElement.id==='pack-id'`),true);assert.match(await status(),/author.myiterator/);await screenshot('after-metadata-error-zh-CN.png');checks.push('Invalid metadata is identified before export and its field is revealed and focused');
 for(const [key,value,message]of [['id','moreiterators.test',/自己的模组 ID/],['id','eoe.test',/自己的模组 ID/],['name','   ',/模组名称/],['authors','',/作者/],['version','01.2.3',/0.1.0/],['version','1.2',/0.1.0/],['id','a.'+'b'.repeat(63),/64/],['name','x'.repeat(101),/100/],['authors','x'.repeat(201),/200/],['description','x'.repeat(4001),/4000/],['version','1'.repeat(33),/32/]]){
  for(const field of ['id','name','authors','description','version'])await input('#pack-'+field,defaults[field]);await input('#pack-'+key,value);const count=calls.filter(call=>call.path==='/api/export-standalone').length;await build();assert.match(await status(),message);assert.equal(await evaluate('document.activeElement.id'),'pack-'+key);assert.equal(calls.filter(call=>call.path==='/api/export-standalone').length,count);
 }
 checks.push('Reserved IDs, empty fields, semantic version and all server string limits match frontend validation');
 for(const field of ['id','name','authors','description','version'])await input('#pack-'+field,defaults[field]);await input('#pack-name','🙂'.repeat(100));await build();await until(`document.querySelector('#pack-status a')`);checks.push('Unicode character counts agree with backend limits');
 await input('#pack-authors','');await evaluate(`MI18n.setLocale('en')`);await build();assert.match(await status(),/Enter an author/);await screenshot('after-metadata-error-en.png');
 preferences=structuredClone(defaults);conflicts=true;await navigate();await build();await choose();const selected=await selections(),preflightCount=calls.filter(call=>call.path==='/api/export-room-check').length;
 await input('#pack-authors','修改后的作者');assert.deepEqual(await selections(),selected);assert.equal(await evaluate(`document.getElementById('export-roomVersions').hidden`),false);await evaluate(`document.getElementById('pack-metadata').open=true;document.getElementById('pack-authors').scrollIntoView({block:'end'});`);await screenshot('after-author-change-zh-CN.png');await build();await until(`document.querySelector('#pack-status a')`);assert.equal(calls.filter(call=>call.path==='/api/export-room-check').length,preflightCount);let exported=calls.filter(call=>call.path==='/api/export-standalone').at(-1).data;assert.equal(exported.authors,'修改后的作者');assert.equal(exported.roomSourceChoices.snapshotToken,'snapshot-1');assert.equal(exported.roomSourceChoices.policies.fixture.palette,'room');checks.push('Author changes retain source, palette and policy selections while exporting current metadata');
 await click('#export-roomVersions button');await until(`!document.getElementById('pack-build').disabled`);assert.deepEqual(await selections(),selected);checks.push('Manual recheck retains still-valid selections');
 staleOnce=true;await build();await until(`fixtureErrors.some(value=>value.code==='room_choices_stale')`);const refreshed=await selections();assert.deepEqual(refreshed.values,['render-project','asset-installed']);assert.equal(refreshed.policy,undefined);await click('#export-roomVersions input[value="settings-installed-v2"]');assert.equal(await evaluate(`document.querySelector('#export-roomVersions select[data-policy]').value`),'');await input('#export-roomVersions select[data-policy]','room');await build();await until(`document.querySelector('#pack-status a')`);exported=calls.filter(call=>call.path==='/api/export-standalone').at(-1).data;assert.equal(exported.roomSourceChoices.snapshotToken,'snapshot-2');assert.equal(exported.roomSourceChoices.choices['fixture/PL_AI'].settings,'settings-installed-v2');checks.push('Changed room files refresh token, retain unaffected choices, and require new choice for the replaced settings version');
 await input('#pack-authors','会话草稿作者');failPreferences=true;await click('[data-export-close]');await until(`!document.getElementById('exportDialog').open`);await until(`document.getElementById('notice').textContent.includes('当前会话已保留')`);assert.equal(await evaluate(`document.getElementById('notice').hidden`),false);await open();assert.equal(await evaluate(`document.getElementById('pack-authors').value`),'会话草稿作者');assert.equal(await evaluate(`document.getElementById('exportDialog').open`),true);checks.push('Close survives failed preference write and reopen recovers the session draft even if preference read also fails');
 await input('#pack-description','取消关闭测试');await evaluate(`document.getElementById('exportDialog').dispatchEvent(new Event('cancel',{cancelable:true}))`);await until(`!document.getElementById('exportDialog').open`);await open();assert.equal(await evaluate(`document.getElementById('pack-description').value`),'取消关闭测试');failPreferences=false;await click('[data-export-close]');await until(`!document.getElementById('exportDialog').open`);for(let index=0;index<100&&preferences.description!=='取消关闭测试';index++)await sleep(20);assert.equal(preferences.authors,'会话草稿作者');assert.equal(preferences.description,'取消关闭测试');checks.push('Escape follows the same safe close behavior and recovered preferences save after service recovery');
 assert.equal(await evaluate('JSON.stringify(project)'),original);assert.deepEqual(errors,[]);checks.push('Project and authored data unchanged');
 const result={ok:true,checks,screenshots};fs.writeFileSync(path.join(output,'results.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
}finally{
 if(closeBrowser)await Promise.race([closeBrowser().catch(()=>{}),sleep(2000)]);socket?.close();browser.kill();await new Promise(resolve=>server.close(resolve));await sleep(600);
 const resolved=path.resolve(temporary);if(path.dirname(resolved)!==path.resolve(os.tmpdir())||!path.basename(resolved).startsWith('mi-export-followup-'))throw Error('Unexpected temporary path');fs.rmSync(resolved,{recursive:true,force:true,maxRetries:10,retryDelay:200});
}
