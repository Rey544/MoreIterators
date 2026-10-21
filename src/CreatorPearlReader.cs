namespace MoreIterators {
using System;
using System.Collections.Generic;
using System.Runtime.CompilerServices;
using System.Text;
using UnityEngine;

// The current pearl owns its conversation. Other pearl pickups cannot interrupt it.
public sealed class CreatorPearlReader {
 sealed class Memory {public CreatorPearlProgress progress;public int generation,lastEntryTick=Int32.MinValue;}
 static readonly ConditionalWeakTable<RainWorldGame,Dictionary<string,Memory>> memories=new ConditionalWeakTable<RainWorldGame,Dictionary<string,Memory>>();
 static readonly Dictionary<string,int> generations=new Dictionary<string,int>();
 static readonly HashSet<string> pendingResets=new HashSet<string>();
 static readonly HashSet<string> previewStories=new HashSet<string>();
 sealed class PreviewMeetingState {public int entries;public string active="";}
 static readonly Dictionary<string,PreviewMeetingState> previewMeetingStates=new Dictionary<string,PreviewMeetingState>();
 static readonly Dictionary<string,HashSet<string>> previewMeetings=new Dictionary<string,HashSet<string>>();
 static readonly Dictionary<string,int> replayResets=new Dictionary<string,int>();
 public static void Reset(string id){int n;generations.TryGetValue(id,out n);generations[id]=n+1;pendingResets.Add(id);previewStories.Remove(id);previewMeetings.Remove(id);previewMeetingStates.Remove(id);}
 public static void ResetForReplay(string id){int seen;if(replayResets.TryGetValue(id,out seen)&&seen==CreatorEncounter.Restart)return;replayResets[id]=CreatorEncounter.Restart;Reset(id);}
 static string StoryKey(string id){return "MORE_ITERATORS_STORY_"+Convert.ToBase64String(Encoding.UTF8.GetBytes(RuntimePaths.ModId+":"+id))+":COMPLETE";}
 static string Key(string id){return "MORE_ITERATORS_PEARLS_"+Convert.ToBase64String(Encoding.UTF8.GetBytes(id))+":";}
 static CreatorPearlProgress Progress(Oracle oracle,string id){
  var cache=memories.GetOrCreateValue(oracle.room.game);Memory memory;int generation;generations.TryGetValue(id,out generation);
  if(cache.TryGetValue(id,out memory)&&memory.generation==generation)return memory.progress;
  var p=new CreatorPearlProgress();var game=oracle.room.game;bool reset=pendingResets.Remove(id);
  if(game.IsStorySession){var records=game.GetStorySession.saveState.miscWorldSaveData.unrecognizedSaveStrings;string key=Key(id);
   if(reset){records.RemoveAll(s=>s.StartsWith(key,StringComparison.Ordinal));game.GetStorySession.saveState.deathPersistentSaveData.unrecognizedSaveStrings.RemoveAll(s=>s==StoryKey(id)||s.StartsWith(StoryKey(id)+":",StringComparison.Ordinal));}
   else foreach(string record in records)if(record.StartsWith(key,StringComparison.Ordinal)){try{var data=Json.Deserialize(Encoding.UTF8.GetString(Convert.FromBase64String(record.Substring(key.Length)))) as Dictionary<string,object>;if(data==null)throw new FormatException("Pearl progress must be a JSON object.");p=CreatorPearlProgress.Load(data);}catch(Exception error){MiDiagnostics.Report("MI-PEARL-MEMORY","CreatorPearlReader.Progress",error,"oracle="+id+" "+MiDiagnostics.Context(oracle.room));}break;}
  }
  if(MoreIteratorsPlugin.Active){if(previewStories.Contains(id))p.storyComplete=true;}
  else if(game.IsStorySession&&game.GetStorySession.saveState.deathPersistentSaveData.unrecognizedSaveStrings.Contains(StoryKey(id)))p.storyComplete=true;
  HashSet<string> preview;
  if(MoreIteratorsPlugin.Active){PreviewMeetingState state;if(previewMeetingStates.TryGetValue(id,out state)){p.meetingEntries=state.entries;p.activeMeeting=state.active;}if(previewMeetings.TryGetValue(id,out preview))foreach(string meeting in preview)p.completedMeetings.Add(meeting);}
  else if(game.IsStorySession)foreach(string record in game.GetStorySession.saveState.deathPersistentSaveData.unrecognizedSaveStrings)if(record.StartsWith(StoryKey(id)+":",StringComparison.Ordinal)){string value=record.Substring(StoryKey(id).Length+1);int entries;if(value.StartsWith("VISITS=",StringComparison.Ordinal)&&Int32.TryParse(value.Substring(7),out entries))p.meetingEntries=Math.Max(p.meetingEntries,entries);else if(value.StartsWith("ACTIVE=",StringComparison.Ordinal))p.activeMeeting=value.Substring(7);else p.completedMeetings.Add(value);}
  cache[id]=new Memory{progress=p,generation=generation};return p;
 }
 static void Save(Oracle oracle,string id,CreatorPearlProgress p){if(!oracle.room.game.IsStorySession)return;var records=oracle.room.game.GetStorySession.saveState.miscWorldSaveData.unrecognizedSaveStrings;string key=Key(id);records.RemoveAll(s=>s.StartsWith(key,StringComparison.Ordinal));records.Add(key+Convert.ToBase64String(Encoding.UTF8.GetBytes(Json.Serialize(p.Data()))));}
 public static bool CompletedStory(Oracle oracle,string id){return Progress(oracle,id).storyComplete;}
 static void MeetingState(Oracle oracle,string id,CreatorPearlProgress p){
  if(MoreIteratorsPlugin.Active)previewMeetingStates[id]=new PreviewMeetingState{entries=p.meetingEntries,active=p.activeMeeting};
  else if(oracle.room.game.IsStorySession){var records=oracle.room.game.GetStorySession.saveState.deathPersistentSaveData.unrecognizedSaveStrings;string prefix=StoryKey(id)+":ACTIVE=";records.RemoveAll(s=>s.StartsWith(prefix,StringComparison.Ordinal));if(!String.IsNullOrEmpty(p.activeMeeting))records.Add(prefix+p.activeMeeting);}
 }
 public static bool StartedMeeting(Oracle oracle,string id,string meeting){return Progress(oracle,id).activeMeeting==meeting;}
 public static void StartMeeting(Oracle oracle,string id,string meeting){var p=Progress(oracle,id);p.activeMeeting=meeting;MeetingState(oracle,id,p);Save(oracle,id,p);}
 public static int MeetingEntries(Oracle oracle,string id){return Progress(oracle,id).meetingEntries;}
 public static void EnterMeeting(Oracle oracle,string id){
  var progress=Progress(oracle,id);var memory=memories.GetOrCreateValue(oracle.room.game)[id];if(memory.lastEntryTick==oracle.room.game.clock)return;memory.lastEntryTick=oracle.room.game.clock;progress.meetingEntries=Math.Min(9999,progress.meetingEntries+1);
  if(!MoreIteratorsPlugin.Active&&oracle.room.game.IsStorySession){var records=oracle.room.game.GetStorySession.saveState.deathPersistentSaveData.unrecognizedSaveStrings;string prefix=StoryKey(id)+":VISITS=";records.RemoveAll(s=>s.StartsWith(prefix,StringComparison.Ordinal));records.Add(prefix+progress.meetingEntries);}
  MeetingState(oracle,id,progress);Save(oracle,id,progress);
 }
 public static bool CompletedMeeting(Oracle oracle,string id,string meeting){return Progress(oracle,id).completedMeetings.Contains(meeting);}
 public static void CompleteMeeting(Oracle oracle,string id,string meeting){
  var progress=Progress(oracle,id);progress.completedMeetings.Add(meeting);if(progress.activeMeeting==meeting)progress.activeMeeting="";MeetingState(oracle,id,progress);
  if(MoreIteratorsPlugin.Active){HashSet<string> values;if(!previewMeetings.TryGetValue(id,out values)){values=new HashSet<string>();previewMeetings[id]=values;}values.Add(meeting);}
  else if(oracle.room.game.IsStorySession){var records=oracle.room.game.GetStorySession.saveState.deathPersistentSaveData.unrecognizedSaveStrings;string key=StoryKey(id)+":"+meeting;if(!records.Contains(key))records.Add(key);}
  Save(oracle,id,progress);
 }
 // Commit the final first-story line before its lethal/movement completion action.
 // Story completion/entry counters use death persistence; pearl reads keep cycle save rules.
 public static void CompleteStory(Oracle oracle,string id){
  var progress=Progress(oracle,id);progress.storyComplete=true;if(progress.activeMeeting=="first")progress.activeMeeting="";MeetingState(oracle,id,progress);
  if(MoreIteratorsPlugin.Active)previewStories.Add(id);
  else if(oracle.room.game.IsStorySession){var records=oracle.room.game.GetStorySession.saveState.deathPersistentSaveData.unrecognizedSaveStrings;string key=StoryKey(id);if(!records.Contains(key))records.Add(key);}
  Save(oracle,id,progress);
 }
 readonly CreatorSpeech speech;readonly Oracle oracle;readonly CreatorDialogueState state=new CreatorDialogueState();
 CreatorPearlVisits visits=new CreatorPearlVisits();
 readonly HashSet<AbstractPhysicalObject> extractionRequests=new HashSet<AbstractPhysicalObject>();
 string pendingGreetingKind="",responseKey="";
 readonly HashSet<PhysicalObject> observed=new HashSet<PhysicalObject>();readonly Dictionary<string,int> last=new Dictionary<string,int>();
 DataPearl current;PearlProject project;PearlReaderProfile profile;PearlReaderBody selectedProfile;CreatorDialogueLine[] body=new CreatorDialogueLine[0];CreatorGroupAction bodyAction;
 bool departed,walkedIn,greeting,pendingGreeting,readBody,awaitingInitialStory;int cooldown,restart,entryTicks,observationCooldown;string readKey="",displayId="",mode="",config="";Player listener,currentGiver;
 public string CurrentText{get{return !state.CurrentPresented?"":state.Current.text;}}
 public string PearlId{get{return current==null?"":displayId;}}
 public bool Active{get{return current!=null||greeting;}}
 public bool Receiving{get{return Active||pendingGreeting;}}
 public CreatorPearlReader(Oracle o){oracle=o;speech=new CreatorSpeech(o);restart=CreatorEncounter.Restart;mode=CreatorRuntime.Mode;config=IteratorDesign.ForRoom(o.room).dialogueJson;state.BeforeAction=delegate(CreatorGroupAction action,Action<bool> finished,Action<int> steps){CreatorDialogueActions.For(oracle).Schedule(action,listener,finished,steps);};state.LineCompleted=delegate(CreatorDialogueLine line){var action=CreatorDialogueActions.For(oracle).Completed(line.action,listener);if(action!=null)action();};}
 public void Cancel(){
  bool active=Active||state.Pending;
  if(active){
   CreatorDialogueActions.For(oracle).Cancel();
   if(oracle.room!=null&&oracle.room.game!=null&&oracle.room.game.cameras!=null&&oracle.room.game.cameras.Length>0&&oracle.room.game.cameras[0]!=null)ClearHUD();
   Release();
  }
  pendingGreeting=false;visits.DiscardEntry();CreatorPearlOffers.Clear(oracle,"reader cancelled");
 }
 public void ObservePresence(Player player){visits.Observe(player!=null&&!player.dead&&player.room==oracle.room,oracle.room.game.clock);}
 void BeginPresentation(){CreatorReadingPresentation.Begin(oracle,selectedProfile==null?null:selectedProfile.presentation,CreatorDialogueProfile.For(IteratorDesign.ForRoom(oracle.room)).pearlReading.presentation,profile==null?null:profile.presentation);}
 int Cycle{get{return oracle.room.game.IsStorySession?oracle.room.game.GetStorySession.saveState.cycleNumber:0;}}
 PearlVariant Pick(string key,PearlVariant[] pool){
  var choices=new List<PearlVariant>();if(pool!=null)foreach(var v in pool)if(v!=null&&v.lines!=null&&Array.Exists(v.lines,CreatorDialogueLine.Runnable))choices.Add(v);
  if(choices.Count==0)return new PearlVariant();int old;last.TryGetValue(key,out old);int i=choices.Count==1?0:!last.ContainsKey(key)?UnityEngine.Random.Range(0,choices.Count):(old+1+UnityEngine.Random.Range(0,choices.Count-1))%choices.Count;last[key]=i;return choices[i];
 }
 void Begin(PearlVariant group){state.Begin(group.lines,CreatorDialogueActions.For(oracle).Completed(group.action,listener));}
 void Depart(PearlVariant group){state.Depart(group.lines,CreatorDialogueActions.For(oracle).Completed(group.action,listener));}
 void Return(PearlVariant group){state.Return(group.lines,CreatorDialogueActions.For(oracle).Completed(group.action,listener));}
 void ClearHUD(){speech.Clear();}
 void Release(){CreatorReadingPresentation.Clear(oracle);speech.Finish();if(current!=null){var custom=current as CreatorDataPearl;if(custom!=null)custom.hover=null;}current=null;currentGiver=null;project=null;profile=null;selectedProfile=null;body=new CreatorDialogueLine[0];bodyAction=null;state.Clear();departed=false;walkedIn=false;greeting=false;responseKey="";cooldown=45;}
 bool Mark(){return MoreIteratorsPlugin.Active?CreatorRuntime.Mark:oracle.room.game.IsStorySession&&oracle.room.game.GetStorySession.saveState.deathPersistentSaveData.theMark;}
 bool Speak(){var hud=oracle.room.game.cameras[0].hud;if(hud==null)return true;if(state.CurrentPresented){if(speech.Showing)return true;state.Finish();}if(CreatorDialogueActions.For(oracle).Active)return true;if(state.Current==null)state.Next();var line=state.Prepare();if(line!=null){if(CreatorDialogueLine.HasText(line)){speech.Say(line);Debug.Log("[More Iterators pearl] "+line.text);}else state.Finish();}return state.Pending||CreatorDialogueActions.For(oracle).Active;}
 public void Respond(PearlVariant[] pool,string key,Player player){TryRespond(pool,key,player);}
 public bool TryRespond(PearlVariant[] pool,string key,Player player){
  if(pool==null||!Array.Exists(pool,group=>group!=null&&group.lines!=null&&Array.Exists(group.lines,CreatorDialogueLine.Runnable)))return false;
  bool attack=key!=null&&(key.StartsWith("attackRock:",StringComparison.Ordinal)||key.StartsWith("attackSpear:",StringComparison.Ordinal));
  bool replyingToAttack=responseKey.StartsWith("attackRock:",StringComparison.Ordinal)||responseKey.StartsWith("attackSpear:",StringComparison.Ordinal);
  if(attack&&replyingToAttack&&(state.Pending||CreatorDialogueActions.For(oracle).Active))return false;
  CreatorDialogueActions.For(oracle).Cancel();ClearHUD();Release();listener=player;greeting=true;pendingGreeting=false;responseKey=key??"";Begin(Pick(key,pool));return true;
 }
 void Complete(CreatorPearlProgress memory,IteratorDesign design){pendingGreeting=false;if(readBody&&body.Length>0){memory.Complete(readKey,Cycle);Save(oracle,design.oracleId,memory);}Release();}
 public bool Update(Player player,IteratorDesign d,bool canStart,bool initialStoryComplete=true){
  speech.Tick();ObservePresence(player);
  if(restart!=CreatorEncounter.Restart||mode!=CreatorRuntime.Mode||config!=d.dialogueJson){bool replay=restart!=CreatorEncounter.Restart;restart=CreatorEncounter.Restart;mode=CreatorRuntime.Mode;config=d.dialogueJson;if(replay)ResetForReplay(d.oracleId);CreatorPearlOffers.Clear(oracle,"configuration/replay changed");observed.Clear();if(Active)ClearHUD();Release();if(replay){visits=new CreatorPearlVisits();ObservePresence(player);extractionRequests.Clear();}pendingGreeting=false;}
  if(!initialStoryComplete&&CreatorRuntime.Mode=="story")awaitingInitialStory=true;
  bool allowed=CreatorRuntime.Mode=="story"||CreatorRuntime.Mode=="read";
  if(!allowed||!PlaybackMode.Enabled&&!Mark()){CreatorPearlOffers.Clear(oracle,"speech unavailable");if(Active){ClearHUD();Release();}visits.DiscardEntry();pendingGreeting=false;return false;}
  if(CreatorRuntime.Paused){CreatorPearlOffers.Clear(oracle,"paused");return Active;}
  var dialogue=CreatorDialogueProfile.For(d);var rules=dialogue.pearlReading;var memory=Progress(oracle,d.oracleId);
  if(initialStoryComplete&&!memory.storyComplete)CompleteStory(oracle,d.oracleId);
  if(initialStoryComplete&&awaitingInitialStory){
   // First-story completion is not a second encounter. Keep its greeting eligible
   // for the next real arrival, including a retry within this same cycle.
   pendingGreeting=false;visits.DiscardEntry();awaitingInitialStory=false;
  }
  if(current!=null&&(currentGiver==null||currentGiver.dead||currentGiver.slatedForDeletetion)){
   CreatorDialogueActions.For(oracle).Cancel();ClearHUD();Release();pendingGreeting=false;visits.DiscardEntry();return false;
  }
  // A read keeps its actual giver even when the encounter selects another co-op player.
  if(current!=null)player=currentGiver!=null&&!currentGiver.dead&&currentGiver.room==oracle.room?currentGiver:null;
  if(player!=null&&!Active)listener=player;
  bool inRoom=player!=null;var held=CreatorHeldItems.Visible(player);
  string entry=visits.Enter(Cycle,memory.lastGreetingCycle,rules);
  if(entry!=null){
   entryTicks=0;pendingGreeting=!Active&&canStart&&rules.greetingEnabled&&(memory.storyComplete||CreatorRuntime.Mode=="read");pendingGreetingKind=entry;
   observed.Clear();foreach(var item in held)observed.Add(item);
  }
  if(!inRoom){entryTicks=0;pendingGreeting=false;if(greeting){ClearHUD();Release();}}
  else entryTicks++;
  if(cooldown>0)cooldown--;if(observationCooldown>0)observationCooldown--;
  bool offered=CreatorPearlOffers.Pending(oracle);
  if(!rules.greetingEnabled||offered||!canStart)pendingGreeting=false;
  if(!Active&&pendingGreeting&&canStart&&entryTicks>=Mathf.RoundToInt(rules.greetingDelay*40)){
   pendingGreeting=false;greeting=true;state.Clear();
   var pool=pendingGreetingKind=="quickReturn"?rules.quickReturn:pendingGreetingKind=="revisit"?rules.revisit:rules.greeting;
   Begin(Pick(pendingGreetingKind,pool));
   Begin(Pick("greetingItems",CreatorHeldItems.Select(held,rules.greetingMixed,rules.greetingWeapons,rules.greetingPearls,rules.greetingItems,rules.greetingCreatures,rules.greetingCorpses,rules.greetingFood)));
   if(pendingGreetingKind=="greeting"){memory.lastGreetingCycle=Cycle;Save(oracle,d.oracleId,memory);}
   visits.Greeted(pendingGreetingKind,oracle.room.game.clock);ClearHUD();
  }
  // A pickup during speech is remembered, never inserted into an active read.
  var fresh=new List<PhysicalObject>();foreach(var item in held)if(!observed.Contains(item))fresh.Add(item);
  if(!Active&&!offered&&!pendingGreeting&&canStart&&inRoom&&dialogue.observation.enabled&&observationCooldown==0&&fresh.Count>0&&Vector2.Distance(player.mainBodyChunk.pos,oracle.firstChunk.pos)<220&&oracle.room.VisualContact(player.mainBodyChunk.pos,oracle.firstChunk.pos)){
   string category=CreatorHeldItems.Category(held);int lastCycle;bool repeated=memory.lastObserved.TryGetValue(category,out lastCycle)&&lastCycle==Cycle;
   var pool=dialogue.observation.For(category,repeated);
   if(!CreatorHeldItems.HasLines(pool))pool=CreatorHeldItems.Select(held,dialogue.observation.For("mixed",repeated),dialogue.observation.For("weapons",repeated),dialogue.observation.For("pearls",repeated),dialogue.observation.For("items",repeated));
   var group=Pick("observation:"+category+(repeated?":repeat":":first"),pool);
   if(group.lines.Length>0){greeting=true;state.Clear();Action finish=CreatorDialogueActions.For(oracle).Completed(group.action,listener);state.Begin(group.lines,delegate {memory.lastObserved[category]=Cycle;Save(oracle,d.oracleId,memory);if(finish!=null)finish();});ClearHUD();observationCooldown=Mathf.Max(1,Mathf.RoundToInt(dialogue.observation.cooldown*40));}
  }
  foreach(var item in held)if(Active||canStart&&inRoom&&Vector2.Distance(player.mainBodyChunk.pos,oracle.firstChunk.pos)<220)observed.Add(item);
  if(greeting){if(!Speak()){Release();return false;}return true;}
  if(!Active&&!pendingGreeting&&canStart&&inRoom&&cooldown==0){
   DataPearl candidate;Player giver;bool extracted=false;CreatorPearlOffers.Take(oracle,out candidate,out giver);
   if(candidate==null&&rules.extractStomachPearl&&(initialStoryComplete||CreatorRuntime.Mode=="read")){
    var stomach=CreatorStomachPearl.Candidate(player,oracle,d);
    if(stomach!=null&&extractionRequests.Add(stomach)){
     // Consume this exact request before any native call, including failure or refusal.
     if(CreatorAffinity.Refuses(oracle,d)){Respond(dialogue.affinity.refusal,"refusal",player);return greeting;}
     candidate=CreatorStomachPearl.Extract(player,oracle,stomach);giver=player;extracted=candidate!=null;
    }
   }
   if(candidate!=null){
    listener=giver;
    // Refuse before taking, hovering, or marking any read as complete.
    if(CreatorAffinity.Refuses(oracle,d)){Respond(dialogue.affinity.refusal,"refusal",giver);return greeting;}
    current=candidate;currentGiver=giver;player=giver;var custom=candidate as CreatorDataPearl;project=custom==null?null:custom.Project;profile=project==null?null:project.Reader(d.projectId);readKey=project==null?"native-misc:"+candidate.abstractPhysicalObject.ID.ToString():project.uid;displayId=project==null?"Misc":project.id;
    if(profile!=null){selectedProfile=profile.Select(dialogue.affinity.enabled?CreatorAffinity.Get(oracle,d).Tier:null);body=selectedProfile.read;bodyAction=selectedProfile.readAction;}else{var selected=Pick("misc",rules.misc);body=selected.lines.Length>0?selected.lines:CreatorMiscPearls.Load(oracle,candidate);bodyAction=selected.action;}
    if(body==null||!Array.Exists(body,CreatorDialogueLine.Runnable)){Debug.Log("[More Iterators pearl] Configured empty read body: "+displayId+"; no read progress recorded.");Release();return false;}
    state.Clear();readBody=memory.ReadBody(readKey,Cycle,rules.preventSameCycleRepeat);
    if(memory.Seen(readKey)){bool own=selectedProfile!=null&&selectedProfile.repeatEnabled;var selected=Pick(own?"repeat:"+readKey:"repeat",own?selectedProfile.repeat:rules.repeat);if(own&&selected.lines.Length>0&&selectedProfile.repeatPrependCommon)Begin(Pick("repeat",rules.repeat));Begin(selected);}
    if(readBody){CreatorAffinity.Gift(oracle,d,readKey);if(memory.Many(readKey,Cycle,rules))Begin(Pick("many",rules.many));bool firstRead=memory.Count(Cycle)==0&&CreatorHeldItems.HasLines(rules.firstPreRead);Begin(Pick(extracted?"extractedPreRead":firstRead?"firstPreRead":"preRead",extracted?rules.extractedPreRead:firstRead?rules.firstPreRead:rules.preRead));state.Begin(body,CreatorDialogueActions.For(oracle).Completed(bodyAction,listener));}
    BeginPresentation();ClearHUD();Debug.Log("[More Iterators pearl] Reading "+displayId+" by "+d.projectId+" body="+readBody);
   }
  }
  if(!Active)return false;
  if(current.slatedForDeletetion){ClearHUD();Release();return false;}
  if(state.CurrentPresented&&!speech.Showing)state.Finish();
  if(CreatorDialogueActions.For(oracle).Active)return true;
  if(!state.MainPending&&!state.Away&&!state.ResponsePending){Complete(memory,d);return false;}
  bool nearExit=false;
  if(inRoom){try{Vector2 exit=oracle.room.MiddleOfTile(oracle.room.ShortcutLeadingToNode(CreatorLaunch.ExitNode(oracle.room.abstractRoom.name)).StartTile);float dist=Vector2.Distance(player.mainBodyChunk.pos,exit);if(dist>85)walkedIn=true;nearExit=walkedIn&&(dist<40||player.enteringShortCut.HasValue||player.inShortcut);}catch(Exception error){MiDiagnostics.Report("MI-PEARL-EXIT","CreatorPearlReader.Update",error,MiDiagnostics.Context(oracle.room));nearExit=player.enteringShortCut.HasValue||player.inShortcut;}}
  bool away=!inRoom||nearExit||current.room!=oracle.room;
  if(away&&!departed&&state.MainPending){CreatorReadingPresentation.Clear(oracle);departed=true;Depart(Pick("leaving",rules.leaving));ClearHUD();
   if(rules.leavePolicy=="restart"){speech.Finish();state.Clear();if(readBody)state.Begin(body,CreatorDialogueActions.For(oracle).Completed(bodyAction,listener));Depart(Pick("leaving",rules.leaving));}
  }
  if(!away&&departed){BeginPresentation();departed=false;Return(Pick("returning",rules.returning));ClearHUD();}
  if(rules.leavePolicy=="cancel"&&away&&!inRoom){Release();return false;}
  if(current.room==oracle.room){Vector2 hover=oracle.firstChunk.pos+new Vector2(-22,24);var custom=current as CreatorDataPearl;if(custom!=null)custom.hover=hover;else if(current.grabbedBy.Count==0)current.firstChunk.vel=Vector2.Lerp(current.firstChunk.vel,Vector2.ClampMagnitude(hover-current.firstChunk.pos,18),.12f);oracle.oracleBehavior.lookPoint=current.firstChunk.pos;}
  if(!inRoom)return true;
  Speak();
  if(!state.Pending&&!departed&&!CreatorDialogueActions.For(oracle).Active){Complete(memory,d);return false;}
  if(rules.leavePolicy=="cancel"&&departed&&!state.ResponsePending){Release();return false;}
  return true;
 }
}
}
