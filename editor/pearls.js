'use strict';
const PearlActions=typeof module!=='undefined'?require('./line-actions.js'):window.MIActionEditor;
const PearlPresentation=PearlActions.presentation;
const MIPearlBranches=(()=>{
  function branch(reader,tier){return tier==='general'?reader:reader?.affinity?.[tier]||reader;}
  function clone(reader,newId){
    const result=structuredClone({read:reader.read,readAction:reader.readAction||{type:'none',delay:0},repeatEnabled:!!reader.repeatEnabled,repeatPrependCommon:!!reader.repeatPrependCommon,repeat:reader.repeat||[],presentation:reader.presentation||{movement:'inherit',eyes:'inherit'}});
    for(const line of [...result.read,...result.repeat.flatMap(group=>group.lines)])line.lineId=newId();return result;
  }
  function previewLines(lines,action,layers=[]){
    const result=structuredClone(lines.filter(PearlActions.runnable));
    for(const line of result){line.previewBeforeActions=PearlActions.sequence(line.beforeAction);line.previewActions=PearlActions.sequence(line.action);line.previewPresentation=PearlPresentation.resolve(...layers,line.presentation);}
    if(result.length)result.at(-1).previewActions.push(...PearlActions.sequence(action));
    return result;
  }
  function repeatSources(reader,common){
    if(!reader?.repeatEnabled)return [common||[]];
    const own=reader.repeat||[];
    return reader.repeatPrependCommon&&own.some(group=>group.lines.some(PearlActions.runnable))?[common||[],own]:[own];
  }
  function positionAt(clientX,clientY,rect,map,size){
    const marginX=5*size/(map.w*20),marginY=5*size/(map.h*20);
    const x=((clientX-rect.left)/rect.width*map.canvasWidth-map.ox)/(map.w*map.s);
    const y=1-((clientY-rect.top)/rect.height*map.canvasHeight-map.oy)/(map.h*map.s);
    return {x:Math.max(marginX,Math.min(1-marginX,x)),y:Math.max(marginY,Math.min(1-marginY,y))};
  }
  return {branch,clone,previewLines,repeatSources,positionAt};
})();
if(typeof module!=='undefined')module.exports=MIPearlBranches;
if(typeof document!=='undefined'){
const $ = id => document.getElementById(id);
const el = (tag, text, className) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
};
const api = async (path, data) => {await MI18n.ready;
    const response = await fetch('/api/' + path, data === undefined ? {} : {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)
    });
    const result = await response.json();
    if (!response.ok) throw Error(MI18n.error(result, response.statusText));
    return result;
};
let projects = [], saved = [], destinations = [], project = null;
let collectionId = 'legacy', collectionCatalog = {activeId:'legacy',projects:[]}, collectionDialogMode = 'new';
const collectionText = (key, values={}) => MI18n.t(`pearl.collection.${key}`,values);
const collectionQuery = (path, id=collectionId) => path+'?collectionId='+encodeURIComponent(id);

let sharedProfiles = {}, readerIndex = 0, affinityTier = 'general', stage = 'read', poolIndex = 0;
let deletedProjects=new Map(),deletedRooms=new Set(),availabilityQueued=false,availabilityRunning=false;
function rememberDeleted(entries){deletedProjects=new Map(entries.map(item=>[item.projectId,item]));deletedRooms=new Set(entries.flatMap(item=>item.rooms||[]));}
const deletedProject=id=>deletedProjects.has(id)||!!sharedProfiles[id]?.deleted;
const affinityText=(key,values={})=>MI18n.t(`pearl.affinity.${key}`,values);
let dirty = false, busy = false, simulateHalcyon = true;
let expandedLines = new WeakSet(), draggingLine = null;
let positionProject='',positionGeometry=null,positionMap=null,positionLoad=0,positionPointer=null;
const positionText=(key,values={})=>MI18n.t(`pearl.placement.${key}`,values);
const groupOpen = new Map();
const stageNames = {read: '首次读取', repeat: '重复交付', leaving: '中途离开', returning: '返回', many: '多颗珍珠'};
const reader = () => {const value=project?.readers[readerIndex];return value&&!deletedProject(value.projectId)?value:undefined;};
const common = () => sharedProfiles[reader()?.projectId]?.dialogue.pearlReading;
const branch = () => MIPearlBranches.branch(reader(),affinityTier);
const missingVariant = () => affinityTier!=='general'&&!Object.hasOwn(reader()?.affinity||{},affinityTier);
const commonStage = () => ['many', 'leaving', 'returning'].includes(stage) || stage === 'repeat' && !branch()?.repeatEnabled;
const stageData = () => commonStage() ? common() : branch();
const isPool = () => stage !== 'read';
const lineList = () => isPool() ? stageData()?.[stage]?.[poolIndex]?.lines : branch()?.read;
const readerLabel = id => projects.find(p=>p.projectId===id)?.name||sharedProfiles[id]?.name||id||MI18n.text('未选择');
const readerName = () => readerLabel(reader()?.projectId);
const archivedShared = () => !!sharedProfiles[reader()?.projectId]?.deleted;
const option = (value, name) => {const node = el('option', name); node.value = value; return node;};

function notice(message = '', bad = false) {
    $('notice').textContent = message;
    $('notice').hidden = !message;
    $('notice').classList.toggle('error', bad);
    $('notice').setAttribute('role', bad ? 'alert' : 'status');
}
function state(label, kind = 'saved') {
    $('saveState').textContent = label;
    $('saveState').dataset.state = kind;
}
function updateHeadings() {
    if (!project) return;
    const projectionOwner=reader()?.projectId||new URLSearchParams(location.search).get('projectId')||new URLSearchParams(location.search).get('project');
    $('roomStudio').href='/rooms?lang='+MI18n.locale+(projectionOwner?'&project='+encodeURIComponent(projectionOwner):'');
    $('projectionStudio').href='/projections?lang='+MI18n.locale+(projectionOwner?'&project='+encodeURIComponent(projectionOwner):'');
    $('pearlTitle').textContent = project.id + '／' + project.name; MI18n.content($('pearlTitle'));
    document.title = project.id + '／' + project.name + ' · 珍珠文本';
    $('readerTitle').textContent = MI18n.t('pearl.reader', {name: reader() ? readerName() : {key: 'common.not_selected'}});
    $('readerScope').replaceChildren();
    if(reader()&&(commonStage()||affinityTier!=='general'))$('readerScope').append(el('span',commonStage()?'该迭代器共用':affinityText(missingVariant()?'fallback':'enabled')));
    $('spawnTitle').textContent = MI18n.t('pearl.ui.spawn');
}
function changed(shared = false) {
    dirty = true;
    if (shared && reader()) sharedProfiles[reader().projectId].dirty = true;
    state('未保存更改', 'dirty');
    notice();
    updateHeadings();
    window.MIUndo?.changed();
}
const changedLines = () => changed(commonStage());
const run = fn => async (...args) => {
    try {return await fn(...args);}
    catch (error) {notice(error.message, true); console.error(error);}
};
async function ensureShared(candidate = project, profiles = sharedProfiles) {
    for (const binding of candidate.readers) {
        if (!profiles[binding.projectId]) profiles[binding.projectId] = await api('dialogue?id=' + encodeURIComponent(binding.projectId));
    }
}
async function refreshProjectAvailability(renderPage=false){
    const [active,rooms,deleted,latest]=await Promise.all([api('projects'),api('pearl-destinations'),api('project-trash'),Promise.all(Object.keys(sharedProfiles).map(async id=>[id,await api('dialogue?id='+encodeURIComponent(id))]))]);
    projects=active;destinations=rooms;rememberDeleted(deleted);
    let sharedChanged=false;
    for(const [id,fresh] of latest){
        const previous=sharedProfiles[id];
        if(!previous)continue; // The author may have switched pearls during this request.
        if(previous.dirty){previous.deleted=!!fresh.deleted;previous.name=fresh.name;}
        else {sharedChanged||=JSON.stringify(previous.dialogue.pearlReading)!==JSON.stringify(fresh.dialogue.pearlReading);sharedProfiles[id]=fresh;}
    }
    if(project&&!reader())stop();
    if(renderPage&&project)render();
    // A newly received shared document must not be overwritten by undoing an
    // unrelated pearl field. Local unsaved pearl content remains untouched.
    if(sharedChanged)window.MIUndo?.reset();
}
function queueAvailabilityRefresh(){
    availabilityQueued=true;if(busy||availabilityRunning)return;
    availabilityRunning=true;availabilityQueued=false;
    refreshProjectAvailability(true).catch(error=>notice(error.message,true)).finally(()=>{availabilityRunning=false;if(availabilityQueued)queueAvailabilityRefresh();});
}
function setBusy(value) {
    busy = value;
    if (value) endLineDrag();
    document.querySelector('main').inert = value;
    for (const id of ['saved', 'new', 'save', 'apply', 'import', 'export', 'collections', 'newCollection', 'renameCollection', 'activateCollection']) $(id).disabled = value || !project;
    $('newCollection').disabled=value;
    $('collections').disabled=value||!collectionCatalog.projects.length;
    $('activateCollection').disabled=value||!project||collectionId===collectionCatalog.activeId;
    if(!value&&availabilityQueued)queueAvailabilityRefresh();
}

