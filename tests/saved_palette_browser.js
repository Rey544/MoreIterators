const paletteOriginalApi=api,paletteOriginalFetch=window.fetch;
let paletteExported=[];
api=async(path,data)=>{
 if(path==='region-package-inspect')return {ok:true,rooms:['DEMO_ROOM'],projectIds:[],dependencies:[],blockers:[]};
 return paletteOriginalApi(path,data);
};
window.fetch=async(path,options)=>{
 if(path==='/api/export-room-check'){
  const data=JSON.parse(options.body),owners=data.scope==='region'?[]:data.projects;
  return {ok:true,json:async()=>({snapshotToken:'palette-fixture',rooms:[],issues:[],parameterConflicts:[],requiresChoices:true,assets:[{key:'palettes/palette26.png',relative:'palettes/palette26.png',projectIds:owners,versions:[{id:'asset-base',origin:'game',complete:true},{id:'asset-saved',origin:'palette_output',complete:true}]}]})};
 }
 if(path==='/api/export-project-package'||path==='/api/export-region-package'){
  paletteExported.push({path,data:JSON.parse(options.body)});
  return {ok:true,json:async()=>({url:'#palette-export'})};
 }
 return paletteOriginalFetch(path,options);
};
(async()=>{
 let checks=0;const assert=(value,message)=>{checks++;if(!value)throw Error(message);};
 try{
  await MI18n.ready;
  for(const mode of ['project','region']){
   if($('exportDialog').open)$('exportDialog').close();
   await $('export').onclick();
   if(mode==='region')await pick(document.querySelector('[name=exportScope][value=region]'));
   const before=paletteExported.length;
   await $('pack-build').onclick();
   assert(paletteExported.length===before,'Export chose a palette without author input');
   const input=$('export-roomVersions').querySelector('[data-asset="palettes/palette26.png"][value="asset-saved"]');
   assert(input&&!input.disabled&&!$('export-roomVersions').hidden,'Saved palette choice is inaccessible');
   assert(input.parentElement.textContent.includes(MI18n.t('export.roomVersion.savedPalette')),'Saved palette source label is missing');
   assert(!project.editor?.externalRoomTools,'Fixture unexpectedly enables external room tools');
   await pick(input);await $('pack-build').onclick();
   const output=paletteExported.at(-1);
   assert(paletteExported.length===before+1&&output.data.roomSourceChoices.assetChoices['palettes/palette26.png']==='asset-saved','Selected palette was omitted from export');
   if(mode==='region')assert(output.data.projects.length===0,'Region-only palette choice invents an MI project');
  }
  assert(!errors.length,'UI errors: '+errors.join('\n'));
  $('result').textContent=JSON.stringify({ok:true,checks});
 }catch(error){$('result').textContent=JSON.stringify({ok:false,checks,error:error.stack,errors});}
})();
