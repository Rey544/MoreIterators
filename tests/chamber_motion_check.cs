using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.CompilerServices;
using MoreIterators;
using UnityEngine;
namespace UnityEngine {
 public struct Vector2 {public float x,y;public Vector2(float x,float y){this.x=x;this.y=y;}public static Vector2 zero {get{return new Vector2();}}public static Vector2 up {get{return new Vector2(0,1);}}public float sqrMagnitude {get{return x*x+y*y;}}public Vector2 normalized {get{float length=(float)Math.Sqrt(sqrMagnitude);return length>.0001f?this*(1/length):zero;}}public static Vector2 operator +(Vector2 a,Vector2 b){return new Vector2(a.x+b.x,a.y+b.y);}public static Vector2 operator -(Vector2 a,Vector2 b){return new Vector2(a.x-b.x,a.y-b.y);}public static Vector2 operator *(Vector2 a,float b){return new Vector2(a.x*b,a.y*b);}public static Vector2 Lerp(Vector2 a,Vector2 b,float t){return a+(b-a)*t;}}
 public static class Mathf {public static float Clamp(float v,float a,float b){return Math.Max(a,Math.Min(b,v));}public static float Sin(float v){return (float)Math.Sin(v);}public static float Cos(float v){return (float)Math.Cos(v);}}
}
public class Room {
 public class Tile {public enum TerrainType {Air,Solid,Slope,Floor,ShortcutEntrance}public TerrainType Terrain;public bool Solid {get{return Terrain==TerrainType.Solid;}}}
 public int width,height,reads;public int[,] cells;public float gravity;public IteratorDesign design=new IteratorDesign();public float PixelWidth {get{return width*20;}}public float PixelHeight {get{return height*20;}}
 public Room(int width,int height){this.width=width;this.height=height;cells=new int[width,height];}
 public Tile GetTile(Vector2 p){reads++;int x=(int)Math.Floor(p.x/20),y=(int)Math.Floor(p.y/20);return new Tile{Terrain=(Tile.TerrainType)(x<0||y<0||x>=width||y>=height?1:cells[x,y])};}
}
public class BodyChunk {public Vector2 pos,lastPos,vel;public int hardSets;public void HardSetPosition(Vector2 p){pos=lastPos=p;hardSets++;}}
public class OracleBehavior {public int consistentBasePosCounter;}
public class Oracle {
 public class OracleArm {public Oracle oracle;public class Joint {public float totalLength=150;public Vector2 pos,lastPos,vel;}public Vector2[] cornerPositions={new Vector2(210,630),new Vector2(770,630),new Vector2(770,70),new Vector2(210,70)};public Joint[] joints={new Joint(),new Joint(),new Joint(),new Joint()};public float framePos,lastFramePos;public bool baseMoving;public Vector2 BasePos(float t){return (cornerPositions[2]+cornerPositions[3])*.5f;}}
 public Room room;public bool owned=true;public OracleArm arm=new OracleArm();public OracleBehavior oracleBehavior=new OracleBehavior();public BodyChunk[] bodyChunks={new BodyChunk{pos=new Vector2(480,350)},new BodyChunk{pos=new Vector2(480,341)}};public BodyChunk firstChunk {get{return bodyChunks[0];}}
 public Oracle(){arm.oracle=this;}
}
public class GenericBodyPart {public Vector2 pos,lastPos,vel;}
public class OracleGraphics {public Oracle oracle;public GenericBodyPart[] feet={new GenericBodyPart(),new GenericBodyPart()};public Vector2[,] knees=new Vector2[2,2];}
namespace MoreIterators {
 public class IteratorDesign {public string chamberPreset="";public float puppetScale=1,torsoLength=1,neckLength=1;public static IteratorDesign ForRoom(Room room){return room.design;}}
 public static class CreatorOracleLifecycle {public static bool Owns(Oracle o){return o.owned;}public static bool ConsumeInitialPlacement(Oracle o){return false;}}
}
public static class ChamberMotionCheck {
 static int checks;
 static void Check(bool value,string why){checks++;if(!value)throw new Exception(why);}
 static bool Same(Vector2 a,Vector2 b){return (a-b).sqrMagnitude<.01f;}
 static Room Load(string root,string name){var lines=File.ReadAllLines(Path.Combine(root,name,"chamber.txt"));var dimensions=lines[1].Split('|')[0].Split('*');var room=new Room(int.Parse(dimensions[0]),int.Parse(dimensions[1]));var tiles=lines[11].TrimEnd('|').Split('|');for(int x=0;x<room.width;x++)for(int y=0;y<room.height;y++)room.cells[x,y]=int.Parse(tiles[x*room.height+room.height-1-y].Split(',')[0]);return room;}
 static CreatorChamberArea Area(Room room,Vector2 preferred){return new CreatorChamberArea(room.width,room.height,delegate(int x,int y){return room.cells[x,y];},preferred);}
 static void SafeRectangle(CreatorChamberArea area,string label){Check(area.valid,label+" has no usable rectangle");for(float x=area.minimum.x;x<=area.maximum.x;x+=5)for(float y=area.minimum.y;y<=area.maximum.y;y+=5)Check(area.Clear(new Vector2(x,y)),label+" crosses terrain");}
 [MethodImpl(MethodImplOptions.NoInlining)]
 static WeakReference UnreferencedOracle(Room room){var oracle=new Oracle{room=room};CreatorChamberMotion.Prepare(oracle);return new WeakReference(oracle);}
 public static void Main(string[] args){try{Run(args);}catch(Exception error){Console.Error.WriteLine(error.Message);Environment.ExitCode=1;}}
 static void Run(string[] args){
  var remove=new List<Action>();CreatorChamberMotion.Install(remove);
  foreach(string name in new[]{"pebbles","moon","broken","irregular","multi-screen"}){
   var room=Load(args[0],name);room.design.chamberPreset="mi-chamber-"+name;var preferred=new Vector2(room.PixelWidth*(name=="moon"?.81f:.5f),room.PixelHeight*(name=="moon"?.27f:.5f));var area=Area(room,preferred);SafeRectangle(area,name);
   var o=new Oracle{room=room};CreatorChamberMotion.Prepare(o,true);Check(area.Clear(o.firstChunk.pos),name+" spawned in terrain");Check(room.gravity==0,name+" changed room gravity");
   if(name=="broken"||name=="moon"){
    Check(CreatorChamberMotion.Seated(o),name+" was not seated");var seat=o.firstChunk.pos;int floorY=(int)Math.Floor((seat.y-30)/20)-1,x=(int)(seat.x/20);Check(room.cells[x,floorY]==1||room.cells[x,floorY]==3,name+" has no floor support");if(name=="moon")Check(seat.x>room.PixelWidth*.65f,"Moon used the left water shaft rather than its platform");
    Check(seat.x>=area.minimum.x&&seat.x<=area.maximum.x&&seat.y>=area.minimum.y-20&&seat.y<=area.maximum.y,name+" seat disconnected from arm frame");
    Check(Same(CreatorChamberMotion.Target(o,new Vector2(999,999)),seat),name+" rest target lost its floor");
    var graphics=new OracleGraphics{oracle=o};CreatorChamberMotion.Graphics(graphics);Check(graphics.feet[0].pos.y>=floorY*20+20,name+" foot is below floor");
    var foot=graphics.feet[0].pos;var knee=graphics.knees[0,0];var shift=new Vector2(40,80);int sets=o.firstChunk.hardSets;
    for(int i=0;i<o.bodyChunks.Length;i++){o.bodyChunks[i].lastPos=o.bodyChunks[i].pos;o.bodyChunks[i].pos+=shift;o.bodyChunks[i].vel=new Vector2(20,20);}
    var displaced=o.firstChunk.pos;
    for(int tick=0;tick<360;tick++){
     CreatorChamberMotion.Prepare(o);CreatorChamberMotion.After(o);
     Check(Same(o.firstChunk.pos,displaced)&&Same(o.firstChunk.vel,new Vector2(20,20))&&o.firstChunk.hardSets==sets,name+" rewrote externally moved body physics");
    }
    CreatorChamberMotion.Graphics(graphics);Check(Same(graphics.feet[0].pos,foot+shift)&&Same(graphics.knees[0,0],knee+shift),name+" sitting limbs remained pinned to the room");
    Check(Same(graphics.feet[0].lastPos,foot)&&Same(graphics.knees[0,1],knee),name+" sitting pose lost body interpolation");
    var rest=CreatorChamberMotion.Target(o,new Vector2(999,999));Check(rest.x==displaced.x&&rest.y<displaced.y,name+" rest target pulled a dragged body to its original corner");
    var action=area.Center;Check(Same(CreatorChamberMotion.Target(o,action,false),action),name+" reading or encounter target was replaced by sitting");
    Check(Same(CreatorChamberMotion.Direction(o,new Vector2(1,0)),new Vector2(1,0)),name+" reading or encounter orientation was replaced by sitting");
    Check(Same(CreatorChamberMotion.MoveTarget(o,action),action)&&Same(CreatorChamberMotion.Target(o,action),action),name+" explicit movement was ignored");
    CreatorChamberMotion.WorkTarget(o,0,action);Check(CreatorChamberMotion.Target(o,action).x==displaced.x,name+" idle restart lost the dragged position");
    o.room=null;CreatorChamberMotion.Prepare(o);CreatorChamberMotion.After(o);o.room=room;
    o.firstChunk.pos=action;CreatorChamberMotion.Prepare(o);Check(Same(o.firstChunk.pos,action)&&o.firstChunk.hardSets==sets,name+" paste repeated spawn placement");
    var copy=new Oracle{room=room};copy.firstChunk.pos=action;copy.bodyChunks[1].pos=action-new Vector2(0,9);CreatorChamberMotion.Prepare(copy);Check(Same(copy.firstChunk.pos,action)&&copy.firstChunk.hardSets==0,name+" new pasted copy was teleported away from its placement");
    Console.WriteLine(name+" initial seat="+seat.x+","+seat.y+" floor="+((floorY+1)*20)+" dragged="+displaced.x+","+displaced.y+" rest="+rest.x+","+rest.y);
   }else{
    Check(!CreatorChamberMotion.Seated(o),name+" incorrectly seated");for(int tick=0;tick<3000;tick+=7)Check(area.Clear(CreatorChamberMotion.Target(o,CreatorChamberMotion.WorkTarget(o,tick,new Vector2(-100,-100)))),name+" work target crosses terrain");
    Vector2 target=CreatorChamberMotion.Target(o,new Vector2(-10000,10000));Check(area.Clear(target),name+" failed to clamp foreign/reading target");
    Check(area.Clear(CreatorChamberMotion.ArmPosition(o.arm,new Vector2(-10000,10000))),name+" rounded arm base can leave safe bounds");
    o.firstChunk.pos=new Vector2(-300,-400);CreatorChamberMotion.After(o);Check(area.Clear(o.firstChunk.pos),name+" failed to contain a displaced body");
   }
   float length=o.arm.joints[0].totalLength;CreatorChamberMotion.Prepare(o);Check(o.arm.joints[0].totalLength==length,"Arm length compounded on each update");
   Console.WriteLine(name+" bounds="+area.minimum.x+","+area.minimum.y+".."+area.maximum.x+","+area.maximum.y+" seated="+CreatorChamberMotion.Seated(o)+" position="+o.firstChunk.pos.x+","+o.firstChunk.pos.y);
  }
  float previousWidth=0,previousHeight=0;
  foreach(float scale in new[]{.5f,1f,2f,3f}){
   var room=Load(args[0],"broken");room.design.chamberPreset="mi-chamber-broken";room.design.puppetScale=scale;room.design.torsoLength=1.4f;
   var o=new Oracle{room=room};CreatorChamberMotion.Prepare(o,true);var area=Area(room,new Vector2(480,350));var graphics=new OracleGraphics{oracle=o};CreatorChamberMotion.Graphics(graphics);
   float clearance=Math.Max(30,(11+14*room.design.torsoLength+room.design.neckLength)*scale-9),floor=o.firstChunk.pos.y-clearance;
   Check(area.Clear(o.firstChunk.pos),"Scaled sitting body overlaps terrain");
   float footDrop=o.firstChunk.pos.y-graphics.feet[0].pos.y;
   float renderedFoot=o.firstChunk.pos.y+12-(5+room.design.neckLength+(5+footDrop)*room.design.torsoLength)*scale;
   Check(renderedFoot>=floor+1.9f,"Scaled seated foot was drawn below its support");
  }
  var platform=new Room(20,20);for(int x=0;x<20;x++){platform.cells[x,0]=1;platform.cells[x,6]=3;}
  var platformArea=Area(platform,new Vector2(200,260));Vector2 supported;
  Check(platformArea.SupportBelow(new Vector2(200,260),30,out supported)&&supported.y==170,"One-way platform was not used as real support");
  platform.cells[9,6]=0;Check(platformArea.SupportBelow(new Vector2(200,260),30,out supported)&&supported.y==50,"Unsupported edge accepted as a full sitting surface");
  foreach(int size in new[]{1,2,3}){
   var room=new Room(70*size,40*size);for(int x=0;x<room.width;x++)for(int y=0;y<room.height;y++)room.cells[x,y]=x<4||y<4||x>=room.width-4||y>=room.height-4?1:0;
   room.design.chamberPreset="mi-chamber-pebbles";var area=Area(room,new Vector2(room.PixelWidth*.5f,room.PixelHeight*.5f));SafeRectangle(area,"expanded "+size);var o=new Oracle{room=room};CreatorChamberMotion.Prepare(o);
   float width=o.arm.cornerPositions[1].x-o.arm.cornerPositions[0].x,height=o.arm.cornerPositions[0].y-o.arm.cornerPositions[2].y;Check(width>previousWidth&&height>previousHeight,"Wider/taller room kept fixed native arm bounds");Check(o.arm.joints[0].totalLength>=150,"Expanded arm shrank");previousWidth=width;previousHeight=height;
  }
  foreach(string marker in new[]{"","broken","mi-chamber-unknown"}){var room=Load(args[0],"broken");room.design.chamberPreset=marker;var o=new Oracle{room=room};var original=o.firstChunk.pos;var corner=o.arm.cornerPositions[0];CreatorChamberMotion.Prepare(o);CreatorChamberMotion.After(o);Check(Same(o.firstChunk.pos,original)&&Same(o.arm.cornerPositions[0],corner),"Unmarked old/custom project was modified");Check(Same(CreatorChamberMotion.Target(o,new Vector2(-1,-2)),new Vector2(-1,-2)),"Unmarked old/custom target was intercepted");}
  var wider=Load(args[0],"multi-screen");var wideOracle=new Oracle{room=wider};CreatorChamberMotion.Prepare(wideOracle);Check(wideOracle.arm.cornerPositions[1].x>1800&&!CreatorChamberMotion.Seated(wideOracle),"Unmarked old wide room was not adapted or was guessed to be damaged");Check(Same(wideOracle.firstChunk.pos,new Vector2(480,350)),"Unmarked old wide room unnecessarily moved its existing safe position");
  var hotRoom=new Room(140,80);for(int x=0;x<hotRoom.width;x++)for(int y=0;y<hotRoom.height;y++)hotRoom.cells[x,y]=x<4||y<4||x>=hotRoom.width-4||y>=hotRoom.height-4?1:0;
  var hot=new Oracle{room=hotRoom};CreatorChamberMotion.Prepare(hot);float stretched=hot.arm.joints[0].totalLength;
  for(int i=0;i<8;i++){hotRoom.design.chamberPreset=i%2==0?"mi-chamber-pebbles":"mi-chamber-irregular";CreatorChamberMotion.Prepare(hot);Check(hot.arm.joints[0].totalLength==stretched,"Preset hot reload compounded joint lengths");}
  hot.room=Load(args[0],"pebbles");CreatorChamberMotion.Prepare(hot);Check(hot.arm.joints[0].totalLength==150&&Same(hot.arm.cornerPositions[0],new Vector2(210,630)),"Leaving adaptation did not restore the original arm");
  var solid=new Room(48,36);for(int x=0;x<solid.width;x++)for(int y=0;y<solid.height;y++)solid.cells[x,y]=1;solid.design.chamberPreset="mi-chamber-broken";var blocked=new Oracle{room=solid};CreatorChamberMotion.Prepare(blocked);int scans=solid.reads;for(int i=0;i<60;i++)CreatorChamberMotion.Prepare(blocked);Check(scans==solid.reads,"No-solution geometry rescanned every frame");
  var native=new Oracle{room=Load(args[0],"broken"),owned=false};native.room.design.chamberPreset="mi-chamber-broken";CreatorChamberMotion.Prepare(native);Check(Same(native.firstChunk.pos,new Vector2(480,350)),"Native oracle was changed");
  var lifetimeRoom=Load(args[0],"broken");lifetimeRoom.design.chamberPreset="mi-chamber-broken";
  var expired=UnreferencedOracle(lifetimeRoom);GC.Collect();GC.WaitForPendingFinalizers();GC.Collect();Check(!expired.IsAlive,"Motion tracking keeps an unused oracle alive");
  var lifetime=new Oracle{room=lifetimeRoom};lifetime.arm.framePos=31;lifetime.arm.lastFramePos=32;var oldArm=lifetime.arm;
  CreatorChamberMotion.Prepare(lifetime);Check(oldArm.framePos==10002.5f,"Seated lifecycle fixture did not adapt");
  lifetime.arm=new Oracle.OracleArm{oracle=lifetime};CreatorChamberMotion.Prepare(lifetime);
  Check(oldArm.framePos==31&&oldArm.lastFramePos==32&&Same(oldArm.cornerPositions[0],new Vector2(210,630))&&oldArm.joints[0].totalLength==150,"Replacing an arm left its previous frame modified");
  lifetime.arm.framePos=123;lifetime.arm.lastFramePos=124;
  for(int i=remove.Count-1;i>=0;i--)remove[i]();remove.Clear();
  Check(Same(lifetime.arm.cornerPositions[0],new Vector2(210,630))&&lifetime.arm.joints[0].totalLength==150&&lifetime.arm.framePos==0&&lifetime.arm.lastFramePos==0,"Uninstall did not restore the original arm frame");
  Check(Same(wideOracle.arm.cornerPositions[1],new Vector2(770,630))&&wideOracle.arm.joints[0].totalLength==150,"Uninstall did not restore another live wide-room arm");
  var outside=new Vector2(-100,-200);int disabledReads=lifetimeRoom.reads;
  CreatorChamberMotion.Prepare(lifetime);CreatorChamberMotion.After(lifetime);
  Check(!CreatorChamberMotion.Seated(lifetime)&&Same(CreatorChamberMotion.Target(lifetime,outside),outside)&&Same(CreatorChamberMotion.BaseTarget(lifetime,outside),outside)&&Same(CreatorChamberMotion.WorkTarget(lifetime,1,outside),outside)&&Same(CreatorChamberMotion.Direction(lifetime,outside),outside)&&Same(CreatorChamberMotion.ArmPosition(lifetime.arm,outside),outside),"Direct behavior calls reactivate adaptation after uninstall");
  var disabledGraphics=new OracleGraphics{oracle=lifetime};CreatorChamberMotion.Graphics(disabledGraphics);Check(Same(disabledGraphics.feet[0].pos,Vector2.zero)&&lifetimeRoom.reads==disabledReads,"Uninstalled motion still adjusts graphics or scans terrain");
  CreatorChamberMotion.Install(remove);CreatorChamberMotion.Prepare(lifetime);Check(CreatorChamberMotion.Seated(lifetime)&&lifetime.arm.framePos==10002.5f,"Reinstall did not restore adaptation");CreatorChamberMotion.Dispose();
  Console.WriteLine("Chamber motion: "+checks+" checks passed.");
 }
}