function colorControl(key, title) {
    const row = el('div', undefined, 'color-row');
    const label = el('label', title), color = el('input'), hex = el('input');
    label.htmlFor = 'color-' + key;
    color.id = label.htmlFor;
    color.type = 'color';
    color.setAttribute('aria-label', title);
    hex.type = 'text';
    hex.maxLength = 7;
    hex.spellcheck = false;
    hex.setAttribute('aria-label', title + ' HEX');
    function sync() {
        const value = project.appearance[key];
        color.value = hex.value = value;
        hex.setCustomValidity('');
        hex.removeAttribute('aria-invalid');
    }
    function set(value) {
        project.appearance[key] = value.toLowerCase();
        sync(); changed(); drawPosition();
    }
    hex.oninput = () => {
        const value = hex.value.startsWith('#') ? hex.value : '#' + hex.value;
        if (/^#[a-f\d]{6}$/i.test(value)) set(value);
        else {hex.setCustomValidity(MI18n.text('请输入六位 Hex 颜色，如 #88bbff')); hex.setAttribute('aria-invalid', 'true');}
    };
    hex.onblur = () => {if (!hex.checkValidity()) hex.reportValidity();};
    color.oninput = () => set(color.value);
    const values = el('div', undefined, 'color-values'); values.append(color, hex);
    row.append(label, values); sync();
    return {row};
}
function appearance() {
    const host = $('appearance');
    host.replaceChildren();
    const dependent = [], effectFields = [], pulseFields = [], musicFields = [];
    for (const [key, title] of [['baseColor', '底色 / 主色'], ['highlightColor', '高光']]) {
        const control = colorControl(key, title);
        host.append(control.row);
    }
    function check(key, title) {
        const label = el('label', undefined, 'check-row'), input = el('input');
        input.type = 'checkbox'; input.checked = project.appearance[key]; input.id = 'appearance-' + key;
        input.onchange = () => {project.appearance[key] = input.checked; updateVisibility(); changed(); drawPosition();};
        label.append(el('span', title), input); host.append(label);
    }
    check('twoTone', '启用双色');
    const secondary = colorControl('secondaryColor', '第二种颜色'); dependent.push(secondary); host.append(secondary.row);
    const effectLabel = el('label', '特效', 'parameter-row'), effect = el('select');
    effect.setAttribute('aria-label', '特效');
    for (const [value, name] of [['none', '无'], ['glow', '柔光'], ['pulse', '脉冲光圈'], ['halcyon', '赞美诗式光圈']]) effect.append(option(value, name));
    effect.value = project.appearance.effect;
    effect.onchange = () => {project.appearance.effect = effect.value; updateVisibility(); changed();};
    effectLabel.append(effect); host.append(effectLabel);
    const halcyonPreview=el('div',undefined,'halcyon-preview'),halcyonLabel=el('label'),halcyonToggle=el('input');
    halcyonToggle.type='checkbox';halcyonToggle.id='halcyonPreview';halcyonToggle.checked=simulateHalcyon;
    halcyonToggle.onchange=()=>{simulateHalcyon=halcyonToggle.checked;};
    halcyonLabel.append(halcyonToggle,el('span',MI18n.t('pearl.ui.simulateHalcyon')));
    halcyonPreview.append(el('p',MI18n.t('pearl.ui.halcyonBeat')),halcyonLabel);host.append(halcyonPreview);
    const effectColor = colorControl('effectColor', '特效颜色'); effectFields.push(effectColor.row); host.append(effectColor.row);
    for (const [key, title, min, max, step] of [
        ['size', '大小', .5, 3, .05], ['effectOpacity', '特效透明度', 0, 1, .01],
        ['effectSize', '光圈范围', 5, 120, 1], ['pulseSpeed', '脉冲速度', .1, 4, .1]
    ]) {
        const label = range(key, title, min, max, step);
        host.append(label);
        if (key.startsWith('effect')) effectFields.push(label);
        if (key === 'pulseSpeed') pulseFields.push(label);
    }
    check('music', '赞美诗音乐');
    const track=project.appearance.musicTrack??=AudioSettings.blank();
    const musicSource=el('label',MI18n.t('pearl28.musicSource'),'parameter-row'),musicMode=el('select');
    for(const [value,key] of [['native','nativeMusic'],['custom','customMusic'],['silent','silentMusic']])musicMode.append(option(value,MI18n.t('pearl28.'+key)));
    musicMode.value=track.mode;musicMode.onchange=()=>{track.mode=musicMode.value;updateVisibility();changed();};
    musicSource.append(musicMode);host.append(musicSource);musicFields.push(musicSource);
    const customMusic=el('div',undefined,'pearl-custom-music');host.append(customMusic);
    const musicName=el('span',track.name||'—','hint');MI18n.content(musicName);
    const musicImport=el('button',MI18n.t('pearl28.importMusic')),musicFile=el('input');musicImport.type='button';musicFile.type='file';musicFile.accept='.mp3,audio/mpeg';musicFile.hidden=true;
    const musicPreview=el('audio');musicPreview.controls=true;musicPreview.preload='none';musicPreview.style.width='100%';if(track.asset)musicPreview.src='/api/audio/'+track.asset+'.mp3';
    musicImport.onclick=()=>musicFile.click();musicFile.onchange=run(async()=>{if(!musicFile.files[0])return;musicImport.disabled=true;try{Object.assign(track,await AudioSettings.importFile(musicFile.files[0]));musicName.textContent=track.name;musicPreview.src='/api/audio/'+track.asset+'.mp3';updateVisibility();changed();}finally{musicImport.disabled=false;musicFile.value='';}});
    const customVolume=el('label',MI18n.t('pearl28.musicVolume'),'range-row'),volumeInput=el('input'),volumeValue=el('output',track.volume);Object.assign(volumeInput,{type:'range',min:0,max:1,step:.01,value:track.volume});volumeInput.oninput=()=>{track.volume=+volumeInput.value;volumeValue.textContent=volumeInput.value;changed();};customVolume.append(volumeInput,volumeValue);
    const loopLabel=el('label',undefined,'check-row'),loopInput=el('input');loopInput.type='checkbox';loopInput.checked=track.loop;loopInput.onchange=()=>{track.loop=loopInput.checked;changed();};loopLabel.append(loopInput,document.createTextNode(MI18n.t('pearl28.loopMusic')));
    customMusic.append(musicName,musicImport,musicFile,musicPreview,customVolume,loopLabel);
    const musicVolume = range('musicVolume', '音乐音量', 0, .6, .01);host.append(musicVolume);
    function updateVisibility() {
        halcyonPreview.hidden=project.appearance.effect!=='halcyon';halcyonToggle.disabled=!project.appearance.music;
        dependent.forEach(({row}) => row.hidden = !project.appearance.twoTone);
        effectFields.forEach(node => node.hidden = project.appearance.effect === 'none');
        pulseFields.forEach(node => node.hidden = !['pulse', 'halcyon'].includes(project.appearance.effect));
        musicFields.forEach(node => node.hidden = !project.appearance.music);
        customMusic.hidden=!project.appearance.music||track.mode!=='custom';
        musicVolume.hidden=!project.appearance.music||track.mode!=='native';
    }
    updateVisibility();
}
function range(key, title, min, max, step) {
    const label = el('label', undefined, 'range-row'), input = el('input'), output = el('output', project.appearance[key]);
    Object.assign(input, {type: 'range', min, max, step, value: project.appearance[key]});
    input.setAttribute('aria-label', title);
    input.oninput = () => {project.appearance[key] = Number(input.value); output.textContent = input.value; changed();};
    label.append(el('span', title), input, output); return label;
}

const roomText=(key,values={})=>MI18n.t('pearl28.'+key,values);
const roomKey=destination=>destination.key||destination.projectId;
const selectedRoomKeys=()=>[...(project?.spawnProjects||[]),...(project?.spawnRooms||[]).map(name=>'room:'+name)];
function positionValue(){return positionProject.startsWith('room:')?project?.spawnRoomPositions?.[positionProject.slice(5)]:project?.spawnPositions?.[positionProject];}
function positionStore(){const room=positionProject.startsWith('room:');project[room?'spawnRoomPositions':'spawnPositions']??={};return [project[room?'spawnRoomPositions':'spawnPositions'],room?positionProject.slice(5):positionProject];}
function roomOption(destination,checked){
    const label=el('label',undefined,'room-option'),checkbox=el('input'),key=roomKey(destination);checkbox.type='checkbox';checkbox.checked=checked;
    checkbox.setAttribute('aria-label',destination.entry+(destination.name===destination.entry?'':' '+destination.name));MI18n.content(checkbox);
    const words=el('span',undefined,'room-label');words.append(MI18n.content(el('span',destination.entry,'room-name')),MI18n.content(el('span',destination.name===destination.entry?'':destination.name,'room-code')));
    checkbox.onchange=()=>{
        if(key.startsWith('room:')){const name=key.slice(5);project.spawnRooms=(project.spawnRooms||[]).filter(id=>id!==name);if(checkbox.checked)project.spawnRooms.push(name);else if(project.spawnRoomPositions)delete project.spawnRoomPositions[name];}
        else{project.spawnProjects=project.spawnProjects.filter(id=>id!==key);if(checkbox.checked)project.spawnProjects.push(key);else if(project.spawnPositions)delete project.spawnPositions[key];}
        changed();renderRooms();
    };label.append(checkbox,words);return label;
}
function renderRooms(){
    const visible=destinations.filter(d=>!deletedProject(d.ownerProjectId||d.projectId)&&!deletedRooms.has(d.entry));
    const byId=new Map(visible.map(d=>[roomKey(d),d]));for(const destination of visible)if(!byId.has('room:'+destination.entry))byId.set('room:'+destination.entry,{...destination,key:'room:'+destination.entry,projectId:''});
    const chosen=selectedRoomKeys().filter(id=>id.startsWith('room:')?!deletedRooms.has(id.slice(5)):!deletedProject(id)).map(id=>byId.get(id)||{key:id,projectId:id.startsWith('room:')?'':id,name:id,entry:id.startsWith('room:')?id.slice(5):'房间暂不可用'}),selected=new Set(chosen.map(d=>d.entry));
    $('spawnCount').textContent='已选 '+chosen.length+' 个房间';$('selectedRooms').replaceChildren(el('h3','已选房间'),...chosen.map(d=>roomOption(d,true)));if(!chosen.length)$('selectedRooms').append(el('p','尚未选择生成房间','room-empty'));
    const query=$('roomSearch').value.trim().toLocaleLowerCase(),remaining=visible.filter(d=>!selected.has(d.entry)&&(d.name+' '+d.entry+' '+d.projectId).toLocaleLowerCase().includes(query)),groups=new Map();
    for(const d of remaining){const key=d.priority?'preferred':d.region||d.entry.split('_')[0];if(!groups.has(key))groups.set(key,[]);groups.get(key).push(d);}
    $('roomResults').replaceChildren();
    for(const [key,rooms] of [...groups].sort(([a],[b])=>Number(b==='preferred')-Number(a==='preferred')||a.localeCompare(b))){
        const details=el('details',undefined,'room-group'),name=key==='preferred'?roomText('preferred'):key+' '+roomText('regionRooms');details.open=!!query||(groupOpen.get(key)??key==='preferred');const body=el('div');details.append(el('summary',name+'（'+rooms.length+'）'),body);let rendered=false;
        const populate=()=>{if(rendered||!details.open)return;rendered=true;body.append(...rooms.map(d=>roomOption(d,false)));};populate();details.ontoggle=()=>{populate();if(!query)groupOpen.set(key,details.open);};$('roomResults').append(details);
    }
    if(!remaining.length)$('roomResults').append(el('p',query?'没有匹配的未选房间':'没有其他房间','room-empty'));
    renderPositionRooms(chosen);
}
function renderPositionRooms(chosen){
    $('spawnPositionPanel').hidden=false;$('positionRoom').disabled=$('refreshPosition').disabled=!chosen.length;$('positionRoom').replaceChildren(...chosen.map(item=>MI18n.content(option(roomKey(item),item.entry+(item.name===item.entry?'':' '+item.name)))));
    const next=chosen.some(item=>roomKey(item)===positionProject)?positionProject:chosen.length?roomKey(chosen[0]):'';$('positionRoom').value=next;
    if(next!==positionProject){positionProject=next;loadPositionGeometry();}else drawPosition();
}
async function loadPositionGeometry(){
    const request=++positionLoad,id=positionProject;positionGeometry=null;drawPosition();
    if(!id)return;$('spawnPositionState').textContent=positionText('loading');
    try{const result=await api('pearl-room?'+(id.startsWith('room:')?'room='+encodeURIComponent(id.slice(5)):'projectId='+encodeURIComponent(id)));if(request!==positionLoad||positionProject!==id)return;positionGeometry=result;drawPosition();}
    catch(error){if(request===positionLoad){$('spawnPositionState').textContent=error.message;notice(error.message,true);}}
}
function drawPosition(preserveId=null){
    const canvas=$('spawnMap'),ctx=canvas.getContext?.('2d');positionMap=null;MI18n.content($('spawnPositionState'));if(!ctx)return;
    ctx.clearRect(0,0,canvas.width,canvas.height);ctx.fillStyle='#111';ctx.fillRect(0,0,canvas.width,canvas.height);
    const g=positionGeometry,position=positionValue();
    for(const [id,key] of [['spawnX','x'],['spawnY','y']]){$(id).disabled=!g;$(id).required=!!position;if(id!==preserveId)$(id).value=position?Number((position[key]*100).toFixed(4)):'';}
    $('autoPosition').disabled=!position;$('spawnPositionState').textContent=g?positionText('automatic'):positionText('chooseRoom');
    if(!g)return;
    const s=Math.min((canvas.width-24)/g.width,(canvas.height-24)/g.height),ox=(canvas.width-g.width*s)/2,oy=(canvas.height-g.height*s)/2;
    positionMap={s,ox,oy,w:g.width,h:g.height,canvasWidth:canvas.width,canvasHeight:canvas.height};
    ctx.fillStyle='#686868';for(const [x,y] of g.solids)ctx.fillRect(ox+x*s,oy+(g.height-y-1)*s,Math.ceil(s),Math.ceil(s));
    ctx.strokeStyle='#666';ctx.strokeRect(ox,oy,g.width*s,g.height*s);ctx.setLineDash([4,4]);
    for(const [x,y] of g.cameras||[])ctx.strokeRect(ox+x/20*s,oy+(g.height-(y+800)/20)*s,70*s,40*s);
    ctx.setLineDash([]);ctx.fillStyle='#bdbdbd';for(const [x,y] of g.shortcuts||[])ctx.fillRect(ox+x*s,oy+(g.height-y-1)*s,Math.max(2,s),Math.max(2,s));
    if(!position)return;
    const x=ox+position.x*g.width*s,y=oy+(1-position.y)*g.height*s;
    MIPearlIcons.drawAt(ctx,Math.round(x),Math.round(y),9,project.appearance,{variant:'map'});
    ctx.strokeStyle='#fff';ctx.lineWidth=1;ctx.beginPath();
    ctx.moveTo(x-10,y);ctx.lineTo(x-7,y);ctx.moveTo(x+7,y);ctx.lineTo(x+10,y);
    ctx.moveTo(x,y-10);ctx.lineTo(x,y-7);ctx.moveTo(x,y+7);ctx.lineTo(x,y+10);ctx.stroke();
    const px=position.x*g.width*20,py=position.y*g.height*20,solid=g.solids.some(tile=>tile[0]===Math.floor(px/20)&&tile[1]===Math.floor(py/20));
    $('spawnPositionState').textContent=positionText('coordinates',{x:Number(px.toFixed(1)),y:Number(py.toFixed(1))})+(solid?' · '+positionText('solid'):'');
}
function setPosition(value,preserveId=null){if(!positionProject||!selectedRoomKeys().includes(positionProject))return;const [store,key]=positionStore();store[key]=value;changed();drawPosition(preserveId);}
function pointerPosition(event){if(!positionMap||busy)return;setPosition(MIPearlBranches.positionAt(event.clientX,event.clientY,$('spawnMap').getBoundingClientRect(),positionMap,project.appearance.size));}
$('positionRoom').onchange=()=>{positionProject=$('positionRoom').value;loadPositionGeometry();};
$('refreshPosition').onclick=loadPositionGeometry;
$('autoPosition').onclick=()=>{const [store,key]=positionStore();delete store[key];changed();drawPosition();};
$('spawnMap').onpointerdown=event=>{if(event.button!==0||!positionMap||busy)return;event.preventDefault();positionPointer=event.pointerId;$('spawnMap').setPointerCapture(event.pointerId);pointerPosition(event);};
$('spawnMap').onpointermove=event=>{if(positionPointer===event.pointerId)pointerPosition(event);};
$('spawnMap').onpointerup=$('spawnMap').onpointercancel=$('spawnMap').onlostpointercapture=()=>{positionPointer=null;};
$('spawnMap').onkeydown=event=>{if(!positionGeometry||!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key))return;event.preventDefault();const p={...(positionValue()||{x:.5,y:.5})};const key=event.key==='ArrowLeft'||event.key==='ArrowRight'?'x':'y',sign=event.key==='ArrowLeft'||event.key==='ArrowDown'?-1:1,dimension=positionGeometry[key==='x'?'width':'height']*20,margin=5*project.appearance.size/dimension;p[key]=Math.max(margin,Math.min(1-margin,p[key]+sign*(event.shiftKey?20:1)/dimension));setPosition(p);};
for(const [id,key] of [['spawnX','x'],['spawnY','y']]){
    $(id).oninput=()=>{const input=$(id),value=Number(input.value);if(input.value===''||!Number.isFinite(value)||value<0||value>100)return;setPosition({...positionValue()||{x:.5,y:.5},[key]:value/100},id);};
    $(id).onchange=()=>{if(!$(id).checkValidity())notice(positionText('invalid'),true);else drawPosition();};
}

