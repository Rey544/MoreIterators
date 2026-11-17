'use strict';
// Availability belongs to the visible part, not its artwork or mirrored source.
// Keep disabled parts' canvases intact so reopening the part restores its work.
const PaintTargets=(()=>{
 let syncing=false,active=true;
 const on=(value)=>value!==false;
 function available(key,p=project){
  const d=p?.design;if(!d)return false;const layers=d.layers||{};
  if(!dimensions[key]||!p.textures?.[key]||!canvases[key]?.length)return false;
  if(key==='forehead'||key==='face')return on(layers.face);
  if(/^antennaLower[LR]$/.test(key))return on(layers.antenna)&&!!d.antennaLowerEnabled;
  if(/^antenna[LR]$/.test(key))return on(layers.antenna)&&on(d.antennaUpperEnabled);
  if(/^earDecoration[LR]$/.test(key))return on(layers.ears)&&!!d.earDecorationEnabled;
  if(/^ear[LR]$/.test(key))return on(layers.ears)&&on(d.earBodyEnabled);
  if(key==='gown')return on(layers.robe);
  if(key==='collar')return on(layers.collar)&&d.collarHeight>.01;
  if(key==='scarf')return !p.legacyOracle&&d.scarfPanels>0;
  const hand=/^puppetHand([0-3])$/.exec(key),sleeve=/^puppetSleeve([23])$/.exec(key);
  if(hand)return on(layers.hands)&&!!d.puppetArms?.[+hand[1]]?.enabled;
  if(key==='sleeve'||key==='sleeveR'||sleeve){
   const index=sleeve?+sleeve[1]:key==='sleeveR'?1:0,arm=d.puppetArms?.[index];
   return on(layers.sleeves)&&!!arm?.enabled&&on(arm.sleeveEnabled)&&(index>=2||on(d[index?'sleeveRightEnabled':'sleeveLeftEnabled']));
  }
  if(/^leg(Thigh|Knee|Shin)R?$/.test(key))return on(layers.feet)&&!!d.straightLegs;
  const piece=garmentFind(d,key);
  if(/^shawl[1-5]$/.test(key))return !!piece&&+key.slice(5)<=d.shawlCount;
  return !!piece?.enabled;
 }
 function visibleKeys(){return [...$('target').options].filter(option=>available(option.value)).map(option=>option.value);}
 function sync(refresh=true){
  if(syncing||!project)return active;
  syncing=true;
  try{
   const select=$('target'),keys=[];
   for(const option of select.options){const enabled=available(option.value);if(option.hidden===enabled)option.hidden=!enabled;if(option.disabled===enabled)option.disabled=!enabled;if(enabled)keys.push(option.value);}
   for(const group of select.querySelectorAll('optgroup')){const empty=![...group.children].some(option=>!option.hidden);if(group.hidden!==empty)group.hidden=empty;}
   const oldActive=active,logical=PuppetArms.selectedTarget(target);active=keys.length>0;
   const moved=active&&!keys.includes(logical);
   if(moved){stroke=null;target=PuppetArms.select(keys[0]);activeLayer=Math.min(activeLayer,canvases[target].length-1);}
   if(!active)stroke=null;
   select.disabled=!active;select.value=active?PuppetArms.selectedTarget(target):'';
   const panel=$('paintPanel');panel.dataset.empty=String(!active);
   for(const node of panel.querySelectorAll('.paint-zoom,.paint-tools,.paint-brush-rails,#paintLayers,#layersDivider,#paintHeightDivider')){node.hidden=!active;node.inert=!active;}
   $('paintViewport').inert=!active;$('paint').setAttribute('aria-disabled',String(!active));
   if(!active){$('layerList').replaceChildren();pc.clearRect(0,0,$('paint').width,$('paint').height);}
   if(refresh&&(moved||oldActive!==active))updateTarget();
   return active;
  }finally{syncing=false;}
 }
 function label(key){
  if(typeof key!=='string'||!key)return '';
  const d=typeof project==='undefined'?null:project?.design;
  const tr=(id,args)=>{if(typeof MI18n==='undefined')return '';const value=MI18n.t(id,args);return value===id?'':value;};
  const authored=value=>typeof value==='string'&&value.trim()?value:'';
  const accessory=d?.accessories?.find(item=>item.id===key);
  if(accessory)return authored(accessory.name)||tr('default.accessory_name',{index:d.accessories.indexOf(accessory)+1});
  const child=/^(.+)\/child\/(\d+)$/.exec(key),pearl=d?.pearlAccessories?.find(item=>item.id===(child?child[1]:key));
  if(pearl){
   if(child){const item=pearl.children?.[Number(child[2])];return item?authored(item.name)||tr('accessories28.76'):'';}
   return authored(pearl.name)||tr('accessories28.53');
  }
  const necklace=/^necklace:(\d+)$/.exec(key);
  if(necklace)return tr('necklace.title',{index:Number(necklace[1])+1});
  const names={head:'ui.0008',body:'ui.0030',neck:'ui.0155',footL:'previewSelection.leftFoot',footR:'previewSelection.rightFoot',gown:'ui.0035',collar:'ui.0140',scarf:'ui.0058',sleeve:'appearance.leftSleeve',sleeveR:'appearance.rightSleeve'};
  if(names[key])return tr(names[key]);
  const text=value=>typeof MI18n==='undefined'?value:MI18n.text(value);
  const host=typeof document==='undefined'?null:document.getElementById('groups');
  const summary=id=>{
   const section=[...(host?.querySelectorAll('details')||[])].find(node=>node.dataset.sectionId===id||node.dataset.paintTarget===id||node.dataset.previewPart===id);
   const value=section?.querySelector(':scope > summary')?.textContent?.trim();
   return value&&value!==id?text(value):'';
  };
  const eye=d?.eyes?.findIndex(item=>item.id===key)??-1,originalEye=/^eye([01])$/.exec(key);
  if(eye>=0)return summary(key)||tr('eyes35.eye',{index:eye+1});
  if(originalEye)return summary('eye-'+(Number(originalEye[1])+1))||tr(Number(originalEye[1])?'eyes35.originalRight':'eyes35.originalLeft');
  const select=typeof document==='undefined'?null:document.getElementById('target'),option=[...(select?.options||[])].find(item=>item.value===key),value=option?.textContent?.trim();
  return value&&value!==key?text(value):summary(key);
 }
 function locateSettings(key){
  const host=$('groups'),byId=id=>[...host.querySelectorAll('details')].find(node=>node.dataset.sectionId===id);
  const field=(root,name)=>root?.querySelector('[data-wardrobe-key="'+name+'"]');
  let section=null,anchor=null;
  if(key==='head')anchor=field(host,'headColor')?.closest('.field');
  else if(key==='body'||key==='neck')anchor=field(host,key==='body'?'torsoLength':'neckLength')?.closest('.field');
  else if(/^eye(?:\d+|-)/.test(key))section=byId(key)||byId('eye-'+(+key.slice(3)+1))||byId('eyes');
  else if(/^foot[LR]$/.test(key))anchor=field(host,key.endsWith('R')&&!project.design.legSymmetry?'rightLegLength':'legLength')?.closest('.field');
  else if(key.startsWith('necklace:'))section=byId(key)||byId('necklaces');
  else if(key.includes('/child/'))section=[...host.querySelectorAll('[data-preview-part]')].find(node=>node.dataset.previewPart===key);
  else if(/^puppetHand[0-3]$/.test(key))section=field(byId('puppetArm'+key.slice(-1)),'handTextureEnabled')?.closest('details');
  else if(['sleeve','sleeveR','puppetSleeve2','puppetSleeve3'].includes(key))section=field(byId('puppetArm'+(key==='sleeve'?0:key==='sleeveR'?1:key.slice(-1))),'sleeveEnabled')?.closest('details');
  else if(/^(antenna|ear)/.test(key))section=byId(key.slice(0,-1)+'-piece');
  else if(key==='forehead'||key==='face')anchor=field(host,key==='forehead'?'faceScale':'cheekScale')?.closest('.field');
  else if(key.startsWith('leg')){
   const name=key.startsWith('legThigh')?'thighLength':key.startsWith('legKnee')?'kneeSize':'shinLength';
   // With symmetric legs the right-side controls are intentionally hidden.
   // Reveal the live shared control without changing the symmetry setting.
   anchor=field(host,key.endsWith('R')&&!project.design.legSymmetry?rightLegKey(name):name)?.closest('.field');
  }
  else section=[...host.querySelectorAll('[data-paint-target]')].find(node=>node.dataset.paintTarget===key)||byId(key);
  section??=anchor?.closest('details');
  if(!section)return;
  for(let node=section;node&&node!==host;node=node.parentElement)if(node.tagName==='DETAILS')node.open=true;
  // Only explicit part selection calls this. Desktop scrolls the settings
  // pane; stacked layouts scroll the document. Undo/loading never call it.
  anchor??=section.querySelector(':scope > summary')||section;
  const settings=$('settings'),scrollable=/auto|scroll/.test(getComputedStyle(settings).overflowY)&&settings.scrollHeight>settings.clientHeight+1;
  const header=document.querySelector('body > header'),headerRect=header?.getBoundingClientRect();
  const viewportTop=headerRect&&headerRect.top<=0&&/fixed|sticky/.test(getComputedStyle(header).position)?Math.max(0,headerRect.bottom):0;
  if(scrollable)settings.scrollTop+=anchor.getBoundingClientRect().top-Math.max(settings.getBoundingClientRect().top,viewportTop)-12;
  const rect=anchor.getBoundingClientRect();
  if(!scrollable||rect.top<viewportTop+8||rect.bottom>innerHeight-8)window.scrollBy({top:rect.top-viewportTop-12,behavior:'instant'});
 }
 return {available,visibleKeys,sync,label,locateSettings,hasActive:()=>active};
})();
