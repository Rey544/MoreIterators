'use strict';
// Pure preview planning: author content and stable line IDs are never rewritten.
const ActionEditor=typeof module!=='undefined'?require('./line-actions.js'):window.MIActionEditor;
const MIDialoguePreview=(()=>{
  const tiers=['notSpeaking','dislikes','neutral','likes'];
  const pearlKeys={pearlFirstPreRead:'firstPreRead',pearlGreetingCreatures:'greetingCreatures',pearlGreetingCorpses:'greetingCorpses',pearlGreetingFood:'greetingFood',pearlGreeting:'greeting',pearlQuickReturn:'quickReturn',pearlRevisit:'revisit',pearlGreetingPearls:'greetingPearls',pearlGreetingMixed:'greetingMixed',pearlExtractedPreRead:'extractedPreRead',pearlGreetingItems:'greetingItems',pearlGreetingWeapons:'greetingWeapons',pearlPreRead:'preRead',pearlMisc:'misc',pearlRepeat:'repeat',pearlMany:'many',pearlLeaving:'leaving',pearlReturning:'returning'};
  function normalize(profile){
    profile.firstCondition??={minEntries:0,minCycle:0,held:'any'};profile.repeatCondition??={minEntries:0,minCycle:0,held:'any'};
    profile.storyMode??='sequence';profile.meetings??=[];profile.loop??=[];profile.repeat??=[];profile.affinity??={};profile.observation??={};profile.pearlReading??={};
    for(const [key,value] of Object.entries({enabled:true,initial:.3,pearlGiftEnabled:false,pearlGiftAmount:.1,attackMode:'vanilla',rockPenalty:.2,spearPenalty:.5,refuseBelow:-.5,refusal:[]}))profile.affinity[key]??=value;
    for(const key of ['attackRock','attackSpear']){profile.affinity[key]??={};for(const tier of tiers)profile.affinity[key][tier]??=[];}
    for(const [key,value] of Object.entries({enabled:true,cooldown:4}))profile.observation[key]??=value;
    for(const key of ['items','weapons','pearls','mixed','creatures','corpses','food']){profile.observation[key]??=[];profile.observation['repeat'+key[0].toUpperCase()+key.slice(1)]??=[];}
    for(const key of Object.values(pearlKeys))profile.pearlReading[key]??=[];
    for(const [key,value] of Object.entries({greetingEnabled:true,greetingDelay:3,quickReturnWindow:30,returnCooldown:10,extractStomachPearl:false,presentation:ActionEditor.presentation.normalize()}))profile.pearlReading[key]??=value;
    for(const chapter of profile.meetings)chapter.condition??={minEntries:0,minCycle:0,held:'any'};
    return profile;
  }
  const isStory=key=>['first','repeat','loop'].includes(key)||key.startsWith('meeting:');
  const meeting=(profile,key)=>profile.meetings?.find(item=>'meeting:'+item.id===key);
  function groups(profile,key,tier='neutral'){
    if(Object.hasOwn(pearlKeys,key))return profile.pearlReading[pearlKeys[key]]||[];
    if(['attackRock','attackSpear'].includes(key))return profile.affinity[key][tier]||[];
    if(key==='refusal')return profile.affinity.refusal;
    if(key.startsWith('observation')){const name=key.slice('observation'.length);return profile.observation[name[0].toLowerCase()+name.slice(1)]||[];}
    return profile[key]||[];
  }
  function entries(profile,key,{chosenPool=null,tier='neutral',lastPools={},random=Math.random}={}){
    const flat=isStory(key),chapter=meeting(profile,key);let selectedPool=null,list=chapter?.lines||profile[key]||[],action=chapter?.action||profile[key+'Action'];
    if(!flat){
      const pool=groups(profile,key,tier),memory=key+':'+tier;selectedPool=chosenPool;
      if(selectedPool===null){let candidates=pool.map((group,index)=>({group,index})).filter(({group})=>group.lines.some(ActionEditor.runnable));if(candidates.length>1)candidates=candidates.filter(item=>item.index!==lastPools[memory]);if(!candidates.length)return [];selectedPool=candidates[Math.floor(random()*candidates.length)].index;lastPools[memory]=selectedPool;}
      list=pool[selectedPool]?.lines||[];action=pool[selectedPool]?.action;
    }
    const spoken=list.map((line,index)=>({line,index})).filter(item=>ActionEditor.runnable(item.line));
    return spoken.map((item,index)=>{const groupAction=index===spoken.length-1?ActionEditor.normalize(action):null;return {...item,stage:key,poolIndex:selectedPool,tier,ordinal:index+1,total:spoken.length,action:groupAction?.type!=='none'?groupAction:null,beforeActions:ActionEditor.sequence(item.line.beforeAction),actions:ActionEditor.sequence(item.line.action,groupAction)};});
  }
  function greeting(profile,carrying,options={}){const a=entries(profile,options.base||'pearlGreeting',options),keys={creatures:'pearlGreetingCreatures',corpses:'pearlGreetingCorpses',food:'pearlGreetingFood',items:'pearlGreetingItems',weapons:'pearlGreetingWeapons',pearls:'pearlGreetingPearls',mixed:'pearlGreetingMixed'};let key=keys[carrying];if(carrying==='mixed'&&!groups(profile,key).some(group=>group.lines.some(ActionEditor.runnable)))key=['pearlGreetingWeapons','pearlGreetingPearls','pearlGreetingItems'].find(key=>groups(profile,key).some(group=>group.lines.some(ActionEditor.runnable)));if(['creatures','corpses','food'].includes(carrying)&&!groups(profile,key).some(group=>group.lines.some(ActionEditor.runnable)))key='pearlGreetingItems';return key?a.concat(entries(profile,key,{...options,chosenPool:null})):a;}
  function reading(profile,value,options={}){return profile.affinity.enabled&&value<profile.affinity.refuseBelow?entries(profile,'refusal',options):entries(profile,options.extracted?'pearlExtractedPreRead':options.firstRead&&groups(profile,'pearlFirstPreRead').some(group=>group.lines.some(ActionEditor.runnable))?'pearlFirstPreRead':'pearlPreRead',options).concat(entries(profile,'pearlMisc',options));}
  function tier(value){return value<-.5?'notSpeaking':value<0?'dislikes':value<.5?'neutral':'likes';}
  function afterHit(affinity,key,value){return affinity.enabled?affinity.attackMode==='vanilla'?-1:Math.max(-1,Math.min(1,value-affinity[key==='attackSpear'?'spearPenalty':'rockPenalty'])):value;}
  return {tiers,normalize,groups,entries,greeting,reading,tier,afterHit,isStory,meeting};
})();
if(typeof module!=='undefined')module.exports=MIDialoguePreview;
if(typeof document!=='undefined'){
const $=id=>document.getElementById(id);
const STAGES={first:'初次进入',repeat:'第 2 次见面',loop:'后续循环对话',pearlFirstPreRead:'每循环首次读珠前言',pearlGreetingCreatures:'携带生物 B',pearlGreetingCorpses:'携带尸体 B',pearlGreetingFood:'携带食物 B',pickup:'拿起工作珍珠',leaving:'尝试离开',returning:'离开后返回',pearlGreeting:'每循环首次问候 A',pearlQuickReturn:'短时返回',pearlRevisit:'离房后再访',pearlGreetingPearls:'携带珍珠 B',pearlGreetingMixed:'携带珍珠与武器 B',pearlExtractedPreRead:'胃中取珠前言',pearlGreetingItems:'携带物品 B',pearlGreetingWeapons:'携带武器 B',pearlPreRead:'读珍珠前言',pearlMisc:'原版无色珍珠',pearlRepeat:'重复交付珍珠',pearlMany:'多珍珠提示',pearlLeaving:'读珍珠时离开',pearlReturning:'读珍珠时返回',observationPearls:'观察珍珠',observationMixed:'观察珍珠与武器',observationItems:'观察一般物品',observationWeapons:'观察武器',attackRock:'被石块击中',attackSpear:'被矛击中',refusal:'低好感拒绝读取'};
const CATEGORIES={story:{name:'剧情',stages:['first','repeat','loop']},interrupt:{name:'流程打断',stages:['pickup','leaving','returning']},greeting:{name:'日常招呼',stages:['pearlGreeting','pearlQuickReturn','pearlRevisit','pearlGreetingItems','pearlGreetingWeapons','pearlGreetingPearls','pearlGreetingMixed','pearlGreetingCreatures','pearlGreetingCorpses','pearlGreetingFood']},reading:{name:'读珍珠',stages:['pearlFirstPreRead','pearlPreRead','pearlExtractedPreRead','pearlMisc','pearlRepeat','pearlMany','pearlLeaving','pearlReturning']},observation:{name:'物品观察',stages:['observationItems','observationWeapons','observationPearls','observationMixed']},affinity:{name:'好感回应',stages:['attackRock','attackSpear','refusal']}};
const observationLabels={Items:'一般物品',Weapons:'武器',Pearls:'珍珠',Mixed:'珍珠与武器',Creatures:'生物',Corpses:'尸体',Food:'食物'};
for(const [name,label] of Object.entries(observationLabels)){STAGES['observation'+name]=label+' 每循环首次观察';STAGES['observationRepeat'+name]=label+' 本循环后续观察';}
CATEGORIES.observation.stages=Object.keys(STAGES).filter(key=>key.startsWith('observation'));
const PEARL_KEYS={pearlFirstPreRead:'firstPreRead',pearlGreetingCreatures:'greetingCreatures',pearlGreetingCorpses:'greetingCorpses',pearlGreetingFood:'greetingFood',pearlGreeting:'greeting',pearlQuickReturn:'quickReturn',pearlRevisit:'revisit',pearlGreetingPearls:'greetingPearls',pearlGreetingMixed:'greetingMixed',pearlExtractedPreRead:'extractedPreRead',pearlGreetingItems:'greetingItems',pearlGreetingWeapons:'greetingWeapons',pearlPreRead:'preRead',pearlMisc:'misc',pearlRepeat:'repeat',pearlMany:'many',pearlLeaving:'leaving',pearlReturning:'returning'};
const social=(key,values={})=>MI18n.t(`dialogue.social.${key}`,values);
const categoryOf=key=>Object.keys(CATEGORIES).find(category=>CATEGORIES[category].stages.includes(key));
const isAttack=key=>['attackRock','attackSpear'].includes(key);
const api=async(path,data)=>{await MI18n.ready;const response=await fetch('/api/'+path,data===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const value=await response.json();if(!response.ok)throw Error(MI18n.error(value,response.statusText));return value;};
const run=fn=>async(...args)=>{try{return await fn(...args);}catch(error){notice(error.message,true);console.error(error);}};
let projects=[],project=null,profile=null,revision=0,stage='first',tier='neutral',poolIndex=0,dirty=false,editVersion=0,busy=false,dragLine=null;
let saveStatus='loading',currentEntry=null;
const rowElements=new Map();
function el(tag,text){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;return node;}
function button(text,action){const node=el('button',text);node.type='button';node.onclick=action;return node;}
function notice(text,error=false){$('notice').textContent=text;$('notice').dataset.kind=error?'error':'info';}
function setSaveState(state){saveStatus=state;$('saveState').dataset.state=state;$('saveState').textContent=({loading:'正在加载…',unsaved:'未保存',saved:'已保存',applied:'已应用到游戏'})[state]||state;}
function changed(){dirty=true;editVersion++;setSaveState('unsaved');notice('');window.MIUndo?.changed();}
const pearlStage=(key=stage)=>Object.hasOwn(PEARL_KEYS,key);
const isPool=(key=stage)=>!MIDialoguePreview.isStory(key);
const pools=(key=stage,selectedTier=tier)=>MIDialoguePreview.groups(profile,key,selectedTier);
const lineList=()=>isPool()?pools()[poolIndex]?.lines:MIDialoguePreview.meeting(profile,stage)?.lines||profile[stage];
function meetingCondition(){const chapter=MIDialoguePreview.meeting(profile,stage);return chapter?.condition||(['first','repeat'].includes(stage)?profile[stage+'Condition']:null);}
function actionTarget(){const chapter=MIDialoguePreview.meeting(profile,stage);if(chapter)return {owner:chapter,key:'action'};return isPool()?{owner:pools()[poolIndex],key:'action'}:{owner:profile,key:stage+'Action'};}
function normalizeProfile(value){return MIDialoguePreview.normalize(value);}
function grow(text){text.style.height='auto';text.style.height=Math.max(64,text.scrollHeight+2)+'px';}
function setBusy(value){busy=value;if(value)endLineDrag();$('save').disabled=$('apply').disabled=value||!profile;$('projects').disabled=value||!projects.length;}
function sameData(a,b){const sort=value=>Array.isArray(value)?value.map(sort):value&&typeof value==='object'?Object.fromEntries(Object.keys(value).sort().map(key=>[key,sort(value[key])])):value;return JSON.stringify(sort(a))===JSON.stringify(sort(b));}
function syncAddress(){if(project)history.replaceState(null,'','?id='+encodeURIComponent(project.projectId)+'&stage='+stage+'&tier='+tier+'&lang='+MI18n.locale);}
function stageNode(tag,key){const node=el(tag,STAGES[key]);if(key.startsWith('meeting:')||key.startsWith('observation')){node.dataset.storyStage=key;MI18n.content(node);}return node;}
function previewTitle(){const name=el('span',project?.name||'迭代器');if(project)MI18n.content(name);$('previewTitle').replaceChildren(name,document.createTextNode('／'),stageNode('span',stage));}
function markCurrent(scroll=false){
  for(const [line,card] of rowElements){const selected=!!currentEntry&&line===currentEntry.line;card.classList.toggle('playing',selected);if(selected){card.setAttribute('aria-current','true');if(scroll)card.scrollIntoView({block:'nearest',behavior:'smooth'});}else card.removeAttribute('aria-current');}
}
function clearDrop(){for(const card of $('lines').children)card.classList.remove('drop-before','drop-after');}
function endLineDrag(){const previous=dragLine;dragLine=null;if(previous?.handle.hasPointerCapture(previous.pointerId))previous.handle.releasePointerCapture(previous.pointerId);clearDrop();for(const card of $('lines').children)card.classList.remove('dragging');}
function lineDropAt(event){
  const host=$('lines'),cards=[...host.children],bounds=host.getBoundingClientRect();
  if(!cards.length||event.clientX<bounds.left||event.clientX>bounds.right)return null;
  const before=cards.findIndex(card=>{const rect=card.getBoundingClientRect();return event.clientY<rect.top+rect.height/2;});
  return before<0?{index:cards.length,card:cards.at(-1),after:true}:{index:before,card:cards[before],after:false};
}
function resetForStructure(){if(playing||currentEntry)stopPlayback();currentEntry=null;markCurrent();}
function moveLine(lines,from,to){if(busy||lines!==lineList()||from===to||from<0||to<0||from>=lines.length||to>=lines.length)return;resetForStructure();const [line]=lines.splice(from,1);lines.splice(to,0,line);changed();renderLines();rowElements.get(line)?.querySelector('.drag-handle')?.focus();}
function timeField(line,key,label,min,index){
  const field=el('label',label),input=el('input');input.type='number';Object.assign(input,{min,max:60,step:.1,value:line[key]});input.setAttribute('aria-label','第 '+(index+1)+' 句'+label);
  input.onchange=()=>{const value=Number(input.value);if(input.value===''||!Number.isFinite(value)||value<min||value>60){input.value=line[key];notice('停留至少 0.1 秒；间隔至少 0 秒，最长均为 60 秒。',true);return;}line[key]=value;changed();};
  input.oninput=()=>{const value=Number(input.value);if(input.value!==''&&Number.isFinite(value)&&value>=min&&value<=60){line[key]=value;changed();}};
  field.append(input);return field;
}
function renderLines(){
  endLineDrag();
  const host=$('lines'),lines=lineList()||[];host.replaceChildren();rowElements.clear();
  if(!lines.length){const empty=el('p',isPool()&&!pools().length?'添加随机组，再编写台词。':'还没有台词。');empty.className='line-empty';host.append(empty);}
  lines.forEach((line,index)=>{
    const card=el('article');card.className='line';card.dataset.index=index;rowElements.set(line,card);
    const head=el('div');head.className='line-header';
    const drag=button('⠿',event=>{event.preventDefault();event.stopPropagation();});drag.className='drag-handle';drag.title='拖动调整顺序；也可用方向键上下移动';drag.setAttribute('aria-label','拖动第 '+(index+1)+' 句');
    drag.onpointerdown=event=>{
      if(event.button!==0||busy||lines!==lineList())return;
      event.preventDefault();event.stopPropagation();endLineDrag();
      dragLine={lines,line,handle:drag,pointerId:event.pointerId,x:event.clientX,y:event.clientY,active:false};
      drag.focus();drag.setPointerCapture(event.pointerId);
    };
    drag.onpointermove=event=>{
      const moving=dragLine;if(!moving||moving.handle!==drag||moving.pointerId!==event.pointerId)return;
      if(!moving.active&&Math.hypot(event.clientX-moving.x,event.clientY-moving.y)<5)return;
      moving.active=true;card.classList.add('dragging');event.preventDefault();clearDrop();
      const drop=lineDropAt(event);if(drop)drop.card.classList.add(drop.after?'drop-after':'drop-before');
    };
    drag.onpointerup=event=>{
      const moving=dragLine;if(!moving||moving.handle!==drag||moving.pointerId!==event.pointerId)return;
      const drop=moving.active?lineDropAt(event):null,from=lines.indexOf(line);event.preventDefault();endLineDrag();
      if(drop)moveLine(lines,from,drop.index-(from<drop.index?1:0));
    };
    drag.onpointercancel=drag.onlostpointercapture=endLineDrag;
    drag.ondragstart=event=>event.preventDefault();
    drag.onkeydown=event=>{if(!['ArrowUp','ArrowDown'].includes(event.key))return;event.preventDefault();event.stopPropagation();const from=lines.indexOf(line);moveLine(lines,from,from+(event.key==='ArrowUp'?-1:1));};
    head.append(drag,Object.assign(el('span','第 '+(index+1)+' 句'),{className:'line-number'}));
    const actions=el('details');actions.className='action-menu';const summary=el('summary','操作');summary.setAttribute('aria-label','第 '+(index+1)+' 句操作');
    const menu=el('div');menu.className='menu-content';
    for(const [label,delta] of [['上移',-1],['下移',1]]){const move=button(label,()=>moveLine(lines,index,index+delta));move.disabled=index+delta<0||index+delta>=lines.length;menu.append(move);}
    const confirm=el('div');confirm.className='delete-confirm';confirm.hidden=true;confirm.append(el('span','删除第 '+(index+1)+' 句？'),button('取消',()=>confirm.hidden=true),Object.assign(button('确认删除',()=>{resetForStructure();lines.splice(index,1);changed();renderLines();}),{className:'danger'}));
    menu.append(Object.assign(button('删除此句',()=>{actions.open=false;confirm.hidden=false;confirm.querySelector('button')?.focus();}),{className:'danger'}));actions.append(summary,menu);head.append(actions);
    const text=el('textarea');text.value=line.text;text.rows=1;text.maxLength=2000;text.setAttribute('aria-label','第 '+(index+1)+' 句台词');text.oninput=()=>{line.text=text.value;grow(text);changed();};
    const timing=el('div');timing.className='line-fields';timing.append(timeField(line,'hold','停留（秒）',.1,index),timeField(line,'gap','间隔（秒）',0,index));
    const standalone=line.kind==='action';
    const before=el('details');before.className='mi-before-action';before.open=ActionEditor.normalize(line.beforeAction).type!=='none';before.append(el('summary','句前动作'),ActionEditor.create(line.beforeAction,value=>{line.beforeAction=value;changed();},{label:'句前动作'}));
    const sentenceAction=ActionEditor.create(line.action,value=>{line.action=value;changed();},{label:standalone?'独立动作':'句末动作'});
    const after=el('details');after.className='mi-after-action';after.open=ActionEditor.normalize(line.action).type!=='none';after.append(el('summary','句末动作'),sentenceAction);
    if(standalone){head.querySelector('.line-number').textContent='独立动作 '+(index+1);card.append(head,confirm,sentenceAction);}else card.append(head,confirm,text,timing,before,after,ActionEditor.presentation.create(line.presentation,value=>{line.presentation=value;changed();}));host.append(card);if(!standalone)grow(text);
  });
  $('addLine').disabled=!profile||(isPool()&&!pools().length);markCurrent();
  $('addAction').disabled=$('addLine').disabled;
}
function renderPreviewOptions(){
  const key=$('playEvent').value==='current'?stage:$('playEvent').value;
  $('previewCarryingField').hidden=!['pearlGreeting','pearlQuickReturn','pearlRevisit'].includes(key);$('previewExtractedField').hidden=key!=='pearlRead';$('previewFirstReadField').hidden=key!=='pearlRead';
  $('previewAffinityField').hidden=!(isAttack(key)||key==='refusal'||key==='pearlRead');
}
function renderAction(){
  const {owner,key}=actionTarget();
  $('groupActionOptions').replaceChildren();
  if(owner)$('groupActionOptions').append(ActionEditor.create(owner[key],value=>{owner[key]=value;changed();},{label:'组结束动作'}));
  $('groupActionDetails').open=!!owner&&ActionEditor.normalize(owner[key]).type!=='none';
}

function render(){
  if(!profile)return;
  syncStoryStages();
  $('roomStudio').href='/rooms?project='+encodeURIComponent(project.projectId)+'&lang='+MI18n.locale;
  $('projectionStudio').href='/projections?project='+encodeURIComponent(project.projectId)+'&lang='+MI18n.locale;
  $('name').textContent=project.name;MI18n.content($('name'));$('enabled').checked=profile.enabled;
  const category=categoryOf(stage)||'story';
  $('stageFieldLabel').textContent=MI18n.t(category==='story'?'dialogue.ui.selectStory':'dialogue.ui.selectContext');
  $('storyOptions').hidden=category!=='story';$('storyMode').value=profile.storyMode;
  const condition=meetingCondition();$('meetingCondition').hidden=!condition;if(condition){$('meetingEntries').value=condition.minEntries;$('meetingCycle').value=condition.minCycle;$('meetingHeld').value=condition.held;}
  const chapter=MIDialoguePreview.meeting(profile,stage),chapterIndex=profile.meetings.indexOf(chapter);
  $('meetingDetails').hidden=!chapter;
  $('meetingNameField').hidden=!chapter;$('meetingName').value=chapter?.name||'';
  $('removeMeeting').hidden=$('meetingUp').hidden=$('meetingDown').hidden=!chapter;
  $('meetingUp').disabled=chapterIndex<=0;$('meetingDown').disabled=chapterIndex<0||chapterIndex>=profile.meetings.length-1;$('addMeeting').disabled=profile.meetings.length>=38;
  for(const tab of $('categories').children){const active=tab.dataset.category===category;tab.classList.toggle('selected',active);tab.setAttribute('aria-selected',String(active));tab.tabIndex=active?0:-1;}
  $('stages').replaceChildren(...CATEGORIES[category].stages.map(key=>Object.assign(stageNode('option',key),{value:key})));$('stages').value=stage;
  $('tierField').hidden=!isAttack(stage);$('affinityTier').value=tier;
  const affinity=profile.affinity;
  $('pearlGiftEnabled').checked=affinity.pearlGiftEnabled;$('pearlGiftAmount').value=affinity.pearlGiftAmount;$('pearlGiftAmount').disabled=!affinity.enabled||!affinity.pearlGiftEnabled;
  $('affinityOptions').hidden=category!=='affinity';$('affinityEnabled').checked=affinity.enabled;$('affinityInitial').value=affinity.initial;$('refuseBelow').value=affinity.refuseBelow;$('attackMode').value=affinity.attackMode;
  for(const key of ['rockPenalty','spearPenalty']){$(key).value=affinity[key];$(key).disabled=affinity.attackMode!=='gradual';}
  $('observationOptions').hidden=category!=='observation';$('observationEnabled').checked=profile.observation.enabled;$('observationCooldown').value=profile.observation.cooldown;
  $('greetingEnabled').checked=profile.pearlReading.greetingEnabled;for(const key of ['greetingDelay','quickReturnWindow','returnCooldown'])$(key).value=profile.pearlReading[key];$('extractStomachPearl').checked=profile.pearlReading.extractStomachPearl;$('readingOptions').hidden=category!=='reading';$('readingPresentation').replaceChildren(ActionEditor.presentation.create(profile.pearlReading.presentation,value=>{profile.pearlReading.presentation=value;changed();},{label:'读珠默认表现'}));
  $('preventRepeat').checked=profile.pearlReading.preventSameCycleRepeat;$('manyEnabled').checked=profile.pearlReading.manyEnabled;$('manyThreshold').value=profile.pearlReading.manyThreshold;
  $('interruptOptions').hidden=!['story','interrupt'].includes(category);$('eventToggle').hidden=category!=='interrupt';$('eventEnabled').checked=stage==='pickup'?profile.pickupEnabled:profile.leaveEnabled;$('cooldown').value=profile.cooldown;
  $('greetingOptions').hidden=category!=='greeting';$('pearlRepeatOptions').hidden=stage!=='pearlRepeat';$('pearlManyOptions').hidden=stage!=='pearlMany';$('pearlLeaveOptions').hidden=!['pearlLeaving','pearlReturning'].includes(stage);$('pearlLeavePolicy').value=profile.pearlReading.leavePolicy;
  $('poolToolbar').hidden=!isPool();$('poolDeleteConfirm').hidden=true;
  if(isPool()){const groups=pools();poolIndex=Math.max(0,Math.min(poolIndex,groups.length-1));$('pool').replaceChildren(...groups.map((group,index)=>{const option=MI18n.content(el('option',(index+1)+'. '+group.name));option.value=index;return option;}));$('pool').value=poolIndex;$('poolName').value=groups[poolIndex]?.name||'';$('removePool').disabled=$('poolName').disabled=$('pool').disabled=!groups.length;$('addPool').disabled=groups.length>=40;}
  renderAction();renderLines();previewTitle();renderPreviewOptions();$('play').disabled=false;syncAddress();
}
function selectStage(key,index=0,fromPlayback=false,selectedTier=tier){if(!Object.hasOwn(STAGES,key))return;const contextChanged=stage!==key||poolIndex!==index||tier!==selectedTier;stage=key;poolIndex=index;tier=selectedTier;if(contextChanged&&!fromPlayback)stopPlayback(true);render();}
async function load(id){
  if(busy)return;
  if(dirty&&!confirm('当前对话尚未保存。放弃修改并切换迭代器？')){$('projects').value=project.projectId;return;}
  const previous=project?.projectId;setBusy(true);$('dialogueEditor').inert=$('dialoguePreview').inert=true;stopPlayback(true);
  try{const result=await api('dialogue?id='+encodeURIComponent(id));stopPlayback(true);project=projects.find(p=>p.projectId===id);profile=normalizeProfile(result.dialogue);revision=result.revision;dirty=false;editVersion=0;poolIndex=0;lastPools={};$('previewAffinity').value=profile.affinity.initial;$('affinityResult').textContent='';$('projects').value=id;render();setSaveState('saved');notice('');window.MIUndo?.reset();}
  catch(error){if(previous)$('projects').value=previous;throw error;}finally{setBusy(false);$('dialogueEditor').inert=$('dialoguePreview').inert=!profile;}
}
async function save(apply=false){
  if(!profile||busy)return;setBusy(true);
  const snapshot=structuredClone(profile),sentRevision=revision,sentVersion=editVersion,id=project.projectId;
  try{const result=await api('dialogue',{projectId:id,dialogue:snapshot,revision:sentRevision,apply});revision=result.revision;dirty=editVersion!==sentVersion;if(!dirty&&result.dialogue){profile=normalizeProfile(result.dialogue);render();}setSaveState(dirty?'unsaved':apply?'applied':'saved');notice(apply?'对话已应用到游戏。':'');}
  catch(error){
    // Applying can fail after the server saved the dialogue. Adopt the new
    // revision only if the server contains our submitted document.
    try{const latest=await api('dialogue?id='+encodeURIComponent(id));if(latest.revision!==sentRevision&&sameData(latest.dialogue,snapshot)){revision=latest.revision;dirty=editVersion!==sentVersion;setSaveState(dirty?'unsaved':'saved');error.message='对话已保存，应用未完成。'+error.message;}}catch(recoveryError){console.warn('Unable to check saved dialogue revision',recoveryError);}
    throw error;
  }finally{window.MIUndo?.rebase();setBusy(false);}
}
for(const [key,category] of Object.entries(CATEGORIES)){
  const tab=button(category.name,()=>selectStage(category.stages[0]));tab.dataset.category=key;tab.setAttribute('role','tab');
  tab.onkeydown=event=>{const all=[...$('categories').children];let index=all.indexOf(tab);if(event.key==='ArrowRight')index=(index+1)%all.length;else if(event.key==='ArrowLeft')index=(index+all.length-1)%all.length;else if(event.key==='Home')index=0;else if(event.key==='End')index=all.length-1;else return;event.preventDefault();selectStage(CATEGORIES[all[index].dataset.category].stages[0]);all[index].focus();};
  $('categories').append(tab);
}
function syncStoryStages(){
  for(const [name,label] of Object.entries(observationLabels)){const item=MI18n.text(label);STAGES['observation'+name]=MI18n.t('dialogue.ui.firstObservation',{item});STAGES['observationRepeat'+name]=MI18n.t('dialogue.ui.laterObservation',{item});}
  for(const key of Object.keys(STAGES))if(key.startsWith('meeting:'))delete STAGES[key];
  CATEGORIES.story.stages=['first','repeat',...profile.meetings.map((chapter,index)=>{const key='meeting:'+chapter.id;STAGES[key]=MI18n.t('dialogue.meetings.number',{n:index+3})+(chapter.name?' '+chapter.name:'');return key;}),'loop'];
  if(!Object.hasOwn(STAGES,stage))stage='first';
  const current=$('playEvent').value||'current';
  $('playEvent').replaceChildren(Object.assign(el('option','当前情境'),{value:'current'}),Object.assign(el('option','读取无色珍珠（完整流程）'),{value:'pearlRead'}),...Object.values(CATEGORIES).map(category=>{const group=el('optgroup');group.label=category.name;group.append(...category.stages.map(key=>Object.assign(stageNode('option',key),{value:key})));return group;}));
  $('playEvent').value=[...$('playEvent').options].some(option=>option.value===current)?current:'current';
}
for(const [id,key] of [['meetingEntries','minEntries'],['meetingCycle','minCycle']])$(id).onchange=()=>{const condition=meetingCondition(),value=Number($(id).value);if(!condition)return;if(!Number.isInteger(value)||value<0||value>9999){$(id).value=condition[key];return;}condition[key]=value;changed();};
$('meetingHeld').onchange=()=>{const condition=meetingCondition();if(condition){condition.held=$('meetingHeld').value;changed();}};
$('storyMode').onchange=()=>{profile.storyMode=$('storyMode').value;changed();};
$('addMeeting').onclick=()=>{if(profile.meetings.length>=38)return;const chapter={id:crypto.randomUUID().replaceAll('-',''),name:'',condition:{minEntries:0,minCycle:0,held:'any'},lines:[],action:{type:'none',delay:0}};profile.meetings.push(chapter);changed();syncStoryStages();selectStage('meeting:'+chapter.id);};
$('meetingName').oninput=()=>{const chapter=MIDialoguePreview.meeting(profile,stage);if(chapter){chapter.name=$('meetingName').value;changed();syncStoryStages();const option=$('stages').selectedOptions[0];if(option)option.textContent=STAGES[stage];previewTitle();}};
$('removeMeeting').onclick=()=>{const chapter=MIDialoguePreview.meeting(profile,stage);if(!chapter||!confirm('删除本次见面剧情及其全部台词？'))return;resetForStructure();profile.meetings.splice(profile.meetings.indexOf(chapter),1);changed();stage='repeat';render();};
for(const [id,offset] of [['meetingUp',-1],['meetingDown',1]])$(id).onclick=()=>{const chapter=MIDialoguePreview.meeting(profile,stage),index=profile.meetings.indexOf(chapter),target=index+offset;if(index<0||target<0||target>=profile.meetings.length)return;resetForStructure();profile.meetings.splice(index,1);profile.meetings.splice(target,0,chapter);changed();render();};
$('readingStillPreset').onclick=()=>ActionEditor.presets.open({kind:'presentation',value:profile.pearlReading.presentation,onApply:value=>{profile.pearlReading.presentation=value;changed();render();}});
$('stages').onchange=()=>selectStage($('stages').value);
$('affinityTier').onchange=()=>selectStage(stage,0,false,$('affinityTier').value);
$('playEvent').replaceChildren(Object.assign(el('option','当前情境'),{value:'current'}),Object.assign(el('option','读取无色珍珠（完整流程）'),{value:'pearlRead'}),...Object.entries(CATEGORIES).map(([,category])=>{const group=el('optgroup');group.label=category.name;group.append(...category.stages.map(key=>Object.assign(stageNode('option',key),{value:key})));return group;}));
$('playEvent').onchange=renderPreviewOptions;
$('resetAffinity').onclick=()=>{$('previewAffinity').value=profile.affinity.initial;$('affinityResult').textContent='';};
$('affinityEnabled').onchange=()=>{profile.affinity.enabled=$('affinityEnabled').checked;changed();render();};
$('pearlGiftEnabled').onchange=()=>{profile.affinity.pearlGiftEnabled=$('pearlGiftEnabled').checked;changed();render();};
$('observationEnabled').onchange=()=>{profile.observation.enabled=$('observationEnabled').checked;changed();};
$('attackMode').onchange=()=>{profile.affinity.attackMode=$('attackMode').value;changed();render();};
$('enabled').onchange=()=>{profile.enabled=$('enabled').checked;changed();};
for(const [id,key] of [['greetingEnabled','greetingEnabled'],['preventRepeat','preventSameCycleRepeat'],['manyEnabled','manyEnabled'],['extractStomachPearl','extractStomachPearl']])$(id).onchange=()=>{profile.pearlReading[key]=$(id).checked;changed();};
function bindNumber(id,target,key,min,max,integer=false){$(id).oninput=()=>{const n=Number($(id).value);if($(id).value!==''&&Number.isFinite(n)&&n>=min&&n<=max&&(!integer||Number.isInteger(n))){target()[key]=n;changed();}};$(id).onchange=()=>{const n=Number($(id).value);if($(id).value===''||!Number.isFinite(n)||n<min||n>max||integer&&!Number.isInteger(n)){$(id).value=target()[key];notice('请输入 '+min+'—'+max+(integer?' 之间的整数。':' 之间的数值。'),true);return;}target()[key]=n;changed();};}
bindNumber('pearlGiftAmount',()=>profile.affinity,'pearlGiftAmount',0,2);
bindNumber('affinityInitial',()=>profile.affinity,'initial',-1,1);bindNumber('refuseBelow',()=>profile.affinity,'refuseBelow',-1,1);bindNumber('rockPenalty',()=>profile.affinity,'rockPenalty',0,2);bindNumber('spearPenalty',()=>profile.affinity,'spearPenalty',0,2);bindNumber('observationCooldown',()=>profile.observation,'cooldown',0,60);
for(const key of ['quickReturnWindow','returnCooldown'])bindNumber(key,()=>profile.pearlReading,key,0,3600);
bindNumber('greetingDelay',()=>profile.pearlReading,'greetingDelay',0,120);bindNumber('manyThreshold',()=>profile.pearlReading,'manyThreshold',2,50,true);bindNumber('cooldown',()=>profile,'cooldown',0,60);
$('eventEnabled').onchange=()=>{profile[stage==='pickup'?'pickupEnabled':'leaveEnabled']=$('eventEnabled').checked;changed();};
$('pearlLeavePolicy').onchange=()=>{profile.pearlReading.leavePolicy=$('pearlLeavePolicy').value;changed();};
$('pool').onchange=()=>selectStage(stage,Number($('pool').value));
$('poolName').oninput=()=>{const group=pools()[poolIndex];if(!group)return;group.name=$('poolName').value;$('pool').selectedOptions[0].textContent=(poolIndex+1)+'. '+group.name;changed();};
$('addPool').onclick=()=>{if(pools().length>=40)return;resetForStructure();pools().push({name:MI18n.t('default.pool_name',{index:pools().length+1}),action:{type:'none',delay:0},lines:[{lineId:crypto.randomUUID().replaceAll('-',''),text:'',hold:2,gap:.6}]});poolIndex=pools().length-1;changed();render();};
$('removePool').onclick=()=>{$('removePool').closest('details').open=false;$('poolDeleteConfirm').hidden=false;$('cancelPoolDelete').focus();};
$('cancelPoolDelete').onclick=()=>$('poolDeleteConfirm').hidden=true;
$('confirmPoolDelete').onclick=()=>{resetForStructure();pools().splice(poolIndex,1);changed();render();};
$('addLine').onclick=()=>{const lines=lineList();if(!lines)return;if(lines.length>=200)return notice('每组最多 200 句。',true);resetForStructure();lines.push({lineId:crypto.randomUUID().replaceAll('-',''),text:'',hold:2,gap:.6});changed();renderLines();rowElements.get(lines.at(-1))?.querySelector('textarea')?.focus();};
$('addAction').onclick=()=>{const lines=lineList();if(!lines||lines.length>=200)return;resetForStructure();lines.push({lineId:crypto.randomUUID().replaceAll('-',''),kind:'action',text:'',hold:.1,gap:0,action:{type:'liftSpinPlayer',delay:0,duration:3}});changed();renderLines();rowElements.get(lines.at(-1))?.querySelector('select')?.focus();};
$('save').onclick=run(()=>save(false));$('apply').onclick=run(()=>save(true));$('projects').onchange=run(()=>load($('projects').value));

let queue=[],responses=[],timer=null,playing=false,away=false,isResponse=false,phase='idle',mainStage='first',mainPool=0,mainTier='neutral',lastPools={};
function playbackButton(){ $('play').textContent=MI18n.text(playing?'重新播放':'播放'); }
function setPlaying(value){playing=value;playbackButton();}
function stopPlayback(reset=false){
  clearTimeout(timer);timer=null;queue=[];responses=[];setPlaying(false);away=false;phase='idle';$('stop').disabled=true;
  if(reset){currentEntry=null;$('subtitle').textContent='……';$('transcript').replaceChildren();}
  markCurrent();
}
function entries(key,chosenPool=null,selectedTier=tier){return MIDialoguePreview.entries(profile,key,{chosenPool,tier:selectedTier,lastPools});}
function eventEnabled(key){
  if((MIDialoguePreview.isStory(key)||['pickup','leaving','returning'].includes(key))&&!profile.enabled)return '接待流程已关闭。';
  if(key==='pickup'&&!profile.pickupEnabled)return '拿起工作珍珠的打断已关闭。';
  if(['leaving','returning'].includes(key)&&!profile.leaveEnabled)return '离开与返回的打断已关闭。';
  if(categoryOf(key)==='greeting'&&!profile.pearlReading.greetingEnabled)return '日常招呼已关闭。';
  if(key==='pearlExtractedPreRead'&&!profile.pearlReading.extractStomachPearl)return '胃中取珠已关闭。';
  if(key==='pearlMany'&&!profile.pearlReading.manyEnabled)return '多珍珠提示已关闭。';
  if((isAttack(key)||key==='refusal')&&!profile.affinity.enabled)return social('affinityDisabled');
  if(key.startsWith('observation')&&!profile.observation.enabled)return social('observationDisabled');
  return '';
}
function showEntry(item){
  currentEntry=item;
  if(stage!==item.stage||isPool(item.stage)&&poolIndex!==item.poolIndex||isAttack(item.stage)&&tier!==item.tier)selectStage(item.stage,item.poolIndex??0,true,item.tier);
  
  $('subtitle').textContent=item.line.text;markCurrent(true);
  const transcript=el('li');transcript.append(stageNode('span',item.stage),document.createTextNode(' · '),MI18n.content(el('span',item.line.text)));$('transcript').append(transcript);
}
function simulateActions(actions,done,before=false){
  const action=actions.shift();if(!action){done();return;}
  phase=before?'beforeAction':'action';
  timer=setTimeout(()=>{
    if(!playing)return;
    
    timer=setTimeout(()=>{
      if(!playing)return;
      $('transcript').append(el('li',MI18n.text(ActionEditor.labels[action.type])));
      if(action.type==='killPlayer'){setPlaying(false);queue=[];responses=[];phase='idle';$('stop').disabled=true;return;}
      if(before&&currentEntry)currentEntry.beforeDone=(currentEntry.beforeDone||0)+1;
      simulateActions(actions,done,before);
    },(ActionEditor.seconds(action)-(action.delay||0))*1000);
  },action.delay*1000);
}

function next(){
  if(!playing)return;
  isResponse=responses.length>0;
  const item=isResponse?responses.shift():away?null:queue.shift();
  if(!item){phase='idle';if(away){return;}setPlaying(false);$('stop').disabled=true;return;}
  currentEntry=item;markCurrent(true);
  const after=()=>simulateActions((item.actions||[]).map(action=>({...action})),()=>{phase='gap';timer=setTimeout(next,Math.max(0,Number(item.line.gap))*1000);});
  simulateActions((item.beforeActions||[]).slice(item.beforeDone||0).map(action=>({...action})),()=>{
    if(!item.line.text.trim()){ $('subtitle').textContent='';after();return; }
    showEntry(item);phase='hold';timer=setTimeout(()=>{if(playing)after();},Math.max(.1,Number(item.line.hold))*1000);
  },true);
}
function interrupt(items){
  clearTimeout(timer);
  if(currentEntry&&!isResponse&&['hold','beforeAction'].includes(phase))queue.unshift(currentEntry);
  if(['action','beforeAction'].includes(phase))$('transcript').append(el('li',social('actionCancelled')));
  responses=items;phase='idle';next();
}
function previewValue(){const value=Number($('previewAffinity').value);if($('previewAffinity').value===''||!Number.isFinite(value)||value< -1||value>1){notice(social('affinityError'),true);return null;}return value;}
function play(){
  if(!profile)return;
  const event=$('playEvent').value,key=event==='current'?stage:event,disabled=eventEnabled(key);
  if(disabled)return notice(disabled);
  let selectedTier=tier,items;
  if(isAttack(key)&&event!=='current'){
    const before=previewValue();if(before===null)return;selectedTier=MIDialoguePreview.tier(before);
    const after=MIDialoguePreview.afterHit(profile.affinity,key,before);$('previewAffinity').value=after;
    $('affinityResult').textContent=social('affinityChange',{before:before.toFixed(2),after:after.toFixed(2)});
  }
  if(key==='pearlRead'){
    const value=previewValue();if(value===null)return;
    items=MIDialoguePreview.reading(profile,value,{lastPools,firstRead:$('previewFirstRead').checked,extracted:$('previewExtracted').checked&&profile.pearlReading.extractStomachPearl});
  }else if(['pearlGreeting','pearlQuickReturn','pearlRevisit'].includes(key))items=MIDialoguePreview.greeting(profile,$('previewCarrying').value,{base:key,lastPools,chosenPool:event==='current'?poolIndex:null});
  else items=entries(key,event==='current'&&isPool()?poolIndex:null,selectedTier);
  const canInterrupt=playing&&event!=='current'&&(['pickup','leaving','returning','pearlLeaving','pearlReturning','attackRock','attackSpear'].includes(key)||key.startsWith('observation'));
  if(canInterrupt){
    if(key==='leaving'||key==='pearlLeaving'){
      away=true;interrupt(items);
      if(key==='pearlLeaving'){
        const policy=profile.pearlReading.leavePolicy;
        if(policy==='restart')queue=entries(mainStage,isPool(mainStage)?mainPool:null,mainTier);
        if(policy==='cancel')queue=[];
      }
    }else{if(key==='returning'||key==='pearlReturning')away=false;interrupt(items);}
    return;
  }
  stopPlayback(true);queue=items;mainStage=items[0]?.stage||key;mainPool=items[0]?.poolIndex??poolIndex;mainTier=selectedTier;setPlaying(true);phase='waiting';$('stop').disabled=false;
  notice('');
  if(key==='pearlGreeting'&&items.length){timer=setTimeout(next,Math.max(0,profile.pearlReading.greetingDelay)*1000);}else next();
}
window.addEventListener('mi-language-change',playbackButton);
$('play').onclick=play;$('stop').onclick=()=>stopPlayback();

const splitKey='moreiterators.dialogue.split';let splitRatio=.58,splitPointer=null;
try{const stored=Number(localStorage.getItem(splitKey));if(stored>.1&&stored<.9)splitRatio=stored;}catch{}
function splitMetrics(){const node=$('dialogueLayout'),style=getComputedStyle(node);return {node,left:node.getBoundingClientRect().left+parseFloat(style.paddingLeft),available:node.clientWidth-parseFloat(style.paddingLeft)-parseFloat(style.paddingRight)-2*parseFloat(style.columnGap)-10};}
function layoutSplit(width=null,persist=false){
  if(matchMedia('(max-width:860px)').matches)return;
  const {node,available}=splitMetrics(),left=Math.max(410,Math.min(available-310,width??available*splitRatio));node.style.setProperty('--editor-width',left+'px');
  if(width!==null)splitRatio=left/available;
  $('splitter').setAttribute('aria-valuenow',String(Math.round(left/available*100)));$('splitter').setAttribute('aria-valuemin',String(Math.round(410/available*100)));$('splitter').setAttribute('aria-valuemax',String(Math.round((available-310)/available*100)));
  if(persist)try{localStorage.setItem(splitKey,String(splitRatio));}catch{}
  document.querySelectorAll('#lines textarea').forEach(grow);
}
$('splitter').onpointerdown=event=>{if(event.button!==0)return;splitPointer=event.pointerId;$('splitter').setPointerCapture(splitPointer);document.body.classList.add('resizing');event.preventDefault();};
$('splitter').onpointermove=event=>{if(event.pointerId!==splitPointer)return;layoutSplit(event.clientX-splitMetrics().left);};
function endSplit(event){if(event.pointerId!==splitPointer)return;splitPointer=null;document.body.classList.remove('resizing');layoutSplit(null,true);}
$('splitter').onpointerup=endSplit;$('splitter').onpointercancel=endSplit;
$('splitter').onkeydown=event=>{const {available}=splitMetrics();let width=available*splitRatio;if(event.key==='ArrowLeft')width-=20;else if(event.key==='ArrowRight')width+=20;else if(event.key==='Home')width=410;else if(event.key==='End')width=available-310;else return;event.preventDefault();layoutSplit(width,true);};
// Author labels are protected from general text translation. Refresh their UI
// prefixes only; rebuilding the editor here would discard in-progress input.
window.addEventListener('mi-language-change',()=>{
  if(!profile)return;
  syncStoryStages();
  $('stageFieldLabel').textContent=MI18n.t(categoryOf(stage)==='story'?'dialogue.ui.selectStory':'dialogue.ui.selectContext');
  document.querySelectorAll('[data-story-stage]').forEach(node=>{const label=STAGES[node.dataset.storyStage];if(label!==undefined)node.textContent=label;});
});
window.addEventListener('resize',()=>layoutSplit());layoutSplit();
window.MIUndo?.register({key:()=>project?'dialogue:'+project.projectId:'',capture:()=>structuredClone(profile),busy:()=>busy,
 restore:snapshot=>{stopPlayback(true);profile=normalizeProfile(snapshot);lastPools={};render();changed();},onError:error=>notice(error.message,true)});
window.MIStudioPage={projectId:()=>project?.projectId,isBusy:()=>busy,saveBeforeNavigate:async()=>{if(dirty)await save(false);return !dirty;},error:message=>notice(message,true)};
window.addEventListener('beforeunload',event=>{if(dirty){event.preventDefault();event.returnValue='';}});
document.addEventListener('click',event=>{for(const details of document.querySelectorAll('.action-menu[open],.more-menu[open]'))if(!details.contains(event.target))details.open=false;});
run(async()=>{
  projects=await api('projects');
  if(!projects.length){const created=await api('save',await api('default'));projects=[created.project];}
  $('projects').replaceChildren(...projects.map(p=>{const option=el('option',p.name);option.value=p.projectId;return option;}));
  const params=new URLSearchParams(location.search),id=params.get('id')||params.get('projectId')||params.get('project');if(Object.hasOwn(STAGES,params.get('stage'))||/^meeting:[a-f0-9]{32}$/.test(params.get('stage')||''))stage=params.get('stage');if(MIDialoguePreview.tiers.includes(params.get('tier')))tier=params.get('tier');
  await load(projects.some(p=>p.projectId===id)?id:projects[0].projectId);
})();

}
