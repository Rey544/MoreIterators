using System;
using System.IO;
using System.Collections.Generic;
using UnityEngine;

namespace MoreIterators {
 public static class RuntimePaths {
  public const string ModId="moreiterators.core";
  static string directory;
  public static string DataDirectory {get{if(directory==null)Initialize();return directory;}}
  public static bool HasIndependentRuntime(string modPath){
   string manifest=Path.Combine(modPath,"content-manifest.json");
   if(!File.Exists(manifest))return false;
   try{
    var data=Json.Deserialize(File.ReadAllText(manifest)) as Dictionary<string,object>;object value;
    // Ordinary register packs remain shared content unless ownership is explicit.
    return data!=null&&data.TryGetValue("independentMod",out value)&&value is bool&&(bool)value;
   }catch{return false;}
  }
  public static void Initialize(){
   if(directory!=null)return;
   directory=Path.Combine(Application.persistentDataPath,"MoreIterators/data/runtime");
   string config=Path.Combine(BepInEx.Paths.ConfigPath,"moreiterators.paths.json");
   if(File.Exists(config))try{
    var data=Json.Deserialize(File.ReadAllText(config)) as Dictionary<string,object>;object value;
    if(data!=null&&data.TryGetValue("runtimeDirectory",out value)&&value is string&&Path.IsPathRooted((string)value))directory=Path.GetFullPath((string)value);
   }catch(Exception e){MiDiagnostics.Report("MI_PATH_CONFIG_READ","RuntimePaths.Initialize",e,config);Debug.LogWarning("[More Iterators] Local path config: "+e.Message);}
   Directory.CreateDirectory(Path.Combine(directory,"creator"));
  }
  public static string DesignPath(string id){
   if(String.IsNullOrEmpty(id)||id.IndexOfAny(Path.GetInvalidFileNameChars())>=0||id.Contains(".."))throw new ArgumentException("Invalid iterator id");
   foreach(var item in IteratorCatalog.Projects())if(IteratorCatalog.Text(item,"oracleId")==id){
    string mod=IteratorCatalog.Text(item,"ownerMod"),path=IteratorCatalog.Text(item,"design");
    if(!String.IsNullOrEmpty(path))foreach(var active in ModManager.ActiveMods)if(active.id==mod){
     string root=Path.GetFullPath(active.path)+Path.DirectorySeparatorChar;
     string file=Path.GetFullPath(Path.Combine(root,path));
     if(!file.StartsWith(root,StringComparison.OrdinalIgnoreCase))throw new InvalidOperationException("Design escaped its content mod");
     return file;
    }
   }
   return Path.Combine(DataDirectory,id+".json");
  }
 }

 public static class IteratorCatalog {
  static float nextRead;
  static List<Dictionary<string,object>> projects=new List<Dictionary<string,object>>();
  public static string Text(Dictionary<string,object> data,string key){object value;return data.TryGetValue(key,out value)&&value is string?(string)value:"";}
  public static List<Dictionary<string,object>> Projects(){
   if(Time.realtimeSinceStartup<nextRead)return projects;nextRead=Time.realtimeSinceStartup+.5f;
   var result=new Dictionary<string,Dictionary<string,object>>();
   foreach(var mod in ModManager.ActiveMods)if(!RuntimePaths.HasIndependentRuntime(mod.path))Read(Path.Combine(mod.path,"moreiterators/registry.json"),mod.id,result);
   Read(Path.Combine(RuntimePaths.DataDirectory,"creator/registry.json"),null,result);
   projects=new List<Dictionary<string,object>>(result.Values);
   projects.Sort((a,b)=>String.CompareOrdinal(Text(a,"projectId"),Text(b,"projectId")));return projects;
  }
  public static bool OwnerEnabled(string id){
   if(ModManager.ActiveMods==null)return false;
   foreach(var active in ModManager.ActiveMods)if(active.id==id)return !RuntimePaths.HasIndependentRuntime(active.path);
   return false;
  }
  // Editor/menu-only discoverability. Inactive local projects must never enter
  // Projects(), Find(), or room ownership while their world assets are disabled.
  public static List<Dictionary<string,object>> PendingLocalProjects(){
   var result=new Dictionary<string,Dictionary<string,object>>();
   Read(Path.Combine(RuntimePaths.DataDirectory,"creator/registry.json"),null,result,true);
   var pending=new List<Dictionary<string,object>>();
   foreach(var item in result.Values)if(Text(item,"ownerMod")=="moreiterators.local"&&!OwnerEnabled("moreiterators.local"))pending.Add(item);
   pending.Sort((a,b)=>String.CompareOrdinal(Text(a,"projectId"),Text(b,"projectId")));return pending;
  }
  static void Read(string file,string owner,Dictionary<string,Dictionary<string,object>> result,bool includePendingLocal=false){
   if(!File.Exists(file))return;
   try{
    var list=Json.Deserialize(File.ReadAllText(file)) as List<object>;if(list==null)return;
    foreach(var entry in list){var item=entry as Dictionary<string,object>;if(item==null)continue;
     if(owner!=null)item["ownerMod"]=owner;
     string mod=Text(item,"ownerMod");bool enabled=OwnerEnabled(mod);
     if((!enabled&&!(includePendingLocal&&mod=="moreiterators.local"))||Text(item,"projectId")==""||Text(item,"ai")==""||Text(item,"entry")==""||Text(item,"oracleId")=="")continue;
     // Normalize once so direct menu indexing and Text() share a string fallback.
     if(String.IsNullOrWhiteSpace(Text(item,"name"))){item["name"]=Text(item,"projectId");MiDiagnostics.Warn("MI_REGISTRY_NAME_FALLBACK","IteratorCatalog.Read","Missing or invalid display name; using project ID.",file+"; project="+Text(item,"projectId"));}
     result[Text(item,"projectId")]=item;
    }
   }catch(Exception e){MiDiagnostics.Report("MI_REGISTRY_READ","IteratorCatalog.Read",e,file);Debug.LogWarning("[More Iterators] Invalid registry "+file+": "+e.Message);}
  }
  public static Dictionary<string,object> Find(string room){if(room==null)return null;var all=Projects();return all.Find(p=>Text(p,"ai")==room)??all.Find(p=>Text(p,"entry")==room&&OwnsEntry(p))??all.Find(p=>Text(p,"entry")==room);}
  static bool OwnsEntry(Dictionary<string,object> project){object raw;var binding=project.TryGetValue("roomBinding",out raw)?raw as Dictionary<string,object>:null;return Text(project,"nativeOracle")==""&&(binding==null||Text(binding,"entryMode")!="existing");}
  public static bool IsEntry(string room){return room!=null&&Projects().Exists(p=>Text(p,"entry")==room);}
  public static bool OwnsEntry(string room){return room!=null&&Projects().Exists(p=>Text(p,"entry")==room&&OwnsEntry(p)&&NativeRoomProjects.Available(p));}
  public static bool OwnsRoom(string room){return IsAI(room)||OwnsEntry(room);}
  public static string Id(string room){var project=Find(room);return project==null?"default":Text(project,"oracleId");}
  public static bool IsAI(string room){var project=Find(room);return project!=null&&NativeRoomProjects.Available(project)&&Text(project,"ai")==room;}
  public static bool IsGenericRoom(string room){var project=Find(room);return project!=null&&OwnsRoom(room)&&NativeRoomProjects.Available(project)&&!IteratorIntegrations.Native(Text(project,"oracleId"));}
 }
}
