using System;
using System.IO;
using System.Collections.Generic;
using System.Runtime.CompilerServices;
using UnityEngine;

namespace MoreIterators {
 public static class ProjectionCatalog {
  sealed class Cached {public long stamp,length;public ProjectionGroup group;}
  static readonly Dictionary<string,Cached> files=new Dictionary<string,Cached>();
  static List<ProjectionGroup> groups=new List<ProjectionGroup>();static float next;
  public static List<ProjectionGroup> All(){
   if(ModManager.ActiveMods==null)return groups;
   if(Time.realtimeSinceStartup<next)return groups;next=Time.realtimeSinceStartup+1;
   var found=new Dictionary<string,ProjectionGroup>();
   foreach(var mod in ModManager.ActiveMods){
    if(PlaybackMode.Enabled&&mod.id!=RuntimePaths.ModId)continue;
#if !PLAYBACK
    if(RuntimePaths.HasIndependentRuntime(mod.path))continue;
#endif
    Read(Path.Combine(mod.path,"moreiterators/projections"),mod.id,found);
   }
   if(!PlaybackMode.Enabled)Read(Path.Combine(RuntimePaths.DataDirectory,"projections"),"",found);
   groups=new List<ProjectionGroup>(found.Values);return groups;
  }
  static void Read(string directory,string owner,Dictionary<string,ProjectionGroup> result){
   if(!Directory.Exists(directory))return;
   try{foreach(string file in Directory.GetFiles(directory,"*.json")){
    try{
     var info=new FileInfo(file);Cached old;ProjectionGroup group;
     if(files.TryGetValue(file,out old)&&old.stamp==info.LastWriteTimeUtc.Ticks&&old.length==info.Length)group=old.group;
     else{
      if(info.Length>32000000)throw new InvalidDataException("Projection document exceeds 32 MB.");
      group=PearlProjectCodec.ReadObject<ProjectionGroup>(Json.Deserialize(File.ReadAllText(file)));
      Validate(group);files[file]=new Cached{stamp=info.LastWriteTimeUtc.Ticks,length=info.Length,group=group};
      MiDiagnostics.Info("projection.load",group.uid+" revision="+group.revision);
     }
     if(owner!="")group.ownerMod=owner;
     var record=IteratorCatalog.Projects().Find(p=>IteratorCatalog.Text(p,"projectId")==group.projectId);
     if(record==null||IteratorCatalog.Text(record,"oracleId")!=group.oracleId||(!String.IsNullOrEmpty(group.ownerMod)&&IteratorCatalog.Text(record,"ownerMod")!=group.ownerMod))continue;
     result[group.uid]=group;
    }catch(FileNotFoundException){}
    catch(Exception error){MiDiagnostics.Report("MI-PROJECTION-DATA","ProjectionCatalog.Read",error,file);}
   }}catch(Exception error){MiDiagnostics.Report("MI-PROJECTION-DIRECTORY","ProjectionCatalog.Read",error,directory);}
  }
  public static void Validate(ProjectionGroup g){
   if(g==null||g.schema!="moreiterators.projection.v1"||String.IsNullOrEmpty(g.uid)||g.uid.Length!=32||String.IsNullOrEmpty(g.projectId)||g.trigger==null||g.images==null||g.tracks==null||g.tracks.Length>32||g.images.Length>16)throw new InvalidDataException("Invalid projection identity or document.");
   if(g.trigger.kind!="work"&&g.trigger.kind!="dialogue"&&g.trigger.kind!="pearl")throw new InvalidDataException("Projection trigger is not implemented: "+g.trigger.kind);
   if(!Finite(g.trigger.beforeSeconds)||g.trigger.beforeSeconds<0||g.trigger.beforeSeconds>120||!Finite(g.trigger.afterSeconds)||g.trigger.afterSeconds<0||g.trigger.afterSeconds>120)throw new InvalidDataException("Invalid projection speech timing.");
   ValidateMask(g.projectMask);
   if(g.trigger.lineIds==null)g.trigger.lineIds=new string[0];
   if(g.trigger.kind!="work"&&(g.trigger.lineIds.Length==0||Array.IndexOf(g.trigger.lineIds,g.trigger.startLineId)<0||Array.IndexOf(g.trigger.lineIds,g.trigger.endLineId)<0))throw new InvalidDataException("Projection sentence anchors have not been resolved.");
   foreach(var image in g.images)if(image==null||String.IsNullOrEmpty(image.id)||image.width<1||image.height<1||image.width>1024||image.height>1024||image.png==null||!image.png.StartsWith("data:image/png;base64,",StringComparison.Ordinal))throw new InvalidDataException("Invalid projection PNG.");
   foreach(var track in g.tracks){
    if(track==null||track.frames==null||track.frames.Length<1||track.frames.Length>128||!Finite(track.delay)||track.delay<0||track.delay>600)throw new InvalidDataException("Invalid projection track.");
    if(Array.IndexOf(new[]{"image","circle","line","glyph","grid","cursor","scanline","matrix"},track.kind)<0)throw new InvalidDataException("Unknown projection element.");
    if(Array.IndexOf(new[]{"native","plain"},track.style)<0)throw new InvalidDataException("Unknown projection style.");
    if(track.maskMode!="inherit"&&track.maskMode!="none"&&track.maskMode!="custom")throw new InvalidDataException("Invalid projection mask mode.");
    ValidateMask(track.mask);
    if(track.kind=="image"&&Array.Find(g.images,i=>i.id==track.imageId)==null)throw new InvalidDataException("Projection image reference is missing.");
    foreach(var f in track.frames)if(f==null||!Finite(f.duration)||f.duration<0||f.duration>600||!Unit(f.x)||!Unit(f.y)||!Finite(f.scale)||f.scale<=0||f.scale>20||!Finite(f.rotation)||!Unit(f.opacity)||!Finite(f.brightness)||f.brightness<0||f.brightness>4||!Unit(f.flicker)||(f.ease!="linear"&&f.ease!="smooth"&&f.ease!="step"))throw new InvalidDataException("Invalid projection keyframe.");
   }
  }
  static void ValidateMask(ProjectionMask mask){
   if(mask==null||!Unit(mask.x)||!Unit(mask.y)||!Unit(mask.width)||!Unit(mask.height)||mask.width<.001f||mask.height<.001f||mask.x+mask.width>1.000001f||mask.y+mask.height>1.000001f)throw new InvalidDataException("Invalid projection rectangle mask.");
  }
  static bool Finite(float n){return !Single.IsNaN(n)&&!Single.IsInfinity(n);}
  static bool Unit(float n){return Finite(n)&&n>=0&&n<=1;}
  public static void Clear(){files.Clear();groups.Clear();next=0;}
 }

