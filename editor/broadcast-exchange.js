                                                                                
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
