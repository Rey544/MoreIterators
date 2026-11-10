import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {pathToFileURL} from 'node:url';
const [chrome,document,profile,hoverSelector]=process.argv.slice(2),sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const browser=spawn(chrome,['--headless','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-background-timer-throttling','--remote-debugging-address=127.0.0.1','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:['ignore','ignore','pipe']});
let stderr='',socket;browser.stderr.on('data',chunk=>stderr+=chunk);
try{
 const file=path.join(profile,'DevToolsActivePort');for(let i=0;i<200&&!fs.existsSync(file);i++)await sleep(50);if(!fs.existsSync(file))throw Error(stderr);
 const port=fs.readFileSync(file,'utf8').split(/\r?\n/)[0],pages=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();socket=new WebSocket(pages.find(page=>page.type==='page').webSocketDebuggerUrl);await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
 let serial=0;const pending=new Map(),events=new Map();socket.onmessage=event=>{const data=JSON.parse(event.data);if(data.id){const item=pending.get(data.id);pending.delete(data.id);data.error?item.reject(Error(JSON.stringify(data.error))):item.resolve(data.result);}else if(events.has(data.method)){events.get(data.method)(data.params);events.delete(data.method);}};
 const call=(method,params={})=>new Promise((resolve,reject)=>{const id=++serial;pending.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params}));});
 await call('Page.enable');const loaded=new Promise(resolve=>events.set('Page.loadEventFired',resolve));await call('Page.navigate',{url:pathToFileURL(document).href});await loaded;
 if(hoverSelector){
  await call('DOM.enable');await call('CSS.enable');const {root}=await call('DOM.getDocument'),{nodeId}=await call('DOM.querySelector',{nodeId:root.nodeId,selector:hoverSelector});
  if(!nodeId)throw Error('Hover test element is missing: '+hoverSelector);
  await call('CSS.forcePseudoState',{nodeId,forcedPseudoClasses:['hover']});await call('Runtime.evaluate',{expression:'window.hoverReady=true'});
 }
 const result=await call('Runtime.evaluate',{expression:"new Promise((resolve,reject)=>{let count=0;function check(){const node=document.getElementById('result');if(node&&node.textContent!=='PENDING')return resolve(node.textContent);if(++count>500)return reject(Error('Browser test did not complete'));setTimeout(check,20);}check();})",awaitPromise:true,returnByValue:true});if(result.exceptionDetails)throw Error(result.exceptionDetails.exception?.description||JSON.stringify(result.exceptionDetails));console.log(result.result.value);
}finally{socket?.close();browser.kill();await sleep(400);}
