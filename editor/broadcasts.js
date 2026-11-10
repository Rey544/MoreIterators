                                                                                
(function (scope, factory) {
  'use strict';
  const api = factory(scope);
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (scope) scope.MIBroadcastExchange = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function (scope) {
  'use strict';
  const SCHEMA = 'moreiterators.broadcast.v1', DEFAULT_COLOR = '#C9CCCF';
  const COLOR = /^#[0-9a-f]{6}$/i, ID = /^[A-Za-z0-9_-]{1,120}$/;
  const DETAIL_STRINGS = {synopsis:100000,region:500,group:500,code:500,broadcastType:500,sourceNode:500,reader:500,abilities:100000,comment:100000,characterColor:7,english:500};
  const DETAIL_LISTS = ['tags','characterTags','aliases','participants'];
  const BROADCAST_STRINGS = {typeLabel:500,groupType:500,groupName:500,middleText:5000,privateLabel:500,secondaryHeading:5000};
  const BROADCAST_FLAGS = ['showParticipants','showComment','showSources','useCharacterColors'];
  const fail = message => { throw new Error(message); };
  const object = value => !!value && typeof value === 'object' && !Array.isArray(value);
  const copy = value => JSON.parse(JSON.stringify(value));
  const style = () => ({font:'normal',size:1,speed:1,hold:2.5});
  const key = value => value.trim().replace(/^[【\[]+|[】\]]+$/g,'').trim().toLowerCase();
  const kind = value => value.kind || ({'广播':'broadcast','角色':'character','蛞蝓猫':'slugcat'}[value.category]);
  function string(value, maximum, message) {
    if (typeof value !== 'string' || value.length > maximum || value.includes('\0')) fail(message);
    return value;
  }
  function color(value) { if (typeof value !== 'string' || !COLOR.test(value)) fail('请输入 RGB 颜色'); return value; }
  function names(value, message, maximum = 1000, width = 200) {
    if (!Array.isArray(value) || value.length > maximum) fail(message);
    value.forEach(item => string(item,width,message));
    return copy(value);
  }
  function prefix(text) {
    const match = /^[ \t]*(?:【([^】\r\n]+)】|\[([^\]\r\n]+)\]|([^:：\r\n]+))[ \t]*[:：]/.exec(text);
    return match ? key(match[1] || match[2] || match[3]) : '';
  }
  function known(raw, allowed, message) {
    if (!object(raw) || Object.keys(raw).some(name => !allowed.includes(name))) fail(message);
  }
  function broadcastDetails(raw) {
    known(raw,[...Object.keys(BROADCAST_STRINGS),...BROADCAST_FLAGS,'mode','sources','annotations'],'RainocTool 广播格式无效');
    for (const [name,max] of Object.entries(BROADCAST_STRINGS)) if (Object.hasOwn(raw,name)) string(raw[name],max,'RainocTool 广播格式无效');
    for (const name of BROADCAST_FLAGS) if (Object.hasOwn(raw,name) && typeof raw[name] !== 'boolean') fail('RainocTool 广播格式无效');
    if (Object.hasOwn(raw,'mode') && !['group','private'].includes(raw.mode)) fail('RainocTool 广播格式无效');
    for (const [name,fields] of [['sources',{participant:500,suffix:500}],['annotations',{label:500,value:5000}]]) {
      if (!Object.hasOwn(raw,name)) continue;
      if (!Array.isArray(raw[name]) || raw[name].length > 1000) fail('RainocTool 广播格式无效');
      for (const item of raw[name]) {
        known(item,Object.keys(fields),'RainocTool 广播格式无效');
        for (const [field,max] of Object.entries(fields)) if (Object.hasOwn(item,field)) string(item[field],max,'RainocTool 广播格式无效');
      }
    }
    return copy(raw);
  }
  function documentDetails(raw) {
    raw = raw == null ? {} : raw;
    known(raw,[...Object.keys(DETAIL_STRINGS),...DETAIL_LISTS,'lines','appearance','iconData','broadcast','readings','regionProfiles','echo'],'RainocTool 广播格式无效');
    for (const [name,max] of Object.entries(DETAIL_STRINGS)) if (raw[name] != null) string(raw[name],max,'RainocTool 广播格式无效');
    if (raw.characterColor) color(raw.characterColor);
    for (const name of DETAIL_LISTS) if (Object.hasOwn(raw,name)) names(raw[name],'RainocTool 广播格式无效');
    if (Object.hasOwn(raw,'broadcast')) broadcastDetails(raw.broadcast);
    if (Object.hasOwn(raw,'appearance')) {
      known(raw.appearance,['baseColor'],'RainocTool 广播图标颜色无效');
      if (Object.hasOwn(raw.appearance,'baseColor')) color(raw.appearance.baseColor);
    }
    if (Object.hasOwn(raw,'lines')) {
      if (!Array.isArray(raw.lines) || raw.lines.length > 10000) fail('RainocTool 广播格式无效');
      for (const line of raw.lines) {
        known(line,['speaker','text'],'RainocTool 广播格式无效');
        if (line.speaker != null) string(line.speaker,500,'RainocTool 广播格式无效');
        if (line.text != null) string(line.text,100000,'RainocTool 广播格式无效');
      }
    }
    if (Object.hasOwn(raw,'readings')) {
      if (!Array.isArray(raw.readings) || raw.readings.length > 500) fail('RainocTool 广播格式无效');
      const seen = new Set();
      for (const reading of raw.readings) {
        known(reading,['id','reader','content'],'RainocTool 广播格式无效');
        if (!validId(reading.id) || seen.has(reading.id)) fail('RainocTool 广播格式无效');
        seen.add(reading.id);
        if (reading.reader != null) string(reading.reader,500,'RainocTool 广播格式无效');
        if (reading.content != null) string(reading.content,1024*1024,'RainocTool 广播格式无效');
      }
    }
    if (raw.regionProfiles != null) {
      if (!Array.isArray(raw.regionProfiles) || raw.regionProfiles.length>500) fail('RainocTool 广播格式无效');
      const seen = new Set();
      for (const profile of raw.regionProfiles) {
        if (!object(profile) || !validId(profile.id) || seen.has(profile.id)) fail('RainocTool 广播格式无效');
        seen.add(profile.id);
        for (const [name,max] of Object.entries({title:500,sceneId:160,synopsis:100000,content:1024*1024,notes:100000})) if (profile[name]!=null) string(profile[name],max,'RainocTool 广播格式无效');
        if (profile.tags!=null) names(profile.tags,'RainocTool 广播格式无效',500,500);
      }
    }
    if (raw.echo != null) {
      if (!object(raw.echo)) fail('RainocTool 广播格式无效');
      if (raw.echo.room!=null) string(raw.echo.room,500,'RainocTool 广播格式无效');
      if (raw.echo.typeNote!=null) string(raw.echo.typeNote,10000,'RainocTool 广播格式无效');
    }
    if (raw.iconData != null) {
      string(raw.iconData,Math.floor(2*1024*1024*4/3)+64,'RainocTool 广播格式无效');
      if (raw.iconData) {
        const match = /^data:(image\/(?:png|jpeg|webp));base64,([A-Za-z0-9+/]+={0,2})$/.exec(raw.iconData);
        if (!match || match[2].length%4) fail('RainocTool 广播格式无效');
        let bytes; try { bytes = scope.atob(match[2]); } catch (_) { fail('RainocTool 广播格式无效'); }
        if (!bytes.length || bytes.length>2*1024*1024) fail('RainocTool 广播格式无效');
        const matches = {'image/png':bytes.length>=24&&bytes.slice(0,8)==='\x89PNG\r\n\x1a\n','image/jpeg':bytes.length>=4&&bytes.slice(0,3)==='\xff\xd8\xff','image/webp':bytes.length>=12&&bytes.slice(0,4)==='RIFF'&&bytes.slice(8,12)==='WEBP'};
        if (!matches[match[1]]) fail('RainocTool 广播格式无效');
      }
    }
    return copy(raw);
  }
  function validId(value) { return typeof value === 'string' && ID.test(value) && !['__proto__','prototype','constructor'].includes(value); }
  function documentMetadata(item) {
    const result = {};
    for (const [name,max] of Object.entries({id:120,title:500,category:500,logicalPath:2000,sourcePath:2000,content:8*1024*1024})) {
      if (item[name] != null) result[name] = string(item[name],max,'RainocTool 广播格式无效');
    }
    if (result.id && !validId(result.id)) fail('RainocTool 广播格式无效');
    if (Object.hasOwn(item,'categories')) result.categories = names(item.categories,'RainocTool 广播格式无效');
    if (Object.hasOwn(item,'archived')) result.archived = !!item.archived;
    result.kind = 'broadcast'; result.details = documentDetails(item.details);
    return result;
  }
  function randomUid() {
    if (scope.crypto && typeof scope.crypto.randomUUID === 'function') return scope.crypto.randomUUID().replace(/-/g,'');
    fail('无法生成广播内部 ID');
  }
  function speakerCandidates(documents) {
    const used = new Set(), result = [];
    for (const item of documents) {
      if (!object(item) || !['character','slugcat'].includes(kind(item))) continue;
      const details = item.details == null ? {} : item.details;
      if (!object(details)) fail('RainocTool 角色格式无效');
      const aliases = names(details.aliases == null ? [] : details.aliases,'RainocTool 角色格式无效');
      const tags = names(details.characterTags == null ? [] : details.characterTags,'RainocTool 角色格式无效');
      if (typeof item.title !== 'string' || !item.title.trim()) continue;
      const tokens = [];
      for (const token of [item.title,...aliases,...tags]) {
        if (!key(token) || used.has(key(token))) continue;
        tokens.push(token); used.add(key(token));
      }
      if (!tokens.length) continue;
      const speaker = {name:tokens[0],aliases:tokens.slice(1),color:color(details.characterColor || '#ffffff')};
      result.push({speaker,source:{id:validId(item.id)?item.id:'',kind:kind(item),category:typeof item.category==='string'?item.category:'',characterTags:tags.filter(tag=>tokens.includes(tag))}});
    }
    return result;
  }
  function validateSpeaker(speaker) {
    if (!object(speaker) || typeof speaker.name !== 'string' || !speaker.name.trim() || speaker.name.length > 100) fail('角色名称需要 1—100 字');
    color(speaker.color); names(speaker.aliases || [],'角色别名无效',30,100);
    for (const name of [speaker.name,...(speaker.aliases || [])]) if (!key(name) || /[:：\r\n]/.test(key(name))) fail('角色名称与别名不能包含冒号或换行');
  }
  function importRainoc(bundle, options = {}) {
    if (!object(bundle) || bundle.format !== 'eoe-lore-project' || bundle.version !== 1) fail('请选择 MI 广播或 RainocTool 导出的 JSON');
    const source = bundle.project;
    if (!object(source) || !Array.isArray(source.documents)) fail('RainocTool 文档列表无效');
    if (source.documents.length > 10000) fail('RainocTool 文档数量超出范围');
    const candidates = speakerCandidates(source.documents), used = new Set(options.usedIds || []), identities = new Set(), projects = [];
    const newUid = options.uid || randomUid;
    for (const item of source.documents) {
      if (!object(item) || kind(item) !== 'broadcast') continue;
      const metadata = documentMetadata(item), details = metadata.details, settings = details.broadcast || {};
      const content = item.content == null ? '' : string(item.content,8*1024*1024,'RainocTool 广播正文无效');
      const effective = !content.trim() && details.lines?.length ? details.lines.map(line=>(line.speaker ? line.speaker+'：' : '')+(line.text || '')).join('\n') : content;
      const texts = effective.replace(/\r\n?/g,'\n').split('\n');
      if (texts.length > 10000) fail('广播需要 1—100 页');
      if (texts.some(text=>text.length>4000)) fail('单句最多 4000 字');
      let number = 1; while (used.has('B'+String(number).padStart(2,'0'))) number++;
      const identifier = 'B'+String(number).padStart(2,'0'); used.add(identifier);
      const name = item.title || identifier;
      if (typeof name !== 'string' || !name.trim() || name.length > 100) fail('请输入 1—100 字的名称');
      const uid = newUid(); if (typeof uid !== 'string' || !/^[a-f0-9]{32}$/.test(uid) || identities.has(uid)) fail('广播内部 ID 无效');
      identities.add(uid);
      const referenced = new Set(texts.map(prefix).filter(Boolean));
      for (const name of details.participants || []) referenced.add(key(name));
      for (const entry of settings.sources || []) if (entry.participant) referenced.add(key(entry.participant));
      const relevant = candidates.filter(entry=>[entry.speaker.name,...entry.speaker.aliases].some(name=>referenced.has(key(name))));
      if (relevant.length > 200) fail('角色绑定最多 200 个');
      relevant.forEach(entry=>validateSpeaker(entry.speaker));
      const pages = []; for (let i=0;i<texts.length;i+=100) pages.push({lines:texts.slice(i,i+100).map(text=>({text,color:'#ffffff',...style()}))});
      const sourceProject = {};
      if (typeof source.name === 'string') sourceProject.name = string(source.name,160,'RainocTool 项目名称无效');
      if (typeof source.uid === 'string' && /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(source.uid)) sourceProject.uid = source.uid;
      if (source.broadcastSettings != null) {
        known(source.broadcastSettings,['alignment'],'RainocTool 广播格式无效');
        if (source.broadcastSettings.alignment !== undefined && !['left','center'].includes(source.broadcastSettings.alignment)) fail('RainocTool 广播格式无效');
        sourceProject.broadcastSettings = copy(source.broadcastSettings);
      }
      projects.push({schema:SCHEMA,id:identifier,uid,name,revision:0,region:'',room:'',x:.5,y:.5,style:style(),
        useCharacterColors:settings.useCharacterColors === true,speakers:relevant.map(entry=>copy(entry.speaker)),pages,
        appearance:{baseColor:details.appearance?.baseColor || DEFAULT_COLOR},
        rainoc:{document:metadata,project:sourceProject,content:texts.join('\n'),speakers:relevant.map(entry=>copy(entry))}});
    }
    if (!projects.length) fail('此 JSON 中没有广播');
    return projects;
  }
  function exportRainoc(project) {
    if (!object(project) || project.schema !== SCHEMA || !/^[a-f0-9]{32}$/.test(project.uid || '')) fail('广播格式无效');
    string(project.name,100,'请输入 1—100 字的名称'); if (!project.name.trim()) fail('请输入 1—100 字的名称');
    if (!Array.isArray(project.pages) || !project.pages.length || project.pages.length>100) fail('广播需要 1—100 页');
    const lines = project.pages.flatMap(page=>{
      if (!object(page) || !Array.isArray(page.lines) || !page.lines.length || page.lines.length>100) fail('每页需要 1—100 句');
      return page.lines.map(line=>string(line?.text,4000,'单句最多 4000 字'));
    });
    const saved = object(project.rainoc) ? project.rainoc : {}, source = object(saved.project) ? saved.project : {};
    const document = object(saved.document) ? documentMetadata(saved.document) : {kind:'broadcast',details:{}};
    document.id = validId(document.id) ? document.id : 'broadcast-'+project.uid;
    document.title = project.name; document.category = document.category || '广播';
    const text = lines.join('\n'), unchanged = saved.content === text && object(saved.document);
    document.content = unchanged ? saved.document.content || '' : text;
    if (!unchanged && !text.trim() && document.details.lines?.length) document.details.lines = [];
    let speakers = project.speakers || [], useCharacterColors = project.useCharacterColors === true;
    if (!Object.hasOwn(project,'style') && !Object.hasOwn(project,'useCharacterColors')) {
      const legacy = new Map();
      for (const line of project.pages.flatMap(page=>page.lines)) {
        const name = prefix(line.text), shade = color(line.color || '#ffffff');
        if (!name && shade.toLowerCase() !== '#ffffff' || name && legacy.has(name) && legacy.get(name).color.toLowerCase() !== shade.toLowerCase()) fail('RainocTool 无法保留这份广播的逐句颜色，请使用 MI JSON。');
        if (name) legacy.set(name,{name,aliases:[],color:shade});
      }
      speakers = [...legacy.values()];useCharacterColors = speakers.some(speaker=>speaker.color.toLowerCase() !== '#ffffff');
    }
    document.details.broadcast = {...(document.details.broadcast || {}),useCharacterColors};
    const icon = project.appearance?.baseColor;
    if (icon !== undefined) document.details.appearance = {...(document.details.appearance || {}),baseColor:color(icon)};
    if (!Array.isArray(speakers) || speakers.length>200) fail('角色绑定最多 200 个');
    const documents = [document], ids = new Set([document.id]);
    speakers.forEach((speaker,index)=>{
      validateSpeaker(speaker);
      const match = Array.isArray(saved.speakers) ? saved.speakers.find(entry=>entry?.speaker?.name===speaker.name) : null;
      const original = object(match?.source) ? match.source : {};
      let id = validId(original.id) ? original.id : 'character-'+project.uid+'-'+(index+1), collision=0;
      while (ids.has(id)) id = 'character-'+project.uid+'-'+(index+1)+'-'+(++collision);
      ids.add(id);
      const aliases = [...new Set(speaker.aliases || [])];
      const tags = Array.isArray(original.characterTags) ? original.characterTags.filter(tag=>aliases.includes(tag)) : [];
      documents.push({id,title:speaker.name,kind:original.kind==='slugcat'?'slugcat':'character',category:original.category || (original.kind==='slugcat'?'蛞蝓猫':'角色'),content:'',
        details:{aliases:aliases.filter(alias=>!tags.includes(alias)),characterTags:tags,characterColor:speaker.color}});
    });
    const sourceUid=typeof source.uid==='string'&&/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(source.uid)?source.uid:'';
    const projectName=typeof source.name==='string'&&source.name.trim()?source.name:project.name;
    string(projectName,160,'RainocTool 项目名称无效');
    const value = {id:'project-'+project.uid,uid:sourceUid || project.uid.replace(/^(.{8})(.{4})(.{4})(.{4})(.{12})$/,'$1-$2-$3-$4-$5'),
      name:projectName,revision:1,images:[],documents,
      categories:[],imageCategories:[],documentCategories:[...new Set(documents.map(doc=>doc.category).filter(Boolean))]};
    if (source.broadcastSettings != null) {
      known(source.broadcastSettings,['alignment'],'RainocTool 广播格式无效');
      if (source.broadcastSettings.alignment!==undefined&&!['left','center'].includes(source.broadcastSettings.alignment)) fail('RainocTool 广播格式无效');
      value.broadcastSettings = copy(source.broadcastSettings);
    }
    return {format:'eoe-lore-project',version:1,project:value,documentAssets:[],exportScope:{mode:'partial',imageIds:[],documentIds:documents.map(doc=>doc.id)}};
  }
  return Object.freeze({importRainoc,exportRainoc,DEFAULT_COLOR});
});

