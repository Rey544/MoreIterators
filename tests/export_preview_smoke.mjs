import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {spawn} from 'node:child_process';
import {fileURLToPath,pathToFileURL} from 'node:url';
import assert from 'node:assert/strict';

const folder=fileURLToPath(new URL('../../evidence/export-multi/',import.meta.url)),temporary=fs.mkdtempSync(path.join(os.tmpdir(),'mi-export-preview-')),profile=path.join(temporary,'profile');
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const browser=spawn('C:/Program Files/Google/Chrome/Application/chrome.exe',['--headless','--disable-gpu','--no-first-run','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:'ignore'});
let socket,call;
try{
 const portFile=path.join(profile,'DevToolsActivePort');for(let index=0;index<200&&!fs.existsSync(portFile);index++)await sleep(20);
 const port=fs.readFileSync(portFile,'utf8').split(/\r?\n/)[0],tabs=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();socket=new WebSocket(tabs.find(tab=>tab.type==='page').webSocketDebuggerUrl);await new Promise(resolve=>socket.onopen=resolve);
 let serial=0;const tasks=new Map();socket.onmessage=event=>{const message=JSON.parse(event.data);if(message.id){const task=tasks.get(message.id);tasks.delete(message.id);message.error?task.reject(Error(JSON.stringify(message.error))):task.resolve(message.result);}};
 call=(method,params={})=>new Promise((resolve,reject)=>{const id=++serial;tasks.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params}));});
 const evaluate=async expression=>{const response=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(response.exceptionDetails)throw Error(response.exceptionDetails.exception?.description||response.exceptionDetails.text);return response.result.value;};
 const until=async expression=>{for(let index=0;index<200;index++){if(await evaluate(expression))return;await sleep(20)}throw Error('Preview timeout: '+expression);};
 await call('Page.enable');
 await call('Page.navigate',{url:pathToFileURL(path.join(folder,'可操作预览.html')).href});await until('!!window.previewReady');await evaluate('previewReady');assert.equal(await evaluate(`document.getElementById('exportDialog').open`),true);
 for(const [count,format]of [[3,'project'],[5,'project'],[12,'project'],[5,'mod'],[5,'playable']]){await evaluate(`choosePreview(${count},${JSON.stringify(format)})`);assert.equal(await evaluate(`document.querySelectorAll('#pack-projects input').length`),count);assert.equal(await evaluate(`document.querySelector('[name=exportFormat]:checked').value`),format);assert.deepEqual(await evaluate('previewErrors'),[]);}
 await call('Page.navigate',{url:pathToFileURL(path.join(folder,'预览.html')).href});await until(`document.querySelector('[data-view="3"]')!==null`);await evaluate(`document.querySelector('[data-view="3"]').click()`);await until(`document.getElementById('view').complete&&document.getElementById('view').naturalWidth>0`);assert.equal(await evaluate(`document.getElementById('view').getAttribute('src')`),'项目ZIP-12个作品-面板.png');assert.equal(await evaluate(`document.body.textContent.includes('导入')`),false);
 await evaluate(`document.querySelector('[data-view="0"]').click()`);await until(`document.getElementById('view').complete&&document.getElementById('view').naturalWidth>0`);assert.equal(await evaluate(`document.getElementById('view').getAttribute('src')`),'改前-多个项目-面板.png');
 await call('Emulation.setDeviceMetricsOverride',{width:1480,height:820,deviceScaleFactor:1,mobile:false});await call('Page.navigate',{url:pathToFileURL(path.join(folder,'改前改后.html')).href});await until(`document.querySelectorAll('main img').length===2&&[...document.querySelectorAll('main img')].every(img=>img.complete&&img.naturalWidth>0)`);const comparison=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});fs.writeFileSync(path.join(folder,'改前改后.png'),Buffer.from(comparison.data,'base64'));
 fs.writeFileSync(path.join(folder,'preview-smoke.json'),JSON.stringify({ok:true,localFile:true,threeFiveTwelveProjects:true,standaloneAndPlayableOpen:true,noImportPreview:true,beforeAfterPreserved:true,navigationWorks:true},null,2));console.log('Local HTML previews open and navigation works.');
}finally{
 if(call)await Promise.race([call('Browser.close').catch(()=>{}),sleep(2000)]);socket?.close();browser.kill();await sleep(500);
 const target=path.resolve(temporary);if(path.dirname(target)!==path.resolve(os.tmpdir())||!path.basename(target).startsWith('mi-export-preview-'))throw Error('Unexpected temporary path');fs.rmSync(target,{recursive:true,force:true,maxRetries:10,retryDelay:200});
}
