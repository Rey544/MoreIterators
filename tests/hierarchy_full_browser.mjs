import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {isDeepStrictEqual} from 'node:util';
const [chrome,base,profile,evidence,projectId='hierarchy-fixture',evidenceKind='full']=process.argv.slice(2),sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const browser=spawn(chrome,['--headless','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-background-timer-throttling','--remote-debugging-address=127.0.0.1','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:['ignore','ignore','pipe']});
let stderr='',socket;browser.stderr.on('data',chunk=>stderr+=chunk);
try{
 const file=path.join(profile,'DevToolsActivePort');for(let i=0;i<200&&!fs.existsSync(file);i++)await sleep(50);if(!fs.existsSync(file))throw Error(stderr);
 const port=fs.readFileSync(file,'utf8').split(/\r?\n/)[0],pages=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();socket=new WebSocket(pages.find(page=>page.type==='page').webSocketDebuggerUrl);await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
 let serial=0;const pending=new Map(),errors=[],networkErrors=[];socket.onmessage=event=>{const data=JSON.parse(event.data);if(data.id){const item=pending.get(data.id);pending.delete(data.id);data.error?item.reject(Error(JSON.stringify(data.error))):item.resolve(data.result);}else if(data.method==='Runtime.exceptionThrown')errors.push(data.params.exceptionDetails.exception?.description||data.params.exceptionDetails.text);else if(data.method==='Runtime.consoleAPICalled'&&data.params.type==='error')errors.push(data.params.args.map(value=>value.description||value.value).join(' '));else if(data.method==='Network.responseReceived'&&data.params.response.status>=400)networkErrors.push({url:data.params.response.url.replace(base,''),status:data.params.response.status});};
 const call=(method,params={})=>new Promise((resolve,reject)=>{const id=++serial;pending.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params}));});
 const evaluate=async expression=>{const value=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(value.exceptionDetails)throw Error(value.exceptionDetails.exception?.description||JSON.stringify(value.exceptionDetails));return value.result.value;};
 await call('Page.enable');await call('Runtime.enable');await call('Network.enable');await call('Emulation.setDeviceMetricsOverride',{width:1366,height:960,deviceScaleFactor:1,mobile:false});await call('Page.navigate',{url:base+'/?project='+encodeURIComponent(projectId)+'&lang=zh-CN'});
 for(let i=0;i<600;i++){if(await evaluate("typeof project!=='undefined'&&project?.projectId==="+JSON.stringify(projectId)+"&&!loading&&!document.getElementById('save').disabled&&document.getElementById('chamberPreset').options.length===6"))break;if(i===599)throw Error('Full appearance page failed to become ready: '+JSON.stringify({errors,networkErrors}));await sleep(50);}
 let checks=0;const check=(value,message)=>{checks++;if(!value)throw Error(message);};
 const initial=await evaluate('JSON.stringify(project.design)');const originalFile=await(await fetch(base+'/api/projects')).json();
 check(await evaluate("$('projectName').value===project.name&&!!project.name&&$('chamberPreset').options.length===6&&$('chamberPreset').value===''&&$('replaceChamberPreset').disabled"),'Full project or current chamber selection is not usable');
 check(await evaluate("!document.querySelector('[data-section-id=chamber]').open&&!document.querySelector('[data-section-id=waiting]').open&&!document.querySelector('[data-section-id=chamberPresets]').open"),'Room controls should start folded');
 await evaluate("$('chamberPreset').value='mi-chamber-moon';$('chamberPreset').dispatchEvent(new Event('change'))");
 for(let i=0;i<200;i++){if(await evaluate("$('chamberPresetPreview').complete&&$('chamberPresetPreview').naturalWidth>0"))break;await sleep(20);}
 check(await evaluate("$('chamberPresetPreview').complete&&$('chamberPresetPreview').naturalWidth>0&&$('chamberSize').value==='original'&&!$('replaceChamberPreset').disabled"),'Real native chamber preview or sizes failed to load');
 check(await evaluate("document.querySelector('[data-section-id=iteratorVoice]').parentElement===$('groups')&&document.querySelector('[data-section-id=sleeves]').closest('[data-section-id=clothes]')"),'Actual full-page hierarchy differs from isolated controls');
 check(await evaluate("$('puppet').width>0&&$('paint').width>0&&canvases.forehead.length>0"),'Offline puppet or paint workspace failed');
 for(const locale of ['zh-CN','en']){
  await evaluate('MI18n.setLocale('+JSON.stringify(locale)+',false)');await sleep(180);
  await evaluate("document.querySelectorAll('#settings details').forEach(node=>node.open=false);document.querySelector('[data-section-id=chamber]').open=true;document.querySelector('[data-section-id=roomPalette]').open=true;$('settings').scrollTop=0;window.scrollTo(0,0)");
  check(await evaluate('JSON.stringify(project.design)')===initial,'Language/layout changed design values');
  check(await evaluate('!dirty&&!MIUndo.state.undo'),'Read-only hierarchy interactions changed dirty/history state');
  check(await evaluate('document.documentElement.scrollWidth<=innerWidth+1'),'Full desktop page overflows horizontally');
  const shot=await call('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(evidence,'appearance-'+evidenceKind+'-'+locale+'-1366.png'),Buffer.from(shot.data,'base64'));
  await evaluate("(()=>{document.querySelector('[data-section-id=chamber]').open=false;document.querySelector('[data-section-id=waiting]').open=false;const clothes=document.querySelector('[data-section-id=clothes]');clothes.open=true;document.querySelector('[data-section-id=sleeves]').open=true;document.querySelector('[data-section-id=sleevePair0]').open=true;document.querySelector('[data-section-id=puppetSleeve0]').open=true;$('settings').scrollTop+=clothes.getBoundingClientRect().top-$('settings').getBoundingClientRect().top;window.scrollTo(0,0);})()");await sleep(50);
  const sleeves=await call('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(evidence,'appearance-'+evidenceKind+'-sleeves-'+locale+'-1366.png'),Buffer.from(sleeves.data,'base64'));
 }
 check(JSON.stringify(await(await fetch(base+'/api/projects')).json())===JSON.stringify(originalFile),'Viewing hierarchy wrote saved JSON before save');
 const pixels=await evaluate("Object.fromEntries(Object.entries(canvases).map(([key,layers])=>[key,layers.map(canvas=>canvas.toDataURL())]))");
 const puppet=await evaluate("render();$('puppet').toDataURL()");
 await evaluate('save()');check(await evaluate('JSON.stringify(project.design)')===initial,'Saving changed design values');
 const saved=await(await fetch(base+'/api/projects')).json(),differences=Object.fromEntries([...new Set([...Object.keys(saved[0].design),...Object.keys(originalFile[0].design)])].filter(key=>!isDeepStrictEqual(saved[0].design[key],originalFile[0].design[key])).map(key=>[key,{before:originalFile[0].design[key],after:saved[0].design[key]}]));
 if(evidenceKind==='raw-default'){
  const expected=['antennaInner','antennaOuter','antennaLowerInner','antennaLowerOuter','earInner','earOuter','earDecorationInner','earDecorationOuter'].map(key=>key+'Mode').concat('puppetSleeveSyncSeparated');check(isDeepStrictEqual(Object.keys(differences).sort(),expected.sort()),'Unexpected old default normalization fields: '+JSON.stringify(Object.keys(differences)));
  for(const [key,value]of Object.entries(differences))check(key==='puppetSleeveSyncSeparated'?value.before===false&&value.after===true:value.before===''&&value.after===(['antennaInnerMode','antennaOuterMode'].includes(key)?'solid':'original'),'Unexpected mode normalization '+key);
 }else check(!Object.keys(differences).length,'Saved design differs from original: '+JSON.stringify(differences));
 await evaluate('(async()=>load((await api("projects")).find(item=>item.projectId===project.projectId)))()');check(await evaluate('JSON.stringify(project.design)')===initial,'Reload changed design values');
 check(isDeepStrictEqual(await evaluate("Object.fromEntries(Object.entries(canvases).map(([key,layers])=>[key,layers.map(canvas=>canvas.toDataURL())]))"),pixels),'Reload changed decoded texture pixels');
 check(await evaluate("render();$('puppet').toDataURL()")===puppet,'Reload changed offline puppet rendering');
 check(errors.length===0,'Browser console errors: '+JSON.stringify(errors));check(networkErrors.every(item=>item.url==='/favicon.ico'&&item.status===404),'Failed resources: '+JSON.stringify(networkErrors));
 console.log(JSON.stringify({ok:true,checks,errors,networkErrors,realServer:true,isolatedData:true,designRoundtrip:true,normalizedFields:Object.keys(differences),normalization:differences,texturePixelsUnchanged:true,puppetPixelsUnchanged:true,textureCount:Object.keys(pixels).length}));
}finally{socket?.close();browser.kill();await sleep(400);}