(function(scope){
 'use strict';
                                                                 
 const mask=['..+####+.....','.+#....#+....','+#..++..+....','#..+##+......','#.+#.........','#.+#.##....#.','#..+.##....#+','+#.....#..+##','.++.....#+###','........+####','.......+####+','.....#######.','......+###+..'];
 function draw(canvas,color='#C9CCCF'){
  const ctx=canvas.getContext('2d'),w=canvas.width,h=canvas.height;
  if(!ctx||!w||!h)return;
  const scale=Math.min(w,h)<13?Math.min(w,h)/13:Math.floor(Math.min(w,h)/13),ox=Math.floor((w-13*scale)/2),oy=Math.floor((h-13*scale)/2);
  ctx.save();ctx.setTransform(1,0,0,1,0,0);ctx.clearRect(0,0,w,h);ctx.globalCompositeOperation='source-over';ctx.fillStyle=/^#[\da-f]{6}$/i.test(color)?color:'#C9CCCF';ctx.imageSmoothingEnabled=false;
  for(let y=0;y<13;y++)for(let x=0;x<13;x++){const pixel=mask[y][x];if(pixel==='.')continue;ctx.globalAlpha=pixel==='+'?115/255:1;ctx.fillRect(ox+x*scale,oy+y*scale,scale,scale);}
  ctx.restore();
 }
 scope.MIBroadcastIcon={draw};
})(globalThis);

