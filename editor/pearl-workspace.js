/* Resizable pearl studio columns. Layout preferences never enter pearl files. */
(function(scope){
 'use strict';
 const minimum=[230,300,190,250],defaults=[240,450,220,300],key='moreiterators.pearl.workspace.v1';
 const clamp=(value,min,max)=>Math.max(min,Math.min(max,value));
 function widths(available,preferred=defaults){
  const total=minimum.reduce((a,b)=>a+b,0);available=Math.max(total,available);
  const source=preferred.length===4&&preferred.every(n=>Number.isFinite(n)&&n>0)?preferred:defaults;
  const result=Array(4).fill(0),free=new Set([0,1,2,3]);let remaining=available;
  while(free.size){const weight=[...free].reduce((sum,i)=>sum+source[i],0);let fixed=false;
   const constrained=[...free].filter(i=>remaining*source[i]/weight<minimum[i]);
   for(const i of constrained){result[i]=minimum[i];remaining-=minimum[i];free.delete(i);fixed=true;}
   if(!fixed){for(const i of free)result[i]=remaining*source[i]/weight;break;}
  }return result;
 }
 function movePair(current,index,delta){const result=current.slice(),pair=result[index]+result[index+1];result[index]=clamp(result[index]+delta,minimum[index],pair-minimum[index+1]);result[index+1]=pair-result[index];return result;}
 function height(value,fallback){return clamp(Number.isFinite(value)?value:fallback,280,1600);}
 function mount(){
  const layout=document.getElementById('pearlLayout');if(!layout)return;
  const columns=[...layout.querySelectorAll('.pearl-column')],horizontal=[...layout.querySelectorAll('.pearl-width-handle')],vertical=[...layout.querySelectorAll('.pearl-height-handle')];
  let state={widths:defaults.slice(),heights:[null,null,null,null]},actual=defaults.slice(),drag=null,frame=0;
  try{const stored=JSON.parse(localStorage.getItem(key));if(stored&&Array.isArray(stored.widths)&&stored.widths.length===4&&stored.widths.every(n=>Number.isFinite(n)&&n>0))state.widths=stored.widths;if(Array.isArray(stored?.heights)&&stored.heights.length===4)state.heights=stored.heights.map(n=>Number.isFinite(n)?height(n,420):null);}catch{}
  const persist=()=>{try{localStorage.setItem(key,JSON.stringify(state));}catch{}};
  function refresh(){
   frame=0;const mode=innerWidth>=1180?'wide':innerWidth>760?'compact':'stacked';layout.dataset.layout=mode;
   const style=getComputedStyle(layout),available=layout.clientWidth-parseFloat(style.paddingLeft)-parseFloat(style.paddingRight)-30;
   actual=widths(available,state.widths);if(mode==='wide')layout.style.setProperty('--pearl-columns',actual.map(n=>n+'px').join(' 10px '));
   columns.forEach((column,index)=>{const value=height(state.heights[index],Math.max(420,innerHeight-210));column.style.setProperty('--pearl-column-height',value+'px');const handle=vertical[index];handle.setAttribute('aria-valuemin','280');handle.setAttribute('aria-valuemax','1600');handle.setAttribute('aria-valuenow',String(Math.round(value)));});
   horizontal.forEach((handle,index)=>{handle.setAttribute('aria-valuemin',String(minimum[index]));handle.setAttribute('aria-valuemax',String(Math.round(actual[index]+actual[index+1]-minimum[index+1])));handle.setAttribute('aria-valuenow',String(Math.round(actual[index])));});
  }
  const schedule=()=>{if(!frame)frame=requestAnimationFrame(refresh);};
  function finish(event){if(!drag||drag.pointer!==event.pointerId)return;const handle=drag.handle;drag=null;document.body.classList.remove('pearl-resizing');if(handle.hasPointerCapture(event.pointerId))handle.releasePointerCapture(event.pointerId);persist();}
  function bind(handle,index,axis){
   handle.onpointerdown=event=>{if(event.button!==0||axis==='x'&&layout.dataset.layout!=='wide')return;event.preventDefault();handle.focus();drag={handle,index,axis,pointer:event.pointerId,start:axis==='x'?event.clientX:event.clientY,widths:actual.slice(),height:columns[index].getBoundingClientRect().height};handle.setPointerCapture(event.pointerId);document.body.classList.add('pearl-resizing');};
   handle.onpointermove=event=>{if(!drag||drag.handle!==handle||drag.pointer!==event.pointerId)return;event.preventDefault();if(axis==='x')state.widths=movePair(drag.widths,index,event.clientX-drag.start);else state.heights[index]=height(drag.height+event.clientY-drag.start,420);refresh();};
   handle.onpointerup=handle.onpointercancel=handle.onlostpointercapture=finish;
   handle.ondblclick=()=>{if(axis==='x')state.widths=defaults.slice();else state.heights[index]=null;refresh();persist();};
   handle.onkeydown=event=>{const negative=axis==='x'?'ArrowLeft':'ArrowUp',positive=axis==='x'?'ArrowRight':'ArrowDown';if(![negative,positive,'Home','End'].includes(event.key))return;event.preventDefault();if(axis==='x'){const delta=event.key==='Home'?-1e6:event.key==='End'?1e6:event.key===negative?-20:20;state.widths=movePair(actual,index,delta);}else{const current=columns[index].getBoundingClientRect().height;state.heights[index]=height(event.key==='Home'?280:event.key==='End'?1600:current+(event.key===negative?-20:20),420);}refresh();persist();};
  }
  horizontal.forEach((handle,index)=>bind(handle,index,'x'));vertical.forEach((handle,index)=>bind(handle,index,'y'));
  window.addEventListener('resize',schedule);refresh();return {refresh};
 }
 const api={widths,movePair,height,mount,minimum};if(typeof module!=='undefined'&&module.exports)module.exports=api;else{scope.MIPearlWorkspace=api;if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount,{once:true});else mount();}
})(typeof window!=='undefined'?window:globalThis);
