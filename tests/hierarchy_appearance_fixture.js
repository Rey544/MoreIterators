const $=id=>document.getElementById(id),noop=()=>{},run=fn=>fn;
let project,target='forehead',dirtyCount=0;
const dimensions={},canvases={},canvas=(w=32,h=64)=>Object.assign(document.createElement('canvas'),{width:w,height:h}),composite=()=>canvas(),clothParts=()=>({base:canvas(),overlay:canvas()}),clothPreview=()=>canvas();
const changed=()=>{dirtyCount++;MIUndo.changed();},markDirty=changed,checkpoint=noop;
const Eyes={settings:noop},HeadSegments={settings:noop,targets:noop},AudioSettings={settings:noop};
const wardrobeSettings=noop,buildNecklaceSettings=noop,buildPearlAccessorySettings=noop;
window.fetch=async input=>{const url=new URL(input,'http://fixture.invalid');return {ok:true,json:async()=>url.pathname.startsWith('/locales/')?PEARL_CATALOGS[url.pathname.split('/').pop().replace('.json','')]:{dialogue:{first:[]}}};};