function render() {
    if (!project) return;
    renderCollections();
    $('pearlId').value = project.id; $('pearlId').disabled = project.revision > 0;
    $('name').value = project.name; $('notes').value = project.notes;
    $('identity').textContent = '内部 ID：' + project.uid;
    appearance();
    const visibleReaders=project.readers.map((binding,index)=>({binding,index})).filter(({binding})=>!deletedProject(binding.projectId));
    if(!visibleReaders.some(({index})=>index===readerIndex))readerIndex=visibleReaders[0]?.index??-1;
    $('readers').replaceChildren(...visibleReaders.map(({binding,index})=>option(index,readerLabel(binding.projectId))));
    if(!visibleReaders.length)$('readers').append(option('', '尚未添加读取者'));
    $('readers').disabled=!visibleReaders.length;$('readers').value=visibleReaders.length?readerIndex:'';
    $('readerAffinity').value=affinityTier;$('readerAffinity').disabled=!reader();
    $('empty').hidden = !!reader(); $('readerEditor').hidden = !reader(); $('unbind').disabled = !reader();
    $('candidate').replaceChildren(...projects.filter(p => !deletedProject(p.projectId)&&!project.readers.some(r => r.projectId === p.projectId)).map(p => option(p.projectId, p.name)));
    $('bind').disabled = !$('candidate').options.length;
    renderRooms(); renderReader(); updateHeadings();
}
function clearLineDrop() {
    for (const card of $('lines').children) card.classList.remove('drop-before', 'drop-after');
}
function endLineDrag() {
    const previous = draggingLine;
    draggingLine = null;
    if (previous?.handle.hasPointerCapture(previous.pointerId)) previous.handle.releasePointerCapture(previous.pointerId);
    clearLineDrop();
    for (const card of $('lines').children) card.classList.remove('dragging');
}
function lineDropAt(event) {
    const host = $('lines'), cards = [...host.children], bounds = host.getBoundingClientRect();
    if (!cards.length || event.clientX < bounds.left || event.clientX > bounds.right) return null;
    const before = cards.findIndex(card => {const rect = card.getBoundingClientRect(); return event.clientY < rect.top + rect.height / 2;});
    return before < 0 ? {index: cards.length, card: cards.at(-1), after: true} : {index: before, card: cards[before], after: false};
}
function moveLine(lines, line, to) {
    if (busy || lines !== lineList()) return;
    const from = lines.indexOf(line);
    if (from < 0 || to < 0 || to >= lines.length || from === to) return;
    stop();
    lines.splice(from, 1); lines.splice(to, 0, line);
    changedLines(); renderReader();
    $('lines').children[to]?.querySelector('.line-drag-handle')?.focus();
}
function lineCard(line, index, lines) {
    const card = el('details', undefined, 'line');
    card.open = expandedLines.has(line);
    card.ontoggle = () => card.open ? expandedLines.add(line) : expandedLines.delete(line);
    const summary = el('summary', undefined, 'line-summary');
    const handle = el('button', '⠿', 'line-drag-handle');
    handle.type = 'button';
    handle.title = '拖动调整顺序；也可用方向键上下移动';
    handle.setAttribute('aria-label', '拖动第 ' + (index + 1) + ' 句调整顺序');
    handle.onclick = event => {event.preventDefault(); event.stopPropagation();};
    handle.onpointerdown = event => {
        if (event.button !== 0 || busy || lines !== lineList()) return;
        event.preventDefault(); event.stopPropagation(); endLineDrag();
        draggingLine = {lines, line, handle, pointerId: event.pointerId, x: event.clientX, y: event.clientY, active: false};
        handle.focus(); handle.setPointerCapture(event.pointerId);
    };
    handle.onpointermove = event => {
        const drag = draggingLine;
        if (!drag || drag.handle !== handle || drag.pointerId !== event.pointerId) return;
        if (!drag.active && Math.hypot(event.clientX - drag.x, event.clientY - drag.y) < 5) return;
        drag.active = true; card.classList.add('dragging'); event.preventDefault();
        clearLineDrop(); const drop = lineDropAt(event);
        if (drop) drop.card.classList.add(drop.after ? 'drop-after' : 'drop-before');
    };
    handle.onpointerup = event => {
        const drag = draggingLine;
        if (!drag || drag.handle !== handle || drag.pointerId !== event.pointerId) return;
        const drop = drag.active ? lineDropAt(event) : null, from = lines.indexOf(line);
        event.preventDefault(); endLineDrag();
        if (drop) moveLine(lines, line, drop.index - (from < drop.index ? 1 : 0));
    };
    handle.onpointercancel = handle.onlostpointercapture = endLineDrag;
    handle.ondragstart = event => event.preventDefault();
    handle.onkeydown = event => {
        if (!['ArrowUp', 'ArrowDown'].includes(event.key)) return;
        event.preventDefault(); event.stopPropagation();
        moveLine(lines, line, lines.indexOf(line) + (event.key === 'ArrowUp' ? -1 : 1));
    };
    const snippet = el('span', line.text.trim() || '空白台词 · 点击编辑', 'line-snippet');if(line.text.trim())MI18n.content(snippet);
    const timing = el('span', line.hold + ' 秒', 'line-timing');
    summary.append(handle, el('span', '第 ' + (index + 1) + ' 句', 'line-number'), snippet, timing);
    const body = el('div', undefined, 'line-body'), actions = el('details', undefined, 'line-actions');
    const menuTitle = el('summary', '操作');
    menuTitle.setAttribute('aria-label', '第 ' + (index + 1) + ' 句操作');
    actions.append(menuTitle);
    const menu = el('div', undefined, 'line-menu');
    const remove = el('button', '删除…', 'danger'), confirmation = el('div', undefined, 'line-delete-confirm');
    confirmation.hidden = true; confirmation.setAttribute('role', 'group');
    const confirmDelete = el('button', '确认删除', 'danger'), cancel = el('button', '取消');
    confirmation.append(el('span', '删除第 ' + (index + 1) + ' 句？'), confirmDelete, cancel);
    remove.onclick = () => {confirmation.hidden = false; actions.open = false; cancel.focus();};
    cancel.onclick = () => {confirmation.hidden = true; menuTitle.focus();};
    confirmDelete.onclick = () => {stop(); lines.splice(index, 1); changedLines(); renderReader(); $('addLine').focus();};
    menu.append(remove); actions.append(menu);
    const text = el('textarea');
    Object.assign(text, {value: line.text, maxLength: 2000, rows: 3});
    text.setAttribute('aria-label', '第 ' + (index + 1) + ' 句');
    text.oninput = () => {line.text = text.value; snippet.toggleAttribute('data-i18n-content',!!line.text.trim());snippet.textContent = line.text.trim() || '空白台词 · 点击编辑'; changedLines();};
    const timingFields = el('div', undefined, 'bar line-time-fields');
    for (const [key, title, min] of [['hold', '停留', .1], ['gap', '间隔', 0]]) {
        const label = el('label', title), input = el('input');
        Object.assign(input, {type: 'number', min, max: 60, step: .1, value: line[key], required: true});
        input.setAttribute('aria-label', '第 ' + (index + 1) + ' 句' + title + '（秒）');
        input.oninput = () => {
            if (input.value === '' || !input.checkValidity()) return;
            line[key] = Number(input.value); timing.textContent = line.hold + ' 秒'; changedLines();
        };
        label.append(input, document.createTextNode('秒')); timingFields.append(label);
    }
    const standalone=line.kind==='action';
    const before=el('details',undefined,'mi-before-action');before.open=PearlActions.normalize(line.beforeAction).type!=='none';before.append(el('summary','句前动作'),PearlActions.create(line.beforeAction,value=>{line.beforeAction=value;changedLines();},{label:'句前动作'}));
    const actionFields=PearlActions.create(line.action,value=>{line.action=value;changedLines();},{label:standalone?'独立动作':'句末动作'});
    const after=el('details',undefined,'mi-after-action');after.open=PearlActions.normalize(line.action).type!=='none';after.append(el('summary','句末动作'),actionFields);
    if(standalone){snippet.textContent='独立动作';timing.textContent='';body.append(actions,confirmation,actionFields);}else body.append(actions,confirmation,text,timingFields,before,after,PearlPresentation.create(line.presentation,value=>{line.presentation=value;changedLines();}));
    card.append(summary, body); return card;
}
function renderReader() {
    endLineDrag();
    updateHeadings();
    renderVariantTools();
    if (!reader() || !common()) return;
    const binding = branch(), shared = common();
    const readonly=missingVariant()&&!commonStage()||commonStage()&&archivedShared();
    for(const id of ['preventRepeat','manyEnabled','leavePolicy'])$(id).disabled=archivedShared();
    $('sharedHelp').inert=archivedShared();
    $('lines').inert=readonly;$('poolTools').inert=readonly;$('privateRepeat').disabled=missingVariant();
    $('privateRepeat').checked = !!binding.repeatEnabled;
    $('prependCommonRepeat').checked=!!binding.repeatPrependCommon;$('prependCommonRepeat').disabled=missingVariant()||!binding.repeatEnabled;$('prependCommonRepeatField').hidden=!binding.repeatEnabled;
    $('threshold').value = shared.manyThreshold;
    $('preventRepeat').checked = shared.preventSameCycleRepeat;
    $('manyEnabled').checked = shared.manyEnabled;
    $('threshold').disabled = archivedShared() || !shared.manyEnabled;
    $('sharedHelp').hidden = !commonStage();
    $('repeatOptions').hidden = stage !== 'repeat';
    $('manyOptions').hidden = stage !== 'many';
    $('leaveOptions').hidden = !['leaving', 'returning'].includes(stage);
    $('dialogueLink').href = '/dialogue?id=' + encodeURIComponent(reader().projectId) + '&stage=' + ({repeat: 'pearlRepeat', many: 'pearlMany', leaving: 'pearlLeaving', returning: 'pearlReturning'}[stage] || 'first');
    $('leavePolicy').value = shared.leavePolicy;
    for (const button of $('stages').children) {
        const selected = button.dataset.stage === stage;
        button.classList.toggle('selected', selected);
        button.setAttribute('aria-pressed', selected);
    }
    $('poolTools').hidden = !isPool();
    if (isPool()) {
        const pool = stageData()[stage];
        poolIndex = Math.max(0, Math.min(poolIndex, pool.length - 1));
        $('pool').replaceChildren(...pool.map((item, i) => option(i, item.name)));
        if (!pool.length) $('pool').append(option('', '尚无随机组'));
        $('pool').value = pool.length ? poolIndex : '';
        $('pool').disabled = !pool.length;
        $('poolName').value = pool[poolIndex]?.name || '';
        $('poolName').disabled = $('removePool').disabled = !pool.length;
    }
    const lines = lineList() || [];
    $('lines').replaceChildren(...lines.map((line, i) => lineCard(line, i, lines)));
    if (!lines.length) $('lines').append(el('p', isPool() && !stageData()[stage].length ? '先添加一个随机组' : '还没有台词', 'line-empty'));
    $('addLine').disabled = readonly || isPool() && !stageData()[stage].length;
    $('addAction').disabled=$('addLine').disabled;
    renderPearlAction();renderReaderPresentation();
}
function renderReaderPresentation(){
    const host=$('readerPresentation');host.hidden=commonStage();
    host.replaceChildren(PearlPresentation.create(branch()?.presentation,value=>{if(!reader()||missingVariant())return;branch().presentation=value;changed();},{label:'本珍珠读取表现',mode:true}));
    host.inert=missingVariant();
}
function readingPresentationLayers(){return [common()?.presentation,reader()?.presentation,branch()!==reader()?branch()?.presentation:null];}
function showPearlPresentation(value){$('pearlPresentationState').textContent=PearlPresentation.describe(value);MI18n.content($('pearlPresentationState'));}
function renderVariantTools(){
    const visible=!!reader()&&affinityTier!=='general';
    $('affinityVariantTools').hidden=!visible;$('removeAffinityConfirm').hidden=true;
    $('createAffinityVariant').hidden=!missingVariant();$('removeAffinityVariant').hidden=missingVariant();
    $('affinityVariantState').textContent=affinityText(missingVariant()?'fallback':'enabled');
}
function pearlActionTarget(){return isPool()?{owner:stageData()?.[stage]?.[poolIndex],key:'action'}:{owner:branch(),key:'readAction'};}
function renderPearlAction(){
    const {owner,key}=pearlActionTarget();
    $('pearlActionOptions').replaceChildren(MIActionEditor.create(owner?.[key],value=>{if(owner){owner[key]=value;changedLines();}},{label:'组结束动作'}));
    $('pearlActionOptions').inert=!owner||missingVariant()&&!commonStage()||commonStage()&&archivedShared();
    $('pearlActionDetails').open=!!owner&&owner[key]?.type!=='none'&&!!owner[key]?.type;
}
$('readerAffinity').onchange=()=>{stop();affinityTier=$('readerAffinity').value;poolIndex=0;lastPool={};renderReader();};
$('createAffinityVariant').onclick=()=>{
    if(!reader()||!missingVariant())return;
    reader().affinity??={};reader().affinity[affinityTier]=MIPearlBranches.clone(reader(),()=>crypto.randomUUID().replaceAll('-',''));
    stop();poolIndex=0;changed();renderReader();
};
$('removeAffinityVariant').onclick=()=>{$('removeAffinityConfirm').hidden=false;$('cancelRemoveAffinity').focus();};
$('cancelRemoveAffinity').onclick=()=>$('removeAffinityConfirm').hidden=true;
$('confirmRemoveAffinity').onclick=()=>{if(!reader()?.affinity)return;delete reader().affinity[affinityTier];if(!Object.keys(reader().affinity).length)delete reader().affinity;stop();poolIndex=0;changed();renderReader();};
function renderSaved() {
    $('saved').replaceChildren(option('', '切换珍珠'), ...saved.map(p => MI18n.content(option(p.id, p.id + '／' + p.name))));
    $('saved').value = project?.id || '';
}
function renderCollections() {
    if(!collectionCatalog.projects.length)return;
    $('collections').replaceChildren(...collectionCatalog.projects.map(item=>MI18n.content(option(item.id,item.name))));
    $('collections').value=collectionId;
    const active=collectionCatalog.projects.find(item=>item.id===collectionCatalog.activeId);
    $('collectionActive').replaceChildren();$('collectionActive').hidden=collectionCatalog.activeId===collectionId;
    if(!$('collectionActive').hidden)$('collectionActive').append(el('span',MI18n.t('pearl.ui.activeGame',{name:active?.name||collectionCatalog.activeId})));
    $('collections').title=collectionCatalog.projects.find(item=>item.id===collectionId)?.name||'';
    $('activateCollection').disabled=busy||collectionId===collectionCatalog.activeId;
    const params=new URLSearchParams(location.search);params.set('collectionId',collectionId);params.set('lang',MI18n.locale);history.replaceState(null,'','?'+params);
}
async function list() {saved = await api(collectionQuery('pearls'));renderSaved();}
async function preparePearl(candidate) {
    const next=structuredClone(candidate),profiles={};
    if (!next.appearance || !Array.isArray(next.readers) || !Array.isArray(next.spawnProjects)) throw Error('珍珠项目内容不完整');
    next.spawnPositions??={};for(const binding of next.readers){binding.repeatEnabled??=false;binding.repeatPrependCommon??=false;binding.repeat??=[];}
    await ensureShared(next,profiles);return {next,profiles};
}
function adoptPearl(prepared, imported=false) {
    stop();positionProject='';positionGeometry=null;positionMap=null;positionLoad++;project=prepared.next;sharedProfiles=prepared.profiles;lastPool={};expandedLines=new WeakSet();
    dirty=imported;readerIndex=poolIndex=0;affinityTier='general';$('readerAffinity').value=affinityTier;stage='read';$('roomSearch').value='';render();$('saved').value=project.id;
    state(dirty||!project.revision?'未保存更改':'已保存',dirty||!project.revision?'dirty':'saved');notice();
    window.MIUndo?.reset();
}
async function switchCollection(id, confirmed=false) {
    if(busy)return false;
    if(!collectionCatalog.projects.some(item=>item.id===id))throw Error(collectionText('missing'));
    if(!confirmed&&dirty&&!confirm(collectionText('discard'))){$('collections').value=collectionId;return false;}
    setBusy(true);
    try{
        const nextSaved=await api(collectionQuery('pearls',id)),candidate=nextSaved[0]||await api(collectionQuery('pearl-default',id));
        const prepared=await preparePearl(candidate);
        collectionId=id;saved=nextSaved;renderSaved();adoptPearl(prepared);return true;
    }catch(error){$('collections').value=collectionId;throw error;}finally{setBusy(false);renderCollections();}
}
function collectionDialog(mode) {
    if(busy)return;collectionDialogMode=mode;$('moreMenu').open=false;
    $('collectionDialogTitle').textContent=collectionText(mode==='new'?'new':'rename');
    $('collectionName').value=mode==='new'?'':collectionCatalog.projects.find(item=>item.id===collectionId)?.name||'';
    $('collectionError').textContent='';$('collectionDialog').showModal();$('collectionName').focus();
}
$('collections').onchange=run(()=>switchCollection($('collections').value));
$('newCollection').onclick=()=>collectionDialog('new');$('renameCollection').onclick=()=>collectionDialog('rename');
$('cancelCollection').onclick=()=>$('collectionDialog').close();
$('collectionForm').onsubmit=async event=>{
    event.preventDefault();const name=$('collectionName').value.trim();if(!name)return $('collectionName').reportValidity();
    if(collectionDialogMode==='new'&&dirty&&!confirm(collectionText('discard')))return;
    $('confirmCollection').disabled=true;$('collectionError').textContent='';
    try{
        const request=collectionDialogMode==='new'?{name}:{id:collectionId,name};
        const previous=new Set(collectionCatalog.projects.map(item=>item.id));
        collectionCatalog=await api('pearl-projects',request);
        $('collectionDialog').close();renderCollections();
        if(collectionDialogMode==='new'){
            const created=collectionCatalog.projects.find(item=>!previous.has(item.id));if(!created)throw Error(collectionText('missing'));
            await switchCollection(created.id,true);
        }
    }catch(error){if($('collectionDialog').open)$('collectionError').textContent=error.message;else notice(error.message,true);}finally{$('confirmCollection').disabled=false;}
};
$('activateCollection').onclick=run(async()=>{
    if(busy)return;
    if(dirty){await save(true);return;}
    setBusy(true);
    try{collectionCatalog=await api('pearl-projects/activate',{id:collectionId});renderCollections();notice(collectionText('activated'));$('moreMenu').open=false;}
    finally{setBusy(false);}
});
function validateInputs() {
    for (const input of document.querySelectorAll('main input')) {
        if (!input.disabled && !input.closest('[hidden]') && !input.checkValidity()) {
            let parent = input.parentElement;
            while (parent) {if (parent.tagName === 'DETAILS') parent.open = true; parent = parent.parentElement;}
            input.reportValidity(); throw Error('请检查标出的输入项。');
        }
    }
}
async function writeShared(id, profile, apply) {
    try {
        const result = await api('dialogue', {projectId: id, dialogue: profile.dialogue, revision: profile.revision, apply});
        profile.revision = result.revision; if (result.dialogue) profile.dialogue = result.dialogue; profile.dirty = false;
    } catch (error) {
        // An apply error can occur after the server has saved the dialogue.
        // Only adopt that revision if the stored content is exactly our submission.
        try {
            const stored = await api('dialogue?id=' + encodeURIComponent(id));
            if (JSON.stringify(stored.dialogue) === JSON.stringify(profile.dialogue)) {
                profile.revision = stored.revision; profile.dirty = false;
            }
        } catch (_) {}
        throw error;
    }
}
function contentKey(value) {
    if (Array.isArray(value)) return value.map(contentKey);
    if (value && typeof value === 'object') return Object.fromEntries(Object.keys(value).sort().map(key => [key, contentKey(value[key])]));
    return value;
}
async function writePearl(apply) {
    try {return (await api(apply ? 'pearl-apply' : 'pearl-save', project)).project;}
    catch (error) {
        try {
            const stored = (await api(collectionQuery('pearls'))).find(p => p.id === project.id && p.uid === project.uid);
            const withoutRevision = p => {const clone = structuredClone(p); delete clone.revision; delete clone.updatedAt; return JSON.stringify(contentKey(clone));};
            if (stored && withoutRevision(stored) === withoutRevision(project)) project = stored;
        } catch (_) {}
        throw error;
    }
}
async function save(apply = false, alreadyLocked = false) {
    if (busy && !alreadyLocked || !project) return false;
    validateInputs(); setBusy(true); state(apply ? '正在保存并应用…' : '正在保存…', 'saving'); notice();
    try {
        // A different studio tab can delete or restore an iterator after this
        // pearl was opened. Refresh status without replacing unsaved wording.
        await refreshProjectAvailability();
        for (const [id, profile] of Object.entries(sharedProfiles)) {
            if (!profile.deleted && (profile.dirty || apply && project.readers.some(r => r.projectId === id))) await writeShared(id, profile, apply);
        }
        project = await writePearl(apply);
        const pending=Object.entries(sharedProfiles).filter(([,profile])=>profile.deleted&&profile.dirty);
        dirty = pending.length>0; expandedLines = new WeakSet();
        if(apply)collectionCatalog=await api('pearl-projects');
        await list(); render();
        if(pending.length){
            state(MI18n.t(apply?'pearl.lifecycle.appliedPending':'pearl.lifecycle.savedPending'),'dirty');
            notice(MI18n.t('pearl.lifecycle.sharedPending',{names:pending.map(([id,profile])=>profile.name||id).join('、')}),true);
        }else{
            state(apply ? '已应用到游戏' : '已保存', apply ? 'applied' : 'saved');
            notice(apply ? '已写入游戏数据；将在所选房间生成珍珠。' : '已保存编辑内容，尚未应用到游戏。');
        }
        return true;
    } catch (error) {
        state('未完成 · 请重试', 'error'); throw error;
    } finally {window.MIUndo?.rebase();if (!alreadyLocked) setBusy(false);}
}
async function open(candidate, imported = false) {
    if (busy) return;
    if (dirty && !confirm('放弃当前未保存更改并切换珍珠？')) {$('saved').value = project?.id || ''; return;}
    setBusy(true);
    try {
        const prepared=await preparePearl(typeof candidate === 'function' ? await candidate() : candidate);
        adoptPearl(prepared,imported);
    } catch (error) {$('saved').value = project?.id || ''; throw error;}
    finally {setBusy(false);}
}

