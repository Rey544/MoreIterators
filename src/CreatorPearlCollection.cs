namespace MoreIterators {
using System;
using System.IO;
using System.Collections.Generic;
using System.Security.Cryptography;
using System.Text;
using UnityEngine;

// A local authoring collection is published as one generation. Content mods
// retain their own catalogs and never participate in this local switch.
internal static class CreatorPearlCollection {
 static string generation="";
 static float pendingSince=-1;
 static Dictionary<string,PearlProject> cached=new Dictionary<string,PearlProject>();
 static HashSet<string> retired=new HashSet<string>();
 static HashSet<string> contentIds=new HashSet<string>();
 internal static string Generation{get{return generation;}}
 internal static bool Merge(Dictionary<string,PearlProject> destination){
#if PLAYBACK
  return false;
#else
  string marker=Path.Combine(RuntimePaths.DataDirectory,"pearl-project.json");
  contentIds=new HashSet<string>(destination.Keys);
  if(!File.Exists(marker)&&generation.Length==0)return false;
  try{
   var data=Json.Deserialize(File.ReadAllText(marker)) as Dictionary<string,object>;
   if(data==null||Text(data,"schema")!="moreiterators.pearl-runtime.v1")throw new InvalidDataException("Invalid local pearl collection manifest.");
   string next=Text(data,"generation"),collection=Text(data,"collectionId");
   if(!Uid(next)||(collection!="legacy"&&!Uid(collection)))throw new InvalidDataException("Invalid pearl collection identity.");
   // The publisher replaces files before committing its new manifest. Never
   // inspect those files again under a generation we already accepted.
   if(next==generation){pendingSince=-1;MergeCached(destination);return true;}
   object raw;var files=data.TryGetValue("files",out raw)?raw as System.Collections.IList:null;
   if(files==null)throw new InvalidDataException("Pearl collection manifest has no file list.");
   var loaded=new Dictionary<string,PearlProject>();var names=new HashSet<string>();
   foreach(object entry in files){
    var item=entry as Dictionary<string,object>;if(item==null)throw new InvalidDataException("Invalid pearl collection entry.");
    string name=Text(item,"name"),uid=Text(item,"uid"),digest=Text(item,"sha256");
    if(!Uid(uid)||!System.Text.RegularExpressions.Regex.IsMatch(name,"^[A-Z]{1,4}[0-9]{2,4}\\.json$")||!names.Add(name)||!System.Text.RegularExpressions.Regex.IsMatch(digest,"^[a-fA-F0-9]{64}$"))throw new InvalidDataException("Invalid pearl collection file identity or SHA256.");
    byte[] bytes=File.ReadAllBytes(Path.Combine(CreatorPearlCatalog.Root,name));
    string actual;using(var sha=SHA256.Create())actual=BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-","");
    if(!String.Equals(actual,digest,StringComparison.OrdinalIgnoreCase))throw new InvalidDataException("Pearl collection file does not match its published SHA256: "+name);
    var pearl=PearlProjectCodec.Read(Json.Deserialize(Encoding.UTF8.GetString(bytes)) as Dictionary<string,object>);
    if(pearl==null||pearl.schema!="moreiterators.pearl.v1"||pearl.uid!=uid||pearl.id+".json"!=name||pearl.runtimeId!="MoreIterators_"+uid||pearl.collectionId!=collection||loaded.ContainsKey(pearl.runtimeId))throw new InvalidDataException("Pearl collection files do not match the published generation.");
    loaded.Add(pearl.runtimeId,pearl);
   }
   var removed=new HashSet<string>();
   var retiredIds=data.TryGetValue("retiredUids",out raw)?raw as System.Collections.IList:null;
   if(retiredIds!=null)foreach(object value in retiredIds){string uid=value as string;if(!Uid(uid))throw new InvalidDataException("Invalid retired pearl identity.");if(!loaded.ContainsKey("MoreIterators_"+uid))removed.Add("MoreIterators_"+uid);}
   foreach(string id in cached.Keys)if(!loaded.ContainsKey(id))removed.Add(id);
   cached=loaded;retired=removed;generation=next;pendingSince=-1;
  }catch(Exception error){
   // Publishing replaces the files before the manifest; keep the last complete
   // generation during that short interval and report a sustained mismatch.
   if(pendingSince<0)pendingSince=Time.realtimeSinceStartup;
   if(Time.realtimeSinceStartup-pendingSince>3)MiDiagnostics.Report("MI-PEARL-COLLECTION","CreatorPearlCollection.Merge",error,marker);
  }
  MergeCached(destination);
  return true;
#endif
 }
 static void MergeCached(Dictionary<string,PearlProject> destination){
  foreach(var pair in cached){
   if(contentIds.Contains(pair.Key)){MiDiagnostics.Warn("MI-PEARL-OWNER-CONFLICT","CreatorPearlCollection.Merge","Local pearl UID conflicts with installed content; the content pearl was retained.",pair.Key+" owner="+destination[pair.Key].ownerMod);continue;}
   destination[pair.Key]=pair.Value;new DataPearl.AbstractDataPearl.DataPearlType(pair.Key,true);
  }
 }
 static string Text(Dictionary<string,object> value,string key){object raw;return value.TryGetValue(key,out raw)?raw as string??"":"";}
 static bool Uid(string value){return value!=null&&System.Text.RegularExpressions.Regex.IsMatch(value,"^[a-f0-9]{32}$");}
 internal static bool RetiredSpawnKey(string key){int split=key.LastIndexOf(':');string id="MoreIterators_"+key.Substring(split+1);return retired.Contains(id)&&!contentIds.Contains(id);}
 internal static bool AllowsSpawnRequest(PearlProject pearl){return generation.Length==0?String.IsNullOrEmpty(pearl.ownerMod):cached.ContainsKey(pearl.runtimeId)&&!contentIds.Contains(pearl.runtimeId);}
 static bool Retired(AbstractPhysicalObject value){var pearl=value as DataPearl.AbstractDataPearl;return pearl!=null&&retired.Contains(pearl.dataPearlType.value)&&!contentIds.Contains(pearl.dataPearlType.value);}
 internal static void RemoveInactive(RainWorldGame game){
#if !PLAYBACK
  if(game==null||game.world==null||retired.Count==0)return;
  // Remove only known local preview pearls from the inactive collection.
  // Vanilla pearls, work pearls and separately installed content stay intact.
  foreach(var player in game.Players){var realized=player.realizedCreature as Player;if(realized!=null&&Retired(realized.objectInStomach))realized.objectInStomach=null;}
  foreach(var room in game.world.abstractRooms){
   if(room==null)continue;
   for(int i=room.entities.Count-1;i>=0;i--){
    var pearl=room.entities[i] as AbstractPhysicalObject;if(!Retired(pearl))continue;
    var realized=pearl.realizedObject;
    if(realized!=null){for(int n=realized.grabbedBy.Count-1;n>=0;n--){var grasp=realized.grabbedBy[n];grasp.grabber.ReleaseGrasp(grasp.graspUsed);}realized.Destroy();}
    room.RemoveEntity(pearl);
   }
  }
#endif
 }
}
}
