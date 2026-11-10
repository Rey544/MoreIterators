import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import {createRequire} from 'node:module';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {spawnSync} from 'node:child_process';
const require = createRequire(import.meta.url), root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const exchange = require(path.join(root,'editor/broadcast-exchange.js'));
const browserModule=vm.createContext({crypto:globalThis.crypto,atob});
vm.runInContext(fs.readFileSync(path.join(root,'editor/broadcast-exchange.js'),'utf8'),browserModule);
assert.equal(typeof browserModule.MIBroadcastExchange.importRainoc,'function');
assert.equal(typeof browserModule.MIBroadcastExchange.exportRainoc,'function');
const clone = value => JSON.parse(JSON.stringify(value));
const uid = () => '1234567890abcdef1234567890abcdef';
const bundle = documents => ({format:'eoe-lore-project',version:1,project:{name:'原项目',uid:'abcdef12-3456-7890-abcd-ef1234567890',images:[{data:'unrelated picture'}],documents,broadcastSettings:{alignment:'center'}}});
const character = (id,title,aliases,color) => ({id,title,kind:'character',category:'迭代器',content:'不应导出的人物正文',details:{aliases,characterTags:[],characterColor:color,iconData:'unrelated picture'}});
const doc = (content='甲：第一句\r\n\r\n（提示）\r\n', details={}) => ({id:'original-broadcast',title:'原广播',kind:'broadcast',category:'广播',categories:['广播'],logicalPath:'广播/原稿.md',archived:false,content,details:{appearance:{baseColor:'#D4A6FF'},comment:'原注释',english:'original',regionProfiles:[],echo:{karma:1,type:'once',room:'',typeNote:''},broadcast:{mode:'private',typeLabel:'原类型',groupName:'原群组',secondaryHeading:'原副标题',sources:[{participant:'甲',suffix:'原来源'}],annotations:[{label:'原标签',value:'原附注'}],useCharacterColors:true},...details}});
const fixture = bundle([character('a','角色甲',['甲','shared'],'#80CFFF'),character('b','角色乙',['shared','乙'],'#ABCDEF'),character('unused','无关人物',['unused'],'#FFFFFF'),doc(),doc('乙：第二篇',{appearance:{}})]);
fixture.project.documents[4].id='second-broadcast';
const before = JSON.stringify(fixture);
let serial=0;
const imported = exchange.importRainoc(fixture,{usedIds:['B01','B03'],uid:()=>String(++serial).padStart(32,'0')});
assert.deepEqual(imported.map(p=>p.id),['B02','B04']);
assert.equal(imported[0].appearance.baseColor,'#D4A6FF');
assert.equal(imported[1].appearance.baseColor,'#C9CCCF');
assert.deepEqual(imported[0].speakers.map(s=>s.name),['角色甲']);
assert.deepEqual(imported[1].speakers.map(s=>s.name),['角色甲','角色乙']);                                
assert.deepEqual(imported[1].speakers[1].aliases,['乙']);                              
assert.equal(JSON.stringify(fixture),before);
const original = imported[0], originalSnapshot=JSON.stringify(original), exported = exchange.exportRainoc(original);
assert.equal(JSON.stringify(original),originalSnapshot);
assert.equal(exported.project.documents[0].content,fixture.project.documents[3].content);
assert.equal(exported.project.documents[0].details.broadcast.secondaryHeading,'原副标题');
assert.deepEqual(exported.project.documents[0].details.echo,fixture.project.documents[3].details.echo);
assert.equal(exported.project.documents[0].logicalPath,'广播/原稿.md');
assert.equal(exported.project.images.length,0);
assert.deepEqual(exported.documentAssets,[]);
assert.equal(exported.project.documents.length,2);
assert.equal(exported.project.documents[1].content,'');
assert.equal(exported.project.documents[1].details.iconData,undefined);
assert.equal(exported.exportScope.mode,'partial');
assert.equal(exported.project.uid,fixture.project.uid);
assert.equal(exported.project.documents[0].details.appearance.baseColor,'#D4A6FF');
assert.equal(exported.project.documents[1].details.characterColor,'#80CFFF');
const modified=clone(original);
modified.name='修改名称';modified.pages=[{lines:[{text:'甲：修改正文'}]},{lines:[{text:'后一页'}]}];
modified.appearance.baseColor='#123456';modified.speakers[0].color='#654321';modified.useCharacterColors=false;
const changed=exchange.exportRainoc(modified);
assert.equal(changed.project.documents[0].title,'修改名称');
assert.equal(changed.project.documents[0].content,'甲：修改正文\n后一页');
assert.equal(changed.project.documents[0].details.appearance.baseColor,'#123456');
assert.equal(changed.project.documents[0].details.broadcast.useCharacterColors,false);
assert.equal(changed.project.documents[1].details.characterColor,'#654321');
assert.equal(changed.project.documents[0].details.broadcast.secondaryHeading,'原副标题');
assert.equal(changed.project.documents[0].details.pages,undefined);
const fallback=exchange.importRainoc(bundle([doc('  ',{lines:[{speaker:'甲',text:'旧格式正文'}]})]),{uid})[0];
assert.equal(fallback.pages[0].lines[0].text,'甲：旧格式正文');
assert.equal(exchange.exportRainoc(fallback).project.documents[0].content,'  ');
fallback.pages[0].lines[0].text='';
assert.deepEqual(exchange.exportRainoc(fallback).project.documents[0].details.lines,[]);
const sparse=exchange.importRainoc(bundle([{id:'sparse',kind:'broadcast',title:'无设置',content:'原文'}]),{uid})[0];
assert.equal(sparse.appearance.baseColor,'#C9CCCF');
assert.equal(sparse.useCharacterColors,false);
const long=exchange.importRainoc(bundle([doc(Array.from({length:101},(_,i)=>'第'+i+'行').join('\n'))]),{uid})[0];
assert.deepEqual(long.pages.map(p=>p.lines.length),[100,1]);
const noRoom=clone(sparse);delete noRoom.appearance;
assert.equal(exchange.exportRainoc(noRoom).project.documents[0].details.appearance,undefined);
for (const invalid of ['red','#fff','#12345678',[1,2,3],null]) {
  assert.throws(()=>exchange.importRainoc(bundle([doc('正文',{appearance:{baseColor:invalid}})]),{uid}),/RGB/);
}
for (const details of [{mi:{}},{broadcast:{pages:[]}},{appearance:{baseColor:'#123456',mi:{}}},{lines:[{speaker:'甲',text:'文本',id:'x'}]}]) {
  assert.throws(()=>exchange.importRainoc(bundle([doc('正文',details)]),{uid}),/格式无效|图标颜色/);
}
assert.throws(()=>exchange.importRainoc({format:'eoe-lore-project',version:2,project:{documents:[]}}),/请选择/);
assert.throws(()=>exchange.importRainoc(bundle([])),/没有广播/);
assert.throws(()=>exchange.importRainoc(bundle([doc('x'.repeat(4001))]),{uid}),/4000/);
assert.throws(()=>exchange.importRainoc(bundle([doc()]),{uid:()=>''}),/ID/);
assert.throws(()=>exchange.importRainoc(bundle([doc(),doc()]),{uid}),/ID/);
assert.throws(()=>exchange.importRainoc(bundle([doc('',{broadcast:{useCharacterColors:'yes'}})]),{uid}),/格式无效/);
console.log('Broadcast exchange: pure conversion checks passed.');
const legacy=clone(original);delete legacy.style;delete legacy.speakers;delete legacy.useCharacterColors;delete legacy.rainoc;
legacy.pages=[{lines:[{text:'Moon: First',color:'#33aa66',font:'display',size:1.3,speed:.5,hold:4},{text:'Pebbles: Second',color:'#aa3377',font:'normal',size:.8,speed:2,hold:.4}]}];
const legacySnapshot=clone(legacy),legacyExport=exchange.exportRainoc(legacy);
assert.deepEqual(legacy,legacySnapshot);
assert.equal(legacyExport.project.documents[1].details.characterColor,'#33aa66');
assert.equal(legacyExport.project.documents[2].details.characterColor,'#aa3377');

