import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {pathToFileURL} from 'node:url';
const [chrome,document,profile,evidence]=process.argv.slice(2),sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const browser=spawn(chrome,['--headless','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-background-timer-throttling','--remote-debugging-address=127.0.0.1','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:['ignore','ignore','pipe']});
let stderr='',socket;browser.stderr.on('data',chunk=>stderr+=chunk);
try{
 const file=path.join(profile,'DevToolsActivePort');for(let i=0;i<200&&!fs.existsSync(file);i++)await sleep(50);if(!fs.existsSync(file))throw Error(stderr);
 const port=fs.readFileSync(file,'utf8').split(/\r?\n/)[0],pages=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();socket=new WebSocket(pages.find(page=>page.type==='page').webSocketDebuggerUrl);await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
 let serial=0;const pending=new Map();socket.onmessage=event=>{const data=JSON.parse(event.data);if(data.id){const item=pending.get(data.id);pending.delete(data.id);data.error?item.reject(Error(JSON.stringify(data.error))):item.resolve(data.result);}};
 const call=(method,params={})=>new Promise((resolve,reject)=>{const id=++serial;pending.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params}));});
 await call('Page.enable');await call('Emulation.setDeviceMetricsOverride',{width:1366,height:960,deviceScaleFactor:1,mobile:false});await call('Page.navigate',{url:pathToFileURL(document).href});
 let result;
 for(let i=0;i<300;i++){const value=await call('Runtime.evaluate',{expression:"document.getElementById('result')?.textContent",returnByValue:true});if(value.result?.value&&value.result.value!=='PENDING'){result=JSON.parse(value.result.value);break;}await sleep(50);}
 if(!result)throw Error('Browser verification did not complete');
 for(const locale of ['zh-CN','en']){
  await call('Runtime.evaluate',{expression:'MI18n.setLocale('+JSON.stringify(locale)+',false)',awaitPromise:true});await sleep(100);
  for(const width of [1366,420]){await call('Emulation.setDeviceMetricsOverride',{width,height:960,deviceScaleFactor:1,mobile:false});await sleep(100);const image=await call('Page.captureScreenshot',{format:'png'});fs.writeFileSync(evidence+'-'+locale+'-'+width+'.png',Buffer.from(image.data,'base64'));}
 }
 console.log(JSON.stringify(result));
}finally{socket?.close();browser.kill();await sleep(400);}
