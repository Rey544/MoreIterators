namespace MoreIterators {
using System;
using System.IO;
using System.Collections.Generic;
using System.Runtime.CompilerServices;
using UnityEngine;

[Serializable] public sealed class PearlAppearance {
 public string baseColor="#000000",highlightColor="#b0d8f0",secondaryColor="#365576",effect="none",effectColor="#88bbff";
 public AudioTrackDesign musicTrack=new AudioTrackDesign();
 public bool twoTone,music;public float size=1,effectOpacity=.4f,effectSize=28,pulseSpeed=1,musicVolume=.16f;
}
[Serializable] public sealed class PearlVariant {public string name="";public CreatorDialogueLine[] lines=new CreatorDialogueLine[0];public CreatorGroupAction action=new CreatorGroupAction();}
[Serializable] public class PearlReaderBody {
 public CreatorReadingPresentationOptions presentation=new CreatorReadingPresentationOptions();
 public CreatorDialogueLine[] read=new CreatorDialogueLine[0];public CreatorGroupAction readAction=new CreatorGroupAction();
 public bool repeatEnabled,repeatPrependCommon;public PearlVariant[] repeat=new PearlVariant[0];
}
[Serializable] public sealed class PearlReaderAffinity {
 public PearlReaderBody notSpeaking,dislikes,neutral,likes;
 public PearlReaderBody For(string tier){return tier=="notSpeaking"?notSpeaking:tier=="dislikes"?dislikes:tier=="neutral"?neutral:tier=="likes"?likes:null;}
}
[Serializable] public sealed class PearlReaderProfile:PearlReaderBody {
 public string projectId="",oracleId="",name="",leavePolicy="resume";public bool requireMark=true;public int manyThreshold=3;
 public PearlReaderAffinity affinity;
 public PearlVariant[] leaving=new PearlVariant[0],returning=new PearlVariant[0],many=new PearlVariant[0];
 public PearlReaderBody Select(string tier){return affinity==null?this:affinity.For(tier)??this;}
}
[Serializable] public sealed class PearlSpawnPosition {public float x,y;}
[Serializable] public sealed class PearlSpawn {public string projectId="",entry="";public PearlSpawnPosition position;}
[Serializable] public sealed class PearlProject {
 public string schema="",id="",uid="",runtimeId="",name="",ownerMod="",collectionId="legacy";public int revision;
 public PearlAppearance appearance=new PearlAppearance();public PearlReaderProfile[] readers=new PearlReaderProfile[0];public PearlSpawn[] spawns=new PearlSpawn[0];
 public PearlReaderProfile Reader(string project){return Array.Find(readers,r=>r.projectId==project);}
}
// Read nested arrays explicitly: the game's Unity serializer can omit mod-defined
// nested types. This follows the same dictionary format as the design loader.
public static class PearlProjectCodec {
 public static PearlProject Read(Dictionary<string,object> data){return (PearlProject)Value(typeof(PearlProject),data);}
 public static T ReadObject<T>(object data){return (T)Value(typeof(T),data);}
 static object Value(Type type,object value){
  if(type.IsArray){var list=value as System.Collections.IList;if(list==null)throw new FormatException("Expected pearl array");Type item=type.GetElementType();var array=Array.CreateInstance(item,list.Count);for(int i=0;i<list.Count;i++)array.SetValue(Value(item,list[i]),i);return array;}
  if(type==typeof(string)||type.IsPrimitive)return Convert.ChangeType(value,type,System.Globalization.CultureInfo.InvariantCulture);
  var data=value as Dictionary<string,object>;if(data==null)throw new FormatException("Expected pearl object");object result=Activator.CreateInstance(type);
  foreach(var field in type.GetFields(System.Reflection.BindingFlags.Public|System.Reflection.BindingFlags.Instance)){object raw;if(data.TryGetValue(field.Name,out raw))field.SetValue(result,Value(field.FieldType,raw));}return result;
 }
}
public static class CreatorPearlCatalog {
 static float next;static List<PearlProject> items=new List<PearlProject>();
 public static string Root{get{return Path.Combine(RuntimePaths.DataDirectory,"pearls");}}
 public static List<PearlProject> All(){
  if(ModManager.ActiveMods==null)return items;
  if(Time.realtimeSinceStartup<next)return items;next=PlaybackMode.Enabled?float.MaxValue:Time.realtimeSinceStartup+.75f;
  var found=new Dictionary<string,PearlProject>();
  foreach(var mod in ModManager.ActiveMods)if(!PlaybackMode.Enabled||mod.id==RuntimePaths.ModId){
#if !PLAYBACK
   if(RuntimePaths.HasIndependentRuntime(mod.path))continue;
#endif
   ReadDirectory(Path.Combine(mod.path,"moreiterators/pearls"),found,mod.id);
  }
  if(!PlaybackMode.Enabled&&!CreatorPearlCollection.Merge(found))ReadDirectory(Root,found);items=new List<PearlProject>(found.Values);items.Sort((a,b)=>String.CompareOrdinal(a.id,b.id));return items;
 }
 static void ReadDirectory(string dir,Dictionary<string,PearlProject> found,string owner=""){
  if(!Directory.Exists(dir))return;
  string[] files;
  try{files=Directory.GetFiles(dir,"*.json");}
  catch(Exception error){MiDiagnostics.Report("MI-PEARL-DIRECTORY","CreatorPearlCatalog.ReadDirectory",error,dir);return;}
  foreach(string file in files){if(Path.GetFileName(file)=="spawn-request.json")continue;
   try{var p=PearlProjectCodec.Read(Json.Deserialize(File.ReadAllText(file)) as Dictionary<string,object>);if(p==null||p.schema!="moreiterators.pearl.v1"||String.IsNullOrEmpty(p.uid)||p.runtimeId!="MoreIterators_"+p.uid||p.uid.Length!=32)throw new InvalidDataException("Unsupported pearl schema or runtime identity.");
    if(owner!="")p.ownerMod=owner;
    if(p.readers==null)p.readers=new PearlReaderProfile[0];if(p.spawns==null)p.spawns=new PearlSpawn[0];found[p.runtimeId]=p;
    new DataPearl.AbstractDataPearl.DataPearlType(p.runtimeId,true);
   }catch(FileNotFoundException){/* The editor may remove a file after enumeration. */}
   catch(Exception error){MiDiagnostics.Report("MI-PEARL-DATA","CreatorPearlCatalog.ReadDirectory",error,file);}
  }
 }
 public static PearlProject Find(string runtimeId){return All().Find(p=>p.runtimeId==runtimeId);}
}
public static class CreatorPearlRuntime {
 sealed class SpawnState {public HashSet<string> spawned=new HashSet<string>();public Dictionary<string,string> requests=new Dictionary<string,string>();public float next;public string collection="";}
 static readonly ConditionalWeakTable<RainWorldGame,SpawnState> sessions=new ConditionalWeakTable<RainWorldGame,SpawnState>();
 internal static void ReadSpawnRequest(out string uid,out string nonce){
  uid=nonce="";if(PlaybackMode.Enabled)return;
  string file=Path.Combine(CreatorPearlCatalog.Root,"spawn-request.json");
  if(!File.Exists(file))return;
  try{
   var request=Json.Deserialize(File.ReadAllText(file)) as Dictionary<string,object>;object rawUid,rawNonce;
   if(request==null||!request.TryGetValue("uid",out rawUid)||!(rawUid is string)||((string)rawUid).Length!=32||!request.TryGetValue("nonce",out rawNonce)||!(rawNonce is string)||String.IsNullOrEmpty((string)rawNonce))throw new InvalidDataException("Pearl spawn request requires a valid uid and nonce.");
   uid=(string)rawUid;nonce=(string)rawNonce;
  }catch(FileNotFoundException){/* Optional request was removed between checking and reading. */}
  catch(DirectoryNotFoundException){/* Optional local preview directory was removed. */}
  catch(Exception error){MiDiagnostics.Report("MI-PEARL-SPAWN-REQUEST","CreatorPearlRuntime.ReadSpawnRequest",error,file);}
 }
 public static void Ready(Room room){if(room==null||room.game==null||room.abstractRoom==null)return;string name=room.abstractRoom.name;if(IteratorCatalog.OwnsEntry(name))room.gravity=0;Spawn(room);}
 public static void Tick(RainWorldGame game){
  var state=sessions.GetOrCreateValue(game);foreach(var cam in game.cameras){var room=cam.room;if(room!=null&&IteratorCatalog.OwnsEntry(room.abstractRoom.name))room.gravity=0;}
  if(Time.realtimeSinceStartup<state.next)return;state.next=Time.realtimeSinceStartup+.8f;
  CreatorPearlCatalog.All();
  if(state.collection!=CreatorPearlCollection.Generation&&game.world!=null){
   // Replacing local content must not reset installed content's spawn history,
   // or duplicate active pearls already carried away from the entry room.
   state.spawned.RemoveWhere(CreatorPearlCollection.RetiredSpawnKey);
   foreach(string key in new List<string>(state.requests.Keys))if(CreatorPearlCollection.RetiredSpawnKey(key))state.requests.Remove(key);
   CreatorPearlCollection.RemoveInactive(game);state.collection=CreatorPearlCollection.Generation;
  }
  foreach(var cam in game.cameras){var room=cam.room;if(room!=null)Ready(room);}
 }
 static void Spawn(Room room){
  var session=sessions.GetOrCreateValue(room.game);string uid="",nonce="";
  ReadSpawnRequest(out uid,out nonce);
  int index=0;foreach(var p in CreatorPearlCatalog.All()){
   var spawn=Array.Find(p.spawns,s=>s.entry==room.abstractRoom.name);if(spawn==null)continue;
   string key=room.abstractRoom.name+":"+p.uid,previous;bool refresh=p.uid==uid&&CreatorPearlCollection.AllowsSpawnRequest(p)&&(!session.requests.TryGetValue(key,out previous)||previous!=nonce);
   if(session.spawned.Contains(key)&&!refresh)continue;
   session.spawned.Add(key);if(refresh)session.requests[key]=nonce;
   bool exists=false;foreach(var a in room.abstractRoom.entities){var pearl=a as DataPearl.AbstractDataPearl;if(pearl!=null&&pearl.dataPearlType.value==p.runtimeId){exists=true;break;}}
   if(exists)continue;
   Vector2 pos;
   if(spawn.position!=null){
    float px,py;if(!CreatorPearlPlacement.TryPosition(spawn.position.x,spawn.position.y,room.PixelWidth,room.PixelHeight,5*p.appearance.size,out px,out py)){Debug.LogWarning("[More Iterators pearl] Spawn position outside room bounds: "+p.id);continue;}
    pos=new Vector2(px,py);if(room.GetTile(pos).Solid){Debug.LogWarning("[More Iterators pearl] Spawn position is inside solid terrain: "+p.id);continue;}
   }else{
    pos=new Vector2(room.PixelWidth*.5f+(index++%8-3)*18,room.PixelHeight*.5f);
    if(room.GetTile(pos).Solid){Vector2 origin=pos;float best=float.MaxValue;for(int x=2;x<room.TileWidth-2;x++)for(int y=2;y<room.TileHeight-2;y++)if(!room.GetTile(x,y).Solid){Vector2 q=room.MiddleOfTile(x,y);float dist=Vector2.SqrMagnitude(q-origin);if(dist<best){best=dist;pos=q;}}}
   }
   CreatorDataPearl.Create(room,pos,p);Debug.Log("[More Iterators pearl] Spawned "+p.id+" in "+room.abstractRoom.name);
  }
 }
}
public sealed class CreatorDataPearl:DataPearl {
 readonly CreatorAudioChannel customMusic=new CreatorAudioChannel(20);
 readonly string runtimeId;public Vector2? hover;int tick;float beat;bool startedSong;
 public PearlProject Project{get{return CreatorPearlCatalog.Find(runtimeId);}}
 public CreatorDataPearl(AbstractPhysicalObject a,World w):base(a,w){runtimeId=((DataPearl.AbstractDataPearl)a).dataPearlType.value;}
 public static bool Realize(AbstractPhysicalObject a){var p=a as DataPearl.AbstractDataPearl;if(p==null||CreatorPearlCatalog.Find(p.dataPearlType.value)==null)return false;a.realizedObject=new CreatorDataPearl(a,a.world);return true;}
 public static CreatorDataPearl Create(Room room,Vector2 pos,PearlProject p){var a=new DataPearl.AbstractDataPearl(room.world,AbstractPhysicalObject.AbstractObjectType.DataPearl,null,room.GetWorldCoordinate(pos),room.game.GetNewID(),-1,-1,null,new DataPearl.AbstractDataPearl.DataPearlType(p.runtimeId,true));room.abstractRoom.AddEntity(a);a.RealizeInRoom();var pearl=a.realizedObject as CreatorDataPearl;if(pearl!=null)pearl.firstChunk.HardSetPosition(pos);return pearl;}
 public override void Update(bool eu){
  var p=Project;if(p!=null){firstChunk.rad=5*p.appearance.size;color=IteratorDesign.C(p.appearance.baseColor);highlightColor=IteratorDesign.C(p.appearance.highlightColor);}
  if(hover.HasValue&&grabbedBy.Count==0){gravity=0;firstChunk.vel=Vector2.Lerp(firstChunk.vel,Vector2.ClampMagnitude((hover.Value-firstChunk.pos)*.09f,3),.15f);}else gravity=.9f;
  base.Update(eu);tick++;glimmer=lastGlimmer=0;beat=0;
  var player=room==null||room.game==null||room.game.manager==null?null:room.game.manager.musicPlayer;
  bool music=p!=null&&p.appearance.effect=="halcyon"&&p.appearance.music&&hover.HasValue;
  var track=p==null?null:p.appearance.musicTrack;bool native=track==null||track.mode=="native";
  customMusic.Update(room,track,music&&!native);
  if(music&&!native)beat=.5f+.5f*Mathf.Sin(tick*.06f);
  if(music&&native&&player!=null&&ModManager.MSC){if(!startedSong){if(player.song==null){player.RequestHalcyonSong("NA_19 - Halcyon Memories");startedSong=true;}}if(startedSong&&player.song is MoreSlugcats.HalcyonSong){((MoreSlugcats.HalcyonSong)player.song).setVolume=p.appearance.musicVolume;beat=.5f+.5f*Mathf.Sin(tick*.06f);}}
  else if(startedSong){if(player!=null&&player.song is MoreSlugcats.HalcyonSong)player.song.FadeOut(80);startedSong=false;}
 }
 public override void Destroy(){customMusic.Stop();base.Destroy();}
 public override void InitiateSprites(RoomCamera.SpriteLeaser s,RoomCamera cam){base.InitiateSprites(s,cam);Array.Resize(ref s.sprites,5);s.sprites[3]=new FSprite("JetFishEyeA");s.sprites[4]=new FSprite("Futile_White");s.sprites[4].shader=cam.game.rainWorld.Shaders["VectorCircle"];cam.ReturnFContainer("Items").AddChild(s.sprites[3]);s.sprites[3].MoveBehindOtherNode(s.sprites[1]);cam.ReturnFContainer("ForegroundLights").AddChild(s.sprites[4]);}
 public override void DrawSprites(RoomCamera.SpriteLeaser s,RoomCamera cam,float t,Vector2 camera){base.DrawSprites(s,cam,t,camera);var p=Project;if(p==null||slatedForDeletetion||room!=cam.room)return;var a=p.appearance;Vector2 pos=Vector2.Lerp(firstChunk.lastPos,firstChunk.pos,t)-camera;
  Color body=IteratorDesign.C(a.baseColor);if(body==Color.black)body.g=1f/255;s.sprites[0].color=body;s.sprites[0].scale=a.size;s.sprites[1].color=IteratorDesign.C(a.highlightColor);s.sprites[1].scale=a.size;
  var secondary=s.sprites[3];secondary.isVisible=a.twoTone;secondary.color=IteratorDesign.C(a.secondaryColor);secondary.scale=a.size*.6f;secondary.SetPosition(pos+new Vector2(1,-1)*a.size);
  float pulse=.5f+.5f*Mathf.Sin((tick+t)*.05f*a.pulseSpeed);var glow=s.sprites[2];glow.color=IteratorDesign.C(a.effectColor);glow.scale=a.effectSize/16f;glow.alpha=a.effect=="none"?0:a.effectOpacity*(a.effect=="glow"?1:.55f+.45f*pulse);
  var ring=s.sprites[4];ring.isVisible=a.effect=="pulse"||a.effect=="halcyon";ring.SetPosition(pos);ring.color=IteratorDesign.C(a.effectColor);ring.scale=a.effectSize*(.55f+((tick+t)*a.pulseSpeed/100f%1f)+beat*.1f)/8f;ring.alpha=a.effectOpacity*(1-((tick+t)*a.pulseSpeed/100f%1f));
 }
}
}
