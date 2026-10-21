"use strict";
// Normalize immediately; language resources may finish after the page is usable.
(()=>{
  const header=document.querySelector('body.mi-studio>header');if(!header||header.dataset.chromeReady)return;
  const pages=[['/','外观调整'],['/dialogue','对话编辑'],['/pearls','珍珠文本'],['/broadcasts','广播编辑'],['/projections','投影编辑'],['/rooms','区域连接']];
  const brand=header.querySelector('.studio-brand,.studio-title,strong');
  if(brand){const title=brand.querySelector('strong')||brand;title.textContent=pages.find(([path])=>path===location.pathname)?.[1]||title.textContent;for(const icon of brand.querySelectorAll('.pearl-mark,.studio-icon,[aria-hidden=true]'))icon.remove();}
  const menus=[...header.querySelectorAll('details')];
  const menu=header.querySelector('#otherStudios,#moreMenu')||menus[0]||document.createElement('details');
  const buttons=[...header.querySelectorAll('button')].filter(node=>!['save','apply','dialogueEditor'].includes(node.id));
  const links=[...header.querySelectorAll('a')],dialogue=header.querySelector('#dialogueEditor');
  const language=header.querySelector('.mi-language-choice');
  const left=document.createElement('div');left.className='mi-topbar-left';
  const right=document.createElement('div');right.className='mi-topbar-actions';
  if(brand)left.append(brand);
  const contexts=header.querySelectorAll('.collection-choice,.current-pearl,.project-choice');
  if(contexts.length)for(const context of contexts)left.append(context);
  else {const choice=header.querySelector('#projects,#saved');if(choice)left.append(choice);}
  for(const id of ['collectionActive','saveState','save','apply']){const node=header.querySelector('#'+id);if(node)right.append(node);}
  const summary=document.createElement('summary');summary.textContent='⋯';summary.setAttribute('aria-label','更多操作');
  const content=document.createElement('div');content.className='mi-topbar-menu-content';
  const operations=document.createElement('div');operations.className='mi-menu-operations';
  if(window.MIUndo)for(const [id,label,direction] of [['editorUndo','撤销编辑（Ctrl+Z）',-1],['editorRedo','重做编辑（Ctrl+Shift+Z / Ctrl+Y）',1]]){const item=document.createElement('button');item.id=id;item.type='button';item.textContent=label;item.disabled=true;item.onclick=()=>MIUndo.step(direction);operations.append(item);}
  for(const button of buttons)operations.append(button);
  content.append(operations);
  const navigation=document.createElement('nav');navigation.className='mi-menu-links';navigation.setAttribute('aria-label','切换页面');
  for(const [path,label] of pages){
    const link=path==='/dialogue'&&dialogue?dialogue:links.find(node=>new URL(node.href,location.href).pathname===path)||document.createElement('a');
    link.textContent=label;link.dataset.studioDestination=path;
    if(link.tagName==='A')link.href=path;
    if(path===location.pathname){link.classList.add('current-page');link.setAttribute('aria-current','page');}
    navigation.append(link);
  }
  const voice=document.createElement('a');voice.id='voiceEditorLink';voice.href='/#iteratorVoice';voice.textContent='无印记声线';voice.dataset.studioDestination='/';navigation.append(voice);
  for(const link of links)if(!navigation.contains(link))navigation.append(link);
  content.append(navigation);if(language)content.append(language);
  menu.replaceChildren(summary,content);menu.className='mi-topbar-menu';menu.open=false;
  right.append(menu);header.replaceChildren(left,right);header.classList.add('mi-topbar');header.dataset.chromeReady='true';
  for(const old of menus)if(old!==menu){old.replaceChildren();old.hidden=true;header.append(old);}
  function updateTargets(){
    const query=new URLSearchParams(location.search);
    const projectId=window.MIStudioPage?.projectId?.()||document.querySelector('#projects')?.value||query.get('project')||query.get('projectId')||query.get('id')||'';
    for(const link of navigation.querySelectorAll('a[data-studio-destination]')){
      const url=new URL(link.dataset.studioDestination,location.href);
      if(projectId)url.searchParams.set(url.pathname==='/dialogue'?'id':'project',projectId);
      url.searchParams.set('lang',window.MI18n?.locale||query.get('lang')||'zh-CN');
      if(link.id==='voiceEditorLink')url.hash='iteratorVoice';link.href=url;
    }
  }
  menu.addEventListener('toggle',()=>{if(menu.open)updateTargets();});
  menu.addEventListener('click',event=>{if(event.target.closest('button,a'))menu.open=false;});
  document.addEventListener('click',event=>{if(!menu.contains(event.target))menu.open=false;});
  document.addEventListener('keydown',event=>{if(event.key==='Escape'&&menu.open){menu.open=false;summary.focus();}});
  window.addEventListener('mi-language-change',updateTargets);
  window.MI18n?.ready.then(()=>{
    const choice=header.querySelector('.mi-language-choice');if(choice)content.append(choice);
    for(const button of header.querySelectorAll(':scope>button'))operations.append(button);
    MI18n.scan(header);updateTargets();
  });
})();
