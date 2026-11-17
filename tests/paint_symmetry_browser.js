let checks=0,stroke,target='face',activeLayer=0,canvases={},dimensions={},project={textures:{},design:{}},historyBusy=false;
const canvas=(width,height)=>Object.assign(document.createElement('canvas'),{width,height});
const MI18n={text:s=>s,t:key=>key},PuppetArms={selectedTarget:key=>key},fabricKey=()=>false;
function initializePaintStroke(){if(!stroke.original){const c=canvases.face[0];stroke.original=c.getContext('2d').getImageData(0,0,c.width,c.height);}return true;}
function check(value,message){checks++;if(!value)throw Error(message);}
function pixels(c=canvases.face[0]){return c.getContext('2d').getImageData(0,0,c.width,c.height).data;}
function setup(tool='pen',sx=false,sy=false,width=7,height=5){
 const c=canvas(width,height);canvases={face:[c]};dimensions={face:[width,height]};project.textures.face={layers:[{id:'one',visible:true,locked:false,opacity:1}]};
 stroke={tool,size:1,alpha:.4,color:'#ff0000',symmetry:sx,symmetryY:sy,coverage:new Map(),grain:new Map(),original:null};return c;
}
function sameMirror(c,sx,sy){const p=pixels(c);for(let y=0;y<c.height;y++)for(let x=0;x<c.width;x++){const at=(y*c.width+x)*4,other=((sy?c.height-1-y:y)*c.width+(sx?c.width-1-x:x))*4;for(let k=0;k<4;k++)if(p[at+k]!==p[other+k])return false;}return true;}
try{
 for(const [sx,sy,count] of [[false,false,1],[true,false,2],[false,true,2],[true,true,4]]){
  setup('pen',sx,sy);dab(1,1);check(stroke.coverage.size===count,'Unexpected mirrored pen pixel count');check([...pixels()].filter((_,i)=>i%4===3).filter(Boolean).length===count,'Unexpected painted pen pixel count');
 }
 setup('pen',true,true);dab(3,2);dab(3,2);check(stroke.coverage.size===1,'Centre axis pixel was duplicated');check(pixels()[(2*7+3)*4+3]===102,'Centre paint grew more opaque');
 setup('pen',true,true);stroke.size=5;dab(2,2);dab(4,2);check([...pixels()].filter((_,i)=>i%4===3).every(a=>a<=102),'Overlapping mirrored pen grew more opaque');check(sameMirror(canvases.face[0],true,true),'Mirrored pen is not symmetric');
 const erase=setup('erase',true,true);erase.getContext('2d').fillRect(0,0,7,5);dab(1,1);dab(5,3);check(pixels()[(1*7+1)*4+3]===153,'Mirrored eraser applied twice');check(pixels()[(2*7+3)*4+3]===255,'Eraser touched unrelated pixels');
 setup('spray',true,true,9,9);stroke.size=5;dab(2,2);check(sameMirror(canvases.face[0],true,true),'Spray opacity is not mirrored');
 setup('grain',true,true);let randomCalls=0;const originalRandom=Math.random;Math.random=()=>{randomCalls++;return .1;};try{dab(1,1);dab(5,3);}finally{Math.random=originalRandom;}check(randomCalls===1,'Mirrored grain used different random samples');check(stroke.coverage.size===4,'Mirrored grain lost a quadrant');
 setup('line',true,true,9,9);drawPaintSegment([1,1],[3,2]);check(sameMirror(canvases.face[0],true,true),'Line does not share XY symmetry');
 setup('pen',true,true);dab(-5,9);check(stroke.original===null&&stroke.coverage.size===0,'Out of bounds brush changed image');
 for(const [sx,sy] of [[false,false],[true,false],[false,true],[true,true]]){
  const fill=canvas(7,5),ctx=fill.getContext('2d'),g=ctx.createLinearGradient(0,0,7,5);g.addColorStop(0,'#112233');g.addColorStop(1,'#ddeeff');ctx.fillStyle=g;ctx.fillRect(0,0,7,5);const before=pixels(fill).slice();mirrorPaintGradient(fill,sx,sy);const p=pixels(fill);
  if(sx)check(sameMirror(fill,true,false),'Gradient X is not symmetric');if(sy)check(sameMirror(fill,false,true),'Gradient Y is not symmetric');
  check(p[(2*7+3)*4]===before[(2*7+3)*4],'Gradient modified the odd centre pixel');
  if(!sx&&!sy)check(p.every((value,index)=>value===before[index]),'Unsymmetric gradient changed');
 }
 const old={symmetry:true,layers:[{id:'kept',name:'old',locked:false,visible:true,opacity:1}]},oldText=JSON.stringify(old);PaintLayers.normalize(old,'face');check(JSON.stringify(old)===oldText,'Legacy texture was rewritten to add Y symmetry');check(PaintLayers.blank('face').symmetryY===false,'New texture does not default Y off');
 setup();project.textures.face.symmetry=true;project.textures.face.symmetryY=true;const saved=PaintLayers.snapshot('face',0);check(saved.texture.symmetry===true&&saved.texture.symmetryY===true,'History snapshot lost symmetry state');
 document.getElementById('result').textContent=JSON.stringify({ok:true,checks});
}catch(error){document.getElementById('result').textContent=JSON.stringify({ok:false,checks,error:error.stack});}
