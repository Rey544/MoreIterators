'use strict';
const easingErrors=[];
window.addEventListener('error',event=>{if(!event.message.startsWith('ResizeObserver loop'))easingErrors.push(event.message);});
window.addEventListener('unhandledrejection',event=>easingErrors.push(String(event.reason)));
const easingFrame={duration:1,x:.2,y:.4,scale:1,rotation:0,opacity:1,brightness:1,flicker:0,ease:'linear'};
const easingGroup={uid:'fixture-easing',projectId:'fixture-project',name:'Easing fixture',revision:1,enabled:true,loop:true,trigger:{kind:'work',source:'',pearlUid:'',startLineId:'',endLineId:''},images:[],tracks:[{id:'fixture-track',name:'Circle',kind:'circle',color:'#ffffff',style:'plain',delay:.5,frames:[easingFrame,{...easingFrame,duration:2,x:.7},{...easingFrame,duration:3,x:.3}]}]};
let easingSaved=null,releaseReference;
const referenceWaiting=new Promise(resolve=>releaseReference=resolve);
window.fetch=async(input,options={})=>{
  const path=new URL(input,'http://fixture.invalid').pathname;let value;
  if(path.startsWith('/locales/'))value=EASING_CATALOGS[path.split('/').pop().replace('.json','')];
  else if(path==='/api/projections')value={projects:[{projectId:easingGroup.projectId,name:'Fixture'}],projections:[easingGroup],applied:{}};
  else if(path==='/api/projection-sources')value={sources:[]};
  else if(path==='/api/projection-background')value={width:1000,height:600};
  else if(path==='/api/projection-settings')value={mask:{enabled:false,x:0,y:0,width:1,height:1},revision:0};
  else if(path==='/api/projection-reference'){await referenceWaiting;value={assets:[],elements:[]};}
  else if(path==='/api/projection-save'){easingSaved=JSON.parse(options.body);value=easingSaved;}
  else throw Error('Unexpected isolated route '+path);
  return {ok:true,json:async()=>structuredClone(value)};
};
                                                                               
