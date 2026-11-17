using System;
using System.Collections.Generic;
using MoreIterators;
using UnityEngine;
namespace UnityEngine {
 public struct Vector2 {public float x,y;public Vector2(float x,float y){this.x=x;this.y=y;}public static Vector2 zero {get{return new Vector2();}}public static Vector2 up {get{return new Vector2(0,1);}}public float sqrMagnitude {get{return x*x+y*y;}}public Vector2 normalized {get{float length=(float)Math.Sqrt(sqrMagnitude);return length>.0001f?this*(1/length):zero;}}public static Vector2 operator +(Vector2 a,Vector2 b){return new Vector2(a.x+b.x,a.y+b.y);}public static Vector2 operator -(Vector2 a,Vector2 b){return new Vector2(a.x-b.x,a.y-b.y);}public static Vector2 operator *(Vector2 a,float b){return new Vector2(a.x*b,a.y*b);}public static Vector2 Lerp(Vector2 a,Vector2 b,float t){return a+(b-a)*t;}}
 public static class Mathf {public static float Clamp(float v,float a,float b){return Math.Max(a,Math.Min(b,v));}public static float Sin(float v){return (float)Math.Sin(v);}public static float Cos(float v){return (float)Math.Cos(v);}}
}
public class AbstractRoom {public string name="MI_AI";}
public class Room {
 public class Tile {public enum TerrainType {Air,Solid,Slope,Floor,ShortcutEntrance}public TerrainType Terrain;public bool Solid {get{return Terrain==TerrainType.Solid;}}}
 public AbstractRoom abstractRoom=new AbstractRoom();public List<object> updateList=new List<object>();public bool readyForAI=true;public IteratorDesign design=new IteratorDesign();public float PixelWidth {get{return 960;}}public float PixelHeight {get{return 720;}}
 public Tile GetTile(Vector2 point){return new Tile{Terrain=point.x<80||point.x>=880||point.y<80||point.y>=640?Tile.TerrainType.Solid:Tile.TerrainType.Air};}
 public void AddObject(object value){updateList.Add(value);}
}
public class BodyChunk {public Vector2 pos=new Vector2(350,350),lastPos,vel;public int hardSets;public void HardSetPosition(Vector2 point){pos=lastPos=point;hardSets++;}}
public class AbstractPhysicalObject {public int ID;}
public class OracleBehavior {public int consistentBasePosCounter;public Oracle oracle;}
public class Conversation {public void Destroy(){}}
public class SSOracleBehavior:OracleBehavior {public float killFac,lastKillFac;public Conversation conversation;public object action;public SSOracleBehavior(Oracle oracle){this.oracle=oracle;}}
public class Oracle {
 public enum OracleID {SS,SL,DM}
 public class OracleArm {public Oracle oracle;public class Joint {public float totalLength=150;public Vector2 pos,lastPos,vel;}public Vector2[] cornerPositions={new Vector2(210,630),new Vector2(770,630),new Vector2(770,70),new Vector2(210,70)};public Joint[] joints={new Joint(),new Joint(),new Joint(),new Joint()};public float framePos,lastFramePos;public bool baseMoving;public OracleArm(Oracle oracle){this.oracle=oracle;}public Vector2 BasePos(float time){return (cornerPositions[2]+cornerPositions[3])*.5f;}}
 public Room room;public OracleID ID=OracleID.SS;public bool slatedForDeletetion;public int glowers;public float health=1;public AbstractPhysicalObject abstractPhysicalObject=new AbstractPhysicalObject();public OracleArm arm;public OracleBehavior oracleBehavior;public List<PebblesPearl> marbles;public OracleProjectionScreen myScreen;public BodyChunk[] bodyChunks={new BodyChunk(),new BodyChunk{pos=new Vector2(350,341)}};public BodyChunk firstChunk {get{return bodyChunks[0];}}
 public Oracle(Room room){this.room=room;arm=new OracleArm(this);oracleBehavior=new SSOracleBehavior(this);On.Oracle.Construct(this,abstractPhysicalObject,room);}
 public void SetLocalGravity(float value){}
}
public class PebblesPearl {}
public class OracleProjectionScreen {public OracleProjectionScreen(Room room,OracleBehavior behavior){}}
public class GenericBodyPart {public Vector2 pos,lastPos,vel;}
public class OracleGraphics {public Oracle oracle;public GenericBodyPart[] feet={new GenericBodyPart(),new GenericBodyPart()};public Vector2[,] knees=new Vector2[2,2];}
public static class ModManager {public static bool MSC;}
namespace MoreSlugcats {public static class MoreSlugcatsEnums {public static class OracleID {public static Oracle.OracleID DM=Oracle.OracleID.DM;}}}
namespace On {public static class Oracle {
 public delegate void orig_ctor(global::Oracle oracle,AbstractPhysicalObject abstractObject,Room room);public delegate void hook_ctor(orig_ctor orig,global::Oracle oracle,AbstractPhysicalObject abstractObject,Room room);public static event hook_ctor ctor;
 public delegate void orig_SetUpSwarmers(global::Oracle oracle);public delegate void hook_SetUpSwarmers(orig_SetUpSwarmers orig,global::Oracle oracle);public static event hook_SetUpSwarmers SetUpSwarmers;
 public delegate void orig_GlowerEaten(global::Oracle oracle);public delegate void hook_GlowerEaten(orig_GlowerEaten orig,global::Oracle oracle);public static event hook_GlowerEaten GlowerEaten;
 public static void Construct(global::Oracle oracle,AbstractPhysicalObject abstractObject,Room room){if(ctor!=null)ctor(delegate {},oracle,abstractObject,room);}
}}
namespace MoreIterators {
 public class IteratorDesign {public string chamberPreset="mi-chamber-broken",nativeOracle="SS";public float puppetScale=1,torsoLength=1,neckLength=1;public static IteratorDesign ForRoom(Room room){return room.design;}public static IteratorDesign ForId(string id){return new IteratorDesign();}}
 public class IteratorBehavior:SSOracleBehavior {public IteratorBehavior(Oracle oracle):base(oracle){}}
 public class CreatorEncounter {public bool slatedForDeletetion;public bool OwnerPresent {get{return true;}}public bool Owns(Oracle oracle){return false;}}
 public static class IteratorCatalog {public static object Find(string name){return new object();}public static bool IsAI(string name){return true;}public static string Id(string name){return name;}}
 public static class NativeRoomProjects {public static bool IsNative(object value){return false;}}
 public static class IteratorIntegrations {public static object ForRoom(string name){return null;}}
 public static class UiText {public static string Get(string value){return value;}}
 public static class MiDiagnostics {public static void Debug(params object[] values){}public static void Report(params object[] values){}public static void Behavior(params object[] values){}}
 public static class CreatorRoomSettings {public static void CaptureGravity(Room room){}public static void PrepareGravity(Room room,bool useRoom){}public static bool RoomGravity(IteratorDesign design){return true;}}
}
public static class OracleInitialPlacementCheck {
 static int checks;static void Check(bool value,string reason){checks++;if(!value)throw new Exception(reason);}static bool Same(Vector2 a,Vector2 b){return (a-b).sqrMagnitude<.0001f;}
 public static void Main(){try{Run();}catch(Exception error){Console.Error.WriteLine(error.Message);Environment.ExitCode=1;}}
 static void Run(){
  var remove=new List<Action>();CreatorOracleLifecycle.Install(remove);CreatorChamberMotion.Install(remove);
  foreach(string preset in new[]{"mi-chamber-broken","mi-chamber-moon"}){
   var room=new Room();room.design.chamberPreset=preset;var loaded=new Oracle(room);room.AddObject(loaded);
   loaded.firstChunk.pos+=new Vector2(.1f,.1f);CreatorChamberMotion.Prepare(loaded);
   Check(loaded.firstChunk.hardSets==1&&loaded.firstChunk.pos.y==110,preset+" room-loader first update did not place the normal first oracle");
   var pasted=new Vector2(650,400);loaded.firstChunk.pos=pasted;CreatorChamberMotion.Prepare(loaded);CreatorChamberMotion.After(loaded);
   Check(Same(loaded.firstChunk.pos,pasted)&&loaded.firstChunk.hardSets==1,preset+" first-placement marker was used twice");
   var copy=new Oracle(room);room.AddObject(copy);copy.firstChunk.pos=pasted;CreatorChamberMotion.Prepare(copy);
   Check(Same(copy.firstChunk.pos,pasted)&&copy.firstChunk.hardSets==0,preset+" copied oracle was given the normal first placement");
   var copyAtNative=new Oracle(room);room.AddObject(copyAtNative);CreatorChamberMotion.Prepare(copyAtNative);
   Check(Same(copyAtNative.firstChunk.pos,new Vector2(350,350))&&copyAtNative.firstChunk.hardSets==0,preset+" native-position copy was mistaken for initial room loading");
   var movedRoom=new Room();movedRoom.design.chamberPreset=preset;var moved=new Oracle(movedRoom);movedRoom.AddObject(moved);moved.firstChunk.pos=pasted;CreatorChamberMotion.Prepare(moved);
   Check(Same(moved.firstChunk.pos,pasted)&&moved.firstChunk.hardSets==0,preset+" movement before the first update was overwritten");
   var waitingRoom=new Room();waitingRoom.design.chamberPreset=preset;var waiting=new Oracle(waitingRoom);waiting.room=null;CreatorChamberMotion.Prepare(waiting);waiting.room=waitingRoom;CreatorChamberMotion.Prepare(waiting);
   Check(waiting.firstChunk.hardSets==1&&waiting.firstChunk.pos.y==110,preset+" missing room consumed the first-placement marker");
   var waitingArmRoom=new Room();waitingArmRoom.design.chamberPreset=preset;var waitingArm=new Oracle(waitingArmRoom);var arm=waitingArm.arm;waitingArm.arm=null;CreatorChamberMotion.Prepare(waitingArm);waitingArm.arm=arm;CreatorChamberMotion.Prepare(waitingArm);
   Check(waitingArm.firstChunk.hardSets==1,preset+" incomplete construction consumed the first-placement marker");
  }
  for(int i=remove.Count-1;i>=0;i--)remove[i]();Console.WriteLine("Oracle initial placement: "+checks+" checks passed.");
 }
}