$('saved').onchange = run(async () => {const selected = saved.find(p => p.id === $('saved').value); if (selected) await open(selected);});
$('new').onclick = run(async () => {await open(() => api(collectionQuery('pearl-default'))); $('moreMenu').open = false;});
$('save').onclick = run(() => save());
$('apply').onclick = run(() => save(true));
$('pearlId').oninput = () => {project.id = $('pearlId').value.toUpperCase(); $('pearlId').value = project.id; changed();};
$('name').oninput = () => {project.name = $('name').value; changed();};
$('notes').oninput = () => {project.notes = $('notes').value; changed();};
$('bind').onclick = run(async () => {
    const id = $('candidate').value;
    if (busy || !id || project.readers.some(r => r.projectId === id)) return;
    setBusy(true);
    try {
        const binding = await api('pearl-reader?id=' + encodeURIComponent(id));
        if (!sharedProfiles[id]) sharedProfiles[id] = await api('dialogue?id=' + encodeURIComponent(id));
        project.readers.push(binding); readerIndex = project.readers.length - 1; affinityTier='general'; poolIndex = 0;
        stop(); changed(); render();
        $('candidate').closest('details').open = false;
    } finally {setBusy(false);}
});
$('unbind').onclick = () => {
    if (!reader() || !confirm('移除「' + readerName() + '」与 ' + project.id + ' 的绑定？此珍珠中为该读取者编写的台词会一并移除。')) return;
    project.readers.splice(readerIndex, 1); stop(); changed(); render();
};
$('readers').onchange = () => {stop(); readerIndex = Number($('readers').value); affinityTier='general';$('readerAffinity').value=affinityTier;poolIndex = 0; lastPool = {}; renderReader();};
$('prependCommonRepeat').onchange=()=>{branch().repeatPrependCommon=$('prependCommonRepeat').checked;changed();};
$('privateRepeat').onchange = () => {branch().repeatEnabled = $('privateRepeat').checked; poolIndex = 0; changed(); renderReader();};
$('preventRepeat').onchange = () => {common().preventSameCycleRepeat = $('preventRepeat').checked; changed(true);};
$('manyEnabled').onchange = () => {common().manyEnabled = $('manyEnabled').checked; $('threshold').disabled = !common().manyEnabled; changed(true);};
$('threshold').oninput = () => {if ($('threshold').value !== '' && $('threshold').checkValidity()) {common().manyThreshold = Number($('threshold').value); changed(true);}};
$('leavePolicy').onchange = () => {common().leavePolicy = $('leavePolicy').value; changed(true);};
for (const button of $('stages').children) button.onclick = () => {stage = button.dataset.stage; poolIndex = 0; renderReader();};
$('pool').onchange = () => {poolIndex = Number($('pool').value); renderReader();};
$('poolName').oninput = () => {
    stageData()[stage][poolIndex].name = $('poolName').value;
    $('pool').selectedOptions[0].textContent = $('poolName').value; changedLines();
};
$('addPool').onclick = () => {const pool = stageData()[stage]; pool.push({name: MI18n.t('default.pool_name', {index: pool.length + 1}), lines: []}); poolIndex = pool.length - 1; changedLines(); renderReader();};
$('removePool').onclick = () => {
    if (!confirm('删除当前随机组及其中所有台词？')) return;
    stageData()[stage].splice(poolIndex, 1); changedLines(); renderReader();
};
$('addLine').onclick = () => {
    const lines = lineList(); if (!lines) return;
    const line = {lineId: crypto.randomUUID().replaceAll('-', ''), text: '', hold: 2.5, gap: .6}; lines.push(line); expandedLines.add(line);
    changedLines(); renderReader();
    $('lines').lastElementChild.querySelector('textarea').focus();
};
$('addAction').onclick=()=>{const lines=lineList();if(!lines||lines.length>=200)return;const line={lineId:crypto.randomUUID().replaceAll('-',''),kind:'action',text:'',hold:.1,gap:0,action:{type:'liftSpinPlayer',delay:0,duration:3}};lines.push(line);expandedLines.add(line);changedLines();renderReader();};
$('roomSearch').oninput = renderRooms;
$('refreshRooms').onclick=run(async()=>{await refreshProjectAvailability(true);if(positionProject)await loadPositionGeometry();});
function updateSpawnToggle(){const collapsed=$('spawnPanel').hidden;$('toggleSpawn').textContent=collapsed?'▶':'▼';$('toggleSpawn').setAttribute('aria-label',MI18n.t(collapsed?'studio.navigation.expandSpawns':'studio.navigation.collapseSpawns'));}
MI18n.ready.then(updateSpawnToggle);window.addEventListener('mi-language-change',updateSpawnToggle);
$('toggleSpawn').onclick = () => {
    const collapsed = !$('spawnPanel').hidden;
    $('spawnPanel').hidden = collapsed;
    $('toggleSpawn').setAttribute('aria-expanded', !collapsed);
    updateSpawnToggle();
    document.querySelector('main').classList.toggle('spawn-collapsed', collapsed);
};
$('export').onclick = () => {
    const url = URL.createObjectURL(new Blob([JSON.stringify(project, null, 2)], {type: 'application/json'})), link = el('a');
    link.href = url; link.download = project.id + '.json'; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000); $('moreMenu').open = false;
};
$('import').onclick = () => {$('file').click(); $('moreMenu').open = false;};
$('file').onchange = run(async () => {
    const file = $('file').files[0]; if (!file) return;
    try {
        const imported = JSON.parse(await file.text());
        if (imported.schema !== 'moreiterators.pearl.v1') throw Error('不是珍珠项目文件');
        const defaults=await api(collectionQuery('pearl-default'));
        imported.uid=defaults.uid;imported.revision=0;imported.collectionId=collectionId;
        delete imported.runtimeId;delete imported.updatedAt;
        if(saved.some(item=>item.id===imported.id))imported.id=defaults.id;
        await open(imported, true);
    } finally {$('file').value = '';}
});
document.addEventListener('keydown', event => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
        event.preventDefault(); run(() => save(event.shiftKey))();
    }
    if (event.key === 'Escape') {endLineDrag(); $('moreMenu').open = false;}
});

