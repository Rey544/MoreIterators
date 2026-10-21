namespace MoreIterators {
using System;
using System.IO;
using System.Collections.Generic;
using UnityEngine;

// Only called at the main menu, before creating the temporary preview save.
// A newly exported TEST room must pass the same den lookup as a normal room.
public static class CreatorLaunch {
 const string UiMessage="MoreIterators.UiMessage";
 static Exception Visible(Exception error){error.Data[UiMessage]=error.Message;return error;}
 static string ContentKey(string key){return PlaybackMode.Enabled?key+".playback":key;}
 public static string Normalize(string room){return room;}
 public static int ExitNode(string room){var p=IteratorCatalog.Find(room);object value;
  if(p!=null&&IteratorCatalog.Text(p,"entry")==room&&p.TryGetValue("entryNode",out value))return Convert.ToInt32(value);
  if(p!=null&&p.TryGetValue("exitNode",out value))return Convert.ToInt32(value);return p!=null&&NativeRoomProjects.IsNative(p)?0:1;}
 public static int CameraCount(string text){
  string[] lines=text.Split('\n');if(lines.Length<4)throw Visible(new InvalidOperationException(UiText.Get("game.launch.camera_positions_missing")));
  int count=0;foreach(string camera in lines[3].Split('|'))if(camera.Trim().Length>0)count++;
  if(count==0)throw Visible(new InvalidOperationException(UiText.Get("game.launch.camera_views_missing")));return count;
 }
 public static List<string> RoomNames(string text){
  var names=new List<string>();bool rooms=false;
  foreach(string raw in text.Split('\n')){string line=raw.Trim();if(line=="ROOMS"){rooms=true;continue;}if(line=="END ROOMS"){rooms=false;break;}if(!rooms||line.StartsWith("//"))continue;int colon=line.IndexOf(" : ",StringComparison.Ordinal);if(colon>0)names.Add(line.Substring(0,colon));}
  return names;
 }
 public static bool Matches(List<string> names,Dictionary<string,int> map,string region="TEST"){
  int start;if(names.Count==0||map==null||!map.TryGetValue(names[0],out start))return false;
  for(int i=0;i<names.Count;i++){int value;if(!map.TryGetValue(names[i],out value)||value!=start+i)return false;}
  int end;return map.TryGetValue(region+"OffscreenDen",out end)&&end==start+names.Count;
 }
 public static bool ConnectionsMatch(string text,string ai,string entry,int aiNode,int entryNode){
  string[] aiLinks=null,entryLinks=null;bool rooms=false;
  foreach(string raw in text.Split('\n')){
   string line=raw.Trim();if(line=="ROOMS"){rooms=true;continue;}if(line=="END ROOMS"){rooms=false;continue;}
   if(!rooms||line.StartsWith("//"))continue;string[] fields=line.Split(':');if(fields.Length<2)continue;
   string name=fields[0].Trim();if(name!=ai&&name!=entry)continue;
   string[] links=fields[1].Split(',');for(int i=0;i<links.Length;i++)links[i]=links[i].Trim();
   if(name==ai){if(aiLinks!=null)return false;aiLinks=links;}else{if(entryLinks!=null)return false;entryLinks=links;}
  }
  return aiLinks!=null&&entryLinks!=null&&aiNode>=0&&entryNode>=0&&aiNode<aiLinks.Length&&entryNode<entryLinks.Length&&aiLinks[aiNode]==entry&&entryLinks[entryNode]==ai;
 }
 static bool ExternalEntry(Dictionary<string,object> project){object raw;var binding=project.TryGetValue("roomBinding",out raw)?raw as Dictionary<string,object>:null;return binding!=null&&IteratorCatalog.Text(binding,"entryMode")=="existing";}
 public static void Report(string entry,bool ok,string error){try{Directory.CreateDirectory(CreatorRuntime.Root);File.WriteAllText(Path.Combine(CreatorRuntime.Root,"launch-status.json"),Json.Serialize(new Dictionary<string,object>{{"entry",entry},{"ok",ok},{"error",error},{"time",DateTime.UtcNow.ToString("o")}}));}catch(Exception failure){MiDiagnostics.Report("MI-LAUNCH-STATUS","CreatorLaunch.Report",failure,"entry="+entry+" path="+CreatorRuntime.Root);}}
 public static bool Ensure(Menu.MainMenu menu,string entry){
  UiText.Use(menu==null?null:menu.manager.rainWorld);
  try{
   Dictionary<string,object> project=null;foreach(var p in CreatorRuntime.Projects())if((string)p["entry"]==entry||(string)p["ai"]==entry){project=p;break;}
   string region=entry.Split('_')[0];
   if(project==null)throw Visible(new InvalidOperationException(UiText.Get(ContentKey("game.launch.project_missing"))));
   string ai=(string)project["ai"],outside=(string)project["entry"];
   if(NativeRoomProjects.IsNative(project)&&!ModManager.MSC)throw Visible(new InvalidOperationException(UiText.Get("game.launch.moon_requires_msc")));
   string folder=region.ToLowerInvariant();
   string worldText=File.ReadAllText(AssetManager.ResolveFilePath("world/"+folder+"/world_"+folder+".txt"));var names=RoomNames(worldText);
   if(!names.Contains(ai)||!names.Contains(outside))throw Visible(new InvalidOperationException(UiText.Format(ContentKey("game.launch.rooms_missing"),region)));
   foreach(string room in new[]{ai,outside}){
    foreach(string suffix in new[]{".txt","_settings.txt"})if(!File.Exists(WorldLoader.FindRoomFile(room,false,suffix,false)))throw Visible(new InvalidOperationException(UiText.Format(ContentKey("game.launch.asset_missing"),room+suffix)));
    int cameras=CameraCount(File.ReadAllText(WorldLoader.FindRoomFile(room,false,".txt",false)));
    for(int i=1;i<=cameras;i++)if(!File.Exists(WorldLoader.FindRoomFile(room,false,"_"+i+".png",false)))throw Visible(new InvalidOperationException(UiText.Format(ContentKey("game.launch.camera_background_missing"),i,room+"_"+i+".png")));
   }
   var progression=menu.manager.rainWorld.progression;
   if(NativeRoomProjects.IsNative(project)){
    if(!RainWorld.roomNameToIndex.ContainsKey(ai)||!RainWorld.roomNameToIndex.ContainsKey(outside))throw Visible(new InvalidOperationException(UiText.Get("game.launch.native_index_missing")));
    Report(entry,true,"");Debug.Log("[More Iterators] Native entry verified: "+outside+" -> "+ai+"; timeline="+project["timeline"]);return true;
   }
   if(Array.IndexOf(progression.regionNames,region)<0)throw Visible(new InvalidOperationException(UiText.Get("game.launch.restart_required")));
   if(ExternalEntry(project)){
    // Existing regions can contain unrelated campaign-conditioned alternatives.
    // Only the explicit unconditional pair and both newly indexed IDs belong
    // to this project; retain the stricter whole-index check for owned regions.
    if(!RainWorld.roomNameToIndex.ContainsKey(ai)||!RainWorld.roomNameToIndex.ContainsKey(outside)||!ConnectionsMatch(worldText,ai,outside,ExitNode(ai),ExitNode(outside)))throw Visible(new InvalidOperationException(UiText.Get("game.launch.restart_required")));
   }else if(!Matches(names,RainWorld.roomNameToIndex,region)||!RainWorld.roomNameToIndex.ContainsKey(entry))throw Visible(new InvalidOperationException(UiText.Get("game.launch.restart_required")));
   Report(entry,true,"");Debug.Log("[More Iterators] Entry verified: "+project["name"]+" -> "+entry);return true;
  }catch(Exception e){
   MiDiagnostics.Report("MI_LAUNCH_FAILED","CreatorLaunch.Ensure",e,entry);
   string detail=e.Data[UiMessage] as string??UiText.Get("game.launch.unexpected");
   string text=UiText.Format("game.launch.failed",detail);Report(entry,false,text);
   if(menu!=null)menu.manager.ShowDialog(new Menu.DialogNotify(text,new Vector2(600,240),menu.manager,delegate{}));return false;
  }
 }
}
}