 // Signals originate in MI's own speech/encounter code. No IL or global HUD hook
 // is needed, and unrelated oracles never enter this controller.
 public sealed class CreatorProjections:UpdatableAndDeletable,INotifyWhenRoomUnloaded {
  static readonly ConditionalWeakTable<Oracle,CreatorProjections> instances=new ConditionalWeakTable<Oracle,CreatorProjections>();
  static readonly List<CreatorProjections> live=new List<CreatorProjections>();
  readonly Oracle oracle;readonly Dictionary<string,Run> runs=new Dictionary<string,Run>();
  object speaker;string line="";bool interrupted,working;int ticks,restart;
  sealed class Run {public ProjectionGroup group;public float elapsed,leadRemaining,tailRemaining;public object owner;public bool active,finished,scope,trailing;public readonly List<ProjectionSprite> sprites=new List<ProjectionSprite>();}
  CreatorProjections(Oracle o){oracle=o;room=o.room;restart=CreatorEncounter.Restart;live.Add(this);}
  public static CreatorProjections For(Oracle oracle){
   if(oracle==null||oracle.room==null||oracle.room.abstractRoom==null||!IteratorCatalog.IsAI(oracle.room.abstractRoom.name))return null;
   CreatorProjections value;if(!instances.TryGetValue(oracle,out value)||value.slatedForDeletetion){instances.Remove(oracle);value=new CreatorProjections(oracle);instances.Add(oracle,value);oracle.room.AddObject(value);}
   value.CheckRestart();return value;
  }
  public static void SetWorking(Oracle oracle,bool value){var c=For(oracle);if(c!=null)c.working=value;}
  // Called only after the sentence's existing gap and before-action finish.
  // Pending speech counts as Showing, so the dialogue scheduler cannot advance.
  public static float Prepare(Oracle oracle,object source,string id){
   var c=For(oracle);if(c==null)return 0;c.Refresh();float before=0;
   foreach(var run in c.runs.Values)if(run.group.trigger.kind!="work"&&run.group.trigger.startLineId==id){
    if(!run.scope)before=Math.Max(before,run.group.trigger.beforeSeconds);
    else if(run.owner==source)before=Math.Max(before,run.leadRemaining);
   }
   c.speaker=source;c.line=id??"";c.interrupted=false;
   if(before<=0)return 0;
   foreach(var run in c.runs.Values)if(run.group.trigger.kind!="work"&&run.group.trigger.startLineId==id&&!run.scope){
    run.scope=true;run.owner=source;c.Start(run);run.leadRemaining=before;
    // All groups share the same speech start, while each retains its own lead.
    run.elapsed=run.group.trigger.beforeSeconds-before;
    foreach(var sprite in run.sprites)sprite.visible=run.elapsed>=0;
   }
   return before;
  }
  public static void Line(Oracle oracle,object source,string id){var c=For(oracle);if(c==null)return;c.speaker=source;c.line=id??"";c.interrupted=false;c.Refresh();
   foreach(var run in c.runs.Values){if(run.group.trigger.kind=="work")continue;if(run.group.trigger.startLineId==id){
    if(!run.scope){run.scope=true;run.owner=source;c.Start(run);}if(run.owner==source)run.leadRemaining=0;
   }}
  }
  public static void Pause(Oracle oracle,object source){CreatorProjections c;if(oracle==null||!instances.TryGetValue(oracle,out c))return;
   if(c.speaker==source)c.interrupted=true;
   foreach(var run in c.runs.Values)if(run.owner==source&&run.trailing){c.Stop(run);run.trailing=false;run.scope=false;}
  }
  public static void EndLine(Oracle oracle,object source,string id){CreatorProjections c;if(oracle==null||!instances.TryGetValue(oracle,out c))return;
   foreach(var run in c.runs.Values)if(run.owner==source&&run.group.trigger.endLineId==id&&!run.trailing){
    run.scope=false;run.leadRemaining=0;
    if(run.active&&run.group.trigger.afterSeconds>0){run.trailing=true;run.tailRemaining=run.group.trigger.afterSeconds;}
    else c.Stop(run);
   }
  }
  public static void Finish(Oracle oracle,object source,bool preserveTail=false){CreatorProjections c;if(oracle==null||!instances.TryGetValue(oracle,out c))return;
   if(c.speaker==source){c.line="";c.interrupted=false;}
   foreach(var run in c.runs.Values)if(run.group.trigger.kind!="work"&&run.owner==source){
    if(preserveTail&&run.trailing)continue;c.Stop(run);run.scope=false;run.trailing=false;run.leadRemaining=0;
   }
  }
  // Future entity/item recognizers can dispatch their own explicit source here;
  // reserved trigger types are rejected until a recognizer provides real context.
  void Refresh(){
   string project=IteratorDesign.ForRoom(room).projectId;var keep=new HashSet<string>();
   foreach(var group in ProjectionCatalog.All())if(group.enabled&&group.projectId==project){
    keep.Add(group.uid);Run run;
    if(runs.TryGetValue(group.uid,out run)&&System.Object.ReferenceEquals(run.group,group))continue;
    if(run!=null)Dispose(run);runs[group.uid]=new Run{group=group};
   }
   var remove=new List<string>();foreach(var pair in runs)if(!keep.Contains(pair.Key)){Dispose(pair.Value);remove.Add(pair.Key);}foreach(string uid in remove)runs.Remove(uid);
  }
  void Start(Run run){
   Dispose(run);run.elapsed=0;run.leadRemaining=0;run.tailRemaining=0;run.trailing=false;run.finished=false;
   try{foreach(var track in run.group.tracks){var sprite=new ProjectionSprite(this,run.group,track);run.sprites.Add(sprite);room.AddObject(sprite);}run.active=true;MiDiagnostics.Info("projection.start",run.group.uid+" "+MiDiagnostics.Context(room));}
   catch(Exception error){Dispose(run);run.finished=true;MiDiagnostics.Report("MI-PROJECTION-START","CreatorProjections.Start",error,run.group.uid);}
  }
  void Stop(Run run){if(!run.active)return;Dispose(run);run.finished=true;MiDiagnostics.Info("projection.stop",run.group.uid);}
  static void Dispose(Run run){foreach(var sprite in run.sprites)sprite.Destroy();run.sprites.Clear();run.active=false;}
  void CheckRestart(){
   if(restart==CreatorEncounter.Restart)return;restart=CreatorEncounter.Restart;
   speaker=null;line="";interrupted=false;
   foreach(var run in runs.Values){Dispose(run);run.elapsed=0;run.leadRemaining=0;run.tailRemaining=0;run.trailing=false;run.owner=null;run.finished=false;run.scope=false;}
  }
  public override void Update(bool eu){
   base.Update(eu);if(oracle.slatedForDeletetion||oracle.room!=room||room==null||room.game==null){Destroy();return;}
   CheckRestart();
   if(CreatorRuntime.Paused)return;
   if(ticks++%40==0)Refresh();
   // The shared encounter supplies exact work state; native integrations expose
   // reception through IteratorBehavior when they retain their own dialogue.
   var behavior=oracle.oracleBehavior as IteratorBehavior;
   if(IteratorIntegrations.Native(IteratorDesign.ForRoom(room).oracleId)&&behavior!=null)working=!behavior.encounterActive;
   foreach(var run in runs.Values){bool work=run.group.trigger.kind=="work";
    if(work){if(working){if(!run.active&&!run.finished)Start(run);}else{Stop(run);run.finished=false;}}
    bool present=false;foreach(var player in room.game.Players)if(player.realizedCreature!=null&&player.realizedCreature.room==room){present=true;break;}
    if(!work&&run.trailing&&!present){Stop(run);run.trailing=false;run.scope=false;}
    bool paused=!work&&(!present||!run.trailing&&(interrupted||run.owner!=speaker||!ProjectionTimeline.Contains(run.group,line)));
    foreach(var sprite in run.sprites){sprite.visible=!paused&&run.elapsed>=0;sprite.time=Math.Max(0,run.elapsed);}
    if(!run.active||paused)continue;
    if(run.trailing){run.tailRemaining-=1f/40f;if(run.tailRemaining<=.00001f){Stop(run);run.trailing=false;continue;}}
    run.leadRemaining=Math.Max(0,run.leadRemaining-1f/40f);
    run.elapsed+=1f/40f;float duration=ProjectionTimeline.Duration(run.group);
    if(run.elapsed>duration){if(run.group.loop)run.elapsed%=duration;
     else if(!work&&(run.scope||run.trailing)&&(run.group.trigger.beforeSeconds>0||run.group.trigger.afterSeconds>0))run.elapsed=duration;
     else Stop(run);
    }
   }
  }
  public override void Destroy(){foreach(var r in runs.Values)Dispose(r);runs.Clear();instances.Remove(oracle);live.Remove(this);base.Destroy();}
  public void RoomUnloaded(){Destroy();}
  public static void Shutdown(){foreach(var value in live.ToArray())value.Destroy();ProjectionCatalog.Clear();}
 }
}
