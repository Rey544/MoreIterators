/* Shared, in-flow version entry. Version data comes from the local server. */
'use strict';
(()=>{
 if(window.MIStudioAbout)return;
 let footer,button,community,principles,dialog,heading,body,closeButton,data,pending,state='loading';
 const fallback={title:['版本与更新','Version and updates'],brand:['更多迭代器','More Iterators'],latest:['最近更新','Latest update'],history:['历史更新','Earlier updates'],thanks:['感谢测试与协助','Thanks for testing and assistance'],loading:['正在读取版本…','Loading version…'],failed:['无法读取版本信息，请稍后重试。','Version information is unavailable. Try again shortly.'],close:['关闭','Close'],development:['开发版','Development build'],planned:['正式首发 {version}：待发布','First release {version}: not published'],empty:['暂无更新记录','No update notes available']};
 const locale=()=>window.MI18n?.locale==='en'?'en':'zh-CN';
 function tr(key,params={}){let value=window.MI18n?.t('about.'+key,params);if(!value||value==='about.'+key)value=fallback[key][locale()==='en'?1:0];return value.replace(/\{(\w+)\}/g,(_,name)=>String(params[name]??''));}
 function node(tag,text,className){const element=document.createElement(tag);if(text!==undefined)element.textContent=text;if(className)element.className=className;return element;}
 function authored(element){if(window.MI18n)MI18n.content(element);else element.setAttribute('translate','no');return element;}
 function safeLink(value,host){try{const url=new URL(value);return url.protocol==='https:'&&host.test(url.hostname)?url.href:null;}catch{return null;}}
 function updateEntry(){
  if(!button)return;button.textContent=data?tr('brand')+' '+data.version:tr('title');button.title=tr('title');button.setAttribute('aria-label',tr('title')+(data?' '+data.version:''));
  const english=locale()==='en';
  community.replaceChildren();
  const url=safeLink(data?.community?.discordUrl,/^(discord\.gg|discord\.com)$/i);
  if(url){
   const link=authored(node('a',undefined,'mi-discord-link'));link.href=url;link.target='_blank';link.rel='noopener noreferrer';link.title='Discord';link.setAttribute('aria-label','Discord');
   const icon=node('span',undefined,'mi-discord-icon');icon.setAttribute('aria-hidden','true');link.append(icon);community.append(link);
  }
  const intro=english?'MoreIterators is a completely free, open-source OC creation tool for creators with no coding experience.':'MoreIterators 是完全免费、开源的 OC 制作工具，希望帮助没有编程基础的创作者实现自己的想法。';
  const source=english?'If someone charges you to provide or install this tool, please subscribe to the official version for free on Steam Workshop and notify the creator.':'如果有人收费提供或代装本工具，请到 Steam 创意工坊免费订阅官方版本，并告知创作者。';
  const request=english?'We ask that you avoid using this tool to offer paid OC creation commissions.':'不建议将基于本工具的 OC 制作作为有偿约稿服务出售。';
  principles.replaceChildren(node('p',intro),node('p',source),node('p',request));
  const workshop=safeLink(data?.community?.workshopUrl,/^steamcommunity\.com$/i);
  if(workshop){const link=node('a',english?'Official Workshop page':'官方创意工坊页面');link.href=workshop;link.target='_blank';link.rel='noopener noreferrer';principles.append(link);}
 }
 function readPayload(payload){
  const version=typeof payload.version==='string'?payload.version:payload.version?.version;
  if(typeof version!=='string'||!/^\d+\.\d+\.\d+(?:-[a-zA-Z0-9.-]+)?$/.test(version))throw Error('Invalid version response');
  const changelog=payload.changelog&&typeof payload.changelog==='object'?payload.changelog:{};
  const community=payload.community&&typeof payload.community==='object'?payload.community:{};
  return {version,changelog,community};
 }
 async function refresh(){
  if(pending)return pending;
  pending=(async()=>{const response=await fetch('/api/version',{cache:'no-store'});if(!response.ok)throw Error('Version HTTP '+response.status);data=readPayload(await response.json());updateEntry();return data;})();
  try{return await pending;}finally{pending=null;}
 }
 function entry(value){
  const section=authored(node('section',undefined,'mi-about-release'));
  section.append(node('h4',String(value.version||'')));
  const lines=value.changes?.[locale()]||value.changes?.['zh-CN']||[],list=node('ul');
  for(const line of lines)if(typeof line==='string')list.append(node('li',line));
  section.append(list);return section;
 }
 function render(){
  if(!dialog||!data)return;const scroll=body.scrollTop||0;
  state='ready';
  heading.textContent=tr('title');closeButton.textContent=tr('close');body.replaceChildren();
  const version=authored(node('p',tr('brand')+' '+data.version,'mi-about-version'));
  if(data.version.includes('-'))version.append(node('span',tr('development'),'mi-about-build'));
  body.append(version);
  const planned=data.changelog.plannedRelease;
  if(typeof planned==='string'&&data.version.startsWith(planned+'-'))body.append(node('p',tr('planned',{version:planned}),'mi-about-pending'));
  const entries=Array.isArray(data.changelog.entries)?data.changelog.entries:[],first=entries[0];
  body.append(node('h3',tr('latest')));
  body.append(first?entry(first):node('p',tr('empty'),'mi-about-empty'));
  body.append(node('h3',tr('thanks')));
  const names=Array.isArray(data.changelog.thanks)?data.changelog.thanks:[];
  body.append(authored(node('p',names.filter(name=>typeof name==='string').map(name=>name==='匿名测试者'?(locale()==='en'?'Anonymous Tester':'匿名测试者'):name).join(' · '),'mi-about-thanks')));
  if(entries.length>1){body.append(node('h3',tr('history')));for(const previous of entries.slice(1))body.append(entry(previous));}
  body.scrollTop=scroll;
 }
 function makeDialog(){
  if(dialog)return;
  dialog=node('dialog',undefined,'mi-about');dialog.id='miStudioAbout';dialog.setAttribute('aria-labelledby','miStudioAboutTitle');
  const head=node('div',undefined,'mi-about-heading');heading=node('h2',tr('title'));heading.id='miStudioAboutTitle';head.append(heading);
  body=node('div',undefined,'mi-about-body');body.tabIndex=0;body.setAttribute('role','region');body.setAttribute('aria-label',tr('title'));
  const actions=node('div',undefined,'mi-about-actions');closeButton=node('button',tr('close'));closeButton.type='button';closeButton.onclick=()=>dialog.close();actions.append(closeButton);
  dialog.append(head,body,actions);dialog.addEventListener('cancel',event=>{event.preventDefault();dialog.close();});document.body.append(dialog);
 }
 async function open(){
  makeDialog();if(!dialog.open)dialog.showModal();heading.textContent=tr('title');closeButton.textContent=tr('close');
  state='loading';
  body.replaceChildren(node('p',tr('loading'),'mi-about-state'));
  try{await refresh();render();}catch(error){state='failed';body.replaceChildren(node('p',tr('failed'),'mi-about-state'));console.warn('[MI version]',error);}
 }
 async function mount(){
  if(window.MI18n)await MI18n.ready;if(document.getElementById('miVersionFooter'))return;
  footer=node('footer',undefined,'mi-version-footer');footer.id='miVersionFooter';button=authored(node('button',tr('title'),'mi-version-link'));button.type='button';button.onclick=open;
  const row=node('div',undefined,'mi-footer-row');community=authored(node('div',undefined,'mi-community'));principles=authored(node('div',undefined,'mi-tool-principles'));row.append(button,community);footer.append(principles,row);document.body.append(footer);updateEntry();
  refresh().catch(()=>{});
 }
 window.MIStudioAbout={open,refresh};
 window.addEventListener('mi-language-change',()=>{updateEntry();if(body)body.setAttribute('aria-label',tr('title'));if(dialog?.open){if(state==='ready')render();else{heading.textContent=tr('title');closeButton.textContent=tr('close');body.replaceChildren(node('p',tr(state),'mi-about-state'));}}});
 window.addEventListener('focus',()=>{if(button)refresh().catch(()=>{});});
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount,{once:true});else mount();
})();
