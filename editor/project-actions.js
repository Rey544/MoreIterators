"use strict";
// Loaded after app.js. All existing authoring state remains owned by that page.
window.MIProjectActions=(()=>{
  const t=(key,values={})=>MI18n.t('project.lifecycle.'+key,values);
  let busy=false,unavailable=false,blockedAfterContent=false,lastIdentity='';
  const unavailableMessage=()=>blockedAfterContent?MI18n.t('project.manage.reloadAfterChange'):t('reloadAfterDelete');
  function announce(){if(typeof BroadcastChannel!=='undefined'){const channel=new BroadcastChannel('mi-project-lifecycle');channel.postMessage({type:'changed'});channel.close();}}
  const current=()=>typeof project==='undefined'?null:project;
  function fixed(value){return !!value&&(!!value.fixedProject||!!value.legacyOracle||(typeof projects!=='undefined'&&projects.some(p=>p.projectId===value.projectId&&p.fixedProject)));}
  function refresh(){const p=current(),pageBusy=window.MIStudioPage?.isBusy?.(),button=document.getElementById('deleteProject');if(button){button.textContent=t('delete');button.disabled=busy||unavailable||pageBusy||!p||fixed(p);button.title=p&&fixed(p)?t('fixed'):'';}const recent=document.getElementById('recentlyDeleted');if(recent){recent.textContent=t('recent');recent.disabled=busy||unavailable||pageBusy;}}
  async function perform(operation){if(busy||unavailable)return;const main=document.querySelector('main'),wasInert=main.inert;busy=true;main.inert=true;syncProjectControls();try{await operation();}catch(error){notice(unavailable?unavailableMessage():error.message,true);if(dialog?.open){const message=node('p','project-manage-error',error.message);message.setAttribute('role','alert');host.append(message);}console.error(error);}finally{busy=false;main.inert=wasInert||unavailable;syncProjectControls();}}
  // A committed deletion must stay unavailable until a different document loads.
  async function afterDelete(p){
    const id=p.projectId;blockedAfterContent=false;unavailable=true;announce();
    projects=projects.filter(item=>item.projectId!==id);
    let refreshError;
    try{await listProjects();}catch(error){refreshError=error;}
    if(current()?.projectId===id){
      const next=projects.find(item=>item.projectId!==id);
      if(next){try{await load(next);}catch(error){refreshError=refreshError||error;await load(await newProject());}}
      else await load(await newProject());
    }
    if(!current()?.projectId||current().projectId===id)throw Error(unavailableMessage());
    unavailable=false;
    notice(t('deleted',{name:p.name})+(refreshError?' '+refreshError.message:''),!!refreshError);
  }
  async function reloadAfterChange(){
    const id=current()?.projectId;blockedAfterContent=true;unavailable=true;syncProjectControls();
    await listProjects();const active=projects.find(item=>item.projectId===id);
    if(!active||await load(active)===false||current()?.projectId!==id)throw Error(unavailableMessage());
    unavailable=false;blockedAfterContent=false;
  }
  async function remove(){
    const p=current();if(!p||fixed(p)||window.MIStudioPage?.isBusy?.())return;
    await manage({projectId:p.projectId},JSON.parse(JSON.stringify(serialize())));
  }
  let manager,form,state;
  const mt=(key,values={})=>MI18n.t('project.manage.'+key,values);
  function node(tag,className,text){const item=document.createElement(tag);if(className)item.className=className;if(text!==undefined)item.textContent=text;return item;}
  function content(tag,className,text){const item=node(tag,className,text);MI18n.content(item);return item;}
  function button(text,action,className){const item=node('button',className,text);item.type='button';item.onclick=action;return item;}
  function translated(text){return MI18n.text?MI18n.text(String(text||'')):String(text||'');}
  function itemLabel(item){return ['appearance','dialogue','overseer','rooms','projectionSettings'].includes(item.type)?translated(item.label):String(item.label||'');}
  function makeManager(){
    if(manager)return;
    manager=node('dialog','project-manage-dialog');manager.id='projectManageDialog';manager.setAttribute('aria-labelledby','projectManageTitle');
    manager.addEventListener('cancel',event=>{if(busy)event.preventDefault();});
    manager.addEventListener('close',()=>{state=null;syncProjectControls();});
    form=node('div','project-manage-form');manager.append(form);document.body.append(manager);
  }
  async function manage(source,draft){
    if(busy||unavailable)return;
    makeManager();
    await perform(async()=>{
      if(source.token&&typeof dirty!=='undefined'&&dirty)await save();
      const result=await api('project-associations',{source,...(draft?{project:draft}:{})});
      state={inspection:result,source:result.source,draft,deleteProject:!result.source.archived,choices:new Map(result.items.map(item=>[item.id,'keep'])),selected:new Set(),replaceIds:new Set(),targetProjectId:'',plan:null,error:''};
      dialog?.close();renderManager();manager.showModal();
    });
    refresh();
  }
  function changedPlan(){if(!state)return;state.plan=null;state.replaceIds.clear();state.error='';renderManager();}
  function choice(item,action){state.choices.set(item.id,action);changedPlan();}
  function bulk(action){for(const item of state.inspection.items)if(state.selected.has(item.id)&&item.allowedActions.includes(action))state.choices.set(item.id,action);changedPlan();}
  function request(){return {source:state.source,snapshot:state.inspection.snapshot,...(state.draft?{project:state.draft}:{}),deleteProject:state.deleteProject,choices:[...state.choices].map(([id,action])=>({id,action})),targetProjectId:state.targetProjectId,replaceIds:[...state.replaceIds]};}
  async function manageTask(operation){
    if(busy||!state)return;
    await perform(async()=>{manager.inert=true;try{await operation();}catch(error){if(state){state.error=error.message;state.plan=null;}throw error;}finally{manager.inert=false;if(state)renderManager();}});
  }
  async function preview(){
    await manageTask(async()=>{
      if([...state.choices.values()].includes('move')&&!state.targetProjectId)throw Error(mt('chooseTarget'));
      state.error='';const payload=request();state.plan=null;state.plan=await api('project-associations-plan',payload);
    });
  }
  async function applyPlan(){
    if(!state?.plan?.canApply||!state.plan.planToken)return;
    await manageTask(async()=>{
      const source=state.source,result=await api('project-associations-apply',{planToken:state.plan.planToken});
      // Close before refreshing author state, which may fail independently of the
      // already committed server transaction.
      manager.close();announce();
      if(result.deletedProject)await afterDelete(source);
      else{
        await reloadAfterChange();
        notice(mt(result.requiresApply?'completed':'updated'));
      }
    });
  }
  function renderManager(){
    if(!state)return;
    const focusId=document.activeElement?.id;form.replaceChildren();const info=state.inspection;
    const heading=node('div','project-manage-heading'),title=node('h2','',mt(state.source.archived?'archivedTitle':'title'));title.id='projectManageTitle';
    heading.append(title,button(t('close'),()=>manager.close(),'project-manage-close'));
    const identity=content('p','project-manage-identity',state.source.name+' ('+state.source.projectId+')');form.append(heading,identity);
    if(!state.source.archived){
      const label=node('label','project-manage-delete'),check=node('input');check.type='checkbox';check.id='manageDeleteProject';check.checked=state.deleteProject;
      check.onchange=()=>{state.deleteProject=check.checked;changedPlan();};label.append(check,node('span','',mt('deleteProject')));form.append(label);
    }
    for(const text of info.notes||[])form.append(node('p','project-manage-note',translated(text)));
    const controls=node('div','project-manage-tools'),selectLabel=node('label','project-manage-all'),all=node('input');all.type='checkbox';all.id='manageSelectAll';
    const selectable=info.items.filter(item=>item.allowedActions.length>1);all.checked=!!selectable.length&&selectable.every(item=>state.selected.has(item.id));all.indeterminate=state.selected.size>0&&!all.checked;
    all.onchange=()=>{state.selected=new Set(all.checked?selectable.map(item=>item.id):[]);renderManager();};selectLabel.append(all,node('span','',mt('selectAll')));controls.append(selectLabel);
    for(const action of ['keep','delete','move']){const command=button(mt('bulk'+action[0].toUpperCase()+action.slice(1)),()=>bulk(action));command.disabled=!info.items.some(item=>state.selected.has(item.id)&&item.allowedActions.includes(action));command.dataset.action=action;command.id='manageBulk_'+action;controls.append(command);}
    form.append(controls);
    const list=node('div','project-manage-items');
    for(const item of info.items){
      const row=node('div','project-manage-item');row.dataset.item=item.id;
      const check=node('input');check.type='checkbox';check.id='manageSelect_'+item.id;check.checked=state.selected.has(item.id);check.disabled=item.allowedActions.length<=1;check.setAttribute('aria-label',mt('selectItem',{name:itemLabel(item)}));
      check.onchange=()=>{if(check.checked)state.selected.add(item.id);else state.selected.delete(item.id);renderManager();};
      const text=node('div','project-manage-item-text');text.append(content('strong','',(['reader','spawn','projection'].includes(item.type)?mt('kind.'+item.type)+': ':'')+itemLabel(item)));if(item.detail)text.append(node('span','project-manage-item-detail',translated(item.detail)));if(item.shared)text.append(node('span','project-manage-shared',mt('sharedAssociation')));
      const action=node('select');action.id='manageAction_'+item.id;action.setAttribute('aria-label',mt('itemAction',{name:itemLabel(item)}));action.dataset.itemAction=item.id;
      for(const name of item.allowedActions){const option=node('option','',mt(name));option.value=name;action.append(option);}action.value=state.choices.get(item.id);action.disabled=item.allowedActions.length<=1;action.onchange=()=>choice(item,action.value);
      row.append(check,text,action);list.append(row);
    }
    if(!info.items.length)list.append(node('p','',mt('noContent')));form.append(list);
    const moving=[...state.choices.values()].includes('move'),targetLabel=node('label','project-manage-target'),target=node('select');target.id='manageTarget';target.disabled=!moving;
    const empty=node('option','',mt('chooseTarget'));empty.value='';target.append(empty);
    for(const entry of info.targets){const option=content('option','',entry.name+' ('+entry.projectId+')');option.value=entry.projectId;target.append(option);}target.value=state.targetProjectId;target.onchange=()=>{state.targetProjectId=target.value;changedPlan();};
    targetLabel.append(node('span','',mt('target')),target);form.append(targetLabel);
    if(state.plan){
      const previewArea=node('section','project-manage-preview');previewArea.setAttribute('aria-live','polite');previewArea.append(node('h3','',mt('previewTitle')));
      const summary=node('ul');for(const item of state.plan.summary||[])summary.append(node('li','',translated(item)));previewArea.append(summary);
      const conflicts=state.plan.conflicts||[];
      if(conflicts.length){previewArea.append(node('h3','project-manage-conflict-title',mt('conflicts')));for(const conflict of conflicts){const label=node('label','project-manage-conflict');if(conflict.canReplace){const check=node('input');check.type='checkbox';check.id='manageReplace_'+conflict.id;check.checked=state.replaceIds.has(conflict.id);check.onchange=()=>{if(check.checked)state.replaceIds.add(conflict.id);else state.replaceIds.delete(conflict.id);state.plan.canApply=false;renderManager();};label.append(check);}label.append(node('span','',translated(conflict.message)+(conflict.canReplace?' '+mt('replaceExplicit'):'')));previewArea.append(label);}}
      form.append(previewArea);
    }
    if(state.error){const error=node('p','project-manage-error',state.error);error.setAttribute('role','alert');form.append(error);}
    const footer=node('div','project-manage-footer');const inspect=button(mt(state.plan?'updatePreview':'preview'),preview);inspect.id='managePreview';
    const apply=button(mt('execute'),applyPlan,'danger');apply.id='manageApply';apply.disabled=!state.plan?.canApply||!state.plan?.planToken;
    footer.append(inspect,apply);form.append(footer);if(focusId)document.getElementById(focusId)?.focus?.({preventScroll:true});
  }
  let dialog,host,recentEntries=[],recentOperations=[];
  function makeDialog(){
    if(dialog)return;
    dialog=node('dialog','project-trash-dialog');dialog.style.cssText='max-width:min(720px,90vw);max-height:80vh;overflow:auto';
    host=node('div','project-trash-list');dialog.append(host);document.body.append(dialog);
    dialog.addEventListener('cancel',event=>{if(busy)event.preventDefault();});
    dialog.addEventListener('close',()=>syncProjectControls());
  }
  function renderRecent(){
    host.replaceChildren();host.append(node('h2','',t('recent')));
    if(!recentEntries.length)host.append(node('p','',t('empty')));
    for(const entry of recentEntries){
      const row=node('div','project-trash-row'),label=content('span','project-trash-name',entry.name+' ('+entry.projectId+')');
      const restore=button(t('restore'),()=>perform(async()=>{
        if(typeof dirty!=='undefined'&&dirty)await save();
        const result=await api('project-restore',{token:entry.token});announce();await listProjects();await load(result.project);dialog.close();notice(t('restored',{name:result.project.name}));
      }));
      const manageRelated=button(mt('manageRelated'),()=>manage({token:entry.token}));row.append(label,manageRelated,restore);host.append(row);
    }
    if(recentOperations.length){
      host.append(node('h3','',mt('operationHistory')));
      for(const operation of recentOperations){
        const row=node('div','project-trash-row'),label=node('span','project-trash-name'),target=typeof projects!=='undefined'&&projects.find(item=>item.projectId===operation.targetProjectId);
        label.append(content('span','',operation.sourceName+' ('+operation.sourceProjectId+')'+(operation.targetProjectId?' → '+(target?.name||operation.targetProjectId):'')));
        const when=new Date(operation.createdAt);if(!Number.isNaN(when.getTime()))label.append(node('small','',when.toLocaleString(MI18n.locale)));
        const undo=button(mt('undoOperation'),()=>perform(async()=>{
          if(typeof dirty!=='undefined'&&dirty)await save();
          await api('project-associations-restore',{operationToken:operation.token});announce();await reloadAfterChange();
          dialog.close();notice(mt('operationRestored'));
        }));row.append(label,undo);host.append(row);
      }
    }
    host.append(button(t('close'),()=>dialog.close()));
  }
  async function recent(){
    makeDialog();await perform(async()=>{
      [recentEntries,recentOperations]=await Promise.all([api('project-trash'),api('project-association-operations')]);renderRecent();
      if(!dialog.open)dialog.showModal();
    });
  }
  function install(){document.getElementById('deleteProject')?.addEventListener('click',remove);document.getElementById('recentlyDeleted')?.addEventListener('click',recent);refresh();}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install,{once:true});else install();
  // Project selection is asynchronous; this updates availability without changing
  // app.js or replacing its load/save handlers.
  setInterval(()=>{const p=current(),identity=(p?.projectId||'')+':'+fixed(p);if(identity!==lastIdentity){lastIdentity=identity;refresh();}},500);
  window.addEventListener('mi-language-change',()=>{refresh();if(unavailable)notice(unavailableMessage(),true);if(state)renderManager();if(dialog?.open)renderRecent();});
  return {refresh,remove,recent,get busy(){return busy||unavailable||!!manager?.open||!!dialog?.open;},get unavailable(){return unavailable;},get unavailableMessage(){return unavailableMessage();}};
})();