const arg = process.argv.indexOf('--rainoc');
const rainocInput=arg>=0?process.argv[arg+1]:process.env.RAINOCTOOL_HTML;
if (!rainocInput) {
  console.log('Native RainocTool integration not run; supply --rainoc <formal index.html> or RAINOCTOOL_HTML.');
  process.exit(0);
}
const rainocPath=path.resolve(rainocInput), html=fs.readFileSync(rainocPath,'utf8');
const script=[...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)].map(m=>m[1]).find(s=>s.includes('global.OCLocal = api;'));
assert.ok(script,'formal RainocTool inline script exists');
function iife(marker,startMarker,endMarker) {
  const markerAt=script.indexOf(marker), start=script.lastIndexOf(startMarker,markerAt), end=script.indexOf(endMarker,markerAt);
  assert.ok(markerAt>=0&&start>=0&&end>=markerAt,'native module: '+marker);
  return script.slice(start,end+endMarker.length);
}
const category=iife('scope.OCCategoryModel = api;','(function(scope) {','})(typeof window !== "undefined" ? window : globalThis);');
const model=iife('global.OCLocal = api;','(function(global) {','})(typeof self === "undefined" ? globalThis : self);');
const storage=script.slice(0,script.indexOf('})(globalThis);')+'})(globalThis);'.length);
const route=iife('OCStandalone.route = route;','(() => {','})();');
const context=vm.createContext({structuredClone,TextEncoder,TextDecoder,atob,btoa,console,crypto:globalThis.crypto,OCStandalone:{crypto:globalThis.crypto}});
vm.runInContext(category,context);vm.runInContext(model,context);
for(const candidate of [exported,changed,exchange.exportRainoc(sparse),exchange.exportRainoc(fallback),legacyExport]) {
  context.candidate=clone(candidate.project);
  const validated=vm.runInContext('OCLocal.project(candidate,OCLocal.empty(candidate.id,candidate.name,[],candidate.uid),new Map())',context);
  assert.equal(validated.documents[0].content,candidate.project.documents[0].content);
}
console.log('Broadcast exchange: formal RainocTool validateProject accepted all exports.');
const chromeArg=process.argv.indexOf('--browser');
const chrome=chromeArg>=0?process.argv[chromeArg+1]:'C:/Program Files/Google/Chrome/Application/chrome.exe';
assert.ok(fs.existsSync(chrome),'isolated headless browser exists');
const temp=fs.mkdtempSync(path.join(os.tmpdir(),'mi-broadcast-rainoc-'));
const browserCheck=`(async()=>{try {
  await OCStandalone.init();
  if(OCStandalone.storage!=='indexeddb')throw Error('Expected isolated IndexedDB');
  const bundle=${JSON.stringify(changed).replace(/</g,'\\u003c')};
  const response=await OCStandalone.route(new Request('https://oc-local.invalid/api/projects/import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(bundle)}));
  const imported=await response.json();if(!response.ok)throw Error(JSON.stringify(imported));
  const response2=await OCStandalone.route(new Request('https://oc-local.invalid/api/projects/'+imported.id+'/export'));
  const output=await response2.json();if(!response2.ok)throw Error(JSON.stringify(output));
  const broadcast=output.project.documents.find(d=>d.kind==='broadcast'),character=output.project.documents.find(d=>d.kind==='character');
  if(broadcast.content!=='甲：修改正文\\n后一页'||broadcast.details.appearance.baseColor!=='#123456'||character.details.characterColor!=='#654321'||broadcast.details.broadcast.secondaryHeading!=='原副标题')throw Error('native import/export changed authored fields');
  const copyResponse=await OCStandalone.route(new Request('https://oc-local.invalid/api/projects/import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...output,importMode:'copy'})}));
  if(!copyResponse.ok)throw Error('native exported copy failed');
  document.getElementById('result').textContent='PASS native import → export → copy import; isolated IndexedDB';
}catch(error){document.getElementById('result').textContent='FAIL '+error.stack;}})();`;
const page=path.join(temp,'check.html');
const combined=[storage,category,model,'globalThis.OCProjectZip={ZipError:class extends Error{}};',route,browserCheck].join('\n');
fs.writeFileSync(page,'<!doctype html><meta charset="utf-8"><pre id="result">PENDING</pre><script>'+combined.replace(/<\/script/gi,'<\\/script')+'</script>');
try {
  const run=spawnSync(chrome,['--headless=new','--disable-gpu','--no-first-run','--disable-background-networking','--disable-extensions','--disable-sync','--user-data-dir='+path.join(temp,'profile'),'--dump-dom','--virtual-time-budget=15000',pathToFileURL(page).href],{encoding:'utf8',timeout:45000,maxBuffer:2*1024*1024,windowsHide:true});
  if(run.error)throw run.error;
  assert.match(run.stdout,/PASS native import → export → copy import; isolated IndexedDB/,run.stdout.match(/<pre id="result">([\s\S]*?)<\/pre>/)?.[1]||run.stderr.slice(-2000));
  console.log('Broadcast exchange: native import → export → copy import passed in isolated Chrome IndexedDB.');
} finally {
                                                                                             
  if(path.dirname(temp)===os.tmpdir()&&path.basename(temp).startsWith('mi-broadcast-rainoc-'))fs.rmSync(temp,{recursive:true,force:true,maxRetries:5,retryDelay:200});
}
