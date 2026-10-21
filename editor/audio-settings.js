"use strict";
const AudioSettings=(()=>{
 const fields=[['musicWork','工作状态'],['musicReception','接待状态'],['musicReading','读珍珠']];
 const blank=()=>({mode:'native',asset:'',name:'',volume:1,loop:true});
 function init(p){for(const [key] of fields)p.design[key]={...blank(),...p.design[key]};}
 async function importFile(file){
  if(!file||!file.name.toLowerCase().endsWith('.mp3'))throw Error(MI18n.text('仅支持 MP3'));
  if(file.size>10*1024*1024)throw Error(MI18n.text('MP3 最大为 10 MB'));
  const raw=await file.arrayBuffer(),AudioContext=window.AudioContext||window.webkitAudioContext;
  if(AudioContext){const context=new AudioContext();try{const clip=await context.decodeAudioData(raw.slice(0));if(clip.duration>600)throw Error(MI18n.text('音乐时长不能超过 10 分钟'));}finally{await context.close();}}
  const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).replace(/^data:[^;]*;/,'data:audio/mpeg;'));reader.onerror=reject;reader.readAsDataURL(file);});
  const response=await fetch('/api/audio/import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:file.name,data})});const result=await response.json();if(!response.ok)throw Error(result.error||MI18n.text('音乐导入失败'));return result.track;
 }
 function settings(parent,d){
  const owner=project,version=loadVersion;
  const section=garmentSection(parent,'背景音乐');section.dataset.sectionId='customMusic';
  for(const [key,title] of fields){
   const part=garmentSection(section,title),track=d[key]??=blank();
   garmentField(part,track,'mode','音乐来源','select',{native:'保持原版',custom:'自定义 MP3',silent:'静音'});
   const body=settingDependency(part,()=>track.mode==='custom');
   const name=document.createElement('span');name.className='hint';MI18n.content(name);name.textContent=track.name||'—';body.append(name);
   const input=document.createElement('input');input.type='file';input.accept='.mp3,audio/mpeg';input.hidden=true;body.append(input);
   garmentButton(body,'导入 MP3',()=>input.click());input.onchange=()=>run(async()=>{if(!input.files[0])return;const imported=await importFile(input.files[0]);if(project!==owner||loadVersion!==version)throw Error(MI18n.text('项目已切换，请重新导入。'));Object.assign(track,imported);name.textContent=track.name;buildSettings();changed();})();
   const preview=document.createElement('audio');preview.controls=true;preview.preload='none';preview.style.width='100%';if(track.asset)preview.src='/api/audio/'+track.asset+'.mp3';body.append(preview);
   garmentField(body,track,'volume','音量','range',0,1,.01);garmentField(body,track,'loop','循环播放','checkbox');
  }
 }
 return {fields,blank,init,importFile,settings};
})();
