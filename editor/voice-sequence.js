"use strict";
// Keep the integer planner identical to CreatorVoiceSequence.cs. Text is local
// source material for sound, never a translation request or a dialogue edit.
const VoiceSequence=(()=>{
 function hash(text){let n=2166136261;for(let i=0;i<text.length;i++){n^=text.charCodeAt(i);n=Math.imul(n,16777619)>>>0;}return n>>>0;}
 function rng(seed){let n=seed||1;return max=>{n^=n<<13;n^=n>>>17;n^=n<<5;return (n>>>0)%max;};}
 function make(text,s){
  s={...s};for(const key of ['speed','pitch','chaos'])s[key]=Math.round(s[key]*100000)/100000;
  text=String(text||'').slice(0,600);const clean=text.replace(/[\x00-\x20]/g,'');if(!clean)return {notes:[],ticks:0,utterance:''};
  const next=rng(hash(text)),chance=amount=>next(10000)<Math.round(amount*10000),units=[];
  for(let i=0;i<clean.length;i+=3)units.push(clean.slice(i,i+3));
  if(s.reverse&&s.chaos>0&&chance(s.chaos))units.reverse();
  const chunks=[];
  for(const unit of units){const parts=s.split&&s.chaos>0&&chance(s.chaos*.65)?unit.split(''):[unit];for(const part of parts){chunks.push(part);if(s.repeat&&s.chaos>0&&chance(s.chaos*.45))chunks.push(part);}}
  const budget=Math.max(6,Math.min(480,Math.ceil(text.length*2.8/s.speed))),notes=[];let tick=0,index=0,previous=-1,previousUnit=null;
  while(tick<budget&&notes.length<96){
   const unit=chunks[index++%chunks.length],sum=s.shortWeight+s.mediumWeight+s.longWeight,choice=sum>0?next(sum):0;
   const range=sum===0||choice<s.shortWeight?[5,5]:choice<s.shortWeight+s.mediumWeight?[11,10]:[22,17];
   const length=Math.min(budget-tick,Math.max(3,Math.floor((range[0]+next(range[1]))/s.speed+.5)));
   let sample=hash(unit)%5;if(sample===previous&&unit!==previousUnit)sample=(sample+1+next(4))%5;previous=sample;previousUnit=unit;
   const pitch=Math.max(.2,Math.min(3,s.pitch*(1+(s.chaos>0?(next(2001)-1000)/1000*.18*s.chaos:0))));
   // Native Moon recordings have a quiet lead-in. Select an audible fragment
   // instead of repeatedly truncating that lead-in into a silent short note.
   const offset=.3+((hash(unit)>>>8)%600)/1000;
   notes.push({start:tick,ticks:length,sample,pitch,offset});tick+=length+Math.max(1,Math.floor((3+next(6))/s.speed+.5));
  }
  return {notes,ticks:budget,utterance:chunks.join(' · ')};
 }
 return {make,hash};
})();
