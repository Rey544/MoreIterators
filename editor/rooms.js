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
const MIRoomIdentity={
  region:value=>/^[A-Z][A-Z0-9]{1,7}$/.test(String(value||'').trim().toUpperCase()),
  errors:value=>{
    const region=String(value?.region||'').trim().toUpperCase(),errors={};
    if(!MIRoomIdentity.region(region))errors.region={key:'regionFormat'};
    for(const key of ['ai','entry']){
      const name=String(value?.[key]||'').trim().toUpperCase();
      if(!/^[A-Z][A-Z0-9]{1,7}_[A-Z0-9_]{1,64}$/.test(name)||!errors.region&&!name.startsWith(region+'_'))errors[key]={key:'roomFormat',values:{example:(errors.region?'PL':region)+(key==='ai'?'_AI':'_POOL')}};
    }
    if(!errors.ai&&!errors.entry&&String(value.ai).trim().toUpperCase()===String(value.entry).trim().toUpperCase())errors.entry={key:'sameRoom'};
    return errors;
  },
  previewSource:(kind,draft,applied)=>kind==='ai'||draft.entryMode==='copy'?{room:applied[kind],region:applied.region}:{room:draft.entry,region:MIRoomIdentity.region(draft.region)?draft.region.trim().toUpperCase():applied.region}
};
if(typeof module!=='undefined')module.exports={...MIRoomChoices,overseer:MIOverseerControls,identity:MIRoomIdentity};
if(typeof document!=='undefined'){
const $=id=>document.getElementById(id),t=(key,values={})=>MI18n.t(`rooms.${key}`,values),ot=(key,values={})=>MI18n.t(`overseer.${key}`,values);
const el=(tag,text)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=text;return node;};
const content=(tag,text)=>MI18n.content(el(tag,text));
const option=(value,label,disabled=false)=>Object.assign(el('option',label),{value,disabled});
const api=async(path,data)=>{await MI18n.ready;const response=await fetch('/api/'+path,data===undefined?{headers:{'X-MI-Language':MI18n.locale}}:{method:'POST',headers:{'Content-Type':'application/json','X-MI-Language':MI18n.locale},body:JSON.stringify(data)});const result=await response.json();if(!response.ok)throw Error(MI18n.error(result,response.statusText));return result;};
const run=fn=>async(...args)=>{try{return await fn(...args);}catch(error){notice(error.message,true);console.error(error);}};
let roomDraftDirty=false,roomDraftRevision=0,bindingCheck=null,workflow=null;
let connectionSelection={ownedRoom:'',ownedNode:null,targetRoom:'',targetNode:null},selectedConnections=[],requiredConnectionId='';
let projects=[],project=null,description=null,binding=null,catalog=null,busy=false,dirty=false,limit=80,catalogRefreshing=false,catalogTimer=null,appliedNoticeBinding=null;
let roomLoadErrors={},roomDraftReady=false;
let connectionActionError='';
const exitRepairActions=el('div');exitRepairActions.className='room-actions';exitRepairActions.hidden=true;$('connectionError').style.whiteSpace='pre-line';$('connectionError').after(exitRepairActions);
let overseerDocument=null,overseerConfig=null,overseerAll=null,overseerProfileId='default',overseerDirty=false,cleanupDocument=null,cleanupBusy=false,cleanupConfirmedToken=null;
const overseerProbabilities=['lens','GateScene','Angry'];
function notice(message='',bad=false){appliedNoticeBinding=null;$('notice').textContent=message;$('notice').dataset.kind=bad?'error':'info';}
function warnings(host,items){$(host).replaceChildren(...[...new Set(items||[])].map(message=>content('p',MI18n.text(message))));}
function setBusy(value){
  busy=value;const editable=!!description?.editable,pending=!!workflow?.pending;
  $('projects').disabled=value||!projects.length;$('bindingFields').disabled=value||!editable||pending||!roomDraftReady;
  $('applyRoomNames').disabled=value||!editable||pending||!workflow||!roomDraftReady;$('cancelRoomNames').disabled=value;
  $('connectionFields').disabled=value||!editable||!workflow;$('applyConnection').disabled=value||!editable||!workflow;
  for(const button of exitRepairActions.querySelectorAll('button'))button.disabled=value||!editable||pending;
  $('refreshCatalog').disabled=value;for(const part of Object.values(diagramParts))part.preview.disabled=value||!part.room;
  overseerControls();cleanupControls();if(catalog)renderRooms();
}
function invalidate(){if(project)$('saveState').textContent=Object.keys(roomLoadErrors).length?'':t(workflow?.pending?'pendingReconnect':dirty?'pending':description?.editable?'saved':'readOnly');}
function changed(){dirty=roomDraftDirty=true;invalidate();renderIdentity();renderPairs();$('nameStatus').textContent='';$('nameError').textContent='';notice();window.MIUndo?.changed();}
function renderIdentity(){
  const errors=MIRoomIdentity.errors(binding);
  for(const key of ['region','ai','entry']){const error=errors[key],message=error?t(error.key,error.values):'';$(key).setCustomValidity(message);$(key).setAttribute('aria-invalid',String(!!error));$(key+'Error').textContent=message;}
  return !Object.keys(errors).length;
}
function endpoint(room,node){return node===null||node===undefined?t('shaftUnknown',{room}):t('shaft',{room,node,ordinal:node+1});}
function pairText(value){return endpoint(value.ai,value.aiNode)+' ↔ '+endpoint(value.entry,value.entryNode);}
function linkText(link){return endpoint(link.from.room,link.from.node)+' ↔ '+endpoint(link.to.room,link.to.node);}
function showLinks(id,links){$(id).replaceChildren(...(links||[]).map(link=>content('p',linkText(link))));}
for(const id of ['appliedPair','draftPair','livePair','bindingCheckPair','currentConnectionList','priorConnectionList'])MI18n.content($(id));
function appliedNotice(){if(appliedNoticeBinding)$('notice').textContent=t('connectionApplied');}
function connectionText(room,node){const link=MIRoomChoices.connection(catalog,room,node);return endpoint(room.name,node)+' → '+(link.target==='DISCONNECTED'?t('disconnected'):link.target?endpoint(link.target,link.node):t('unknownConnection'));}
function renderPairs(){
  const applied=description?.binding;if(!binding||!applied){$('bindingPairs').hidden=true;return;}$('bindingPairs').hidden=false;
  $('appliedPair').textContent=(workflow?.connections||[]).map(linkText).join('\n')||pairText(applied);$('draftPair').textContent=[binding.region,binding.ai,binding.entry].join(' ');
  $('bindingRecord').querySelector('[value=draft]').disabled=!dirty;if(!dirty&&$('bindingRecord').value==='draft')$('bindingRecord').value='applied';
  const record=$('bindingRecord').value;$('appliedPairRow').hidden=record!=='applied';$('livePairRow').hidden=record!=='catalog';$('draftPairRow').hidden=record!=='draft';
  const rows=MIRoomChoices.rooms(catalog).filter(room=>room.name===applied.ai),room=rows.length===1?rows[0]:null;
  $('livePairLabel').textContent=t(MIRoomChoices.live(catalog)?'livePair':['live','stale'].includes(catalog?.source)?'stalePair':'offlinePair');
  $('livePair').textContent=room?connectionText(room,applied.aiNode):t('roomNotInCatalog',{room:applied.ai});
  $('projectRegion').replaceChildren(el('span',t('projectRegion')),content('span',applied.region));
}
function workflowRooms(){
  const previous=new Set((workflow?.pending?.rooms||[]).filter(room=>room.original!==room.name).map(room=>room.original));
  const all=new Map((workflow?.rooms||[]).filter(room=>!room.owned&&!previous.has(room.name)).map(room=>[room.name,room]));
  for(const room of MIRoomChoices.rooms(catalog))if(!previous.has(room.name))all.set(room.name,room);
  for(const room of workflow?.rooms||[])if(room.owned)all.set(room.name,{...all.get(room.name),...room});
  return [...all.values()];
}
function ownRooms(){return (workflow?.rooms||[]).filter(room=>room.owned);}
function selectedRoom(name){return workflowRooms().find(room=>room.name===name);}
function pickerRoom(name){const pending=workflow?.pending?.rooms?.find(room=>room.original===name);return selectedRoom(pending?.name||name);}
function sourceRoom(name){return workflow?.pending?.rooms?.find(room=>room.name===name)?.original||name;}
function requiredOwnedRooms(){const required=workflow?.pending?.required||[],link=required.find(item=>item.id===requiredConnectionId)||required[0],owned=new Set(ownRooms().map(room=>room.name));return link?[link.room,link.toRoom].filter(name=>owned.has(name)):[];}
function allowedTarget(room){const required=requiredOwnedRooms();return !!room&&room.name!==connectionSelection.ownedRoom&&(required.length!==2||required.includes(room.name));}
function nodeAvailable(room,node){
  if(!room?.verified||!room.owned&&!MIRoomChoices.live(catalog))return false;
  const target=room.connections?.[node];if(target==='DISCONNECTED')return true;
  if(workflow?.pending)return (workflow.pending.required||[]).some(link=>(link.room===room.name&&link.node===node)||(link.toRoom===room.name&&link.toNode===node));
  return target===connectionSelection.ownedRoom||target===connectionSelection.targetRoom;
}
function renderNodes(){
  for(const [id,key,roomKey]of [['ownedNode','ownedNode','ownedRoom'],['targetNode','targetNode','targetRoom']]){
    const room=selectedRoom(connectionSelection[roomKey]),count=Number.isInteger(room?.exitCount)?Math.max(0,Math.min(64,room.exitCount)):0;
    $(id).replaceChildren(option('',t(room?'chooseExit':'chooseRoomFirst')),...Array.from({length:count},(_,node)=>option(node,t('exitOption',{ordinal:node+1}),!nodeAvailable(room,node))));
    $(id).value=connectionSelection[key]===null?'':String(connectionSelection[key]);
  }
  renderConnectionDiagram();
}
function resetConnectionSelection(){connectionSelection={ownedRoom:'',ownedNode:null,targetRoom:'',targetNode:null};}
function workflowIssueText(issue){
  if(issue.code==='exitCountMismatch')return t('error.workflowGeometryDetails',{room:issue.room,actual:issue.actualExitCount,slots:issue.connectionSlotCount,geometrySource:issue.geometrySource,connectionSource:issue.connectionSource});
  return t('error.workflowGeometry',{room:issue.room});
}
function renderWorkflowIssues(){
  const issues=workflow?.issues||[];$('connectionError').textContent=connectionActionError||roomLoadErrors.workflow||issues.map(workflowIssueText).join('\n');exitRepairActions.replaceChildren();
  if(!workflow?.pending)for(const issue of issues.filter(value=>value.canReconcile)){
    const owner=project?.projectId,row=el('div'),name=content('span',issue.room),button=el('button',t('refreshExits'));row.className='room-actions';button.type='button';button.dataset.room=issue.room;button.disabled=busy||!description?.editable;button.onclick=()=>reconcileExits(issue.room,owner);row.append(name,button);exitRepairActions.append(row);
  }
  exitRepairActions.hidden=!exitRepairActions.children.length;
}
function setConnectionError(message=''){connectionActionError=message;renderWorkflowIssues();}
async function reconcileExits(room,owner){
  if(busy||project?.projectId!==owner||!description?.editable||!workflow||workflow.pending||!(workflow.issues||[]).some(issue=>issue.room===room&&issue.canReconcile))return;
  const previousDirty=dirty,previousDraftDirty=roomDraftDirty;setConnectionError();setBusy(true);
  try{const result=await api('room-workflow/apply',{projectId:owner,revision:workflow.revision,connections:[],reconcileRooms:[room]});adoptWorkflow(result,{preserveNames:true});dirty=previousDirty;roomDraftDirty=previousDraftDirty;invalidate();renderPairs();$('connectionStatus').textContent=t('exitsUpdated');resetCleanup();window.MIUndo?.rebase();}
  catch(error){setConnectionError(error.message);}finally{setBusy(false);}
}
function renderConnections(){
  const pending=workflow?.pending;
  for(const [id,key]of [['ownedNode','ownExitLabel'],['targetRoom','targetRoomLabel'],['targetNode','targetExitLabel']])$(id).setAttribute('aria-label',t(key));
  $('cancelRoomNames').hidden=!pending;$('pendingConnectionNote').hidden=!pending;$('priorConnections').hidden=!pending;$('currentConnections').hidden=!!pending;
  showLinks('currentConnectionList',workflow?.connections);showLinks('priorConnectionList',workflow?.connections);
  const requiredOwned=requiredOwnedRooms();
  $('ownRoomChoices').replaceChildren(...ownRooms().filter(room=>requiredOwned.length!==2||requiredOwned.includes(room.name)).map(room=>{
    const button=el('button');button.append(content('span',room.name));button.title=room.name;button.type='button';button.setAttribute('aria-pressed',String(connectionSelection.ownedRoom===room.name));
    if(pending){const state=el('small',t(selectedConnections.some(link=>link.from.room===room.name||link.to.room===room.name)?'connectionSelected':'pendingReconnect'));button.append(state);}
    button.onclick=()=>{connectionSelection={ownedRoom:room.name,ownedNode:null,targetRoom:'',targetNode:null};setConnectionError();renderConnections();renderRooms();};return button;
  }));
  const targets=workflowRooms().filter(allowedTarget);
  $('targetRoom').replaceChildren(option('',t('targetRoomPlaceholder')),...targets.map(room=>contentOption(room.name,room.name)));
  $('targetRoom').value=connectionSelection.targetRoom;
  const required=pending?.required||[];$('requiredConnectionField').hidden=required.length<2;
  if(required.length&&!required.some(link=>link.id===requiredConnectionId))requiredConnectionId=required[0].id;
  $('requiredConnection').replaceChildren(...required.map(link=>contentOption(link.id,link.room+' ↔ '+link.toRoom+(selectedConnections.some(item=>item.replaces===link.id)?' ('+t('connectionSelected')+')':''))));$('requiredConnection').value=requiredConnectionId;
  renderNodes();renderWorkflowIssues();setBusy(busy);
}
function renderBinding(){
  if(!binding)return;for(const key of ['region','ai','entry','oracleId'])$(key).value=binding[key]||'';renderIdentity();renderConnections();
  warnings('bindingWarnings',description.warnings);renderPairs();
  for(const id of ['appearanceStudio','dialogueStudio','projectionStudio']){const href=({appearanceStudio:'/',dialogueStudio:'/dialogue',projectionStudio:'/projections'})[id];$(id).href=href+'?project='+encodeURIComponent(project.projectId)+'&lang='+MI18n.locale;}
  const params=new URLSearchParams(location.search);params.set('project',project.projectId);params.set('lang',MI18n.locale);history.replaceState(null,'','?'+params);
}
function renderCatalog(){
  const source=MIRoomChoices.live(catalog)?'live':catalog?.source==='live'?'stale':catalog?.source||'offline';
  $('catalogSource').textContent=t(source);$('catalogSource').dataset.source=source;
  $('catalogTime').textContent=catalog?.capturedAt?new Date(catalog.capturedAt).toLocaleTimeString():'';
  warnings('catalogWarnings',catalog?.warnings);
  const selected=$('catalogRegion').value;$('catalogRegion').replaceChildren(option('@project',t('projectRegion')),option('',t('allRegions')),...(catalog?.regions||[]).map(region=>contentOption(region.name,region.name)));$('catalogRegion').value=selected==='@project'||!selected||(catalog?.regions||[]).some(region=>region.name===selected)?selected:'@project';
  renderRooms();renderConnections();renderPairs();if(overseerConfig)renderOverseerRooms();
}
function contentOption(value,name){return MI18n.content(option(value,name));}
function cleanupControls(){const disabled=busy||cleanupBusy||!project;$('scanCleanup').disabled=disabled;$('prepareCleanup').disabled=disabled||!cleanupDocument?.canApply||!cleanupDocument?.token;$('confirmCleanup').disabled=disabled||!cleanupConfirmedToken;}
function resetCleanup(){cleanupDocument=null;cleanupConfirmedToken=null;$('cleanupConfirm').hidden=true;$('cleanupRooms').replaceChildren();warnings('cleanupWarnings',[]);$('cleanupState').textContent=t('cleanupNeedsScan');$('cleanupNotice').textContent='';$('prepareCleanup').textContent=t('cleanupButton',{count:0});cleanupControls();}
function renderCleanup(){
  const rooms=cleanupDocument?.rooms||[],ready=rooms.filter(room=>room.status==='ready');
  warnings('cleanupWarnings',cleanupDocument?.warnings);
  $('cleanupState').textContent=rooms.length?t('cleanupCount',{count:rooms.length}):t('cleanupEmpty');$('prepareCleanup').textContent=t('cleanupButton',{count:ready.length});
  $('cleanupRooms').replaceChildren(...rooms.map(room=>{const row=el('article');row.className='cleanup-room';const heading=el('header');heading.append(content('strong',room.name),el('span',t('cleanupStatus'+room.status)));row.append(heading);for(const reason of room.reasons||[])row.append(content('p',MI18n.text(reason)));
    if(room.files?.length){const files=el('details');files.append(el('summary',t('cleanupFiles',{count:room.files.length})));const list=el('ul');for(const file of room.files){const item=el('li');item.append(el('div',t('cleanupScope'+file.scope)),content('div',file.path),el('div',t('fileBytes',{size:file.size})));list.append(item);}files.append(list);row.append(files);}return row;}));cleanupControls();
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
  if(owner&&!projects.some(item=>item.projectId===owner))owners.push(contentOption(owner,owner+' ('+ot('ownerUnavailable')+')'));
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
const diagramParts={};
for(const [side,host]of [['owned','ownedRoomPreview'],['target','targetRoomPreview']]){
  const preview=el('button');preview.type='button';preview.className='connection-room-preview';
  const image=el('img');image.alt='';image.hidden=true;const name=content('span','');preview.append(image,name);
  preview.onclick=()=>openConnectionPicker(side);diagramParts[side]={preview,image,name,room:''};$(host).append(preview);
}
$('catalogMapPicker').onclick=()=>openConnectionPicker('target',true);
let diagramPreviewKey='',diagramPreviewToken=0;
function canUseEntry(room){return !!workflow&&allowedTarget(room)&&!busy&&!!description?.editable&&!!room.verified&&(room.owned||MIRoomChoices.live(catalog))&&Array.from({length:room.exitCount||0},(_,node)=>node).some(node=>nodeAvailable(room,node));}
function chooseEntryRoom(room){
  if(!canUseEntry(room))throw Error(t(!room?.owned&&!MIRoomChoices.live(catalog)?'needsLive':'unverifiedRoom'));
  connectionSelection.targetRoom=room.name;connectionSelection.targetNode=null;setConnectionError();renderConnections();renderRooms();return true;
}
function openConnectionPicker(side,choose=false){
  if(!project||!workflow||!window.MIRoomPicker)return;
  const selected=connectionSelection[side==='owned'?'ownedRoom':'targetRoom'],name=selected||ownRooms()[0]?.name||description.binding.ai;
  const actual=sourceRoom(name),region=actual.split('_')[0];
  return MIRoomPicker.open({room:actual,region,projectId:project.projectId,readOnly:!choose||!description?.editable,
    selectable:room=>canUseEntry(pickerRoom(room.name)),unavailableText:t(!MIRoomChoices.live(catalog)?'needsLive':'unverifiedRoom'),
    onSelect:room=>chooseEntryRoom(pickerRoom(room.room))});
}
function renderConnectionDiagram(){
  if(!project)return;
  for(const side of ['owned','target']){const part=diagramParts[side],name=connectionSelection[side+'Room'];part.room=name;part.preview.hidden=!name;part.name.textContent=name;part.preview.disabled=busy||!name;part.preview.setAttribute('aria-label',MI18n.text('房间预览')+' '+name);}
  const names=[connectionSelection.ownedRoom,connectionSelection.targetRoom],key=[project.projectId,...names].join('\n');if(key===diagramPreviewKey)return;diagramPreviewKey=key;const token=++diagramPreviewToken;
  ['owned','target'].forEach((side,index)=>{const part=diagramParts[side];part.image.hidden=true;part.image.removeAttribute('src');if(!names[index])return;api('room-picker-preview?room='+encodeURIComponent(sourceRoom(names[index]))+'&projectId='+encodeURIComponent(project.projectId)).then(value=>{if(token!==diagramPreviewToken)return;if(value.image){part.image.src=value.image;part.image.hidden=false;}}).catch(()=>{});});
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
    const card=el('article');card.className='room-card';card.classList.toggle('selected',room.name===connectionSelection.targetRoom);
    const header=el('div');header.className='room-card-header';header.append(content('strong',room.name));
    const owned=MIRoomChoices.owned(catalog,room,description?.binding),choose=el('button',t('useRoom'));choose.type='button';choose.disabled=!canUseEntry(selectedRoom(room.name));
    choose.onclick=run(()=>chooseEntryRoom(selectedRoom(room.name)));const preview=el('button',MI18n.text('房间预览'));preview.type='button';preview.onclick=()=>MIRoomPicker.open({room:room.name,region:room.region,projectId:project?.projectId||'',readOnly:true});header.append(preview,choose);card.append(header);
    const meta=el('div');meta.className='room-meta';meta.append(content('span',room.region),el('span',Number.isInteger(room.exitCount)&&room.exitCount>=0?t('exits',{count:room.exitCount}):t('unknownExits')));if(owned)meta.append(el('span',t('projectOwnedRoom')));else if(room.oracle)meta.append(el('span',t('oracleRoom')));if(room.conditional)meta.append(el('span',t('conditional')));if(!room.verified)meta.append(el('span',t('unverified')));card.append(meta);
    const links=el('div');links.className='room-links';(room.connections||[]).forEach((target,node)=>links.append(content('p',connectionText(room,node))));card.append(links);return card;
  }));$('showMore').hidden=all.length<=limit;
}
function adoptWorkflow(result,{preserveNames=false}={}){
  workflow=result;description.binding=structuredClone(result.binding);selectedConnections=[];requiredConnectionId='';resetConnectionSelection();
  if(!preserveNames)binding={...structuredClone(result.binding),...result.pending?.names};
  dirty=!!result.pending;roomDraftDirty=false;renderBinding();invalidate();
}
function clearProjectState(){
  project=null;binding=null;description=null;workflow=null;overseerDocument=null;overseerConfig=null;overseerAll=null;overseerProfileId='default';overseerDirty=false;roomDraftReady=false;roomDraftRevision=0;roomDraftDirty=false;dirty=false;roomLoadErrors={};connectionActionError='';bindingCheck=null;selectedConnections=[];requiredConnectionId='';resetConnectionSelection();exitRepairActions.replaceChildren();exitRepairActions.hidden=true;
  for(const id of ['region','ai','entry','oracleId']){$(id).value='';$(id).setCustomValidity('');$(id).removeAttribute('aria-invalid');}
  for(const id of ['regionError','aiError','entryError'])$(id).textContent='';
  for(const id of ['nameStatus','nameError','connectionStatus','connectionError','overseerNotice','saveState'])$(id).textContent='';
  for(const id of ['ownRoomChoices','currentConnectionList','priorConnectionList','targetRoom','ownedNode','targetNode','requiredConnection','bindingWarnings','overseerProfiles','overseerSelectedRooms'])$(id).replaceChildren();
  $('overseerForm').reset();$('overseerCanvas').getContext('2d').clearRect(0,0,$('overseerCanvas').width,$('overseerCanvas').height);
  for(const part of Object.values(diagramParts)){part.room='';part.preview.hidden=true;part.image.hidden=true;part.image.removeAttribute('src');}
  diagramPreviewKey='';diagramPreviewToken++;$('cancelRoomNames').hidden=true;$('pendingConnectionNote').hidden=true;$('priorConnections').hidden=true;
  renderBindingCheck();renderPairs();resetCleanup();overseerControls();overseerStatus();window.MIUndo?.reset();
}
async function loadProject(id){
  if(busy)return;if(project&&(roomDraftDirty||overseerDirty)){try{await saveRoomDrafts();}catch(error){$('projects').value=project.projectId;throw error;}}
  const selected=projects.find(item=>item.projectId===id);clearProjectState();
  if(!selected){setBusy(false);$('saveState').textContent=t('noProject');notice();return;}
  project=selected;$('projects').value=id;setBusy(true);notice();
  try{const keys=['binding','overseer','draft','workflow'],responses=await Promise.allSettled(['room-binding','overseer','room-draft','room-workflow'].map(route=>api(route+'?projectId='+encodeURIComponent(id)))),loaded={};
    responses.forEach((response,index)=>{if(response.status==='fulfilled')loaded[keys[index]]=response.value;else roomLoadErrors[keys[index]]=response.reason?.message||String(response.reason);});
    const {binding:result,overseer,draft,workflow:state}=loaded;
    description=result||(state?{binding:state.binding,editable:state.editable===true,warnings:[]}:null);roomDraftReady=!!draft;if(draft)roomDraftRevision=draft.revision;
    if(state&&description)adoptWorkflow(state);else if(description)binding=structuredClone(description.binding);
    if(binding&&!state?.pending&&draft?.binding){binding={...binding,...Object.fromEntries(['region','ai','entry'].map(key=>[key,draft.binding[key]]))};dirty=['region','ai','entry'].some(key=>binding[key]!==description.binding[key]);}
    roomDraftDirty=false;$('catalogRegion').value='@project';$('roomSearch').value='';limit=80;invalidate();renderBinding();renderCatalog();
    if(overseer)adoptOverseer(overseer);else overseerNotice(roomLoadErrors.overseer||'',true);
    $('nameStatus').textContent=state?.pending?t('pendingReconnect'):'';$('nameError').textContent=[roomLoadErrors.binding,roomLoadErrors.draft].filter(Boolean).join('\n');renderWorkflowIssues();window.MIUndo?.reset();
  }finally{setBusy(false);renderRooms();if(project&&$('cleanupDetails').open&&!cleanupDocument)loadCleanup();}
}
for(const key of ['region','ai','entry'])$(key).oninput=()=>{if(!binding)return;binding[key]=$(key).value;changed();};
$('targetRoom').onchange=()=>{connectionSelection.targetRoom=$('targetRoom').value;connectionSelection.targetNode=null;setConnectionError();renderNodes();renderRooms();};
for(const key of ['ownedNode','targetNode'])$(key).onchange=()=>{connectionSelection[key]=$(key).value===''?null:Number($(key).value);setConnectionError();};
$('requiredConnection').onchange=()=>{requiredConnectionId=$('requiredConnection').value;resetConnectionSelection();setConnectionError();renderConnections();};
$('projects').onchange=run(()=>loadProject($('projects').value));
$('roomSearch').oninput=$('catalogRegion').onchange=()=>{limit=80;renderRooms();};$('showMore').onclick=()=>{limit+=80;renderRooms();};
$('projectRegion').onclick=()=>{$('catalogRegion').value='@project';$('roomSearch').value='';limit=80;renderRooms();};
$('bindingRecord').onchange=renderPairs;
async function refreshCatalog(manual=false){
  if(busy||catalogRefreshing)return;catalogRefreshing=true;if(manual)$('refreshCatalog').disabled=true;
  try{catalog=await api('rooms');renderCatalog();if(manual&&project&&Object.keys(roomLoadErrors).length)await loadProject(project.projectId);
  }catch(error){renderCatalog();if(manual)notice(error.message,true);}finally{catalogRefreshing=false;$('refreshCatalog').disabled=busy;}
}
function scheduleCatalog(){clearTimeout(catalogTimer);catalogTimer=setTimeout(async()=>{if(!document.hidden)await refreshCatalog();scheduleCatalog();},10000);}
$('refreshCatalog').onclick=()=>refreshCatalog(true);
function renderBindingCheck(){
  $('bindingCheck').hidden=!bindingCheck;if(!bindingCheck)return;
  $('bindingCheckState').textContent=t(bindingCheck.applied?'checkApplied':'pending');$('bindingCheckPair').textContent=pairText(bindingCheck.binding);
  $('bindingCheckChanges').replaceChildren(...(bindingCheck.connectionChanges||[]).map(change=>{const row=el('tr');row.append(content('td',change.room),content('td',t('shaftIndex',{node:change.node,ordinal:change.node+1})),content('td',change.fromRoom==='DISCONNECTED'?t('disconnected'):change.fromRoom||t('unknownConnection')),content('td',change.to==='DISCONNECTED'?t('disconnected'):change.to));return row;}));
  $('bindingCheckFiles').replaceChildren(...Object.entries(bindingCheck.worldFiles||{}).flatMap(([path,text])=>[content('p',path),content('pre',text)]));
}
async function alignRoomDraft(result){
  if(!roomDraftReady){try{const draft=await api('room-draft?projectId='+encodeURIComponent(project.projectId));roomDraftRevision=draft.revision;roomDraftReady=true;delete roomLoadErrors.draft;}catch(error){roomLoadErrors.draft=error.message;$('nameError').textContent=error.message;}return;}
  if(Number.isInteger(result.draftRevision)){if(!result.draftPreserved)roomDraftRevision=result.draftRevision;else notice(t('appliedDraftPending',{error:MI18n.t('studio.roomDraft.error8')}),true);}
  else {try{const draft=await api('room-draft',{projectId:project.projectId,binding:structuredClone(binding),revision:roomDraftRevision});roomDraftRevision=draft.revision;}catch(error){notice(t('appliedDraftPending',{error:error.message}),true);}}
}
$('bindingForm').onsubmit=async event=>{
  event.preventDefault();if(busy||!description?.editable||!workflow||!roomDraftReady||workflow.pending)return;renderIdentity();if(!$('bindingForm').reportValidity())return;setBusy(true);$('nameError').textContent='';notice();
  try{const result=await api('room-workflow/names',{projectId:project.projectId,revision:workflow.revision,names:Object.fromEntries(['region','ai','entry'].map(key=>[key,binding[key]]))});
    adoptWorkflow(result);$('nameStatus').textContent=t(result.pending?'pendingReconnect':'namesUnchanged');$('connectionStatus').textContent='';await alignRoomDraft(result);window.MIUndo?.rebase();
  }catch(error){$('nameError').textContent=error.message;invalidate();}finally{setBusy(false);}
};
$('cancelRoomNames').onclick=async()=>{
  if(busy||!workflow?.pending)return;setBusy(true);$('nameError').textContent='';
  try{const result=await api('room-workflow/cancel',{projectId:project.projectId,revision:workflow.revision});adoptWorkflow(result);$('nameStatus').textContent='';$('connectionStatus').textContent='';await alignRoomDraft(result);window.MIUndo?.rebase();}
  catch(error){$('nameError').textContent=error.message;}finally{setBusy(false);}
};
$('connectionForm').onsubmit=async event=>{
  event.preventDefault();if(busy||!description?.editable||!workflow)return;setConnectionError();
  const value=connectionSelection;if(!value.ownedRoom){setConnectionError(t('chooseOwnRoom'));$('ownRoomChoices').querySelector('button')?.focus();return;}
  if(!value.targetRoom||value.ownedNode===null||value.targetNode===null){setConnectionError(t('chooseBothExits'));return;}
  const required=workflow.pending?.required||[],link={from:{room:value.ownedRoom,node:value.ownedNode},to:{room:value.targetRoom,node:value.targetNode},...(required.length?{replaces:requiredConnectionId||required[0].id}:{})};
  const choices=selectedConnections.filter(item=>item.replaces!==link.replaces);choices.push(link);
  const remaining=required.filter(item=>!choices.some(choice=>choice.replaces===item.id));
  if(remaining.length){selectedConnections=choices;requiredConnectionId=remaining[0].id;resetConnectionSelection();$('connectionStatus').textContent=t('moreConnections',{count:remaining.length});renderConnections();return;}
  setBusy(true);notice();
  try{const result=await api('room-workflow/apply',{projectId:project.projectId,revision:workflow.revision,connections:choices,...(roomDraftReady?{draftRevision:roomDraftRevision}:{})});adoptWorkflow(result);$('saveState').textContent=t('restart');$('nameStatus').textContent='';$('connectionStatus').textContent=t('connectionApplied');resetCleanup();await alignRoomDraft(result);renderOverseerRooms();window.MIUndo?.rebase();}
  catch(error){setConnectionError(error.message);}finally{setBusy(false);}
};
function revealInvalid(event){for(let node=event.target.parentElement;node;node=node.parentElement)if(node.tagName==='DETAILS')node.open=true;}
$('bindingForm').addEventListener('invalid',revealInvalid,true);$('connectionForm').addEventListener('invalid',revealInvalid,true);
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
window.MIUndo?.register({key:()=>project?.projectId,capture:()=>({binding,overseer:overseerAll}),busy:()=>busy||cleanupBusy||!binding||!!workflow?.pending,
 restore:value=>{const roomChanged=JSON.stringify(binding)!==JSON.stringify(value.binding),monitorChanged=JSON.stringify(overseerAll)!==JSON.stringify(value.overseer);binding=structuredClone(value.binding);overseerAll=structuredClone(value.overseer);if(roomChanged)dirty=roomDraftDirty=true;if(monitorChanged)overseerDirty=true;invalidate();renderBinding();renderRooms();selectOverseerProfile(overseerProfileId);overseerStatus();notice();},onError:error=>notice(error.message,true)});
