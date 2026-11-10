(async()=>{
 let checks=0;const check=(value,message)=>{checks++;if(!value)throw Error(message);},get=id=>document.getElementById(id),change=(id,value)=>{get(id).value=value;get(id).dispatchEvent(new Event('change',{bubbles:true}));},stage=key=>get('stages').querySelector('[data-stage="'+key+'"]').click();
 try{
  await MI18n.ready;await MI18n.setLocale('zh-CN',false);await pearlWait(()=>get('readers').options.length>=1&&!get('save').disabled);selectReader(0);MIUndo.reset();
  check(get('halcyonPreview').closest('#appearancePreviewControls'),'Preview-only control remains in saved appearance parameters');
  check(!get('appearance').contains(get('halcyonPreview')),'Preview control duplicated in appearance');
  const state=get('saveState').dataset.state;get('halcyonPreview').click();MIUndo.flush();check(get('saveState').dataset.state===state&&!MIUndo.state.undo,'Preview simulation dirties saved pearl');
  change('readerAffinity','likes');check(!get('affinityVariantTools').hidden&&!get('createAffinityVariant').hidden,'Missing affinity branch cannot be authored on read stage');
  stage('leaving');check(get('readerAffinity').closest('label').hidden&&get('affinityVariantTools').hidden,'Shared leaving stage exposes private affinity');
  get('createAffinityVariant').click();MIUndo.flush();check(!MIUndo.state.undo,'Hidden create branch mutates pearl on shared stage');
  for(const key of ['returning','many']){stage(key);check(get('readerAffinity').closest('label').hidden&&get('affinityVariantTools').hidden,'Shared '+key+' exposes affinity');}
  stage('read');check(get('readerAffinity').value==='likes'&&!get('readerAffinity').closest('label').hidden,'Stage switch loses selected affinity');
  get('createAffinityVariant').click();MIUndo.flush();check(!get('removeAffinityVariant').hidden,'Create branch failed');check(await MIUndo.undo(),'Create branch undo failed');check(!get('createAffinityVariant').hidden&&get('readerAffinity').value==='likes','Undo lost branch context');check(await MIUndo.redo()&&!get('removeAffinityVariant').hidden,'Create branch redo failed');
  stage('repeat');check(get('privateRepeat').closest('#repeatOptions')&&get('preventRepeat').closest('#sharedRepeatOptions'),'Current/shared repeat settings remain mixed');check(!get('sharedRepeatOptions').hidden,'Shared repeat rule unavailable');
  MIUndo.reset();get('privateRepeat').click();MIUndo.flush();check(get('privateRepeat').checked,'Private repeat cannot be enabled');check(await MIUndo.undo()&&!get('privateRepeat').checked,'Private repeat undo failed');
  MIUndo.reset();const prevention=get('preventRepeat').checked;get('preventRepeat').click();MIUndo.flush();check(get('preventRepeat').checked!==prevention,'Shared repeat switch did not update');check(await MIUndo.undo()&&get('preventRepeat').checked===prevention,'Shared repeat undo failed');
  stage('leaving');get('removeAffinityVariant').click();check(get('removeAffinityConfirm').hidden,'Hidden remove action opens confirmation on shared stage');get('confirmRemoveAffinity').click();stage('read');check(!get('removeAffinityVariant').hidden,'Hidden confirmation removed affinity branch');
  const before=get('saveState').dataset.state;await MI18n.setLocale('en',false);await new Promise(resolve=>setTimeout(resolve,30));stage('repeat');check(get('repeatOptions').querySelector('strong').textContent==='This pearl'&&get('sharedRepeatOptions').querySelector('strong').textContent==='Shared by iterator','Scope headings untranslated');check(get('saveState').dataset.state===before,'Language switch changes saved state');
  if(get('readers').options.length>1){selectReader(1);stage('repeat');check(get('sharedRepeatOptions').hidden&&get('readerAffinity').closest('label').hidden,'Native reader exposes shared MI settings');selectReader(0);stage('repeat');}
  check(!pearlErrors.length,pearlErrors.join('\n'));check(!pearlCalls.some(call=>call.path==='/api/pearl-apply'||call.path==='/api/pearl-save'),'Hierarchy test called live/save/apply operation');
  get('result').textContent=JSON.stringify({ok:true,checks});
 }catch(error){get('result').textContent=JSON.stringify({ok:false,checks,error:error.stack,errors:pearlErrors});}
})();
