let fixtureLoadFailure='room-workflow',fixtureLoadIssues=[],fixtureReconcileCalls=[];
const loadingFixtureFetch=window.fetch;
window.fetch=async(input,options={})=>{
 const url=new URL(input,'http://fixture.invalid'),route=url.pathname.replace('/api/',''),body=options.body?JSON.parse(options.body):null;
 if(route==='projects')return {ok:true,json:async()=>[{projectId:'oc-room-fixture',name:'First'},{projectId:'oc-room-second',name:'Second'}]};
 if(!body&&route===fixtureLoadFailure)return {ok:false,json:async()=>({error:'TEST_ENTRY geometry count 2 does not match world_test.txt count 1'})};
 if(route==='room-workflow/apply'&&body?.reconcileRooms){
  fixtureReconcileCalls.push(structuredClone(body));roomCalls.push({route,body});fixtureLoadIssues=[];fixtureWorkflowRevision++;
  return {ok:true,json:async()=>({...fixtureWorkflow(),editable:true,issues:[]})};
 }
 const response=await loadingFixtureFetch(input,options);if(!response.ok)return response;
 let value=await response.json();
 if(route==='room-workflow'){
  value.editable=true;value.issues=structuredClone(fixtureLoadIssues);
  for(const issue of value.issues){const room=value.rooms.find(room=>room.name===issue.room);if(room){room.connections=room.connections.slice(0,1);room.verified=false;room.exitCount=issue.actualExitCount;room.actualExitCount=issue.actualExitCount;room.connectionSlotCount=issue.connectionSlotCount;room.issues=[issue];}}
 }
 if(url.searchParams.get('projectId')==='oc-room-second'&&['room-binding','room-workflow'].includes(route))value=JSON.parse(JSON.stringify(value).replaceAll('TEST_', 'SECOND_'));
 return {ok:true,json:async()=>value};
};