window.addEventListener('beforeunload',event=>{if(roomDraftDirty||overseerDirty){event.preventDefault();event.returnValue='';}});
document.addEventListener('visibilitychange',()=>{if(!document.hidden)refreshCatalog();});
window.addEventListener('mi-language-change',()=>{if(catalog)renderCatalog();if(binding)renderBinding();renderBindingCheck();appliedNotice();if(cleanupDocument)renderCleanup();if(overseerConfig){renderOverseerProfiles();renderOverseerRooms();for(const key of overseerProbabilities){$('overseerChance'+key).title=ot('chanceHint');$('overseerChance'+key).setAttribute('aria-label',ot(key));$('overseerLabel'+key).textContent=ot(key);}$('overseerProbabilities').title=ot('chanceHint');overseerStatus();}});
run(async()=>{setBusy(true);try{
 const [saved,rooms]=await Promise.allSettled([api('projects'),api('rooms')]);if(saved.status==='rejected')throw saved.reason;projects=saved.value;
 const catalogError=rooms.status==='rejected'?rooms.reason?.message||String(rooms.reason):'';catalog=rooms.status==='fulfilled'?rooms.value:{regions:[],source:'offline',fresh:false,complete:false,warnings:[catalogError]};
 if(!projects.length){const created=await api('save',await api('default'));projects=[created.project];}$('projects').replaceChildren(option('',t('chooseProject')),...projects.map(item=>contentOption(item.projectId,item.name)));renderCatalog();const params=new URLSearchParams(location.search),id=params.get('project')||params.get('projectId')||params.get('id')||projects[0]?.projectId;busy=false;await loadProject(id);if(catalogError)notice(catalogError,true);
}finally{setBusy(false);scheduleCatalog();}})();
}
