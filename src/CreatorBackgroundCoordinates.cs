using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Runtime.CompilerServices;
using System.Text.RegularExpressions;
using UnityEngine;

namespace MoreIterators {
 public static class CreatorBackgroundCoordinates {
  sealed class State {public bool valid;public Vector2 position;}
  static ConditionalWeakTable<BackgroundScene,State> scenes=new ConditionalWeakTable<BackgroundScene,State>();
  public static void Install(List<Action> remove){
   On.BackgroundScene.RoomToWorldPos+=RoomToWorldPos;
   remove.Add(delegate {On.BackgroundScene.RoomToWorldPos-=RoomToWorldPos;scenes=new ConditionalWeakTable<BackgroundScene,State>();});
  }
  static Vector2 RoomToWorldPos(On.BackgroundScene.orig_RoomToWorldPos orig,BackgroundScene scene,Vector2 point){
   Vector2 result=orig(scene,point);
   if(!(scene is AboveCloudsView)||scene.room==null||scene.room.abstractRoom==null)return result;
   if(ModManager.MSC&&scene.room.world!=null&&scene.room.world.region!=null&&scene.room.world.region.name=="LC")return result;
   State state=scenes.GetValue(scene,Read);
   return state.valid?result+(state.position-scene.room.abstractRoom.mapPos)*(20f/3f):result;
  }
  static State Read(BackgroundScene scene){
   var state=new State();string room=scene.room.abstractRoom.name;
   if(String.IsNullOrEmpty(room)||!Regex.IsMatch(room,@"^[A-Z][A-Z0-9]{1,7}_[A-Z0-9_]{1,64}$"))return state;
   string relative="world/"+room.Split('_')[0].ToLowerInvariant()+"-rooms/"+room+"_mi_background.json";
   try {
    string file=AssetManager.ResolveFilePath(relative);
    if(!File.Exists(file))return state;
    bool managed=false;
    foreach(var asset in ContentAssets.Files(relative.Substring(0,relative.LastIndexOf('/')),".json"))if(String.Equals(Path.GetFullPath(asset.path),Path.GetFullPath(file),StringComparison.OrdinalIgnoreCase)&&ContentAssets.Managed(asset.owner)){managed=true;break;}
    if(!managed)return state;
    if(new FileInfo(file).Length>4096)throw new InvalidDataException("Background coordinates exceed the supported size.");
    var data=Json.Deserialize(File.ReadAllText(file)) as Dictionary<string,object>;
    object value;
    if(data==null||!data.TryGetValue("schema",out value)||!Equals(value,"moreiterators.background-coordinates.v1")||!data.TryGetValue("room",out value)||!Equals(value,room))throw new InvalidDataException("Background coordinates do not match the room.");
    Vector2 size=Pair(data,"size"),position=Pair(data,"mapPosition");
    if(size.x!=scene.room.abstractRoom.size.x||size.y!=scene.room.abstractRoom.size.y)return state;
    state.position=position;state.valid=true;
   }catch(Exception error){MiDiagnostics.Report("MI-ROOM-COORDINATES","CreatorBackgroundCoordinates.Read",error,room);}
   return state;
  }
  static Vector2 Pair(Dictionary<string,object> data,string key){
   object raw;var values=data.TryGetValue(key,out raw)?raw as List<object>:null;
   if(values==null||values.Count!=2)throw new InvalidDataException("Invalid background coordinate pair.");
   return new Vector2(Number(values[0]),Number(values[1]));
  }
  static float Number(object value){
   if(!(value is double)&&!(value is long)&&!(value is int)&&!(value is float))throw new InvalidDataException("Background coordinates must be numbers.");
   float result=Convert.ToSingle(value,CultureInfo.InvariantCulture);
   if(float.IsNaN(result)||float.IsInfinity(result)||Math.Abs(result)>10000000f)throw new InvalidDataException("Background coordinates are outside the supported range.");
   return result;
  }
 }
}