let easingClock=0,easingSerial=0;
const easingCallbacks=new Map();
window.requestAnimationFrame=callback=>{easingCallbacks.set(++easingSerial,callback);return easingSerial;};
window.cancelAnimationFrame=id=>easingCallbacks.delete(id);
function easingTick(ms=0){easingClock+=ms;const callbacks=[...easingCallbacks.values()];easingCallbacks.clear();for(const callback of callbacks)callback(easingClock);}
function easingAdvance(ms){while(ms>0){const delta=Math.min(50,ms);easingTick(delta);ms-=delta;}}
let easingPose=null;
const easingArc=CanvasRenderingContext2D.prototype.arc,easingClear=CanvasRenderingContext2D.prototype.clearRect;
CanvasRenderingContext2D.prototype.clearRect=function(...args){if(this.canvas.id==='preview')easingPose=null;return easingClear.apply(this,args);};
CanvasRenderingContext2D.prototype.arc=function(...args){if(this.canvas.id==='preview'&&args[2]===70){const m=this.getTransform();easingPose={x:m.e/1000,y:m.f/600,scale:Math.hypot(m.a,m.b),rotation:Math.atan2(m.b,m.a)*180/Math.PI,opacity:this.globalAlpha,filter:this.filter,color:this.strokeStyle};}return easingArc.apply(this,args);};
window.runProjectionEasingTests=async()=>{
  let checks=0;
  const $=id=>document.getElementById(id),check=(value,message)=>{checks++;if(!value)throw Error(message);};
  const near=(actual,expected,message)=>check(Math.abs(actual-expected)<.00001,message+': '+actual+' != '+expected);
  const wait=async test=>{for(let i=0;i<200;i++){if(test())return;await new Promise(resolve=>setTimeout(resolve,10));}throw Error('Fixture did not initialize: '+easingErrors.join('; '));};
  const input=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('input',{bubbles:true}));};
  const select=index=>document.querySelectorAll('#frameList button')[index].click();
  const time=()=>Number($('timeDisplay').textContent.split(' / ')[0]);
  await wait(()=>!$('studio').inert&&document.querySelectorAll('#frameList button').length===3);
  check($('ease').disabled,'Initial hold must not offer incoming easing');
  select(1);input('ease','quadIn');easingTick();easingAdvance(500);
  near(time(),2,'Reference library must not block playback');near(easingPose.x,.23125,'Animation must use quadratic easing');
  const ctx=$('preview').getContext('2d'),pixels=ctx.getImageData(299,238,5,5).data;
  check([...pixels].some((value,index)=>index%4===0&&value>100),'Actual Canvas did not draw eased circle at expected position');
  releaseReference();await new Promise(resolve=>setTimeout(resolve,0));
  const nativeNames=['LerpQuadEaseIn','LerpQuadEaseOut','LerpQuadEaseInOut','LerpSinEaseInOut','LerpExpEaseIn','LerpExpEaseOut','LerpExpEaseInOut','LerpCircEaseIn','LerpCircEaseOut','LerpCircEaseInOut','LerpBackEaseIn','LerpBackEaseOut','LerpBackEaseInOut','LerpElasticEaseIn','LerpElasticEaseOut','LerpElasticEaseInOut'];
  const modes=[...$('ease').options].map(option=>option.value),quarterPositions={};
  check(modes.length===19,'Missing easing choices');
  for(const kind of modes){
    input('ease',kind);near(time(),1.5,kind+' must restart incoming transition');check(!$('pause').disabled,kind+' did not start preview');
    easingTick();easingAdvance(500);const factor=MIProjectionTimeline.ease(kind,.25);near(easingPose.x,.2+.5*factor,kind+' actual canvas pose');quarterPositions[kind]=easingPose.x;
    easingAdvance(1500);near(time(),3.5,kind+' must end at selected keyframe');near(easingPose.x,.7,kind+' final pose');check($('pause').disabled,kind+' loop setting must not repeat selected preview');
    easingAdvance(500);near(time(),3.5,kind+' must not play following keyframe');
  }
  near(quarterPositions.linear,.325,'Linear reference');check(quarterPositions.quadIn<quarterPositions.linear,'Quadratic in is indistinguishable from linear');check(quarterPositions.backIn<.2,'Back anticipation missing');check(quarterPositions.elasticOut>.7,'Elastic overshoot missing');
  input('ease','quadOut');easingTick();easingAdvance(300);$('pause').click();const paused=time();easingAdvance(300);near(time(),paused,'Pause did not freeze time');
  $('play').click();easingTick();easingAdvance(200);near(time(),paused+.2,'Play did not resume paused time');
  easingAdvance(1500);near(time(),3.5,'Resumed preview ignored selected endpoint');check($('pause').disabled,'Resumed preview played following keyframe');
  input('playhead',2);easingAdvance(200);near(time(),2,'Scrub did not pause playback');near(easingPose.x,.41875,'Scrub did not sample current curve');
  $('stop').click();near(time(),0,'Stop must rewind');check(easingPose===null,'Track appeared before delay');
  select(0);check($('ease').disabled,'Selecting initial frame leaves easing enabled');near(time(),.5,'Initial keyframe selection ignores delay');near(easingPose.x,.2,'Initial keyframe pose changed');
  select(2);input('ease','quadIn');easingTick();easingAdvance(750);near(time(),4.25,'Last transition preview starts wrong');near(easingPose.x,.675,'Last transition eased pose');easingAdvance(2250);near(time(),6.5,'Last transition endpoint');check($('pause').disabled,'Last transition did not stop');
  $('play').click();easingTick();easingAdvance(600);near(time(),.6,'Play at final endpoint must restart');
  $('loop').checked=false;$('loop').dispatchEvent(new Event('change'));input('playhead',6.4);$('play').click();easingTick();easingAdvance(200);near(time(),6.5,'Non-loop playback did not end');check($('pause').disabled,'Non-loop playback did not stop');
  $('loop').checked=true;$('loop').dispatchEvent(new Event('change'));input('playhead',6.4);$('play').click();easingTick();easingAdvance(200);near(time(),.1,'Normal loop playback no longer wraps');
  select(1);input('duration',4);near(time(),5.5,'Duration edit must seek adjusted endpoint');near(Number($('playhead').max),8.5,'Duration edit did not update timeline length');
  input('trackDelay',1);near(time(),6,'Delay edit must seek adjusted endpoint');near(Number($('playhead').max),9,'Delay edit did not update timeline length');
  input('ease','quadIn');near(time(),2,'Preview ignored changed duration/delay');easingTick();easingAdvance(1000);near(easingPose.x,.23125,'Changed duration/delay ease incorrect');
  for(const [id,value,key,expected] of [['x',60,'x',.6],['y',30,'y',.3],['scale',1.5,'scale',1.5],['rotation',45,'rotation',45],['opacity',40,'opacity',.4]]){input(id,value);near(easingPose[key],expected,id+' edit did not redraw selected frame');near(time(),6,id+' edit did not seek endpoint');check($('pause').disabled,id+' edit did not pause');}
  input('brightness',.5);near(easingPose.opacity,.2,'Brightness did not affect opacity');check(easingPose.filter==='brightness(0.5)','Brightness did not update actual Canvas filter');
  input('flicker',50);check(easingPose.opacity<.2,'Flicker did not update opacity');input('trackColor','#ff0000');check(easingPose.color==='#ff0000','Track color did not redraw');
  for(const [id,value] of [['x',20],['y',40],['scale',1],['rotation',0],['opacity',100],['brightness',1],['flicker',0]])input(id,value);
  check($('easeDescription').textContent.includes(MI18n.t('projection.ease.unchanged')),'Identical keyframes have no explanation');
  input('ease','elasticIn');easingTick();easingAdvance(1000);near(easingPose.x,.2,'Identical poses must remain unchanged');
  const expectedFrames=structuredClone(easingGroup.tracks[0].frames);expectedFrames[1].duration=4;expectedFrames[1].ease='elasticIn';expectedFrames[1].x=.2;expectedFrames[2].ease='quadIn';
  await $('save').onclick();check(easingSaved!==null,'Fixture save not captured');check(JSON.stringify(easingSaved.tracks[0].frames)===JSON.stringify(expectedFrames),'Preview changed frames beyond explicit edits');check(easingSaved.tracks[0].delay===1,'Delay edit not retained');
  const authored=JSON.stringify(easingSaved);for(const locale of ['en','zh-CN']){MI18n.setLocale(locale,false);await new Promise(resolve=>setTimeout(resolve,0));for(let i=3;i<$('ease').options.length;i++){const option=$('ease').options[i];check(option.text.includes(nativeNames[i-3]),'Original method missing in '+locale);check(option.text!==nativeNames[i-3],'Localized name missing in '+locale);check(!option.text.includes('projection.ease.'),'Raw localization key shown');}check($('ease').title===$('ease').selectedOptions[0].text,'Selected label tooltip not translated');}
  await $('save').onclick();check(JSON.stringify(easingSaved)===authored,'Language switch changed authored projection');
  MIUndo.flush();input('ease','quadOut');MIUndo.flush();easingTick();easingAdvance(500);
  check(await MIUndo.undo(),'Cannot undo easing change during preview');near(time(),0,'Undo did not reset playback');check($('pause').disabled,'Undo left preview playing');check($('ease').value==='elasticIn','Undo did not restore easing identifier');
  check(await MIUndo.redo(),'Cannot redo easing change');near(time(),0,'Redo did not reset playback');check($('pause').disabled,'Redo restarted preview');check($('ease').value==='quadOut','Redo did not restore easing identifier');
  $('play').click();easingTick();easingAdvance(6500);near(time(),6.5,'Undo/redo retained stale selected preview endpoint');check(!$('pause').disabled,'Undo/redo stopped whole-group playback at former preview end');$('stop').click();
  check(!easingErrors.length,easingErrors.join('\n'));return {ok:true,checks,curves:modes.length,quarterPositions,referenceDelay:'passed',timelineControls:'passed',parameterRedraw:'passed',authoredValues:'preserved',errors:easingErrors};
};