let queue = [], current = null, responses = [], response = false, away = false, timer = null, lastPool = {}, actionPending=false;
function pickPool(source,key,layers=readingPresentationLayers()){
    const pool=(source||[]).filter(v=>v.lines.some(PearlActions.runnable));if(!pool.length)return [];
    const indices=pool.map((_,i)=>i).filter(i=>pool.length===1||i!==lastPool[key]);
    const index=indices[Math.floor(Math.random()*indices.length)];lastPool[key]=index;
    return MIPearlBranches.previewLines(pool[index].lines,pool[index].action,layers);
}
function pick(key){
    if(key==='repeat')return MIPearlBranches.repeatSources(branch(),common().repeat).flatMap((pool,index)=>pickPool(pool,key+':'+index));
    return pickPool(common()[key],key,key==='leaving'?[]:readingPresentationLayers());
}
function bodyLines(){return MIPearlBranches.previewLines(branch().read,branch().readAction,readingPresentationLayers());}
let activePreviewKind=null;
function previewButtons(kind){
    activePreviewKind=kind;
    for(const [id,event,label] of [['play','read','首次读取'],['playRepeat','repeat','本循环重复交付'],['playNextCycle','nextCycle','下个循环再次交付'],['playMany','many','多珍珠提示后读取']]){
        const button=$(id);button.textContent=kind===event?MI18n.t('pearl28.restartPreview'):MI18n.text(label);button.dataset.previewActive=String(kind===event);
    }
}
function stop() {
    previewButtons(null);clearTimeout(timer);queue=[];responses=[];current=null;away=false;actionPending=false;
    $('subtitle').textContent='……';$('playState').textContent='未开始';showPearlPresentation(null);
}
function simulatePearlActions(actions,complete,beforeLine=null){
    const action=actions.shift();if(!action){actionPending=false;complete();return;}
    actionPending=true;$('playState').textContent=MI18n.t('dialogue.social.actionWaiting',{seconds:action.delay||0});
    timer=setTimeout(()=>{
        $('playState').textContent=MI18n.text(PearlActions.labels[action.type]);
        timer=setTimeout(()=>{if(action.type==='killPlayer'){queue=[];responses=[];current=null;actionPending=false;previewButtons(null);$('playState').textContent=MI18n.t('dialogue.social.actionExecuted');showPearlPresentation(null);}
            else {if(beforeLine)beforeLine.beforeDone=(beforeLine.beforeDone||0)+1;simulatePearlActions(actions,complete,beforeLine);}},(PearlActions.seconds(action)-(action.delay||0))*1000);
    },(action.delay||0)*1000);
}
function next() {
    response=responses.length>0;current=response?responses.shift():away?null:queue.shift();
    if(!current){if(!away)previewButtons(null);$('playState').textContent=away?'暂停，等待返回':'读取结束，恢复工作';showPearlPresentation(null);return;}
    const line=current;
    const after=()=>{current=null;simulatePearlActions([...(line.previewActions||[])],()=>{timer=setTimeout(next,line.gap*1000);});};
    simulatePearlActions((line.previewBeforeActions||[]).slice(line.beforeDone||0),()=>{
      showPearlPresentation(line.previewPresentation);$('subtitle').textContent=line.text;$('playState').textContent=response?'临时回应':'读取内容';
      if(!line.text.trim()){after();return;}
      timer=setTimeout(after,line.hold*1000+line.text.length*70);
    },line);
}
function interrupt(lines) {
    clearTimeout(timer);if(current&&!response)queue.unshift(current);
    current=null;actionPending=false;responses=lines;next();
}
function play(kind) {
    if(!reader()||!common())return;
    stop();previewButtons(kind);const content=bodyLines(),prelude=content.length?pickPool(common()[$('previewStomachPearl').checked&&common().extractStomachPearl?'extractedPreRead':'preRead'],'prelude'):[],body=[...prelude,...content];
    queue=kind==='repeat'?[...pick('repeat'),...(common().preventSameCycleRepeat?[]:body)]
        :kind==='nextCycle'?[...pick('repeat'),...body]
        :kind==='many'?[...(common().manyEnabled?pick('many'):[]),...body]:body;
    next();
}
window.addEventListener('mi-language-change',()=>{showPearlPresentation(current?.previewPresentation);previewButtons(activePreviewKind);});
$('play').onclick=()=>play('read');$('playRepeat').onclick=()=>play('repeat');
$('playNextCycle').onclick=()=>play('nextCycle');$('playMany').onclick=()=>play('many');
$('stop').onclick=stop;
$('leave').onclick=()=>{away=true;interrupt(pick('leaving'));if(common().leavePolicy==='restart')queue=bodyLines();if(common().leavePolicy==='cancel')queue=[];};
$('return').onclick=()=>{away=false;interrupt(pick('returning'));};

