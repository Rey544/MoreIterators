let fixtureExportFailure='rooms',fixturePendingExport=true,fixtureImportResult=null,fixtureNotice='';
const failureOriginalApi=api;
api=async(path,data)=>{
 if(path.startsWith('project-package-rooms')&&fixtureExportFailure==='rooms')throw Error('TEST_ENTRY: rooms/rendered/TEST_ENTRY.txt has 2 exits; world/test/world_test.txt has 1 connection slot');
 if(path.startsWith('region-package-choices')&&fixtureExportFailure==='regionChoices')throw Error('Region PL: world/pl/world_pl.txt is missing');
 if(path==='region-package-inspect'&&fixtureExportFailure==='regionInspect')throw Error('PL_POOL: rooms/rendered/PL_POOL.txt cannot be read');
 return failureOriginalApi(path,data);
};
const failureOriginalFetch=window.fetch;
window.fetch=async(path,options)=>{
 if(path==='/api/export-room-check')return {ok:true,json:async()=>({rooms:[],assets:[],issues:[],snapshotToken:'fixture',requiresChoices:false})};
 if(path==='/api/export-project-package'){calls.push({path:'export-project-package',data:JSON.parse(options.body)});return {ok:true,json:async()=>({url:'#fixture-project',connectionsPending:fixturePendingExport})};}
 if(path==='/api/project-package-inspect')return {ok:true,json:async()=>({kind:'project-bundle',collisions:[]})};
 if(path==='/api/import-project-package')return {ok:true,json:async()=>({ok:true,project:{projectId:'imported',name:'Imported'},connectionsPending:true})};
 return failureOriginalFetch(path,options);
};
function notice(value){fixtureNotice=value;}
async function listProjects(){}
async function changeProject(next){const incoming=await next();if(incoming){project=incoming;notice('');}}
function choose(extensions,callback){return callback({name:'fixture.zip'});}
(async()=>{
 let checks=0;const assert=(value,message)=>{checks++;if(!value)throw Error(message);};
 try{
  await MI18n.ready;await $('export').onclick();
  assert($('pack-status').textContent.includes('TEST_ENTRY')&&$('pack-status').textContent.includes('world/test/world_test.txt'),'Room failure lost its room and file');
  assert(!$('pack-build').disabled,'Room failure permanently disabled retry');
  assert(!$('export-matchedRooms').children.length,'Room failure retained old matched rooms');
  fixtureExportFailure='';await $('pack-build').onclick();
  assert($('export-matchedRooms').children.length===2,'Retry did not reload room choices');
  assert(!$('pack-status').textContent.includes('world_test.txt'),'Retry retained a resolved failure');
  await $('pack-build').onclick();
  assert(downloads.some(url=>url.endsWith('#fixture-project')),'Pending connections prevented editable project export');
  assert($('pack-status').textContent.includes(MI18n.t('export.connectionsPending')),'Pending connections were hidden after export');
  fixtureExportFailure='regionChoices';await pick(document.querySelector('[name=exportScope][value=region]'));
  assert($('pack-status').textContent.includes('world/pl/world_pl.txt'),'Region catalog failure lost its source');
  assert(!$('pack-build').disabled,'Region catalog failure cannot be retried');
  fixtureExportFailure='regionInspect';await $('pack-build').onclick();
  assert($('pack-status').textContent.includes('PL_POOL')&&$('pack-status').textContent.includes('PL_POOL.txt'),'Region inspection failure was replaced with a generic message');
  fixtureExportFailure='';await $('pack-build').onclick();
  assert(!$('pack-status').textContent.includes('PL_POOL.txt'),'Resolved region error remained visible');
  const imported=await MIProjectPackageImport(new Blob(['fixture']),result=>fixtureImportResult=result);
  assert(imported.projectId==='imported'&&fixtureImportResult.connectionsPending===true,'Import dropped the pending connection state');
  assert(!Object.hasOwn(imported,'connectionsPending'),'Import injected status metadata into the authored project');
  await $('import').onclick();
  assert(project.projectId==='imported'&&fixtureNotice===MI18n.t('import.connectionsPending'),'Loading the imported project erased the pending-state notice');
  assert(!errors.length,'Unexpected frontend errors: '+errors.join('\n'));
  $('result').textContent=JSON.stringify({ok:true,checks});
 }catch(error){$('result').textContent=JSON.stringify({ok:false,checks,error:error.stack,errors});}
})();
