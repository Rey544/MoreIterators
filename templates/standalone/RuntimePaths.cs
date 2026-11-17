using System;
using System.IO;
using System.Collections.Generic;
using System.Diagnostics;
using UnityEngine;
namespace MoreIterators {
public static class RuntimePaths {
 public const string ModId="__MOD_ID__";
 public static bool TryContentRoot(out string root){root=null;if(ModManager.InitializationScreenFinished&&ModManager.ActiveMods!=null)foreach(var m in ModManager.ActiveMods)if(m!=null&&m.enabled&&m.id==ModId){root=m.path;return true;}return false;}
 public static string ContentRoot {get{string root;if(TryContentRoot(out root))return root;throw new InvalidOperationException("Content mod is not enabled: "+ModId);}}
 public static string DataDirectory {get{return Path.Combine(Application.persistentDataPath,ModId);}}
 public static void Initialize(){}
 public static string DesignPath(string id){
  if(String.IsNullOrEmpty(id)||id.Contains("..")||id.IndexOfAny(Path.GetInvalidFileNameChars())>=0)throw new ArgumentException("Invalid iterator ID");
  string root=ContentRoot;
  var project=IteratorCatalog.Projects().Find(p=>IteratorCatalog.Text(p,"oracleId")==id);
  string relative=project==null?"":IteratorCatalog.Text(project,"design");
  if(relative=="")relative="designs/"+id+".json";
  return ContentAssets.ResolveOwnedFile(ModId,relative);
 }
}
public static class IteratorCatalog {
 public const int ProjectsCacheVersion=1;
 static readonly Stopwatch clock=Stopwatch.StartNew();
 static List<Dictionary<string,object>> projects;
 static string loadedRoot,loadedFile,lastError;
 static long loadedStamp,loadedLength;
 static int loadedGeneration=-1;static double nextRead;
 static void Reset(){projects=null;loadedRoot=loadedFile=null;loadedGeneration=-1;nextRead=0;}
 public static string Text(Dictionary<string,object> d,string key){object v;return d.TryGetValue(key,out v)&&v is string?(string)v:"";}
 public static List<Dictionary<string,object>> Projects(){
  string root;
  // Hooks can query the catalogue before Rain World has populated ActiveMods.
  // Never commit an empty cache on that path or read a different content mod.
  if(!RuntimePaths.TryContentRoot(out root)){Reset();lastError=null;return new List<Dictionary<string,object>>();}
  try{
   int generation=ContentAssets.Generation;
   if(loadedGeneration!=generation){Reset();loadedGeneration=generation;}
   if(projects!=null&&projects.Count>0&&loadedRoot==root&&clock.Elapsed.TotalSeconds<nextRead)return projects;
   string file=ContentAssets.ResolveOwnedFile(RuntimePaths.ModId,"moreiterators/registry.json");
   if(file==null)throw new FileNotFoundException("Content registry was not found.");
   var info=new FileInfo(file);
   if(!info.Exists){ContentAssets.InvalidateDirectory("moreiterators");file=ContentAssets.ResolveOwnedFile(RuntimePaths.ModId,"moreiterators/registry.json");if(file==null)throw new FileNotFoundException("Content registry was not found.");info=new FileInfo(file);}
   if(projects!=null&&projects.Count>0&&loadedRoot==root&&loadedFile==file&&loadedStamp==info.LastWriteTimeUtc.Ticks&&loadedLength==info.Length){loadedGeneration=ContentAssets.Generation;nextRead=clock.Elapsed.TotalSeconds+.25;return projects;}
   var source=Json.Deserialize(File.ReadAllText(file)) as List<object>;
   if(source==null)throw new InvalidDataException("Registry must be a JSON array");
   var loaded=new List<Dictionary<string,object>>();
   foreach(var value in source){var p=value as Dictionary<string,object>;if(p==null||Text(p,"projectId")==""||Text(p,"name")==""||Text(p,"ai")==""||Text(p,"entry")==""||Text(p,"oracleId")=="")throw new InvalidDataException("Registry contains an incomplete iterator record");p["ownerMod"]=RuntimePaths.ModId;loaded.Add(p);}
   projects=loaded;loadedRoot=root;loadedFile=file;loadedStamp=info.LastWriteTimeUtc.Ticks;loadedLength=info.Length;loadedGeneration=ContentAssets.Generation;nextRead=projects.Count==0?0:clock.Elapsed.TotalSeconds+.25;lastError=null;return projects;
  }catch(Exception e){
   Reset();
   string error="[More Iterators content "+RuntimePaths.ModId+"] Cannot load registry at "+root+": "+e.Message;
   if(error!=lastError){UnityEngine.Debug.LogWarning(error);lastError=error;}
   return new List<Dictionary<string,object>>();
  }
 }
 public static Dictionary<string,object> Find(string room){if(room==null)return null;var all=Projects();return all.Find(p=>Text(p,"ai")==room)??all.Find(p=>Text(p,"entry")==room&&OwnsEntry(p))??all.Find(p=>Text(p,"entry")==room);}
 static bool OwnsEntry(Dictionary<string,object> project){object raw;var binding=project.TryGetValue("roomBinding",out raw)?raw as Dictionary<string,object>:null;return binding==null||Text(binding,"entryMode")!="existing";}
 public static bool IsEntry(string room){return room!=null&&Projects().Exists(p=>Text(p,"entry")==room);}
 public static bool OwnsEntry(string room){return room!=null&&Projects().Exists(p=>Text(p,"entry")==room&&OwnsEntry(p));}
 public static bool OwnsRoom(string room){return IsAI(room)||OwnsEntry(room);}
 public static string Id(string room){var p=Find(room);return p==null?"default":Text(p,"oracleId");}
 public static bool IsAI(string room){var p=Find(room);return p!=null&&Text(p,"ai")==room;}
 public static bool IsGenericRoom(string room){return OwnsRoom(room)&&!IteratorIntegrations.Native(Id(room));}
}
}
