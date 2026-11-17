let scanCount=0,listingCount=0,lastScan=null,deferredScan=null,downloadedBlob=null,syncActive=0,maxSyncActive=0,syncGate=null,importFailure=null,preflightFailure=false;
const syncedTokens=new Set(),failSync=new Set(['demo-pool/DEMO_ENTRY']),sourceVersions=new Map(),missingRecords=[];
project.schema='moreiterators.project.v1';project.textures={head:{layers:[{png:'data:image/png;base64,fixture'}]}};
const sourceVersion=(pid,name)=>pid+'/'+name+':'+(sourceVersions.get(pid+'/'+name)||1);
const selectionOriginalApi=api;
api=async(path,data)=>{
 if(path.startsWith('project-package-rooms')){listingCount++;const query=new URLSearchParams(path.split('?')[1]);if(query.get('check')!=='0')throw Error('Room listing repeated version preflight');return roomFixture(query.get('id'));}
 if(path==='sync-room'){
  calls.push({path,data:structuredClone(data)});syncActive++;maxSyncActive=Math.max(maxSyncActive,syncActive);
  const name=roomFixture(data.projectId).rooms.find(row=>row.kind===data.kind).name,key=data.projectId+'/'+name;
  try{if(syncGate){const wait=syncGate;syncGate=null;await wait;}if(failSync.has(key))throw Error('Rained output did not update: '+name);syncedTokens.add(sourceVersion(data.projectId,name));return {ok:true,room:name,cameras:1};}finally{syncActive--;}
 }
 return selectionOriginalApi(path,data);
};
const selectionOriginalFetch=window.fetch,oldCreateObjectURL=URL.createObjectURL.bind(URL);
URL.createObjectURL=blob=>{downloadedBlob=blob;return oldCreateObjectURL(blob);};
function selectedReport(data){
 const rooms=data.projects.flatMap(id=>roomFixture(id).rooms.filter(row=>row.required).map(row=>({projectId:id,room:row.name,kind:row.kind,required:true,syncable:true,sourceToken:sourceVersion(id,row.name),state:syncedTokens.has(sourceVersion(id,row.name))?'ready':'needs_sync',renderVersions:[{id:'old-'+row.name,origin:'project',complete:true,pairedSource:false,modifiedAt:1000},{id:'new-'+row.name,origin:'installed',complete:true,pairedSource:true,modifiedAt:2000}],settingsVersions:[{id:'settings-'+row.name,origin:'project',complete:true}],recommendedSourceId:'new-'+row.name,recommendedSettingsId:'settings-'+row.name})));
 for(const name of data.extraRooms||[])rooms.push({projectId:data.projects[0],room:name,kind:'extra',required:false,syncable:false,state:'ready',renderVersions:[{id:'render-'+name,origin:'enabled',complete:true,pairedSource:false}],settingsVersions:[{id:'settings-'+name,origin:'enabled',complete:true}],recommendedSourceId:'render-'+name,recommendedSettingsId:'settings-'+name});
 for(const room of rooms){room.missingFiles=missingRecords.filter(file=>file.projectId===room.projectId&&file.room===room.room);room.missing=room.missingFiles.map(file=>file.name);if(room.missingFiles.length){if(room.state!=='needs_sync')room.state='missing';if(room.missingFiles.some(file=>file.kind==='settings'))room.settingsVersions.forEach(value=>value.complete=false);}}
 return {rooms,assets:[],issues:[],snapshotToken:'fixture-'+scanCount,missingFiles:structuredClone(missingRecords),parameterConflicts:[{projectId:'demo-pool',room:'DEMO_AI',kind:'gravity'}],requiresChoices:false};
}
window.fetch=async(path,options)=>{
 if(path==='/api/export-room-check'){
  scanCount++;lastScan=JSON.parse(options.body);calls.push({path,data:lastScan});
  if(deferredScan){const wait=deferredScan;deferredScan=null;return await wait;}
  if(preflightFailure)return {ok:false,json:async()=>({error:'Current room scan failed'})};
  return {ok:true,json:async()=>selectedReport(lastScan)};
 }
 if(path==='/api/export-file-import'){
  const data=JSON.parse(options.body);calls.push({path,data});if(importFailure)return {ok:false,json:async()=>({code:importFailure,params:{name:'DEMO_MISSING_settings.txt'}})};
  for(const file of data.files){const index=missingRecords.findIndex(row=>row.id===file.missingFileId);if(index<0)throw Error('Wrong import target');missingRecords.splice(index,1);}
  return {ok:true,json:async()=>({ok:true,imported:data.files})};
 }
 if(path==='/api/export-project-package'){calls.push({path,data:JSON.parse(options.body)});return {ok:true,json:async()=>({url:'#fixture-project'})};}
 return selectionOriginalFetch(path,options);
};
const syncCalls=()=>calls.filter(call=>call.path==='sync-room'),importCalls=()=>calls.filter(call=>call.path==='/api/export-file-import');
const missingFile=(id,room,name,kind='settings',relative='rooms/'+room+'/rendered/'+name)=>({id,projectId:'demo-pool',room,name,kind,relative,reason:'missing_file'});
async function chooseFiles(id,files){const input=document.querySelector('[data-missing-file="'+id+'"] input[type=file]');Object.defineProperty(input,'files',{configurable:true,value:files});await input.onchange();await flush();}
(async()=>{
 let checks=0;const assert=(value,message)=>{checks++;if(!value)throw Error(message);};
 try{
  await MI18n.ready;
  for(const [locale,message]of [['zh-CN','房间同步请求无效。'],['en','Invalid room sync request.']]){MI18n.setLocale(locale,false);assert(MI18n.error({error:'Invalid room sync request.'})===message,'Sync request error is not localized');assert(MI18n.error({code:'export.fileImport.stale'})===CATALOGS[locale]['export.fileImport.stale'],'Import error is not localized');}
  MI18n.setLocale('zh-CN',false);await $('export').onclick();
  assert(scanCount===2&&listingCount===1,'Batch sync did not use one initial and one final preflight without another catalog');
  assert(syncCalls().length===2&&maxSyncActive===1,'Owned rooms were not synchronized sequentially');
  assert(syncCalls().every(call=>call.data.apply===false&&call.data.forExport===true),'Export sync could apply room files or use fallback settings');
  assert(!calls.some(call=>call.path==='save'),'Opening export saved the authored project');
  assert($('export-matchedRooms').children.length===2,'Required rooms missing');
  assert($('export-matchedRooms').textContent.includes('Rained output did not update: DEMO_ENTRY'),'Sync failure reason is hidden');
  assert($('export-matchedRooms').querySelectorAll('.export-sync-room').length===1,'Successful sync still requires a manual button');
  assert(!$('export-matchedRooms').querySelector('.export-sync-room').disabled,'Retry remains disabled');
  assert(!document.querySelector('[data-policy]'),'Gravity or palette choice was repeated during export');
  assert($('export-matchedRooms').querySelector('input[value="new-DEMO_AI"]').checked,'Latest rendering not selected');
  assert(!$('export-matchedRooms').querySelector('.export-room-options').open,'Version choices unnecessarily expanded');
  await $('export-refreshRooms').onclick();assert(syncCalls().length===2,'Failed sync automatically retried without source change');
  await $('export-matchedRooms').querySelector('input[value="old-DEMO_AI"]').onchange();
  const formatScans=scanCount,formatListings=listingCount;
  for(const format of ['mod','playable','project']){await pick(document.querySelector('[name=exportFormat][value='+format+']'));assert(scanCount===formatScans&&listingCount===formatListings,'Format change repeated scanning');assert($('export-matchedRooms').querySelector('input[value="old-DEMO_AI"]').checked,'Format change lost authored version choice');}
  failSync.clear();await $('export-matchedRooms').querySelector('.export-sync-room').onclick();
  assert(syncCalls().length===3&&!$('export-matchedRooms').querySelector('.export-sync-room'),'Explicit retry did not complete');
  assert($('export-matchedRooms').querySelector('input[value="old-DEMO_AI"]').checked,'Retry replaced author version choice');
  const missing=$('export-roomChoices').querySelector('input[value="DEMO_MISSING"]');assert(!missing.disabled,'Old catalog status prevents selection');await pick(missing);
  assert(lastScan.extraRooms.includes('DEMO_MISSING'),'Extra room selection did not rescan');
  missingRecords.push(missingFile('settings','DEMO_MISSING','DEMO_MISSING_settings.txt'),missingFile('variant','DEMO_MISSING','DEMO_MISSING_settings-White.txt'),missingFile('camera','DEMO_MISSING','DEMO_MISSING_2.png','render'),missingFile('palette','','palette8.png','asset','palettes/palette8.png'),missingFile('region','','properties.txt','region','regions/DEMO/properties.txt'));
  await $('export-refreshRooms').onclick();
  assert(document.querySelectorAll('[data-missing-file]').length===5,'Missing room, variant, palette or region files were hidden');
  assert(document.querySelector('[data-missing-file=settings]').closest('.export-extra-room'),'Extra settings import is not beside that room');
  assert(document.querySelector('[data-missing-file=settings]>span').textContent===MI18n.t('export.roomState.missingFile',{file:'DEMO_MISSING_settings.txt'}),'Extra room missing file does not use the concise missing filename');
  assert(!document.querySelector('[data-missing-file=settings]').closest('.export-extra-room').querySelector(':scope>p.muted'),'Extra room repeats the same missing file in a separate status paragraph');
  assert(document.querySelector('[data-missing-file=palette]>span').textContent==='palettes/palette8.png'&&document.querySelector('[data-missing-file=region]>span').textContent==='regions/DEMO/properties.txt','Ungrouped missing files do not show their relative locations');
  assert(!document.querySelector('[data-missing-file=settings] button').disabled,'Import remains disabled after scanning');
  const beforeCancel=importCalls().length;await chooseFiles('settings',[]);assert(importCalls().length===beforeCancel,'Cancel sent an import request');
  await chooseFiles('settings',[new File(['bad'],'wrong.txt')]);assert(importCalls().length===beforeCancel&&document.querySelector('[data-missing-file=settings]').textContent.includes(MI18n.t('export.fileImport.nameMismatch',{expected:'DEMO_MISSING_settings.txt'})),'Wrong file was sent or expected name hidden');
  const readFile=FileReader.prototype.readAsDataURL;let readCount=0;FileReader.prototype.readAsDataURL=function(file){readCount++;return readFile.call(this,file);};await chooseFiles('settings',[{name:'DEMO_MISSING_settings.txt',size:64*1024*1024+1}]);assert(readCount===0&&importCalls().length===beforeCancel&&document.querySelector('[data-missing-file=settings]').textContent.includes(MI18n.t('export.fileImport.tooLarge')),'Large file was read before checking size');FileReader.prototype.readAsDataURL=readFile;
  importFailure='export.fileImport.stale';await chooseFiles('settings',[new File(['settings'],'DEMO_MISSING_settings.txt')]);assert(document.querySelector('[data-missing-file=settings]').textContent.includes(CATALOGS['zh-CN']['export.fileImport.stale']),'Import API failure was not shown beside file');importFailure=null;
  const beforeImportScans=scanCount,beforeImportListings=listingCount;await chooseFiles('settings',[new File(['settings'],'DEMO_MISSING_settings.txt'),new File(['variant'],'DEMO_MISSING_settings-White.txt'),new File(['png'],'DEMO_MISSING_2.png')]);
  const imported=importCalls().at(-1).data;assert(imported.files.length===3&&imported.files.every(file=>file.missingFileId&&file.base64&&!Object.hasOwn(file,'targetRelative')),'Import lost server-approved targets');
  assert(imported.snapshotToken&&scanCount===beforeImportScans+1&&listingCount===beforeImportListings,'Import reread catalogs or omitted fresh check');
  assert(!document.querySelector('[data-missing-file=settings]')&&document.querySelectorAll('[data-missing-file]').length===2,'Imported state was not refreshed');
  assert($('export-matchedRooms').querySelector('input[value="old-DEMO_AI"]').checked,'Import reset author version choice');
  await chooseFiles('palette',[new File(['png'],'palette8.png')]);await chooseFiles('region',[new File(['settings'],'properties.txt')]);assert(!document.querySelector('[data-missing-file]'),'Palette or region import did not refresh');
  missingRecords.push(missingFile('regionScope','','properties.txt','region','regions/DEMO/properties.txt'));window.regionBlocked=true;await pick(document.querySelector('[name=exportScope][value=region]'));assert(!$('export-roomVersions').hidden&&$('export-roomVersions').querySelector('[data-missing-file=regionScope]'),'Region failure hid its missing-file import');window.regionBlocked=false;await chooseFiles('regionScope',[new File(['settings'],'properties.txt')]);assert(!$('export-roomVersions').querySelector('[data-missing-file=regionScope]'),'Region import did not refresh its failed inspection');await pick(document.querySelector('[name=exportScope][value=project]'));
  preflightFailure=true;await $('export-refreshRooms').onclick();const exportsBefore=calls.filter(call=>call.path==='/api/export-project-package').length;await $('pack-build').onclick();assert(calls.filter(call=>call.path==='/api/export-project-package').length===exportsBefore&&$('pack-status').textContent.includes('Current room scan failed'),'Failed preflight used an old successful report to export');assert(errors.pop()==='Current room scan failed','Expected preflight failure was not reported');preflightFailure=false;await $('export-refreshRooms').onclick();
  sourceVersions.set('demo-pool/DEMO_AI',2);missingRecords.push(missingFile('ownedSettings','DEMO_AI','DEMO_AI_settings.txt'));const beforeSettingsSync=syncCalls().length;await $('export-refreshRooms').onclick();assert(syncCalls().length===beforeSettingsSync,'Room with missing settings used default settings to sync');await chooseFiles('ownedSettings',[new File(['settings'],'DEMO_AI_settings.txt')]);assert(syncCalls().length===beforeSettingsSync+1,'Room did not auto sync after its missing settings were imported');
  sourceVersions.set('demo-pool/DEMO_AI',3);sourceVersions.set('demo-pool/DEMO_ENTRY',2);
  let releaseSync;syncGate=new Promise(resolve=>releaseSync=resolve);const pendingSync=$('export-refreshRooms').onclick();await flush();const beforeSwitch=syncCalls().length;
  await pick(document.querySelector('[name=exportFormat][value=json]'));assert(!$('pack-build').disabled,'JSON waits for obsolete sync');releaseSync();await pendingSync;await flush();assert(syncCalls().length===beforeSwitch,'JSON switch continued old sync batch');
  assert($('export-roomContent').hidden&&$('export-roomVersions').hidden,'JSON shows room controls');
  const jsonScans=scanCount;calls.length=0;await $('pack-build').onclick();assert(scanCount===jsonScans&&!calls.some(call=>call.path==='save'||call.path==='sync-room'||call.path.includes('export-project')),'JSON depends on rooms or backend packaging');
  const value=JSON.parse(await downloadedBlob.text());assert(value.schema==='moreiterators.project.v1'&&value.textures.head.layers[0].png===project.textures.head.layers[0].png,'JSON lost authored structure');assert(!Object.hasOwn(value,'snapshotToken')&&!Object.hasOwn(value,'roomSourceChoices'),'JSON contains export-only state');
  await pick(document.querySelector('[name=exportFormat][value=project]'));assert(scanCount>jsonScans&&syncCalls().some(call=>call.data.kind==='entry'),'Leaving JSON did not check current source');
  projects[1].roomBinding={entryMode:'existing'};const second=$('pack-projects').querySelector('input[value="demo-oracle"]');await pick(second);const secondSyncs=syncCalls().filter(call=>call.data.projectId==='demo-oracle');assert(lastScan.projects.length===2&&secondSyncs.length===1&&secondSyncs[0].data.kind==='ai','Multiple projects or external entry sync scope is incorrect');await pick(second,false);
  let release;deferredScan=new Promise(resolve=>release=resolve);const pending=$('export-refreshRooms').onclick();await flush();await pick(document.querySelector('[name=exportFormat][value=json]'));release({ok:false,json:async()=>({error:'Late obsolete room failure'})});await pending;await flush();assert(!$('pack-status').textContent.includes('Late obsolete')&&!$('pack-build').disabled,'Stale scan affected JSON');
  await pick($('pack-projects').querySelector('input[value="demo-oracle"]'));assert($('pack-status').textContent.includes(MI18n.t('export.format.oneProject')),'JSON multiple selection is not explained');
  assert(!errors.length,'Unexpected errors: '+errors.join('\n'));$('result').textContent=JSON.stringify({ok:true,checks,scanCount});
 }catch(error){$('result').textContent=JSON.stringify({ok:false,checks,error:error.stack,errors});}
})();
