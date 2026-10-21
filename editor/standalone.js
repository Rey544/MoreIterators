'use strict';
(()=>{
 const byId=id=>document.getElementById(id);let cover='',options,building=false;
 byId('roomStudio').onclick=()=>{byId('roomStudio').href='/rooms?project='+encodeURIComponent(project?.projectId||'')+'&lang='+MI18n.locale;};
 function label(text,node){const l=document.createElement('label');l.append(node,document.createTextNode(text));return l;}
 function selectedIds(){return [...byId('pack-projects').querySelectorAll('input:checked')].map(c=>c.value);}
 function review(){
  let node=byId('pack-selectionSummary');if(!node){node=document.createElement('p');node.id='pack-selectionSummary';node.setAttribute('role','status');byId('pack-projects').after(node);}
  const count=selectedIds().length,includePearls=byId('pack-pearls').checked,collection=byId('pack-pearlCollection').selectedOptions[0]?.textContent||'';
  node.textContent=MI18n.t(includePearls?'export.selection_with_pearls':'export.selection_no_pearls',{count,collection});
  byId('pack-build').disabled=building||count===0||count>100||(includePearls&&!byId('pack-pearlCollection').value);
 }
 byId('openPlayableExport').onclick=run(async()=>{
  await save();const [settings,pearlProjects]=await Promise.all([api('export-settings?id='+encodeURIComponent(project.projectId)),api('pearl-projects')]);options=settings;
  byId('pack-pearlCollection').replaceChildren(...pearlProjects.projects.map(item=>{const node=MI18n.content(document.createElement('option'));node.value=item.id;node.textContent=item.name;return node;}));
  byId('pack-pearlCollection').value=pearlProjects.projects.some(item=>item.id===options.pearlCollectionId)?options.pearlCollectionId:pearlProjects.activeId;
  for(const key of ['id','name','authors','description','version'])byId('pack-'+key).value=options[key]||'';
  cover=options.cover||'';byId('pack-coverPreview').src=cover;byId('pack-coverPreview').hidden=!cover;
  for(const key of ['dialogue','pearls','broadcasts','workPearls','projections'])byId('pack-'+key).checked=key==='projections'?options[key]!==false:!!options[key];
  byId('pack-pearlCollectionField').hidden=!byId('pack-pearls').checked;
  const saved=new Set(Array.isArray(options.projects)?options.projects:[project.projectId]);
  byId('pack-projects').replaceChildren(...projects.map(p=>{const input=document.createElement('input');input.type='checkbox';input.value=p.projectId;input.checked=saved.has(p.projectId);input.onchange=review;return label(p.name,input);}));
  byId('pack-status').textContent='';review();
  byId('exportDialog').close();byId('playableExportDialog').showModal();
 });
 byId('pack-pearls').onchange=()=>{byId('pack-pearlCollectionField').hidden=!byId('pack-pearls').checked;review();};
 byId('pack-pearlCollection').onchange=review;
 byId('pack-all').onclick=()=>{byId('pack-projects').querySelectorAll('input').forEach(c=>c.checked=true);review();};
 byId('pack-none').onclick=()=>{byId('pack-projects').querySelectorAll('input').forEach(c=>c.checked=false);review();};
 byId('pack-cover').onchange=run(async()=>{const file=byId('pack-cover').files[0];if(!file)return;if(file.size>8000000)throw Error('封面最大 8 MB');cover=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result);r.onerror=reject;r.readAsDataURL(file);});byId('pack-coverPreview').src=cover;byId('pack-coverPreview').hidden=false;});
 byId('pack-clearCover').onclick=()=>{cover='';byId('pack-cover').value='';byId('pack-coverPreview').hidden=true;};
 byId('pack-build').onclick=run(async()=>{
  const request={cover,settingsProject:project.projectId,projects:selectedIds()};
  if(!request.projects.length||request.projects.length>100)throw Error(MI18n.t('export.choose_projects'));
  for(const key of ['id','name','authors','description','version'])request[key]=byId('pack-'+key).value;
  for(const key of ['dialogue','pearls','broadcasts','workPearls','projections'])request[key]=byId('pack-'+key).checked;
  if(request.pearls){request.pearlCollectionId=byId('pack-pearlCollection').value;if(!request.pearlCollectionId)throw Error(MI18n.t('pearl.collection.choose'));}
  const status=byId('pack-status');building=true;review();status.textContent='正在编译独立模组…';
  try{const result=await api('export-standalone',request);const a=document.createElement('a');a.href=result.url;a.download='';a.textContent='下载独立模组';status.replaceChildren(a);a.click();}
  catch(e){status.textContent=e.message;throw e;}finally{building=false;review();}
 });
})();
