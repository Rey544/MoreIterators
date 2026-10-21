'use strict';
let necklaceSizeClipboard=null;
function necklacePearl(color='#c5d6ce',highlight='#b7e5ef',dual=false){return {color,highlight,dual,size:0};}
function necklaceStrand(i=0){return {pearls:9,size:2.2,thickness:.4,leftX:-5,leftY:0,rightX:5,rightY:0,symmetric:true,sag:8+i*4,softness:.7,stringColor:'#737e78',colorMode:0,primary:necklacePearl(),alternate:necklacePearl('#354d45','#d2ebe2',true),beads:[]};}
function necklaceStyle(row,i){return row.colorMode===2&&row.beads[i]?row.beads[i]:row.colorMode===1&&i%2?row.alternate:row.primary;}
function buildNecklaceSettings(host,d,changed){
 let group=document.createElement('details');group.id='necklaceSettings';group.dataset.sectionId='necklaces';let summary=document.createElement('summary');summary.textContent='珍珠项链';group.append(summary);

 let rows=document.createElement('div');
 function field(parent,label,obj,key,type,min,max,step,options,after){
  let row=document.createElement('label');row.className='field';let span=document.createElement('span');span.textContent=label;let input=document.createElement(type==='select'?'select':'input'),output;
  input.setAttribute('aria-label',label);input.dataset.necklace=key;
  if(type==='select'){for(let [value,name] of Object.entries(options)){let option=document.createElement('option');option.value=value;option.textContent=name;input.append(option);}input.value=obj[key];}
  else{input.type=type;if(type==='range'){input.min=min;input.max=max;input.step=step;}if(type==='checkbox')input.checked=obj[key];else input.value=obj[key];if(type==='range'){output=document.createElement('output');output.textContent=input.value;}}
  input.oninput=()=>{obj[key]=type==='checkbox'?input.checked:type==='color'?input.value:Number(input.value);if(output)output.textContent=input.value;if(after)after(input);changed();};row.append(span,input);if(output)row.append(output);parent.append(row);return row;
 }
 function colors(parent,label,p){
  let section=document.createElement('div');parent.append(section);let header=document.createElement('p');header.className='hint';header.textContent=label;section.append(header);
  let highlight;field(section,label+' · 双色高光',p,'dual','checkbox',0,0,0,null,()=>{highlight.hidden=!p.dual;});field(section,label+' · 主体色',p,'color','color');highlight=field(section,label+' · 高光色',p,'highlight','color');highlight.hidden=!p.dual;
 }
 function rebuild(){
  rows.replaceChildren();for(let i=0;i<d.necklaceCount;i++){
   d.necklaces[i]??=necklaceStrand(i);let v=d.necklaces[i],section=document.createElement('details'),title=document.createElement('summary');title.textContent='第 '+(i+1)+' 条项链';section.append(title);section.open=i===0;rows.append(section);const prefix='项链 '+(i+1)+' · ';
   const slider=(label,key,min,max,step,after)=>field(section,prefix+label,v,key,'range',min,max,step,null,after);
   function copySize(parent,label,get,set){let box=document.createElement('div');box.className='tools';for(let action of ['复制','粘贴']){let b=document.createElement('button');b.textContent=action+label;b.setAttribute('aria-label',prefix+action+label);b.onclick=()=>{if(action==='复制'){necklaceSizeClipboard=get();notice('已复制大小 '+necklaceSizeClipboard);}else if(necklaceSizeClipboard!==null){set(necklaceSizeClipboard);changed();}else notice('请先复制一个大小。');};box.append(b);}parent.append(box);}
   let individual,sizeDetails;slider('珍珠数量','pearls',0,32,1,()=>{if(individual)individual();if(sizeDetails)sizeDetails();});let strandSize=slider('珍珠直径','size',.6,6,.1);copySize(section,'本层大小',()=>v.size,n=>{v.size=n;strandSize.querySelector('input').value=n;strandSize.querySelector('output').textContent=n;});
   let perSize=document.createElement('details'),perTitle=document.createElement('summary'),perBody=document.createElement('div');perTitle.textContent=prefix+'逐颗大小';perSize.append(perTitle,perBody);section.append(perSize);
   sizeDetails=()=>{perBody.replaceChildren();if(!v.pearls)return;let chooser=document.createElement('select');chooser.setAttribute('aria-label',prefix+'选择尺寸珍珠');for(let j=0;j<v.pearls;j++){let o=document.createElement('option');o.value=j;o.textContent='第 '+(j+1)+' 颗';chooser.append(o);v.beads[j]??=structuredClone(v.colorMode===1&&j%2?v.alternate:v.primary);v.beads[j].size??=0;}let detail=document.createElement('div');perBody.append(chooser,detail);const show=()=>{detail.replaceChildren();let bead=v.beads[+chooser.value],label=prefix+'第 '+(+chooser.value+1)+' 颗直径（0 跟随本层）';let row=field(detail,label,bead,'size','range',0,6,.1);copySize(detail,'此颗大小',()=>bead.size||v.size,n=>{bead.size=n;row.querySelector('input').value=n;row.querySelector('output').textContent=n;});};chooser.onchange=show;show();};sizeDetails();
   slider('线的粗细','thickness',.1,2,.05);field(section,prefix+'线的颜色',v,'stringColor','color');
   let rightX,rightY;field(section,prefix+'固定点左右对称',v,'symmetric','checkbox',0,0,0,null,()=>{rightX.hidden=rightY.hidden=v.symmetric;});
   slider('左固定点 · 左右','leftX',-18,18,.1);slider('左固定点 · 上下','leftY',-200,200,.1);rightX=slider('右固定点 · 左右','rightX',-18,18,.1);rightY=slider('右固定点 · 上下','rightY',-200,200,.1);rightX.hidden=rightY.hidden=v.symmetric;
   slider('下垂幅度','sag',0,26,.1);slider('柔软与弹性','softness',0,1,.01);
   let palette=document.createElement('div');function paintOptions(){palette.replaceChildren();if(v.colorMode===0)colors(palette,prefix+'整排',v.primary);else if(v.colorMode===1){colors(palette,prefix+'奇数颗',v.primary);colors(palette,prefix+'偶数颗',v.alternate);}else{
    if(!v.pearls){palette.textContent='先增加珍珠数量。';return;}
    let select=document.createElement('select');select.setAttribute('aria-label',prefix+'选择珍珠');for(let j=0;j<v.pearls;j++){let o=document.createElement('option');o.value=j;o.textContent='第 '+(j+1)+' 颗（从左固定点数起）';select.append(o);v.beads[j]??=structuredClone(j%2?v.alternate:v.primary);}
    let detail=document.createElement('div');palette.append(select,detail);let show=()=>{detail.replaceChildren();colors(detail,prefix+'第 '+(+select.value+1)+' 颗',v.beads[+select.value]);};select.onchange=show;show();
   }}individual=()=>{if(v.colorMode===2)paintOptions();};
   field(section,prefix+'配色方式',v,'colorMode','select',0,0,0,{0:'整排一致',1:'交替配色',2:'逐颗设置'},paintOptions);section.append(palette);paintOptions();
  }
 }
 field(group,'项链数量',d,'necklaceCount','select',0,0,0,{0:'关闭',1:'1 条',2:'2 条',3:'3 条',4:'4 条',5:'5 条'},rebuild);group.append(rows);rebuild();
 let scarf=[...host.children].find(v=>v.dataset.sectionId==='scarf');if(scarf)scarf.after(group);else host.append(group);
}
function drawNecklaces(ctx,d,anchors,guides){
 const center=anchors[0].map((v,i)=>(v+anchors[1][i])/2),scale=d.puppetScale;
 for(let n=d.necklaceCount-1;n>=0;n--){
  let row=d.necklaces[n]||necklaceStrand(n),a=[center[0]+row.leftX*scale,center[1]-row.leftY*scale],b=[center[0]+(row.symmetric?-row.leftX:row.rightX)*scale,center[1]-(row.symmetric?row.leftY:row.rightY)*scale],points=[],total=0;
  ctx.strokeStyle=row.stringColor;ctx.lineWidth=row.thickness*scale;ctx.lineJoin='round';ctx.beginPath();
  for(let i=0;i<25;i++){let u=i/24,p=[a[0]+(b[0]-a[0])*u,a[1]+(b[1]-a[1])*u+4*row.sag*scale*u*(1-u)];if(i){total+=Math.hypot(p[0]-points[i-1][0],p[1]-points[i-1][1]);ctx.lineTo(...p);}else ctx.moveTo(...p);points.push(p);}ctx.stroke();
  for(let i=0;i<row.pearls;i++){
   let remaining=total*(i+1)/(row.pearls+1),p=points[0];for(let j=1;j<points.length;j++){let len=Math.hypot(points[j][0]-points[j-1][0],points[j][1]-points[j-1][1]);if(remaining<=len||j===24){let u=len?Math.min(1,remaining/len):0;p=points[j-1].map((v,k)=>v+(points[j][k]-v)*u);break;}remaining-=len;}
   let style=necklaceStyle(row,i),diameter=(row.beads[i]?.size||row.size)*scale;
   MIPearlIcons.drawAt(ctx,p[0],p[1],diameter,MIPearlIcons.accessoryAppearance(style));
  }
  if(guides&&document.getElementById('necklaceSettings')?.open){ctx.fillStyle=referenceColor();ctx.fillRect(a[0]-.4,a[1]-.4,.8,.8);ctx.fillRect(b[0]-.4,b[1]-.4,.8,.8);}
 }
}
