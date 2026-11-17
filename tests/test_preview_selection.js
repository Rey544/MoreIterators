'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../editor/preview-selection.js'),'utf8');
const api=require('../editor/preview-selection.js');
const tests=[];
function test(name,run){run();tests.push(name);}
function record(key,points=[0,0,20,0,20,20,0,20],image=null){return {key,points,triangles:[0,1,2,0,2,3],image,uv:[0,0,1,0,1,1,0,1],alpha:1,bounds:[0,0,20,20]};}
test('triangle geometry rejects outside and degenerate surfaces',()=>{
 assert.equal(api.barycentric([30,30],[0,0,20,0,0,20]),null);
 assert.equal(api.barycentric([0,0],[0,0,0,0,0,0]),null);
 assert.deepEqual(api.barycentric([5,5],[0,0,20,0,0,20]),[.5,.25,.25]);
});
test('hits follow drawing order and deduplicate one part',()=>{
 assert.deepEqual(api.hits([10,10],[record('body'),record('cloth'),record('cloth')]),['cloth','body']);
});
test('transparent image pixels allow selecting underlying material',()=>{
 const image={};assert.deepEqual(api.hits([10,10],[record('body'),record('cloth',undefined,image)],()=>false),['body']);
 assert.deepEqual(api.hits([10,10],[record('body'),record('cloth',undefined,image)],()=>true),['cloth','body']);
});
test('texture samples use triangle UV coordinates',()=>{
 let observed;api.hit(record('cloth',undefined,{}),[5,10],(image,u,v)=>{observed=[u,v];return true;});assert.deepEqual(observed,[.25,.5]);
});
test('zero opacity and pointer outside a room preview cannot be picked',()=>{
 const hidden=record('hidden');hidden.alpha=0;assert.deepEqual(api.hits([10,10],[hidden]),[]);assert.deepEqual(api.hits([30,10],[record('visible')]),[]);
});
test('pan zoom device pixel ratio and mirror transforms affect pick geometry',()=>{
 const points=api.transformed([0,0,10,10],{a:-4,b:0,c:0,d:4,e:100,f:50});assert.deepEqual(points,[100,50,60,90]);
});
test('repeated clicks cycle overlapping materials and wrap',()=>{
 let result=api.cycle(['front','back'],[10,10],null,100);assert.equal(result.key,'front');result=api.cycle(['front','back'],[12,10],result.click,200);assert.equal(result.key,'back');result=api.cycle(['front','back'],[12,10],result.click,300);assert.equal(result.key,'front');
});
test('moving to another location resets overlap cycling',()=>{
 const first=api.cycle(['front','back'],[10,10],null,100);assert.equal(api.cycle(['front','back'],[20,10],first.click,200).key,'front');
});
test('changed hidden parts and long pauses reset overlap cycling',()=>{
 const first=api.cycle(['front','back'],[10,10],null,100);assert.equal(api.cycle(['back'],[10,10],first.click,200).key,'back');assert.equal(api.cycle(['front','back'],[10,10],first.click,2000).key,'front');
});
test('empty background clears overlap cycling',()=>{
 assert.deepEqual(api.cycle([],[10,10],null,100),{key:null,click:null});
});
function fixture(){
 const locations=[],updates=[],saved={};let clock=100;
 const context={getTransform:()=>({a:1,b:0,c:0,d:1,e:0,f:0})};
 const canvas={width:200,height:100,getBoundingClientRect:()=>({left:0,top:0,width:200,height:100})};
 const sandbox={localStorage:{getItem:()=>null,setItem:(k,v)=>saved[k]=v},project:{projectId:'one',design:{frontSymmetry:true},textures:{}},loading:false,changingProject:false,document:{getElementById:()=>canvas},performance:{now:()=>clock++},requestAnimationFrame:()=>1,
  PaintTargets:{available:key=>key==='sleeveR',locateSettings:key=>locations.push(key)},PuppetArms:{select:()=> 'sleeve'},stroke:null,target:'face',activeLayer:4,canvases:{sleeve:[{},{}]},updateTarget:()=>updates.push(true)};
 vm.runInNewContext(source+'\nglobalThis.selection=PreviewSelection;',sandbox);
 const selection=sandbox.selection;return {selection,sandbox,locations,updates,saved,context};
}
test('hover does not select a part or move the settings pane',()=>{
 const f=fixture();f.selection.begin(f.context);f.selection.rect('sleeveR',null,0,0,20,20,f.context);f.selection.move({clientX:10,clientY:10});assert.deepEqual(f.locations,[]);assert.deepEqual(f.updates,[]);assert.equal(f.sandbox.target,'face');
});
test('explicit click updates texture selection and jumps once without changing project data',()=>{
 const f=fixture(),before=JSON.stringify(f.sandbox.project);f.selection.begin(f.context);f.selection.rect('sleeveR',null,0,0,20,20,f.context);f.selection.click({clientX:10,clientY:10});assert.equal(f.sandbox.target,'sleeve');assert.equal(f.sandbox.activeLayer,1);assert.deepEqual(f.locations,['sleeveR']);assert.equal(f.updates.length,1);assert.equal(JSON.stringify(f.sandbox.project),before);assert.deepEqual(f.saved,{});
});
test('non texture parts navigate without replacing the painting target',()=>{
 const f=fixture();f.selection.begin(f.context);f.selection.rect('head',null,0,0,20,20,f.context);f.selection.click({clientX:10,clientY:10});assert.equal(f.sandbox.target,'face');assert.deepEqual(f.locations,['head']);assert.equal(f.updates.length,0);
});
test('changing projects resets click cycling and ignores old geometry',()=>{
 const f=fixture();f.selection.begin(f.context);f.selection.rect('body',null,0,0,20,20,f.context);f.selection.rect('head',null,0,0,20,20,f.context);f.selection.click({clientX:10,clientY:10});f.sandbox.project={projectId:'two',design:{},textures:{}};f.selection.begin(f.context);f.selection.rect('other',null,0,0,20,20,f.context);f.selection.click({clientX:10,clientY:10});assert.deepEqual(f.locations,['head','other']);
});
test('canceling a pan or zoom prevents an accidental repeated click cycle',()=>{
 const f=fixture();f.selection.begin(f.context);f.selection.rect('body',null,0,0,20,20,f.context);f.selection.rect('head',null,0,0,20,20,f.context);f.selection.click({clientX:10,clientY:10});f.selection.cancel();f.selection.click({clientX:10,clientY:10});assert.deepEqual(f.locations,['head','head']);
});
test('fit to window measurement never adds selectable geometry',()=>{
 const f=fixture();f.selection.begin(f.context,true);f.selection.rect('head',null,0,0,20,20,f.context);f.selection.click({clientX:10,clientY:10});assert.deepEqual(f.locations,[]);
});
console.log(JSON.stringify({tests:tests.length,passed:tests.length,failures:0,cases:tests},null,2));
