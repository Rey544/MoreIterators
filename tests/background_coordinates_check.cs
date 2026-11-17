using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
namespace UnityEngine {
 public struct Vector2 {
  public float x,y;public Vector2(float x,float y){this.x=x;this.y=y;}
  public static Vector2 operator +(Vector2 a,Vector2 b){return new Vector2(a.x+b.x,a.y+b.y);}
  public static Vector2 operator -(Vector2 a,Vector2 b){return new Vector2(a.x-b.x,a.y-b.y);}
  public static Vector2 operator *(Vector2 a,float b){return new Vector2(a.x*b,a.y*b);}
 }
}
public class AbstractRoom {public string name="TEST_A";public Vector2 size=new Vector2(48,36),mapPos=new Vector2(12,30);}
public class Region {public string name="TEST";}
public class World {public Region region=new Region();}
public class Room {public AbstractRoom abstractRoom=new AbstractRoom();public World world=new World();}
public class BackgroundScene {public Room room=new Room();}
public class AboveCloudsView:BackgroundScene {}
public static class ModManager {public static bool MSC=true;}
public static class AssetManager {public static string root;public static int reads;public static string ResolveFilePath(string path){reads++;return Path.Combine(root,path);}}
public static class Json {
 public static object Deserialize(string text){return Convert(new System.Web.Script.Serialization.JavaScriptSerializer().DeserializeObject(text));}
 static object Convert(object value){var map=value as Dictionary<string,object>;if(map!=null){var result=new Dictionary<string,object>();foreach(var pair in map)result[pair.Key]=Convert(pair.Value);return result;}var array=value as object[];if(array!=null){var result=new List<object>();foreach(var item in array)result.Add(Convert(item));return result;}return value;}
}
namespace MoreIterators {
 public class ContentAsset {public string path,owner;}
 public static class ContentAssets {
  public static bool managed=true;
  public static List<ContentAsset> Files(string directory,string extension){var result=new List<ContentAsset>();string folder=Path.Combine(AssetManager.root,directory);if(Directory.Exists(folder))foreach(string path in Directory.GetFiles(folder,"*"+extension))result.Add(new ContentAsset{path=path,owner="fixture"});return result;}
  public static bool Managed(string owner){return managed;}
 }
 public static class MiDiagnostics {public static int errors;public static void Report(string code,string method,Exception error,string room){errors++;}}
}
namespace On {
 public static class BackgroundScene {
  public delegate Vector2 orig_RoomToWorldPos(global::BackgroundScene scene,Vector2 point);
  public delegate Vector2 hook_RoomToWorldPos(orig_RoomToWorldPos orig,global::BackgroundScene scene,Vector2 point);
  public static event hook_RoomToWorldPos RoomToWorldPos;
  public static Vector2 Call(orig_RoomToWorldPos orig,global::BackgroundScene scene,Vector2 point){return RoomToWorldPos==null?orig(scene,point):RoomToWorldPos(orig,scene,point);}
 }
}
public static class BackgroundCoordinatesCheck {
 static int assertions,calls;
 static void Check(bool condition,string why){assertions++;if(!condition)throw new Exception(why);}
 static Vector2 Native(BackgroundScene scene,Vector2 point){calls++;return new Vector2(100+point.x,200+point.y);}
 static Vector2 Run(BackgroundScene scene){int before=calls;var result=On.BackgroundScene.Call(Native,scene,new Vector2(3,7));Check(calls==before+1,"orig must run exactly once");return result;}
 static void Same(Vector2 value,float x,float y,string why){Check(Math.Abs(value.x-x)<.002&&Math.Abs(value.y-y)<.002,why);}
 static string Data(string room,string size,string position){return "{\"schema\":\"moreiterators.background-coordinates.v1\",\"room\":\""+room+"\",\"size\":"+size+",\"mapPosition\":"+position+"}";}
 public static void Main(string[] args){
  AssetManager.root=args[0];string file=Path.Combine(args[0],"world/test-rooms/TEST_A_mi_background.json");Directory.CreateDirectory(Path.GetDirectoryName(file));
  var remove=new List<Action>();MoreIterators.CreatorBackgroundCoordinates.Install(remove);
  Same(Run(new AboveCloudsView()),103,207,"missing coordinates preserve native behavior");
  File.WriteAllText(file,Data("TEST_A","[48,36]","[42,90]"));
  var scene=new AboveCloudsView();Same(Run(scene),303,607,"coordinate correction");
  int reads=AssetManager.reads;for(int i=0;i<100;i++)Run(scene);Check(reads==AssetManager.reads,"no frame file reads");
  Same(scene.room.abstractRoom.mapPos,12,30,"world map must not change");
  Same(Run(new BackgroundScene()),103,207,"other background scenes unaffected");
  var lc=new AboveCloudsView();lc.room.world.region.name="LC";Same(Run(lc),103,207,"native LC behavior preserved");
  MoreIterators.ContentAssets.managed=false;Same(Run(new AboveCloudsView()),103,207,"foreign independent runtime not corrected twice");MoreIterators.ContentAssets.managed=true;
  File.WriteAllText(file,Data("TEST_A","[49,36]","[42,90]"));Same(Run(new AboveCloudsView()),103,207,"changed geometry invalidates stored coordinates");
  File.WriteAllText(file,Data("TEST_B","[48,36]","[42,90]"));Same(Run(new AboveCloudsView()),103,207,"renamed room mismatch rejected");
  File.WriteAllText(file,Data("TEST_A","[48,36]","[true,90]"));Same(Run(new AboveCloudsView()),103,207,"non-numeric coordinates rejected");
  File.WriteAllText(file,"{broken");Same(Run(new AboveCloudsView()),103,207,"corrupt file falls back");Check(MoreIterators.MiDiagnostics.errors==3,"bad contexts reported once per scene");
  bool raised=false;try{On.BackgroundScene.Call(delegate(BackgroundScene s,Vector2 p){throw new InvalidOperationException("native");},new AboveCloudsView(),new Vector2());}catch(InvalidOperationException){raised=true;}Check(raised,"native exceptions not swallowed");
  remove[0]();Same(Run(scene),103,207,"uninstall removes correction");
  remove.Clear();MoreIterators.CreatorBackgroundCoordinates.Install(remove);File.WriteAllText(file,Data("TEST_A","[48,36]","[72,120]"));Same(Run(scene),503,807,"reinstall clears old scene cache");remove[0]();
  Console.WriteLine("background coordinate checks passed: "+assertions);
 }
}
