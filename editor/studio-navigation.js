"use strict";
// Save authoring data before moving between studios. This never applies it to
// the game; each page owns the precise save operation and error reporting.
window.MIStudioNavigation=(()=>{
  const paths=new Set(['/','/dialogue','/pearls','/broadcasts','/projections','/rooms']);
  let navigating=false;
  const text=key=>window.MI18n?.t('studio.navigation.'+key)||key;
  function address(href){
    const url=new URL(href,location.href),page=window.MIStudioPage,owner=window.MIProjectActions?.unavailable?null:page?.projectId?.();
    if(url.origin!==location.origin||!paths.has(url.pathname))return null;
    // A failed/deleted selection has no current owner. Do not carry an old
    // project's query parameter from a previously rendered navigation link.
    for(const key of ['projectId','project','id'])url.searchParams.delete(key);
    if(owner)url.searchParams.set(url.pathname==='/dialogue'?'id':'project',owner);
    url.searchParams.set('lang',window.MI18n?.locale||'zh-CN');return url;
  }
  async function go(href,{newTab=false}={}){
    const url=address(href);if(!url||navigating)return false;
    if(window.MIProjectActions?.unavailable){window.MIStudioPage?.error?.(window.MIProjectActions.unavailableMessage);return false;}
    navigating=true;const page=window.MIStudioPage;
    for(const menu of document.querySelectorAll('header details[open]'))menu.open=false;
    const opened=newTab?window.open('about:blank','_blank'):null;if(opened)opened.opener=null;
    const wasInert=document.body.inert;document.body.inert=true;document.body.setAttribute('aria-busy','true');
    try{
      const deadline=Date.now()+30000;
      while(page?.isBusy?.()){if(Date.now()>deadline)throw Error(text('busy'));await new Promise(resolve=>setTimeout(resolve,40));}
      if(await page?.saveBeforeNavigate?.()===false)throw Error(text('incomplete'));
      const finalUrl=address(url.href)||url;
      if(opened&&!opened.closed)opened.location.replace(finalUrl.href);else location.assign(finalUrl.href);
      return true;
    }catch(error){
      if(opened&&!opened.closed)opened.close();
      if(page?.error)page.error(error.message);
      else {const notice=document.getElementById('notice');if(notice){notice.textContent=error.message;notice.hidden=false;notice.setAttribute('role','alert');}}
      return false;
    }finally{document.body.inert=wasInert;document.body.removeAttribute('aria-busy');navigating=false;}
  }
  function click(event){
    if(event.defaultPrevented||event.type==='click'&&event.button!==0||event.type==='auxclick'&&event.button!==1)return;
    const anchor=event.target.closest?.('a[href]'),button=event.target.closest?.('button#dialogueEditor');
    if(anchor?.hasAttribute('download'))return;
    const href=anchor?.href||(button?'/dialogue':null),url=href&&address(href);if(!url)return;
    if(url.pathname===location.pathname&&url.search===location.search&&url.hash)return;
    event.preventDefault();event.stopImmediatePropagation();
    void go(url.href,{newTab:event.button===1||event.ctrlKey||event.metaKey||anchor?.target==='_blank'||!!button});
  }
  document.addEventListener('click',click,true);document.addEventListener('auxclick',click,true);
  return {go,address,get busy(){return navigating;}};
})();
