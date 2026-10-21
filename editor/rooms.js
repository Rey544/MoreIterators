'use strict';
const MIRoomChoices={
  rooms:catalog=>(catalog?.regions||[]).flatMap(region=>(region.rooms||[]).map(room=>({...room,region:room.region||region.name}))),
  filtered:(catalog,selected,query,current)=>{const region=selected==='@project'?current?.region||'':selected,search=String(query||'').trim().toUpperCase();return MIRoomChoices.rooms(catalog).filter(room=>(!region||room.region===region)&&(!search||(room.name+' '+room.region+' '+(room.tags||'')).toUpperCase().includes(search)));},
  connection:(catalog,room,node)=>{const target=room?.connections?.[node];if(!target)return {target:null,node:null};if(target==='DISCONNECTED')return {target,node:null};const rows=MIRoomChoices.rooms(catalog).filter(item=>item.name===target),matches=rows.length===1?rows[0].connections.map((value,index)=>value===room.name?index:-1).filter(index=>index>=0):[];return {target,node:matches.length===1?matches[0]:null};},
  owned:(catalog,room,current)=>room?.name===current?.ai||current?.entryMode==='copy'&&room?.name===current.entry||(catalog?.ownedRooms||[]).some(item=>item.room===room?.name),
  free:(room,node,current)=>room?.connections?.[node]==='DISCONNECTED'||current?.entryMode==='existing'&&room?.name===current.entry&&node===current.entryNode&&room?.connections?.[node]===current.ai,
  verified:room=>!!room?.verified&&!room.conditional&&!room.oracle&&Array.isArray(room.connections)&&room.connections.length===room.exitCount,
  live:catalog=>!!catalog?.fresh&&!!catalog.complete&&catalog.source==='live'&&Number.isFinite(Date.parse(catalog.capturedAt))&&Date.now()-Date.parse(catalog.capturedAt)>=0&&Date.now()-Date.parse(catalog.capturedAt)<=30000
};
const MIOverseerControls={
  ownerValid:value=>typeof value==='string'&&Array.from(value.trim()).length<=12&&!/[\p{Cc}\p{Cs}<>]/u.test(value),
  nameValid:value=>typeof value==='string'&&Array.from(value.trim()).length>=1&&Array.from(value.trim()).length<=60&&!/[\p{Cc}\p{Cs}<>]/u.test(value),
  defaultRooms:binding=>binding?[binding.ai,...(binding.entryMode==='copy'?[binding.entry]:[])]:[],
  rooms:(profile,binding)=>profile?.rooms||MIOverseerControls.defaultRooms(binding)
};
if(typeof module!=='undefined')module.exports={...MIRoomChoices,overseer:MIOverseerControls};
if(typeof document!=='undefined'){
const $=id=>document.getElementById(id),t=(key,values={})=>MI18n.t(`rooms.${key}`,values),ot=(key,values={})=>MI18n.t(`overseer.${key}`,values);
const el=(tag,text)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=text;return node;};
const content=(tag,text)=>MI18n.content(el(tag,text));
const option=(value,label,disabled=false)=>Object.assign(el('option',label),{value,disabled});
const api=async(path,data)=>{await MI18n.ready;const response=await fetch('/api/'+path,data===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const result=await response.json();if(!response.ok)throw Error(MI18n.error(result,response.statusText));return result;};
const run=fn=>async(...args)=>{try{return await fn(...args);}catch(error){notice(error.message,true);console.error(error);}};
let roomDraftDirty=false,roomDraftRevision=0;
let projects=[],project=null,description=null,binding=null,catalog=null,busy=false,dirty=false,plan=null,token=null,limit=80,catalogRefreshing=false,catalogTimer=null,appliedNoticeBinding=null;
let overseerDocument=null,overseerConfig=null,overseerAll=null,overseerProfileId='default',overseerDirty=false,cleanupDocument=null,cleanupBusy=false,cleanupConfirmedToken=null;
const overseerProbabilities=['lens','GateScene','Angry'];
function notice(message='',bad=false){appliedNoticeBinding=null;$('notice').textContent=message;$('notice').dataset.kind=bad?'error':'info';}
function warnings(host,items){$(host).replaceChildren(...(items||[]).map(message=>content('p',MI18n.text(message))));}
function setBusy(value){busy=value;$('projects').disabled=value||!projects.length;$('bindingFields').disabled=value||!description?.editable;$('previewBinding').disabled=value||!description?.editable;$('refreshCatalog').disabled=value;$('applyBinding').disabled=value||!token;overseerControls();cleanupControls();if(catalog)renderRooms();}
function invalidate(){plan=null;token=null;$('planContent').hidden=true;$('planEmpty').hidden=false;$('planEmpty').textContent=t('previewNeeded');$('applyBinding').disabled=true;if(project)$('saveState').textContent=t(dirty?'pending':description?.editable?'saved':'readOnly');}
function changed(){dirty=roomDraftDirty=true;invalidate();$('saveState').textContent=t('pending');renderPairs();notice();window.MIUndo?.changed();}
function endpoint(room,node){return node===null||node===undefined?t('shaftUnknown',{room}):t('shaft',{room,node,ordinal:node+1});}
function pairText(value){return endpoint(value.ai,value.aiNode)+' ↔ '+endpoint(value.entry,value.entryNode);}
for(const id of ['appliedPair','draftPair','livePair','previewPair'])MI18n.content($(id));
function appliedNotice(){if(appliedNoticeBinding)$('notice').replaceChildren(el('span',t('applied')+' '),content('span',pairText(appliedNoticeBinding)));}
function connectionText(room,node){const link=MIRoomChoices.connection(catalog,room,node);return endpoint(room.name,node)+' → '+(link.target==='DISCONNECTED'?t('disconnected'):link.target?endpoint(link.target,link.node):t('unknownConnection'));}
function plannedConnection(change,changes){if(change.to==='DISCONNECTED')return t('disconnected');const reverse=changes.filter(item=>item.room===change.to&&item.to===change.room);return endpoint(change.to,reverse.length===1?reverse[0].node:null);}
function renderPairs(){
  const applied=description?.binding;if(!binding||!applied){$('bindingPairs').hidden=true;return;}$('bindingPairs').hidden=false;
  $('appliedPair').textContent=pairText(applied);$('draftPair').textContent=pairText(binding);$('draftPairRow').hidden=!dirty;
  const rows=MIRoomChoices.rooms(catalog).filter(room=>room.name===applied.ai),room=rows.length===1?rows[0]:null;
  $('livePairLabel').textContent=t(MIRoomChoices.live(catalog)?'livePair':'catalogPair');
  $('livePair').textContent=room?connectionText(room,applied.aiNode):t('roomNotInCatalog',{room:applied.ai});
  $('projectRegion').replaceChildren(el('span',t('projectRegion')),content('span',applied.region));
}
function nodes(id,count,value,room=null){
  const maximum=Number.isInteger(count)&&count>0?Math.min(count,64):0;
  const name=id==='aiNode'?binding.ai:binding.entry;
  const choices=Array.from({length:maximum},(_,node)=>{const free=!room||MIRoomChoices.free(room,node,description?.binding);return MI18n.content(option(node,room?connectionText(room,node):endpoint(name,node),!free));});
  $(id).replaceChildren(...choices);$(id).value=String(value);
  if(!choices.some(choice=>String(choice.value)===String(value))){$(id).prepend(MI18n.content(option(value,endpoint(name,value)+' · '+t('unverified'),true)));$(id).value=String(value);}
}
function selectedRoom(){return MIRoomChoices.rooms(catalog).find(room=>room.name===binding?.entry);}
function renderNodes(){
  if(!binding)return;nodes('aiNode',description?.aiExitCount,binding.aiNode);
  const room=binding.entryMode==='existing'?selectedRoom():null;
  nodes('entryNode',room?.exitCount??description?.entryExitCount,binding.entryNode,room);
  let message='';if(binding.entryMode==='existing')message=!MIRoomChoices.live(catalog)?t('needsLive'):!room?t('chooseRoom'):!MIRoomChoices.verified(room)?t('unverifiedRoom'):!MIRoomChoices.free(room,binding.entryNode,description.binding)?t('occupied'):'';
  $('entryStatus').textContent=message;
}
function renderBinding(){
  if(!binding)return;for(const key of ['region','ai','entry','oracleId','entryMode'])$(key).value=binding[key];renderNodes();
  $('projectName').replaceChildren(content('span',project.name));warnings('bindingWarnings',description.warnings);renderPairs();setBusy(busy);
  for(const id of ['appearanceStudio','dialogueStudio','projectionStudio']){const href=({appearanceStudio:'/',dialogueStudio:'/dialogue',projectionStudio:'/projections'})[id];$(id).href=href+'?project='+encodeURIComponent(project.projectId)+'&lang='+MI18n.locale;}
  const params=new URLSearchParams(location.search);params.set('project',project.projectId);params.set('lang',MI18n.locale);history.replaceState(null,'','?'+params);
}
function renderCatalog(){
  const source=MIRoomChoices.live(catalog)?'live':catalog?.source==='live'?'stale':catalog?.source||'offline';
  $('catalogSource').textContent=t(source);$('catalogSource').dataset.source=source;
  $('catalogTime').textContent=catalog?.capturedAt?new Date(catalog.capturedAt).toLocaleTimeString():'';
  warnings('catalogWarnings',catalog?.warnings);
  const selected=$('catalogRegion').value;$('catalogRegion').replaceChildren(option('@project',t('projectRegion')),option('',t('allRegions')),...(catalog?.regions||[]).map(region=>contentOption(region.name,region.name)));$('catalogRegion').value=selected==='@project'||!selected||(catalog?.regions||[]).some(region=>region.name===selected)?selected:'@project';
  renderRooms();renderNodes();renderPairs();if(overseerConfig)renderOverseerRooms();
}
function contentOption(value,name){return MI18n.content(option(value,name));}
function cleanupControls(){const disabled=busy||cleanupBusy||!project;$('scanCleanup').disabled=disabled;$('prepareCleanup').disabled=disabled||!cleanupDocument?.canApply||!cleanupDocument?.token;$('confirmCleanup').disabled=disabled||!cleanupConfirmedToken;}
function resetCleanup(){cleanupDocument=null;cleanupConfirmedToken=null;$('cleanupConfirm').hidden=true;$('cleanupRooms').replaceChildren();warnings('cleanupWarnings',[]);$('cleanupState').textContent=t('cleanupNeedsScan');$('cleanupNotice').textContent='';$('prepareCleanup').textContent=t('cleanupButton',{count:0});cleanupControls();}
function renderCleanup(){
  const rooms=cleanupDocument?.rooms||[],ready=rooms.filter(room=>room.status==='ready');
  warnings('cleanupWarnings',cleanupDocument?.warnings);
  $('cleanupState').textContent=rooms.length?t('cleanupCount',{count:rooms.length}):t('cleanupEmpty');$('prepareCleanup').textContent=t('cleanupButton',{count:ready.length});
  $('cleanupRooms').replaceChildren(...rooms.map(room=>{const row=el('article');row.className='cleanup-room';const heading=el('header');heading.append(content('strong',room.name),el('span',t('cleanupStatus'+room.status)));row.append(heading);for(const reason of room.reasons||[])row.append(content('p',MI18n.text(reason)));
    if(room.files?.length){const files=el('details');files.append(el('summary',t('cleanupFiles',{count:room.files.length})));const list=el('ul');for(const file of room.files){const item=el('li');item.append(el('span',t('cleanupScope'+file.scope)+' · '),content('span',file.path),el('span',' · '+t('fileBytes',{size:file.size})));list.append(item);}files.append(list);row.append(files);}return row;}));cleanupControls();
}
async function loadCleanup(){
  if(busy||cleanupBusy||!project)return;const projectId=project.projectId;cleanupBusy=true;cleanupConfirmedToken=null;$('cleanupConfirm').hidden=true;cleanupControls();$('cleanupNotice').textContent='';
  try{const result=await api('room-cleanup?projectId='+encodeURIComponent(projectId));if(project?.projectId!==projectId)return;cleanupDocument=result;renderCleanup();}
  catch(error){if(project?.projectId===projectId){cleanupDocument=null;$('cleanupNotice').textContent=error.message;}}finally{cleanupBusy=false;cleanupControls();}
}
function overseerNotice(message='',bad=false){$('overseerNotice').textContent=message;$('overseerNotice').dataset.kind=bad?'error':'info';}
function overseerControls(){
  const disabled=busy||!overseerConfig||overseerDocument?.editable===false;
  $('overseerFields').disabled=disabled;$('overseerAppearance').disabled=!overseerConfig?.enabled;
  $('overseerOwner').disabled=!overseerConfig?.enabled;
  $('addOverseer').disabled=disabled||(overseerAll?.guests||[]).length>=16;$('removeOverseer').hidden=overseerProfileId==='default';
  $('saveOverseer').disabled=disabled;$('applyOverseer').disabled=disabled||!overseerDocument?.canApply;
}
function overseerStatus(){
  $('overseerState').dataset.state=overseerDirty?'dirty':'saved';
  $('overseerState').textContent=!overseerDocument?'':overseerDocument.editable===false?ot('readOnly'):overseerDirty?ot('unsaved'):overseerDocument.appliedRevision===overseerDocument.revision?ot('applied'):overseerDocument.revision>0?ot('saved'):ot('default');
}
function renderOverseer(){
  if(!overseerConfig){overseerControls();overseerStatus();return;}
  renderOverseerProfiles();renderOverseerRooms();
  $('overseerEnabled').checked=overseerConfig.enabled;$('overseerOwner').value=overseerConfig.ownerAbbreviation;
  for(const [name,key] of [['Body','bodyColors'],['Tip','tipColors']]){
    const colors=overseerConfig[key];$('overseer'+name+'Gradient').checked=colors.length===2;
    $('overseer'+name+'1').value=colors[0];$('overseer'+name+'2').value=colors[1]||colors[0];$('overseer'+name+'2').hidden=colors.length!==2;
  }
  $('overseerPupil').value=overseerConfig.eyePupil;$('overseerEyeWhite').value=overseerConfig.eyeWhite;
  for(const key of overseerProbabilities){$('overseerChance'+key).value=Number((overseerConfig.probabilities[key]*100).toFixed(6));$('overseerChance'+key).title=ot('chanceHint');$('overseerChance'+key).setAttribute('aria-label',ot(key));$('overseerLabel'+key).textContent=ot(key);}
  $('overseerProbabilities').title=ot('chanceHint');$('overseerOwner').setCustomValidity('');
  overseerControls();overseerStatus();drawOverseer();
}
function changedOverseer(){overseerDirty=true;overseerNotice();overseerStatus();overseerControls();drawOverseer();window.MIUndo?.changed();}
function adoptOverseer(result){overseerDocument=result;overseerAll=structuredClone(result.config);overseerAll.guests??=[];selectOverseerProfile(overseerProfileId,false);overseerDirty=false;renderOverseer();overseerNotice((result.warnings||[]).map(value=>MI18n.text(value)).join('\n')||(!result.canApply?ot('applyProjectFirst'):''));}
function selectOverseerProfile(id,render=true){
  overseerProfileId=id;overseerConfig=id==='default'?overseerAll:overseerAll?.guests.find(item=>item.id===id);
  if(!overseerConfig){overseerProfileId='default';overseerConfig=overseerAll;}
  $('removeOverseerConfirm').hidden=true;if(render)renderOverseer();
}
function renderOverseerProfiles(){
  if(!overseerAll)return;
  $('overseerProfiles').replaceChildren(option('default',ot('defaultProfile')),...overseerAll.guests.map(item=>contentOption(item.id,item.name)));$('overseerProfiles').value=overseerProfileId;
  $('overseerNameField').hidden=overseerProfileId==='default';$('overseerName').value=overseerConfig.name||'';$('overseerName').required=overseerProfileId!=='default';$('overseerName').setCustomValidity(overseerProfileId==='default'||MIOverseerControls.nameValid(overseerConfig.name)?'':ot('nameInvalid'));
  const owner=Object.hasOwn(overseerConfig,'ownerProjectId')?overseerConfig.ownerProjectId:project.projectId;
  const owners=[option('',ot('unbound')),...projects.map(item=>contentOption(item.projectId,item.name))];
  if(owner&&!projects.some(item=>item.projectId===owner))owners.push(contentOption(owner,owner+' · '+ot('ownerUnavailable')));
  $('overseerOwnerProject').replaceChildren(...owners);$('overseerOwnerProject').value=owner;
}
function overseerDefaultRooms(){return MIOverseerControls.defaultRooms(description?.binding);}
function overseerRooms(){return MIOverseerControls.rooms(overseerConfig,description?.binding);}
function renderOverseerRooms(){
  if(!overseerConfig)return;
  const selected=overseerRooms(),defaultMode=!Object.hasOwn(overseerConfig,'rooms');
  $('overseerDefaultRoomsField').hidden=overseerProfileId!=='default';$('overseerDefaultRooms').checked=defaultMode;
  $('overseerSelectedRooms').replaceChildren(...selected.map(name=>{const label=el('label'),input=el('input');label.className='check-row';input.type='checkbox';input.checked=true;input.onchange=()=>{overseerConfig.rooms=selected.filter(room=>room!==name);changedOverseer();renderOverseerRooms();};label.append(input,content('span',name));return label;}));
  if(!selected.length)$('overseerSelectedRooms').append(el('span',ot('noRooms')));
  const known=new Set(MIRoomChoices.rooms(catalog).filter(room=>room.verified&&!room.conditional).map(room=>room.name));for(const name of overseerDefaultRooms())known.add(name);if(description?.binding?.entry)known.add(description.binding.entry);
  const search=$('overseerRoomSearch').value.trim().toUpperCase(),previous=$('overseerRoomChoice').value,available=[...known].filter(name=>!selected.includes(name)&&(!search||name.includes(search))).sort();
  $('overseerRoomChoice').replaceChildren(option('',ot('chooseRoom')),...available.slice(0,300).map(name=>contentOption(name,name)));if(available.includes(previous))$('overseerRoomChoice').value=previous;
  $('addOverseerRoom').disabled=!$('overseerRoomChoice').value||selected.length>=64;
  $('overseerRoomCatalog').textContent=ot(MIRoomChoices.live(catalog)?'roomsLive':'roomsCached');
}
$('overseerProfiles').onchange=()=>selectOverseerProfile($('overseerProfiles').value);
$('addOverseer').onclick=()=>{if(!overseerAll||overseerAll.guests.length>=16)return;const item={id:crypto.randomUUID().replaceAll('-',''),name:ot('newProfile'),enabled:false,ownerProjectId:'',ownerAbbreviation:'',rooms:[],bodyColors:['#72E6C4'],tipColors:['#B4FFF2'],eyeWhite:'#FFFFFF',eyePupil:'#000000',probabilities:{lens:.35,GateScene:.2,Angry:0}};overseerAll.guests.push(item);changedOverseer();selectOverseerProfile(item.id);};
$('removeOverseer').onclick=()=>$('removeOverseerConfirm').hidden=false;
$('cancelRemoveOverseer').onclick=()=>$('removeOverseerConfirm').hidden=true;
$('confirmRemoveOverseer').onclick=()=>{if(overseerProfileId==='default')return;overseerAll.guests=overseerAll.guests.filter(item=>item.id!==overseerProfileId);selectOverseerProfile('default');changedOverseer();};
$('overseerName').oninput=()=>{if(overseerProfileId==='default')return;overseerConfig.name=$('overseerName').value;$('overseerName').setCustomValidity(MIOverseerControls.nameValid(overseerConfig.name)?'':ot('nameInvalid'));changedOverseer();const item=[...$('overseerProfiles').options].find(option=>option.value===overseerProfileId);if(item)item.textContent=overseerConfig.name;};
$('overseerOwnerProject').onchange=()=>{overseerConfig.ownerProjectId=$('overseerOwnerProject').value;changedOverseer();};
$('overseerDefaultRooms').onchange=()=>{if($('overseerDefaultRooms').checked)delete overseerConfig.rooms;else overseerConfig.rooms=overseerDefaultRooms();changedOverseer();renderOverseerRooms();};
$('overseerRoomSearch').oninput=renderOverseerRooms;
$('overseerRoomChoice').onchange=()=>$('addOverseerRoom').disabled=!$('overseerRoomChoice').value||overseerRooms().length>=64;
$('addOverseerRoom').onclick=()=>{const name=$('overseerRoomChoice').value;if(!name)return;overseerConfig.rooms=[...overseerRooms(),name];changedOverseer();renderOverseerRooms();};
function drawOverseer(time=0){
  if(!overseerConfig)return;
  MIOverseerPreview.draw($('overseerCanvas'),overseerConfig,time);
}
let overseerPreviewFrame=0;
function animateOverseerPreview(now){
  if(now-overseerPreviewFrame>90&&!document.hidden&&overseerConfig){
    const rect=$('overseerCanvas').getBoundingClientRect();
    if(rect.bottom>0&&rect.top<innerHeight){drawOverseer(now/1000);overseerPreviewFrame=now;}
  }
  requestAnimationFrame(animateOverseerPreview);
}
requestAnimationFrame(animateOverseerPreview);
function renderRooms(){
  const all=MIRoomChoices.filtered(catalog,$('catalogRegion').value,$('roomSearch').value,description?.binding);
  $('roomCount').textContent=all.length>limit?t('visibleRooms',{visible:limit,total:all.length}):t('roomCount',{count:all.length});$('roomList').replaceChildren(...all.slice(0,limit).map(room=>{
    const card=el('article');card.className='room-card';card.classList.toggle('selected',room.name===binding?.entry&&binding?.entryMode==='existing');
    const header=el('div');header.className='room-card-header';header.append(content('strong',room.name));
    const owned=MIRoomChoices.owned(catalog,room,description?.binding),choose=el('button',t('useRoom'));choose.type='button';choose.disabled=busy||!description?.editable||!MIRoomChoices.live(catalog)||!MIRoomChoices.verified(room)||owned||room.name===binding?.ai||!room.connections.some((_,node)=>MIRoomChoices.free(room,node,description.binding));
    choose.onclick=()=>{if(busy)return;const oldRegion=binding.region;binding.entryMode='existing';binding.entry=room.name;binding.region=room.region;if(binding.ai.startsWith(oldRegion+'_'))binding.ai=room.region+binding.ai.slice(oldRegion.length);binding.entryNode=room.connections.findIndex((_,node)=>MIRoomChoices.free(room,node,description.binding));changed();renderBinding();renderRooms();};header.append(choose);card.append(header);
    const meta=el('div');meta.className='room-meta';meta.append(content('span',room.region),el('span',Number.isInteger(room.exitCount)&&room.exitCount>=0?t('exits',{count:room.exitCount}):t('unknownExits')));if(owned)meta.append(el('span',t('projectOwnedRoom')));else if(room.oracle)meta.append(el('span',t('oracleRoom')));if(room.conditional)meta.append(el('span',t('conditional')));if(!room.verified)meta.append(el('span',t('unverified')));card.append(meta);
    const links=el('div');links.className='room-links';(room.connections||[]).forEach((target,node)=>links.append(content('p',connectionText(room,node))));card.append(links);return card;
  }));$('showMore').hidden=all.length<=limit;
}
async function loadProject(id){
  if(busy)return;if(project&&(roomDraftDirty||overseerDirty)){try{await saveRoomDrafts();}catch(error){$('projects').value=project.projectId;throw error;}}
  if(!projects.some(item=>item.projectId===id)){project=null;binding=null;description=null;overseerDocument=null;overseerConfig=null;overseerAll=null;overseerProfileId='default';overseerDirty=false;invalidate();resetCleanup();renderPairs();setBusy(false);overseerStatus();$('saveState').textContent=t('noProject');notice();return;}
  setBusy(true);invalidate();
  try{const [result,overseer,draft]=await Promise.all([api('room-binding?projectId='+encodeURIComponent(id)),api('overseer?projectId='+encodeURIComponent(id)),api('room-draft?projectId='+encodeURIComponent(id))]);project=projects.find(item=>item.projectId===id);description=result;binding=structuredClone(draft.binding||result.binding);roomDraftRevision=draft.revision;dirty=!!draft.binding;roomDraftDirty=false;resetCleanup();$('projects').value=id;$('catalogRegion').value='@project';$('roomSearch').value='';limit=80;$('saveState').textContent=t(dirty?'pending':result.editable?'saved':'readOnly');renderBinding();renderCatalog();overseerProfileId='default';adoptOverseer(overseer);notice();window.MIUndo?.reset();}
  catch(error){$('projects').value=project?.projectId||'';throw error;}finally{setBusy(false);renderRooms();if($('cleanupDetails').open&&!cleanupDocument)loadCleanup();}
}
for(const key of ['region','ai','entry','oracleId'])$(key).oninput=()=>{if(!binding)return;binding[key]=$(key).value;changed();if(key==='entry'||key==='ai')renderNodes();};
$('entryMode').onchange=()=>{binding.entryMode=$('entryMode').value;changed();renderNodes();renderRooms();};
for(const key of ['aiNode','entryNode'])$(key).onchange=()=>{binding[key]=Number($(key).value);changed();renderNodes();};
$('projects').onchange=run(()=>loadProject($('projects').value));
$('roomSearch').oninput=$('catalogRegion').onchange=()=>{limit=80;renderRooms();};$('showMore').onclick=()=>{limit+=80;renderRooms();};
$('projectRegion').onclick=()=>{$('catalogRegion').value='@project';$('roomSearch').value='';limit=80;renderRooms();};
async function refreshCatalog(manual=false){
  if(busy||catalogRefreshing)return;catalogRefreshing=true;if(manual)$('refreshCatalog').disabled=true;
  try{const next=await api('rooms'),previousRoom=MIRoomChoices.rooms(catalog).find(room=>room.name===binding?.entry),nextRoom=MIRoomChoices.rooms(next).find(room=>room.name===binding?.entry);
    const invalidatePlan=token&&(manual||catalog?.generation!==next.generation||binding?.entryMode==='existing'&&(!MIRoomChoices.live(next)||JSON.stringify(previousRoom)!==JSON.stringify(nextRoom)));
    catalog=next;if(invalidatePlan){invalidate();notice(t('catalogChanged'));}renderCatalog();
  }catch(error){renderCatalog();if(manual)notice(error.message,true);}finally{catalogRefreshing=false;$('refreshCatalog').disabled=busy;}
}
function scheduleCatalog(){clearTimeout(catalogTimer);catalogTimer=setTimeout(async()=>{if(!document.hidden)await refreshCatalog();scheduleCatalog();},10000);}
$('refreshCatalog').onclick=()=>refreshCatalog(true);
function renderPlan(){
  if(!plan)return;warnings('planWarnings',plan.warnings);
    $('connectionChanges').replaceChildren(...(plan.connectionChanges||[]).map(change=>{const row=el('tr'),room=MIRoomChoices.rooms(catalog).find(item=>item.name===change.room),previous=MIRoomChoices.connection(catalog,room,change.node);row.append(content('td',change.room),content('td',t('shaftIndex',{node:change.node,ordinal:change.node+1})),content('td',change.fromRoom==='DISCONNECTED'?t('disconnected'):endpoint(change.fromRoom||t('unknownConnection'),previous.target===change.fromRoom?previous.node:null)),content('td',plannedConnection(change,plan.connectionChanges||[])));return row;}));
    $('roomCopies').replaceChildren(...(plan.roomCopies||[]).map(room=>{const item=el('li');item.append(el('span',t(room.kind==='ai'?'copyAi':'copyEntry')),document.createTextNode(' · '),content('span',room.name));return item;}));
    $('worldFileContent').replaceChildren(...Object.entries(plan.worldFiles||{}).flatMap(([path,text])=>{const name=content('p',path);name.className='world-file-name';return [name,content('pre',text)];}));
    $('previewPair').textContent=pairText(plan.binding);$('planContent').hidden=false;$('planEmpty').hidden=true;
}
$('bindingForm').onsubmit=run(async event=>{
  event.preventDefault();if(busy||!description?.editable)return;setBusy(true);invalidate();notice();
  try{const result=await api('room-binding/preview',{projectId:project.projectId,binding:structuredClone(binding)});plan=result.plan||result;token=result.token||plan.token;
    if(!token)throw Error(t('missingToken'));binding=structuredClone(plan.binding);renderBinding();warnings('planWarnings',plan.warnings);
    renderPlan();$('saveState').textContent=t('previewed');renderPairs();window.MIUndo?.rebase();
  }catch(error){invalidate();throw error;}finally{setBusy(false);}
});
$('applyBinding').onclick=run(async()=>{
  if(busy||!token)return;setBusy(true);notice();
  try{const result=await api('room-binding/apply',{projectId:project.projectId,binding:structuredClone(binding),token});binding=structuredClone(result.binding||binding);description.binding=structuredClone(binding);dirty=roomDraftDirty=false;invalidate();resetCleanup();renderBinding();$('saveState').textContent=t('restart');warnings('bindingWarnings',result.warnings||[]);appliedNoticeBinding=structuredClone(binding);appliedNotice();
    // A previously autosaved draft must not reappear after a newer binding
    // was applied. Keep revision checks: another tab may own a newer draft.
    try{const draft=await api('room-draft',{projectId:project.projectId,binding:structuredClone(binding),revision:roomDraftRevision});roomDraftRevision=draft.revision;}
    catch(error){let matches=false;try{const latest=await api('room-draft?projectId='+encodeURIComponent(project.projectId));matches=!latest.binding||JSON.stringify(latest.binding)===JSON.stringify(binding);if(matches)roomDraftRevision=latest.revision;}catch(_){}if(!matches)notice(t('appliedDraftPending',{error:error.message}),true);}
    renderOverseerRooms();window.MIUndo?.rebase();
    try{const latest=await api('overseer?projectId='+encodeURIComponent(project.projectId));if(overseerDocument){overseerDocument.canApply=latest.canApply;if(latest.revision===overseerDocument.revision)overseerDocument.appliedRevision=latest.appliedRevision;overseerStatus();}}catch(error){console.warn(error);}
  }
  catch(error){invalidate();throw error;}finally{setBusy(false);renderRooms();}
});
for(const key of overseerProbabilities){
  const label=el('label'),caption=el('span'),percent=el('span'),input=el('input');caption.id='overseerLabel'+key;percent.className='overseer-percent';
  input.id='overseerChance'+key;input.type='number';input.min=0;input.max=100;input.step='any';input.required=true;input.setAttribute('aria-label',ot(key));
  input.oninput=()=>{if(overseerConfig){if(input.validity.valid)overseerConfig.probabilities[key]=Number(input.value)/100;changedOverseer();}};
  percent.append(input,el('span','%'));label.append(caption,percent);$('overseerProbabilities').append(label);
}
$('overseerEnabled').onchange=()=>{overseerConfig.enabled=$('overseerEnabled').checked;changedOverseer();};
$('overseerOwner').oninput=()=>{const value=$('overseerOwner').value;overseerConfig.ownerAbbreviation=value;$('overseerOwner').setCustomValidity(MIOverseerControls.ownerValid(value)?'':ot('ownerInvalid'));changedOverseer();};
for(const [name,key] of [['Body','bodyColors'],['Tip','tipColors']]){
  const update=()=>{const dual=$('overseer'+name+'Gradient').checked;overseerConfig[key]=[$('overseer'+name+'1').value];if(dual)overseerConfig[key].push($('overseer'+name+'2').value);$('overseer'+name+'2').hidden=!dual;changedOverseer();};
  $('overseer'+name+'Gradient').onchange=update;for(const side of ['1','2'])$('overseer'+name+side).oninput=update;
}
for(const [id,key] of [['overseerPupil','eyePupil'],['overseerEyeWhite','eyeWhite']])$(id).oninput=()=>{overseerConfig[key]=$(id).value;changedOverseer();};
async function persistOverseer(apply){
  if(busy||!overseerConfig)return false;if(!$('overseerForm').reportValidity()){overseerNotice(MI18n.t('studio.navigation.invalid'),true);return false;}
  setBusy(true);overseerNotice();
  try{const result=await api('overseer/'+(apply?'apply':'save'),{projectId:project.projectId,config:structuredClone(overseerAll),revision:overseerDocument.revision});adoptOverseer(result);invalidate();resetCleanup();window.MIUndo?.rebase();return true;}
  catch(error){overseerNotice(error.message,true);console.error(error);return false;}finally{setBusy(false);}
}
$('overseerForm').onsubmit=event=>{event.preventDefault();persistOverseer(false);};$('applyOverseer').onclick=()=>persistOverseer(true);
$('cleanupDetails').ontoggle=()=>{if($('cleanupDetails').open&&!cleanupDocument)loadCleanup();};$('scanCleanup').onclick=loadCleanup;
$('prepareCleanup').onclick=()=>{if(!cleanupDocument?.canApply||busy||cleanupBusy)return;cleanupConfirmedToken=cleanupDocument.token;$('cleanupConfirmRooms').replaceChildren(...cleanupDocument.rooms.filter(room=>room.status==='ready').map(room=>content('li',room.name)));$('cleanupConfirm').hidden=false;cleanupControls();};
$('cancelCleanup').onclick=()=>{cleanupConfirmedToken=null;$('cleanupConfirm').hidden=true;cleanupControls();};
$('confirmCleanup').onclick=async()=>{
  if(busy||cleanupBusy||!cleanupConfirmedToken||cleanupConfirmedToken!==cleanupDocument?.token)return;const confirmed=cleanupConfirmedToken;setBusy(true);
  try{const result=await api('room-cleanup/apply',{projectId:project.projectId,token:confirmed}),previous=cleanupDocument;cleanupDocument={...previous,token:null,canApply:false,rooms:(result.retained||[]).map(room=>({...previous.rooms.find(item=>item.name===room.name),...room}))};cleanupConfirmedToken=null;$('cleanupConfirm').hidden=true;renderCleanup();invalidate();$('cleanupNotice').textContent=t('cleanupDoneRooms',{rooms:(result.deleted||[]).join('、')});}
  catch(error){cleanupConfirmedToken=null;if(cleanupDocument){cleanupDocument.token=null;cleanupDocument.canApply=false;}$('cleanupConfirm').hidden=true;$('cleanupNotice').textContent=error.message;}finally{setBusy(false);}
};
async function saveRoomDrafts(){
 if(roomDraftDirty){setBusy(true);try{const result=await api('room-draft',{projectId:project.projectId,binding:structuredClone(binding),revision:roomDraftRevision});roomDraftRevision=result.revision;roomDraftDirty=false;}finally{setBusy(false);}}
 if(overseerDirty&&!await persistOverseer(false))throw Error($('overseerNotice').textContent||MI18n.t('studio.navigation.incomplete'));
 window.MIUndo?.rebase();
 return !roomDraftDirty&&!overseerDirty;
}
window.MIStudioPage={projectId:()=>project?.projectId,isBusy:()=>busy||cleanupBusy||!!window.MIUndo?.busy,saveBeforeNavigate:saveRoomDrafts,error:message=>notice(message,true)};
window.MIUndo?.register({key:()=>project?.projectId,capture:()=>({binding,overseer:overseerAll}),busy:()=>busy||cleanupBusy||!binding,
 restore:value=>{const roomChanged=JSON.stringify(binding)!==JSON.stringify(value.binding),monitorChanged=JSON.stringify(overseerAll)!==JSON.stringify(value.overseer);binding=structuredClone(value.binding);overseerAll=structuredClone(value.overseer);if(roomChanged)dirty=roomDraftDirty=true;if(monitorChanged)overseerDirty=true;invalidate();renderBinding();renderRooms();selectOverseerProfile(overseerProfileId);overseerStatus();notice();},onError:error=>notice(error.message,true)});
window.addEventListener('beforeunload',event=>{if(roomDraftDirty||overseerDirty){event.preventDefault();event.returnValue='';}});
document.addEventListener('visibilitychange',()=>{if(!document.hidden)refreshCatalog();});
window.addEventListener('mi-language-change',()=>{if(catalog)renderCatalog();if(binding)renderBinding();if(plan)renderPlan();appliedNotice();if(cleanupDocument)renderCleanup();if(overseerConfig){renderOverseerProfiles();renderOverseerRooms();for(const key of overseerProbabilities){$('overseerChance'+key).title=ot('chanceHint');$('overseerChance'+key).setAttribute('aria-label',ot(key));$('overseerLabel'+key).textContent=ot(key);}$('overseerProbabilities').title=ot('chanceHint');overseerStatus();}});
run(async()=>{setBusy(true);try{[projects,catalog]=await Promise.all([api('projects'),api('rooms')]);if(!projects.length){const created=await api('save',await api('default'));projects=[created.project];}$('projects').replaceChildren(option('',t('chooseProject')),...projects.map(item=>contentOption(item.projectId,item.name)));renderCatalog();const params=new URLSearchParams(location.search),id=params.get('project')||params.get('projectId')||params.get('id')||projects[0]?.projectId;busy=false;await loadProject(id);}finally{setBusy(false);scheduleCatalog();}})();
}