function undoContent(){
    const value=structuredClone(project);for(const key of ['revision','updatedAt','runtimeId'])delete value[key];
    return {project:value,shared:Object.fromEntries(Object.entries(sharedProfiles).map(([id,profile])=>[id,structuredClone(profile.dialogue.pearlReading)]))};
}
window.MIUndo?.register({key:()=>project?'pearl:'+collectionId+':'+project.uid:'',capture:undoContent,busy:()=>busy||availabilityRunning,
 restore:snapshot=>{
    stop();positionLoad++;positionProject='';positionGeometry=null;positionMap=null;expandedLines=new WeakSet();lastPool={};
    const metadata={};for(const key of ['uid','collectionId','revision','updatedAt','runtimeId'])if(Object.hasOwn(project,key))metadata[key]=project[key];
    if(project.revision>0)metadata.id=project.id;
    project={...structuredClone(snapshot.project),...metadata};
    for(const [id,reading] of Object.entries(snapshot.shared)){const shared=sharedProfiles[id];if(shared&&JSON.stringify(shared.dialogue.pearlReading)!==JSON.stringify(reading)){shared.dialogue.pearlReading=structuredClone(reading);shared.dirty=true;}}
    render();changed();
 },onError:error=>notice(error.message,true)});
const canvas = $('preview'), ctx = canvas.getContext('2d');
function draw(time) {
    if (project) MIPearlIcons.pearl(canvas, project.appearance, {time,tight:true,halcyonPlaying:simulateHalcyon});
    else ctx.clearRect(0, 0, canvas.width, canvas.height);
    requestAnimationFrame(draw);
}
requestAnimationFrame(draw);
window.MIStudioPage={projectId:()=>reader()?.projectId||new URLSearchParams(location.search).get('project')||new URLSearchParams(location.search).get('projectId'),isBusy:()=>busy||availabilityRunning,
 saveBeforeNavigate:async()=>{if(dirty){await save(false);if(dirty)throw Error(MI18n.t('studio.navigation.sharedPending'));}return !dirty;},error:message=>notice(message,true)};
