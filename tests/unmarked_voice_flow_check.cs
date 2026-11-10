using System;
using System.Collections.Generic;
using System.IO;
using MoreIterators;

namespace UnityEngine {
 public class Object {public static void Destroy(Object value){}}
 public class GameObject {public T AddComponent<T>() where T:new(){return new T();}}
 public class AudioSource:Object {public GameObject gameObject=new GameObject();public AudioClip clip=new AudioClip();public float time;}
 public class AudioClip {public float length=5;}
 public class AudioEchoFilter:Object {public bool enabled;public float delay,decayRatio,wetMix,dryMix;}
 public class AudioLowPassFilter:Object {public bool enabled;public float cutoffFrequency,lowpassResonanceQ;}
 public class AudioDistortionFilter:Object {public bool enabled;public float distortionLevel;}
}
public class VirtualMicrophone {public class SoundObject {public UnityEngine.AudioSource audioSource=new UnityEngine.AudioSource();}}
public class ChunkSoundEmitter {public bool alive,requireActiveUpkeep,slatedForDeletetion;public float volume,pitch,initialVolume;public VirtualMicrophone.SoundObject currentSoundObject;public void Destroy(){slatedForDeletetion=true;}}
public class UpdatableAndDeletable {public Room room;public bool slatedForDeletetion;public virtual void Update(bool eu){}public virtual void Destroy(){slatedForDeletetion=true;}}
public interface INotifyWhenRoomUnloaded {void RoomUnloaded();}
public partial class SoundID {
 public static readonly SoundID SS_AI_Talk_1=new SoundID(),SS_AI_Talk_2=new SoundID(),SS_AI_Talk_3=new SoundID(),SS_AI_Talk_4=new SoundID(),SS_AI_Talk_5=new SoundID();
 public static readonly SoundID SL_AI_Talk_1=new SoundID(),SL_AI_Talk_2=new SoundID(),SL_AI_Talk_3=new SoundID(),SL_AI_Talk_4=new SoundID(),SL_AI_Talk_5=new SoundID();
}
namespace On {public static class Room {
 public delegate ChunkSoundEmitter orig_PlaySound_SoundID_BodyChunk_bool_float_float_bool(global::Room room,SoundID sound,BodyChunk chunk,bool loop,float volume,float pitch,bool randomStart);
 public delegate ChunkSoundEmitter hook_PlaySound_SoundID_BodyChunk_bool_float_float_bool(orig_PlaySound_SoundID_BodyChunk_bool_float_float_bool orig,global::Room room,SoundID sound,BodyChunk chunk,bool loop,float volume,float pitch,bool randomStart);
 public static event hook_PlaySound_SoundID_BodyChunk_bool_float_float_bool PlaySound_SoundID_BodyChunk_bool_float_float_bool;
 public static ChunkSoundEmitter Invoke(orig_PlaySound_SoundID_BodyChunk_bool_float_float_bool orig,global::Room room,SoundID sound,BodyChunk chunk,bool loop,float volume,float pitch,bool randomStart){return PlaySound_SoundID_BodyChunk_bool_float_float_bool==null?orig(room,sound,chunk,loop,volume,pitch,randomStart):PlaySound_SoundID_BodyChunk_bool_float_float_bool(orig,room,sound,chunk,loop,volume,pitch,randomStart);}
}}
public partial class Room {
 public readonly List<ChunkSoundEmitter> emitted=new List<ChunkSoundEmitter>();public int audibleFrames;
 public ChunkSoundEmitter PlaySound(SoundID sound,BodyChunk chunk,bool loop,float volume,float pitch){return On.Room.Invoke(Original,this,sound,chunk,loop,volume,pitch,false);}
 static ChunkSoundEmitter Original(Room room,SoundID sound,BodyChunk chunk,bool loop,float volume,float pitch,bool randomStart){var e=new ChunkSoundEmitter{volume=volume,initialVolume=volume,pitch=pitch};room.emitted.Add(e);return e;}
 public void AudioFrame(){
  foreach(var obj in updateList.ToArray()){var update=obj as UpdatableAndDeletable;if(update!=null&&!update.slatedForDeletetion)update.Update(false);}
  foreach(var e in emitted)if(!e.slatedForDeletetion){if(e.currentSoundObject==null)e.currentSoundObject=new VirtualMicrophone.SoundObject();if(e.volume>0)audibleFrames++;}
 }
}
namespace MoreIterators {

