'use strict';
const $=id=>document.getElementById(id),clone=x=>JSON.parse(JSON.stringify(x));
let project,saved=[],rooms=[],geometry=null,page=0,dirty=false,generation=0,mapRect=null,saving=false,loading=false,imported=[];
const defaultStyle=()=>({font:'normal',size:1,speed:1,hold:2.5});
const newLine=()=>({text:'',color:'#ffffff',...defaultStyle()});
const speakerKey=value=>String(value||'').trim().replace(/^[【\[]+|[】\]]+$/g,'').trim().toLowerCase();
function speakerPrefix(text){const match=/^[ \t]*(?:【([^】\r\n]+)】|\[([^\]\r\n]+)\]|([^:：\r\n]+))[ \t]*[:：]/.exec(text);return match?speakerKey(match[1]||match[2]||match[3]):'';}
function speakerFor(text){const key=speakerPrefix(text);return key?project.speakers.find(s=>[s.name,...s.aliases].some(name=>speakerKey(name)===key)):null;}
function lineColor(text){return project.useCharacterColors?speakerFor(text)?.color||'#ffffff':'#ffffff';}
function normalize(value){
 const p=clone(value);if(!p.style){
  const lines=p.pages.flatMap(page=>page.lines),first=lines.find(l=>l.text.trim())||lines[0]||newLine();
  p.style=Object.fromEntries(Object.keys(defaultStyle()).map(key=>[key,first[key]??defaultStyle()[key]]));
  p.speakers=[];const seen=new Set();
  for(const line of lines){const name=speakerPrefix(line.text);if(name&&!seen.has(name)){seen.add(name);p.speakers.push({name,aliases:[],color:line.color||'#ffffff'});}}
  p.useCharacterColors=p.speakers.some(s=>s.color.toLowerCase()!=='#ffffff');
 }
 p.speakers=p.speakers||[];for(const s of p.speakers)s.aliases=s.aliases||[];return p;
}
async function api(url,value){await MI18n.ready;const r=await fetch(url,value===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(value)});const j=await r.json();if(!r.ok)throw Error(MI18n.error(j,'请求失败'));return j;}
function notice(s,error=false){$('notice').textContent=s;$('notice').dataset.kind=error?'error':'info';}
function changed(){dirty=true;notice('');renderCards();window.MIUndo?.changed();}
function guard(){return !saving&&!loading&&(!dirty||confirm('当前修改尚未保存，确定放弃并切换吗？'));}
function option(value,text){const e=document.createElement('option');e.value=value;e.textContent=text;return e;}
function field(type,value,onchange){const e=document.createElement('input');e.type=type;e.value=value;e.addEventListener('input',()=>onchange(e));return e;}
function button(text,action,title){const e=document.createElement('button');e.type='button';e.textContent=text;e.onclick=action;if(title)e.setAttribute('aria-label',title);return e;}
async function list(){saved=await api('/api/broadcasts');$('saved').replaceChildren(option('','选择已保存广播…'),...saved.map(p=>option(p.id,p.id+' · '+p.name)));if(project&&saved.some(p=>p.uid===project.uid))$('saved').value=project.id;renderCards();}
function renderCards(){
 const cards=saved.map(p=>project?.uid===p.uid?project:p);if(project&&!cards.some(p=>p.uid===project.uid))cards.push(project);
 $('broadcastList').replaceChildren(...cards.map(p=>{const b=button('',()=>{if(p.uid!==project?.uid&&guard())choose(p);});b.className='broadcast-card';b.setAttribute('aria-current',String(p.uid===project?.uid));const name=MI18n.content(document.createElement('span'));name.textContent=p.name||p.id;const id=MI18n.content(document.createElement('small'));id.textContent=p.id;b.append(name,id);return b;}));
}
function choose(p){generation++;project=normalize(p);dirty=false;page=0;render();notice('已打开 '+p.name);window.MIUndo?.reset();}
function render(){for(const k of ['id','name'])$(k).value=project[k];$('id').disabled=project.revision>0;for(const k of Object.keys(defaultStyle()))$(k).value=project.style[k];$('useCharacterColors').checked=project.useCharacterColors;renderSpeakers();renderCards();regionOptions();renderPage();loadGeometry().catch(e=>notice(e.message,true));}
function regionOptions(){const regions=[...new Set(rooms.map(r=>r.region))].sort();$('region').replaceChildren(option('','选择地区'),...regions.map(r=>option(r,r)));$('region').value=project.region;roomOptions()}
function roomOptions(){const items=rooms.filter(r=>r.region===project.region);$('room').replaceChildren(option('','选择房间'),...items.map(r=>option(r.room,r.room)));$('room').value=project.room}
async function loadGeometry(){geometry=null;drawMap();if(!project.room)return;const room=project.room,g=await api('/api/broadcast-room?room='+encodeURIComponent(room));if(project.room===room){geometry=g;drawMap()}}
function drawMap(){const c=$('map'),ctx=c.getContext('2d');ctx.clearRect(0,0,c.width,c.height);ctx.fillStyle='#111111';ctx.fillRect(0,0,c.width,c.height);$('x').value=(project.x*100).toFixed(1);$('y').value=(project.y*100).toFixed(1);mapRect=null;if(!geometry){$('position').textContent='先选择房间';return}
 const g=geometry,s=Math.min((c.width-20)/g.width,(c.height-20)/g.height),ox=(c.width-g.width*s)/2,oy=(c.height-g.height*s)/2;mapRect={s,ox,oy,w:g.width,h:g.height};ctx.fillStyle='#737373';for(const [x,y] of g.solids)ctx.fillRect(ox+x*s,oy+(g.height-y-1)*s,Math.ceil(s),Math.ceil(s));ctx.strokeStyle='#b0b0b0';ctx.lineWidth=1;ctx.setLineDash([4,3]);g.cameras.forEach(([x,y],i)=>{ctx.strokeRect(ox+x/20*s,oy+(g.height-(y+800)/20)*s,1400/20*s,800/20*s);ctx.fillStyle='#dedede';ctx.fillText(String(i+1),ox+x/20*s+3,oy+(g.height-(y+800)/20)*s+12)});
 ctx.setLineDash([]);const x=ox+project.x*g.width*s,y=oy+(1-project.y)*g.height*s;ctx.strokeStyle='white';ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(x,y-8);ctx.lineTo(x+6,y);ctx.lineTo(x,y+8);ctx.lineTo(x-6,y);ctx.closePath();ctx.stroke();const tile=[Math.floor(project.x*g.width),Math.floor(project.y*g.height)],solid=g.solids.some(p=>p[0]===tile[0]&&p[1]===tile[1]);$('position').textContent=`游戏坐标：${Math.round(project.x*g.width*20)}, ${Math.round(project.y*g.height*20)}${solid?' · 注意：当前位置在实体地形内':''}`;
}
$('map').onclick=e=>{if(!mapRect)return;const b=e.currentTarget.getBoundingClientRect(),r=mapRect;project.x=Math.max(0,Math.min(1,((e.clientX-b.left)/b.width*e.currentTarget.width-r.ox)/(r.w*r.s)));project.y=Math.max(0,Math.min(1,1-((e.clientY-b.top)/b.height*e.currentTarget.height-r.oy)/(r.h*r.s)));changed();drawMap()};

