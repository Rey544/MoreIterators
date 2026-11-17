using System;
using System.IO;
using System.Reflection;
using System.Collections.Generic;
using BepInEx;
[assembly:AssemblyVersion("0.4.1.0")]
namespace IteratorContent_aaaaaaaaaaaa {
 [BepInPlugin("mi.legacy.fixture","fixture","0.1.0")]
 public sealed class MoreIteratorsPlugin : BaseUnityPlugin {}
 public static class RuntimePaths {
  public const string ModId="mi.legacy.fixture";
  public static bool TryContentRoot(out string root){root=null;if(ModManager.ActiveMods!=null)foreach(var m in ModManager.ActiveMods)if(m.id==ModId){root=m.path;return true;}return false;}
 }
 public static class IteratorCatalog {
  static List<Dictionary<string,object>> projects;
  static string loadedRoot,loadedFile,lastError;
  static long loadedStamp,loadedLength;
  public static string Text(Dictionary<string,object> d,string key){object v;return d.TryGetValue(key,out v)&&v is string?(string)v:"";}
  public static List<Dictionary<string,object>> Projects(){
   string root;
   if(!RuntimePaths.TryContentRoot(out root)){projects=null;loadedRoot=loadedFile=null;lastError=null;return new List<Dictionary<string,object>>();}
   try{
    string file=ContentAssets.ResolveOwnedFile(RuntimePaths.ModId,"moreiterators/registry.json");
    if(file==null)throw new FileNotFoundException("Content registry was not found.");
    var info=new FileInfo(file);
    if(projects!=null&&loadedRoot==root&&loadedFile==file&&loadedStamp==info.LastWriteTimeUtc.Ticks&&loadedLength==info.Length)return projects;
    var source=Json.Deserialize(File.ReadAllText(file)) as List<object>;
    if(source==null)throw new InvalidDataException("Registry must be a JSON array");
    var loaded=new List<Dictionary<string,object>>();
    foreach(var value in source){var p=value as Dictionary<string,object>;if(p==null||Text(p,"projectId")==""||Text(p,"name")==""||Text(p,"ai")==""||Text(p,"entry")==""||Text(p,"oracleId")=="")throw new InvalidDataException("Registry contains an incomplete iterator record");p["ownerMod"]=RuntimePaths.ModId;loaded.Add(p);}
    projects=loaded;loadedRoot=root;loadedFile=file;loadedStamp=info.LastWriteTimeUtc.Ticks;loadedLength=info.Length;lastError=null;return projects;
   }catch(Exception e){
    projects=null;loadedRoot=loadedFile=null;
    string error="[More Iterators content "+RuntimePaths.ModId+"] Cannot load registry at "+root+": "+e.Message;
    if(error!=lastError){lastError=error;}
    return new List<Dictionary<string,object>>();
   }
  }
 }
 public sealed class ContentAsset {public string path,owner;}
 public static class ContentAssets {
  public static string Relative(string value){return value;}
  public static List<ContentAsset> Files(string directory,string extension,string owner=null){throw new NotSupportedException("Metadata fixture only");}
  public static string ResolveOwnedFile(string owner,string relative){
   relative=Relative(relative);if(relative.Length==0)throw new ArgumentException("Content file is required");
   int separator=relative.LastIndexOf('/');
   string directory=separator<0?"":relative.Substring(0,separator),name=relative.Substring(separator+1);
   foreach(var asset in Files(directory,null,owner))if(String.Equals(Path.GetFileName(asset.path),name,StringComparison.OrdinalIgnoreCase))return asset.path;
   return null;
  }
 }
}