 public static class CreatorOracleLifecycle {public static bool Owns(Oracle o){return o.oracleBehavior is IteratorBehavior;}}
}
static class UnmarkedVoiceFlowCheck {
 static int count;static string dataRoot;static Oracle currentOracle;
 static void SetVoice(bool value){if(CreatorVoiceControl.Enabled!=value)CreatorVoiceControl.Toggle(currentOracle.room.game);}
 static void RequestVoicePreview(){SetVoice(false);SetVoice(true);}
 static void Check(bool value,string message){count++;if(!value)throw new Exception(message);}
 static void Mark(Oracle o,bool value){CreatorRuntime.Mark=value;o.room.game.GetStorySession.saveState.deathPersistentSaveData.theMark=value;}
 static Oracle Scene(bool legacy,bool preview){
  CreatorVoice.Enable();
  RuntimePaths.DataDirectory=Path.Combine(dataRoot,Guid.NewGuid().ToString("N"));Directory.CreateDirectory(RuntimePaths.DataDirectory);File.WriteAllText(Path.Combine(RuntimePaths.DataDirectory,"voice-control.json"),"{\"enabled\":true,\"futureField\":7}");
  CreatorRuntime.Mode="story";CreatorRuntime.Paused=false;MoreIteratorsPlugin.Active=preview;CreatorProjections.starts=0;
  var o=new Oracle{room=new Room{game=new RainWorldGame()}};o.room.game.cameras[0].room=o.room;Mark(o,false);
  var d=new IteratorDesign{oracleId=Guid.NewGuid().ToString(),voice=new CreatorVoiceDesign{enabled=true}};o.room.design=d;
  if(legacy)d.firstDialogue="authored words from an older project";
  else d.dialogueJson="{\"testNonce\":\""+d.oracleId+"\",\"enabled\":true,\"requireMark\":true,\"first\":[{\"text\":\"authored words from a new project\",\"lineId\":\"first\",\"hold\":0.1,\"gap\":0.1}]}";
  o.room.updateList.Add(o);currentOracle=o;return o;
 }
 static Player Listener(Oracle o){var p=new Player{room=o.room};p.firstChunk.pos=new UnityEngine.Vector2(300,300);o.room.game.Players.Add(new AbstractCreature{realizedCreature=p});return p;}
 static void Frame(Oracle o,Player p,CreatorDialogue d,bool finishText=false){o.room.game.clock++;if(finishText)o.room.game.cameras[0].hud.dialogBox.ShowingAMessage=false;CreatorDialogueActions.For(o).Update();d.ObservePresence(p);d.Update(p,new List<CreatorWorkPearl>(),o.room.design);o.room.AudioFrame();}
 static void Drain(Oracle o,Player p,CreatorDialogue d,int ticks){for(int i=0;i<ticks;i++)Frame(o,p,d);}
 static void UntranslatedDoesNotCommit(bool legacy,bool preview){
  var o=Scene(legacy,preview);var p=Listener(o);var profile=CreatorDialogueProfile.For(o.room.design);
  profile.first[0].beforeAction=new CreatorGroupAction{type="killPlayer"};profile.first[0].action=new CreatorGroupAction{type="killPlayer"};profile.firstAction=new CreatorGroupAction{type="killPlayer"};
  var d=new CreatorDialogue(o);Drain(o,p,d,3);
  Check(o.room.emitted.Count>0&&o.room.audibleFrames>0,"unmarked requireMark story actually reaches audible native voice in old/new core/playback projects");
  Check(o.room.emitted[0].initialVolume==0&&!o.room.emitted[0].slatedForDeletetion,"native guard preserves the authored zero-volume fade-in emitter");
  Drain(o,p,d,300);int emitted=o.room.emitted.Count;Drain(o,p,d,160);
  Check(o.room.emitted.Count==emitted,"untranslated material plays once per arrival rather than looping forever");
  Check(!p.dead&&!CreatorDialogueActions.For(o).Active,"voice-only text never runs sentence or group actions");
  Check(o.room.game.cameras[0].hud.dialogBox.said.Count==0&&CreatorProjections.starts==0,"unmarked voice exposes no translated text or projection");
  Check(!d.InitialStoryComplete&&!CreatorPearlReader.StartedMeeting(o,o.room.design.oracleId,"first")&&!CreatorPearlReader.CompletedStory(o,o.room.design.oracleId),"unmarked voice consumes no story or meeting progress");
  Check(o.room.game.GetStorySession.saveState.deathPersistentSaveData.unrecognizedSaveStrings.Count==0,"unmarked voice writes no campaign progress tokens");
  p.room=new Room();Frame(o,p,d);p.room=o.room;Drain(o,p,d,3);Check(o.room.emitted.Count>emitted,"returning visitor can hear untranslated material again");
  d.Suspend();
 }
 static void ControlsAndTranslation(){
  var o=Scene(false,false);var p=Listener(o);var d=new CreatorDialogue(o);SetVoice(false);Drain(o,p,d,5);Check(o.room.emitted.Count==0,"F8 off prevents an unmarked start");
  SetVoice(true);Drain(o,p,d,3);var e=o.oracleBehavior.voice;Check(e!=null&&!e.slatedForDeletetion&&e.volume>0,"F8 on starts existing material during the same visit");
  SetVoice(false);o.room.AudioFrame();Check(e.slatedForDeletetion&&o.oracleBehavior.voice==null,"native guard stops this utterance immediately on F8 mute");
  Drain(o,p,d,3);SetVoice(true);Drain(o,p,d,3);e=o.oracleBehavior.voice;Check(e!=null&&!e.slatedForDeletetion,"unmarked voice can restart after explicit re-enable");
  Mark(o,true);o.room.AudioFrame();Check(e.slatedForDeletetion&&o.oracleBehavior.voice==null,"mark acquisition stops live voice before dialogue next ticks");
  int emitted=o.room.emitted.Count;Frame(o,p,d);Check(o.room.game.cameras[0].hud.dialogBox.said.Count==1&&CreatorProjections.starts==1,"mark enables original first text and projection after untranslated preview");
  Frame(o,p,d,true);Check(d.InitialStoryComplete&&CreatorPearlReader.CompletedStory(o,o.room.design.oracleId),"marked line completes original story normally");Check(o.room.emitted.Count==emitted,"marked translated story starts no voice");
  o=Scene(false,false);p=Listener(o);o.room.design.voice.enabled=false;d=new CreatorDialogue(o);Drain(o,p,d,4);Check(o.room.emitted.Count==0&&!d.InitialStoryComplete,"author voice remains opt-in without consuming unmarked story");
  o.room.design.voice=new CreatorVoiceDesign{enabled=true};Drain(o,p,d,3);Check(o.room.audibleFrames>0,"enabling voice after runtime design refresh works without new arrival");
  e=o.oracleBehavior.voice;CreatorRuntime.Paused=true;o.room.AudioFrame();Check(e.slatedForDeletetion,"global pause stops the emitted syllable");CreatorRuntime.Paused=false;Drain(o,p,d,3);Check(o.oracleBehavior.voice!=null,"unmarked voice resumes after a pause");
  e=o.oracleBehavior.voice;p.room=new Room();Frame(o,p,d);Check(e.slatedForDeletetion&&!d.Speaking,"leaving cancels the unmarked voice and its pending gap");
  o=Scene(true,false);p=Listener(o);CreatorPearlReader.CompleteStory(o,o.room.design.oracleId);int saved=o.room.game.GetStorySession.saveState.deathPersistentSaveData.unrecognizedSaveStrings.Count;d=new CreatorDialogue(o);Drain(o,p,d,3);
  Check(d.InitialStoryComplete&&o.room.audibleFrames>0,"older completed projects can reuse their first text as untranslated sound material");
  Check(o.room.game.GetStorySession.saveState.deathPersistentSaveData.unrecognizedSaveStrings.Count==saved,"untranslated fallback does not alter an existing completed save");
 }
 static void MarkedPreviewAndTransitions(){
  if(PlaybackMode.Enabled){
   var exported=Scene(false,true);Mark(exported,true);var listener=Listener(exported);var dialogue=new CreatorDialogue(exported);Drain(exported,listener,dialogue,3);
   Check(!CreatorVoicePreview.WithoutMark(exported)&&exported.room.emitted.Count==0&&exported.room.game.cameras[0].hud.dialogBox.said.Count==1,"Standalone exports never override a marked save for rehearsal");dialogue.Suspend();return;
  }
  foreach(bool legacy in new[]{false,true})foreach(bool saved in new[]{false,true}){
   var o=Scene(legacy,true);var p=Listener(o);Mark(o,saved);var profile=CreatorDialogueProfile.For(o.room.design);profile.first[0].beforeAction=new CreatorGroupAction{type="giveMark"};profile.first[0].action=new CreatorGroupAction{type="killPlayer"};profile.firstAction=new CreatorGroupAction{type="giveMark"};
   RequestVoicePreview();var d=new CreatorDialogue(o);Drain(o,p,d,3);Check(o.room.audibleFrames>0,"Explicitly requested marked and unmarked new/legacy editor projects can audition immediately through the native guard");
   Check(o.room.game.GetStorySession.saveState.deathPersistentSaveData.theMark==saved&&CreatorRuntime.Mark==saved&&!p.dead,"Voice-only rehearsal runs no mark grants or destructive authored actions");
   Check(!d.InitialStoryComplete&&o.room.game.GetStorySession.saveState.deathPersistentSaveData.unrecognizedSaveStrings.Count==0,"Voice audition writes no story or pearl progress");
   var e=o.oracleBehavior.voice;SetVoice(false);o.room.AudioFrame();Check(e.slatedForDeletetion&&IteratorBehavior.HasCommunicationMark(o)==saved,"F8 off restores the original mark without a reload");
   Frame(o,p,d);SetVoice(true);Drain(o,p,d,3);Check(o.room.audibleFrames>0&&!CreatorDialogueActions.For(o).Active,"Re-enabling audition cancels any action queued by normal story mode");
   e=o.oracleBehavior.voice;CreatorRuntime.Mode="silent";Frame(o,p,d);Check(!d.Speaking&&(e==null||e.slatedForDeletetion),"Switching to silent stops the audition and clears its next line");
   CreatorRuntime.Mode="story";Drain(o,p,d,3);e=o.oracleBehavior.voice;MoreIteratorsPlugin.Active=false;o.room.AudioFrame();if(saved)Check(e==null||e.slatedForDeletetion,"Leaving the preview immediately restores marked-save muting");
   d.Suspend();
  }
   
   
  var queued=Scene(false,true);var player=Listener(queued);SetVoice(false);var actions=CreatorDialogueActions.For(queued);actions.Schedule(new CreatorGroupAction{type="giveMark",delay=.1f},player,null);Check(actions.Active,"Normal story can queue a mark grant while audition is off");
  SetVoice(true);actions.Update();Check(!actions.Active&&!queued.room.game.GetStorySession.saveState.deathPersistentSaveData.theMark&&!CreatorRuntime.Mark,"Enabling audition cancels the pending grant before it can touch either save or preview mark");
 }
 static void ResumeMeetingAfterAudition(){
  if(PlaybackMode.Enabled)return;
  foreach(bool laterMeeting in new[]{false,true}){
   var o=Scene(false,true);Mark(o,true);SetVoice(false);var p=Listener(o);var profile=CreatorDialogueProfile.For(o.room.design);string id=o.room.design.oracleId,meeting=laterMeeting?"later-meeting":"repeat";
   var lines=new[]{new CreatorDialogueLine{text="already completed",gap=0},new CreatorDialogueLine{text="interrupted line",gap=0},new CreatorDialogueLine{text="remaining line",gap=0}};
   if(laterMeeting)profile.meetings=new[]{new CreatorMeeting{id=meeting,lines=lines}};else profile.repeat=new List<CreatorDialogueLine>(lines);
   CreatorPearlReader.CompleteStory(o,id);var d=new CreatorDialogue(o);Frame(o,p,d);Frame(o,p,d,true);var said=o.room.game.cameras[0].hud.dialogBox.said;
   Check(said.Count==2&&said[1]=="interrupted line"&&CreatorPearlReader.StartedMeeting(o,id,meeting),"repeat/later meeting is interrupted after a completed line");
   int entries=CreatorPearlReader.MeetingEntries(o,id);string saved=String.Join("|",o.room.game.GetStorySession.saveState.miscWorldSaveData.unrecognizedSaveStrings.ToArray());
   for(int audition=0;audition<2;audition++){
    int before=said.Count;SetVoice(true);Drain(o,p,d,3);
    Check(said.Count==before&&CreatorPearlReader.MeetingEntries(o,id)==entries&&CreatorPearlReader.StartedMeeting(o,id,meeting)&&!CreatorPearlReader.CompletedMeeting(o,id,meeting),"audition does not consume an active later meeting or count another visit");
    Check(String.Join("|",o.room.game.GetStorySession.saveState.miscWorldSaveData.unrecognizedSaveStrings.ToArray())==saved,"audition keeps existing progress bytes unchanged");
    SetVoice(false);Frame(o,p,d);
    Check(said.Count==before+1&&said[said.Count-1]=="interrupted line"&&CreatorPearlReader.MeetingEntries(o,id)==entries,"leaving audition resumes the interrupted line without replaying completed lines or adding a visit");
   }
   Frame(o,p,d,true);Check(said[said.Count-1]=="remaining line"&&!CreatorPearlReader.CompletedMeeting(o,id,meeting),"resumed meeting preserves the remaining line before completion");Frame(o,p,d,true);
   Check(CreatorPearlReader.CompletedMeeting(o,id,meeting)&&CreatorPearlReader.MeetingEntries(o,id)==entries,"only finishing the restored final line completes the meeting");d.Suspend();
  }
   
   
  var staged=Scene(false,true);Mark(staged,true);SetVoice(false);var visitor=Listener(staged);var rules=CreatorDialogueProfile.For(staged.room.design);
  rules.repeat=new List<CreatorDialogueLine>{new CreatorDialogueLine{text="after unfinished action",gap=0,beforeAction=new CreatorGroupAction{type="sequence",actions=new[]{new CreatorGroupAction{type="giveMark"},new CreatorGroupAction{type="liftSpinPlayer",duration=.25f}}}}};
  CreatorPearlReader.CompleteStory(staged,staged.room.design.oracleId);var story=new CreatorDialogue(staged);Frame(staged,visitor,story);Frame(staged,visitor,story);
  Check(staged.room.sparks==20&&CreatorDialogueActions.For(staged).Active,"first action child completed before the second child is interrupted");
  int visitCount=CreatorPearlReader.MeetingEntries(staged,staged.room.design.oracleId);SetVoice(true);Drain(staged,visitor,story,3);
  Check(staged.room.sparks==20&&!CreatorDialogueActions.For(staged).Active&&staged.room.game.cameras[0].hud.dialogBox.said.Count==0,"audition cancels only unfinished action work without showing its line");
  SetVoice(false);Drain(staged,visitor,story,20);
  Check(staged.room.sparks==20&&staged.room.game.cameras[0].hud.dialogBox.said.Count==1&&staged.room.game.cameras[0].hud.dialogBox.said[0]=="after unfinished action","restored line retries its unfinished action tail without repeating the completed mark grant");
  Check(CreatorPearlReader.MeetingEntries(staged,staged.room.design.oracleId)==visitCount&&!CreatorPearlReader.CompletedMeeting(staged,staged.room.design.oracleId,"repeat"),"action resumption does not add a visit or finish the still-visible line");story.Suspend();
 }
 static DataPearl OfferPearl(Oracle o,Player p,DataPearl pearl=null){
  if(pearl==null)pearl=new DataPearl{room=o.room};pearl.firstChunk.pos=p.firstChunk.pos;
  var grasp=new Grasp{grabber=p,grabbed=pearl};p.grasps=new[]{grasp};pearl.grabbedBy.Add(grasp);
  On.Player.Invoke(delegate(Player player,int index,bool eu){pearl.grabbedBy.Clear();player.grasps[index]=null;pearl.firstChunk.vel=(o.firstChunk.pos-player.firstChunk.pos).normalized*10;},p,0,false);return pearl;
 }
 static void ModeMatrix(){
  foreach(bool legacy in new[]{false,true})foreach(bool preview in new[]{false,true})foreach(string mode in new[]{"silent","story","read"})foreach(bool marked in new[]{false,true})foreach(bool voice in new[]{false,true}){
   var o=Scene(legacy,preview);var p=Listener(o);Mark(o,marked);CreatorRuntime.Mode=mode;
   string file=Path.Combine(RuntimePaths.DataDirectory,"voice-control.json"),saved="{\"enabled\":"+(voice?"true":"false")+",\"futureField\":7}";File.WriteAllText(file,saved);
   Check(CreatorVoiceControl.Enabled==voice&&!CreatorVoicePreview.WithoutMark(o),"stored voice preference never requests audition "+mode);
   var d=new CreatorDialogue(o);Drain(o,p,d,3);var hud=o.room.game.cameras[0].hud.dialogBox;
   string label=(legacy?"legacy":"authored")+" "+(preview?"preview":"campaign")+" "+mode+" mark="+marked+" voice="+voice;
   Check((hud.said.Count>0)==(mode=="story"&&marked),"translated story dispatch "+label);
   Check((o.room.audibleFrames>0)==(mode=="story"&&!marked&&voice),"untranslated story dispatch "+label);
   Check(CreatorRuntime.Mark==marked&&o.room.game.GetStorySession.saveState.deathPersistentSaveData.theMark==marked,"stored preference preserves real mark "+label);
   Check(File.ReadAllText(file)==saved,"dispatch does not rewrite existing preferences "+label);
   if(mode=="read"){
    var profile=CreatorDialogueProfile.For(o.room.design);profile.pearlReading.greetingEnabled=false;
    profile.pearlReading.misc=new[]{new PearlVariant{lines=new[]{new CreatorDialogueLine{text="matrix pearl body",hold=.1f,gap=0}}}};
    var reader=new CreatorPearlReader(o);reader.Update(p,o.room.design,true);OfferPearl(o,p);
    for(int frame=0;frame<160;frame++){o.room.game.clock++;hud.ShowingAMessage=false;reader.Update(p,o.room.design,true);o.room.AudioFrame();}
    Check(hud.said.Contains("matrix pearl body")==marked,"pearl-reading dispatch with an offered pearl "+label);reader.Cancel();
   }
   d.Suspend();
  }
 }
 static void RequestedReadAndNewGame(){
  var o=Scene(false,true);var p=Listener(o);Mark(o,true);RequestVoicePreview();
  Check(CreatorVoicePreview.WithoutMark(o)==!PlaybackMode.Enabled,"explicit request core versus standalone");
  CreatorRuntime.Mode="read";Check(!CreatorVoicePreview.WithoutMark(o)&&IteratorBehavior.HasCommunicationMark(o),"read mode retains marked state even after an explicit request");
  var profile=CreatorDialogueProfile.For(o.room.design);profile.pearlReading.greetingEnabled=false;profile.pearlReading.misc=new[]{new PearlVariant{lines=new[]{new CreatorDialogueLine{text="read after audition",hold=.1f,gap=0}}}};
  var reader=new CreatorPearlReader(o);reader.Update(p,o.room.design,true);OfferPearl(o,p);
  for(int frame=0;frame<160;frame++){o.room.game.clock++;o.room.game.cameras[0].hud.dialogBox.ShowingAMessage=false;reader.Update(p,o.room.design,true);o.room.AudioFrame();}
  Check(o.room.game.cameras[0].hud.dialogBox.said.Contains("read after audition")&&o.room.audibleFrames==0,"read mode is not suppressed or voiced by a story audition request");reader.Cancel();
  CreatorRuntime.Mode="story";
  var newGame=new Oracle{room=new Room{game=new RainWorldGame(),design=o.room.design}};newGame.room.game.cameras[0].room=newGame.room;Mark(newGame,true);CreatorDialogue.Reset(newGame.room.design.oracleId);CreatorPearlReader.Reset(newGame.room.game,newGame.room.design.oracleId);p=Listener(newGame);var dialogue=new CreatorDialogue(newGame);Drain(newGame,p,dialogue,3);
  Check(!CreatorVoicePreview.WithoutMark(newGame)&&newGame.room.game.cameras[0].hud.dialogBox.said.Count==1&&newGame.room.audibleFrames==0,"new replay game does not inherit explicit request while keeping enabled preference");dialogue.Suspend();
 }
 static void CachedMarkSpeech(){
  var o=Scene(false,false);CreatorRuntime.Mark=false;o.room.game.GetStorySession.saveState.deathPersistentSaveData.theMark=true;
  Check(IteratorBehavior.HasCommunicationMark(o),"campaign mark resolver reads the actual save instead of stale preview cache");
  var speech=new CreatorSpeech(o);speech.Say(new CreatorDialogueLine{text="marked save with stale cache",hold=.1f});
  Check(o.room.game.cameras[0].hud.dialogBox.said.Contains("marked save with stale cache")&&o.room.emitted.Count==0,"actual marked campaign displays speech when cached preview mark is false");speech.Clear();
 }
 static void CachedMarkReading(){
  var o=Scene(false,false);var p=Listener(o);CreatorRuntime.Mode="read";CreatorRuntime.Mark=true;o.room.game.GetStorySession.saveState.deathPersistentSaveData.theMark=false;
  Check(!IteratorBehavior.HasCommunicationMark(o),"unmarked campaign ignores stale true preview cache");
  var profile=CreatorDialogueProfile.For(o.room.design);profile.pearlReading.greetingEnabled=false;profile.pearlReading.misc=new[]{new PearlVariant{lines=new[]{new CreatorDialogueLine{text="pearl after actual mark",hold=.1f,gap=0}}}};
  var reader=new CreatorPearlReader(o);reader.Update(p,o.room.design,true,false);var pearl=OfferPearl(o,p);var saved=o.room.game.GetStorySession.saveState.miscWorldSaveData.unrecognizedSaveStrings;var hud=o.room.game.cameras[0].hud.dialogBox;
  for(int frame=0;frame<160;frame++){o.room.game.clock++;hud.ShowingAMessage=false;reader.Update(p,o.room.design,true,false);o.room.AudioFrame();}
  Check(hud.said.Count==0&&!reader.Active&&saved.Count==0,"unmarked reading neither displays nor consumes offered pearl despite cached true mark");
  o.room.game.GetStorySession.saveState.deathPersistentSaveData.theMark=true;CreatorRuntime.Mark=false;OfferPearl(o,p,pearl);
  for(int frame=0;frame<160;frame++){o.room.game.clock++;hud.ShowingAMessage=false;reader.Update(p,o.room.design,true,false);o.room.AudioFrame();}
  Check(hud.said.Contains("pearl after actual mark")&&saved.Count>0,"granting the actual mark permits the same pearl with stale false cache");reader.Cancel();
 }
 static int Main(string[] args){try{dataRoot=Path.GetFullPath(args[0]);Directory.CreateDirectory(dataRoot);var remove=new List<Action>();CreatorNativeVoiceGuard.Install(remove);CreatorPearlOffers.Install(remove);foreach(bool legacy in new[]{false,true})foreach(bool preview in new[]{false,true})UntranslatedDoesNotCommit(legacy,preview);ControlsAndTranslation();MarkedPreviewAndTransitions();ResumeMeetingAfterAudition();ModeMatrix();RequestedReadAndNewGame();if(Environment.GetEnvironmentVariable("MI_VOICE_MARK_CASE")!="read")CachedMarkSpeech();if(Environment.GetEnvironmentVariable("MI_VOICE_MARK_CASE")!="speech")CachedMarkReading();foreach(var f in remove)f();Console.WriteLine(count+" unmarked voice flow assertions passed");return 0;}catch(Exception error){Console.Error.WriteLine(error);return 1;}}
}


