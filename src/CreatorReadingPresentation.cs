namespace MoreIterators {
using System;
using System.Runtime.CompilerServices;
using UnityEngine;

[Serializable] public sealed class CreatorReadingPresentationOptions {
 public string movement="inherit",eyes="inherit";
}

// Presentation owns only the requested destination and eye state of an MI oracle.
// Its body physics, native update, dialogue, projections and actions continue normally.
public static class CreatorReadingPresentation {
 sealed class State {
  public CreatorReadingPresentationOptions body,defaults,line,fallbackBody;
  public object source;public bool reading,outputValid,controlling,suspended;
  public Vector2 anchor,output;public int tick,restart;public string mode,config;public Room room;public IteratorBehavior owner;
 }
 static readonly ConditionalWeakTable<Oracle,State> states=new ConditionalWeakTable<Oracle,State>();
 static bool Owned(Oracle oracle){return oracle!=null&&oracle.oracleBehavior is IteratorBehavior;}
 static string Movement(string value){return value=="still"||value=="small"||value=="large"?value:"inherit";}
 static string Eyes(string value){return value=="natural"||value=="open"||value=="closed"?value:"inherit";}
 static CreatorReadingPresentationOptions Copy(CreatorReadingPresentationOptions value){return value==null?new CreatorReadingPresentationOptions():new CreatorReadingPresentationOptions{movement=Movement(value.movement),eyes=Eyes(value.eyes)};}
 static string Select(string line,string body,string defaults){return line!="inherit"?line:body!="inherit"?body:defaults;}
 static string Move(CreatorReadingPresentationOptions value){return value==null?"inherit":Movement(value.movement);}
 static string Eye(CreatorReadingPresentationOptions value){return value==null?"inherit":Eyes(value.eyes);}
 static string EffectiveMovement(State s){return Select(Move(s.line),Move(s.reading?s.body:null),Select("inherit",Move(s.reading?s.fallbackBody:null),Move(s.reading?s.defaults:null)));}
 static string EffectiveEyes(State s){return Select(Eye(s.line),Eye(s.reading?s.body:null),Select("inherit",Eye(s.reading?s.fallbackBody:null),Eye(s.reading?s.defaults:null)));}
 public static CreatorReadingPresentationOptions Resolve(CreatorReadingPresentationOptions line,CreatorReadingPresentationOptions body,CreatorReadingPresentationOptions defaults,CreatorReadingPresentationOptions fallbackBody=null){var state=new State{line=line,body=body,defaults=defaults,fallbackBody=fallbackBody,reading=true};return new CreatorReadingPresentationOptions{movement=EffectiveMovement(state),eyes=EffectiveEyes(state)};}
 static void Capture(Oracle oracle,State state){state.restart=CreatorEncounter.Restart;state.mode=CreatorRuntime.Mode;state.config=IteratorDesign.ForRoom(oracle.room).dialogueJson;state.room=oracle.room;state.owner=(IteratorBehavior)oracle.oracleBehavior;}
 public static void Begin(Oracle oracle,CreatorReadingPresentationOptions body,CreatorReadingPresentationOptions defaults,CreatorReadingPresentationOptions fallbackBody=null){
  if(!Owned(oracle)||oracle.room==null)return;
  var state=states.GetValue(oracle,o=>new State());state.body=Copy(body);state.defaults=Copy(defaults);state.fallbackBody=Copy(fallbackBody);state.reading=true;state.line=null;state.source=null;state.controlling=false;Capture(oracle,state);
 }
 public static void SetLine(Oracle oracle,object source,CreatorReadingPresentationOptions line){
  if(!Owned(oracle)||oracle.room==null)return;
  var state=states.GetValue(oracle,o=>new State());if(state.mode!=null&&!Valid(oracle,state))Reset(state);state.line=Copy(line);state.source=source;Capture(oracle,state);
 }
 public static void ClearLine(Oracle oracle,object source){State state;if(oracle!=null&&states.TryGetValue(oracle,out state)&&System.Object.ReferenceEquals(source,state.source)){state.line=null;state.source=null;}}
 public static void Clear(Oracle oracle){State state;if(oracle!=null&&states.TryGetValue(oracle,out state))Reset(state);}
 static void Reset(State state){state.reading=false;state.body=state.defaults=state.fallbackBody=state.line=null;state.source=null;state.controlling=false;}
 static bool Suspended(Oracle oracle){var owner=oracle.oracleBehavior as IteratorBehavior;return CreatorDialogueActions.For(oracle).Active||(owner!=null&&owner.PersonalSpace!=null&&owner.PersonalSpace.Avoiding);}
 static bool Valid(Oracle oracle,State state){return Owned(oracle)&&System.Object.ReferenceEquals(oracle.oracleBehavior,state.owner)&&oracle.room!=null&&oracle.room==state.room&&!oracle.slatedForDeletetion&&oracle.Consious&&!StudioRuntime.Recording&&state.restart==CreatorEncounter.Restart&&state.mode==CreatorRuntime.Mode&&state.config==IteratorDesign.ForRoom(oracle.room).dialogueJson;}
 public static bool EyesClosed(Oracle oracle,bool native){
  State state;if(oracle==null||!states.TryGetValue(oracle,out state)||!Valid(oracle,state)||Suspended(oracle))return native;
  string eyes=EffectiveEyes(state);return eyes=="closed"?true:eyes=="open"?false:native;
 }
 public static bool ControlsMovement(Oracle oracle){State state;return oracle!=null&&states.TryGetValue(oracle,out state)&&state.controlling&&!state.suspended;}
 public static Vector2 Target(Oracle oracle,Vector2 native){State state;return Owned(oracle)&&oracle.room!=null&&!oracle.slatedForDeletetion&&states.TryGetValue(oracle,out state)&&state.outputValid?state.output:native;}
 public static void Tick(Oracle oracle,Vector2 native){
  State state;if(oracle==null||!states.TryGetValue(oracle,out state))return;
  if(!Valid(oracle,state))Reset(state);
  if(oracle.room==null||!Owned(oracle)||oracle.slatedForDeletetion){states.Remove(oracle);return;}
  if(CreatorRuntime.Paused)return;
  bool suspended=Suspended(oracle);string movement=EffectiveMovement(state);
  bool controlled=!suspended&&movement!="inherit";
  if(controlled&&(!state.controlling||state.suspended)){state.anchor=oracle.firstChunk.pos;state.tick=0;}
  state.controlling=controlled;state.suspended=suspended;
  Vector2 desired=native;
  if(controlled){
   state.tick++;float radius=movement=="small"?30:movement=="large"?110:0;
   // Start at the anchor and gradually grow the orbit, so changing options never teleports.
   float ramp=Math.Min(1,state.tick/80f);
   desired=state.anchor+new Vector2((float)Math.Sin(state.tick*.013f)*radius*ramp,(float)Math.Sin(state.tick*.009f)*radius*.55f*ramp);
   desired=new Vector2(Mathf.Clamp(desired.x,30,Math.Max(30,oracle.room.PixelWidth-30)),Mathf.Clamp(desired.y,30,Math.Max(30,oracle.room.PixelHeight-30)));
   if(oracle.room.GetTile(desired).Solid)desired=state.outputValid?state.output:state.anchor;
  }
  if(!state.outputValid){if(!controlled)return;state.output=native;state.outputValid=true;}
  state.output+=Vector2.ClampMagnitude(desired-state.output,3f);
  if(!controlled&&Vector2.Distance(state.output,native)<.01f)state.outputValid=false;
 }
}
}
