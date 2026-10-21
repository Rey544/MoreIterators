"use strict";
const VoiceAudio=(()=>{
 let context=null,serial=0,playing=false,timer=null,nodes=[],sources=[],callback=null;const buffers=new Map();
 function state(value){callback?.(value);}
 function stop(){serial++;playing=false;clearTimeout(timer);for(const source of sources){try{source.stop();}catch{}}for(const node of nodes){try{node.disconnect();}catch{}}sources=[];nodes=[];state('stopped');callback=null;}
 const own=node=>(nodes.push(node),node);
 function curve(amount){const k=amount*80,values=new Float32Array(1024);for(let i=0;i<values.length;i++){const x=i*2/(values.length-1)-1;values[i]=(1+k)*x/(1+k*Math.abs(x));}return values;}
 async function load(bank){
  if(!buffers.has(bank))buffers.set(bank,Promise.all(Array.from({length:5},async(_,index)=>{
   const response=await fetch('/api/voice-sample?bank='+encodeURIComponent(bank)+'&index='+index);
   if(!response.ok){let message='无法读取原版声音，请检查游戏路径';try{message=(await response.json()).error||message;}catch{}throw Error(message);}
   return context.decodeAudioData(await response.arrayBuffer());
  })).catch(error=>{buffers.delete(bank);throw error;}));
  return buffers.get(bank);
 }
 async function play(text,settings,onstate){
  stop();const request=serial;callback=onstate;state('loading');
  try{
   const Type=globalThis.AudioContext||globalThis.webkitAudioContext;if(!Type)throw Error('此浏览器不支持声音预览');
   context??=new Type();await context.resume();const bank=await load(settings.bank);if(request!==serial)return;
   const plan=VoiceSequence.make(text,settings);if(!plan.notes.length)throw Error('请先选择或输入一段台词');
   const base=context.currentTime+.04;
   for(const note of plan.notes){
    const source=own(context.createBufferSource()),gain=own(context.createGain());sources.push(source);source.buffer=bank[note.sample];source.playbackRate.value=note.pitch;
    const offset=Math.min(note.offset,Math.max(0,source.buffer.duration-.08));
    const start=base+note.start/40,duration=Math.max(.01,Math.min(note.ticks/40,(source.buffer.duration-offset)/note.pitch-.06)),end=start+duration;
    let tail=source;
    if(settings.muffle>0){const low=own(context.createBiquadFilter());low.type='lowpass';low.frequency.value=18000*Math.pow(650/18000,settings.muffle);low.Q.value=1;tail.connect(low);tail=low;}
    if(settings.electric>0){const shaper=own(context.createWaveShaper());shaper.curve=curve(settings.electric*.8);shaper.oversample='2x';tail.connect(shaper);tail=shaper;}
    tail.connect(gain);
    if(settings.echo>0){const delay=own(context.createDelay(1)),feedback=own(context.createGain()),wet=own(context.createGain());delay.delayTime.value=.18;feedback.gain.value=.25+.3*settings.echo;wet.gain.value=.45*settings.echo;tail.connect(delay);delay.connect(feedback);feedback.connect(delay);delay.connect(wet);wet.connect(gain);}
    const nativeVolume=settings.bank==='moon'?.5:note.sample===1?.6:.7,level=settings.volume*nativeVolume;
    gain.gain.setValueAtTime(0,start);gain.gain.linearRampToValueAtTime(level,start+Math.min(.05,duration/2));gain.gain.setValueAtTime(level,Math.max(start+duration/2,end-.05));gain.gain.linearRampToValueAtTime(0,end);gain.connect(context.destination);
    source.start(start,offset);source.stop(end);
   }
   playing=true;state('playing');timer=setTimeout(()=>{if(request===serial)stop();},plan.ticks*25+100);
   return plan;
  }catch(error){if(request===serial){stop();onstate?.('error',error);throw error;}}
 }
 return {play,stop,get playing(){return playing;},get active(){return callback!==null;},curve};
})();
