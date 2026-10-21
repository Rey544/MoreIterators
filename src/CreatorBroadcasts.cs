namespace MoreIterators {
using System;
using System.IO;
using System.Collections.Generic;
using System.Runtime.CompilerServices;
using MoreSlugcats;
using UnityEngine;

[Serializable] public sealed class BroadcastLine {
 public string text="",color="#ffffff",font="normal";public float size=1,speed=1,hold=2.5f;
}
[Serializable] public sealed class BroadcastPage {public BroadcastLine[] lines=new BroadcastLine[0];}
[Serializable] public sealed class BroadcastStyle {public string font="normal";public float size=1,speed=1,hold=2.5f;}
[Serializable] public sealed class BroadcastSpeaker {public string name="",color="#ffffff";public string[] aliases=new string[0];}
[Serializable] public sealed class BroadcastProject {
 public string schema="",id="",uid="",runtimeId="",name="",region="",room="";public int revision;public float x=.5f,y=.5f;
 public BroadcastPage[] pages=new BroadcastPage[0];
 // Null means an older file with intentional per-line styling.
 public BroadcastStyle style;public bool useCharacterColors;public BroadcastSpeaker[] speakers=new BroadcastSpeaker[0];
}
public static class CreatorBroadcastStyle {
 static string Key(string value){return (value??"").Trim().Trim('【','】','[',']').Trim().ToLowerInvariant();}
 public static string Prefix(string text){
  if(String.IsNullOrEmpty(text))return "";int colon=text.IndexOfAny(new[]{':','：'});if(colon<0)return "";
  string prefix=text.Substring(0,colon);if(prefix.IndexOfAny(new[]{'\r','\n'})>=0)return "";return Key(prefix);
 }
 public static BroadcastLine Resolve(BroadcastProject project,BroadcastLine line){
  if(project.style==null)return line;
  var s=project.style;var result=new BroadcastLine{text=line.text,font=s.font,size=s.size,speed=s.speed,hold=s.hold,color="#ffffff"};
  string key=Prefix(line.text);if(!project.useCharacterColors||key.Length==0||project.speakers==null)return result;
  foreach(var speaker in project.speakers){if(speaker==null)continue;bool match=Key(speaker.name)==key;
   if(!match&&speaker.aliases!=null)foreach(string alias in speaker.aliases)if(Key(alias)==key){match=true;break;}
   if(match){result.color=speaker.color;break;}
  }return result;
 }
}
public static class CreatorBroadcastCatalog {
 static float next;static List<BroadcastProject> items=new List<BroadcastProject>();
 public static List<BroadcastProject> All(){
  if(ModManager.ActiveMods==null)return items;
  if(Time.realtimeSinceStartup<next)return items;next=PlaybackMode.Enabled?float.MaxValue:Time.realtimeSinceStartup+1;
  var found=new Dictionary<string,BroadcastProject>();
  foreach(var m in ModManager.ActiveMods)if(!PlaybackMode.Enabled||m.id==RuntimePaths.ModId){
#if !PLAYBACK
   if(RuntimePaths.HasIndependentRuntime(m.path))continue;
#endif
   Read(Path.Combine(m.path,"moreiterators/broadcasts"),found);
  }
  if(!PlaybackMode.Enabled)Read(Path.Combine(RuntimePaths.DataDirectory,"broadcasts"),found);
  items=new List<BroadcastProject>(found.Values);items.Sort((a,b)=>String.CompareOrdinal(a.id,b.id));return items;
 }
 static void Read(string dir,Dictionary<string,BroadcastProject> found){if(!Directory.Exists(dir))return;
  string[] files;try{files=Directory.GetFiles(dir,"*.json");}
  catch(Exception error){MiDiagnostics.Report("MI-BROADCAST-DIRECTORY","CreatorBroadcastCatalog.Read",error,dir);return;}
  foreach(string file in files)try{
   var p=PearlProjectCodec.ReadObject<BroadcastProject>(Json.Deserialize(File.ReadAllText(file)));
   if(p==null||p.schema!="moreiterators.broadcast.v1"||String.IsNullOrEmpty(p.uid)||p.uid.Length!=32||p.runtimeId!="MoreIterators_Broadcast_"+p.uid||p.pages==null||p.pages.Length==0)throw new InvalidDataException("Unsupported broadcast schema, runtime identity or page list.");
   found[p.runtimeId]=p;new ChatlogData.ChatlogID(p.runtimeId,true);
  }catch(FileNotFoundException){/* The editor may remove a file after enumeration. */}
  catch(Exception error){MiDiagnostics.Report("MI-BROADCAST-DATA","CreatorBroadcastCatalog.Read",error,file);}
 }
 public static BroadcastProject Find(string id){return All().Find(p=>p.runtimeId==id);}
}
public static class CreatorBroadcastRuntime {
 sealed class RoomState {public Dictionary<string,CollectToken> tokens=new Dictionary<string,CollectToken>();public Dictionary<string,int> revisions=new Dictionary<string,int>();public float next;}
 sealed class Session {public HashSet<string> collected=new HashSet<string>();}
 static readonly ConditionalWeakTable<Room,RoomState> rooms=new ConditionalWeakTable<Room,RoomState>();
 static readonly ConditionalWeakTable<RainWorldGame,Session> sessions=new ConditionalWeakTable<RainWorldGame,Session>();
 public static void Tick(Room room){if(!ModManager.MSC||room.game==null||!room.game.IsStorySession)return;
  var state=rooms.GetOrCreateValue(room);if(Time.realtimeSinceStartup<state.next)return;state.next=Time.realtimeSinceStartup+1;
  var wanted=new HashSet<string>();
  foreach(var p in CreatorBroadcastCatalog.All())if(p.room==room.abstractRoom.name){
   wanted.Add(p.runtimeId);int revision;CollectToken previous;
   bool changed=state.revisions.TryGetValue(p.runtimeId,out revision)&&revision!=p.revision;
   if(changed){if(state.tokens.TryGetValue(p.runtimeId,out previous)){previous.stalk.Destroy();previous.Destroy();state.tokens.Remove(p.runtimeId);}sessions.GetOrCreateValue(room.game).collected.Remove(p.runtimeId);}
   state.revisions[p.runtimeId]=p.revision;
   if(state.tokens.ContainsKey(p.runtimeId)||sessions.GetOrCreateValue(room.game).collected.Contains(p.runtimeId))continue;
   var placed=new PlacedObject(MoreSlugcatsEnums.PlacedObjectType.WhiteToken,null);
   var data=new CollectToken.CollectTokenData(placed,false);data.isWhite=true;data.tokenString=p.runtimeId;data.handlePos=new Vector2(0,-30);placed.data=data;
   placed.pos=new Vector2(Mathf.Clamp01(p.x)*room.PixelWidth,Mathf.Clamp01(p.y)*room.PixelHeight);
   var token=new CollectToken(room,placed);state.tokens[p.runtimeId]=token;room.AddObject(token);
   Debug.Log("[More Iterators broadcast] "+p.id+" placed in "+p.room+" at "+placed.pos);
  }
  var remove=new List<string>();foreach(var pair in state.tokens)if(!wanted.Contains(pair.Key)){pair.Value.stalk.Destroy();pair.Value.Destroy();remove.Add(pair.Key);}foreach(string key in remove)state.tokens.Remove(key);
 }
 public static void Process(On.Player.orig_ProcessChatLog orig,Player player){
  var p=player.chatlogID==null?null:CreatorBroadcastCatalog.Find(player.chatlogID.value);
  if(p==null){orig(player);return;}if(!player.chatlog||player.room==null)return;
  var game=player.room.game;var hud=game.cameras[0].hud;if(hud==null)return;
  player.mushroomCounter=25;player.Stun(25);foreach(var other in game.Players)if(other.realizedCreature!=null&&other.realizedCreature!=player)other.realizedCreature.Stun(20);
  player.chatlogCounter++;
  if(player.chatlogCounter>=60&&hud.chatLog==null){
   if(player.chatlogCounter==60){hud.chatLog=new CreatorBroadcastDisplay(hud,p);hud.parts.Add(hud.chatLog);sessions.GetOrCreateValue(game).collected.Add(p.runtimeId);}
   else{player.chatlog=false;Debug.Log("[More Iterators broadcast] Finished "+p.id);}
  }
 }
}
}
