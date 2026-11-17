import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import http from 'node:http';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const editor=fileURLToPath(new URL('../editor/',import.meta.url));
const workspace=path.resolve(editor,'../../../..'),before=path.join(workspace,'outputs/mi-042-publish-20261110/release/MoreIterators/editor');
const output=path.resolve(editor,'../../evidence/export-ui');fs.mkdirSync(output,{recursive:true});
const temporary=fs.mkdtempSync(path.join(os.tmpdir(),'mi-export-bundle-')),profile=path.join(temporary,'profile');
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms)),calls=[],errors=[],screenshots=[],checks=[];
const project={projectId:'pool',name:'pool moon',editor:{externalRoomTools:true},design:{authored:'unchanged'}},projects=[project,{projectId:'oracle',name:'第二个迭代器',editor:{externalRoomTools:true},design:{authored:'other'}}];
const original=JSON.stringify(projects),defaults={id:'author.pool',name:'pool moon',authors:'author',version:'0.4.2',description:'',projects:['pool'],parts:['appearance','textures','room','dialogue'],format:'project',scope:'project',extraRooms:[],startRoom:null,region:'TEST',scene:null,dialogue:true,pearls:false,broadcasts:false,workPearls:false,projections:false};
let preferences=structuredClone(defaults),baseline=false,conflicts=false,regionEmpty=false,snapshot=1,failExport='',importInfo=null,importReplies=[];
const version=(id,origin)=>({id,origin,origins:[origin],complete:true,pairedSource:true,hash:id,cameraCount:1,modifiedAt:origin==='project'?'2026-11-02T10:00:00Z':'2026-11-11T10:00:00Z'});
const report=()=>({snapshotToken:'snapshot-'+snapshot,requiresChoices:conflicts,issues:[],rooms:conflicts?[{projectId:'pool',room:'TEST_POOL_ENTRY',renderVersions:[version('render-project','project')],settingsVersions:[version('settings-project','project'),version('settings-installed','installed')]}]:[],assets:[{key:'soundeffects/ambient/factory.ogg',relative:'soundeffects/ambient/factory.ogg',projectId:'pool',versions:[{...version('builtin','game'),builtin:true}]}],parameterConflicts:[]});
const fixture=`let project=${JSON.stringify(project)},projects=${original};const serialize=()=>structuredClone(project);async function save(){};window.fixtureErrors=[];function run(fn){return async(...args)=>{try{return await fn(...args)}catch(error){fixtureErrors.push({message:error.message,code:error.code})}}}function notice(message,bad){const node=document.getElementById('notice');node.textContent=message;node.hidden=false;node.dataset.kind=bad?'error':'success';}const api=async(path,data)=>{const response=await fetch('/api/'+path,data===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}),value=await response.json();if(!response.ok)throw Error(value.message||value.error||'Fixture failure');return value};window.MIExportScene={mount(){},reset(){},serialize(){return null},setEnabled(){},setCover(){}};HTMLAnchorElement.prototype.click=function(){window.lastDownload=this.href;};`;
const json=(res,value,status=200)=>{res.writeHead(status,{'content-type':'application/json; charset=utf-8'});res.end(JSON.stringify(value));};
const server=http.createServer(async(req,res)=>{try{
 const url=new URL(req.url,'http://fixture.invalid');
 if(url.pathname.startsWith('/api/')){
  let raw='';for await(const chunk of req)raw+=chunk;const data=raw&&req.headers['content-type']!=='application/zip'?JSON.parse(raw):null;calls.push({path:url.pathname,data,choices:req.headers['x-mi-import-choices'],replace:req.headers['x-mi-replace-project']});
  if(url.pathname==='/api/export-settings'){if(data)preferences=structuredClone(data);return json(res,data?{ok:true}:preferences);}
  if(url.pathname==='/api/pearl-projects')return json(res,{projects:[{id:'pearls',name:'珍珠项目'}],activeId:'pearls'});
  if(url.pathname==='/api/project-bundle-mod-check')return json(res,{mods:[{id:'author.map',name:'外部地图项目',excluded:['__pycache__/scratch.pyc'],files:12,bytes:1024}]});
  if(url.pathname==='/api/project-bundle-mods')return json(res,{mods:[{id:'author.map',name:'外部地图项目',version:'1.0.0',available:true}]});
  if(url.pathname==='/api/project-package-rooms'){const id=url.searchParams.get('id'),tag=id==='pool'?'POOL':'ORACLE';return json(res,{projectId:id,extraRooms:[],rooms:[{name:'TEST_'+tag+'_AI',region:'TEST',kind:'ai',required:true,available:true},{name:'TEST_'+tag+'_ENTRY',region:'TEST',kind:'entry',required:true,available:true},{name:'TEST_GARDEN',region:'TEST',kind:'extra',available:true}]});}
  if(url.pathname==='/api/export-room-check')return json(res,report());
  if(url.pathname==='/api/region-package-choices')return json(res,{regions:[{name:'TEST',available:false,reason:'TEST 是共享测试区域'},{name:'PL',available:true}]});
  if(url.pathname==='/api/region-package-inspect')return json(res,{ok:true,rooms:['PL_AI','PL_ENTRY'],dependencies:[],blockers:[],includedProjects:regionEmpty?[]:[{projectId:'oracle',name:'第二个迭代器'}],projectIds:regionEmpty?[]:['oracle']});
  if(url.pathname==='/api/project-package-inspect')return json(res,importInfo||{projectId:'pool',name:'pool moon',collision:true});
  if(url.pathname==='/api/import-project-package')return json(res,importReplies.shift()||{ok:true,project,projects:[project],externalMods:[]});
  if(['/api/export-project-package','/api/export-standalone','/api/export-playable','/api/export-region-package','/api/export'].includes(url.pathname)){if(failExport)return json(res,{error:failExport},400);return json(res,{url:'/fixture.zip'});}
  throw Error('Unexpected API '+url.pathname);
 }
 if(url.pathname==='/favicon.ico'){res.writeHead(204);return res.end();}
 if(url.pathname==='/fixture.zip'){res.writeHead(200,{'content-type':'application/zip'});return res.end(Buffer.from('504b0506000000000000000000000000000000000000','hex'));}
 const resource=url.pathname==='/'?'index.html':decodeURIComponent(url.pathname).slice(1),base=baseline?before:editor,file=path.resolve(base,resource);
 if(!file.startsWith(path.resolve(base)+path.sep)||!fs.existsSync(file)){res.writeHead(404);return res.end();}
 let content=fs.readFileSync(file);
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
 const set=(selector,value)=>evaluate(`(()=>{const node=document.querySelector(${JSON.stringify(selector)});node.value=${JSON.stringify(value)};node.dispatchEvent(new Event('change',{bubbles:true}));})()`);
 const navigate=async(language='zh-CN')=>{await call('Page.navigate',{url:origin+'/?lang='+language+'&sample='+Date.now()});await until(`window.MI18n&&document.getElementById('export')?.onclick`);await click('#export');await until(`document.getElementById('exportDialog').open&&!document.getElementById('exportDialog').inert`);await evaluate('document.fonts.ready');};
 const build=async()=>{await click('#pack-build');await until(`!document.getElementById('pack-build').disabled`);};
 const screenshot=async name=>{await sleep(250);const result=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});const file=path.join(output,name);fs.writeFileSync(file,Buffer.from(result.data,'base64'));screenshots.push(file);const clip=await evaluate(`(()=>{const box=document.querySelector('dialog[open]').getBoundingClientRect();return {x:Math.max(0,box.x),y:Math.max(0,box.y),width:box.width,height:Math.min(innerHeight-box.y,box.height),scale:1}})()`);const cropped=await call('Page.captureScreenshot',{format:'png',clip,captureBeyondViewport:false});fs.writeFileSync(path.join(output,name.replace('.png','-面板.png')),Buffer.from(cropped.data,'base64'));};
 await call('Runtime.enable');await call('Page.enable');await call('Emulation.setDeviceMetricsOverride',{width:1100,height:900,deviceScaleFactor:1,mobile:false});
 baseline=false;await navigate();await click('[data-export-close]');await until(`!document.getElementById('exportDialog').open`);
 const start=()=>evaluate(`window.importPromise=MIProjectPackageImport(new Blob(['fixture']));void 0`);
 const imported=()=>calls.filter(item=>item.path==='/api/import-project-package');
 function bundle(count,collisions=[]){return {kind:'project-bundle',projects:Array.from({length:count},(_,i)=>({projectId:'project-'+i,name:'Project '+i})),externalMods:[],collisions};}
 for(const count of [3,5,20]){
  importInfo=bundle(count);importReplies=[{ok:true,projects:importInfo.projects}];const before=imported().length;await start();const result=await evaluate('importPromise');assert.equal(result.projectId,'project-0');assert.equal(imported().length,before+1);assert.equal(await evaluate(`document.getElementById('projectImportDialog').open`),false);
 }
 checks.push('Three, five and twenty new projects import directly without an overview dialog');
 importInfo={projectId:'single',name:'Single project',collision:false};importReplies=[{ok:true,project:{projectId:'single'}}];await start();assert.equal((await evaluate('importPromise')).projectId,'single');assert.equal(imported().at(-1).replace,undefined);checks.push('Legacy single-project import remains direct');
 importInfo={projectId:'single',name:'Single project',collision:true};let before=imported().length;await evaluate(`window.confirm=()=>false`);await start();assert.equal(await evaluate('importPromise'),null);assert.equal(imported().length,before);
 await evaluate(`window.confirm=()=>true`);importReplies=[{ok:true,project:{projectId:'single'}}];await start();await evaluate('importPromise');assert.equal(imported().at(-1).replace,'1');checks.push('Legacy overwrite uses the original confirmation and cancel writes nothing');
 const collision={key:'project/project-0',name:'Project 0',kind:'project'};importInfo=bundle(5,[collision]);before=imported().length;await start();await until(`document.getElementById('projectImportDialog').open`);assert.equal(await evaluate(`document.querySelectorAll('#import-contents .import-project-row').length`),1);assert.equal(await evaluate(`document.querySelector('[data-import-key]').value`),'keep');assert.equal(await evaluate(`document.getElementById('import-contents').textContent.includes('Project 1')`),false);await click('#import-cancel');assert.equal(await evaluate('importPromise'),null);assert.equal(imported().length,before);checks.push('Five-project import only asks about the conflicting item; cancel writes nothing');
 importReplies=[{ok:true,projects:importInfo.projects}];await start();await until(`document.getElementById('projectImportDialog').open`);await set('[data-import-key]','replace');await click('#import-confirm');await evaluate('importPromise');assert.deepEqual(JSON.parse(imported().at(-1).choices),{'project/project-0':'replace'});checks.push('Only explicit per-item overwrite choices are sent');
 importInfo=bundle(3);importReplies=[{ok:false,...bundle(3,[collision])}];before=imported().length;await start();await until(`document.getElementById('projectImportDialog').open`);assert.equal(imported().length,before+1);assert.equal(await evaluate(`document.querySelector('[data-import-key]').value`),'keep');await click('#import-cancel');assert.equal(await evaluate('importPromise'),null);assert.equal(imported().length,before+1);checks.push('A conflict appearing after inspection stops import and requests a choice');
 const later={key:'project/project-1',name:'Project 1',kind:'project'};importInfo=bundle(3,[collision]);importReplies=[{ok:false,...bundle(3,[collision,later])},{ok:true,projects:bundle(3).projects}];await start();await until(`document.getElementById('projectImportDialog').open`);await set('[data-import-key]','replace');await click('#import-confirm');await until(`document.querySelectorAll('[data-import-key]').length===2&&!document.getElementById('import-confirm').disabled`);assert.deepEqual(await evaluate(`[...document.querySelectorAll('[data-import-key]')].map(node=>node.value)`),['replace','keep']);await click('#import-confirm');await evaluate('importPromise');assert.deepEqual(JSON.parse(imported().at(-1).choices),{'project/project-0':'replace','project/project-1':'keep'});checks.push('A newly conflicting item defaults to keep without losing the earlier explicit choice');
 importInfo={kind:'project-bundle',projects:[],externalMods:[{id:'author.map',name:'Map'}],collisions:[]};importReplies=[{ok:true,projects:[],externalMods:importInfo.externalMods}];await start();assert.equal(await evaluate('importPromise'),null);assert.equal(await evaluate(`document.getElementById('projectImportDialog').open`),false);checks.push('External-only package imports without adding a project overview');
 assert.equal(await evaluate('JSON.stringify(projects)'),original);assert.deepEqual(errors,[]);checks.push('Open authored projects remain unchanged');
 const result={ok:true,checks};fs.writeFileSync(path.join(output,'import-flow-results.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));

}finally{
 if(closeBrowser)await Promise.race([closeBrowser().catch(()=>{}),sleep(2000)]);socket?.close();browser.kill();await new Promise(resolve=>server.close(resolve));await sleep(600);
 const resolved=path.resolve(temporary);if(path.dirname(resolved)!==path.resolve(os.tmpdir())||!path.basename(resolved).startsWith('mi-export-bundle-'))throw Error('Unexpected temporary path');fs.rmSync(resolved,{recursive:true,force:true,maxRetries:10,retryDelay:200});
}
