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
  const projects=await(await fetch(base+'/api/projects')).json(),project=projects.find(p=>p.name==='PL');
  await call('Page.enable');await call('Runtime.enable');await call('Network.enable');await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
  await call('Page.navigate',{url:base+'/rooms?project='+encodeURIComponent(project.projectId)+'&lang=zh-CN'});
  await wait("document.getElementById('region')?.value==='PL'&&!document.getElementById('bindingFields').disabled");
  await evaluate('document.fonts.ready');await shot('old-real');
  check(await evaluate("document.getElementById('entryMode')!==null&&!document.getElementById('connectionWorkspace').open"),'Frozen baseline does not match the old workflow.');
  console.log(JSON.stringify({ok:true,checks,source:'frozen candidate',actualPage:'/rooms',errors}));
}finally{socket?.close();browser.kill();await sleep(400);}
