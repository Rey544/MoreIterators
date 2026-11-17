let fixtureWorkflowRevision=0,fixturePending=null,fixtureWorkflowError=null,fixtureNameError=null,fixtureDraftRevision=0,fixtureDraft=null,fixtureDraftPreserved=false,fixtureHoldNames=false,fixtureReleaseNames=null;
let fixtureConnections=[{from:{room:roomBinding.ai,node:0},to:{room:roomBinding.entry,node:0}}];
let fixtureMultipleRequired=false;
const fixtureOriginalFetch=window.fetch;
function fixtureWorkflow(){
 const names=fixturePending?.names||roomBinding;
 const rooms=['ai','entry'].map(kind=>({name:names[kind],kind,owned:true,region:names.region,exitCount:kind==='ai'?2:2,verified:true,connections:fixturePending?['DISCONNECTED','DISCONNECTED']:[kind==='ai'?names.entry:names.ai,'DISCONNECTED']}));
 return {projectId:'oc-room-fixture',revision:fixtureWorkflowRevision,binding:structuredClone(roomBinding),pending:structuredClone(fixturePending),rooms,connections:structuredClone(fixtureConnections)};
}
window.fetch=async(input,options={})=>{
 const url=new URL(input,'http://fixture.invalid'),route=url.pathname.replace('/api/',''),body=options.body?JSON.parse(options.body):null;
 if(!route.startsWith('room-workflow')&&route!=='room-draft')return fixtureOriginalFetch(input,options);
 roomCalls.push({route,query:Object.fromEntries(url.searchParams),body});
 if(route==='room-draft'){
  if(body){if(body.revision!==fixtureDraftRevision)return {ok:false,json:async()=>({error:'Draft changed in another page'})};fixtureDraft=body.binding;fixtureDraftRevision++;}
  return {ok:true,json:async()=>({revision:fixtureDraftRevision,binding:structuredClone(fixtureDraft)})};
 }
 if(route==='room-workflow')return {ok:true,json:async()=>fixtureWorkflow()};
 if(body.revision!==fixtureWorkflowRevision)return {ok:false,json:async()=>({error:'Workflow changed in another page'})};
 if(route==='room-workflow/names'){
  if(fixtureNameError)return {ok:false,json:async()=>fixtureNameError};
  if(fixtureHoldNames)await new Promise(resolve=>fixtureReleaseNames=resolve);
  const names=Object.fromEntries(Object.entries(body.names).map(([key,value])=>[key,value.trim().toUpperCase()]));
  fixturePending={id:'pending-fixture',names,rooms:['ai','entry'].map(kind=>({kind,name:names[kind],original:roomBinding[kind],exitCount:2})),required:[{id:'old-pair',room:names.ai,node:0,toRoom:names.entry,toNode:0}]};fixtureWorkflowRevision++;
  if(fixtureMultipleRequired)fixturePending.required.push({id:'old-external',room:names.entry,node:1,toRoom:roomItems.find(room=>room.name.endsWith('_GARDEN')).name,toNode:1});
 }else if(route==='room-workflow/cancel'){fixturePending=null;fixtureWorkflowRevision++;}
 else if(route==='room-workflow/apply'){
  if(fixtureWorkflowError)return {ok:false,json:async()=>fixtureWorkflowError};
  if(fixturePending)Object.assign(roomBinding,fixturePending.names);
  fixtureConnections=body.connections.map(({from,to})=>({from,to}));fixturePending=null;fixtureWorkflowRevision++;
  if(!fixtureDraftPreserved){fixtureDraft=structuredClone(roomBinding);fixtureDraftRevision++;}
  return {ok:true,json:async()=>({...fixtureWorkflow(),draftRevision:fixtureDraftRevision,draftPreserved:fixtureDraftPreserved})};
 }else throw Error('Unexpected workflow fixture route '+route);
 return {ok:true,json:async()=>fixtureWorkflow()};
};