window.addEventListener('beforeunload', event => {if (dirty) {event.preventDefault(); event.returnValue = '';}});
if(typeof BroadcastChannel!=='undefined'){const lifecycle=new BroadcastChannel('mi-project-lifecycle');lifecycle.onmessage=event=>{if(event.data?.type==='changed')queueAvailabilityRefresh();};}
window.addEventListener('focus',()=>{if(project)queueAvailabilityRefresh();});
run(async () => {
    setBusy(true);
    try {
        const initial=await Promise.all([api('projects'), api('pearl-destinations'),api('project-trash')]);projects=initial[0];destinations=initial[1];rememberDeleted(initial[2]);
        collectionCatalog=await api('pearl-projects');
        const requested=new URLSearchParams(location.search).get('collectionId');
        const id=collectionCatalog.projects.some(item=>item.id===requested)?requested:collectionCatalog.activeId;
        busy=false;await switchCollection(id);
    } finally {setBusy(false);}
})();

window.addEventListener('mi-language-change',()=>{renderCollections();for(const input of document.querySelectorAll('#appearance input'))if(input.validity.customError)input.setCustomValidity(MI18n.text('请输入六位 Hex 颜色，如 #88bbff'));});

window.addEventListener('mi-language-change',()=>{if(project){appearance();renderRooms();}drawPosition();});

}
