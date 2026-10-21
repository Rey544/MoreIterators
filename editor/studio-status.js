'use strict';
document.addEventListener('DOMContentLoaded',()=>{
 const nodes=document.querySelectorAll('#saveState,#notice,#status,#overseerState');
 const update=node=>{
  const state=node.dataset.state||'',text=node.textContent||'';
  const failed=node.dataset.kind==='error'||node.getAttribute('role')==='alert'||node.classList.contains('error')||/失败|错误|冲突|failed|error|conflict/i.test(text);
  const unsaved=!failed&&(/^(unsaved|dirty)$/.test(state)||/^(有未保存修改|尚未保存|未保存修改|Unsaved changes|Not saved)(\s|[·：:]|$)/i.test(text.trim()));
  if(node.classList.contains('mi-unsaved')!==unsaved)node.classList.toggle('mi-unsaved',unsaved);
 };
 for(const node of nodes){update(node);new MutationObserver(()=>update(node)).observe(node,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['data-state','data-kind','role','class']});}
});
