'use strict';

// These pure functions are shared by preview, timeline, and the regression check.
const MIProjectionTimeline = (() => {
  const values = ['x', 'y', 'scale', 'rotation', 'opacity', 'brightness', 'flicker'];
  const end = track => Number(track.delay || 0) + (track.frames || []).reduce((sum, frame) => sum + Number(frame.duration || 0), 0);
  const duration = group => Math.max(0, ...(group?.tracks || []).map(end));
  const frameTime = (track, index) => Number(track.delay || 0) + (index > 0 ? track.frames.slice(0, index + 1).reduce((sum, frame) => sum + Number(frame.duration || 0), 0) : 0);
  function sample(track, time) {
    if (!track.frames?.length || time < Number(track.delay || 0)) return null;
    let local = time - Number(track.delay || 0), previous = track.frames[0];
    if (local < Number(previous.duration || 0)) return {...previous};
    local -= Number(previous.duration || 0);
    for (let index = 1; index < track.frames.length; index++) {
      const next = track.frames[index], span = Number(next.duration || 0);
      if (local < span && span > 0) {
        // Destination-key step holds the previous pose throughout the interval.
        // At its exact end this loop advances to the destination, including any
        // consecutive zero-duration keys, just like the game sampler.
        let factor = next.ease === 'step' ? 0 : Math.max(0, Math.min(1, local / span));
        if (next.ease === 'smooth') factor = factor * factor * (3 - 2 * factor);
        const result = {...next};
        for (const key of values) result[key] = Number(previous[key]) + (Number(next[key]) - Number(previous[key])) * factor;
        return result;
      }
      local -= span; previous = next;
    }
    return {...previous};
  }
  // Match ProjectionSprite.DrawSprites: brightness affects opacity and, for
  // plain images/primitives, RGB. Native Projection encodes image size in RGB.
  function appearance(pose, time) {
    const blink = 1 - pose.flicker * (.5 + .5 * Math.sin(time * 91) * Math.sin(time * 37));
    return {opacity:Math.max(0,Math.min(1,pose.opacity * pose.brightness * blink)),brightness:Math.min(pose.brightness,2)};
  }
  function maskAreas(group,track,projectMask,roomAreas,width,height){
    let areas=group.confineToRoom?roomAreas:null;
    const mask=track.maskMode==='none'?null:track.maskMode==='custom'?track.mask:projectMask;
    if(!mask?.enabled)return areas;
    const custom=[mask.x*width,mask.y*height,mask.width*width,mask.height*height];
    if(!areas)return [custom];
    return areas.map(([x,y,w,h])=>{const left=Math.max(x,custom[0]),top=Math.max(y,custom[1]),right=Math.min(x+w,custom[0]+custom[2]),bottom=Math.min(y+h,custom[1]+custom[3]);return [left,top,right-left,bottom-top];}).filter(r=>r[2]>0&&r[3]>0);
  }
  return {end, duration, frameTime, sample, appearance, maskAreas};
})();
if (typeof module !== 'undefined' && module.exports) module.exports = MIProjectionTimeline;

