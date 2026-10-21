using System;
using System.Collections.Generic;
using System.Runtime.CompilerServices;

namespace MoreIterators {
 // Own the whole constructor lifetime, including a room loader constructing an
 // oracle before ReadyForAI. Renaming only around our own `new Oracle` misses it.
 public static class CreatorOracleLifecycle {
  sealed class Ownership {public bool constructing=true,attaching,reportedNative;}
  sealed class EncounterOwner {public Oracle oracle;}
  static readonly ConditionalWeakTable<Oracle,Ownership> owned=new ConditionalWeakTable<Oracle,Ownership>();
  static readonly ConditionalWeakTable<Room,EncounterOwner> encounters=new ConditionalWeakTable<Room,EncounterOwner>();

  public static bool Owns(Oracle oracle){Ownership value;return oracle!=null&&owned.TryGetValue(oracle,out value);}
  static string Context(Oracle oracle){return "room="+(oracle.room==null||oracle.room.abstractRoom==null?"<none>":oracle.room.abstractRoom.name)+" entity="+(oracle.abstractPhysicalObject==null?"<none>":oracle.abstractPhysicalObject.ID.ToString())+" behavior="+(oracle.oracleBehavior==null?"<none>":oracle.oracleBehavior.GetType().FullName);}

  // Behaviour ownership is established before a directly constructed copy can
  // update. Dialogue, pearls and room controls are deliberately deferred until
  // ReadyForAI/Update, after the constructor and room initialization complete.
  public static bool EnsureBehavior(Oracle oracle,bool reportRecovery){
   Ownership state;if(oracle==null||!owned.TryGetValue(oracle,out state))return false;
   if(state.constructing||state.attaching||oracle.room==null||oracle.slatedForDeletetion)return false;
   if(oracle.oracleBehavior is IteratorBehavior)return true;
   string context=Context(oracle);state.attaching=true;
   try {
    var previous=oracle.oracleBehavior as SSOracleBehavior;
    var replacement=new IteratorBehavior(oracle);
    oracle.oracleBehavior=replacement;
    if(previous!=null){previous.killFac=0;previous.lastKillFac=0;if(previous.conversation!=null){previous.conversation.Destroy();previous.conversation=null;}}
    if(reportRecovery)ReportNative(state,"CreatorOracleLifecycle.EnsureBehavior","发现复制迭代器残留原版行为，已在更新前接管。",context);
    else MiDiagnostics.Info("oracle.behavior.attach",context);
    return true;
   } catch(Exception error){MiDiagnostics.Report("MI-ORACLE-ATTACH","CreatorOracleLifecycle.EnsureBehavior",error,context);return false;}
   finally {state.attaching=false;}
  }
  static void ReportNative(Ownership state,string node,string detail,string context){if(state.reportedNative)return;state.reportedNative=true;MiDiagnostics.Behavior("MI-ORACLE-NATIVE-BEHAVIOR",node,detail,context);}
  public static bool SuppressNativeStory(SSOracleBehavior behavior,string node,bool meeting){
   Ownership state;if(behavior==null||behavior.oracle==null||!owned.TryGetValue(behavior.oracle,out state))return false;
   // A silent authored character must not become a native SS encounter. Keep
   // the established action policy for managed controllers and integrations.
   if(behavior is IteratorBehavior)return meeting&&IteratorIntegrations.ForRoom(behavior.oracle.room.abstractRoom.name)==null;
   // Do not replace a controller from inside its own constructor or SeePlayer.
   // The first safe update will repair it; the native story is blocked now.
   if(!state.constructing&&!state.attaching)ReportNative(state,node,"发现复制迭代器残留原版行为，已阻止原版剧情动作。",Context(behavior.oracle)+" action="+behavior.action);
   return true;
  }
  public static bool ClaimEncounter(Oracle oracle){
   if(!Owns(oracle)||oracle.room==null||!oracle.room.readyForAI||!(oracle.oracleBehavior is IteratorBehavior))return false;
   var room=oracle.room;var state=encounters.GetValue(room,delegate(Room key){return new EncounterOwner();});
   if(state.oracle!=null&&!state.oracle.slatedForDeletetion&&state.oracle.room==room)return false;
   foreach(var item in room.updateList)if(item is CreatorEncounter&&!item.slatedForDeletetion)return false;
   state.oracle=oracle;return true;
  }
  public static void ReleaseEncounter(Oracle oracle){EncounterOwner state;if(oracle!=null&&oracle.room!=null&&encounters.TryGetValue(oracle.room,out state)&&state.oracle==oracle)state.oracle=null;}
  public static bool ControlsRoom(Oracle oracle){EncounterOwner state;return !Owns(oracle)||(oracle.room!=null&&encounters.TryGetValue(oracle.room,out state)&&state.oracle==oracle);}
  static bool OwnsRoom(Room room){
   if(room==null||room.abstractRoom==null)return false;
   var project=IteratorCatalog.Find(room.abstractRoom.name);
   return project!=null&&IteratorCatalog.IsAI(room.abstractRoom.name)&&!NativeRoomProjects.IsNative(project);
  }

