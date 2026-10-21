namespace MoreIterators {
using System;
using System.IO;
using System.Collections.Generic;
using UnityEngine;

[Serializable] public sealed class CreatorDialogueLine {
 public string text="",lineId="";public float hold=2,gap=.6f;public CreatorGroupAction beforeAction=new CreatorGroupAction(),action=new CreatorGroupAction();
 public CreatorReadingPresentationOptions presentation=new CreatorReadingPresentationOptions();
 public static bool HasText(CreatorDialogueLine line){return line!=null&&!System.String.IsNullOrWhiteSpace(line.text);}
 public static bool Runnable(CreatorDialogueLine line){return HasText(line)||line!=null&&(CreatorGroupAction.Usable(line.beforeAction)||CreatorGroupAction.Usable(line.action));}
}
public sealed class CreatorDialogueProfile {
 public CreatorPearlRules pearlReading=new CreatorPearlRules();
 public CreatorAffinityRules affinity=new CreatorAffinityRules();public CreatorObservationRules observation=new CreatorObservationRules();
 public CreatorGroupAction firstAction=new CreatorGroupAction(),repeatAction=new CreatorGroupAction(),loopAction=new CreatorGroupAction();
 public CreatorMeetingCondition firstCondition=new CreatorMeetingCondition(),repeatCondition=new CreatorMeetingCondition();
 public string storyMode="sequence";public CreatorMeeting[] meetings=new CreatorMeeting[0];
 public List<CreatorDialogueLine> loop=new List<CreatorDialogueLine>();
 public bool enabled,requireMark=true,pickupEnabled=true,leaveEnabled=true;
 public float cooldown=4;
 public List<CreatorDialogueLine> first=new List<CreatorDialogueLine>(),repeat=new List<CreatorDialogueLine>();
 public List<List<CreatorDialogueLine>> pickup=new List<List<CreatorDialogueLine>>(),leaving=new List<List<CreatorDialogueLine>>(),returning=new List<List<CreatorDialogueLine>>();
 static readonly Dictionary<string,CreatorDialogueProfile> cache=new Dictionary<string,CreatorDialogueProfile>();
 static T Val<T>(Dictionary<string,object> d,string k,T fallback){object v;try{return d.TryGetValue(k,out v)?(T)Convert.ChangeType(v,typeof(T)):fallback;}catch{return fallback;}}
 static List<CreatorDialogueLine> Lines(object raw){var result=new List<CreatorDialogueLine>();var list=raw as List<object>;if(list!=null)foreach(var x in list){var d=x as Dictionary<string,object>;if(d==null)continue;var line=new CreatorDialogueLine{text=Val(d,"text",""),lineId=Val(d,"lineId",""),beforeAction=d.ContainsKey("beforeAction")?PearlProjectCodec.ReadObject<CreatorGroupAction>(d["beforeAction"]):new CreatorGroupAction(),action=d.ContainsKey("action")?PearlProjectCodec.ReadObject<CreatorGroupAction>(d["action"]):new CreatorGroupAction(),presentation=d.ContainsKey("presentation")?PearlProjectCodec.ReadObject<CreatorReadingPresentationOptions>(d["presentation"]):new CreatorReadingPresentationOptions(),hold=Mathf.Clamp(Val(d,"hold",2f),.1f,60),gap=Mathf.Clamp(Val(d,"gap",.6f),0,60)};if(CreatorDialogueLine.Runnable(line))result.Add(line);}return result;}
 static List<List<CreatorDialogueLine>> Pool(Dictionary<string,object> d,string k){var result=new List<List<CreatorDialogueLine>>();object raw;if(d.TryGetValue(k,out raw)){var arr=raw as List<object>;if(arr!=null)foreach(var x in arr){var item=x as Dictionary<string,object>;object list;if(item!=null&&item.TryGetValue("lines",out list)){var lines=Lines(list);if(lines.Count>0){var group=new CreatorDialogueGroup(lines);object action;if(item.TryGetValue("action",out action))group.action=PearlProjectCodec.ReadObject<CreatorGroupAction>(action);result.Add(group);}}}}return result;}
 public static CreatorDialogueProfile For(IteratorDesign d){string json=d.dialogueJson??"",key=String.IsNullOrEmpty(json)?d.oracleId+":"+d.firstDialogue+":"+d.repeatDialogue:json;CreatorDialogueProfile p;if(cache.TryGetValue(key,out p))return p;p=new CreatorDialogueProfile();
  try{var data=String.IsNullOrWhiteSpace(json)?null:Json.Deserialize(json) as Dictionary<string,object>;if(data!=null){p.enabled=Val(data,"enabled",false);p.requireMark=Val(data,"requireMark",true);p.pickupEnabled=Val(data,"pickupEnabled",true);p.leaveEnabled=Val(data,"leaveEnabled",true);p.cooldown=Val(data,"cooldown",4f);object v;if(data.TryGetValue("first",out v))p.first=Lines(v);if(data.TryGetValue("repeat",out v))p.repeat=Lines(v);if(data.TryGetValue("loop",out v))p.loop=Lines(v);p.storyMode=Val(data,"storyMode","sequence");if(data.TryGetValue("firstCondition",out v))p.firstCondition=PearlProjectCodec.ReadObject<CreatorMeetingCondition>(v);if(data.TryGetValue("repeatCondition",out v))p.repeatCondition=PearlProjectCodec.ReadObject<CreatorMeetingCondition>(v);if(data.TryGetValue("meetings",out v)){var list=v as List<object>;if(list!=null){var parsed=new List<CreatorMeeting>();foreach(var item in list)parsed.Add(PearlProjectCodec.ReadObject<CreatorMeeting>(item));p.meetings=parsed.ToArray();}}p.pickup=Pool(data,"pickup");p.leaving=Pool(data,"leaving");p.returning=Pool(data,"returning");if(data.TryGetValue("affinity",out v))p.affinity=PearlProjectCodec.ReadObject<CreatorAffinityRules>(v);if(data.TryGetValue("observation",out v))p.observation=PearlProjectCodec.ReadObject<CreatorObservationRules>(v);if(data.TryGetValue("firstAction",out v))p.firstAction=PearlProjectCodec.ReadObject<CreatorGroupAction>(v);if(data.TryGetValue("repeatAction",out v))p.repeatAction=PearlProjectCodec.ReadObject<CreatorGroupAction>(v);if(data.TryGetValue("loopAction",out v))p.loopAction=PearlProjectCodec.ReadObject<CreatorGroupAction>(v);}}
  catch(Exception e){MiDiagnostics.Report("MI_DIALOGUE_PROFILE_READ","CreatorDialogueProfile.For",e,d.oracleId);Debug.LogWarning("[Creator dialogue] "+e.Message);}
  try{var data=String.IsNullOrWhiteSpace(json)?null:Json.Deserialize(json) as Dictionary<string,object>;object rules;if(data!=null&&data.TryGetValue("pearlReading",out rules))p.pearlReading=PearlProjectCodec.ReadObject<CreatorPearlRules>(rules);}catch(Exception e){MiDiagnostics.Report("MI_PEARL_RULES_READ","CreatorDialogueProfile.For",e,d.oracleId);Debug.LogWarning("[Creator pearl rules] "+e.Message);}
  p.requireMark=true;
  if(String.IsNullOrEmpty(json)){
   if(d.firstDialogue==null||d.repeatDialogue==null)MiDiagnostics.Warn("MI_DIALOGUE_NULL_TEXT","CreatorDialogueProfile.For","Null legacy dialogue was treated as empty.",d.oracleId);
   p.enabled=!IteratorIntegrations.Native(d.oracleId);
   foreach(string text in (d.firstDialogue??"").Split('\n'))if(text.Trim().Length>0)p.first.Add(new CreatorDialogueLine{text=text});
   foreach(string text in (d.repeatDialogue??"").Split('\n'))if(text.Trim().Length>0)p.repeat.Add(new CreatorDialogueLine{text=text});
  }
  if(cache.Count>64)cache.Clear();cache[key]=p;return p;
 }
}

// One resumable main sequence and a higher-priority response sequence.
// The interrupted main line is replayed once; completed lines never restart.
public sealed class CreatorDialogueState {
 sealed class Step {public CreatorDialogueLine line;public Action completed;public CreatorGroupAction[] before;public int beforeIndex;public bool beforeRunning,beforeFailed,presented;}
 readonly LinkedList<Step> main=new LinkedList<Step>();readonly Queue<Step> response=new Queue<Step>();Step current;
 public CreatorDialogueLine Current{get{return current==null?null:current.line;}}public bool CurrentIsResponse,Away,Started;public Action<CreatorDialogueLine> LineCompleted;public Action<CreatorGroupAction,Action<bool>,Action<int>> BeforeAction;int gap;
 public bool CurrentPresented{get{return current!=null&&current.presented;}}
 public bool Pending{get{return current!=null||main.Count>0||response.Count>0||gap>0;}}
 public bool ResponsePending{get{return response.Count>0||(current!=null&&CurrentIsResponse)||gap>0;}}
 public bool MainPending{get{return main.Count>0||(current!=null&&!CurrentIsResponse);}}
 static List<Step> Steps(IEnumerable<CreatorDialogueLine> lines,Action completed){var result=new List<Step>();if(lines!=null)foreach(var line in lines)if(CreatorDialogueLine.Runnable(line))result.Add(new Step{line=line,before=CreatorGroupAction.Flatten(line.beforeAction)});if(result.Count>0)result[result.Count-1].completed=completed;return result;}
 public void Begin(IEnumerable<CreatorDialogueLine> lines,Action completed=null){foreach(var step in Steps(lines,completed))main.AddLast(step);Started=true;}
 public void Finish(){if(current==null)return;gap=Math.Max(0,(int)(current.line.gap*40));var line=current.line;Action completed=current.completed;current.completed=null;current=null;if(LineCompleted!=null)LineCompleted(line);if(completed!=null)completed();}
 public CreatorDialogueLine Next(){if(current!=null)return null;if(gap>0){gap--;return null;}CurrentIsResponse=response.Count>0;if(CurrentIsResponse)current=response.Dequeue();else if(!Away&&main.Count>0){current=main.First.Value;main.RemoveFirst();}if(current!=null)current.beforeFailed=false;return Current;}
 // A Step retains completed before-action children through an interruption. Only
 // its unfinished tail is rescheduled, and text cannot appear until it succeeds.
 public CreatorDialogueLine Prepare(){
  if(current==null||current.presented||current.beforeRunning||current.beforeFailed)return null;
  if(current.beforeIndex<current.before.Length){
   if(BeforeAction==null)return null;
   var step=current;int start=step.beforeIndex;var tail=new CreatorGroupAction[step.before.Length-start];Array.Copy(step.before,start,tail,0,tail.Length);step.beforeRunning=true;
   BeforeAction(tail.Length==1?tail[0]:new CreatorGroupAction{type="sequence",actions=tail},delegate(bool complete){step.beforeRunning=false;if(complete)step.beforeIndex=step.before.Length;else step.beforeFailed=true;},delegate(int count){step.beforeIndex=Math.Max(step.beforeIndex,Math.Min(step.before.Length,start+count));});
   return null;
  }
  current.presented=true;return current.line;
 }
 public void Interrupt(IEnumerable<CreatorDialogueLine> lines,Action completed=null){if(current!=null&&!CurrentIsResponse){current.presented=false;main.AddFirst(current);}current=null;response.Clear();gap=0;foreach(var step in Steps(lines,completed))response.Enqueue(step);}
 public void Depart(IEnumerable<CreatorDialogueLine> lines,Action completed=null){if(!MainPending)return;Away=true;Interrupt(lines,completed);}
 public void Return(IEnumerable<CreatorDialogueLine> lines,Action completed=null){if(!Away)return;Away=false;if(MainPending)Interrupt(lines,completed);}
 public void Clear(){main.Clear();response.Clear();current=null;gap=0;Away=false;Started=false;}
}

public sealed class CreatorDialogue {
 sealed class Session {public CreatorDialogueState state=new CreatorDialogueState();public bool entered,firstComplete;public RainWorldGame game;public Oracle owner;}
 static readonly Dictionary<string,Session> sessions=new Dictionary<string,Session>();
 readonly CreatorSpeech speech;readonly Oracle oracle;Session session;CreatorDialogueState state;readonly HashSet<DataPearl> held=new HashSet<DataPearl>();
 Player listener;int cooldown,lastPickup=-1,lastLeaving=-1,lastReturning=-1;bool present,entryPresent,walkedIn,departed,markAttempted,firstAwaitingMark;string mode="",config="";int restart;
 public bool Speaking{get{return state.Pending&&!state.Away||state.Current!=null;}}
 public string CurrentText{get{return !state.CurrentPresented?"":state.Current.text;}}
 public bool AwaitingReturn{get{return state.Away;}}
 public bool InitialStoryComplete{get{return session.firstComplete;}}
 public static void Reset(string id){sessions.Remove(id);}
 public CreatorDialogue(Oracle o){oracle=o;speech=new CreatorSpeech(o);Attach();restart=CreatorEncounter.Restart;mode=CreatorRuntime.Mode;config=IteratorDesign.ForRoom(o.room).dialogueJson;}
 void Attach(){string id=IteratorDesign.ForRoom(oracle.room).oracleId;if(!sessions.TryGetValue(id,out session)||session.game!=oracle.room.game){session=new Session{game=oracle.room.game,firstComplete=CreatorPearlReader.CompletedStory(oracle,id)};sessions[id]=session;}if(session.owner!=oracle){session.state=new CreatorDialogueState();session.entered=session.firstComplete;session.owner=oracle;}state=session.state;state.BeforeAction=delegate(CreatorGroupAction action,Action<bool> finished,Action<int> steps){CreatorDialogueActions.For(oracle).Schedule(action,listener,finished,steps);};state.LineCompleted=delegate(CreatorDialogueLine line){if(CreatorGroupAction.GrantsMark(line.action)&&!HasMark())markAttempted=true;var action=CreatorDialogueActions.For(oracle).Completed(line.action,listener);if(action!=null)action();};}
 void StopHUD(){speech.Clear();}
 public void Suspend(){state.Interrupt(new CreatorDialogueLine[0]);StopHUD();}
 // Sample departure before speech/action/reception gates. Clearing a dead player's
 // HUD must not count as finishing the interrupted line.
 public void ObservePresence(Player player){
  if(player!=null&&!player.dead&&!player.slatedForDeletetion&&player.room==oracle.room)return;
  present=false;entryPresent=false;walkedIn=false;
  if(state.MainPending){state.Away=true;departed=true;}
  if(state.Current!=null){state.Interrupt(new CreatorDialogueLine[0]);StopHUD();}
 }
 void CompleteFirst(string id){if(session.firstComplete)return;if(!HasMark()&&GrantsMark(CreatorDialogueProfile.For(IteratorDesign.ForRoom(oracle.room)))){firstAwaitingMark=true;return;}firstAwaitingMark=false;session.firstComplete=true;CreatorPearlReader.CompleteStory(oracle,id);}
 void BeginFirst(CreatorDialogueProfile profile,IteratorDesign design,Player player){
  session.entered=true;
  if(profile.first.Exists(CreatorDialogueLine.Runnable))CreatorPearlReader.StartMeeting(oracle,design.oracleId,"first");
  Action action=CreatorDialogueActions.For(oracle).Completed(profile.firstAction,player);
  state.Begin(profile.first,delegate {CompleteFirst(design.oracleId);if(CreatorGroupAction.GrantsMark(profile.firstAction)&&!HasMark())markAttempted=true;if(action!=null)action();});
  // Empty first sequences unlock reading without executing an empty group's action.
  if(!state.MainPending)CompleteFirst(design.oracleId);
 }
 bool MeetingReady(string meeting,CreatorMeetingCondition condition,IteratorDesign design,Player player){
  if(CreatorPearlReader.StartedMeeting(oracle,design.oracleId,meeting)||condition==null)return true;var game=oracle.room.game;int cycle=game.IsStorySession?game.GetStorySession.saveState.cycleNumber:0;
  return CreatorPearlReader.MeetingEntries(oracle,design.oracleId)>=condition.minEntries&&cycle>=condition.minCycle&&CreatorHeldItems.Matches(CreatorHeldItems.Visible(player),condition.held);
 }
 void BeginNext(CreatorDialogueProfile profile,IteratorDesign design,Player player){
  if(!session.firstComplete){if(MeetingReady("first",profile.firstCondition,design,player))BeginFirst(profile,design,player);return;}
  session.entered=true;
  if(profile.storyMode!="firstThenLoop"){
   if(CreatorPearlReader.StartedMeeting(oracle,design.oracleId,"repeat")&&profile.repeat.Exists(CreatorDialogueLine.Runnable)){BeginMeeting("repeat",profile.repeat,profile.repeatAction,design,player);return;}
   foreach(var active in profile.meetings)if(active!=null&&active.lines!=null&&Array.Exists(active.lines,CreatorDialogueLine.Runnable)&&CreatorPearlReader.StartedMeeting(oracle,design.oracleId,active.id)){BeginMeeting(active.id,active.lines,active.action,design,player);return;}
   if(profile.repeat.Exists(CreatorDialogueLine.Runnable)&&!CreatorPearlReader.CompletedMeeting(oracle,design.oracleId,"repeat")){if(MeetingReady("repeat",profile.repeatCondition,design,player))BeginMeeting("repeat",profile.repeat,profile.repeatAction,design,player);return;}
   foreach(var meeting in profile.meetings)if(meeting!=null&&meeting.lines!=null&&Array.Exists(meeting.lines,CreatorDialogueLine.Runnable)&&!CreatorPearlReader.CompletedMeeting(oracle,design.oracleId,meeting.id)){if(MeetingReady(meeting.id,meeting.condition,design,player))BeginMeeting(meeting.id,meeting.lines,meeting.action,design,player);return;}
  }
  if(profile.loop.Exists(CreatorDialogueLine.Runnable))state.Begin(profile.loop,CreatorDialogueActions.For(oracle).Completed(profile.loopAction,player));
 }
 void BeginMeeting(string id,IEnumerable<CreatorDialogueLine> lines,CreatorGroupAction groupAction,IteratorDesign design,Player player){
  CreatorPearlReader.StartMeeting(oracle,design.oracleId,id);
  Action action=CreatorDialogueActions.For(oracle).Completed(groupAction,player);
  state.Begin(lines,delegate {CreatorPearlReader.CompleteMeeting(oracle,design.oracleId,id);if(action!=null)action();});
 }
 static bool GrantsMark(CreatorDialogueProfile profile){
  if(!profile.first.Exists(CreatorDialogueLine.Runnable))return false;
  if(CreatorGroupAction.GrantsMark(profile.firstAction))return true;
  return profile.first.Exists(line=>CreatorGroupAction.GrantsMark(line.beforeAction)||CreatorGroupAction.GrantsMark(line.action));
 }
 void Return(List<CreatorDialogueLine> group,Player player){state.Return(group,CreatorDialogueActions.For(oracle).Completed(group,player));}
 void Depart(List<CreatorDialogueLine> group,Player player){state.Depart(group,CreatorDialogueActions.For(oracle).Completed(group,player));}
 void Interrupt(List<CreatorDialogueLine> group,Player player){CreatorDialogueActions.For(oracle).Cancel();state.Interrupt(group,CreatorDialogueActions.For(oracle).Completed(group,player));}
 List<CreatorDialogueLine> Pick(List<List<CreatorDialogueLine>> pool,ref int last){if(pool.Count==0)return new List<CreatorDialogueLine>();int i=pool.Count==1?0:last<0?UnityEngine.Random.Range(0,pool.Count):(last+1+UnityEngine.Random.Range(0,pool.Count-1))%pool.Count;last=i;return pool[i];}
 bool HasMark(){var game=oracle.room.game;return MoreIteratorsPlugin.Active?CreatorRuntime.Mark:(game.IsStorySession&&game.GetStorySession.saveState.deathPersistentSaveData.theMark);}
 public void ObserveHeld(List<CreatorWorkPearl> pearls){foreach(var pearl in pearls){if(pearl.room==oracle.room&&pearl.grabbedBy.Exists(g=>g.grabber is Player))held.Add(pearl);else held.Remove(pearl);}}
 public void Update(Player player,List<CreatorWorkPearl> pearls,IteratorDesign d){
  speech.Tick();listener=player;var p=CreatorDialogueProfile.For(d);bool enabled=p.enabled&&CreatorRuntime.Mode=="story";
  if(mode!=CreatorRuntime.Mode||restart!=CreatorEncounter.Restart||config!=d.dialogueJson){
   bool hard=restart!=CreatorEncounter.Restart;StopHUD();speech.Finish();if(hard){Reset(d.oracleId);CreatorPearlReader.ResetForReplay(d.oracleId);Attach();entryPresent=false;}else {state.Clear();if(!session.firstComplete)session.entered=false;}present=false;departed=false;walkedIn=false;markAttempted=false;firstAwaitingMark=false;held.Clear();mode=CreatorRuntime.Mode;restart=CreatorEncounter.Restart;config=d.dialogueJson;
  }
  if(!enabled){if(state.Pending){state.Clear();StopHUD();}speech.Finish();return;}
  bool allowed=PlaybackMode.Enabled||!p.requireMark||HasMark()||!session.firstComplete&&GrantsMark(p);if(!allowed){if(state.Pending){state.Clear();StopHUD();}if(!session.firstComplete)session.entered=false;speech.Finish();present=false;return;}
  // A cancelled grant must leave another opportunity to obtain the mark. Its
  // hidden sentence may already be consumed, so replay the unfinished prelude.
  if(markAttempted&&!CreatorDialogueActions.For(oracle).Active){
   markAttempted=false;
   if(!HasMark()){state.Clear();StopHUD();session.entered=false;firstAwaitingMark=false;present=false;departed=false;}
   else if(firstAwaitingMark)CompleteFirst(d.oracleId);
  }
  if(cooldown>0)cooldown--;
  bool inRoom=player!=null&&!player.dead&&!player.slatedForDeletetion&&player.room==oracle.room;ObservePresence(player);
  if(!session.entered&&CreatorPearlReader.CompletedStory(oracle,d.oracleId)){session.entered=true;session.firstComplete=true;}
  if(inRoom&&!present){
   bool arrival=!entryPresent;present=true;entryPresent=true;if(arrival)CreatorPearlReader.EnterMeeting(oracle,d.oracleId);
   if(session.firstComplete&&!state.MainPending){state.Clear();departed=false;if(arrival)BeginNext(p,d,player);}
   else if(state.Away||departed){Return(p.leaveEnabled?Pick(p.returning,ref lastReturning):new List<CreatorDialogueLine>(),player);StopHUD();departed=false;}
   else if(!session.entered)BeginNext(p,d,player);
  }
  // Finish an already displayed line before deciding whether anything is interrupted.
  if(inRoom&&state.CurrentPresented&&!speech.Showing)state.Finish();
  bool nearExit=false;
  if(inRoom){try{Vector2 exit=oracle.room.MiddleOfTile(oracle.room.ShortcutLeadingToNode(CreatorLaunch.ExitNode(oracle.room.abstractRoom.name)).StartTile);float dist=Vector2.Distance(player.mainBodyChunk.pos,exit);if(dist>85)walkedIn=true;nearExit=walkedIn&&(dist<42||player.enteringShortCut.HasValue||player.inShortcut);}catch{nearExit=player.enteringShortCut.HasValue||player.inShortcut;}}
  if(present&&state.MainPending&&(!inRoom||nearExit)&&!departed){departed=true;Depart(p.leaveEnabled?Pick(p.leaving,ref lastLeaving):new List<CreatorDialogueLine>(),player);StopHUD();Debug.Log("[Creator dialogue] leave; resume="+state.MainPending);}
  if(inRoom&&departed&&!nearExit){Return(p.leaveEnabled?Pick(p.returning,ref lastReturning):new List<CreatorDialogueLine>(),player);StopHUD();departed=false;Debug.Log("[Creator dialogue] returned; resume="+state.MainPending);}
  if(!inRoom){present=false;walkedIn=false;if(state.Current!=null){state.Interrupt(new List<CreatorDialogueLine>());StopHUD();}return;}
  foreach(var pearl in pearls){bool grabbed=pearl.room==oracle.room&&pearl.grabbedBy.Exists(g=>g.grabber is Player);if(grabbed&&!held.Contains(pearl)){held.Add(pearl);if(!departed&&p.pickupEnabled&&cooldown==0&&p.pickup.Count>0){Interrupt(Pick(p.pickup,ref lastPickup),player);StopHUD();cooldown=Mathf.Max(1,(int)(p.cooldown*40));Debug.Log("[Creator dialogue] pickup variant="+lastPickup+"; resume="+state.MainPending);}}else if(!grabbed)held.Remove(pearl);}
  var hud=oracle.room.game.cameras[0].hud;if(hud==null)return;if(hud.dialogBox==null)hud.InitDialogBox();
  if(state.CurrentPresented){if(speech.Showing)return;state.Finish();}
  if(CreatorDialogueActions.For(oracle).Active)return;
  if(state.Current==null)state.Next();var line=state.Prepare();if(line!=null){if(CreatorDialogueLine.HasText(line)){speech.Say(line,!HasMark());Debug.Log("[Creator dialogue] "+d.oracleId+" : "+line.text);}else state.Finish();}
  if(session.firstComplete&&!state.Pending)speech.Finish();
 }
}
}
