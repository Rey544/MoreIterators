import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {spawn} from 'node:child_process';

const [chrome,base,profile,evidence]=process.argv.slice(2);
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const browser=spawn(chrome,['--headless','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-background-timer-throttling','--remote-debugging-address=127.0.0.1','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:['ignore','ignore','pipe']});
let stderr='',socket;
browser.stderr.on('data',chunk=>stderr+=chunk);
try{
  const file=path.join(profile,'DevToolsActivePort');
  for(let i=0;i<200&&!fs.existsSync(file);i++)await sleep(50);
  if(!fs.existsSync(file))throw Error(stderr);
  const port=fs.readFileSync(file,'utf8').split(/\r?\n/)[0],pages=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();
  socket=new WebSocket(pages.find(page=>page.type==='page').webSocketDebuggerUrl);
  await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
  let serial=0,checks=0;
  const pending=new Map(),errors=[],networkErrors=[],writes=[],maps=[];
  socket.onmessage=event=>{
    const data=JSON.parse(event.data);
    if(data.id){const item=pending.get(data.id);pending.delete(data.id);data.error?item.reject(Error(JSON.stringify(data.error))):item.resolve(data.result);}
    else if(data.method==='Runtime.exceptionThrown')errors.push(data.params.exceptionDetails.exception?.description||data.params.exceptionDetails.text);
    else if(data.method==='Network.responseReceived'&&data.params.response.status>=400)networkErrors.push({url:data.params.response.url.replace(base,''),status:data.params.response.status});
    else if(data.method==='Network.requestWillBeSent'){
      const request=data.params.request;
      if(request.method==='POST')writes.push({url:request.url.replace(base,''),data:request.postData?JSON.parse(request.postData):null});
      if(request.url.includes('/api/room-picker-map?'))maps.push(new URL(request.url).searchParams.toString());
    }
  };
  const call=(method,params={})=>new Promise((resolve,reject)=>{const id=++serial;pending.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params}));});
  const evaluate=async expression=>{const value=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(value.exceptionDetails)throw Error(value.exceptionDetails.exception?.description||JSON.stringify(value.exceptionDetails));return value.result.value;};
  const wait=async expression=>{for(let i=0;i<600;i++){if(await evaluate(expression))return;await sleep(50);}throw Error('Timeout: '+expression+' '+JSON.stringify({errors,networkErrors}));};
  const check=(value,message)=>{checks++;if(!value)throw Error(message);};
  const input=async(id,value)=>{await evaluate(`(()=>{const input=document.getElementById(${JSON.stringify(id)});input.value=${JSON.stringify(value)};input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));})()`);};
  const click=async selector=>{
    const rect=await evaluate(`(()=>{const element=document.querySelector(${JSON.stringify(selector)});if(!element||element.disabled)throw Error('Unavailable control: '+${JSON.stringify(selector)});element.scrollIntoView({block:'center'});const r=element.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
    await call('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...rect});
    await call('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...rect});
  };
  const shot=async name=>{const value=await call('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(evidence,name+'.png'),Buffer.from(value.data,'base64'));};
  const json=async route=>{const response=await fetch(base+route);if(!response.ok)throw Error(await response.text());return response.json();};
  const projects=await json('/api/projects'),project=projects.find(p=>p.name==='PL workflow fixture'),pid=project.projectId;
  const binding=await json('/api/room-binding?projectId='+encodeURIComponent(pid)),health=await json('/api/health');
  const data=path.resolve(health.dataDirectory),fixtureRoot=path.dirname(data);
  if(!path.basename(fixtureRoot).startsWith('mi-pl-workflow-')||path.basename(data)!=='data')throw Error('The browser test requires isolated fixture data.');
  const projectRoot=path.join(data,'projects',pid),projectFile=path.join(projectRoot,'project.json');
  function snapshot(){
    const hashes={};const roots=[path.join(projectRoot,'rooms'),path.join(projectRoot,'rendered'),path.join(data,'local-mod'),path.join(fixtureRoot,'game/RainWorld_Data/StreamingAssets/mods')];
    const read=root=>{if(!fs.existsSync(root))return;for(const row of fs.readdirSync(root,{withFileTypes:true})){const file=path.join(root,row.name);if(row.isDirectory())read(file);else if(row.isFile())hashes[path.relative(fixtureRoot,file)]=createHash('sha256').update(fs.readFileSync(file)).digest('hex');}};
    roots.forEach(read);hashes.project=createHash('sha256').update(fs.readFileSync(projectFile)).digest('hex');return hashes;
  }
  const fixtureProject=JSON.parse(fs.readFileSync(projectFile,'utf8'));fixtureProject.name='PL';
  fs.writeFileSync(projectFile,JSON.stringify(fixtureProject));
  const initial=snapshot(),initialNames=binding.binding;
  const url=base+'/rooms?project='+encodeURIComponent(pid)+'&lang=zh-CN';
  await call('Page.enable');await call('Runtime.enable');await call('Network.enable');
  await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
  await call('Page.navigate',{url});
  await wait("document.getElementById('region')&&!document.getElementById('bindingFields').disabled&&!document.getElementById('applyRoomNames').disabled");
  check(await evaluate("document.getElementById('region').value==='TEST'"),'Fixture must begin in TEST.');
  check(await evaluate("document.getElementById('connectionWorkspace').tagName==='SECTION'&&!document.getElementById('overseerWorkspace').open&&!document.getElementById('entryMode')&&!document.getElementById('previewBinding')&&!document.getElementById('applyBinding')"),'Both tasks must be visible without the old combined workflow.');
  check(await evaluate("Math.abs(document.getElementById('ownedNode').getBoundingClientRect().top-document.getElementById('targetNode').getBoundingClientRect().top)<2"),'The two exit controls are not aligned.');
  await shot('actual-default');
  await input('region','PL_');await input('ai','AI');await input('entry','POOL');await click('#applyRoomNames');await sleep(80);
  check(writes.length===0,'Invalid identity reached backend.');
  check(await evaluate("document.getElementById('regionError').textContent.includes('PL')&&document.getElementById('aiError').textContent.includes('PL_AI')"),'Name fields lack exact feedback.');
  await input('region','PL');await input('ai','PL_AI');await input('entry','PL_POOL');await click('#applyRoomNames');
  await wait("document.getElementById('nameStatus').textContent==='待重新连接'&&!document.getElementById('connectionFields').disabled");
  const pendingState=await json('/api/room-workflow?projectId='+encodeURIComponent(pid));
  check(pendingState.pending?.names.ai==='PL_AI'&&pendingState.pending?.required.length>0,'The real backend did not stage names and required connections.');
  check(JSON.stringify(snapshot())===JSON.stringify(initial),'Names changed active source, output, or project files.');
  check(writes.filter(item=>item.url==='/api/room-workflow/names').length===1&&!writes.some(item=>item.url==='/api/room-workflow/apply'),'Name action also applied a connection.');
  check(await evaluate("document.getElementById('targetRoom').value===''&&document.getElementById('ownedNode').value===''&&document.getElementById('targetNode').value===''&&!document.getElementById('priorConnections').open"),'Staged rename preselected old exits.');
  check(await evaluate("Math.abs(document.getElementById('ownedNode').getBoundingClientRect().top-document.getElementById('targetNode').getBoundingClientRect().top)<2"),'Pending labels misalign the exit controls.');
  await evaluate('window.scrollTo(0,0)');await shot('actual-pending');
  await call('Page.navigate',{url});await wait("document.getElementById('nameStatus')?.textContent==='待重新连接'&&!document.getElementById('connectionFields').disabled");
  check(await evaluate("document.getElementById('ai').value==='PL_AI'&&document.getElementById('bindingFields').disabled"),'Reload lost staged names.');
  const required=pendingState.pending.required;
  check(required.length===1,'The baseline fixture unexpectedly requires multiple reconnections.');
  const from=required[0].room,to=required[0].toRoom;
  await evaluate(`(()=>{const button=[...document.querySelectorAll('#ownRoomChoices button')].find(item=>item.firstChild.textContent===${JSON.stringify(from)});button.click();})()`);
  await input('targetRoom',to);await input('ownedNode',String(required[0].node));await input('targetNode',String(required[0].toNode));
  await click('#ownedRoomPreview button');await wait("document.querySelector('dialog.mi-room-picker .rp-detail h3')?.textContent==="+JSON.stringify(initialNames.ai)+"&&document.querySelector('dialog.mi-room-picker .rp-hint')?.textContent==='相机预览'");
  check(new URLSearchParams(maps.at(-1)).get('region')==='TEST','Pending copy preview could not use the old source.');await click('dialog.mi-room-picker header button');
  const originalFile=path.join(projectRoot,'rooms',initialNames.ai+'.txt'),bytes=fs.readFileSync(originalFile);
  fs.writeFileSync(originalFile,Buffer.concat([bytes,Buffer.from('\nfixture source change\n')]));
  try{await click('#applyConnection');await wait("document.getElementById('connectionError').textContent.includes('已改变')&&!document.getElementById('connectionFields').disabled");}
  finally{fs.writeFileSync(originalFile,bytes);}
  check(JSON.stringify(snapshot())===JSON.stringify(initial),'A rejected connection removed or changed old files.');
  check((await json('/api/room-workflow?projectId='+encodeURIComponent(pid))).pending!==null,'A failed connection discarded the pending rename.');
  check(await evaluate("document.getElementById('targetRoom').value==='PL_POOL'&&document.getElementById('ownedNode').value!==''"),'Failure discarded selected endpoints.');
  await evaluate('window.scrollTo(0,0)');await shot('actual-conflict');
  await click('#applyConnection');await wait("!document.getElementById('connectionFields').disabled&&(document.getElementById('connectionStatus').textContent==='连接已应用。'||document.getElementById('connectionError').textContent)");
  check(await evaluate("!document.getElementById('connectionError').textContent"),'Real connection rejected: '+await evaluate("document.getElementById('connectionError').textContent"));
  const saved=await json('/api/room-workflow?projectId='+encodeURIComponent(pid));
  check(saved.binding.region==='PL'&&saved.binding.ai==='PL_AI'&&saved.binding.entry==='PL_POOL'&&!saved.pending,'Explicit connection did not activate PL.');
  check(saved.rooms.filter(room=>room.owned).some(room=>room.name==='PL_POOL'),'The waiting room was removed during connection.');
  check(!fs.existsSync(originalFile),'Old source was left after successful reconnection.');
  check(fs.existsSync(path.join(projectRoot,'rooms/PL_AI.txt'))&&fs.existsSync(path.join(projectRoot,'rooms/PL_POOL.txt')),'New room sources were not activated.');
  const backups=fs.readdirSync(path.join(projectRoot,'room-backups')).map(name=>path.join(projectRoot,'room-backups',name,'source',initialNames.ai+'.txt')).filter(file=>fs.existsSync(file));
  check(backups.some(file=>fs.readFileSync(file).equals(bytes)),'Old source is not preserved in its backup.');
  check(writes.filter(item=>item.url==='/api/room-workflow/apply').length===2&&!writes.some(item=>item.url.startsWith('/api/room-binding/')),'UI used an unintended combined or repeated apply request.');
  await evaluate('window.scrollTo(0,0)');await shot('actual-success');
  await call('Page.navigate',{url});await wait("document.getElementById('region')?.value==='PL'&&!document.getElementById('bindingFields').disabled");
  check(await evaluate("document.getElementById('entry').value==='PL_POOL'&&document.getElementById('draftPairRow').hidden"),'Reload restored old room names or a stale draft.');
  const draft=await json('/api/room-draft?projectId='+encodeURIComponent(pid));check(draft.binding===null,'Successful connection retained an obsolete draft.');
  await evaluate('window.scrollTo(0,0)');await shot('actual-reloaded');
  await evaluate("document.querySelector('#ownRoomChoices button').click()");await click('#ownedRoomPreview button');await wait("document.querySelector('dialog.mi-room-picker .rp-detail h3')?.textContent==='PL_AI'&&document.querySelector('dialog.mi-room-picker .rp-hint')?.textContent==='相机预览'");
  check(new URLSearchParams(maps.at(-1)).get('region')==='PL','Applied source preview did not use PL.');await click('dialog.mi-room-picker header button');
  await call('Emulation.setDeviceMetricsOverride',{width:460,height:1000,deviceScaleFactor:1,mobile:false});await evaluate('window.scrollTo(0,0)');
  check(await evaluate('document.documentElement.scrollWidth<=innerWidth'),'Narrow page overflows horizontally.');await shot('actual-narrow');
  check(await evaluate("(()=>{const b=document.querySelector('#ownRoomChoices button'),label=b.querySelector('span');label.textContent='PL_'+ 'A'.repeat(64);b.title=label.textContent;return document.documentElement.scrollWidth<=innerWidth&&getComputedStyle(label).textOverflow==='ellipsis'&&b.title===label.textContent;})()"),'Long room IDs overflow or lose their full title.');
  check(errors.length===0,'Browser exceptions: '+JSON.stringify(errors));
  check(networkErrors.every(item=>item.url==='/favicon.ico'&&item.status===404||item.url==='/api/room-workflow/apply'&&item.status===400),'Unexpected failed requests: '+JSON.stringify(networkErrors));
  console.log(JSON.stringify({ok:true,checks,realServer:true,isolatedData:true,actualPage:'/rooms',savedBinding:saved.binding,required,writes:writes.map(item=>item.url),mapRequests:maps,errors,networkErrors}));

}finally{socket?.close();browser.kill();await sleep(400);}
