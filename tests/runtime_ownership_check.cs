using System;
using System.IO;
using System.Collections.Generic;
using MoreIterators;
using MoreSlugcats;

 
 
public static class ModManager {
 public class Mod {public string id,path,TargetedPath,NewestPath;public bool hasTargetedVersionFolder,hasNewestFolder;public Mod(string id,string path){this.id=id;this.path=path;}}
 public static List<Mod> ActiveMods=new List<Mod>();
}
namespace UnityEngine {
 public static class Application {public static string persistentDataPath;}
 public static class Time {public static float realtimeSinceStartup=1;}
 public static class Debug {public static void LogWarning(object value){Console.WriteLine(value);}}
}
namespace BepInEx {public static class Paths {public static string ConfigPath;}}
namespace MoreIterators {
 public static class CreatorPearlCollection {public static bool Merge(Dictionary<string,PearlProject> destination){return false;}}
 public static class MiDiagnostics {
  public static void Report(string code,string node,Exception error,string context){}
  public static void Warn(string code,string node,string detail,string context){}
 }
 public sealed class CreatorDialogueLine {public string text;}
 public static class IteratorIntegrations {public static bool Native(string id){return false;}}
 public static class NativeRoomProjects {public static bool Available(Dictionary<string,object> p){return true;}}
}
public class DataPearl {
 public class AbstractDataPearl {
  public class DataPearlType {
   public static readonly List<string> Registered=new List<string>();
   public DataPearlType(string id,bool register){if(register)Registered.Add(id);}
  }
 }
}
namespace MoreSlugcats {public class ChatlogData {
 public class ChatlogID {
  public static readonly List<string> Registered=new List<string>();
  public ChatlogID(string id,bool register){if(register)Registered.Add(id);}
 }
}}

