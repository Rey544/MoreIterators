'use strict';
const assert=require('node:assert/strict');
const timeline=require('../editor/projections.js');
const curves=['linear','smooth','step','quadIn','quadOut','quadInOut','sineInOut','expIn','expOut','expInOut','circIn','circOut','circInOut','backIn','backOut','backInOut','elasticIn','elasticOut','elasticInOut'];
const frame={duration:1,x:.2,y:.3,scale:1,rotation:0,opacity:.4,brightness:.8,flicker:.1,ease:'smooth'};
const target={...frame,duration:2,x:.7,y:.8,scale:2,rotation:180,opacity:.9,brightness:1.4,flicker:.7};
const fields=['x','y','scale','rotation','opacity','brightness','flicker'];
let checks=0;
const near=(actual,expected,message)=>{checks++;assert.ok(Math.abs(actual-expected)<1e-10,message+': '+actual+' != '+expected);};
for(const kind of curves){
  const track={delay:.5,frames:[frame,{...target,ease:kind},{...frame,duration:0,x:.8}]},before=JSON.stringify(track);
  near(timeline.ease(kind,0),0,kind+' initial endpoint');
  near(timeline.ease(kind,1),kind==='step'?0:1,kind+' final factor');
  near(timeline.ease(kind,-1),0,kind+' negative time clamps');
  near(timeline.ease(kind,2),kind==='step'?0:1,kind+' time beyond end clamps');
  assert.equal(timeline.sample(track,.49),null);
  assert.deepEqual(timeline.sample(track,.5),frame);
  assert.deepEqual(timeline.sample(track,1.49),frame);
  for(const progress of [.1,.25,.5,.75,.9]){
    const pose=timeline.sample(track,1.5+2*progress),factor=timeline.ease(kind,progress);
    assert.ok(Number.isFinite(factor),kind+' has nonfinite factor');
    for(const key of fields)near(pose[key],frame[key]+(target[key]-frame[key])*factor,kind+' interpolates '+key);
  }
  near(timeline.sample(track,3.5).x,.8,kind+' exact endpoint advances zero-duration keys');
  near(timeline.sample(track,4).x,.8,kind+' holds final pose');
  assert.equal(JSON.stringify(track),before,'Preview mutated authored frames');
  if(kind!=='linear')assert.ok([.1,.25,.75,.9].some(value=>Math.abs(timeline.ease(kind,value)-value)>.02),kind+' silently falls back to linear');
}
near(timeline.ease('quadIn',.25),.0625,'quadratic in');
near(timeline.ease('quadOut',.25),.4375,'quadratic out');
near(timeline.ease('quadInOut',.25),.125,'quadratic in-out');
assert.ok(timeline.ease('backIn',.25)<0,'Back in lost anticipation');
assert.ok(timeline.ease('backOut',.75)>1,'Back out lost overshoot');
assert.ok(timeline.ease('elasticIn',.85)<0,'Elastic in lost oscillation');
assert.ok(timeline.ease('elasticOut',.15)>1,'Elastic out lost oscillation');
assert.equal(timeline.transition({frames:[frame]},0),null);
assert.equal(timeline.transition(null,1),null);
assert.deepEqual(timeline.transition({delay:.5,frames:[frame,target]},1),{start:1.5,end:3.5,changed:true});
assert.deepEqual(timeline.transition({delay:.5,frames:[frame,{...frame,duration:0,ease:'elasticIn'}]},1),{start:1.5,end:1.5,changed:false});
console.log(JSON.stringify({ok:true,curves:curves.length,checks}));
