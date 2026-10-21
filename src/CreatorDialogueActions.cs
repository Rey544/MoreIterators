namespace MoreIterators {
using System;
using System.Collections.Generic;
using System.Reflection;
using System.Runtime.CompilerServices;
using UnityEngine;

public sealed class CreatorActionClock {
 int wait,charge,total;public bool Active{get;private set;}public bool Waiting{get{return wait>0;}}public float Factor{get{return total==0?0:charge/(float)total;}}
 public void Start(float seconds,float duration=1){wait=(int)Math.Ceiling(Math.Max(0,Math.Min(60,seconds))*40);charge=0;total=Math.Max(1,(int)Math.Ceiling(duration*40));Active=true;}
 public void Cancel(){Active=false;wait=charge=0;}
 public bool Tick(bool valid,bool paused){if(!valid){Cancel();return false;}if(!Active||paused)return false;if(wait>0){wait--;return false;}if(++charge<total)return false;Active=false;return true;}
}
public sealed class CreatorDialogueActions {
 static readonly MethodInfo nativeEnterShortcut=typeof(Creature).GetMethod("SuckedIntoShortCut",BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic,null,new[]{typeof(RWCustom.IntVector2),typeof(bool)},null);
 sealed class Batch {public int remaining,completed;public bool signalled;public Action<bool> finished;public Action<int> progress;}
 sealed class Request {public CreatorGroupAction action;public Player player;public int restart;public string config,mode;public Batch batch;}
 static readonly ConditionalWeakTable<Oracle,CreatorDialogueActions> all=new ConditionalWeakTable<Oracle,CreatorDialogueActions>();
 public static CreatorDialogueActions For(Oracle o){return all.GetValue(o,x=>new CreatorDialogueActions(x));}
 readonly Oracle oracle;readonly CreatorActionClock clock=new CreatorActionClock();readonly Queue<Request> pending=new Queue<Request>();Request current;Vector2 destination,motionOrigin;bool markLiftStarted,motionStarted;Player controlledPlayer;Batch holdBatch;Vector2[] holdTargets,lastTargets;
 public bool Active{get{return current!=null||pending.Count>0;}}
 CreatorDialogueActions(Oracle o){oracle=o;}
 static bool Supported(string type){return type=="killPlayer"||type=="liftSpinPlayer"||type=="liftAndGiveMark"||type=="giveMark"||type=="movePlayerToExit";}
 static bool InRange(float value,float min,float max){return !Single.IsNaN(value)&&!Single.IsInfinity(value)&&value>=min&&value<=max;}
 static CreatorGroupAction Copy(CreatorGroupAction action){
  if(action==null||!Supported(action.type))throw new ArgumentException("Unsupported or nested action.");
  if(!InRange(action.delay,0,60))throw new ArgumentException("Invalid action delay.");
  if(action.type!="killPlayer"&&action.type!="giveMark"&&!InRange(action.duration,.25f,15))throw new ArgumentException("Invalid action duration.");
  if(action.type=="liftSpinPlayer"&&(!InRange(action.offsetX,-1000,1000)||!InRange(action.offsetY,-1000,1000)||!InRange(action.radius,0,200)||!InRange(action.endAngle,-1440,1440)))throw new ArgumentException("Invalid lift geometry.");
  return new CreatorGroupAction{type=action.type,delay=action.delay,duration=action.duration,exitNode=action.exitNode,offsetX=action.offsetX,offsetY=action.offsetY,radius=action.radius,endAngle=action.endAngle};
 }
 public void Schedule(CreatorGroupAction action,Player player,Action<bool> finished,Action<int> completedSteps=null){
  var begin=Completed(action,player,finished,completedSteps);if(begin!=null)begin();else if(finished!=null)finished(false);
 }
 public Action Completed(CreatorGroupAction action,Player player){return Completed(action,player,null,null);}
 Action Completed(CreatorGroupAction action,Player player,Action<bool> finished,Action<int> progress){
  if(action==null||(action.type!="sequence"&&!Supported(action.type))||player==null)return null;
  var batch=new Batch{finished=finished,progress=progress};var requests=new List<Request>();Exception invalid=null;
  try{
   var steps=action.type=="sequence"?action.actions:new[]{action};
   if(steps==null||steps.Length==0||steps.Length>16)throw new ArgumentException("An action sequence must contain 1 to 16 flat actions.");
   foreach(var step in steps)requests.Add(new Request{action=Copy(step),player=player,batch=batch,restart=CreatorEncounter.Restart,config=IteratorDesign.ForRoom(oracle.room).dialogueJson,mode=CreatorRuntime.Mode});
   batch.remaining=requests.Count;
  }catch(Exception error){invalid=error;}
  bool consumed=false;
  return delegate {
   if(consumed)return;consumed=true;
   if(invalid!=null){MiDiagnostics.Report("MI-DIALOGUE-ACTION","CreatorDialogueActions.Schedule",invalid,MiDiagnostics.Context(oracle.room));Signal(batch,false);return;}
   if(requests.Count==0||!Valid(requests[0])){Signal(batch,false);return;}
   foreach(var request in requests)pending.Enqueue(request);if(current==null)StartNext();
  };
 }
 void Signal(Batch batch,bool success){
  if(batch==null||batch.signalled)return;batch.signalled=true;
  try{if(batch.finished!=null)batch.finished(success);}catch(Exception error){MiDiagnostics.Report("MI-DIALOGUE-ACTION","CreatorDialogueActions.Finished",error,MiDiagnostics.Context(oracle.room));}
 }
 void CompletedStep(Request request){
  var batch=request.batch;batch.remaining--;batch.completed++;
  try{if(batch.progress!=null)batch.progress(batch.completed);}catch(Exception error){MiDiagnostics.Report("MI-DIALOGUE-ACTION","CreatorDialogueActions.Progress",error,MiDiagnostics.Context(oracle.room));}
  if(batch.remaining==0)Signal(batch,true);
 }
 public Action Completed(IEnumerable<CreatorDialogueLine> lines,Player player){var group=lines as CreatorDialogueGroup;return group==null?null:Completed(group.action,player);}
 bool Valid(Request request){return request!=null&&oracle.room!=null&&oracle.oracleBehavior is IteratorBehavior&&IteratorCatalog.IsAI(oracle.room.abstractRoom.name)&&CreatorRuntime.UsesDialogue(oracle.room.abstractRoom.name)&&request.player!=null&&!request.player.dead&&!request.player.slatedForDeletetion&&!request.player.inShortcut&&!request.player.enteringShortCut.HasValue&&request.player.room==oracle.room&&!oracle.slatedForDeletetion&&request.restart==CreatorEncounter.Restart&&request.config==IteratorDesign.ForRoom(oracle.room).dialogueJson&&request.mode==CreatorRuntime.Mode&&CreatorRuntime.Mode!="silent"&&!StudioRuntime.Recording;}
 void StartNext(){
  if(current!=null||pending.Count==0)return;current=pending.Dequeue();markLiftStarted=motionStarted=false;lastTargets=null;
  if(holdBatch!=current.batch||controlledPlayer!=current.player)ReleaseControl();
  if(!Valid(current)){Cancel();return;}
  try{
   var action=current.action;
   if(action.type=="movePlayerToExit")destination=oracle.room.MiddleOfTile(ExitShortcut(action.exitNode).StartTile);
   else if(action.type=="liftAndGiveMark"||action.type=="giveMark"){
    var game=oracle.room.game;
    if(!MoreIteratorsPlugin.Active&&(game==null||!game.IsStorySession||game.GetStorySession==null||game.GetStorySession.saveState==null||game.GetStorySession.saveState.deathPersistentSaveData==null))throw new ArgumentException("A communication mark requires a story save or creator preview.");
    if(action.type=="liftAndGiveMark")destination=MarkLiftDestination(current.player);
   }
   clock.Start(action.delay,action.type=="killPlayer"?1:action.type=="giveMark"?0:action.duration);
   MiDiagnostics.Info("dialogue.action","oracle="+IteratorDesign.ForRoom(oracle.room).oracleId+" action="+action.type+(action.type=="movePlayerToExit"?" exit="+action.exitNode:""));
  }catch(Exception error){MiDiagnostics.Report("MI-DIALOGUE-ACTION","CreatorDialogueActions.Start",error,MiDiagnostics.Context(oracle.room));Cancel();}
 }
 ShortcutData ExitShortcut(int node){
  var room=oracle.room;
  if(nativeEnterShortcut==null)throw new MissingMethodException("Creature.SuckedIntoShortCut");
  if(!room.shortCutsReady)throw new ArgumentException("Shortcuts are not ready in the current chamber.");
  if(node<0||room.abstractRoom.connections==null||node>=room.abstractRoom.connections.Length||room.abstractRoom.nodes==null||node>=room.abstractRoom.nodes.Length||room.abstractRoom.nodes[node].type!=AbstractRoomNode.Type.Exit)throw new ArgumentException("The configured exit is not an Exit node in the current chamber: "+node);
  if(room.abstractRoom.connections[node]<0)throw new ArgumentException("The configured exit is disconnected: "+node);
  var target=room.world.GetAbstractRoom(room.abstractRoom.connections[node]);
  if(target==null||target.ExitIndex(room.abstractRoom.index)<0)throw new ArgumentException("The configured exit has no connected destination: "+node);
  var shortcut=room.ShortcutLeadingToNode(node);
  if(shortcut.shortCutType!=ShortcutData.Type.RoomExit||shortcut.destNode!=node||room.GetTile(shortcut.StartTile).Terrain!=Room.Tile.TerrainType.ShortcutEntrance)throw new ArgumentException("The configured exit has no matching room shortcut: "+node);
  return shortcut;
 }
 public void Cancel(){
  var batches=new HashSet<Batch>();if(current!=null)batches.Add(current.batch);foreach(var request in pending)batches.Add(request.batch);
  ReleaseControl();clock.Cancel();pending.Clear();current=null;ClearVisual();foreach(var batch in batches)Signal(batch,false);
 }
 void ClearVisual(){var b=oracle.oracleBehavior as IteratorBehavior;if(b!=null){b.killFac=0;b.lastKillFac=0;}}
 Vector2 MarkLiftDestination(Player player){
  var start=player.mainBodyChunk.pos;var result=start;
  // Stop below a ceiling instead of pulling a player through authored room geometry.
  for(int rise=10;rise<=70;rise+=10){
   var candidate=new Vector2(Mathf.Clamp(start.x,40,oracle.room.PixelWidth-40),Mathf.Clamp(start.y+rise,40,oracle.room.PixelHeight-40));
   if(oracle.room.GetTile(candidate+new Vector2(0,16)).Solid||oracle.room.GetTile(candidate-new Vector2(0,16)).Solid)break;
   result=candidate;
  }
  return result;
 }
 void ReleaseControl(){
  var player=controlledPlayer;controlledPlayer=null;holdBatch=null;holdTargets=null;lastTargets=null;
  // Only damp our own surviving lift. Never move a departed, dead or shortcut player.
  if(player==null||player.dead||player.slatedForDeletetion||player.room!=oracle.room||player.inShortcut||player.enteringShortCut.HasValue)return;
  foreach(var chunk in player.bodyChunks)chunk.vel*=.2f;
  // Stun(2) expires naturally; no controller, gravity override or permanent lock is installed.
 }
 void HoldPlayer(Request request){
  if(holdTargets==null||holdBatch!=request.batch||controlledPlayer!=request.player)return;
  request.player.Stun(2);
  for(int i=0;i<request.player.bodyChunks.Length&&i<holdTargets.Length;i++){
   var chunk=request.player.bodyChunks[i];chunk.vel=chunk.vel*.8f+Vector2.ClampMagnitude(holdTargets[i]-chunk.pos,40)*.2f;
  }
 }
 void GiveMark(Player player){
  var game=oracle.room.game;
  if(game!=null&&game.IsStorySession&&game.GetStorySession!=null&&game.GetStorySession.saveState!=null&&game.GetStorySession.saveState.deathPersistentSaveData!=null)game.GetStorySession.saveState.deathPersistentSaveData.theMark=true;
  if(MoreIteratorsPlugin.Active)CreatorRuntime.GrantMark();
  // This action grants communication only. Calling native General_GiveMark would
  // also change karma/Hunter cycles or extract Spearmaster's pearl in some campaigns.
  try{
   var graphics=player.graphicsModule as PlayerGraphics;if(graphics!=null)graphics.markAlpha=1;
   for(int i=0;i<20;i++)oracle.room.AddObject(new Spark(player.mainBodyChunk.pos,RWCustom.Custom.RNV()*UnityEngine.Random.value*40,Color.white,null,30,120));
   oracle.room.PlaySound(SoundID.SS_AI_Give_The_Mark_Boom,0f,1f,1f);
  }catch(Exception error){MiDiagnostics.Report("MI-DIALOGUE-ACTION","CreatorDialogueActions.MarkEffects",error,MiDiagnostics.Context(oracle.room));}
 }
 void MovePlayer(Player player,float progress,bool spin){
  player.Stun(2);
  if(!motionStarted){
   motionStarted=true;motionOrigin=player.mainBodyChunk.pos;
   holdTargets=null;
   if(spin){
    destination=new Vector2(Mathf.Clamp(motionOrigin.x+current.action.offsetX,40,oracle.room.PixelWidth-40),Mathf.Clamp(motionOrigin.y+current.action.offsetY,40,oracle.room.PixelHeight-40));
    if(player.tongue!=null&&player.tongue.Attached)player.tongue.Release();
   }
   if(current.action.type=="movePlayerToExit")foreach(var chunk in player.bodyChunks)chunk.vel*=0;
  }
  Vector2 target=destination;
  if(spin){
   target=Vector2.Lerp(motionOrigin,destination,progress);
   if(current.action.radius>0){
    // The authored radius moves the entire player around the moving orbit centre.
    // Body spacing remains fixed; a large orbit must never stretch the creature.
    float orbitAngle=progress*current.action.endAngle*(float)Math.PI/180;
    target+=new Vector2((float)Math.Cos(orbitAngle),(float)Math.Sin(orbitAngle))*current.action.radius;
   }
  }
  if(current.action.type=="movePlayerToExit"){
   // Stay outside the entrance until the authored clock completes. Pulling at the
   // entrance from frame one lets native shortcut physics finish a long action early.
   float distance=Vector2.Distance(motionOrigin,destination);
   var outside=distance>48?destination-(destination-motionOrigin).normalized*48:motionOrigin;
   target=Vector2.Lerp(motionOrigin,outside,progress);
  }
  if(spin||current.action.type=="liftAndGiveMark"){controlledPlayer=player;holdBatch=current.batch;}
  lastTargets=new Vector2[player.bodyChunks.Length];
  // Native-style velocity damping and short Stun preserve ordinary physics.
  for(int i=0;i<player.bodyChunks.Length;i++){
   float angle=progress*current.action.endAngle*(float)Math.PI/180+i*(float)Math.PI;
   // Radius zero means a straight lift, with ordinary body spacing intact.
   Vector2 offset=spin&&current.action.radius>0?new Vector2((float)Math.Cos(angle)*8,(float)Math.Sin(angle)*8):new Vector2(0,i==0?8:-8);
   lastTargets[i]=target+offset;
   var chunk=player.bodyChunks[i];chunk.vel=chunk.vel*.8f+Vector2.ClampMagnitude(target+offset-chunk.pos,40)*.2f;
   if(current.action.type=="movePlayerToExit")KeepOutsideExit(chunk);
  }
 }
 void KeepOutsideExit(BodyChunk chunk){
  var away=chunk.pos-destination;float distance=Vector2.Distance(chunk.pos,destination);
  if(distance<.01f)away=new Vector2(oracle.room.PixelWidth*.5f,oracle.room.PixelHeight*.5f)-destination;
  if(Vector2.Distance(away,new Vector2())<.01f)away=new Vector2(0,1);
  var normal=away.normalized;float radial=chunk.vel.x*normal.x+chunk.vel.y*normal.y;
  // Bound only the entrance-facing component; preserve tangential motion. The
  // 32px guard covers both body chunks even when initial momentum or offsets
  // would cross the entrance before the scheduled native handoff.
  float minimum=32-distance;
  if(radial<minimum)chunk.vel+=normal*(minimum-radial);
 }
 public void Update(){
  if(!Active)return;
  if(!Valid(current)){Cancel();return;}
  if(CreatorRuntime.Paused)return;
  var b=(IteratorBehavior)oracle.oracleBehavior;var request=current;bool waiting=clock.Waiting;bool execute=clock.Tick(true,false);
  b.player=request.player;b.lookPoint=request.player.mainBodyChunk.pos;
  if(waiting||request.action.type=="giveMark"||request.action.type=="killPlayer")HoldPlayer(request);
  if(request.action.type=="killPlayer"){b.lastKillFac=b.killFac;b.killFac=clock.Factor;}
  else if(!waiting&&request.action.type!="giveMark"){
   if(request.action.type=="liftAndGiveMark"&&!markLiftStarted){
    markLiftStarted=true;
    if(request.player.tongue!=null&&request.player.tongue.Attached)request.player.tongue.Release();
    try{oracle.room.PlaySound(SoundID.SS_AI_Give_The_Mark_Telekenisis,0f,1f,1f);}
    catch(Exception error){MiDiagnostics.Report("MI-DIALOGUE-ACTION","CreatorDialogueActions.MarkSound",error,MiDiagnostics.Context(oracle.room));}
   }
   MovePlayer(request.player,clock.Factor,request.action.type=="liftSpinPlayer");
  }
  if(!execute)return;
  bool nextInBatch=pending.Count>0&&pending.Peek().batch==request.batch;
  if(nextInBatch&&(request.action.type=="liftSpinPlayer"||request.action.type=="liftAndGiveMark"))holdTargets=lastTargets;
  else if(!nextInBatch)ReleaseControl();
  current=null;ClearVisual();
  try{
   // Consume before touching game state. Completed children are never retried.
   if(request.action.type=="liftAndGiveMark"||request.action.type=="giveMark")GiveMark(request.player);
   else if(request.action.type=="killPlayer"){
    ReleaseControl();var victim=request.player;
    victim.mainBodyChunk.vel+=RWCustom.Custom.RNV()*12;
    for(int i=0;i<20;i++)oracle.room.AddObject(new Spark(victim.mainBodyChunk.pos,RWCustom.Custom.RNV()*UnityEngine.Random.value*40,Color.white,null,30,120));
    victim.Die();
   }else if(request.action.type=="movePlayerToExit"){
    // Native transport carries connected objects and removes them from the room.
    ReleaseControl();var shortcut=ExitShortcut(request.action.exitNode);if(request.player.tongue!=null&&request.player.tongue.Attached)request.player.tongue.Release();nativeEnterShortcut.Invoke(request.player,new object[]{shortcut.StartTile,false});
   }
  }catch(Exception error){MiDiagnostics.Report("MI-DIALOGUE-ACTION","CreatorDialogueActions.Execute",error,MiDiagnostics.Context(oracle.room));Signal(request.batch,false);Cancel();return;}
  CompletedStep(request);
  if(request.action.type=="killPlayer"||request.action.type=="movePlayerToExit"){Cancel();return;}
  StartNext();
 }
}
}