function renderSpeakers(){
 $('speakers').replaceChildren();project.speakers.forEach((speaker,index)=>{
  const row=document.createElement('div');row.className='speaker-row';
  const name=field('text',speaker.name,e=>{speaker.name=e.value;changed();refreshSpeakerBadges();preview();});name.maxLength=100;name.placeholder='角色名称';name.setAttribute('aria-label','角色名称');
  const aliases=field('text',speaker.aliases.join('、'),e=>{speaker.aliases=e.value.split(/[,，、]/).map(s=>s.trim()).filter(Boolean);changed();refreshSpeakerBadges();preview();});aliases.placeholder='别名或缩写';aliases.setAttribute('aria-label','别名或缩写');
  const color=field('color',speaker.color,e=>{speaker.color=e.value;changed();refreshSpeakerBadges();preview();});color.setAttribute('aria-label','角色颜色');
  row.append(name,aliases,color,button('×',()=>{project.speakers.splice(index,1);changed();renderSpeakers();refreshSpeakerBadges();preview();},'删除角色绑定'));$('speakers').append(row);
 });
}
function refreshSpeakerBadges(){document.querySelectorAll('.speaker-indicator').forEach((badge,i)=>{const text=project.pages[page].lines[i]?.text||'',speaker=speakerFor(text);badge.textContent=speaker?speaker.name:'';badge.style.color=lineColor(text);});}
function renderPage(){
 generation++;page=Math.max(0,Math.min(page,project.pages.length-1));$('page').replaceChildren(...project.pages.map((_,i)=>option(i,'第 '+(i+1)+' 页')));$('page').value=page;$('lines').replaceChildren();
 project.pages[page].lines.forEach((line,i)=>{
  const div=document.createElement('div');div.className='line';const text=document.createElement('textarea');text.value=line.text;text.maxLength=4000;text.placeholder='广播文本';text.setAttribute('aria-label','第 '+(i+1)+' 句');
  text.oninput=()=>{line.text=text.value;changed();refreshSpeakerBadges();preview();};div.append(text);
  const bar=document.createElement('div');bar.className='line-controls';const badge=MI18n.content(document.createElement('span'));badge.className='speaker-indicator';
  const up=button('↑',()=>moveLine(i,-1),'上移一句'),down=button('↓',()=>moveLine(i,1),'下移一句'),remove=button('删除',()=>{project.pages[page].lines.splice(i,1);changed();renderPage();});up.disabled=i===0;down.disabled=i===project.pages[page].lines.length-1;remove.disabled=project.pages[page].lines.length===1;
  bar.append(badge,up,down,remove);div.append(bar);$('lines').append(div);
 });
 $('previous').disabled=page===0;$('next').disabled=page===project.pages.length-1;$('pageUp').disabled=page===0;$('pageDown').disabled=page===project.pages.length-1;$('deletePage').disabled=project.pages.length===1;$('addPage').disabled=project.pages.length>=100;$('addLine').disabled=project.pages[page].lines.length>=100;
 refreshSpeakerBadges();preview();
}
function moveLine(i,d){const a=project.pages[page].lines,j=i+d;if(j<0||j>=a.length)return;[a[i],a[j]]=[a[j],a[i]];changed();renderPage();}
function previewLine(line){const p=MI18n.content(document.createElement('p'));p.style.color=lineColor(line.text);p.style.fontSize=(18*project.style.size)+'px';p.style.fontWeight=project.style.font==='display'?'bold':'normal';return p;}
function preview(){generation++;$('preview').replaceChildren();project.pages[page].lines.forEach(line=>{const p=previewLine(line);p.textContent=line.text.replaceAll('<LINE>','\n');$('preview').append(p);});$('playState').textContent=MI18n.t('broadcast.preview',{index:page+1,total:project.pages.length});}
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function play(){const token=++generation;for(let j=page;j<project.pages.length;j++){if(token!==generation)return;$('preview').replaceChildren();$('playState').textContent='正在播放第 '+(j+1)+' 页';for(const line of project.pages[j].lines){const el=previewLine(line);$('preview').append(el);for(const ch of Array.from(line.text.replaceAll('<LINE>','\n'))){if(token!==generation)return;el.textContent+=ch;await wait(50/project.style.speed);}await wait(project.style.hold*1000);if(token!==generation)return;}}$('playState').textContent='播放结束';}
async function save(apply){
 if(saving||loading)return false;for(const input of document.querySelectorAll('.broadcast-detail input'))if(!input.checkValidity()){input.reportValidity();return false;}
 saving=true;document.querySelector('main').inert=true;try{const r=await api('/api/broadcast-'+(apply?'apply':'save'),project);project=normalize(r.project);dirty=false;$('id').disabled=true;renderPage();await list();window.MIUndo?.rebase();notice(apply?'已保存并应用。前往 '+project.room+' 触碰网格即可播放。':'已保存 '+project.name);return true;}catch(e){notice(e.message,true);return false;}finally{saving=false;document.querySelector('main').inert=false;}
}
function importSelected(p){choose(p);dirty=true;window.MIUndo?.reset();notice('已载入，尚未保存');}
function importPayload(value){
 // RainocTool exports may contain large unrelated pictures. Only transfer the
 // broadcast and character fields required by this importer to the local API.
 if(value?.format!=='eoe-lore-project'||!Array.isArray(value.project?.documents))return value;
 const documents=value.project.documents.filter(item=>item&&['broadcast','character','slugcat','广播','角色','蛞蝓猫'].includes(item.kind||item.category)).map(item=>{
  const d=item.details,details=d&&typeof d==='object'&&!Array.isArray(d)?Object.fromEntries(['aliases','characterTags','characterColor','broadcast'].filter(k=>Object.hasOwn(d,k)).map(k=>[k,d[k]])):d;
  return {kind:item.kind,category:item.category,title:item.title,content:item.content,details};
 });
 return {format:value.format,version:value.version,project:{documents}};
}
$('new').onclick=async()=>{if(!guard())return;loading=true;try{choose(await api('/api/broadcast-default'));}catch(e){notice(e.message,true);}finally{loading=false;}};
$('newBroadcast').onclick=()=>$('new').click();$('saved').onchange=()=>{if($('saved').value&&guard())choose(saved.find(p=>p.id===$('saved').value));};
$('id').oninput=()=>{project.id=$('id').value.toUpperCase();$('id').value=project.id;changed();};$('name').oninput=()=>{project.name=$('name').value;changed();};
$('font').onchange=()=>{project.style.font=$('font').value;changed();preview();};for(const key of ['size','speed','hold'])$(key).oninput=()=>{if($(key).checkValidity()){project.style[key]=Number($(key).value);changed();preview();}};
$('useCharacterColors').onchange=()=>{project.useCharacterColors=$('useCharacterColors').checked;changed();refreshSpeakerBadges();preview();};
$('addSpeaker').onclick=()=>{if(project.speakers.length>=200)return;project.speakers.push({name:'',aliases:[],color:'#ffffff'});changed();renderSpeakers();$('speakers').lastElementChild?.querySelector('input')?.focus();};
$('region').onchange=()=>{project.region=$('region').value;project.room='';changed();roomOptions();loadGeometry();};$('room').onchange=()=>{project.room=$('room').value;changed();loadGeometry().catch(e=>notice(e.message,true));};
for(const k of ['x','y'])$(k).oninput=()=>{const v=Number($(k).value);if(Number.isFinite(v)){project[k]=Math.max(0,Math.min(1,v/100));changed();drawMap();}};
$('page').onchange=()=>{page=Number($('page').value);renderPage();};$('addPage').onclick=()=>{project.pages.push({lines:[newLine()]});page=project.pages.length-1;changed();renderPage();};
$('deletePage').onclick=()=>{if(project.pages.length>1&&confirm('删除本页及其文本？')){project.pages.splice(page,1);changed();renderPage();}};
for(const [id,d] of [['pageUp',-1],['pageDown',1]])$(id).onclick=()=>{const j=page+d;if(j<0||j>=project.pages.length)return;[project.pages[page],project.pages[j]]=[project.pages[j],project.pages[page]];page=j;changed();renderPage();};
$('addLine').onclick=()=>{project.pages[page].lines.push(newLine());changed();renderPage();};$('save').onclick=()=>save(false);$('apply').onclick=()=>save(true);$('play').onclick=play;$('stop').onclick=preview;$('previous').onclick=()=>{page--;renderPage();};$('next').onclick=()=>{page++;renderPage();};
$('refreshRooms').onclick=async()=>{try{rooms=await api('/api/broadcast-rooms?refresh=1');regionOptions();await loadGeometry();notice('已刷新房间列表');}catch(e){notice(e.message,true);}};
$('export').onclick=()=>{const blob=new Blob([JSON.stringify(project,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=project.id+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),5000);};
$('import').onclick=()=>{if(guard())$('file').click();};$('file').onchange=async()=>{if(!$('file').files.length)return;loading=true;try{const value=JSON.parse(await $('file').files[0].text()),result=await api('/api/broadcast-import',importPayload(value));imported=result.projects;if(imported.length===1)importSelected(imported[0]);else{$('importChoice').replaceChildren(...imported.map((p,i)=>option(i,p.name)));$('importPicker').showModal();}}catch(e){notice(e.message,true);}finally{$('file').value='';loading=false;}};
$('confirmImport').onclick=()=>{const selected=imported[Number($('importChoice').value)];if(selected)importSelected(selected);$('importPicker').close();};
window.MIUndo?.register({key:()=>project?.uid||'',capture:()=>{if(!project)return null;const p=clone(project);delete p.revision;delete p.runtimeId;return p;},restore:async snapshot=>{const revision=project.revision;project={...clone(snapshot),revision};changed();render();},busy:()=>saving||loading,onError:error=>notice(error.message,true)});
window.MIStudioPage={projectId:()=>new URLSearchParams(location.search).get('projectId')||new URLSearchParams(location.search).get('project'),isBusy:()=>saving||loading,saveBeforeNavigate:async()=>{if(dirty&&!await save(false))throw Error($('notice').textContent);return !dirty;},error:message=>notice(message,true)};
window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});
for(const id of ['projectionStudio','roomStudio'])$(id).onclick=event=>{const params=new URLSearchParams(location.search),owner=params.get('projectId')||params.get('project'),target=new URL(event.currentTarget.href,location.href);if(owner)target.searchParams.set('project',owner);target.searchParams.set('lang',MI18n.locale);event.currentTarget.href=target;};
(async()=>{loading=true;try{rooms=await api('/api/broadcast-rooms');await list();choose(saved[0]||await api('/api/broadcast-default'));}catch(e){notice(e.message,true);}finally{loading=false;}})();
document.addEventListener('click',event=>{for(const menu of document.querySelectorAll('.more-menu[open],.page-menu[open]'))if(!menu.contains(event.target)||event.target.closest('button,a'))menu.open=false;});
document.addEventListener('keydown',event=>{if(event.key==='Escape')for(const menu of document.querySelectorAll('.more-menu[open],.page-menu[open]'))menu.open=false;});
