import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {fileURLToPath,pathToFileURL} from 'node:url';
const out=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../evidence/room-picker'),profile=fs.mkdtempSync(path.join(out,'profile-'));
const browser=spawn('C:/Program Files/Google/Chrome/Application/chrome.exe',['--headless','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-background-timer-throttling','--remote-debugging-address=127.0.0.1','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:['ignore','ignore','pipe']});
let stderr='';browser.stderr.on('data',chunk=>stderr+=chunk);const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));let socket;
try{
 const file=path.join(profile,'DevToolsActivePort');for(let i=0;i<200&&!fs.existsSync(file);i++)await sleep(50);if(!fs.existsSync(file))throw Error(stderr);
 const port=fs.readFileSync(file,'utf8').split(/\r?\n/)[0],pages=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();socket=new WebSocket(pages.find(page=>page.type==='page').webSocketDebuggerUrl);await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
 let serial=0;const pending=new Map(),events=new Map();socket.onmessage=event=>{const data=JSON.parse(event.data);if(data.id){const item=pending.get(data.id);pending.delete(data.id);if(data.error)item.reject(Error(JSON.stringify(data.error)));else item.resolve(data.result);}else if(events.has(data.method)){events.get(data.method)(data.params);events.delete(data.method);}};
 const call=(method,params={})=>new Promise((resolve,reject)=>{const id=++serial;pending.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params}));});
 const evaluate=async expression=>{const result=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(result.exceptionDetails)throw Error(result.exceptionDetails.exception?.description||JSON.stringify(result.exceptionDetails));return result.result.value;};
 await call('Page.enable');await call('Emulation.setDeviceMetricsOverride',{width:1320,height:900,deviceScaleFactor:1,mobile:false});
 const targets=[['picker','zh-CN'],['picker','en'],['connection','zh-CN'],['connection','en'],['broadcast','zh-CN'],['broadcast','en']];
 const results=[];for(const[kind,locale]of targets){
  const name=kind+'-'+locale+'.html',loaded=new Promise(resolve=>events.set('Page.loadEventFired',resolve));await call('Page.navigate',{url:pathToFileURL(path.join(out,name)).href+'?lang='+locale});await loaded;await evaluate('window.previewReady');
  const result=await evaluate(kind==='picker'?'runRoomPickerTests()':kind==='connection'?'runConnectionTests()':'runBroadcastPickerTests()');results.push({kind,locale,...result});
  if(kind==='picker'){await evaluate("resetRoomPreview();waitFor(()=>document.querySelector('.rp-hint')?.textContent===MI18n.text('相机预览'))");}else if(kind==='connection'){await evaluate("fixtureLive=true;document.querySelector('#refreshCatalog').click()");await sleep(100);}
  const screenshot=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});fs.writeFileSync(path.join(out,kind+'-'+locale+'.png'),Buffer.from(screenshot.data,'base64'));
 }
 fs.writeFileSync(path.join(out,'test-results.json'),JSON.stringify(results,null,2));console.log(JSON.stringify(results,null,2));
}finally{socket?.close();browser.kill();await sleep(400);if(path.dirname(fs.realpathSync(profile))===fs.realpathSync(out))try{fs.rmSync(profile,{recursive:true,force:true});}catch{}}
