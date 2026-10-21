'use strict';
const HandTextureBase=(()=>{
 function target(key){
  const match=/^puppetHand([0-3])$/.exec(key);if(!match)return null;
  const d=project.design,index=+match[1],mirror=index%2===1&&d[index<2?'puppetArmSymmetry':'puppetExtraArmSymmetry'],sourceIndex=mirror?index-1:index;
  return {key:'puppetHand'+sourceIndex,index:sourceIndex,arm:d.puppetArms[sourceIndex]};
 }
 function hasPixels(image){return image.getContext('2d').getImageData(0,0,image.width,image.height).data.some((value,index)=>index%4===3&&value);}
 function nativePart(info){
  const model=project.legacyOracle&&typeof legacyModel!=='undefined'&&legacyModel?legacyModel:preset;
  return model?.parts?.find(part=>part.kind==='hand'&&(part.xy.filter((_,i)=>i%2===0).reduce((a,b)=>a+b,0)>0)===(info.index%2===1));
 }
 async function prepare(key){
  const info=target(key);if(!info)return true;
  const tex=project.textures[info.key],base=canvases[info.key]?.[0];
  if(tex?.editableBase||base&&hasPixels(base))return true;
  const part=nativePart(info);if(!part?.png)return false;
  imageOf(part.png);const im=images.get(part.png);if(!im)return false;
  try{await im.decode();return !!im.naturalWidth;}catch{return false;}
 }
 function original(info){
  const part=nativePart(info);
  if(!part?.png)return null;
  const arm=info.arm,tint=arm.handTextureTint??arm.handOwnColor??false;
  // When texture tint is enabled, leave the native mask white so the later
  // single color multiplication restores the intended original hand color.
  return tintImage(part.png,tint?'#ffffff':arm.handOwnColor?arm.handColor:project.design.headColor);
 }
 function source(key){
  const info=target(key);if(!info)return composite(key);
  const tex=project.textures[info.key],base=canvases[info.key]?.[0],art=composite(info.key);
  // This is only a paint guide for an untouched native hand. Old custom hand
  // projects retain their exact composed artwork until explicitly edited.
  if(info.arm.handTextureEnabled||tex.editableBase||tex.layers[0]?.visible===false||!base||hasPixels(base))return art;
  const native=original(info);if(!native)return art;
  const result=canvas(art.width,art.height),ctx=result.getContext('2d');ctx.imageSmoothingEnabled=false;ctx.drawImage(native,0,0,result.width,result.height);ctx.drawImage(art,0,0);return result;
 }
 function ensure(key){
  const info=target(key);if(!info)return true;
  const tex=project.textures[info.key],base=canvases[info.key]?.[0];if(!tex||!base||tex.editableBase)return true;
  if(typeof PaintLayers!=='undefined')PaintLayers.requireEditable(info.key,0);
  if(!hasPixels(base)){
   const native=original(info);if(!native)return false;
   const ctx=base.getContext('2d');ctx.imageSmoothingEnabled=false;ctx.drawImage(native,0,0,base.width,base.height);
   tex.layers[0].visible??=true;tex.layers[0].opacity??=1;
  }
  // A cleared or intentionally hidden initialized base stays cleared/hidden.
  tex.editableBase=true;return true;
 }
 return {target,source,ensure,prepare};
})();
