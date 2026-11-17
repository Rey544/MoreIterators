'use strict';
(()=>{
 const byId=id=>document.getElementById(id),dialog=byId('exportDialog');
 let externalMods=new Set(),externalRows=[],loadingExternal=false,loadingExternalCheck=false,externalError=false,externalErrorText='',externalSequence=0;
 let cover='',building=false,loadingRooms=false,loadingRegion=false,roomsError='',regionError='',roomSequence=0,regionSequence=0,roomRows=[],extras=new Set(),regionData=null,reviewed='';
 let draft=null,draftTimer=null,saveQueue=Promise.resolve(),loadingPreferences=false;
 const sessionDrafts=new Map();
 let startRoom=null,selectedRegion=null,seedExtraDefaults=false,savedScene=null,sceneEdited=false,lastFormat='';
 let roomCheck=null,roomCheckSignature='',roomSourceChoices={},roomAssetChoices={},roomCheckSequence=0,loadingRoomCheck=false,roomCheckError='',syncingRoom='';
 let syncQueue=Promise.resolve(),importingFiles=false;
 const syncAttempts=new Set(),syncErrors=new Map(),importErrors=new Map();
 const roomReview=document.createElement('section');roomReview.id='export-roomVersions';roomReview.className='export-section export-room-versions';roomReview.hidden=true;byId('export-roomReviewAnchor').before(roomReview);
 const ids=()=>[...byId('pack-projects').querySelectorAll('input:checked')].map(c=>c.value);
 const selectedParts=()=>[...dialog.querySelectorAll('[name=part]:checked')].map(c=>c.value);
 const parts=()=>format()==='json'?[]:format()==='assets'?selectedParts():['appearance','textures','room','dialogue'];
 const scope=()=>dialog.querySelector('[name=exportScope]:checked').value;
 const format=()=>dialog.querySelector('[name=exportFormat]:checked')?.value;
 const associated=()=>format()!=='assets'&&['pearls','workPearls','broadcasts','projections'].some(k=>byId('pack-'+k).checked);
 const text=s=>MI18n.text(s);
 function changed(){if(!dialog.open||loadingPreferences||!draft)return;draft.revision++;clearTimeout(draftTimer);draftTimer=setTimeout(()=>persistDraft().catch(error=>{byId('pack-status').textContent=error.message;}),400);}
 async function persistDraft(){
  clearTimeout(draftTimer);const token=draft;if(!token||token.saved===token.revision)return;
  const revision=token.revision,data=preferenceData(token);
  const job=saveQueue.catch(()=>{}).then(()=>api('export-settings',data));saveQueue=job;
  await job;token.saved=Math.max(token.saved,revision);if(sessionDrafts.get(token.pid)?.token===token&&token.saved>=token.revision)sessionDrafts.delete(token.pid);
 }
 function preferenceData(token=draft){return {...request(),settingsProject:token?.pid||project.projectId,projects:ids(),extraRooms:[...extras],externalMods:[...externalMods],parts:selectedParts(),...Object.fromEntries(['dialogue','pearls','broadcasts','workPearls','projections'].map(key=>[key,byId('pack-'+key).checked])),format:format(),pearlCollectionId:byId('pack-pearlCollection').value};}
 async function closeDialog(){const token=draft;if(token&&token.saved!==token.revision)sessionDrafts.set(token.pid,{token,settings:structuredClone(preferenceData(token))});dialog.close();try{await persistDraft();}catch(error){if(typeof notice==='function')notice(MI18n.t('export.preferencesNotSaved'),true);}}
 const sceneEditor=window.MIExportScene,sceneReady=MI18n.ready.then(()=>sceneEditor?.mount(byId('pack-sceneEditor'),{onChange:()=>{if(!loadingPreferences)sceneEdited=true;invalidateExport();changed();},onCoverChange:value=>{cover=value;byId('pack-coverPreview').src=cover;byId('pack-coverPreview').hidden=!cover;invalidateExport();changed();}}));
 function selectValue(select,value){if(value&&!Array.from(select.options).some(option=>option.value===value)){const option=MI18n.content(document.createElement('option'));option.value=value;option.textContent=value;option.disabled=true;option.title=text('缺少文件');select.append(option);}select.value=value||'';}
 const validSelection=select=>!!select.value&&!select.selectedOptions[0]?.disabled;
 function focusExportTarget(target){if(!target)return;for(let parent=target.parentElement;parent&&parent!==dialog;parent=parent.parentElement)if(parent.tagName==='DETAILS')parent.open=true;if(!target.matches('input,select,textarea,button,a'))target.tabIndex=-1;target.scrollIntoView({block:'center',behavior:'smooth'});target.focus();}
 function validationIssue(ignoreRoomChoices=false){
  const region=scope()==='region',selected=region&&Array.isArray(regionData?.projectIds)?regionData.projectIds:ids(),chosen=parts(),current=format(),runtime=['mod','playable'].includes(current),issue=(message,target,retry)=>({message,target,retry}),formatTarget=dialog.querySelector('[name=exportFormat]:checked')||dialog.querySelector('[name=exportFormat]');
  const missing=selected.find(id=>!projects.some(value=>value.projectId===id));if(missing)return issue(MI18n.t('export.validation.missingProject',{name:missing}),[...byId('pack-projects').querySelectorAll('input')].find(input=>input.value===missing));
  if(!current)return issue(MI18n.t('export.format.selectFormat'),formatTarget);
  if(region&&!['region','playable'].includes(current))return issue(MI18n.t('export.format.regionScope'),formatTarget);
  if(!region&&current==='region')return issue(MI18n.t('export.format.projectScope'),dialog.querySelector('[name=exportScope][value=region]'));
  if(!region&&!selected.length&&!(current==='project'&&externalMods.size))return issue(MI18n.t('export.format.selectProjects'),byId('pack-projects').querySelector('input')||byId('pack-projects'));
  if(selected.length>100)return issue(MI18n.t('export.selection.tooManyProjects'),byId('pack-projects'));
  if(current==='json')return selected.length===1?null:issue(MI18n.t('export.format.oneProject'),byId('pack-projects').querySelector('input')||byId('pack-projects'));
  if(current==='assets'&&selected.length!==1)return issue(MI18n.t('export.format.oneProject'),byId('pack-projects').querySelector('input:checked')||byId('pack-projects'));
  if(current==='assets'&&associated())return issue(MI18n.t('export.format.associated'),byId('export-associated').querySelector('input:checked'));
  const required=!region&&(current==='project'?['appearance','textures','room','dialogue']:runtime?['appearance','textures','room']:[])||[],absent=required.filter(value=>!chosen.includes(value));
  if(absent.length){const inputs=absent.map(value=>dialog.querySelector('[name=part][value='+value+']'));return issue(MI18n.t('export.validation.parts',{parts:inputs.map(input=>input.parentElement.textContent.trim()).join(MI18n.locale==='zh-CN'?'、':', ')}),inputs[0]);}
  if(scope()==='project'&&externalMods.size&&current!=='project')return issue(MI18n.t('export.selection.externalFormat'),dialog.querySelector('[name=exportFormat][value=project]'));
  if(scope()==='project'&&externalMods.size&&(externalError||[...externalMods].some(id=>!externalRows.some(row=>row.id===id&&row.available!==false))))return issue(externalErrorText||MI18n.t('export.selection.externalMissing'),byId('export-externalProjects').querySelector('summary'));
  if(current==='project'&&!selected.length&&extras.size)return issue(MI18n.t('export.selection.extraProjectRequired'),byId('export-extraRooms').querySelector('summary'));
  if(current==='assets'&&!chosen.length)return issue(MI18n.t('export.format.selectParts'),dialog.querySelector('[name=part]'));
  if(current==='assets'&&chosen.includes('room')&&extras.size)return issue(MI18n.t('export.format.extraRooms'),byId('export-extraRooms').querySelector('summary'));
  if(current==='project'){
   if(!byId('pack-projectName').value.trim())return issue(MI18n.t('export.package.nameRequired'),byId('pack-projectName'));
   if(/[\u0000-\u001f\u007f\\/:*?"<>|]/.test(byId('pack-projectName').value)||/[. ]$/.test(byId('pack-projectName').value)||/^(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)/i.test(byId('pack-projectName').value))return issue(MI18n.t('export.package.nameInvalid'),byId('pack-projectName'));
   if(Array.from(byId('pack-projectName').value).length>100)return issue(MI18n.t('export.validation.metadataLength',{limit:100}),byId('pack-projectName'));
   if(byId('pack-projectVersion').value.length>32||!/^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/.test(byId('pack-projectVersion').value.trim()))return issue(MI18n.t('export.package.versionRequired'),byId('pack-projectVersion'));
  }
  if(runtime){
   for(const [key,limit]of [['id',64],['name',100],['authors',200],['description',4000],['version',32]])if(Array.from(byId('pack-'+key).value).length>limit)return issue(MI18n.t('export.validation.metadataLength',{limit}),byId('pack-'+key));
   const id=byId('pack-id').value.trim(),version=byId('pack-version').value.trim();
   if(!/^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)+$/.test(id))return issue(MI18n.t('export.validation.modId'),byId('pack-id'));
   if(id.startsWith('moreiterators')||id.startsWith('eoe.'))return issue(MI18n.t('export.validation.modReserved'),byId('pack-id'));
   if(!byId('pack-name').value.trim())return issue(MI18n.t('export.validation.modName'),byId('pack-name'));
   if(!byId('pack-authors').value.trim())return issue(MI18n.t('export.validation.modAuthors'),byId('pack-authors'));
   if(!/^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/.test(version))return issue(MI18n.t('export.validation.modVersion'),byId('pack-version'));
  }
  if(current!=='assets'&&(!region||current==='playable'&&selected.length)&&byId('pack-pearls').checked&&!validSelection(byId('pack-pearlCollection')))return issue(MI18n.t('export.validation.pearl'),byId('pack-pearlCollection'));
  if(!region&&chosen.includes('room')&&roomsError)return issue(roomsError,byId('pack-build'),'rooms');
  if(region){
   if(regionError)return issue(regionError,byId('pack-build'),'region');
   if(!validSelection(byId('export-region')))return issue(MI18n.t('export.validation.region'),byId('export-region'));
   if(!regionData)return issue(MI18n.t('export.validation.regionFailed'),byId('pack-build'),'region');
   if(regionData.blockers?.length)return issue(regionData.blockers[0],byId('export-regionSummary'));
   if(!regionData.ok)return issue(MI18n.t('export.validation.regionFailed'),byId('pack-build'),'region');
  }
  if(current==='playable'&&!validSelection(byId('export-startRoom')))return issue(MI18n.t('playable.badStart'),byId('export-startRoom'));
  if(!ignoreRoomChoices&&roomCheckError)return issue(roomCheckError,byId('pack-build'),'roomCheck');
  if(!ignoreRoomChoices&&roomCheck){
   const missingFile=missingFiles()[0];if(missingFile)return issue(MI18n.t('export.roomState.missingFile',{file:missingFile.name}),[...dialog.querySelectorAll('[data-missing-file]')].find(node=>node.dataset.missingFile===missingKey(missingFile))||roomReview);
   const pending=roomCheck.rooms?.find(room=>room.state==='needs_sync');if(pending)return issue(syncError(pending)||MI18n.t('export.roomState.syncFirst',{room:pending.room}),[...dialog.querySelectorAll('[data-room-key]')].find(node=>node.dataset.roomKey===versionKey(pending))||byId('export-matchedRooms'));
   const missing=roomCheck.issues?.[0];if(missing)return issue(MI18n.t('export.validation.roomMissing',{room:missing.room,kind:MI18n.t('export.roomVersion.'+(missing.kind==='source'?'render':'settings'))}),[...dialog.querySelectorAll('[data-room-key]')].find(node=>node.dataset.roomKey===versionKey(missing))||roomReview);
   for(const room of roomCheck.rooms||[])for(const [kind,versions]of [['source',room.renderVersions],['settings',room.settingsVersions]])if(!versions.some(version=>version.complete&&version.id===roomSourceChoices[versionKey(room)]?.[kind]))return issue(MI18n.t('export.validation.roomChoice',{room:room.room,kind:MI18n.t('export.roomVersion.'+(kind==='source'?'render':'settings'))}),[...dialog.querySelectorAll('[data-room-key] input:not(:disabled)')].find(input=>input.dataset.room===versionKey(room)&&input.dataset.kind===kind)||roomReview);
   for(const asset of roomCheck.assets||[])if(asset.versions.some(version=>version.complete)&&!asset.versions.some(version=>version.complete&&version.id===roomAssetChoices[asset.key]))return issue(MI18n.t('export.validation.assetChoice',{name:/^(?:[A-Za-z]:|[\\/])/.test(asset.relative)?MI18n.t('export.roomVersion.asset'):asset.relative}),[...roomReview.querySelectorAll('input:not(:disabled)')].find(input=>input.dataset.asset===asset.key)||roomReview);
  }
  return null;
 }
 function showValidation(issue,focus=false){const status=byId('pack-status');for(const field of dialog.querySelectorAll('[aria-invalid=true]'))field.removeAttribute('aria-invalid');if(issue){status.textContent=issue.message;status.dataset.validation='true';if(issue.target?.matches('input,select,textarea'))issue.target.setAttribute('aria-invalid','true');if(focus)focusExportTarget(issue.target);}else if(status.dataset.validation){status.textContent='';delete status.dataset.validation;}}
 function label(value,node){const l=document.createElement('label'),span=MI18n.content(document.createElement('span'));span.textContent=value;l.append(node,span);return l;}
 function note(value){byId('export-formatNote').textContent=text(value);byId('export-formatNote').hidden=!value;}
 function invalidate(){reviewed='';roomCheckSequence++;loadingRoomCheck=false;roomCheckError='';roomCheck=null;roomCheckSignature='';roomReview.hidden=true;byId('export-review').hidden=true;byId('pack-status').textContent='';review();}
 function invalidateExport(){reviewed='';byId('export-review').hidden=true;byId('pack-status').textContent='';review();}
 function versionKey(room){return room.projectId+'/'+room.room;}
 function syncToken(room){return versionKey(room)+'/'+(room.sourceToken||JSON.stringify({state:room.state,reason:room.reason,render:room.renderVersions?.map(value=>[value.id,value.modifiedAt])}));}
 function syncError(room){return syncErrors.get(syncToken(room))||'';}
 function missingKey(file){return file.id||JSON.stringify([file.projectId,file.room,file.relative]);}
 function missingFiles(){const values=[...(roomCheck?.missingFiles||[]),...(roomCheck?.rooms||[]).flatMap(room=>room.missingFiles||[])],seen=new Set();return values.filter(file=>{const key=missingKey(file);if(seen.has(key))return false;seen.add(key);return true;}).map(file=>({...file,name:file.name||file.relative?.split('/').pop()||''}));}
 function roomMissingFiles(room){return missingFiles().filter(file=>file.projectId===room.projectId&&file.room===room.room);}
 function versionChoicesReady(){return !roomCheck||!(roomCheck.issues||[]).length&&(roomCheck.rooms||[]).every(room=>['source','settings'].every(kind=>(kind==='source'?room.renderVersions:room.settingsVersions).some(version=>version.complete&&version.id===roomSourceChoices[versionKey(room)]?.[kind])))&&(roomCheck.assets||[]).every(asset=>!asset.versions.some(version=>version.complete)||asset.versions.some(version=>version.complete&&version.id===roomAssetChoices[asset.key]));}
 function roomChoicesReady(){return versionChoicesReady();}
 function roomChoicePayload(){return roomCheck?.rooms?.length||roomCheck?.assets?.length?{snapshotToken:roomCheck.snapshotToken,choices:structuredClone(roomSourceChoices),assetChoices:{...roomAssetChoices},extraRooms:request().extraRooms}:undefined;}
 function hasUnpairedRoomSource(){return format()==='project'&&(roomCheck?.rooms||[]).some(room=>room.state!=='needs_sync'&&room.renderVersions.some(version=>version.id===roomSourceChoices[versionKey(room)]?.source&&!version.pairedSource));}
 function versionOrigin(version,origin=version.origin){if(version.builtin)return MI18n.t('export.selection.builtin');const names={project:'export.roomVersion.project',local:'export.roomVersion.local',installed:'export.roomVersion.installed',enabled:'export.roomVersion.enabled',palette_output:'export.roomVersion.savedPalette',rained:'export.roomVersion.rained',game:'export.roomVersion.game',source:'export.roomVersion.source'};return MI18n.t(names[origin]||'export.roomVersion.other');}
 function versionLabel(version){const name=version.providers?.[0]?.name||version.providers?.[0]?.id||(ids().length>1?(version.projectIds||[]).map(id=>projects.find(project=>project.projectId===id)?.name||id).join(', '):'');return name?MI18n.t('export.roomVersion.provider',{origin:versionOrigin(version),name}):versionOrigin(version);}
 function versionOrigins(version){return [...new Set(version.origins||[])].map(origin=>versionOrigin(version,origin)).concat((version.providers||[]).map(provider=>provider.name||provider.id)).join('\n');}
 function changeRoomChoice(){reviewed='';byId('export-review').hidden=true;byId('pack-status').textContent='';drawRooms();updateRoomVersionNotice();review();}
 function focusRoomChoice(){const radio=[...dialog.querySelectorAll('[data-room-key] input[type=radio]:not(:disabled),#export-roomVersions input[type=radio]:not(:disabled)')].find(input=>![...dialog.querySelectorAll('input[type=radio]')].some(other=>other.name===input.name&&other.checked));if(radio)focusExportTarget(radio);}
 function versionDate(value){const date=new Date(typeof value==='number'&&value<1e12?value*1000:value);return value&&!Number.isNaN(date.valueOf())?date.toLocaleString(MI18n.locale):MI18n.t('export.roomVersion.undated');}
 function roomVersionFields(room){
  const container=document.createElement('div');container.className='export-room-version';container.dataset.roomKey=versionKey(room);
  for(const [kind,key,versions]of [['source','export.roomVersion.render',room.renderVersions||[]],['settings','export.roomVersion.settings',room.settingsVersions||[]]]){
   if(!(versions||[]).some(version=>version.complete)&&roomMissingFiles(room).length)continue;
   if(versions.length===1&&versions[0].complete)continue;
   const group=document.createElement('fieldset'),legend=document.createElement('legend');legend.textContent=MI18n.t(key);group.append(legend);
   if(!versions.length){const missing=document.createElement('p');missing.className='muted';missing.textContent=MI18n.t('export.validation.roomMissing',{room:room.room,kind:MI18n.t(key)});group.append(missing);}
   const unavailable=document.createElement('details'),unavailableTitle=document.createElement('summary');unavailableTitle.textContent=MI18n.t('export.selection.unavailableVersions');unavailable.append(unavailableTitle);
   for(const version of versions){
    const input=document.createElement('input'),line=document.createElement('label'),body=document.createElement('span'),origin=document.createElement('span'),date=document.createElement('span');input.type='radio';input.name='room-version-'+versionKey(room)+'-'+kind;input.value=version.id;input.dataset.room=versionKey(room);input.dataset.kind=kind;input.checked=roomSourceChoices[versionKey(room)]?.[kind]===version.id;input.disabled=!version.complete;origin.textContent=versionLabel(version);origin.title=versionOrigins(version);date.className='muted';date.textContent=versionDate(version.modifiedAt);body.append(origin,date);
    if(!version.complete){const issue=document.createElement('span');issue.className='muted';issue.textContent=MI18n.t('export.roomVersion.incomplete');body.append(issue);}
    input.onchange=()=>{roomSourceChoices[versionKey(room)]??={};roomSourceChoices[versionKey(room)][kind]=version.id;changeRoomChoice();};line.append(input,body);(version.complete?group:unavailable).append(line);
   }
   if(unavailable.children.length>1)group.append(unavailable);container.append(group);
  }
  return container;
 }
 function drawRoomVersions(){
  drawRooms();roomReview.replaceChildren();
  const assets=(roomCheck?.assets||[]).filter(asset=>asset.versions.length>1||asset.versions.some(version=>!version.complete));
  const remaining=missingFiles().filter(file=>scope()==='region'||!document.querySelector('[data-missing-file="'+CSS.escape(missingKey(file))+'"]'));
  const regionalRepairs=scope()==='region'?(roomCheck?.rooms||[]).filter(room=>syncError(room)):[];
  roomReview.hidden=format()==='json'||!assets.length&&!hasUnpairedRoomSource()&&!remaining.length&&!regionalRepairs.length;if(roomReview.hidden)return;
  appendMissingFiles(roomReview,remaining,true);
  for(const room of regionalRepairs){const host=document.createElement('div'),name=MI18n.content(document.createElement('p'));host.dataset.roomKey=versionKey(room);name.textContent=room.room;host.append(name);appendSyncState(host,room);roomReview.append(host);}
  for(const asset of assets){
   const group=document.createElement('details'),legend=MI18n.content(document.createElement('summary'));group.className='export-room-asset';legend.textContent=/^(?:[A-Za-z]:|[\\/])/.test(asset.relative)?MI18n.t('export.roomVersion.asset'):asset.relative;group.append(legend);
   group.open=!asset.versions.some(version=>version.complete&&version.id===roomAssetChoices[asset.key]);
   for(const version of asset.versions){
    const input=document.createElement('input'),line=document.createElement('label'),body=document.createElement('span'),origin=document.createElement('span'),date=document.createElement('span');input.type='radio';input.name='room-asset-'+asset.key;input.value=version.id;input.dataset.asset=asset.key;input.checked=roomAssetChoices[asset.key]===version.id;input.disabled=!version.complete;origin.textContent=versionLabel(version);origin.title=versionOrigins(version);date.className='muted';date.textContent=versionDate(version.modifiedAt);body.append(origin,date);
    if(!version.complete){const issue=document.createElement('span');issue.className='muted';issue.textContent=MI18n.t('export.roomVersion.incomplete');body.append(issue);}
    input.onchange=()=>{roomAssetChoices[asset.key]=version.id;changeRoomChoice();};line.append(input,body);group.append(line);
   }
   roomReview.append(group);
  }
  const notice=document.createElement('p');notice.id='export-roomVersionNotice';notice.setAttribute('role','status');roomReview.append(notice);updateRoomVersionNotice();
 }
 function updateRoomVersionNotice(){const notice=byId('export-roomVersionNotice');if(!notice)return;notice.textContent=roomChoicesReady()&&hasUnpairedRoomSource()?MI18n.t('export.roomVersion.unpaired'):'';notice.hidden=!notice.textContent;}
 async function roomExportApi(path,data){
  await MI18n.ready;const response=await fetch('/api/'+path,{method:'POST',headers:{'Content-Type':'application/json','X-MI-Language':MI18n.locale},body:JSON.stringify(data)}),body=await response.json();
  if(!response.ok)throw Object.assign(Error(MI18n.error(body,response.statusText)),{code:body.code||body.errorCode||body.error?.code});return body;
 }
 function exportSignature(kind,data){return JSON.stringify({kind,parts:parts(),data});}
 function roomSignature(data){return JSON.stringify({projects:data.projects,extraRooms:data.extraRooms,scope:data.scope,region:data.scope==='region'?data.region:''});}
 function acceptRoomCheck(result,signature,preserve=false){
  const previous=preserve?{sources:roomSourceChoices,assets:roomAssetChoices}:null;
  roomCheck=result;roomCheckSignature=signature;roomSourceChoices={};roomAssetChoices={};
  for(const room of roomCheck.rooms||[])for(const [kind,versions]of [['source',room.renderVersions||[]],['settings',room.settingsVersions||[]]]){const complete=versions.filter(version=>version.complete),saved=previous?.sources[versionKey(room)]?.[kind],recommended=kind==='source'?room.recommendedSourceId:room.recommendedSettingsId,selected=complete.find(version=>version.id===saved)||complete.find(version=>version.id===recommended)||(complete.length===1?complete[0]:null);if(selected){roomSourceChoices[versionKey(room)]??={};roomSourceChoices[versionKey(room)][kind]=selected.id;}}
  for(const asset of roomCheck.assets||[]){const complete=asset.versions.filter(version=>version.complete),saved=previous?.assets[asset.key],selected=complete.find(version=>version.id===saved)||complete.find(version=>version.id===asset.recommendedId)||(complete.length===1?complete[0]:null);if(selected)roomAssetChoices[asset.key]=selected.id;}
  drawRoomVersions();
 }
 async function refreshRoomCheck(preserve=true){
  const sequence=++roomCheckSequence,data=request(),signature=roomSignature(data);
  if(format()==='json'||scope()==='region'&&!data.region||scope()==='project'&&(!data.projects.length||!parts().includes('room'))){roomCheck=null;roomCheckSignature='';roomCheckError='';loadingRoomCheck=false;drawRoomVersions();review();return;}
  loadingRoomCheck=true;roomCheckError='';review();drawRooms();
  const current=()=>sequence===roomCheckSequence&&signature===roomSignature(request())&&dialog.open&&format()!=='json';
  try{
   const payload={projects:data.projects,extraRooms:data.extraRooms,scope:data.scope,region:data.region};
   let result=await roomExportApi('export-room-check',payload);if(!current())return;acceptRoomCheck(result,signature,preserve);
   const attempt=syncQueue.catch(()=>{}).then(()=>autoSyncRooms(result,current));syncQueue=attempt;
   if(await attempt&&current()){result=await roomExportApi('export-room-check',payload);if(!current())return;acceptRoomCheck(result,signature,true);for(const room of result.rooms||[])if(room.state==='needs_sync'&&syncAttempts.has(syncToken(room))&&!syncError(room))syncErrors.set(syncToken(room),MI18n.t('export.roomState.syncIncomplete'));}
  }
  catch(error){if(sequence===roomCheckSequence){roomCheckError=error.message||MI18n.t('export.validation.roomsFailed');roomCheck=null;roomCheckSignature='';drawRoomVersions();}}
  finally{if(sequence===roomCheckSequence){loadingRoomCheck=false;drawRoomVersions();review();}}
 }
 function review(){
  const selected=ids(),chosen=parts(),region=scope()==='region',current=format(),runtime=['mod','playable'].includes(current);
  byId('export-projectContent').hidden=region;byId('export-regionContent').hidden=!region;
  byId('export-assetParts').hidden=current!=='assets';byId('export-associated').hidden=['assets','json'].includes(current)||region&&(current!=='playable'||!regionData?.projectIds?.length);byId('export-externalProjects').hidden=region||current==='json';roomReview.hidden=current==='json'||!parts().includes('room')||(!roomReview.children.length);
  byId('export-roomContent').hidden=region||!chosen.includes('room');byId('pack-pearlCollectionField').hidden=!byId('pack-pearls').checked;
  for(const input of dialog.querySelectorAll('[name=exportFormat]')){input.disabled=building;input.parentElement.hidden=region?!['region','playable'].includes(input.value):input.value==='region';delete input.parentElement.dataset.available;}
  byId('pack-projectMetadata').hidden=current!=='project';byId('pack-metadata').hidden=!runtime;byId('pack-workPearls').closest('label').hidden=!runtime;
  byId('pack-sceneAssets').hidden=!runtime;byId('export-coverTitle').textContent=text(current==='playable'?'封面与场景':'封面');sceneEditor?.setEnabled(current==='playable');
  byId('export-startRoomField').hidden=current!=='playable';drawStartRooms(region,selected);
  byId('export-formatNote').textContent='';byId('export-formatNote').hidden=true;byId('export-completeContent').hidden=true;
  const busy=building||loadingPreferences||current!=='json'&&(loadingRooms||loadingRoomCheck||loadingRegion||loadingExternalCheck||!!syncingRoom||importingFiles),issue=validationIssue();byId('pack-build').disabled=busy;byId('pack-build').setAttribute('aria-describedby','pack-status');dialog.setAttribute('aria-busy',String(busy));
  const recheck=byId('export-refreshRooms');if(recheck)recheck.disabled=busy;
  for(const button of dialog.querySelectorAll('.export-sync-room,.export-import-file'))button.disabled=busy;
  byId('pack-build').textContent=loadingRooms||loadingRoomCheck?MI18n.t('export.validation.roomsLoading'):loadingRegion?MI18n.t('export.validation.regionLoading'):loadingPreferences?MI18n.t('export.validation.preferencesLoading'):building?text('正在检查导出内容…'):issue?.retry?MI18n.t('export.roomVersion.recheck'):text('导出');
  if(!busy)showValidation(issue);
 }
 function drawStartRooms(region,selected){
  const select=byId('export-startRoom');
  const names=[...new Set(region?(regionData?.rooms||[]):roomRows.filter(row=>selected.includes(row.projectId)&&row.available&&(row.required||extras.has(row.name))).map(row=>row.name))].filter(name=>!name.startsWith('GATE_')&&!name.endsWith('OFFSCREEN'));
  const waiting=roomRows.find(row=>row.projectId===project?.projectId&&row.kind==='entry'&&names.includes(row.name))||roomRows.find(row=>row.kind==='entry'&&selected.includes(row.projectId)&&names.includes(row.name));
  const blank=document.createElement('option');blank.value='';blank.textContent=text('选择起始房间');
  select.replaceChildren(blank,...names.map(name=>{const option=MI18n.content(document.createElement('option'));option.value=name;option.textContent=name;return option;}));
  if(startRoom===null&&names.length)startRoom=waiting?.name||'';
  selectValue(select,startRoom);
 }
 function checkedRoom(row){const rooms=roomCheck?.rooms||[];return rooms.find(room=>room.projectId===row.projectId&&room.room===row.name)||(!row.required?rooms.find(room=>room.room===row.name):null);}
 function roomStatus(row,room){
  if(syncingRoom===row.projectId+'/'+row.name)return MI18n.t('export.roomState.syncing');
  if(loadingRoomCheck)return MI18n.t('export.roomState.checking');
  if((room?.state||row.state)==='needs_sync')return MI18n.t('export.roomState.needsSync');
  const current=room||row,missing=(current.missing||[])[0];if(missing)return MI18n.t('export.roomState.missingFile',{file:missing});
  if(current.reason==='render_invalid')return MI18n.t('export.roomState.invalidRender');if(current.reason==='settings_invalid')return MI18n.t('export.roomState.invalidSettings');
  if(room){if(!(room.renderVersions||[]).some(version=>version.complete))return MI18n.t('export.roomState.missingRender');if(!(room.settingsVersions||[]).some(version=>version.complete))return MI18n.t('export.roomState.missingSettings');return MI18n.t('export.roomState.ready');}
  if(row.reason==='render_missing')return MI18n.t('export.roomState.missingRender');if(row.reason==='settings_missing')return MI18n.t('export.roomState.missingSettings');if(row.reason)return MI18n.text(row.reason);
  return MI18n.t(row.available?'export.roomState.ready':'export.roomState.missingRender');
 }
 function appendRoomVersions(host,row,room){
  if(!room)return;
  const fields=roomVersionFields(room);if(!fields.children.length)return;
  const details=document.createElement('details'),summary=document.createElement('summary');details.className='export-room-options';details.dataset.roomKey=versionKey(room);summary.textContent=MI18n.t('export.roomState.chooseVersion');details.append(summary,fields);details.open=['source','settings'].some(kind=>!(kind==='source'?room.renderVersions:room.settingsVersions).some(version=>version.complete&&version.id===roomSourceChoices[versionKey(room)]?.[kind]));host.append(details);
 }
 function syncKind(room){
  if(room.syncable===false||!['ai','entry'].includes(room.kind)||room.required===false||!(room.settingsVersions||[]).some(version=>version.complete))return '';
  const owner=projects.find(value=>value.projectId===room.projectId),binding=owner?.roomBinding;
  if(room.kind==='entry'&&binding?.entryMode==='existing')return '';
  return room.kind;
 }
 async function autoSyncRooms(result,current){
  let attempted=false;
  for(const room of result.rooms||[]){
   if(!current())break;
   const kind=syncKind(room),token=syncToken(room);if(room.state!=='needs_sync'||!kind||syncAttempts.has(token))continue;
   syncAttempts.add(token);syncErrors.delete(token);attempted=true;syncingRoom=versionKey(room);drawRooms();review();
   try{await api('sync-room',{projectId:room.projectId,kind,apply:false,forExport:true});}
   catch(error){syncErrors.set(token,error.message||MI18n.t('export.roomState.syncFailed'));}
   finally{if(syncingRoom===versionKey(room))syncingRoom='';if(current()){drawRooms();review();}}
  }
  return attempted;
 }
 async function retrySync(room){
  if(syncingRoom||loadingRoomCheck||building||importingFiles)return;
  syncAttempts.delete(syncToken(room));syncErrors.delete(syncToken(room));await refreshRoomCheck();
 }
 function appendSyncState(host,room){
  if(!room||room.state!=='needs_sync')return;
  const error=syncError(room);if(!error)return;
  const line=document.createElement('div'),message=document.createElement('span');line.className='export-room-repair';message.textContent=error;line.append(message);
  if(syncKind(room)){const retry=document.createElement('button');retry.type='button';retry.className='export-sync-room';retry.textContent=MI18n.t('export.roomState.retrySync');retry.disabled=!!syncingRoom||loadingRoomCheck||building||importingFiles;retry.onclick=run(()=>retrySync(room));line.append(retry);}
  host.append(line);
 }
 function appendMissingFiles(host,files,showRelative=false){
  for(const file of files){
   const line=document.createElement('div'),name=MI18n.content(document.createElement('span'));line.className='export-missing-file';line.dataset.missingFile=missingKey(file);name.textContent=host.classList.contains('export-extra-room')&&file.reason==='missing_file'?MI18n.t('export.roomState.missingFile',{file:file.name}):showRelative?file.relative||file.name:file.name;name.title=file.relative||'';line.append(name);
   if(file.reason!=='invalid_file'){
    const input=document.createElement('input'),button=document.createElement('button');input.type='file';input.multiple=true;input.hidden=true;button.type='button';button.className='export-import-file';button.textContent=MI18n.t('export.roomState.importFile');button.disabled=loadingRoomCheck||!!syncingRoom||building||importingFiles;button.onclick=()=>input.click();input.onchange=run(async()=>{const chosen=Array.from(input.files||[]);input.value='';if(chosen.length)await importMissingFiles(file,chosen);});line.append(button,input);
   }else{const error=document.createElement('span');error.textContent=MI18n.t('export.roomState.invalidFile');line.append(error);}
   if(importErrors.has(missingKey(file))){const error=document.createElement('span');error.className='export-file-error';error.textContent=importErrors.get(missingKey(file));line.append(error);}
   host.append(line);
  }
 }
 async function importMissingFiles(target,files){
  if(importingFiles||building||loadingRoomCheck||syncingRoom||format()==='json')return;
  const signature=roomSignature(request()),sequence=roomCheckSequence,token=roomCheck?.snapshotToken,current=()=>dialog.open&&format()!=='json'&&sequence===roomCheckSequence&&signature===roomSignature(request());
  const available=missingFiles().filter(file=>file.projectId===target.projectId&&file.room===target.room&&file.reason!=='invalid_file'),selected=[];
  importingFiles=true;importErrors.delete(missingKey(target));review();drawRoomVersions();
  try{
   if(files.length>64||files.some(file=>file.size>64*1024*1024)||files.reduce((sum,file)=>sum+file.size,0)>64*1024*1024)throw Error(MI18n.t('export.fileImport.tooLarge'));
   for(const file of files){
    const matches=available.filter(value=>value.name.toLowerCase()===file.name.toLowerCase()),match=matches.length===1?matches[0]:matches.find(value=>missingKey(value)===missingKey(target));if(!match)throw Error(MI18n.t('export.fileImport.nameMismatch',{expected:target.name}));
    const base64=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',')[1]||'');reader.onerror=()=>reject(Error(MI18n.t('export.roomState.fileReadFailed',{file:file.name})));reader.readAsDataURL(file);});
    selected.push({name:file.name,base64,missingFileId:match.id,projectId:match.projectId,room:match.room,relative:match.relative});
   }
   if(!current())return;
   const data=request();await roomExportApi('export-file-import',{projects:data.projects,extraRooms:data.extraRooms,scope:data.scope,region:data.region,snapshotToken:token,files:selected});
   if(current()){for(const file of available)importErrors.delete(missingKey(file));if(scope()==='region')await refreshRegion();else await refreshRoomCheck();}
  }catch(error){if(current())importErrors.set(missingKey(target),error.message||MI18n.t('export.roomState.importFailed'));}
  finally{importingFiles=false;drawRoomVersions();review();}
 }
 function drawRooms(){
  const selected=new Set(ids()),required=roomRows.filter(row=>row.required&&selected.has(row.projectId));
  byId('export-matchedRooms').replaceChildren(...required.map(row=>{
   const room=checkedRoom(row),host=document.createElement('div'),line=document.createElement('div');host.className='export-matched-item';host.dataset.roomKey=row.projectId+'/'+row.name;line.className='export-matched-row';const kind=document.createElement('span'),name=MI18n.content(document.createElement('span')),state=document.createElement('span');kind.textContent=text(row.kind==='ai'?'演算室':'等待房间');name.textContent=row.name;state.textContent=roomStatus(row,room);line.append(kind,name,state);host.append(line);
   appendSyncState(host,room);if(room)appendMissingFiles(host,roomMissingFiles(room));
   appendRoomVersions(host,row,room);return host;
  }));
  const mandatory=new Set(required.map(r=>r.name)),query=byId('export-roomSearch').value.trim().toUpperCase(),seen=new Set();
  const candidates=roomRows.filter(row=>{if(!selected.has(row.projectId)||mandatory.has(row.name)||seen.has(row.name))return false;seen.add(row.name);return true;});
  for(const name of extras)if(!candidates.some(row=>row.name===name)&&!mandatory.has(name))candidates.push({name,projectId:ids()[0],region:name.split('_')[0],available:false});
  candidates.sort((a,b)=>Number(extras.has(b.name))-Number(extras.has(a.name)));
  byId('export-roomChoices').replaceChildren(...candidates.filter(row=>!query||row.name.includes(query)||row.region.includes(query)).map(row=>{const host=document.createElement('div');host.className='export-extra-room';host.dataset.roomKey=row.projectId+'/'+row.name;const c=document.createElement('input');c.type='checkbox';c.value=row.name;c.checked=extras.has(row.name);c.onchange=run(async()=>{if(c.checked)extras.add(row.name);else extras.delete(row.name);invalidate();changed();await refreshRoomCheck();});const l=label(row.name,c);if(row.reason)l.title=MI18n.text(row.reason);host.append(l);if(c.checked){const room=checkedRoom(row),files=room?roomMissingFiles(room):[];if(room?.state==='missing'&&!files.length){const status=document.createElement('p');status.className='muted';status.textContent=roomStatus(row,room);host.append(status);}appendSyncState(host,room);appendMissingFiles(host,files);appendRoomVersions(host,row,room);}return host;}));
  for(const id of ['export-requiredRooms','export-extraRooms'])if(byId(id).querySelector('.export-missing-file,.export-room-repair'))byId(id).open=true;
 }
 const roomRefresh=document.createElement('button');roomRefresh.id='export-refreshRooms';roomRefresh.type='button';roomRefresh.textContent=MI18n.t('export.roomVersion.recheck');roomRefresh.onclick=run(async()=>{await refreshRooms();if(scope()==='region')await refreshRegion();});byId('export-matchedRooms').after(roomRefresh);
 function drawExternalMods(){
  const rows=[...externalRows,...[...externalMods].filter(id=>!externalRows.some(row=>row.id===id)).map(id=>({id,name:id,available:false,reason:MI18n.t('export.selection.externalMissing')}))];
  byId('export-externalChoices').replaceChildren(...rows.map(row=>{const input=document.createElement('input');input.type='checkbox';input.value=row.id;input.checked=externalMods.has(row.id);input.disabled=row.available===false&&!input.checked;input.onchange=run(async()=>{input.checked?externalMods.add(row.id):externalMods.delete(row.id);invalidateExport();changed();await inspectExternalMods();});const item=label(row.name||row.id,input);if(row.reason)item.title=MI18n.text(row.reason);return item;}));
 }
 async function inspectExternalMods(){
  const sequence=++externalSequence,selected=[...externalMods],details=byId('export-externalExcluded');externalError=false;externalErrorText='';details.hidden=true;details.querySelector('div').replaceChildren();
  if(!selected.length){loadingExternalCheck=false;review();return;}loadingExternalCheck=true;review();
  try{const result=await api('project-bundle-mod-check',{externalMods:selected});if(sequence!==externalSequence)return;for(const item of result.mods||[]){if(!item.excluded?.length)continue;const heading=MI18n.content(document.createElement('p')),list=MI18n.content(document.createElement('ul'));heading.textContent=item.name||item.id;for(const name of item.excluded){const line=document.createElement('li');line.textContent=name;list.append(line);}details.querySelector('div').append(heading,list);details.hidden=false;}}
  catch(error){if(sequence===externalSequence){externalError=true;externalErrorText=error.message;byId('export-externalStatus').textContent=error.message;}}
  finally{if(sequence===externalSequence){loadingExternalCheck=false;review();}}
 }
 async function refreshExternalMods(){
  if(loadingExternal)return;loadingExternal=true;externalError=false;byId('export-externalStatus').textContent=MI18n.t('export.selection.loadingProjects');
  try{const result=await api('project-bundle-mods');externalRows=result.mods||[];drawExternalMods();if(externalMods.size)await inspectExternalMods();byId('export-externalStatus').textContent=externalRows.length?'':MI18n.t('export.selection.noExternalProjects');}
  catch(error){externalError=true;byId('export-externalStatus').textContent=error.message;drawExternalMods();}
  finally{loadingExternal=false;review();}
 }
 byId('export-externalProjects').addEventListener('toggle',()=>{if(byId('export-externalProjects').open&&!externalRows.length)refreshExternalMods();});
 async function refreshRooms(){
  if(format()==='json'){roomSequence++;roomRows=[];roomsError='';loadingRooms=false;await refreshRoomCheck();return;}
  const sequence=++roomSequence;loadingRooms=true;roomsError='';review();
  try{const result=await Promise.all(ids().filter(id=>projects.some(project=>project.projectId===id)).map(id=>api('project-package-rooms?id='+encodeURIComponent(id)+'&check=0')));if(sequence!==roomSequence)return;roomRows=result.flatMap(value=>value.rooms.map(row=>({...row,projectId:value.projectId})));if(seedExtraDefaults){for(const value of result)for(const name of value.extraRooms||[])extras.add(name);seedExtraDefaults=false;}drawRooms();if(scope()==='project')await refreshRoomCheck();}
  catch(error){if(sequence===roomSequence){roomsError=error.message||MI18n.t('export.validation.roomsFailed');roomRows=[];drawRooms();}}
  finally{if(sequence===roomSequence){loadingRooms=false;review();}}
 }
 async function refreshRegion(){
  const sequence=++regionSequence,selected=ids(),n=byId('export-regionSummary'),code=byId('export-region').value;regionData=null;regionError='';n.replaceChildren();loadingRegion=true;review();
  try{
   if(!validSelection(byId('export-region')))return;
   const result=await api('region-package-inspect',{region:code,projects:selected});if(sequence!==regionSequence||code!==byId('export-region').value||JSON.stringify(selected)!==JSON.stringify(ids())||scope()!=='region')return;regionData=result;await refreshRoomCheck();
   const count=document.createElement('p');count.textContent=MI18n.t('export.region_rooms',{count:result.rooms?.length??result.roomCount??0});n.append(count);if(result.includedProjects?.length){const title=document.createElement('p');title.textContent=MI18n.t('export.selection.regionProjects');n.append(title);for(const item of result.includedProjects){const name=MI18n.content(document.createElement('p'));name.textContent=item.name||item.projectId;n.append(name);}}
   if(result.dependencies?.length){const title=document.createElement('p');title.textContent=text('依赖模组');n.append(title);for(const dependency of result.dependencies){const p=MI18n.content(document.createElement('p'));p.textContent=dependency.name||dependency.id;n.append(p);}}
  }catch(error){if(sequence===regionSequence)regionError=error.message||MI18n.t('export.validation.regionFailed');}
  finally{if(sequence===regionSequence){loadingRegion=false;review();}}
 }
 async function refreshRegionOptions(){
  const sequence=++regionSequence,selected=ids();regionData=null;regionError='';loadingRegion=true;byId('export-regionSummary').replaceChildren();review();
  try{const values=await api('region-package-choices?projects='+encodeURIComponent(selected.filter(id=>projects.some(project=>project.projectId===id)).join(',')));if(sequence!==regionSequence||scope()!=='region'||JSON.stringify(selected)!==JSON.stringify(ids()))return;const select=byId('export-region'),blank=document.createElement('option');blank.value='';blank.textContent=text('选择地区');select.replaceChildren(blank,...(values.regions||values).map(item=>{const option=MI18n.content(document.createElement('option'));option.value=item.code||item.name;option.textContent=item.displayName?item.displayName+' ('+option.value+')':option.value;option.disabled=item.available===false;if(item.reason)option.title=item.reason;return option;}));if(selectedRegion===null)selectedRegion=[...select.options].find(option=>option.value&&!option.disabled)?.value||'';selectValue(select,selectedRegion);await refreshRegion();}
  catch(error){if(sequence===regionSequence)regionError=error.message||MI18n.t('export.validation.regionFailed');}
  finally{if(sequence===regionSequence){loadingRegion=false;review();}}
 }
 byId('roomStudio').onclick=()=>{byId('roomStudio').href='/rooms?project='+encodeURIComponent(project?.projectId||'')+'&lang='+MI18n.locale;};
 byId('export').onclick=run(async()=>{
  if(loadingPreferences)return;const owner=project,current=()=>project===owner&&!window.MIStudioPage?.isBusy();loadingPreferences=true;
  try{
  await sceneReady;if(!current())return;
  if(dialog.open)await closeDialog();dialog.inert=true;draft=null;clearTimeout(draftTimer);
  if(!current())return;
  const [storedOptions,pearlProjects]=await Promise.all([api('export-settings?id='+encodeURIComponent(owner.projectId)).catch(error=>{const cached=sessionDrafts.get(owner.projectId);if(cached)return cached.settings;throw error;}),api('pearl-projects')]);if(!current())return;const recovered=sessionDrafts.get(owner.projectId),options=recovered?.settings||storedOptions;
  byId('pack-pearlCollection').replaceChildren(...pearlProjects.projects.map(item=>{const node=MI18n.content(document.createElement('option'));node.value=item.id;node.textContent=item.name;return node;}));
  selectValue(byId('pack-pearlCollection'),options.pearlCollectionId??pearlProjects.activeId);
  for(const key of ['id','name','authors','description','version'])byId('pack-'+key).value=options[key]||'';
  byId('pack-projectName').value=options.packageName??owner.name??'';byId('pack-projectVersion').value=options.packageVersion||'0.1.0';
  cover=options.cover||'';byId('pack-coverPreview').src=cover;byId('pack-coverPreview').hidden=!cover;
  savedScene=structuredClone(options.scene??null);sceneEdited=false;sceneEditor?.reset(savedScene,cover);
  for(const input of dialog.querySelectorAll('[name=part]'))input.checked=Array.isArray(options.parts)?options.parts.includes(input.value):true;
  for(const key of ['dialogue','pearls','broadcasts','workPearls','projections'])byId('pack-'+key).checked=typeof options[key]==='boolean'?options[key]:key==='dialogue'?selectedParts().includes('dialogue'):false;
  dialog.querySelector('[name=exportScope][value='+(['project','region'].includes(options.scope)?options.scope:'project')+']').checked=true;
  dialog.querySelector('[name=exportFormat][value='+(['project','json','mod','playable','assets','region'].includes(options.format)?options.format:'project')+']').checked=true;
  const allowedFormats=scope()==='region'?['region','playable']:['project','json','mod','playable','assets'];if(!allowedFormats.includes(format()))dialog.querySelector('[name=exportFormat][value='+allowedFormats[0]+']').checked=true;lastFormat=format();
  const selected=Array.isArray(options.projects)?options.projects:[project.projectId],choices=[...projects,...selected.filter(id=>!projects.some(project=>project.projectId===id)).map(projectId=>({projectId,name:projectId}))];
  byId('pack-projects').replaceChildren(...choices.map(p=>{const input=document.createElement('input');input.type='checkbox';input.value=p.projectId;input.checked=selected.includes(p.projectId);input.onchange=run(async()=>{invalidate();changed();await refreshRooms();if(scope()==='region')await refreshRegionOptions();});return label(p.name,input);}));
  externalMods=new Set(options.externalMods||[]);externalRows=[];externalError=false;externalErrorText='';externalSequence++;loadingExternalCheck=false;byId('export-externalExcluded').hidden=true;byId('export-externalChoices').replaceChildren();byId('export-externalStatus').textContent='';extras=new Set(options.extraRooms||[]);seedExtraDefaults=!Array.isArray(options.extraRooms);startRoom=typeof options.startRoom==='string'?options.startRoom:null;selectedRegion=typeof options.region==='string'?options.region:null;byId('export-region').replaceChildren();selectValue(byId('export-region'),selectedRegion);regionSequence++;loadingRegion=false;roomsError='';regionError='';regionData=null;roomRows=[];roomCheck=null;roomCheckSignature='';roomSourceChoices={};roomAssetChoices={};roomCheckSequence++;roomCheckError='';loadingRoomCheck=false;roomReview.hidden=true;byId('export-roomSearch').value='';byId('export-review').hidden=true;byId('pack-status').textContent='';reviewed='';dialog.showModal();await refreshRooms();if(externalMods.size)await refreshExternalMods();if(scope()==='region')await refreshRegionOptions();
  if(!current()){dialog.close();return;}draft={pid:owner.projectId,revision:recovered?1:0,saved:0};if(recovered)sessionDrafts.set(owner.projectId,{token:draft,settings:recovered.settings});
  }finally{loadingPreferences=false;dialog.inert=false;review();}
 });
 for(const input of dialog.querySelectorAll('[name=part],#export-associated input,#pack-pearlCollection'))input.addEventListener('change',run(async()=>{invalidate();await refreshRoomCheck();}));
 for(const input of dialog.querySelectorAll('[name=exportFormat]'))input.addEventListener('change',run(async()=>{
  const previous=lastFormat;lastFormat=format();
  if(format()==='json'||previous==='json'||roomsError){invalidate();await refreshRooms();return;}
  invalidateExport();updateRoomVersionNotice();
  if(loadingRooms||loadingRegion||loadingRoomCheck||!parts().includes('room')||roomCheck&&roomCheckSignature===roomSignature(request()))return;
  if(roomRows.length)await refreshRoomCheck();else await refreshRooms();
 }));
 for(const input of dialog.querySelectorAll('[name=exportFormat],#pack-projectMetadata input,#pack-metadata input,#pack-metadata textarea'))input.addEventListener('change',invalidateExport);
 for(const input of dialog.querySelectorAll('#pack-projectMetadata input,#pack-metadata input,#pack-metadata textarea'))input.addEventListener('input',invalidateExport);
 for(const input of dialog.querySelectorAll('[name=part],[name=exportFormat],#export-associated input,#pack-pearlCollection,#pack-projectMetadata input,#pack-metadata input,#pack-metadata textarea')){input.addEventListener('change',changed);input.addEventListener('input',changed);}
 byId('export-startRoom').onchange=()=>{startRoom=byId('export-startRoom').value;invalidateExport();changed();};
 for(const input of dialog.querySelectorAll('[name=exportScope]'))input.onchange=run(async()=>{const allowed=scope()==='region'?['region','playable']:['project','json','mod','playable','assets'];if(!allowed.includes(format()))dialog.querySelector('[name=exportFormat][value='+allowed[0]+']').checked=true;lastFormat=format();if(scope()!=='region'){regionSequence++;loadingRegion=false;regionError='';}invalidate();changed();if(scope()==='region')await refreshRegionOptions();else await refreshRooms();});
 byId('export-region').onchange=run(async()=>{selectedRegion=byId('export-region').value;invalidate();changed();await refreshRegion();});byId('export-roomSearch').oninput=drawRooms;
 for(const [key,checked] of [['all',true],['none',false]])byId('pack-'+key).onclick=run(async()=>{byId('pack-projects').querySelectorAll('input').forEach(c=>c.checked=checked);invalidate();changed();await refreshRooms();if(scope()==='region')await refreshRegionOptions();});
 byId('export-completeContent').onclick=()=>{dialog.querySelectorAll('[name=part]').forEach(input=>input.checked=true);invalidate();changed();};
 for(const button of dialog.querySelectorAll('[data-export-close]'))button.onclick=run(closeDialog);
 dialog.addEventListener('cancel',event=>{event.preventDefault();run(closeDialog)();});
 byId('pack-cover').onchange=run(async()=>{const file=byId('pack-cover').files[0];if(!file)return;if(file.size>8000000)throw Error(text('封面最大 8 MB'));cover=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result);r.onerror=reject;r.readAsDataURL(file);});byId('pack-coverPreview').src=cover;byId('pack-coverPreview').hidden=false;sceneEditor?.setCover(cover);invalidateExport();changed();});
 byId('pack-clearCover').onclick=()=>{cover='';byId('pack-cover').value='';byId('pack-coverPreview').hidden=true;sceneEditor?.setCover(cover);invalidateExport();changed();};
 function request(){const result={packageName:byId('pack-projectName').value,packageVersion:byId('pack-projectVersion').value,cover,scene:sceneEdited?sceneEditor?.serialize()??null:structuredClone(savedScene),settingsProject:draft?.pid||project.projectId,projects:scope()==='region'&&Array.isArray(regionData?.projectIds)?[...regionData.projectIds]:ids(),externalMods:scope()==='project'?[...externalMods]:[],extraRooms:scope()==='project'&&parts().includes('room')?[...extras].filter(name=>!roomRows.some(row=>row.required&&ids().includes(row.projectId)&&row.name===name)):[],scope:scope(),region:byId('export-region').value,startRoom:byId('export-startRoom').value};for(const k of ['id','name','authors','description','version'])result[k]=byId('pack-'+k).value;for(const k of ['dialogue','pearls','broadcasts','workPearls','projections'])result[k]=format()==='assets'||scope()==='region'&&!result.projects.length?false:k==='dialogue'||k==='workPearls'&&format()==='project'?true:byId('pack-'+k).checked;if(result.pearls)result.pearlCollectionId=byId('pack-pearlCollection').value;return result;}
 async function buildExport(checkOnly=false){
  if(building||loadingPreferences||format()!=='json'&&(loadingRooms||loadingRoomCheck||loadingRegion||loadingExternalCheck||!!syncingRoom||importingFiles))return;
  const initialIssue=validationIssue(true);if(initialIssue){showValidation(initialIssue,true);if(initialIssue.retry==='rooms')await refreshRooms();else if(initialIssue.retry==='roomCheck')await refreshRoomCheck();else if(initialIssue.retry==='region')await refreshRegionOptions();return;}
  building=true;review();const status=byId('pack-status');delete status.dataset.validation;status.textContent=text('正在检查导出内容…');
  try{
   if(format()==='json'){
    const id=ids()[0],value=id===project.projectId?serialize():projects.find(item=>item.projectId===id);if(!value)throw Error(MI18n.t('export.validation.missingProject',{name:id}));
    const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'})),link=document.createElement('a');link.href=url;link.download=(value.name||value.projectId).replace(/[\\/:*?"<>|\u0000-\u001f]/g,'_')+'.json';link.textContent=text('下载');status.replaceChildren(link);link.click();setTimeout(()=>URL.revokeObjectURL(url),60000);return;
   }
   if(ids().includes(project.projectId))await save();await persistDraft();const changedIssue=validationIssue(true);if(changedIssue){showValidation(changedIssue,true);return;}const kind=format(),data=request(),signature=exportSignature(kind,data),{scene,...contentData}=data;let needsReview=checkOnly;
   if(scope()==='region'||ids().length&&parts().includes('room')){
    if(checkOnly||roomCheckSignature!==roomSignature(data)||roomCheck){
     await refreshRoomCheck();if(signature!==exportSignature(format(),request()))return;if(roomCheckError)throw Error(roomCheckError);needsReview||=!roomChoicesReady();
    }
   }
   const issue=validationIssue();if(issue){showValidation(issue,true);return;}
   const previewSignature=JSON.stringify({signature,selection:roomChoicePayload()});
   if(['mod','playable'].includes(kind)&&scope()==='project'&&extras.size&&reviewed!==previewSignature){const choice=roomChoicePayload(),plan=await roomExportApi('export-room-plan',{...contentData,...(choice?{roomSourceChoices:choice}:{})});if(signature!==exportSignature(format(),request())||previewSignature!==JSON.stringify({signature,selection:roomChoicePayload()}))return;const review=byId('export-review'),heading=document.createElement('div'),names=MI18n.content(document.createElement('div'));heading.textContent=text('导出房间编号');names.textContent=plan.rooms.map(r=>r.sourceRoom===r.name?r.name:r.sourceRoom+' → '+r.name).join('\n');review.replaceChildren(heading,names);review.hidden=false;needsReview=true;}
   if(needsReview){reviewed=previewSignature;status.textContent='';return;}
   const choice=roomChoicePayload(),selection=choice?{roomSourceChoices:choice}:{};
   const result=kind==='project'?await roomExportApi('export-project-package',{...contentData,...selection}):kind==='mod'?await roomExportApi('export-standalone',{...contentData,...selection}):kind==='playable'?await roomExportApi('export-playable',{...data,...selection}):kind==='region'?await roomExportApi('export-region-package',{scope:'region',region:data.region,projects:data.projects,...selection}):await roomExportApi('export',{project:data.projects[0]===project.projectId?serialize():projects.find(p=>p.projectId===data.projects[0]),parts:parts(),...selection});
   const a=document.createElement('a');a.href=result.url;a.download='';a.textContent=text('下载');status.replaceChildren(a);a.click();
   if(result.connectionsPending){const p=document.createElement('div');p.textContent=MI18n.t('export.connectionsPending');status.append(p);}
   if(result.missingSources?.length){const p=document.createElement('span');p.textContent='\n'+MI18n.t('export.no_rained_source',{rooms:result.missingSources.join(', ')});status.append(p);}
  }catch(error){
   if(error.code==='room_choices_stale'){
    invalidateExport();roomCheckSignature='';error.message=MI18n.t('export.roomVersion.stale');const data=request(),signature=exportSignature(format(),data);
    try{const result=await roomExportApi('export-room-check',{projects:data.projects,extraRooms:data.extraRooms,scope:data.scope,region:data.region});if(signature===exportSignature(format(),request()))acceptRoomCheck(result,roomSignature(data),true);}catch{}
   }else if(/[A-Za-z]:[\\/]|\\\\[^\\]+\\/.test(error.message))error.message=MI18n.t('export.roomVersion.failed');
   status.textContent=error.message;throw error;
  }finally{building=false;review();}
 }
 byId('pack-build').onclick=run(()=>buildExport());
 window.addEventListener('mi-language-change',()=>{roomRefresh.textContent=MI18n.t('export.roomVersion.recheck');drawRoomVersions();review();});
 window.MIProjectPackageImport=async(file,onResult)=>{
  async function upload(path,choices={},replace=false){const headers={'Content-Type':'application/zip','X-MI-Language':MI18n.locale};if(Object.keys(choices).length)headers['X-MI-Import-Choices']=JSON.stringify(choices);if(replace)headers['X-MI-Replace-Project']='1';const response=await fetch('/api/'+path,{method:'POST',headers,body:file}),body=await response.json();if(!response.ok)throw Error(MI18n.error(body,response.statusText));return body;}
  const finish=result=>{if(typeof onResult==='function')onResult(result);else if(result.externalMods?.length&&typeof notice==='function')notice(MI18n.t('export.import.externalSaved'),false);return result.project||result.projects?.[0]||null;};
  let info=await upload('project-package-inspect');
  if(info.kind!=='project-bundle'){
   if(info.collision&&!window.confirm(MI18n.t('export.replace_project',{name:info.name})))return null;
   const result=await upload('import-project-package',{},!!info.collision);if(!result.ok)throw Error(MI18n.t('export.import.changed'));return finish(result);
  }
  if(!info.collisions?.length){const result=await upload('import-project-package');if(result.ok)return finish(result);if(!result.collisions?.length)throw Error(MI18n.t('export.import.changed'));info=result;}
  const popup=byId('projectImportDialog'),container=byId('import-contents'),status=byId('import-status'),confirm=byId('import-confirm'),choices={};
  function drawCollisions(value){
   container.replaceChildren();status.textContent='';
   for(const item of value.collisions||[]){const row=document.createElement('div');row.className='import-project-row';const name=MI18n.content(document.createElement('strong'));name.textContent=item.name||item.key;row.append(name);const select=document.createElement('select');select.dataset.importKey=item.key;select.setAttribute('aria-label',MI18n.t('export.import.conflict',{name:name.textContent}));const actions=item.kind==='external'?['keep','copy']:['keep','replace'];if(!actions.includes(choices[item.key]))choices[item.key]='keep';for(const action of actions){const option=document.createElement('option');option.value=action;option.textContent=MI18n.t('export.import.'+action);select.append(option);}select.value=choices[item.key];select.onchange=()=>{choices[item.key]=select.value;};row.append(select);container.append(row);}
  }
  drawCollisions(info);confirm.disabled=false;
  popup.showModal();
  return new Promise(resolve=>{
   const close=()=>{if(confirm.disabled)return;popup.close();resolve(null);};byId('import-close').onclick=close;byId('import-cancel').onclick=close;popup.oncancel=event=>{event.preventDefault();close();};
   confirm.onclick=async()=>{if(confirm.disabled)return;confirm.disabled=true;status.textContent=MI18n.t('export.import.working');try{const result=await upload('import-project-package',choices);if(!result.ok){if(result.collisions?.length)drawCollisions(result);throw Error(MI18n.t('export.import.changed'));}popup.close();resolve(finish(result));}catch(error){status.textContent=error.message;}finally{confirm.disabled=false;}};
  });
 };
})();
