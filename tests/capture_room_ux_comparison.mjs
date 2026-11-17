import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {spawn} from 'node:child_process';
import {pathToFileURL} from 'node:url';
const out=path.resolve(process.argv[2]),profile=fs.mkdtempSync(path.join(os.tmpdir(),'mi-room-comparison-')),sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const browser=spawn('C:/Program Files/Google/Chrome/Application/chrome.exe',['--headless','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-background-networking','--remote-debugging-address=127.0.0.1','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:['ignore','ignore','pipe']});
let socket,stderr='';browser.stderr.on('data',chunk=>stderr+=chunk);
try{
 const file=path.join(profile,'DevToolsActivePort');for(let i=0;i<200&&!fs.existsSync(file);i++)await sleep(50);if(!fs.existsSync(file))throw Error(stderr);
 const port=fs.readFileSync(file,'utf8').split(/\r?\n/)[0],pages=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();socket=new WebSocket(pages.find(page=>page.type==='page').webSocketDebuggerUrl);await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
 let serial=0;const pending=new Map(),events=new Map();socket.onmessage=event=>{const data=JSON.parse(event.data);if(data.id){const item=pending.get(data.id);pending.delete(data.id);data.error?item.reject(Error(JSON.stringify(data.error))):item.resolve(data.result);}else if(events.has(data.method)){events.get(data.method)(data.params);events.delete(data.method);}};
 const call=(method,params={})=>new Promise((resolve,reject)=>{const id=++serial;pending.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params}));});
 const evaluate=async expression=>{const value=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(value.exceptionDetails)throw Error(value.exceptionDetails.exception?.description||JSON.stringify(value.exceptionDetails));return value.result.value;};
 await call('Page.enable');await call('Emulation.setDeviceMetricsOverride',{width:1320,height:900,deviceScaleFactor:1,mobile:false});
 const results=[];
 for(const version of ['old','new']){
  const loaded=new Promise(resolve=>events.set('Page.loadEventFired',resolve));await call('Page.navigate',{url:pathToFileURL(path.join(out,version+'.html')).href});await loaded;
  const ready=await evaluate('window.comparisonReady');if(!ready?.ok||ready.errors.length)throw Error(JSON.stringify(ready));
  const summary=await evaluate(`({fields:['region','ai','entry'].map(id=>({id,value:document.getElementById(id).value,visible:document.getElementById(id).checkVisibility()})),primary:[...document.querySelectorAll('#bindingForm button')].filter(node=>node.checkVisibility()).map(node=>node.textContent),secondary:[...document.querySelectorAll('main details')].map(node=>({id:node.id,open:node.open})),width:document.documentElement.scrollWidth,viewport:innerWidth})`);
  const shot=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});fs.writeFileSync(path.join(out,version+'.png'),Buffer.from(shot.data,'base64'));
  if(version==='new'){
   await call('Emulation.setDeviceMetricsOverride',{width:460,height:800,deviceScaleFactor:1,mobile:false});
   summary.narrow=await evaluate(`({width:document.documentElement.scrollWidth,viewport:innerWidth,fields:['region','ai','entry'].every(id=>document.getElementById(id).checkVisibility()),primary:document.getElementById('applyRoomNames').checkVisibility()})`);
   if(summary.narrow.width>summary.narrow.viewport||!summary.narrow.fields||!summary.narrow.primary)throw Error('The narrow names form is not usable');
  }
  results.push({version,...summary});
 }
 fs.writeFileSync(path.join(out,'comparison-checks.json'),JSON.stringify({ok:true,results},null,2));console.log(JSON.stringify({ok:true,results}));
}finally{socket?.close();browser.kill();await sleep(400);}
