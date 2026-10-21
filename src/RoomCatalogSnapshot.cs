using System;
using System.IO;
using System.Collections.Generic;
using System.Globalization;
using System.Text.RegularExpressions;
using UnityEngine;

namespace MoreIterators {
 // Uses the same resolved world files and region list as Warp, without changing Warp's cache.
 public static class RoomCatalogSnapshot {
  static WeakReference owner;
  static int nextRegion;
  static float nextTick;
  static List<object> regions;
  static string generation;
  public static void Tick(RainWorldGame game){
   if(game==null||game.overWorld==null||game.overWorld.regions==null||Time.realtimeSinceStartup<nextTick)return;
   nextTick=Time.realtimeSinceStartup+.2f;
   try{
    if(owner==null||owner.Target!=game){owner=new WeakReference(game);nextRegion=0;regions=new List<object>();generation=Guid.NewGuid().ToString("N");}
    if(nextRegion<game.overWorld.regions.Length){
     Region region=game.overWorld.regions[nextRegion++];
     if(region!=null)regions.Add(ReadRegion(region.name));
     if(nextRegion<game.overWorld.regions.Length)return;
    }
    UpdateLoaded(game);
    var data=new Dictionary<string,object>{{"schema","moreiterators.room-catalog.v1"},{"generation",generation},
     {"capturedAt",DateTime.UtcNow.ToString("o")},{"source","live"},{"complete",true},
     {"currentRegion",game.world==null||game.world.region==null?"":game.world.region.name},
     {"campaign",game.StoryCharacter==null?"":game.StoryCharacter.value},{"regions",regions}};
    var mods=new List<object>();foreach(var mod in ModManager.ActiveMods)mods.Add(mod.id);data["activeMods"]=mods;
    var oracles=new List<object>();foreach(var project in IteratorCatalog.Projects()){
     var item=new Dictionary<string,object>();foreach(string key in new[]{"projectId","oracleId","ai","entry","ownerMod"})item[key]=IteratorCatalog.Text(project,key);oracles.Add(item);
    }data["oracles"]=oracles;
    string path=Path.Combine(RuntimePaths.DataDirectory,"creator/room-catalog.json"),tmp=path+".tmp";
    Directory.CreateDirectory(Path.GetDirectoryName(path));File.WriteAllText(tmp,Json.Serialize(data));
    if(File.Exists(path))File.Replace(tmp,path,null);else File.Move(tmp,path);
    nextTick=Time.realtimeSinceStartup+5f;
   }catch(Exception e){nextTick=Time.realtimeSinceStartup+30f;MiDiagnostics.Report("MI_ROOM_CATALOG","RoomCatalogSnapshot.Tick",e,"Reading resolved region and room assets");}
  }
  static Dictionary<string,object> ReadRegion(string name){
   name=name.ToUpperInvariant();var rooms=new List<object>();
   string path=AssetManager.ResolveFilePath("world/"+name+"/world_"+name+".txt");
   var result=new Dictionary<string,object>{{"name",name},{"rooms",rooms},{"available",File.Exists(path)}};
   if(!File.Exists(path))return result;
   string[] lines=File.ReadAllLines(path);bool inRooms=false,inConditional=false;
   var conditional=new HashSet<string>(StringComparer.OrdinalIgnoreCase);
   foreach(string raw in lines){
    string line=raw.Trim();if(line=="CONDITIONAL LINKS"){inConditional=true;continue;}
    if(line=="END CONDITIONAL LINKS"){inConditional=false;continue;}
    if(inConditional&&!line.StartsWith("//"))foreach(Match match in Regex.Matches(line,@"\b[A-Z0-9]+_[A-Z0-9_]+\b"))conditional.Add(match.Value);
   }
   foreach(string raw in lines){
    string line=raw.Trim();if(line=="ROOMS"){inRooms=true;continue;}if(line=="END ROOMS"){inRooms=false;continue;}
    if(!inRooms||line.Length==0||line.StartsWith("//"))continue;
    string[] parts=line.Split(':');if(parts.Length<2)continue;
    string roomName=parts[0].Trim();bool prefixed=roomName.Contains(")")||roomName.Contains("}");
    int prefix=Math.Max(roomName.LastIndexOf(')'),roomName.LastIndexOf('}'));if(prefix>=0)roomName=roomName.Substring(prefix+1).Trim();
    if(!Regex.IsMatch(roomName,@"^[A-Z0-9]+_[A-Z0-9_]+$"))continue;
    var connections=new List<object>();foreach(string item in parts[1].Split(','))connections.Add(item.Trim());
    string geometry=WorldLoader.FindRoomFile(roomName,false,".txt",false);int exits=ReadExits(geometry);
    var entry=new Dictionary<string,object>{{"name",roomName},{"region",name},{"connections",connections},{"geometryPath",geometry},
     {"exitCount",exits},{"verified",exits>=0&&connections.Count==exits},{"conditional",prefixed||conditional.Contains(roomName)},
     {"oracle",IsOracle(roomName)},{"loaded",false},{"tags",parts.Length>2?String.Join(":",parts,2,parts.Length-2).Trim():""}};
    rooms.Add(entry);
   }
   return result;
  }
  static int ReadExits(string path){
   if(!File.Exists(path))return -1;
   try{
    string nodeLine=null,dimensions=null,tiles=null;using(var reader=new StreamReader(path)){for(int i=0;i<10;i++){nodeLine=reader.ReadLine();if(nodeLine==null)return -1;if(i==1)dimensions=nodeLine;}if(nodeLine.StartsWith("0|")){reader.ReadLine();tiles=reader.ReadLine();}}
    string[] parts=nodeLine.Split('|');int generation,count;
    if(parts.Length<4||!Int32.TryParse(parts[0],out generation)||generation<0||!Int32.TryParse(parts[1],out count)||count<1||parts.Length<count+3)return -1;
    int exits=0;bool pastExits=false;
    for(int i=0;i<count;i++){
     int type=Int32.Parse(parts[i+3].Split(',')[0],CultureInfo.InvariantCulture);
     if(type==AbstractRoomNode.Type.Exit.Index){if(pastExits)return -1;exits++;}else pastExits=true;
    }
    if(generation==0){
     int templates=Int32.Parse(parts[2]);if(templates<1||templates>256||tiles==null)return -1;
     for(int i=0;i<count;i++){
      string[] fields=parts[i+3].Split(',');if(fields.Length<5+count*templates)return -1;
      for(int j=0;j<5;j++)Int32.Parse(fields[j]);
      for(int j=5;j<5+count*templates;j++){string[] pair=fields[j].Split(new[]{' '},StringSplitOptions.RemoveEmptyEntries);if(pair.Length!=2)return -1;Int32.Parse(pair[0]);Int32.Parse(pair[1]);}
     }
     string[] size=dimensions.Split('|')[0].Split('*');int width=Int32.Parse(size[0]),height=Int32.Parse(size[1]);if(width<1||height<1)return -1;
     string[] all=tiles.Split('|');int length=all.Length-(all[all.Length-1]==""?1:0);if((long)width*height!=length)return -1;
     int tileExits=0;for(int i=0;i<length;i++){string[] fields=all[i].Split(',');Int32.Parse(fields[0]);int shortcut=0;
      for(int j=1;j<fields.Length;j++){switch(fields[j]){case "3":shortcut=Math.Max(shortcut,1);break;case "4":shortcut=2;break;case "5":shortcut=3;break;case "9":shortcut=4;break;case "12":shortcut=5;break;}}
      if(shortcut==2)tileExits++;
     }
     if(tileExits!=exits)return -1;
    }
    return exits;
   }catch{return -1;}
  }
  static bool IsOracle(string room){
   if(room.EndsWith("_AI",StringComparison.Ordinal)||room=="RM_AI"||room=="CL_AI"||room=="HR_AI")return true;
   foreach(var project in IteratorCatalog.Projects())if(IteratorCatalog.Text(project,"ai")==room)return true;
   return false;
  }
  static void UpdateLoaded(RainWorldGame game){
   if(game.world==null||game.world.abstractRooms==null)return;
   var loaded=new Dictionary<string,AbstractRoom>(StringComparer.OrdinalIgnoreCase);foreach(var room in game.world.abstractRooms)if(room!=null)loaded[room.name]=room;
   foreach(Dictionary<string,object> region in regions)foreach(Dictionary<string,object> entry in (List<object>)region["rooms"]){
    entry["loaded"]=false;AbstractRoom room;if(!loaded.TryGetValue((string)entry["name"],out room))continue;
    var connections=new List<object>();foreach(int index in room.connections){AbstractRoom other=index<0?null:game.world.GetAbstractRoom(index);connections.Add(other==null?"DISCONNECTED":other.name);}
    int exits=0;if(room.nodes!=null)foreach(var node in room.nodes){if(node.type!=AbstractRoomNode.Type.Exit)break;exits++;}
    // Differences from the resolved file indicate campaign-specific or dynamic links: don't offer them for editing.
    var original=(List<object>)entry["connections"];bool differs=original.Count!=connections.Count;
    for(int i=0;!differs&&i<original.Count;i++)differs=!String.Equals((string)original[i],(string)connections[i],StringComparison.OrdinalIgnoreCase);
    entry["conditional"]=(bool)entry["conditional"]||differs;entry["connections"]=connections;
    entry["exitCount"]=exits;entry["verified"]=room.nodes!=null&&exits==connections.Count;entry["loaded"]=true;
   }
  }
 }
}
