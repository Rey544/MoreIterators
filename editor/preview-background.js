'use strict';
// Preview-only RGB color; never included in exported textures or room lighting.
let backgroundHSV=[220,.12,.16];
function backgroundToHSV(hex){
 const rgb=hex.slice(1).match(/../g).map(v=>parseInt(v,16)/255),max=Math.max(...rgb),min=Math.min(...rgb),delta=max-min;
 let h=delta===0?0:max===rgb[0]?((rgb[1]-rgb[2])/delta+6)%6:max===rgb[1]?(rgb[2]-rgb[0])/delta+2:(rgb[0]-rgb[1])/delta+4;
 return [h*60,max===0?0:delta/max,max];
}
function backgroundRGB(h,s,v){
 const c=v*s,x=c*(1-Math.abs((h/60)%2-1)),m=v-c;
 const rgb=h<60?[c,x,0]:h<120?[x,c,0]:h<180?[0,c,x]:h<240?[0,x,c]:h<300?[x,0,c]:[c,0,x];
 return '#'+rgb.map(a=>Math.round((a+m)*255).toString(16).padStart(2,'0')).join('');
}
function showPreviewBackground(){
 const bg=project.editor.previewBackground,checker=bg.mode==='checker',[h,s,v]=backgroundHSV;
 // Keep the backdrop separate from the canvas resized by the workspace.
 // Its transparent pixels must also remain clear for fitting and texture export.
 $('previewStage').classList.toggle('checker',checker);$('previewStage').style.backgroundColor=bg.color;
 $('backgroundMode').value=bg.mode;$('backgroundSpectrum').hidden=checker;
 $('backgroundSV').style.setProperty('--hue',`hsl(${h} 100% 50%)`);
 $('backgroundCursor').style.left=(s*100)+'%';$('backgroundCursor').style.top=((1-v)*100)+'%';
 $('backgroundSV').setAttribute('aria-valuenow',Math.round(s*100));
 $('backgroundSV').setAttribute('aria-valuetext',`饱和度 ${Math.round(s*100)}%，明度 ${Math.round(v*100)}%`);
 $('backgroundHue').value=h;
}
function loadPreviewBackground(){
 const old=project.editor.previewBackground||{};
 project.editor.previewBackground={mode:old.mode==='checker'?'checker':'solid',color:/^#[0-9a-f]{6}$/i.test(old.color)?old.color:'#242629'};
 backgroundHSV=backgroundToHSV(project.editor.previewBackground.color);showPreviewBackground();
}
function changeBackgroundColor(){project.editor.previewBackground.color=backgroundRGB(...backgroundHSV);showPreviewBackground();markDirty();}
$('backgroundMode').onchange=()=>{project.editor.previewBackground.mode=$('backgroundMode').value;showPreviewBackground();markDirty();};
$('backgroundHue').oninput=()=>{backgroundHSV[0]=+$('backgroundHue').value;changeBackgroundColor();};
function sampleBackground(e){const r=$('backgroundSV').getBoundingClientRect();backgroundHSV[1]=Math.max(0,Math.min(1,(e.clientX-r.left)/r.width));backgroundHSV[2]=1-Math.max(0,Math.min(1,(e.clientY-r.top)/r.height));changeBackgroundColor();}
$('backgroundSV').onpointerdown=e=>{if(e.button!==0)return;e.preventDefault();$('backgroundSV').focus();$('backgroundSV').setPointerCapture(e.pointerId);sampleBackground(e);};
$('backgroundSV').onpointermove=e=>{if($('backgroundSV').hasPointerCapture(e.pointerId))sampleBackground(e);};
$('backgroundSV').onpointerup=e=>{if($('backgroundSV').hasPointerCapture(e.pointerId))$('backgroundSV').releasePointerCapture(e.pointerId);};
$('backgroundSV').onkeydown=e=>{const changes={ArrowLeft:[1,-.01],ArrowRight:[1,.01],ArrowUp:[2,.01],ArrowDown:[2,-.01]},item=changes[e.key];if(!item)return;e.preventDefault();backgroundHSV[item[0]]=Math.max(0,Math.min(1,backgroundHSV[item[0]]+item[1]));changeBackgroundColor();};
document.addEventListener('pointerdown',e=>{if(!$('previewBackground').contains(e.target))$('previewBackground').open=false;});

function loadPreviewGuides(){guide=project.editor.guides!==false;$('guides').checked=guide;$('guideColor').value=referenceColor();}
$('guides').onchange=()=>{guide=$('guides').checked;project.editor.guides=guide;changed();};
$('guideColor').oninput=()=>{project.editor.guideColor=$('guideColor').value;changed();};
document.addEventListener('pointerdown',e=>{if(!$('referenceGuides').contains(e.target))$('referenceGuides').open=false;});