if (typeof document !== 'undefined') (() => {
  const $ = id => document.getElementById(id);
  const t = (key, params = {}) => MI18n.t(`projection.${key}`, params);
  const make = (tag, text, className) => {const node = document.createElement(tag); if (text !== undefined) node.textContent = text; if (className) node.className = className; return node;};
  const author = node => MI18n.content(node);
  const uid = () => crypto.randomUUID().replaceAll('-', '');
  const clone = value => JSON.parse(JSON.stringify(value));
  const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
  const option = (value, label, content = false) => {const node = new Option(label, value); return content ? author(node) : node;};
  const imageCache = new Map(), tintCache = new Map();
  const depthRenderer = typeof MIProjectionDepth === 'undefined' ? null : MIProjectionDepth.createRenderer();
  let groups = [], projects = [], sources = [], applied = {}, group = null, selectedTrack = '', selectedFrame = 0;
  let reference = {}, referenceTab = 'assets', background = null, backgroundStatus = '', clipAreas = [], dirty = false, busy = false;
  let depthBackground = null, lightAngle = [0,0];
  let currentTime = 0, playing = false, lastTick = 0, fitMode = true, zoom = 1, sceneWidth = 1000, sceneHeight = 600, contextVersion = 0, referenceTick = 0;
  let pointerDrag = null, savedStatus = 'loading', projectSettings=null, maskDirty=false;
  let replacement = null;
  const defaultMask=()=>({enabled:false,x:0,y:0,width:1,height:1});
  const track = () => group?.tracks.find(item => item.id === selectedTrack);
  const frame = () => track()?.frames[selectedFrame];
  const seconds = value => Number(value || 0).toFixed(2);
  const defaultFrame = () => ({duration:1,x:.5,y:.5,scale:1,rotation:0,opacity:1,brightness:1,flicker:0,ease:'smooth'});

  async function api(path, data) {
    const response = await fetch('/api/' + path, data === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
    let result;
    try {result = await response.json();} catch {throw Error(t('requestFailed', {status:response.status}));}
    if (!response.ok || result.ok === false) throw Error(MI18n.error(result, t('requestFailed', {status:response.status})));
    return result;
  }
  function notice(message = '', error = false) {$('notice').textContent = message; $('notice').dataset.kind = error ? 'error' : ''; $('notice').setAttribute('role', error ? 'alert' : 'status');}
  function status(key) {savedStatus = key; $('saveState').textContent = t(key); $('saveState').dataset.state = key;}
  function changed() {dirty = true; status('dirty'); notice(); renderGroupOptions(); updateTimelinePosition(); draw();window.MIUndo?.changed();}
  function run(fn) {return async (...args) => {try {return await fn(...args);} catch (error) {notice(error.message, true); if (busy) setBusy(false); console.error(error);}};}
  function setBusy(value) {busy = value; $('studio').inert = value || !group; for (const id of ['save','apply','projects']) $(id).disabled = value || !group;}
  function permitSwitch() {return !(dirty||maskDirty) || confirm(t('discard'));}
  function setPlaying(value) {playing = value; lastTick = 0; $('play').disabled = value || !group?.tracks.length; $('pause').disabled = !value;}
  function pause() {setPlaying(false);}
  function stop() {pause(); currentTime = 0; updateTimelinePosition(); draw();}
  function loadImage(src) {
    if (!src) return null;
    if (!imageCache.has(src)) {const image = new Image(); image.onload = () => draw(); image.src = src; imageCache.set(src, image);}
    const image = imageCache.get(src); return image.complete && image.naturalWidth ? image : null;
  }
  function tintedImage(image, color) {
    if (!color || color.toLowerCase()==='#ffffff') return image;
    const key=image.src+'|'+color;if(tintCache.has(key))return tintCache.get(key);
    const canvas=document.createElement('canvas');canvas.width=image.naturalWidth;canvas.height=image.naturalHeight;
    const ctx=canvas.getContext('2d');ctx.drawImage(image,0,0);ctx.globalCompositeOperation='multiply';ctx.fillStyle=color;ctx.fillRect(0,0,canvas.width,canvas.height);ctx.globalCompositeOperation='destination-in';ctx.drawImage(image,0,0);
    if(tintCache.size>24)tintCache.clear();tintCache.set(key,canvas);return canvas;
  }
  function normalizeGroup(value) {
    const result = clone(value); result.images ||= []; result.tracks ||= []; result.trigger ||= {kind:'work',source:'',pearlUid:'',startLineId:'',endLineId:''};
    result.trigger.beforeSeconds ??= 0; result.trigger.afterSeconds ??= 0;
    for (const item of result.tracks) {item.frames ||= [defaultFrame()]; item.style ||= 'native'; item.glyphIndex ||= 0;item.maskMode ||= 'inherit';item.mask ||= defaultMask();}
    return result;
  }
  function renderGroupOptions() {
    const items = groups.filter(item => item.projectId === group?.projectId);
    if (group && !items.some(item => item.uid === group.uid)) items.push(group);
    $('saved').replaceChildren(...items.map(item => option(item.uid, (item.uid === group?.uid ? group.name : item.name) || t('untitled'), true)));
    if (group) $('saved').value = group.uid;
  }
  function updateGroupFields() {
    renderGroupOptions(); $('groupName').value = group.name || ''; $('enabled').checked = group.enabled !== false; $('loop').checked = !!group.loop; $('confineToRoom').checked = !!group.confineToRoom; $('projects').value = group.projectId;
    $('triggerKind').value = ['dialogue','pearl','work'].includes(group.trigger.kind) ? group.trigger.kind : 'work';
    const address=new URL(location.href);address.searchParams.set('project',group.projectId);address.searchParams.delete('projectId');address.searchParams.set('uid',group.uid);history.replaceState(null,'',address);
    for(const link of document.querySelectorAll('.more-menu a')){const target=new URL(link.href,location.href);target.searchParams.set(target.pathname==='/dialogue'?'id':'project',group.projectId);target.searchParams.set('lang',MI18n.locale);link.href=target;}
  }
  function sourceMatches(item) {const binding = group.trigger; return item.kind === binding.kind && item.source === binding.source && (item.pearlUid || '') === (binding.pearlUid || '') && (!binding.startLineId || item.lines?.some(line => (line.lineId || line.id) === binding.startLineId));}
  function chosenSource() {return sources.find(item => item.id === $('source').value);}
  function sourceTitle(item) {
    if (item.source.startsWith('meetings.')) return MI18n.t('dialogue.meetings.number',{n:item.meetingNumber}) + (item.meetingName ? ' · ' + item.meetingName : '');
    if (item.source === 'loop') return MI18n.t('dialogue.meetings.loop');
    const stage = {'first':'initialStory','repeat':'storyRepeat','pickup':'pickup','leaving':'leaving','returning':'returning','pearlReading.greeting':'greeting','pearlReading.repeat':'pearlRepeat','pearlReading.many':'pearlMany','pearlReading.leaving':'pearlLeaving','pearlReading.returning':'pearlReturning','pearl.read':'pearlRead','pearl.repeat':'pearlRepeat'}[item.source];
    const sourceLabel = ['pearlReading.firstPreRead','pearlReading.greetingCreatures','pearlReading.greetingCorpses','pearlReading.greetingFood',
      'observation.creatures','observation.corpses','observation.food','observation.repeatItems','observation.repeatWeapons','observation.repeatPearls','observation.repeatMixed',
      'observation.repeatCreatures','observation.repeatCorpses','observation.repeatFood'].includes(item.source);
    const label = stage ? t(stage) : sourceLabel ? t('sources.'+item.source) : item.label || item.name || item.source;
    const extra = [item.pearlName,item.poolName].filter(Boolean).join(' · ') || (item.name && item.name !== item.label ? item.name : '');
    return label + (extra ? ' · ' + extra : '');
  }
  function renderBinding() {
    const kind = group.trigger.kind, available = sources.filter(item => item.kind === kind && item.lines?.length);
    $('sourceFields').hidden = kind === 'work'; $('bindingError').textContent = '';
    $('source').replaceChildren(...available.map(item => option(item.id, sourceTitle(item), true)));
    const selected = available.find(sourceMatches);
    if (selected) $('source').value = selected.id;
    else $('source').selectedIndex = -1;
    if (kind !== 'work' && !selected) $('bindingError').textContent = available.length ? t('chooseBinding') : t('noSource');
    renderLineChoices();
  }
  function renderLineChoices() {
    const source = chosenSource(), lines = source?.lines || [];
    for (const id of ['startLine','endLine']) $(id).replaceChildren(...lines.map((line, index) => option(line.lineId || line.id, (index + 1) + ' · ' + String(line.text || '').replace(/\s+/g, ' ').slice(0, 65), true)));
    for (const key of ['beforeSeconds','afterSeconds']) $(key).value = group.trigger[key] || 0;
    $('startLine').value = group.trigger.startLineId || ''; $('endLine').value = group.trigger.endLineId || group.trigger.startLineId || '';
    const start = lines.findIndex(line => (line.lineId || line.id) === $('startLine').value), end = lines.findIndex(line => (line.lineId || line.id) === $('endLine').value);
    [...$('endLine').options].forEach((item, index) => item.disabled = index < start);
    $('bindingText').textContent = start >= 0 && end >= start ? lines.slice(start, end + 1).map(line => line.text || '').join('\n') : '';
    if (source) $('bindingError').textContent = start < 0 || end < start ? t('missingLines') : '';
  }
  function chooseSource() {
    const source = chosenSource(); if (!source) return;
    const first = source.lines?.[0], id = first?.lineId || first?.id || '';
    group.trigger = {kind:source.kind,source:source.source,pearlUid:source.pearlUid || '',startLineId:id,endLineId:id,beforeSeconds:group.trigger.beforeSeconds || 0,afterSeconds:group.trigger.afterSeconds || 0};
    changed(); renderBinding();
  }
  async function loadContext(projectId) {
    const version = ++contextVersion;
    const results = await Promise.allSettled([api('projection-sources?projectId=' + encodeURIComponent(projectId)), api('projection-background?projectId=' + encodeURIComponent(projectId)),api('projection-settings?projectId='+encodeURIComponent(projectId))]);
    if (version !== contextVersion) return;
    const previousBackground = background, previousDepth = depthBackground;
    if(results[2].status==='rejected')throw results[2].reason;
    projectSettings=results[2].value;maskDirty=false;renderMaskSettings();
    if (results[0].status === 'fulfilled') sources = results[0].value.sources || [];
    else {sources = []; notice(results[0].reason.message, true);}
    if (results[1].status === 'fulfilled') {
      const data = results[1].value; background = data.url || data.png || null;
      depthBackground = data.depthUrl || null; lightAngle = data.lightAngle || [0,0];
      clipAreas = data.clipAreas || [];
      sceneWidth = Math.max(1, Number(data.width) || 1000); sceneHeight = Math.max(1, Number(data.height) || 600);
      backgroundStatus = background ? '' : t('backgroundMissing');
    } else {background = null; depthBackground = null; lightAngle = [0,0]; clipAreas = []; backgroundStatus = t('backgroundFailed');}
    if (previousBackground !== background) imageCache.delete(previousBackground);
    if (previousDepth !== depthBackground) imageCache.delete(previousDepth);
    $('preview').width = sceneWidth; $('preview').height = sceneHeight;
    renderBinding(); updateZoom(); draw();
  }
  async function openGroup(value, newGroup = false) {
    setBusy(true); stop(); group = normalizeGroup(value); dirty = false; selectedTrack = group.tracks[0]?.id || ''; selectedFrame = 0;
    updateGroupFields(); renderImages(); renderTimeline(); renderInspector(); status(newGroup ? 'dirty' : applied[group.uid]===group.revision ? 'applied' : 'saved');
    try {await loadContext(group.projectId);window.MIUndo?.reset();} finally {setBusy(false);}
  }
  async function newGroup(projectId = group?.projectId || projects[0]?.projectId) {
    if (!projectId) throw Error(t('noProjects'));
    setBusy(true); const value = await api('projection-default?projectId=' + encodeURIComponent(projectId)); value.name = t('newAnimation'); await openGroup(value, true);
  }
  function renderImages() {
    $('images').replaceChildren(...group.images.map(item => {
      const row = make('div', undefined, 'asset-row'), image = make('img'), name = author(make('span', item.name, 'asset-name'));
      image.src = item.png; image.alt = ''; name.title = item.name;
      const menu=make('details',undefined,'asset-menu action-menu'),summary=make('summary','⋯'),actions=make('div',undefined,'asset-menu-actions');
      summary.title=t('imageActions');summary.setAttribute('aria-label',summary.title);
      const replace=make('button',t('replaceImage')),remove=make('button',t('removeUnusedImage')),add=make('button','+','asset-add');
      replace.type=remove.type=add.type='button';add.title=t('imageTrack');add.setAttribute('aria-label',add.title);
      replace.onclick=()=>{menu.open=false;replacement={uid:group.uid,id:item.id};$('replacePngFile').value='';$('replacePngFile').click();};
      add.onclick = run(() => addTrack('image', item.id)); remove.onclick = run(() => {
        if (group.tracks.some(track => track.imageId === item.id)) throw Error(t('imageInUse'));
        group.images = group.images.filter(image => image.id !== item.id); changed(); renderImages(); renderInspector();
      });
      remove.disabled=group.tracks.some(track=>track.imageId===item.id);if(remove.disabled)remove.title=t('imageInUse');
      menu.addEventListener('toggle',()=>{if(menu.open){
        document.querySelectorAll('.asset-menu[open]').forEach(other=>{if(other!==menu)other.open=false;});
        const rect=summary.getBoundingClientRect();
        actions.style.left=clamp(rect.right-actions.offsetWidth,8,Math.max(8,innerWidth-actions.offsetWidth-8))+'px';
        actions.style.top=(rect.bottom+6+actions.offsetHeight<=innerHeight-8?rect.bottom+6:Math.max(8,rect.top-actions.offsetHeight-6))+'px';
      }});
      actions.append(replace,remove);menu.append(summary,actions);row.append(image,name,menu,add);return row;
    }));
  }
  function addTrack(kind = $('newKind').value, imageId = '') {
    if (group.tracks.length >= 16) throw Error(t('trackLimit'));
    if (kind === 'image' && !group.images.length) {$('pngFile').click(); return;}
    const item = {id:uid(),name:t('trackName', {index:group.tracks.length + 1}),kind,imageId:kind === 'image' ? imageId || group.images[0].id : '',color:'#ffffff',style:'plain',glyphIndex:0,delay:0,frames:[defaultFrame(),{...defaultFrame(),duration:2}]};
    group.tracks.push(item); selectedTrack = item.id; selectedFrame = 0; currentTime = 0; pause(); changed(); renderImages();renderTimeline(); renderInspector();
  }
  function selectFrame(trackId, index, seek = true) {
    selectedTrack = trackId; selectedFrame = index; pause();
    if (seek && track()) currentTime = MIProjectionTimeline.frameTime(track(), index);
    renderTimeline(); renderInspector(); updateTimelinePosition(); draw();
  }
  function renderTimeline() {
    const total = Math.max(1, MIProjectionTimeline.duration(group));
    $('timeline').replaceChildren(...group.tracks.map(item => {
      const row = make('div', undefined, 'timeline-row' + (item.id === selectedTrack ? ' selected' : ''));
      const label = author(make('button', item.name || t('untitled'), 'track-label')); label.title = item.name; label.onclick = () => selectFrame(item.id, 0);
      const lane = make('div', undefined, 'track-lane'), bar = make('div', undefined, 'track-bar');
      bar.style.left = (item.delay / total * 100) + '%'; bar.style.width = ((MIProjectionTimeline.end(item) - item.delay) / total * 100) + '%'; lane.append(bar);
      item.frames.forEach((point, index) => {
        const dot = make('button', undefined, 'frame-dot' + (item.id === selectedTrack && index === selectedFrame ? ' selected' : ''));
        dot.style.left = MIProjectionTimeline.frameTime(item, index) / total * 100 + '%';
        dot.title = t('frameTime', {index:index + 1,seconds:seconds(MIProjectionTimeline.frameTime(item,index))}); dot.setAttribute('aria-label', dot.title); dot.onclick = () => selectFrame(item.id, index); lane.append(dot);
      });
      lane.append(make('div', undefined, 'lane-playhead')); row.append(label, lane); return row;
    }));
    updateTimelinePosition();
  }
  function renderInspector() {
    const item = track(); $('trackEditor').hidden = !item; $('trackEmpty').hidden = !!item; $('removeTrack').disabled = !item;
    if (!item) return;
    renderMaskSettings();
    selectedFrame = clamp(selectedFrame, 0, item.frames.length - 1);
    $('trackName').value = item.name; $('trackDelay').value = item.delay; $('trackColor').value = item.color || '#ffffff'; $('trackStyle').value = item.style || 'native'; $('glyphIndex').value = item.glyphIndex || 0;
    $('glyphIndexField').hidden = !['glyph','matrix'].includes(item.kind);
    $('trackImageField').hidden = item.kind !== 'image'; $('trackStyleField').hidden = item.kind !== 'image'; $('trackColorField').hidden = item.kind === 'image' && item.style !== 'plain';
    $('trackImage').replaceChildren(...group.images.map(image => option(image.id, image.name, true))); $('trackImage').value = item.imageId || '';
    $('frameList').replaceChildren(...item.frames.map((point, index) => {const button = make('button', index === 0 ? t('initial') : String(index + 1), index === selectedFrame ? 'selected' : ''); button.onclick = () => selectFrame(item.id,index); return button;}));
    const point = frame();
    for (const key of ['duration','x','y','scale','rotation','opacity','brightness','flicker','ease']) $(key).value = ['x','y','opacity','flicker'].includes(key) ? +(point[key] * 100).toFixed(3) : point[key];
    $('durationLabel').textContent = selectedFrame === 0 ? t('initialHold') : t('transitionDuration'); $('ease').disabled = selectedFrame === 0; $('removeFrame').disabled = item.frames.length <= 1;
    const index = group.tracks.indexOf(item); $('trackUp').disabled = index === group.tracks.length - 1; $('trackDown').disabled = index === 0;
  }
  function updateTimelinePosition() {
    const duration = MIProjectionTimeline.duration(group), denominator = Math.max(1, duration);
    $('timeDisplay').textContent = seconds(currentTime) + ' / ' + seconds(duration) + ' s'; $('playhead').max = denominator; $('playhead').value = currentTime;
    document.querySelectorAll('.lane-playhead').forEach(node => node.style.left = clamp(currentTime / denominator * 100, 0, 100) + '%');
    $('play').disabled = playing || !group?.tracks.length; $('pause').disabled = !playing;
  }
  function updateZoom() {
    const viewport = $('viewport');
    if (fitMode) zoom = clamp(Math.min((viewport.clientWidth - 20) / sceneWidth, (viewport.clientHeight - 20) / sceneHeight), .01, 2);
    $('preview').style.width = sceneWidth * zoom + 'px'; $('preview').style.height = sceneHeight * zoom + 'px';
    $('zoom').value = zoom * 100; $('zoomValue').textContent = Math.round(zoom * 100) + '%';
    $('fit').setAttribute('aria-pressed', String(fitMode));
  }
  function dimensions(item) {const asset = group.images.find(image => image.id === item.imageId); return item.kind === 'image' ? [asset?.width || 140,asset?.height || 140] : item.kind === 'scanline' ? [280,8] : [140,item.kind === 'line' ? 8 : 140];}
  function draw() {
    const canvas = $('preview'), ctx = canvas.getContext('2d'); ctx.clearRect(0,0,canvas.width,canvas.height); ctx.fillStyle = '#121212'; ctx.fillRect(0,0,canvas.width,canvas.height);
    const backdrop = loadImage(background); if (backdrop) ctx.drawImage(backdrop,0,0,sceneWidth,sceneHeight);
    const depth = loadImage(depthBackground);
    let approximate = false, depthShown = false, depthUnavailable = false;
    for (const item of group?.tracks || []) {
      const pose = MIProjectionTimeline.sample(item,currentTime); if (!pose) continue;
      const [width,height] = dimensions(item), appearance = MIProjectionTimeline.appearance(pose,currentTime);
      ctx.save();
      const masks=MIProjectionTimeline.maskAreas(group,item,projectSettings?.mask,clipAreas,sceneWidth,sceneHeight);
      if(masks){ctx.beginPath();for(const [x,y,w,h] of masks)ctx.rect(x,y,w,h);ctx.clip();}
      ctx.globalAlpha = appearance.opacity;
      const asset = item.kind === 'image' ? group.images.find(image => image.id === item.imageId) : null;
      const image = loadImage(asset?.png);
      const projected = item.kind === 'image' && item.style === 'native' && image && depthRenderer?.draw(ctx,image,depth,pose,[width,height],[sceneWidth,sceneHeight],lightAngle);
      if (item.kind === 'image' && item.style === 'native') {depthShown ||= !!projected;depthUnavailable ||= !!image && !projected;}
      ctx.translate(pose.x * sceneWidth,pose.y * sceneHeight); ctx.rotate(pose.rotation * Math.PI / 180); ctx.scale(pose.scale,pose.scale); ctx.globalAlpha = appearance.opacity; ctx.filter = item.kind==='image'&&item.style==='native'?'none':'brightness(' + appearance.brightness + ')'; ctx.strokeStyle = ctx.fillStyle = item.color || '#ffffff';
      // Runtime segment widths are world-pixel widths, independent of scale.
      ctx.lineWidth = (item.kind==='grid'?1:item.kind==='circle'?1.4:1.5)/pose.scale;
      if (item.kind === 'image') {
        if (image && !projected) {
          ctx.drawImage(item.style==='plain'?tintedImage(image,item.color):image,-width/2,-height/2,width,height);
          if (item.style === 'moon') approximate = true;
        }
      } else if (item.kind === 'circle') {ctx.beginPath(); ctx.arc(0,0,70,0,Math.PI*2); ctx.stroke();}
      else if (item.kind === 'line') {ctx.beginPath(); ctx.moveTo(-70,0); ctx.lineTo(70,0); ctx.stroke();}
      else if (item.kind === 'scanline') {ctx.beginPath(); ctx.moveTo(-140,0); ctx.lineTo(140,0); ctx.stroke();}
      else if (item.kind === 'cursor') {ctx.strokeRect(-70,-70,140,140);ctx.globalAlpha*=.08;ctx.fillRect(-70,-70,140,140);}
      else if (item.kind === 'grid') {ctx.beginPath(); for (let index=-70;index<=70;index+=17.5) {ctx.moveTo(index,-70);ctx.lineTo(index,70);ctx.moveTo(-70,index);ctx.lineTo(70,index);} ctx.stroke();}
      else if (item.kind === 'glyph' || item.kind === 'matrix') {
        approximate = true;
        const count = item.kind === 'matrix' ? 4 : 1, cell = 140/count;
        for(let row=0;row<count;row++)for(let column=0;column<count;column++){
          ctx.save();ctx.translate(-70+(column+.5)*cell,-70+(row+.5)*cell);ctx.scale(cell/140,cell/140);
          ctx.beginPath();ctx.moveTo(0,-60);ctx.lineTo(50,0);ctx.lineTo(0,60);ctx.lineTo(-50,0);ctx.closePath();ctx.moveTo(-30,0);ctx.lineTo(30,0);ctx.moveTo(0,-35);ctx.lineTo(0,35);ctx.stroke();ctx.restore();
        }
      }
      ctx.restore();
      if (item.id === selectedTrack && !playing) {
        ctx.save();ctx.translate(pose.x*sceneWidth,pose.y*sceneHeight);ctx.rotate(pose.rotation*Math.PI/180);ctx.strokeStyle='#eee';ctx.lineWidth=1/zoom;ctx.setLineDash([5/zoom,5/zoom]);ctx.strokeRect(-width*pose.scale/2-4/zoom,-height*pose.scale/2-4/zoom,width*pose.scale+8/zoom,height*pose.scale+8/zoom);ctx.restore();
      }
    }
    if(!playing&&$('showMask').checked){const item=track(),mask=item?.maskMode==='custom'?item.mask:item?.maskMode==='none'?null:projectSettings?.mask;if(mask?.enabled){ctx.save();ctx.strokeStyle='#fff';ctx.lineWidth=1/zoom;ctx.setLineDash([8/zoom,4/zoom]);ctx.strokeRect(mask.x*sceneWidth,mask.y*sceneHeight,mask.width*sceneWidth,mask.height*sceneHeight);ctx.restore();}}
    $('previewState').textContent = backgroundStatus || (depthUnavailable ? t('depthUnavailable') : depthShown ? t('depthPreview') : approximate ? t('approximate') : '');
  }
  function tick(now) {
    if (playing) {
      if (lastTick) currentTime += Math.min((now - lastTick) / 1000,.1);
      lastTick = now; const duration = MIProjectionTimeline.duration(group);
      if (currentTime > duration) {if (group.loop && duration > 0) currentTime %= duration; else {currentTime = duration; pause();}}
      updateTimelinePosition(); draw();
    }
    if (now-referenceTick>70 && referenceTab==='elements' && document.querySelector('.reference-section').open) {drawReferenceEffects(now/1000);referenceTick=now;}
    requestAnimationFrame(tick);
  }
  function canvasPoint(event) {const bounds = $('preview').getBoundingClientRect(); return {x:(event.clientX-bounds.left)/bounds.width,y:(event.clientY-bounds.top)/bounds.height};}
  function hitTrack(point) {
    return [...group.tracks].reverse().find(item => {
      const pose = MIProjectionTimeline.sample(item,currentTime); if (!pose || pose.opacity <= .01) return false;
      const [width,height] = dimensions(item), dx=(point.x-pose.x)*sceneWidth,dy=(point.y-pose.y)*sceneHeight, angle=-pose.rotation*Math.PI/180;
      return Math.abs(dx*Math.cos(angle)-dy*Math.sin(angle)) <= width*pose.scale/2+8/zoom && Math.abs(dx*Math.sin(angle)+dy*Math.cos(angle)) <= Math.max(height*pose.scale/2,8/zoom);
    });
  }
  $('preview').onpointerdown = event => {
    if (event.button !== 0 || !group) return;
    const point = canvasPoint(event), hit = hitTrack(point); if (!hit) return;
    pause();
    if (hit.id !== selectedTrack) {selectedTrack=hit.id; selectedFrame=0;}
    // A drag edits the selected keyframe, and seeks to that frame before moving it.
    currentTime=MIProjectionTimeline.frameTime(track(),selectedFrame); const pose=frame();
    pointerDrag={id:event.pointerId,offsetX:point.x-pose.x,offsetY:point.y-pose.y}; $('preview').setPointerCapture(event.pointerId); renderTimeline();renderInspector();draw();event.preventDefault();
  };
  $('preview').onpointermove = event => {
    if (!pointerDrag || pointerDrag.id !== event.pointerId) return;
    const point=canvasPoint(event), pose=frame();pose.x=clamp(point.x-pointerDrag.offsetX,0,1);pose.y=clamp(point.y-pointerDrag.offsetY,0,1);
    $('x').value=+(pose.x*100).toFixed(2);$('y').value=+(pose.y*100).toFixed(2);changed();
  };
  const endDrag = () => {pointerDrag=null;}; $('preview').onpointerup=endDrag;$('preview').onpointercancel=endDrag;$('preview').onlostpointercapture=endDrag;
  $('preview').onkeydown=event=>{const move={ArrowLeft:[-.001,0],ArrowRight:[.001,0],ArrowUp:[0,-.001],ArrowDown:[0,.001]}[event.key];if(!move||!frame())return;event.preventDefault();pause();frame().x=clamp(frame().x+move[0]*(event.shiftKey?10:1),0,1);frame().y=clamp(frame().y+move[1]*(event.shiftKey?10:1),0,1);currentTime=MIProjectionTimeline.frameTime(track(),selectedFrame);changed();renderInspector();};

  async function readPng(file) {
    if (file.size>4*1024*1024) throw Error(t('pngLimit',{name:file.name}));
    const bytes = new Uint8Array(await file.arrayBuffer());
    if (![137,80,78,71,13,10,26,10].every((value,index)=>bytes[index]===value)) throw Error(t('pngInvalid',{name:file.name}));
    const png=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(Error(t('pngInvalid',{name:file.name})));reader.readAsDataURL(file);});
    const image=await new Promise((resolve,reject)=>{const image=new Image();image.onload=()=>resolve(image);image.onerror=()=>reject(Error(t('pngInvalid',{name:file.name})));image.src=png;});
    if(image.width>1024||image.height>1024||!image.width||!image.height)throw Error(t('pngLimit',{name:file.name}));
    const check=document.createElement('canvas');check.width=image.width;check.height=image.height;const ctx=check.getContext('2d',{willReadFrequently:true});ctx.drawImage(image,0,0);const pixels=ctx.getImageData(0,0,image.width,image.height).data;
    let transparent=false;for(let index=3;index<pixels.length;index+=4)if(pixels[index]<255){transparent=true;break;}
    if(!transparent)throw Error(t('pngAlpha',{name:file.name}));
    return {id:uid(),name:file.name,png,width:image.width,height:image.height};
  }
  function checkImageBudget(images){if(images.reduce((sum,image)=>sum+image.width*image.height,0)>8*1024*1024||images.reduce((sum,image)=>sum+(image.png.split(',')[1]?.length||0)*.75,0)>8*1024*1024)throw Error(t('imageBudget'));}
  $('replacePngFile').oncancel=()=>{replacement=null;};
  $('replacePngFile').onchange=run(async()=>{
    const file=$('replacePngFile').files[0],request=replacement;replacement=null;
    if(!file||!request)return;
    if(busy||!group||request.uid!==group.uid)throw Error(t('replaceChanged'));
    window.MIUndo?.flush();setBusy(true);
    try{
      const incoming=await readPng(file);
      if(!group||request.uid!==group.uid)throw Error(t('replaceChanged'));
      const index=group.images.findIndex(image=>image.id===request.id);
      if(index<0)throw Error(t('replaceChanged'));
      const previous=group.images[index],updated={...previous,name:incoming.name,png:incoming.png,width:incoming.width,height:incoming.height};
      const images=group.images.map((image,i)=>i===index?updated:image);checkImageBudget(images);
      group.images=images;imageCache.delete(previous.png);tintCache.clear();
      pause();changed();renderImages();renderTimeline();renderInspector();notice(t('imageReplaced'));
    }finally{setBusy(false);$('replacePngFile').value='';}
  });
  $('upload').onclick=()=>{$('pngFile').value='';$('pngFile').click();};
  $('pngFile').onchange=run(async()=>{
    const files=[...$('pngFile').files];if(!files.length)return;
    if(group.images.length+files.length>16)throw Error(t('imageLimit'));
    setBusy(true);const images=[];for(const file of files)images.push(await readPng(file));
    checkImageBudget([...group.images,...images]);
    group.images.push(...images);for(const image of images)if(group.tracks.length<16)addTrack('image',image.id);
    changed();renderImages();renderTimeline();renderInspector();setBusy(false);$('pngFile').value='';
  });
  async function useReference(item) {
    if (group.images.length>=16) throw Error(t('imageLimit'));
    setBusy(true);
    try {
      const response=await fetch(item.url);if(!response.ok)throw Error(t('requestFailed',{status:response.status}));
      const image=await readPng(new File([await response.blob()],item.name+'.png',{type:'image/png'}));
      checkImageBudget([...group.images,image]);
      group.images.push(image);if(group.tracks.length<16){addTrack('image',image.id);track().style='native';}
      changed();renderImages();renderTimeline();renderInspector();
    } finally {setBusy(false);}
  }
  function referenceLabel(item,key='name'){return MI18n.locale==='en' ? item[key+'En']||item[key]||item.id : item[key]||item[key+'En']||item.id;}
  function renderReferences(){
    $('refAssets').setAttribute('aria-pressed',String(referenceTab==='assets'));$('refEffects').setAttribute('aria-pressed',String(referenceTab==='elements'));
    const items=reference[referenceTab]||[];$('references').replaceChildren(...items.map(item=>{
      const card=make('div',undefined,'reference-card');const url=item.url||item.previewUrl||item.thumbnail;
      if(url){const image=make('img');image.src=url;image.alt='';image.loading='lazy';card.append(image);}
      else if(referenceTab==='elements'){const canvas=make('canvas');canvas.width=240;canvas.height=150;canvas.dataset.effect=item.id;card.append(canvas);}
      card.append(author(make('strong',referenceLabel(item),'reference-name')));
      const description=referenceLabel(item,'description');if(description&&description!==item.id){card.title=description;author(card);}
      if(url){const link=make('a',t('openOriginal'));link.href=url;link.target='_blank';link.rel='noopener';card.append(link);}
      if(referenceTab==='assets'&&item.kind==='oracle'&&item.hasTransparency&&item.available!==false){const button=make('button',t('useOriginal'),'compact');button.onclick=run(()=>useReference(item));card.append(button);}
      if(referenceTab==='elements'&&['circle','line','glyph','grid','cursor','scanline','matrix'].includes(item.kind)){const button=make('button',t('addEffect'),'compact');button.onclick=run(()=>addTrack(item.id==='scan-line'?'scanline':item.id==='glyph-matrix'?'matrix':item.kind));card.append(button);}
      return card;
    }));$('referenceState').textContent=items.length?(referenceTab==='elements'?t('approximate'):''):t('referenceEmpty');drawReferenceEffects(0);
  }
  function drawReferenceEffects(time) {
    for(const canvas of $('references').querySelectorAll('canvas')){
      const ctx=canvas.getContext('2d'),id=canvas.dataset.effect;ctx.clearRect(0,0,240,150);ctx.save();ctx.translate(120,75);ctx.strokeStyle=ctx.fillStyle='#dce7ed';ctx.lineWidth=1;
      if(['oracle-image','moon-image','overseer-image'].includes(id)){
        const asset=reference.assets?.find(item=>item.id===(Math.floor(time/.375)%2?'aiimg3b':'aiimg3a'))||reference.assets?.[0],image=loadImage(asset?.url);
        if(image){const scale=Math.min(210/image.naturalWidth,130/image.naturalHeight);if(id==='moon-image')ctx.filter='brightness(1.4)';if(id==='overseer-image'){ctx.beginPath();ctx.arc(0,0,60,0,Math.PI*2);ctx.clip();ctx.filter='sepia(1) saturate(2)';}ctx.globalAlpha=id==='moon-image'?.85+.12*Math.sin(time*7):1;ctx.drawImage(image,-image.naturalWidth*scale/2,-image.naturalHeight*scale/2,image.naturalWidth*scale,image.naturalHeight*scale);}
      }else if(id==='projection-circle'){ctx.beginPath();ctx.arc(0,0,43+Math.sin(time*2)*8,0,Math.PI*2);ctx.stroke();ctx.beginPath();ctx.arc(0,0,58,0,Math.PI*2);ctx.stroke();}
      else if(id==='scan-line'){const y=Math.sin(time*1.5)*60;ctx.beginPath();ctx.moveTo(-110,y);ctx.lineTo(110,y);ctx.stroke();}
      else if(id==='projection-cursor'){ctx.translate(Math.sin(time)*15,Math.cos(time)*8);ctx.strokeRect(-45,-45,90,90);ctx.globalAlpha=.12;ctx.fillRect(-45,-45,90,90);}
      else {const count=id==='glyph-matrix'?4:1,size=count===1?45:12;for(let row=0;row<count;row++)for(let col=0;col<count;col++){ctx.save();ctx.translate((col-(count-1)/2)*28,(row-(count-1)/2)*28);ctx.globalAlpha=.6+.4*Math.sin(time*3+row+col);ctx.beginPath();ctx.moveTo(0,-size);ctx.lineTo(size*.7,0);ctx.lineTo(0,size);ctx.lineTo(-size*.7,0);ctx.closePath();ctx.moveTo(-size*.4,0);ctx.lineTo(size*.4,0);ctx.stroke();ctx.restore();}}
      ctx.restore();
    }
  }
  function renderMaskSettings(){
    const mask=projectSettings?.mask||defaultMask();$('projectMaskEnabled').checked=mask.enabled;$('projectMaskFields').hidden=!mask.enabled;
    for(const key of ['x','y','width','height'])$('projectMask'+key).value=+(mask[key]*100).toFixed(3);
    const item=track();if(!item)return;
    $('trackMaskMode').value=item.maskMode||'inherit';$('trackMaskFields').hidden=item.maskMode!=='custom';
    for(const key of ['x','y','width','height'])$('trackMask'+key).value=+((item.mask||defaultMask())[key]*100).toFixed(3);
  }
  function bindMask(prefix,get,edited){
    for(const key of ['x','y','width','height'])$(prefix+key).oninput=()=>{const input=$(prefix+key);if(!input.checkValidity())return;const mask=get(),value=+input.value/100;mask[key]=value;
      if(key==='x')mask.width=Math.min(mask.width,1-value);if(key==='y')mask.height=Math.min(mask.height,1-value);
      if(key==='width')mask.x=Math.min(mask.x,1-value);if(key==='height')mask.y=Math.min(mask.y,1-value);
      edited();renderMaskSettings();draw();};
  }
  function maskChanged(){maskDirty=true;status('dirty');notice();draw();window.MIUndo?.changed();}
  bindMask('projectMask',()=>projectSettings.mask,maskChanged);
  bindMask('trackMask',()=>track().mask,changed);
  $('projectMaskEnabled').onchange=()=>{projectSettings.mask.enabled=$('projectMaskEnabled').checked;maskChanged();renderMaskSettings();};
  $('trackMaskMode').onchange=()=>{track().maskMode=$('trackMaskMode').value;if(track().maskMode==='custom')track().mask.enabled=true;changed();renderMaskSettings();};
  $('showMask').onchange=draw;
  async function save(apply=false){
    for(const input of document.querySelectorAll('#studio input'))if(!input.disabled&&!input.closest('[hidden]')&&!input.checkValidity()){input.reportValidity();throw Error(t('invalidInput'));}
    if(!group.name.trim())throw Error(t('nameRequired'));
    if(group.trigger.kind!=='work'&&(!chosenSource()||!group.trigger.startLineId||!group.trigger.endLineId))throw Error(t('chooseBinding'));
    const submitted=clone(group);
    setBusy(true);pause();status(apply?'applying':'saving');
    try{
      if(projectSettings&&(maskDirty||apply)){projectSettings=await api('projection-settings',{settings:projectSettings,apply});if(maskDirty&&!apply)for(const saved of groups)if(saved.projectId===group.projectId)delete applied[saved.uid];maskDirty=false;}
      const result=await api(apply?'projection-apply':'projection-save',group),stored=normalizeGroup(result.projection||result);
      group=stored;const index=groups.findIndex(item=>item.uid===group.uid);if(index<0)groups.push(clone(group));else groups[index]=clone(group);
      if(apply)applied[group.uid]=group.revision;
      dirty=false;status(apply?'applied':'saved');notice();renderGroupOptions();renderInspector();window.MIUndo?.rebase();
    }catch(error){
      if(apply){
        try{
          const listing=await api('projections'),stored=listing.projections?.find(item=>item.uid===submitted.uid);
          const canonical=value=>Array.isArray(value)?value.map(canonical):value&&typeof value==='object'?Object.fromEntries(Object.keys(value).filter(key=>!['revision','updatedAt'].includes(key)).sort().map(key=>[key,canonical(value[key])])):value;
          if(stored&&JSON.stringify(canonical(normalizeGroup(stored)))===JSON.stringify(canonical(submitted))){
            group=normalizeGroup(stored);groups=listing.projections;applied=listing.applied||{};dirty=false;renderGroupOptions();
            if(group.revision>submitted.revision&&applied[group.uid]===group.revision){status('applied');notice();renderInspector();return;}
            error.message=t('savedApplyFailed',{detail:error.message});
          }
        }catch(recoveryError){console.warn('Could not check projection save after apply failed',recoveryError);}
      }
      status('error');throw error;
    }finally{setBusy(false);}
  }
  $('save').onclick=run(()=>save(false));$('apply').onclick=run(()=>save(true));
  $('newGroup').onclick=run(async()=>{if(permitSwitch())await newGroup();});
  $('saved').onchange=run(async()=>{const id=$('saved').value;if(!permitSwitch()){$('saved').value=group.uid;return;}const selected=groups.find(item=>item.uid===id);if(selected)await openGroup(selected);});
  $('projects').onchange=run(async()=>{const id=$('projects').value;if(!permitSwitch()){$('projects').value=group.projectId;return;}const selected=groups.find(item=>item.projectId===id);if(selected)await openGroup(selected);else await newGroup(id);});
  $('groupName').oninput=()=>{group.name=$('groupName').value;changed();};$('enabled').onchange=()=>{group.enabled=$('enabled').checked;changed();};$('loop').onchange=()=>{group.loop=$('loop').checked;changed();};
  $('confineToRoom').onchange=()=>{group.confineToRoom=$('confineToRoom').checked;changed();draw();};
  $('triggerKind').onchange=()=>{const kind=$('triggerKind').value;group.trigger={kind,source:'',pearlUid:'',startLineId:'',endLineId:'',beforeSeconds:0,afterSeconds:0};renderBinding();if(kind!=='work'&&$('source').options.length){$('source').selectedIndex=0;chooseSource();}changed();};
  $('source').onchange=chooseSource;
  $('refreshSources').onclick=run(async()=>{setBusy(true);try{sources=(await api('projection-sources?projectId='+encodeURIComponent(group.projectId))).sources||[];renderBinding();notice();}finally{setBusy(false);}});
  $('startLine').onchange=()=>{const source=chosenSource(),ids=source.lines.map(line=>line.lineId||line.id);group.trigger.startLineId=$('startLine').value;if(ids.indexOf(group.trigger.endLineId)<ids.indexOf(group.trigger.startLineId))group.trigger.endLineId=group.trigger.startLineId;changed();renderLineChoices();};
  for(const key of ['beforeSeconds','afterSeconds'])$(key).oninput=()=>{if(!$(key).checkValidity())return;group.trigger[key]=+$(key).value;changed();};
  $('endLine').onchange=()=>{group.trigger.endLineId=$('endLine').value;changed();renderLineChoices();};
  $('addTrack').onclick=run(()=>addTrack());$('removeTrack').onclick=()=>{if(!track())return;group.tracks=group.tracks.filter(item=>item.id!==selectedTrack);selectedTrack=group.tracks[0]?.id||'';selectedFrame=0;pause();changed();renderImages();renderTimeline();renderInspector();};
  $('trackName').oninput=()=>{track().name=$('trackName').value;changed();renderTimeline();};
  for(const [id,key] of [['trackDelay','delay'],['trackColor','color'],['trackImage','imageId'],['trackStyle','style'],['glyphIndex','glyphIndex']])$(id).oninput=()=>{if(!$(id).checkValidity())return;track()[key]=['delay','glyphIndex'].includes(key)?+$(id).value:$(id).value;pause();if(key==='delay')currentTime=MIProjectionTimeline.frameTime(track(),selectedFrame);changed();if(key==='delay')renderTimeline();if(key==='style')renderInspector();if(key==='imageId')renderImages();};
  for(const key of ['duration','x','y','scale','rotation','opacity','brightness','flicker','ease'])$(key).oninput=()=>{if(!$(key).checkValidity()||!frame())return;frame()[key]=key==='ease'?$(key).value:+$(key).value/(['x','y','opacity','flicker'].includes(key)?100:1);pause();currentTime=MIProjectionTimeline.frameTime(track(),selectedFrame);changed();if(key==='duration')renderTimeline();};
  $('addFrame').onclick=run(()=>{const item=track();if(item.frames.length>=120||group.tracks.reduce((sum,item)=>sum+item.frames.length,0)>=512)throw Error(t('frameLimit'));item.frames.splice(selectedFrame+1,0,{...frame(),duration:1});selectedFrame++;changed();selectFrame(item.id,selectedFrame);});
  $('removeFrame').onclick=()=>{if(track().frames.length<=1)return;track().frames.splice(selectedFrame,1);selectedFrame=Math.max(0,selectedFrame-1);changed();selectFrame(selectedTrack,selectedFrame);};
  function moveTrack(delta){const index=group.tracks.indexOf(track()),next=index+delta;if(next<0||next>=group.tracks.length)return;[group.tracks[index],group.tracks[next]]=[group.tracks[next],group.tracks[index]];changed();renderTimeline();renderInspector();}
  $('trackUp').onclick=()=>moveTrack(1);$('trackDown').onclick=()=>moveTrack(-1);
  $('play').onclick=()=>{if(currentTime>=MIProjectionTimeline.duration(group))currentTime=0;setPlaying(true);};$('pause').onclick=pause;$('stop').onclick=stop;
  $('playhead').oninput=()=>{pause();currentTime=+$('playhead').value;updateTimelinePosition();draw();};
  $('zoom').oninput=()=>{fitMode=false;zoom=+$('zoom').value/100;updateZoom();draw();};$('fit').onclick=()=>{fitMode=true;updateZoom();draw();};$('actualSize').onclick=()=>{fitMode=false;zoom=1;updateZoom();draw();};
  $('refAssets').onclick=()=>{referenceTab='assets';renderReferences();};$('refEffects').onclick=()=>{referenceTab='elements';renderReferences();};
  function initializeColumns(){
    const divider=$('projectionDivider'),studio=$('studio'),key='moreiterators.projection.sidebar-width.v1';
    let preferred=null,width=330,maximum=960,drag=null,scheduled=0;
    try{const saved=localStorage.getItem(key),value=Number(saved);if(saved!==null&&Number.isFinite(value))preferred=clamp(value,260,960);}catch{}
    const defaultWidth=()=>window.innerWidth>=1750?350:window.innerWidth<=1180?300:330;
    function update(){
      scheduled=0;
      const css=getComputedStyle(studio),available=studio.clientWidth-parseFloat(css.paddingLeft)-parseFloat(css.paddingRight);
      maximum=Math.max(260,Math.min(960,available-420-22));
      width=clamp(preferred??defaultWidth(),260,maximum);
      studio.style.setProperty('--projection-sidebar-width',width+'px');
      divider.setAttribute('aria-label',t('resizeColumns'));
      divider.title=MI18n.text('拖动调整栏宽，方向键微调，双击恢复默认宽度');
      divider.setAttribute('aria-valuemin','260');divider.setAttribute('aria-valuemax',String(Math.round(maximum)));
      divider.setAttribute('aria-valuenow',String(Math.round(width)));divider.setAttribute('aria-valuetext',MI18n.t('unit.pixels',{count:Math.round(width)}));
    }
    function schedule(){if(!scheduled)scheduled=requestAnimationFrame(update);}
    function persist(){try{if(preferred===null)localStorage.removeItem(key);else localStorage.setItem(key,String(preferred));}catch{}}
    function resize(value){preferred=clamp(value,260,maximum);update();}
    divider.addEventListener('pointerdown',event=>{
      if(event.button!==0||window.innerWidth<=760)return;event.preventDefault();
      drag={id:event.pointerId,x:event.clientX,width};divider.setPointerCapture(event.pointerId);
      document.body.classList.add('resizing-projection-columns');
    });
    divider.addEventListener('pointermove',event=>{if(drag?.id===event.pointerId)resize(drag.width+drag.x-event.clientX);});
    function end(){if(!drag)return;drag=null;persist();document.body.classList.remove('resizing-projection-columns');}
    for(const name of ['pointerup','pointercancel','lostpointercapture'])divider.addEventListener(name,end);
    divider.addEventListener('keydown',event=>{
      const step=event.shiftKey?48:16;
      if(event.key==='ArrowLeft'||event.key==='ArrowRight'){event.preventDefault();resize(width+(event.key==='ArrowLeft'?step:-step));persist();}
      else if(event.key==='Home'||event.key==='End'){event.preventDefault();resize(event.key==='Home'?260:maximum);persist();}
    });
    divider.addEventListener('dblclick',()=>{preferred=null;persist();update();});
    window.addEventListener('resize',schedule);window.addEventListener('mi-language-change',schedule);
    MI18n.ready.then(update);
  }
  initializeColumns();
  new ResizeObserver(()=>{updateZoom();draw();}).observe($('viewport'));
  window.MIStudioPage={projectId:()=>group?.projectId,isBusy:()=>busy||!!window.MIUndo?.busy,saveBeforeNavigate:async()=>{if(dirty||maskDirty)await save(false);return !dirty&&!maskDirty;},error:message=>notice(message,true)};
  window.MIUndo?.register({key:()=>group?.uid,capture:()=>{const value=clone(group);delete value.revision;delete value.updatedAt;return {group:value,mask:projectSettings?.mask};},busy:()=>busy||!!pointerDrag||!group,
   restore:value=>{pause();group=normalizeGroup({...value.group,revision:group.revision,updatedAt:group.updatedAt});if(projectSettings&&value.mask){maskDirty=maskDirty||JSON.stringify(projectSettings.mask)!==JSON.stringify(value.mask);projectSettings.mask=clone(value.mask);}if(!group.tracks.some(item=>item.id===selectedTrack))selectedTrack=group.tracks[0]?.id||'';selectedFrame=Math.min(selectedFrame,Math.max(0,(track()?.frames.length||1)-1));currentTime=0;updateGroupFields();renderImages();renderTimeline();renderInspector();renderBinding();renderMaskSettings();changed();},onError:error=>notice(error.message,true)});
  window.addEventListener('beforeunload',event=>{if(dirty||maskDirty){event.preventDefault();event.returnValue='';}});
  window.addEventListener('mi-language-change',()=>{if(!group)return;status(savedStatus);renderImages();renderBinding();renderTimeline();renderInspector();renderReferences();draw();});
  document.addEventListener('pointerdown',event=>{const menu=document.querySelector('.more-menu,.mi-topbar-menu');if(menu&&!menu.contains(event.target))menu.open=false;});
  document.addEventListener('pointerdown',event=>document.querySelectorAll('.asset-menu[open]').forEach(menu=>{if(!menu.contains(event.target))menu.open=false;}));
  document.addEventListener('keydown',event=>{if(event.key==='Escape')document.querySelectorAll('.asset-menu[open]').forEach(menu=>{menu.open=false;menu.querySelector('summary').focus();});});
  document.addEventListener('scroll',()=>document.querySelectorAll('.asset-menu[open]').forEach(menu=>{menu.open=false;}),true);
  async function initialize(){
    await MI18n.ready;status('loading');
    const list=await api('projections');groups=list.projections||[];projects=list.projects||[];applied=list.applied||{};
    if(!projects.length){const created=await api('save',await api('default'));projects=[created.project];}
    $('projects').replaceChildren(...projects.map(item=>option(item.projectId,item.name||item.projectId,true)));
    const params=new URLSearchParams(location.search),requested=groups.find(item=>item.uid===params.get('uid'));
    const requestedProject=params.get('projectId')||params.get('project');
    const projectId=requested?.projectId||projects.find(item=>item.projectId===requestedProject)?.projectId||projects[0].projectId;
    const initial=requested||groups.find(item=>item.projectId===projectId);if(initial)await openGroup(initial);else await newGroup(projectId);
    try{reference=await api('projection-reference');renderReferences();}catch(error){$('referenceState').textContent=error.message;}
    requestAnimationFrame(tick);
  }
  run(initialize)();
})();