  public static void Install(List<Action> remove){
   On.Oracle.hook_ctor constructor=Construct;
   On.Oracle.ctor+=constructor;remove.Add(delegate {On.Oracle.ctor-=constructor;});
   On.Oracle.hook_SetUpSwarmers swarmers=SetUpSwarmers;
   On.Oracle.SetUpSwarmers+=swarmers;remove.Add(delegate {On.Oracle.SetUpSwarmers-=swarmers;});
   On.Oracle.hook_GlowerEaten eaten=GlowerEaten;
   On.Oracle.GlowerEaten+=eaten;remove.Add(delegate {On.Oracle.GlowerEaten-=eaten;});
  }

  static void Construct(On.Oracle.orig_ctor orig,Oracle oracle,AbstractPhysicalObject abstractObject,Room room){
   if(!OwnsRoom(room)){orig(oracle,abstractObject,room);return;}
   string original=room.abstractRoom.name;
   bool moon=ModManager.MSC&&IteratorDesign.ForId(IteratorCatalog.Id(original)).nativeOracle=="DM";
   var ownership=new Ownership();owned.Add(oracle,ownership);
   try {
    room.abstractRoom.name=moon?"DM_AI":"SS_AI";
    orig(oracle,abstractObject,room);
   } finally {room.abstractRoom.name=original;ownership.constructing=false;}
   var expected=moon?MoreSlugcats.MoreSlugcatsEnums.OracleID.DM:Oracle.OracleID.SS;
   if(oracle.ID!=expected){
    // Constructor hooks in another mod can replace the native identity. Repair
    // the body controller together with it; suppressing neurons alone leaves SL
    // behaviour and the offset Moon arm attached to a supposedly custom oracle.
    oracle.ID=expected;oracle.SetLocalGravity(0);oracle.health=1f;
    oracle.oracleBehavior=new SSOracleBehavior(oracle);
    oracle.arm=new Oracle.OracleArm(oracle);
    if(oracle.marbles==null)oracle.marbles=new List<PebblesPearl>();
    if(oracle.myScreen==null){oracle.myScreen=new OracleProjectionScreen(room,oracle.oracleBehavior);room.AddObject(oracle.myScreen);}
   }
   EnsureBehavior(oracle,false);
  }

  static void SetUpSwarmers(On.Oracle.orig_SetUpSwarmers orig,Oracle oracle){
   if(!Owns(oracle)){orig(oracle);return;}
   // Only native Moon owns the five life-linked SL neurons. Never create them
   // for an authored puppet, even if another constructor hook changes its ID.
   oracle.glowers=0;oracle.health=1f;
  }

  static void GlowerEaten(On.Oracle.orig_GlowerEaten orig,Oracle oracle){
   // A stray native neuron must not attach Moon's health/spasm story to a copy.
   if(!Owns(oracle))orig(oracle);
  }
 }
}
