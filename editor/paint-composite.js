'use strict';
const PaintComposite=(()=>{
 function groups(layers,order=layers.map((_,index)=>index)){
  const result=[];
  for(const index of order){if(layers[index].clipToBelow===true&&result.length)result[result.length-1].push(index);else result.push([index]);}
  return result;
 }
 function draw(ctx,image,layer,operation='source-over'){
  if(!image||layer.visible===false)return;
  ctx.save();ctx.globalCompositeOperation=operation;ctx.globalAlpha=layer.opacity??1;ctx.drawImage(image,0,0);ctx.restore();
 }
 function group(layers,images,create,size,indices,rawBase=null){
  const result=create(...size),ctx=result.getContext('2d'),base=indices[0];
  if(base===0&&rawBase)ctx.drawImage(rawBase,0,0);else draw(ctx,images[base],layers[base]);
  for(const index of indices.slice(1))draw(ctx,images[index],layers[index],'source-atop');
  return result;
 }
 function compose(layers,images,create,size,order=null,rawBase=null){
  const result=create(...size),ctx=result.getContext('2d');
  for(const indices of groups(layers,order??undefined))ctx.drawImage(group(layers,images,create,size,indices,rawBase),0,0);
  return result;
 }
 function parts(layers,images,create,size,rawBase){
  const stacks=groups(layers),base=stacks.length?group(layers,images,create,size,stacks[0],rawBase):create(...size),overlay=create(...size),ctx=overlay.getContext('2d');
  if(!stacks.length&&rawBase)base.getContext('2d').drawImage(rawBase,0,0);
  for(const indices of stacks.slice(1))ctx.drawImage(group(layers,images,create,size,indices),0,0);
  return {base,overlay};
 }
 function mergePlan(layers,index,order=layers.map((_,i)=>i)){
  const at=order.indexOf(index);if(at<=0)return null;
  const lower=order[at-1];
  if(layers[index].clipToBelow===true)return {lower,indices:[lower,index],clipToBelow:layers[lower].clipToBelow===true,clipped:true};
  const stacks=groups(layers,order),position=stacks.findIndex(stack=>stack[0]===index);
  if(position<=0)return null;
  return {lower:stacks[position-1][0],indices:stacks[position-1].concat(stacks[position]),clipToBelow:false,clipped:false};
 }
 return {groups,group,compose,parts,mergePlan};
})();
if(typeof module!=='undefined')module.exports=PaintComposite;