'use strict';
const $=id=>document.getElementById(id),clone=x=>JSON.parse(JSON.stringify(x));
let project,saved=[],rooms=[],geometry=null,page=0,dirty=false,generation=0,mapRect=null,saving=false,loading=false,imported=[];
const defaultStyle=()=>({font:'normal',size:1,speed:1,hold:2.5});
const newLine=()=>{const line={text:'',color:'#ffffff',...defaultStyle()};if(project)for(const key of Object.keys(defaultStyle())){const value=styleValue(key);if(value!=='')line[key]=value;}return line;};
const speakerKey=value=>String(value||'').trim().replace(/^[【\[]+|[】\]]+$/g,'').trim().toLowerCase();
function speakerPrefix(text){const match=/^[ \t]*(?:【([^】\r\n]+)】|\[([^\]\r\n]+)\]|([^:：\r\n]+))[ \t]*[:：]/.exec(text);return match?speakerKey(match[1]||match[2]||match[3]):'';}
function speakerFor(text){const key=speakerPrefix(text);return key?(project.speakers||[]).find(s=>[s.name,...(s.aliases||[])].some(name=>speakerKey(name)===key)):null;}
function lineColor(line){return Object.hasOwn(project,'useCharacterColors')?(project.useCharacterColors?speakerFor(line.text)?.color||'#ffffff':'#ffffff'):line.color||'#ffffff';}
function lineStyle(line){return project.style||line;}
function styleValue(key){if(project.style)return project.style[key];const values=project.pages.flatMap(page=>page.lines).map(line=>line[key]??defaultStyle()[key]);return values.every(value=>value===values[0])?values[0]:'';}
function editStyle(key,value){if(project.style)project.style[key]=value;else for(const page of project.pages)for(const line of page.lines)line[key]=value;}
function colorsEnabled(){return Object.hasOwn(project,'useCharacterColors')?project.useCharacterColors:project.pages.some(page=>page.lines.some(line=>line.color.toLowerCase()!=='#ffffff'));}
function editColors(enabled){if(!Object.hasOwn(project,'useCharacterColors')&&!project.speakers?.length){project.speakers=[];const seen=new Set();for(const line of project.pages.flatMap(page=>page.lines)){const name=speakerPrefix(line.text);if(name&&!seen.has(name)){seen.add(name);project.speakers.push({name,aliases:[],color:line.color||'#ffffff'});}}}project.useCharacterColors=enabled;}
function normalize(value){
 const p=clone(value);if(p.appearance?.baseColor!==undefined&&!/^#[\da-f]{6}$/i.test(p.appearance.baseColor))throw Error(MI18n.text('广播图标颜色无效'));
 return p;
}
const iconColor=p=>p.appearance?.baseColor||'#c9cccf';
function renderIcon(){MIBroadcastIcon.draw($('broadcastIcon'),iconColor(project));$('iconColor').value=iconColor(project);}
async function api(url,value){await MI18n.ready;const r=await fetch(url,value===undefined?{headers:{'X-MI-Language':MI18n.locale}}:{method:'POST',headers:{'Content-Type':'application/json','X-MI-Language':MI18n.locale},body:JSON.stringify(value)});const j=await r.json();if(!r.ok)throw Error(MI18n.error(j,'请求失败'));return j;}
function notice(s,error=false){$('notice').textContent=s;$('notice').dataset.kind=error?'error':'info';}
function changed(){dirty=true;notice('');renderCards();window.MIUndo?.changed();}
function guard(){return !saving&&!loading&&(!dirty||confirm('当前修改尚未保存，确定放弃并切换吗？'));}
function option(value,text){const e=document.createElement('option');e.value=value;e.textContent=text;return e;}
function field(type,value,onchange){const e=document.createElement('input');e.type=type;e.value=value;e.addEventListener('input',()=>onchange(e));return e;}
function button(text,action,title){const e=document.createElement('button');e.type='button';e.textContent=text;e.onclick=action;if(title)e.setAttribute('aria-label',title);return e;}
async function list(){saved=await api('/api/broadcasts');$('saved').replaceChildren(option('','选择已保存广播…'),...saved.map(p=>option(p.id,p.name&&p.name!==p.id?p.name+' ('+p.id+')':p.id)));if(project&&saved.some(p=>p.uid===project.uid))$('saved').value=project.id;renderCards();}
function renderCards(){
 const cards=saved.map(p=>project?.uid===p.uid?project:p);if(project&&!cards.some(p=>p.uid===project.uid))cards.push(project);
 $('broadcastList').replaceChildren(...cards.map(p=>{const b=button('',()=>{if(p.uid!==project?.uid&&guard())choose(p);});b.className='broadcast-card';b.setAttribute('aria-current',String(p.uid===project?.uid));const icon=document.createElement('canvas');icon.width=icon.height=39;icon.setAttribute('aria-hidden','true');MIBroadcastIcon.draw(icon,iconColor(p));const body=document.createElement('span');body.className='broadcast-card-text';const name=MI18n.content(document.createElement('span'));name.textContent=p.name||p.id;const id=MI18n.content(document.createElement('small'));id.textContent=p.id;body.append(name,id);b.append(icon,body);return b;}));
}
function choose(p){generation++;project=normalize(p);dirty=false;page=0;render();notice('已打开 '+p.name);window.MIUndo?.reset();}
function renderStyle(){for(const key of Object.keys(defaultStyle())){const input=$(key),value=styleValue(key);if(key==='font'&&!input.querySelector('option[value=""]')){const mixed=option('',MI18n.t('broadcast.perLine'));mixed.disabled=true;input.prepend(mixed);}input.value=value;if(key!=='font'){input.placeholder=MI18n.t('broadcast.perLine');input.required=value!=='';}}$('useCharacterColors').checked=colorsEnabled();}
function render(){for(const k of ['id','name'])$(k).value=project[k];$('id').disabled=project.revision>0;renderStyle();renderIcon();renderSpeakers();renderCards();regionOptions();renderPage();loadGeometry().catch(e=>notice(e.message,true));}
function regionOptions(){const regions=[...new Set(rooms.map(r=>r.region))].sort();$('region').replaceChildren(option('','选择地区'),...regions.map(r=>option(r,r)));$('region').value=project.region;roomOptions()}
function roomOptions(){const items=rooms.filter(r=>r.region===project.region);$('room').replaceChildren(option('','选择房间'),...items.map(r=>option(r.room,r.room)));$('room').value=project.room}
async function loadGeometry(){geometry=null;drawMap();if(!project.room)return;const room=project.room,g=await api('/api/broadcast-room?room='+encodeURIComponent(room));if(project.room===room){geometry=g;drawMap()}}
function drawMap(){const c=$('map'),ctx=c.getContext('2d');ctx.clearRect(0,0,c.width,c.height);ctx.fillStyle='#111111';ctx.fillRect(0,0,c.width,c.height);$('x').value=(project.x*100).toFixed(1);$('y').value=(project.y*100).toFixed(1);mapRect=null;if(!geometry){$('position').textContent='先选择房间';return}
 const g=geometry,s=Math.min((c.width-20)/g.width,(c.height-20)/g.height),ox=(c.width-g.width*s)/2,oy=(c.height-g.height*s)/2;mapRect={s,ox,oy,w:g.width,h:g.height};ctx.fillStyle='#737373';for(const [x,y] of g.solids)ctx.fillRect(ox+x*s,oy+(g.height-y-1)*s,Math.ceil(s),Math.ceil(s));ctx.strokeStyle='#b0b0b0';ctx.lineWidth=1;ctx.setLineDash([4,3]);g.cameras.forEach(([x,y],i)=>{ctx.strokeRect(ox+x/20*s,oy+(g.height-(y+800)/20)*s,1400/20*s,800/20*s);ctx.fillStyle='#dedede';ctx.fillText(String(i+1),ox+x/20*s+3,oy+(g.height-(y+800)/20)*s+12)});
 ctx.setLineDash([]);const x=ox+project.x*g.width*s,y=oy+(1-project.y)*g.height*s;ctx.strokeStyle='white';ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(x,y-8);ctx.lineTo(x+6,y);ctx.lineTo(x,y+8);ctx.lineTo(x-6,y);ctx.closePath();ctx.stroke();const tile=[Math.floor(project.x*g.width),Math.floor(project.y*g.height)],solid=g.solids.some(p=>p[0]===tile[0]&&p[1]===tile[1]);$('position').textContent=MI18n.t(solid?'broadcast.position.solid':'broadcast.position',{x:Math.round(project.x*g.width*20),y:Math.round(project.y*g.height*20)});
}
$('map').onclick=e=>{if(!mapRect)return;const b=e.currentTarget.getBoundingClientRect(),r=mapRect;project.x=Math.max(0,Math.min(1,((e.clientX-b.left)/b.width*e.currentTarget.width-r.ox)/(r.w*r.s)));project.y=Math.max(0,Math.min(1,1-((e.clientY-b.top)/b.height*e.currentTarget.height-r.oy)/(r.h*r.s)));changed();drawMap()};

function renderSpeakers(){
 const group=$('speakers').closest('details');group.hidden=!colorsEnabled();$('speakers').replaceChildren();(project.speakers||[]).forEach((speaker,index)=>{
  const row=document.createElement('div');row.className='speaker-row';
  const name=field('text',speaker.name,e=>{speaker.name=e.value;changed();refreshSpeakerBadges();preview();});name.maxLength=100;name.placeholder='角色名称';name.setAttribute('aria-label','角色名称');
  const aliases=field('text',(speaker.aliases||[]).join('、'),e=>{speaker.aliases=e.value.split(/[,，、]/).map(s=>s.trim()).filter(Boolean);changed();refreshSpeakerBadges();preview();});aliases.placeholder='别名或缩写';aliases.setAttribute('aria-label','别名或缩写');
  const color=field('color',speaker.color,e=>{speaker.color=e.value;changed();refreshSpeakerBadges();preview();});color.setAttribute('aria-label','角色颜色');
  row.append(name,aliases,color,button('×',()=>{project.speakers.splice(index,1);changed();renderSpeakers();refreshSpeakerBadges();preview();},'删除角色绑定'));$('speakers').append(row);
 });
}
function refreshSpeakerBadges(){document.querySelectorAll('.speaker-indicator').forEach((badge,i)=>{const line=project.pages[page].lines[i]||{text:''},speaker=speakerFor(line.text);badge.textContent=speaker?speaker.name:'';badge.style.color=lineColor(line);});}
function renderPage(){
 generation++;renderStyle();page=Math.max(0,Math.min(page,project.pages.length-1));$('page').replaceChildren(...project.pages.map((_,i)=>option(i,'第 '+(i+1)+' 页')));$('page').value=page;$('lines').replaceChildren();
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
function previewLine(line){const p=MI18n.content(document.createElement('p')),style=lineStyle(line);p.style.color=lineColor(line);p.style.fontSize=(18*style.size)+'px';p.style.fontWeight=style.font==='display'?'bold':'normal';return p;}
function preview(){generation++;$('preview').replaceChildren();project.pages[page].lines.forEach(line=>{const p=previewLine(line);p.textContent=line.text.replaceAll('<LINE>','\n');$('preview').append(p);});$('playState').textContent=MI18n.t('broadcast.preview',{index:page+1,total:project.pages.length});}
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function play(){const token=++generation;for(let j=page;j<project.pages.length;j++){if(token!==generation)return;$('preview').replaceChildren();$('playState').textContent='正在播放第 '+(j+1)+' 页';for(const line of project.pages[j].lines){const style=lineStyle(line),el=previewLine(line);$('preview').append(el);for(const ch of Array.from(line.text.replaceAll('<LINE>','\n'))){if(token!==generation)return;el.textContent+=ch;await wait(50/style.speed);}await wait(style.hold*1000);if(token!==generation)return;}}$('playState').textContent='播放结束';}
async function save(apply){
 if(saving||loading)return false;for(const input of document.querySelectorAll('.broadcast-detail input,.broadcast-preview-column input'))if(!input.checkValidity()){input.reportValidity();return false;}
 saving=true;document.querySelector('main').inert=true;try{const r=await api('/api/broadcast-'+(apply?'apply':'save'),project);project=normalize(r.project);dirty=false;$('id').disabled=true;renderPage();await list();window.MIUndo?.rebase();notice(apply?'已保存并应用。前往 '+project.room+' 触碰网格即可播放。':'已保存 '+project.name);return true;}catch(e){notice(e.message,true);return false;}finally{saving=false;document.querySelector('main').inert=false;}
}
function importSelected(p){choose(p);dirty=true;window.MIUndo?.reset();notice('已载入，尚未保存');}
$('new').onclick=async()=>{if(!guard())return;loading=true;try{choose(await api('/api/broadcast-default'));}catch(e){notice(e.message,true);}finally{loading=false;}};
$('newBroadcast').onclick=()=>$('new').click();$('saved').onchange=()=>{if($('saved').value&&guard())choose(saved.find(p=>p.id===$('saved').value));};
$('id').oninput=()=>{project.id=$('id').value.toUpperCase();$('id').value=project.id;changed();};$('name').oninput=()=>{project.name=$('name').value;changed();};
$('iconColor').oninput=()=>{project.appearance={...project.appearance,baseColor:$('iconColor').value};changed();renderIcon();};
$('editIconColor').onclick=()=>$('iconColor').click();
$('font').onchange=()=>{if(!$('font').value)return;editStyle('font',$('font').value);changed();preview();};for(const key of ['size','speed','hold'])$(key).oninput=()=>{if($(key).value!==''&&$(key).checkValidity()){editStyle(key,Number($(key).value));$(key).required=true;changed();preview();}};
$('useCharacterColors').onchange=()=>{editColors($('useCharacterColors').checked);changed();renderSpeakers();refreshSpeakerBadges();preview();};
$('addSpeaker').onclick=()=>{if((project.speakers||[]).length>=200)return;if(!Object.hasOwn(project,'useCharacterColors'))editColors(true);project.speakers.push({name:'',aliases:[],color:'#ffffff'});changed();renderSpeakers();$('speakers').lastElementChild?.querySelector('input')?.focus();};
$('region').onchange=()=>{project.region=$('region').value;project.room='';changed();roomOptions();loadGeometry();};$('room').onchange=()=>{project.room=$('room').value;changed();loadGeometry().catch(e=>notice(e.message,true));};
for(const k of ['x','y'])$(k).oninput=()=>{const v=Number($(k).value);if(Number.isFinite(v)){project[k]=Math.max(0,Math.min(1,v/100));changed();drawMap();}};
$('page').onchange=()=>{page=Number($('page').value);renderPage();};$('addPage').onclick=()=>{project.pages.push({lines:[newLine()]});page=project.pages.length-1;changed();renderPage();};
$('deletePage').onclick=()=>{if(project.pages.length>1&&confirm('删除本页及其文本？')){project.pages.splice(page,1);changed();renderPage();}};
for(const [id,d] of [['pageUp',-1],['pageDown',1]])$(id).onclick=()=>{const j=page+d;if(j<0||j>=project.pages.length)return;[project.pages[page],project.pages[j]]=[project.pages[j],project.pages[page]];page=j;changed();renderPage();};
$('addLine').onclick=()=>{project.pages[page].lines.push(newLine());changed();renderPage();};$('save').onclick=()=>save(false);$('apply').onclick=()=>save(true);$('play').onclick=play;$('stop').onclick=preview;$('previous').onclick=()=>{page--;renderPage();};$('next').onclick=()=>{page++;renderPage();};
$('refreshRooms').onclick=async()=>{try{rooms=await api('/api/broadcast-rooms?refresh=1');regionOptions();await loadGeometry();notice('已刷新房间列表');}catch(e){notice(e.message,true);}};
const mapPickerButton=button('地图选房',async()=>{
 if(saving||loading||!project||!window.MIRoomPicker)return;
 const owner=new URLSearchParams(location.search),current=project;
 await MIRoomPicker.open({room:project.room,region:project.region,projectId:owner.get('project')||owner.get('projectId')||'',pickPoint:true,point:{x:project.x,y:project.y},onSelect:async value=>{
  if(project!==current||saving||loading)return;
  if(!rooms.some(room=>room.room===value.room))rooms.push({region:value.region,room:value.room});
  project.region=value.region;project.room=value.room;if(value.point){project.x=value.point.x;project.y=value.point.y;}
  changed();regionOptions();geometry={...value.geometry,cameras:value.geometry.cameras.map(([x,y])=>[x,value.geometry.height*20-800-y])};drawMap();
 }});
});mapPickerButton.id='broadcastMapPicker';$('refreshRooms').before(mapPickerButton);
function downloadJson(value,name){const blob=new Blob([JSON.stringify(value,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),5000);}
$('export').onclick=()=>{if(!project||saving||loading)return;$('exportFormat').value='mi';$('exchangeLimit').hidden=true;$('exportPicker').showModal();};
$('exportFormat').onchange=()=>{$('exchangeLimit').hidden=$('exportFormat').value!=='rainoc';};
$('confirmExport').onclick=async()=>{if(!project||saving||loading)return;loading=true;$('confirmExport').disabled=true;try{const p=await api('/api/broadcast-validate',project),rainoc=$('exportFormat').value==='rainoc';downloadJson(rainoc?MIBroadcastExchange.exportRainoc(p):p,p.id+(rainoc?'-RainocTool':'')+'.json');$('exportPicker').close();}catch(error){notice(MI18n.text(error.message),true);}finally{loading=false;$('confirmExport').disabled=false;}};
$('import').onclick=()=>{if(guard())$('file').click();};$('file').onchange=async()=>{if(!$('file').files.length)return;loading=true;try{const value=JSON.parse(await $('file').files[0].text());imported=value?.format==='eoe-lore-project'?MIBroadcastExchange.importRainoc(value,{usedIds:saved.map(p=>p.id)}):(await api('/api/broadcast-import',value)).projects;if(imported.length===1)importSelected(await api('/api/broadcast-validate',imported[0]));else{$('importChoice').replaceChildren(...imported.map((p,i)=>option(i,p.name)));$('importPicker').showModal();}}catch(e){notice(MI18n.text(e.message),true);}finally{$('file').value='';loading=false;}};
$('confirmImport').onclick=async()=>{if(loading||saving)return;const selected=imported[Number($('importChoice').value)];if(!selected)return;loading=true;$('confirmImport').disabled=true;try{importSelected(await api('/api/broadcast-validate',selected));$('importPicker').close();}catch(e){notice(MI18n.text(e.message),true);}finally{loading=false;$('confirmImport').disabled=false;}};
window.MIUndo?.register({key:()=>project?.uid||'',capture:()=>{if(!project)return null;const p=clone(project);delete p.revision;delete p.runtimeId;return p;},restore:async snapshot=>{const revision=project.revision;project={...clone(snapshot),revision};changed();render();},busy:()=>saving||loading,onError:error=>notice(error.message,true)});
window.MIStudioPage={projectId:()=>new URLSearchParams(location.search).get('projectId')||new URLSearchParams(location.search).get('project'),isBusy:()=>saving||loading,saveBeforeNavigate:async()=>{if(dirty&&!await save(false))throw Error($('notice').textContent);return !dirty;},error:message=>notice(message,true)};
window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});
for(const id of ['projectionStudio','roomStudio'])$(id).onclick=event=>{const params=new URLSearchParams(location.search),owner=params.get('projectId')||params.get('project'),target=new URL(event.currentTarget.href,location.href);if(owner)target.searchParams.set('project',owner);target.searchParams.set('lang',MI18n.locale);event.currentTarget.href=target;};
(async()=>{loading=true;try{rooms=await api('/api/broadcast-rooms');await list();choose(saved[0]||await api('/api/broadcast-default'));}catch(e){notice(e.message,true);}finally{loading=false;}})();
document.addEventListener('click',event=>{for(const menu of document.querySelectorAll('.more-menu[open],.page-menu[open]'))if(!menu.contains(event.target)||event.target.closest('button,a'))menu.open=false;});
document.addEventListener('keydown',event=>{if(event.key==='Escape')for(const menu of document.querySelectorAll('.more-menu[open],.page-menu[open]'))menu.open=false;});

