using System;
using System.IO;
using System.Collections.Generic;
using UnityEngine;

namespace MoreIterators {
 public static class RuntimePaths {
  public const string ModId="moreiterators.core";
  static string directory;
  sealed class ManifestState {public string path;public long stamp,length;public bool independent;}
  static readonly Dictionary<string,ManifestState> manifests=new Dictionary<string,ManifestState>(StringComparer.OrdinalIgnoreCase);
  static int manifestGeneration=-1;
  public static string DataDirectory {get{if(directory==null)Initialize();return directory;}}
  public static bool HasIndependentRuntime(string modPath){
   int generation=ContentAssets.Generation;
   if(manifestGeneration!=generation){manifests.Clear();manifestGeneration=generation;}
   string manifest=null;
   if(ModManager.ActiveMods!=null)foreach(var mod in ModManager.ActiveMods)if(mod!=null&&mod.enabled&&mod.path==modPath){manifest=ContentAssets.ResolveOwnedFile(mod.id,"content-manifest.json");break;}
   if(!File.Exists(manifest)){manifests.Remove(modPath);return false;}
   try{
    var info=new FileInfo(manifest);ManifestState cached;
    if(manifests.TryGetValue(modPath,out cached)&&cached.path==manifest&&cached.stamp==info.LastWriteTimeUtc.Ticks&&cached.length==info.Length)return cached.independent;
    var data=Json.Deserialize(File.ReadAllText(manifest)) as Dictionary<string,object>;object value;
    // Ordinary register packs remain shared content unless ownership is explicit.
    bool independent=data!=null&&data.TryGetValue("independentMod",out value)&&value is bool&&(bool)value;
    manifests[modPath]=new ManifestState{path=manifest,stamp=info.LastWriteTimeUtc.Ticks,length=info.Length,independent=independent};
    return independent;
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
    if(!String.IsNullOrEmpty(path))return ContentAssets.ResolveOwnedFile(mod,path);
   }
   return Path.Combine(DataDirectory,id+".json");
  }
  public static bool IsLocalDesignPath(string file){
   if(String.IsNullOrEmpty(file))return false;
   string root=Path.GetFullPath(DataDirectory).TrimEnd(Path.DirectorySeparatorChar,Path.AltDirectorySeparatorChar)+Path.DirectorySeparatorChar;
   return Path.GetFullPath(file).StartsWith(root,StringComparison.OrdinalIgnoreCase);
  }
 }

 public static class IteratorCatalog {
  static float nextRead;
  static float lastRead;
  static int loadedGeneration=-1;
  static List<Dictionary<string,object>> projects=new List<Dictionary<string,object>>();
  public static void Reset(){nextRead=lastRead=0;loadedGeneration=-1;projects=new List<Dictionary<string,object>>();}
  public static string Text(Dictionary<string,object> data,string key){object value;return data.TryGetValue(key,out value)&&value is string?(string)value:"";}
  public static List<Dictionary<string,object>> Projects(){
   int generation=ContentAssets.Generation;float now=Time.realtimeSinceStartup;
   if(generation==loadedGeneration&&now>=lastRead&&now<nextRead)return projects;
   lastRead=now;nextRead=now+.5f;loadedGeneration=generation;
   var result=new Dictionary<string,Dictionary<string,object>>();
   try{foreach(var asset in ContentAssets.Files("moreiterators",".json"))if(String.Equals(Path.GetFileName(asset.path),"registry.json",StringComparison.OrdinalIgnoreCase)&&ContentAssets.Managed(asset.owner))Read(asset.path,String.IsNullOrEmpty(asset.owner)?null:asset.owner,result,false,false);}
   catch(Exception error){MiDiagnostics.Report("MI_REGISTRY_DIRECTORY","IteratorCatalog.Projects",error,"moreiterators/registry.json");}
   Read(Path.Combine(RuntimePaths.DataDirectory,"creator/registry.json"),null,result);
   projects=new List<Dictionary<string,object>>(result.Values);
   projects.Sort((a,b)=>String.CompareOrdinal(Text(a,"projectId"),Text(b,"projectId")));return projects;
  }
  public static bool OwnerEnabled(string id){
   if(ModManager.ActiveMods==null)return false;
   foreach(var active in ModManager.ActiveMods)if(active!=null&&active.enabled&&active.id==id)return !RuntimePaths.HasIndependentRuntime(active.path);
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
  static void Read(string file,string owner,Dictionary<string,Dictionary<string,object>> result,bool includePendingLocal=false,bool replace=true){
   if(!File.Exists(file))return;
   try{
    var list=Json.Deserialize(File.ReadAllText(file)) as List<object>;if(list==null)return;
    foreach(var entry in list){var item=entry as Dictionary<string,object>;if(item==null)continue;
     if(owner!=null)item["ownerMod"]=owner;
     string mod=Text(item,"ownerMod");bool enabled=OwnerEnabled(mod);
     if((!enabled&&!(includePendingLocal&&mod=="moreiterators.local"))||Text(item,"projectId")==""||Text(item,"ai")==""||Text(item,"entry")==""||Text(item,"oracleId")=="")continue;
     // Normalize once so direct menu indexing and Text() share a string fallback.
     if(String.IsNullOrWhiteSpace(Text(item,"name"))){item["name"]=Text(item,"projectId");MiDiagnostics.Warn("MI_REGISTRY_NAME_FALLBACK","IteratorCatalog.Read",UiText.Get("Missing or invalid display name; using project ID."),file+"; project="+Text(item,"projectId"));}
     if(replace||!result.ContainsKey(Text(item,"projectId")))result[Text(item,"projectId")]=item;
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
