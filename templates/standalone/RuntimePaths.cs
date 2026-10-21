using System;
using System.IO;
using System.Collections.Generic;
using UnityEngine;
namespace MoreIterators {
public static class RuntimePaths {
 public const string ModId="__MOD_ID__";
 public static bool TryContentRoot(out string root){root=null;if(ModManager.ActiveMods!=null)foreach(var m in ModManager.ActiveMods)if(m.id==ModId){root=m.path;return true;}return false;}
 public static string ContentRoot {get{string root;if(TryContentRoot(out root))return root;throw new InvalidOperationException("Content mod is not enabled: "+ModId);}}
 public static string DataDirectory {get{return Path.Combine(Application.persistentDataPath,ModId);}}
 public static void Initialize(){}
 public static string DesignPath(string id){if(String.IsNullOrEmpty(id)||id.Contains("..")||id.IndexOfAny(Path.GetInvalidFileNameChars())>=0)throw new ArgumentException("Invalid iterator ID");return Path.Combine(ContentRoot,"designs/"+id+".json");}
}
public static class IteratorCatalog {
 static List<Dictionary<string,object>> projects;
 static string loadedRoot,lastError;
 public static string Text(Dictionary<string,object> d,string key){object v;return d.TryGetValue(key,out v)&&v is string?(string)v:"";}
 public static List<Dictionary<string,object>> Projects(){
  string root;
  // Hooks can query the catalogue before Rain World has populated ActiveMods.
  // Never commit an empty cache on that path or read a different content mod.
  if(!RuntimePaths.TryContentRoot(out root)){projects=null;loadedRoot=null;lastError=null;return new List<Dictionary<string,object>>();}
  if(projects!=null&&loadedRoot==root)return projects;
  try{
   var source=Json.Deserialize(File.ReadAllText(Path.Combine(root,"moreiterators/registry.json"))) as List<object>;
   if(source==null)throw new InvalidDataException("Registry must be a JSON array");
   var loaded=new List<Dictionary<string,object>>();
   foreach(var value in source){var p=value as Dictionary<string,object>;if(p==null||Text(p,"projectId")==""||Text(p,"name")==""||Text(p,"ai")==""||Text(p,"entry")==""||Text(p,"oracleId")=="")throw new InvalidDataException("Registry contains an incomplete iterator record");p["ownerMod"]=RuntimePaths.ModId;loaded.Add(p);}
   projects=loaded;loadedRoot=root;lastError=null;return projects;
  }catch(Exception e){
   projects=null;loadedRoot=null;
   string error="[More Iterators content "+RuntimePaths.ModId+"] Cannot load registry at "+root+": "+e.Message;
   if(error!=lastError){Debug.LogWarning(error);lastError=error;}
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
