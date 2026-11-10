'use strict';
(()=>{
 const byId=id=>document.getElementById(id),dialog=byId('exportDialog');
 let cover='',building=false,loadingRooms=false,roomSequence=0,regionSequence=0,roomRows=[],extras=new Set(),regionData=null,reviewed='';
 let draft=null,draftTimer=null,saveQueue=Promise.resolve(),loadingPreferences=false;
 let startRoom=null,selectedRegion=null,seedExtraDefaults=false,savedScene=null,sceneEdited=false;
 let roomCheck=null,roomCheckSignature='',roomSourceChoices={},roomAssetChoices={},roomPolicies={};
 const roomReview=document.createElement('section');roomReview.id='export-roomVersions';roomReview.className='export-section export-room-versions';roomReview.hidden=true;byId('export-roomReviewAnchor').before(roomReview);
 const ids=()=>[...byId('pack-projects').querySelectorAll('input:checked')].map(c=>c.value);
 const parts=()=>[...dialog.querySelectorAll('[name=part]:checked')].map(c=>c.value);
 const scope=()=>dialog.querySelector('[name=exportScope]:checked').value;
 const format=()=>dialog.querySelector('[name=exportFormat]:checked')?.value;
 const associated=()=>['pearls','workPearls','broadcasts','projections'].some(k=>byId('pack-'+k).checked);
 const text=s=>MI18n.text(s);
 function changed(){if(!dialog.open||loadingPreferences||!draft)return;draft.revision++;clearTimeout(draftTimer);draftTimer=setTimeout(()=>persistDraft().catch(error=>{byId('pack-status').textContent=error.message;}),400);}
 async function persistDraft(){
  clearTimeout(draftTimer);const token=draft;if(!token||token.saved===token.revision)return;
  const revision=token.revision,data={...request(),settingsProject:token.pid,extraRooms:[...extras],parts:parts(),format:format(),pearlCollectionId:byId('pack-pearlCollection').value};
  const job=saveQueue.catch(()=>{}).then(()=>api('export-settings',data));saveQueue=job;
  await job;token.saved=Math.max(token.saved,revision);
 }
 async function closeDialog(){await persistDraft();dialog.close();}
 const sceneEditor=window.MIExportScene,sceneReady=MI18n.ready.then(()=>sceneEditor?.mount(byId('pack-sceneEditor'),{onChange:()=>{if(!loadingPreferences)sceneEdited=true;invalidate();changed();},onCoverChange:value=>{cover=value;byId('pack-coverPreview').src=cover;byId('pack-coverPreview').hidden=!cover;invalidate();changed();}}));
 function selectValue(select,value){if(value&&!Array.from(select.options).some(option=>option.value===value)){const option=MI18n.content(document.createElement('option'));option.value=value;option.textContent=value;option.disabled=true;option.title=text('缺少文件');select.append(option);}select.value=value||'';}
 const validSelection=select=>!!select.value&&!select.selectedOptions[0]?.disabled;
 function label(value,node){const l=document.createElement('label'),span=MI18n.content(document.createElement('span'));span.textContent=value;l.append(node,span);return l;}
 function note(value){byId('export-formatNote').textContent=text(value);byId('export-formatNote').hidden=!value;}
 function invalidate(){reviewed='';roomCheck=null;roomCheckSignature='';roomSourceChoices={};roomAssetChoices={};roomPolicies={};roomReview.hidden=true;byId('export-review').hidden=true;byId('pack-status').textContent='';review();}
 function versionKey(room){return room.projectId+'/'+room.room;}
 function versionChoicesReady(){return !roomCheck||!(roomCheck.issues||[]).length&&(roomCheck.rooms||[]).every(room=>['source','settings'].every(kind=>(kind==='source'?room.renderVersions:room.settingsVersions).some(version=>version.complete&&version.id===roomSourceChoices[versionKey(room)]?.[kind])))&&(roomCheck.assets||[]).every(asset=>!asset.versions.some(version=>version.complete)||asset.versions.some(version=>version.complete&&version.id===roomAssetChoices[asset.key]));}
 function activeParameterConflicts(){return (roomCheck?.parameterConflicts||[]).filter(conflict=>{const selected=roomSourceChoices[versionKey(conflict)]?.settings;return selected&&(!conflict.settingsVersionIds?.length||conflict.settingsVersionIds.includes(selected));});}
 function policyValue(conflict){const policy=roomPolicies[conflict.projectId];return conflict.kind==='gravity'?policy?.gravity?.[conflict.room]:policy?.[conflict.kind];}
 function roomChoicesReady(){return versionChoicesReady()&&activeParameterConflicts().every(conflict=>['project','room'].includes(policyValue(conflict)));}
 function exportRoomPolicies(){const result={};for(const conflict of activeParameterConflicts()){const policy=result[conflict.projectId]??={};if(conflict.kind==='gravity')(policy.gravity??={})[conflict.room]=policyValue(conflict)||'';else policy[conflict.kind]=policyValue(conflict)||'';}return result;}
 function roomChoicePayload(){return roomCheck?.rooms?.length||roomCheck?.assets?.length?{snapshotToken:roomCheck.snapshotToken,choices:structuredClone(roomSourceChoices),assetChoices:{...roomAssetChoices},policies:exportRoomPolicies(),extraRooms:request().extraRooms}:undefined;}
 function hasUnpairedRoomSource(){return format()==='project'&&(roomCheck?.rooms||[]).some(room=>room.renderVersions.some(version=>version.id===roomSourceChoices[versionKey(room)]?.source&&!version.pairedSource));}
 function versionOrigin(version,origin=version.origin){const names={project:'export.roomVersion.project',local:'export.roomVersion.local',installed:'export.roomVersion.installed',enabled:'export.roomVersion.enabled',rained:'export.roomVersion.rained',game:'export.roomVersion.game',source:'export.roomVersion.source'};return MI18n.t(names[origin]||'export.roomVersion.other');}
 function versionLabel(version){const name=version.providers?.[0]?.name||version.providers?.[0]?.id||(ids().length>1?(version.projectIds||[]).map(id=>projects.find(project=>project.projectId===id)?.name||id).join(', '):'');return name?MI18n.t('export.roomVersion.provider',{origin:versionOrigin(version),name}):versionOrigin(version);}
 function versionOrigins(version){return [...new Set(version.origins||[])].map(origin=>versionOrigin(version,origin)).concat((version.providers||[]).map(provider=>provider.name||provider.id)).join('\n');}
 function changeRoomChoice(refreshPolicies=true){reviewed='';byId('export-review').hidden=true;byId('pack-status').textContent='';if(refreshPolicies)drawRoomPolicies();updateRoomVersionNotice();review();}
 function drawRoomPolicies(){
  const conflicts=activeParameterConflicts();
  for(const host of roomReview.querySelectorAll('[data-policy-host]')){
   host.replaceChildren();
   for(const conflict of conflicts.filter(value=>versionKey(value)===host.dataset.policyHost)){
    const {projectId:id,room,kind}=conflict,line=document.createElement('label'),title=document.createElement('span'),select=document.createElement('select');title.textContent=MI18n.t('export.roomVersion.'+kind);select.dataset.policy=kind;select.dataset.project=id;select.dataset.room=room;
    for(const [value,label]of [['','export.roomVersion.choosePolicy'],['project','export.roomVersion.currentProject'],['room','export.roomVersion.selectedRoom']]){const option=document.createElement('option');option.value=value;option.textContent=MI18n.t(label);select.append(option);}select.value=policyValue(conflict)||'';select.onchange=()=>{const policy=roomPolicies[id]??={};if(kind==='gravity')(policy.gravity??={})[room]=select.value;else policy[kind]=select.value;changeRoomChoice(false);};line.append(title,select);host.append(line);
   }
  }
 }
 function focusRoomChoice(){const select=[...roomReview.querySelectorAll('select[data-policy]')].find(input=>!input.value),radio=[...roomReview.querySelectorAll('input[type=radio]:not(:disabled)')].find(input=>![...roomReview.querySelectorAll('input[type=radio]')].some(other=>other.name===input.name&&other.checked)),target=select||radio;if(target){target.scrollIntoView({block:'center',behavior:'smooth'});target.focus();}}
 function versionDate(value){const date=new Date(typeof value==='number'&&value<1e12?value*1000:value);return value&&!Number.isNaN(date.valueOf())?date.toLocaleString(MI18n.locale):MI18n.t('export.roomVersion.undated');}
 function drawRoomVersions(){
  roomReview.replaceChildren();const visibleVersions=(roomCheck?.rooms||[]).some(room=>[room.renderVersions,room.settingsVersions].some(versions=>versions.length>1||versions.some(version=>!version.complete)))||(roomCheck?.assets||[]).some(asset=>asset.versions.length>1||asset.versions.some(version=>!version.complete));roomReview.hidden=!visibleVersions&&!activeParameterConflicts().length&&!hasUnpairedRoomSource()&&!(roomCheck?.issues||[]).length;if(roomReview.hidden)return;
  const heading=document.createElement('div'),title=document.createElement('h3'),recheck=document.createElement('button');heading.className='export-projects-heading';title.textContent=MI18n.t('export.roomVersion.title');recheck.type='button';recheck.textContent=MI18n.t('export.roomVersion.recheck');recheck.disabled=building;recheck.onclick=run(()=>buildExport(true));heading.append(title,recheck);roomReview.append(heading);
  for(const room of roomCheck.rooms||[]){
   const groups=[['source','export.roomVersion.render',room.renderVersions],['settings','export.roomVersion.settings',room.settingsVersions]].filter(([, ,versions])=>versions.length>1||versions.some(version=>!version.complete));if(!groups.length&&!(roomCheck.parameterConflicts||[]).some(conflict=>versionKey(conflict)===versionKey(room)))continue;
   const section=document.createElement('div'),name=MI18n.content(document.createElement('h4'));section.className='export-room-version';name.textContent=room.room;section.append(name);
   const owner=projects.find(value=>value.projectId===room.projectId);if(owner&&ids().length>1){const author=MI18n.content(document.createElement('p'));author.className='muted';author.textContent=owner.name;section.append(author);}
   for(const [kind,key,versions]of groups){
    const group=document.createElement('fieldset'),legend=document.createElement('legend');legend.textContent=MI18n.t(key);group.append(legend);
    for(const version of versions){
     const input=document.createElement('input'),line=document.createElement('label'),body=document.createElement('span'),origin=document.createElement('span'),date=document.createElement('span');input.type='radio';input.name='room-version-'+versionKey(room)+'-'+kind;input.value=version.id;input.dataset.room=versionKey(room);input.dataset.kind=kind;input.checked=roomSourceChoices[versionKey(room)]?.[kind]===version.id;input.disabled=!version.complete;origin.textContent=versionLabel(version);origin.title=versionOrigins(version);date.className='muted';date.textContent=versionDate(version.modifiedAt);body.append(origin,date);
     if(!version.complete){const issue=document.createElement('span');issue.className='muted';issue.textContent=MI18n.t('export.roomVersion.incomplete');body.append(issue);}
     input.onchange=()=>{roomSourceChoices[versionKey(room)]??={};roomSourceChoices[versionKey(room)][kind]=version.id;changeRoomChoice();};line.append(input,body);group.append(line);
    }
    section.append(group);
   }
   const policies=document.createElement('div');policies.className='export-room-policy';policies.dataset.policyHost=versionKey(room);section.append(policies);roomReview.append(section);
  }
  for(const asset of roomCheck.assets||[]){
   if(asset.versions.length<2&&asset.versions.every(version=>version.complete))continue;
   const group=document.createElement('fieldset'),legend=MI18n.content(document.createElement('legend'));group.className='export-room-asset';legend.textContent=/^(?:[A-Za-z]:|[\\/])/.test(asset.relative)?MI18n.t('export.roomVersion.asset'):asset.relative;group.append(legend);
   for(const version of asset.versions){
    const input=document.createElement('input'),line=document.createElement('label'),body=document.createElement('span'),origin=document.createElement('span'),date=document.createElement('span');input.type='radio';input.name='room-asset-'+asset.key;input.value=version.id;input.dataset.asset=asset.key;input.checked=roomAssetChoices[asset.key]===version.id;input.disabled=!version.complete;origin.textContent=versionLabel(version);origin.title=versionOrigins(version);date.className='muted';date.textContent=versionDate(version.modifiedAt);body.append(origin,date);
    if(!version.complete){const issue=document.createElement('span');issue.className='muted';issue.textContent=MI18n.t('export.roomVersion.incomplete');body.append(issue);}
    input.onchange=()=>{roomAssetChoices[asset.key]=version.id;changeRoomChoice();};line.append(input,body);group.append(line);
   }
   roomReview.append(group);
  }
  const notice=document.createElement('p'),locate=document.createElement('button');notice.id='export-roomVersionNotice';notice.setAttribute('role','status');locate.id='export-locateChoice';locate.type='button';locate.textContent=MI18n.t('export.roomVersion.locateChoice');locate.onclick=focusRoomChoice;roomReview.append(notice,locate);drawRoomPolicies();updateRoomVersionNotice();
 }
 function updateRoomVersionNotice(){const notice=byId('export-roomVersionNotice');if(!notice)return;notice.textContent=!versionChoicesReady()?MI18n.t((roomCheck.issues||[]).length?'export.roomVersion.missing':'export.roomVersion.choose'):!roomChoicesReady()?MI18n.t('export.roomVersion.pendingPolicy'):hasUnpairedRoomSource()?MI18n.t('export.roomVersion.unpaired'):'';notice.hidden=!notice.textContent;byId('export-locateChoice').hidden=roomChoicesReady()||!!roomCheck.issues?.length;}
 async function roomExportApi(path,data){
  await MI18n.ready;const response=await fetch('/api/'+path,{method:'POST',headers:{'Content-Type':'application/json','X-MI-Language':MI18n.locale},body:JSON.stringify(data)}),body=await response.json();
  if(!response.ok)throw Object.assign(Error(MI18n.error(body,response.statusText)),{code:body.code||body.errorCode||body.error?.code});return body;
 }
 function exportSignature(kind,data){return JSON.stringify({kind,parts:parts(),data});}
 function acceptRoomCheck(result,signature){
  roomCheck=result;roomCheckSignature=signature;roomSourceChoices={};roomAssetChoices={};roomPolicies={};
  const owners=new Set([...(roomCheck.rooms||[]).map(room=>room.projectId),...(roomCheck.assets||[]).flatMap(asset=>asset.projectIds||[asset.projectId])]);
  for(const id of ids())if(owners.has(id)||projects.find(value=>value.projectId===id)?.editor?.externalRoomTools===true)roomPolicies[id]={};
  for(const room of roomCheck.rooms||[])for(const [kind,versions]of [['source',room.renderVersions],['settings',room.settingsVersions]]){const complete=versions.filter(version=>version.complete);if(complete.length===1){roomSourceChoices[versionKey(room)]??={};roomSourceChoices[versionKey(room)][kind]=complete[0].id;}}
  for(const asset of roomCheck.assets||[]){const complete=asset.versions.filter(version=>version.complete);if(complete.length===1)roomAssetChoices[asset.key]=complete[0].id;}
  drawRoomVersions();
 }
 function review(){
  const selected=ids(),chosen=parts(),region=scope()==='region',added=associated(),full=['appearance','textures','room','dialogue'].every(k=>chosen.includes(k));
  const current=format(),runtime=['mod','playable'].includes(current),missingProject=selected.some(id=>!projects.some(project=>project.projectId===id));
  byId('export-projectContent').hidden=false;byId('export-regionContent').hidden=!region;
  for(const label of dialog.querySelectorAll('[data-project-part]'))label.hidden=region;
  byId('pack-dialogue').parentElement.hidden=region&&current!=='playable';byId('export-associated').hidden=region&&current!=='playable';
  byId('export-roomContent').hidden=region||!chosen.includes('room');byId('pack-pearlCollectionField').hidden=!byId('pack-pearls').checked;
  const mod=!region&&selected.length>0&&['appearance','textures','room'].every(k=>chosen.includes(k));
  const available={project:!region&&selected.length===1&&full&&!added,mod,playable:region?selected.length>0:mod,assets:!region&&selected.length===1&&chosen.length>0&&!added&&(!chosen.includes('room')||!extras.size),region:region};
  for(const input of dialog.querySelectorAll('[name=exportFormat]')){input.disabled=building;input.parentElement.hidden=false;input.parentElement.dataset.available=String(!!available[input.value]);}
  byId('pack-metadata').hidden=!runtime;
  byId('pack-sceneAssets').hidden=!runtime;byId('export-coverTitle').textContent=text(current==='playable'?'封面与场景':'封面');sceneEditor?.setEnabled(current==='playable');
  byId('export-startRoomField').hidden=current!=='playable';drawStartRooms(region,selected);
  let message='';
  if(missingProject)message='standalone.error.projects';
  else if(!available[current]){
   if(region&&!['region','playable'].includes(current))message='export.format.regionScope';
   else if(!region&&current==='region')message='export.format.projectScope';
   else if(!selected.length)message='export.format.selectProjects';
   else if(['project','assets'].includes(current)&&selected.length!==1)message='export.format.oneProject';
   else if(['project','assets'].includes(current)&&added)message='export.format.associated';
   else if(current==='project'||runtime)message='export.format.requiredParts';
   else if(current==='assets'&&extras.size)message='export.format.extraRooms';
   else message='export.format.selectParts';
  }else if(current==='playable'&&!validSelection(byId('export-startRoom')))message='playable.badStart';
  byId('export-formatNote').textContent=message?MI18n.t(message):'';byId('export-formatNote').hidden=!message;
  byId('export-completeContent').hidden=region||available[current]||!['project','mod','playable'].includes(current)||['appearance','textures','room'].every(k=>chosen.includes(k))&&(current!=='project'||full);
  byId('pack-build').disabled=building||loadingPreferences||loadingRooms||missingProject||!roomChoicesReady()||!available[current]||(['mod','playable'].includes(current)&&byId('pack-pearls').checked&&!validSelection(byId('pack-pearlCollection')))||(current==='playable'&&!validSelection(byId('export-startRoom')))||(region&&(!regionData?.ok||regionData.blockers?.length||!validSelection(byId('export-region'))));
  const recheck=roomReview.querySelector('button');if(recheck)recheck.disabled=building||loadingRooms;
  byId('pack-build').textContent=text(reviewed||roomCheck&&roomChoicesReady()&&!(scope()==='project'&&extras.size&&['mod','playable'].includes(current))?'导出':'检查并导出');
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
 function drawRooms(){
  const selected=new Set(ids()),required=roomRows.filter(row=>row.required&&selected.has(row.projectId));
  byId('export-matchedRooms').replaceChildren(...required.map(row=>{const line=document.createElement('div');line.className='export-matched-row';const kind=document.createElement('span'),name=MI18n.content(document.createElement('span')),status=document.createElement('span');kind.textContent=text(row.kind==='ai'?'演算室':'等待房间');name.textContent=row.name;status.textContent=text(row.available?'已匹配':'缺少文件');line.append(kind,name,status);return line;}));
  const mandatory=new Set(required.map(r=>r.name)),query=byId('export-roomSearch').value.trim().toUpperCase(),seen=new Set();
  const candidates=roomRows.filter(row=>{if(!selected.has(row.projectId)||mandatory.has(row.name)||seen.has(row.name))return false;seen.add(row.name);return true;});
  for(const name of extras)if(!candidates.some(row=>row.name===name)&&!mandatory.has(name))candidates.push({name,region:name.split('_')[0],available:false,reason:text('缺少文件')});
  byId('export-roomChoices').replaceChildren(...candidates.filter(row=>!query||row.name.includes(query)||row.region.includes(query)).map(row=>{const c=document.createElement('input');c.type='checkbox';c.value=row.name;c.checked=extras.has(row.name);c.disabled=!row.available&&!c.checked;c.onchange=()=>{if(c.checked)extras.add(row.name);else extras.delete(row.name);invalidate();changed();};const l=label(row.name,c);if(row.reason)l.title=row.reason;return l;}));
 }
 async function refreshRooms(){
  const sequence=++roomSequence;loadingRooms=true;review();
  try{const result=await Promise.all(ids().filter(id=>projects.some(project=>project.projectId===id)).map(id=>api('project-package-rooms?id='+encodeURIComponent(id))));if(sequence!==roomSequence)return;roomRows=result.flatMap(value=>value.rooms.map(row=>({...row,projectId:value.projectId})));if(seedExtraDefaults){for(const value of result)for(const name of value.extraRooms||[])extras.add(name);seedExtraDefaults=false;}drawRooms();}
  finally{if(sequence===roomSequence){loadingRooms=false;review();}}
 }
 async function refreshRegion(){
  const sequence=++regionSequence,selected=ids(),n=byId('export-regionSummary');regionData=null;n.replaceChildren();review();const code=byId('export-region').value;if(!validSelection(byId('export-region'))||selected.some(id=>!projects.some(project=>project.projectId===id)))return;
  const result=await api('region-package-inspect',{region:code,projects:selected});if(sequence!==regionSequence||code!==byId('export-region').value||JSON.stringify(selected)!==JSON.stringify(ids())||scope()!=='region')return;regionData=result;
  for(const value of [MI18n.t('export.region_rooms',{count:result.rooms?.length??result.roomCount??0}),...(result.blockers||[])]){const p=document.createElement('p');p.textContent=value;n.append(p);}
  if(result.dependencies?.length){const title=document.createElement('p');title.textContent=text('依赖模组');n.append(title);for(const dependency of result.dependencies){const p=MI18n.content(document.createElement('p'));p.textContent=dependency.name||dependency.id;n.append(p);}}review();
 }
 async function refreshRegionOptions(){const selected=ids();regionData=null;review();const values=await api('region-package-choices?projects='+encodeURIComponent(selected.filter(id=>projects.some(project=>project.projectId===id)).join(',')));if(scope()!=='region'||JSON.stringify(selected)!==JSON.stringify(ids()))return;const select=byId('export-region'),blank=document.createElement('option');blank.value='';blank.textContent=text('选择地区');select.replaceChildren(blank,...(values.regions||values).map(item=>{const option=MI18n.content(document.createElement('option'));option.value=item.code||item.name;option.textContent=item.displayName?item.displayName+' ('+option.value+')':option.value;option.disabled=item.available===false;if(item.reason)option.title=item.reason;return option;}));if(selectedRegion===null)selectedRegion=[...select.options].find(option=>option.value&&!option.disabled)?.value||'';selectValue(select,selectedRegion);await refreshRegion();}
 byId('roomStudio').onclick=()=>{byId('roomStudio').href='/rooms?project='+encodeURIComponent(project?.projectId||'')+'&lang='+MI18n.locale;};
 byId('export').onclick=run(async()=>{
  if(loadingPreferences)return;const owner=project,current=()=>project===owner&&!window.MIStudioPage?.isBusy();loadingPreferences=true;
  try{
  await sceneReady;if(!current())return;
  if(dialog.open){await persistDraft();dialog.close();}dialog.inert=true;draft=null;clearTimeout(draftTimer);
  await save();if(!current())return;
  const [options,pearlProjects]=await Promise.all([api('export-settings?id='+encodeURIComponent(owner.projectId)),api('pearl-projects')]);if(!current())return;
  byId('pack-pearlCollection').replaceChildren(...pearlProjects.projects.map(item=>{const node=MI18n.content(document.createElement('option'));node.value=item.id;node.textContent=item.name;return node;}));
  selectValue(byId('pack-pearlCollection'),options.pearlCollectionId??pearlProjects.activeId);
  for(const key of ['id','name','authors','description','version'])byId('pack-'+key).value=options[key]||'';
  cover=options.cover||'';byId('pack-coverPreview').src=cover;byId('pack-coverPreview').hidden=!cover;
  savedScene=structuredClone(options.scene??null);sceneEdited=false;sceneEditor?.reset(savedScene,cover);
  for(const input of dialog.querySelectorAll('[name=part]'))input.checked=Array.isArray(options.parts)?options.parts.includes(input.value):true;
  for(const key of ['dialogue','pearls','broadcasts','workPearls','projections'])byId('pack-'+key).checked=typeof options[key]==='boolean'?options[key]:key==='dialogue'?parts().includes('dialogue'):false;
  dialog.querySelector('[name=exportScope][value='+(['project','region'].includes(options.scope)?options.scope:'project')+']').checked=true;
  dialog.querySelector('[name=exportFormat][value='+(['project','mod','playable','assets','region'].includes(options.format)?options.format:'project')+']').checked=true;
  const selected=Array.isArray(options.projects)?options.projects:[project.projectId],choices=[...projects,...selected.filter(id=>!projects.some(project=>project.projectId===id)).map(projectId=>({projectId,name:projectId}))];
  byId('pack-projects').replaceChildren(...choices.map(p=>{const input=document.createElement('input');input.type='checkbox';input.value=p.projectId;input.checked=selected.includes(p.projectId);input.onchange=run(async()=>{invalidate();changed();await refreshRooms();if(scope()==='region')await refreshRegionOptions();});return label(p.name,input);}));
  extras=new Set(options.extraRooms||[]);seedExtraDefaults=!Array.isArray(options.extraRooms);startRoom=typeof options.startRoom==='string'?options.startRoom:null;selectedRegion=typeof options.region==='string'?options.region:null;byId('export-region').replaceChildren();selectValue(byId('export-region'),selectedRegion);regionData=null;roomRows=[];roomCheck=null;roomCheckSignature='';roomSourceChoices={};roomAssetChoices={};roomPolicies={};roomReview.hidden=true;byId('export-roomSearch').value='';byId('export-review').hidden=true;byId('pack-status').textContent='';reviewed='';dialog.showModal();await refreshRooms();if(scope()==='region')await refreshRegionOptions();
  if(!current()){dialog.close();return;}draft={pid:owner.projectId,revision:0,saved:0};
  }finally{loadingPreferences=false;dialog.inert=false;review();}
 });
 for(const input of dialog.querySelectorAll('[name=part],[name=exportFormat],#export-associated input,#pack-pearlCollection,#pack-metadata input,#pack-metadata textarea'))input.addEventListener('change',invalidate);
 for(const input of dialog.querySelectorAll('[name=part],[name=exportFormat],#export-associated input,#pack-pearlCollection,#pack-metadata input,#pack-metadata textarea')){input.addEventListener('change',changed);input.addEventListener('input',changed);}
 byId('export-startRoom').onchange=()=>{startRoom=byId('export-startRoom').value;invalidate();changed();};
 for(const input of dialog.querySelectorAll('[name=exportScope]'))input.onchange=run(async()=>{invalidate();changed();if(scope()==='region')await refreshRegionOptions();});
 byId('export-region').onchange=run(async()=>{selectedRegion=byId('export-region').value;invalidate();changed();await refreshRegion();});byId('export-roomSearch').oninput=drawRooms;
 for(const [key,checked] of [['all',true],['none',false]])byId('pack-'+key).onclick=run(async()=>{byId('pack-projects').querySelectorAll('input').forEach(c=>c.checked=checked);invalidate();changed();await refreshRooms();if(scope()==='region')await refreshRegionOptions();});
 byId('export-completeContent').onclick=()=>{dialog.querySelectorAll('[name=part]').forEach(input=>input.checked=true);invalidate();changed();};
 for(const button of dialog.querySelectorAll('[data-export-close]'))button.onclick=run(closeDialog);
 dialog.addEventListener('cancel',event=>{event.preventDefault();run(closeDialog)();});
 byId('pack-cover').onchange=run(async()=>{const file=byId('pack-cover').files[0];if(!file)return;if(file.size>8000000)throw Error(text('封面最大 8 MB'));cover=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result);r.onerror=reject;r.readAsDataURL(file);});byId('pack-coverPreview').src=cover;byId('pack-coverPreview').hidden=false;sceneEditor?.setCover(cover);invalidate();changed();});
 byId('pack-clearCover').onclick=()=>{cover='';byId('pack-cover').value='';byId('pack-coverPreview').hidden=true;sceneEditor?.setCover(cover);invalidate();changed();};
 function request(){const result={cover,scene:sceneEdited?sceneEditor?.serialize()??null:structuredClone(savedScene),settingsProject:draft?.pid||project.projectId,projects:ids(),extraRooms:scope()==='project'&&parts().includes('room')?[...extras].filter(name=>!roomRows.some(row=>row.required&&ids().includes(row.projectId)&&row.name===name)):[],scope:scope(),region:byId('export-region').value,startRoom:byId('export-startRoom').value};for(const k of ['id','name','authors','description','version'])result[k]=byId('pack-'+k).value;for(const k of ['dialogue','pearls','broadcasts','workPearls','projections'])result[k]=byId('pack-'+k).checked;if(result.pearls)result.pearlCollectionId=byId('pack-pearlCollection').value;return result;}
 async function buildExport(checkOnly=false){
  if(building)return;building=true;review();const status=byId('pack-status');status.textContent=text('正在检查导出内容…');
  try{
   await persistDraft();const kind=format(),data=request(),signature=exportSignature(kind,data),{scene,...contentData}=data;let needsReview=checkOnly;
   if(scope()==='region'||parts().includes('room')){
    if(checkOnly||roomCheckSignature!==signature){
     const result=await roomExportApi('export-room-check',{projects:data.projects,extraRooms:data.extraRooms,scope:data.scope,region:data.region});if(signature!==exportSignature(format(),request()))return;
     acceptRoomCheck(result,signature);needsReview||=!!roomCheck.requiresChoices||!roomChoicesReady()||hasUnpairedRoomSource();
    }
   }
   if(!roomChoicesReady()){status.textContent=MI18n.t(versionChoicesReady()?'export.roomVersion.pendingPolicy':'export.roomVersion.choose');focusRoomChoice();return;}
   const previewSignature=JSON.stringify({signature,selection:roomChoicePayload()});
   if(['mod','playable'].includes(kind)&&scope()==='project'&&extras.size&&reviewed!==previewSignature){const choice=roomChoicePayload(),plan=await roomExportApi('export-room-plan',{...contentData,...(choice?{roomSourceChoices:choice}:{})});if(signature!==exportSignature(format(),request())||previewSignature!==JSON.stringify({signature,selection:roomChoicePayload()}))return;const review=byId('export-review'),heading=document.createElement('div'),names=MI18n.content(document.createElement('div'));heading.textContent=text('导出房间编号');names.textContent=plan.rooms.map(r=>r.sourceRoom===r.name?r.name:r.sourceRoom+' → '+r.name).join('\n');review.replaceChildren(heading,names);review.hidden=false;needsReview=true;}
   if(needsReview){reviewed=previewSignature;status.textContent='';return;}
   const choice=roomChoicePayload(),selection=choice?{roomSourceChoices:choice}:{};
   const result=kind==='project'?await roomExportApi('export-project-package',{projectId:data.projects[0],extraRooms:data.extraRooms,...selection}):kind==='mod'?await roomExportApi('export-standalone',{...contentData,...selection}):kind==='playable'?await roomExportApi('export-playable',{...data,...selection}):kind==='region'?await roomExportApi('export-region-package',{scope:'region',region:data.region,projects:data.projects,...selection}):await roomExportApi('export',{project:data.projects[0]===project.projectId?serialize():projects.find(p=>p.projectId===data.projects[0]),parts:parts(),...selection});
   const a=document.createElement('a');a.href=result.url;a.download='';a.textContent=text('下载');status.replaceChildren(a);a.click();
   if(result.missingSources?.length){const p=document.createElement('span');p.textContent='\n'+MI18n.t('export.no_rained_source',{rooms:result.missingSources.join(', ')});status.append(p);}
  }catch(error){
   if(error.code==='room_choices_stale'){
    invalidate();error.message=MI18n.t('export.roomVersion.stale');const data=request(),signature=exportSignature(format(),data);
    try{const result=await roomExportApi('export-room-check',{projects:data.projects,extraRooms:data.extraRooms,scope:data.scope,region:data.region});if(signature===exportSignature(format(),request()))acceptRoomCheck(result,signature);}catch{}
   }else if(/[A-Za-z]:[\\/]|\\\\[^\\]+\\/.test(error.message))error.message=MI18n.t('export.roomVersion.failed');
   status.textContent=error.message;throw error;
  }finally{building=false;review();}
 }
 byId('pack-build').onclick=run(()=>buildExport());
 window.addEventListener('mi-language-change',()=>{if(roomCheck)drawRoomVersions();review();});
 window.MIProjectPackageImport=async file=>{
  async function upload(path,replace=false){const r=await fetch('/api/'+path,{method:'POST',headers:{'Content-Type':'application/zip','X-MI-Language':MI18n.locale,...(replace?{'X-MI-Replace-Project':'1'}:{})},body:file});const body=await r.json();if(!r.ok)throw Error(MI18n.error(body,r.statusText));return body;}
  const info=await upload('project-package-inspect');
  if(info.collision&&!confirm(MI18n.t('export.replace_project',{name:info.name})))return null;
  const result=await upload('import-project-package',!!info.collision);if(!result.ok)throw Error(text('项目已存在，请重新确认覆盖。'));return result.project;
 };
})();