public static class RuntimeOwnershipCheck {
 static int count;
 static void Check(bool value,string label){if(!value)throw new Exception(label);count++;}
 static string Record(string id,string owner){return "{\"projectId\":\""+id+"\",\"name\":\""+id+"\",\"ai\":\""+id+"_AI\",\"entry\":\""+id+"_ENTRY\",\"oracleId\":\""+id+"\",\"ownerMod\":\""+owner+"\"}";}
 static void Write(string path,string text){Directory.CreateDirectory(Path.GetDirectoryName(path));File.WriteAllText(path,text);}
 static void Package(string root,string id,char key,string manifest){
  string folder=Path.Combine(root,id),uid=new string(key,32);
  Write(Path.Combine(folder,"moreiterators/registry.json"),"["+Record(id,id)+"]");
  Write(Path.Combine(folder,"moreiterators/pearls/pearl.json"),"{\"schema\":\"moreiterators.pearl.v1\",\"id\":\""+id+"\",\"uid\":\""+uid+"\",\"runtimeId\":\"MoreIterators_"+uid+"\"}");
  Write(Path.Combine(folder,"moreiterators/broadcasts/broadcast.json"),"{\"schema\":\"moreiterators.broadcast.v1\",\"id\":\""+id+"\",\"uid\":\""+uid+"\",\"runtimeId\":\"MoreIterators_Broadcast_"+uid+"\",\"pages\":[{}]}");
  if(manifest!=null)Write(Path.Combine(folder,"content-manifest.json"),manifest);
  ModManager.ActiveMods.Add(new ModManager.Mod(id,folder));
 }
 static void Catalogues(int expected){
  Check(IteratorCatalog.Projects().Count==expected,"expected registry count");
  Check(CreatorPearlCatalog.All().Count==expected,"expected pearl count");
  Check(CreatorBroadcastCatalog.All().Count==expected,"expected broadcast count");
  Check(DataPearl.AbstractDataPearl.DataPearlType.Registered.Count==expected,"excluded pearls never register enum IDs");
  Check(ChatlogData.ChatlogID.Registered.Count==expected,"excluded broadcasts never register enum IDs");
 }
 static int Main(string[] args){try{Run(args);return 0;}catch(Exception e){Console.Error.WriteLine(e.GetType().FullName+": "+e.Message);return 1;}}
 static void Run(string[] args){
  string root=args[1];AssetManager.Root=Path.Combine(root,"assets");Directory.CreateDirectory(AssetManager.Root);UnityEngine.Application.persistentDataPath=Path.Combine(root,"userdata");BepInEx.Paths.ConfigPath=Path.Combine(root,"config");
  Package(root,"standalone",'a',"{\"schema\":\"moreiterators.playback-export.v1\",\"independentMod\":true}");
  Package(root,"registered",'b',null);
  Package(root,"declared-shared",'c',"{\"independentMod\":false}");
  switch(args[0]){
   case "catalogues":
#if PLAYBACK
    Catalogues(1);Check(IteratorCatalog.Find("standalone_AI")!=null,"playback owns its registry");
    Check(CreatorPearlCatalog.All()[0].id=="standalone"&&CreatorBroadcastCatalog.All()[0].id=="standalone","playback owns its pearl and broadcast catalogues");
    Check(IteratorCatalog.Find("registered_AI")==null,"playback does not consume shared content");
#else
    Catalogues(2);Check(IteratorCatalog.Find("standalone_AI")==null,"MI does not own the standalone room");
    Check(IteratorCatalog.Find("registered_AI")!=null&&IteratorCatalog.Find("declared-shared_AI")!=null,"ordinary register packages remain available");
    Check(CreatorPearlCatalog.All().Find(p=>p.id=="standalone")==null,"MI excludes standalone pearl data");
    Check(CreatorBroadcastCatalog.All().Find(p=>p.id=="standalone")==null,"MI excludes standalone broadcast data");
#endif
    break;
#if !PLAYBACK
   case "pending":
    string localRegistry=Path.Combine(RuntimePaths.DataDirectory,"creator/registry.json");
    Write(localRegistry,"["+Record("local-preview","moreiterators.local")+","+Record("foreign-disabled","disabled")+","+Record("standalone-copy","standalone")+"]");
    var pending=IteratorCatalog.PendingLocalProjects();Check(pending.Count==1&&IteratorCatalog.Text(pending[0],"projectId")=="local-preview","only applied inactive local projects appear in menu discovery");
    Check(IteratorCatalog.Find("local-preview_AI")==null&&!IteratorCatalog.OwnsRoom("local-preview_AI")&&!IteratorCatalog.OwnsRoom("local-preview_ENTRY"),"inactive local content does not own runtime rooms");Check(!IteratorCatalog.OwnerEnabled("moreiterators.local"),"local owner is disabled");
    ModManager.ActiveMods.Add(new ModManager.Mod("moreiterators.local",Path.Combine(root,"more_iterators_local")));UnityEngine.Time.realtimeSinceStartup+=1;
    Check(IteratorCatalog.PendingLocalProjects().Count==0,"enabled local project no longer appears as pending");Check(IteratorCatalog.Find("local-preview_AI")!=null&&IteratorCatalog.OwnsRoom("local-preview_ENTRY"),"enabled local content enters normal catalogue");
    ModManager.ActiveMods.RemoveAll(m=>m.id=="moreiterators.local");UnityEngine.Time.realtimeSinceStartup+=1;Write(localRegistry,"[]");
    Check(IteratorCatalog.PendingLocalProjects().Count==0&&IteratorCatalog.Find("local-preview_AI")==null,"deleted registration cannot remain in pending or runtime catalogue");break;
   case "local":
    Write(Path.Combine(RuntimePaths.DataDirectory,"creator/registry.json"),"["+Record("reclaimed","standalone")+","+Record("local-shared","registered")+"]");
    Check(IteratorCatalog.Projects().Count==3,"local shared registration supplements ordinary content");
    Check(IteratorCatalog.Find("reclaimed_AI")==null,"local registry cannot reclaim standalone-owned rooms");
    Check(IteratorCatalog.Find("local-shared_AI")!=null,"local registry can still register shared content");break;
   case "metadata":
    Package(root,"malformed",'d',"{broken");Package(root,"string-flag",'e',"{\"independentMod\":\"true\"}");Package(root,"unrelated",'f',"{\"schema\":\"other\"}");
    Catalogues(5);Check(!RuntimePaths.HasIndependentRuntime(Path.Combine(root,"malformed")),"invalid optional metadata does not claim ownership");
    Check(IteratorCatalog.Find("string-flag_AI")!=null,"a string is not the independentMod boolean");
    Check(IteratorCatalog.Find("unrelated_AI")!=null,"unrelated manifests preserve register compatibility");break;
#endif
   default:throw new ArgumentException("Unknown scenario");
  }
  Console.WriteLine(count+" ownership assertions passed: "+args[0]);
 }
}
