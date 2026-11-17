using System;
using System.IO;
using System.Collections.Generic;
using System.Diagnostics;

namespace MoreIterators {
 public sealed class ContentAsset {
  public string path,owner;
 }

 // Catalog names are shared across content packs. Keep their provider identity
 // while using the game's actual resource order (including version folders).
 public static class ContentAssets {
  static readonly HashSet<string> warned=new HashSet<string>(StringComparer.OrdinalIgnoreCase);
  sealed class ModState {
   public ModManager.Mod identity;public string id,path,basePath,version,targetVersion,targeted,newest;public bool enabled,hasTargeted,hasNewest;public int loadOrder;
  }
  sealed class DirectoryState {
   public double loaded;public List<ContentAsset> files;public List<string> ambiguous;
  }
  static readonly Stopwatch clock=Stopwatch.StartNew();
  static readonly Dictionary<string,DirectoryState> directories=new Dictionary<string,DirectoryState>(StringComparer.OrdinalIgnoreCase);
  static readonly List<ModState> mods=new List<ModState>();
  static string gameRoot,consoleRoot;static object activeMods;static bool initialized,hadMods,ready;static int generation;
  public static int Generation {get{CheckContext();return generation;}}
  static void CheckContext(){
   string root=RWCustom.Custom.RootFolderDirectory(),console=AssetManager.GetConsoleFilesSubfolder();
   bool present=ModManager.ActiveMods!=null;
   bool same=initialized&&gameRoot==root&&consoleRoot==console&&hadMods==present&&ready==ModManager.InitializationScreenFinished&&ReferenceEquals(activeMods,ModManager.ActiveMods)&&mods.Count==(present?ModManager.ActiveMods.Count:0);
   if(same&&present)for(int i=0;i<mods.Count;i++){
    var current=ModManager.ActiveMods[i];var previous=mods[i];
    if(!ReferenceEquals(previous.identity,current)||current==null||previous.id!=current.id||previous.path!=current.path||previous.basePath!=current.basePath||previous.version!=current.version||previous.targetVersion!=current.targetGameVersion||previous.enabled!=current.enabled||previous.loadOrder!=current.loadOrder||previous.hasTargeted!=current.hasTargetedVersionFolder||previous.hasNewest!=current.hasNewestFolder||
       previous.targeted!=(current.hasTargetedVersionFolder?current.TargetedPath:null)||previous.newest!=(current.hasNewestFolder?current.NewestPath:null)){same=false;break;}
   }
   if(same)return;
   directories.Clear();mods.Clear();generation++;
   gameRoot=root;consoleRoot=console;hadMods=present;ready=ModManager.InitializationScreenFinished;activeMods=ModManager.ActiveMods;initialized=true;
   if(present)foreach(var mod in ModManager.ActiveMods)mods.Add(mod==null?new ModState():new ModState{identity=mod,id=mod.id,path=mod.path,basePath=mod.basePath,version=mod.version,targetVersion=mod.targetGameVersion,enabled=mod.enabled,loadOrder=mod.loadOrder,hasTargeted=mod.hasTargetedVersionFolder,hasNewest=mod.hasNewestFolder,
    targeted=mod.hasTargetedVersionFolder?mod.TargetedPath:null,newest=mod.hasNewestFolder?mod.NewestPath:null});
  }
  public static void InvalidateDirectory(string directory){directory=Relative(directory);CheckContext();directories.Remove(directory);generation++;}
  public static string Relative(string value){
   if(value==null)throw new ArgumentNullException("value");
   string path=value.Replace('\\','/');
   if(Path.IsPathRooted(path)||path.StartsWith("/",StringComparison.Ordinal))throw new ArgumentException("Content path must be relative");
   if(path.Length==0)return path;
   foreach(string part in path.Split('/'))if(part.Length==0||part=="."||part==".."||part.IndexOfAny(Path.GetInvalidFileNameChars())>=0||part.IndexOf(':')>=0)throw new ArgumentException("Invalid content path");
   return path;
  }
  static bool Within(string file,string directory){
   if(String.IsNullOrEmpty(directory))return false;
   string root=Path.GetFullPath(directory).TrimEnd(Path.DirectorySeparatorChar,Path.AltDirectorySeparatorChar)+Path.DirectorySeparatorChar;
   return Path.GetFullPath(file).StartsWith(root,StringComparison.OrdinalIgnoreCase);
  }
  static string Provider(string file){
   string owner="",longest="";
   if(ModManager.ActiveMods!=null)foreach(var mod in ModManager.ActiveMods){
    var roots=new List<string>();roots.Add(mod.path);
    if(mod.hasTargetedVersionFolder)roots.Add(mod.TargetedPath);
    if(mod.hasNewestFolder)roots.Add(mod.NewestPath);
    foreach(string root in roots)if(!String.IsNullOrEmpty(root)&&root.Length>longest.Length&&Within(file,root)){owner=mod.id;longest=root;}
   }
   return owner;
  }
  public static List<ContentAsset> Files(string directory,string extension,string owner=null){
   directory=Relative(directory);CheckContext();
   DirectoryState snapshot;double now=clock.Elapsed.TotalSeconds;
   if(!ready||!directories.TryGetValue(directory,out snapshot)||now-snapshot.loaded>=.25){
    snapshot=ReadDirectory(directory);snapshot.loaded=clock.Elapsed.TotalSeconds;
    if(directories.Count>=128)directories.Clear();
    if(ready)directories[directory]=snapshot;
   }
   foreach(string path in snapshot.ambiguous)if((String.IsNullOrEmpty(extension)||String.Equals(Path.GetExtension(path),extension,StringComparison.OrdinalIgnoreCase))&&warned.Add(path))
    MiDiagnostics.Warn("MI-ASSET-AMBIGUOUS","ContentAssets.Files",UiText.Get("Merged content has multiple providers; keeping each pack's own file."),path);
   var result=new List<ContentAsset>();var seen=new HashSet<string>(StringComparer.OrdinalIgnoreCase);
   foreach(var asset in snapshot.files){
    if(!String.IsNullOrEmpty(extension)&&!String.Equals(Path.GetExtension(asset.path),extension,StringComparison.OrdinalIgnoreCase))continue;
    if(owner!=null&&!String.Equals(owner,asset.owner,StringComparison.Ordinal))continue;
     
    if(seen.Add(asset.owner+"/"+Path.GetFileName(asset.path)))result.Add(new ContentAsset{path=asset.path,owner=asset.owner});
   }
   return result;
  }
  static DirectoryState ReadDirectory(string directory){
   string[] paths=AssetManager.ListDirectory(directory,false,true);
   string merged=Path.Combine(RWCustom.Custom.RootFolderDirectory(),"mergedmods");
   var snapshot=new DirectoryState{files=new List<ContentAsset>(),ambiguous=new List<string>()};
   foreach(string path in paths){
    string provider=Provider(path),name=Path.GetFileName(path);
    if(Within(path,merged)){
     // A merged common filename cannot identify which of several A01/registry
     // files it replaces. Only accept it when its original provider is unique.
     var providers=new HashSet<string>(StringComparer.OrdinalIgnoreCase);
     foreach(string original in paths)if(!Within(original,merged)&&String.Equals(Path.GetFileName(original),name,StringComparison.OrdinalIgnoreCase))providers.Add(Provider(original));
     if(providers.Count!=1){
      if(providers.Count>1)snapshot.ambiguous.Add(path);
      continue;
     }
     foreach(string candidate in providers)provider=candidate;
    }
    snapshot.files.Add(new ContentAsset{path=path,owner=provider});
   }
   return snapshot;
  }
  public static string ResolveOwnedFile(string owner,string relative){
   relative=Relative(relative);if(relative.Length==0)throw new ArgumentException("Content file is required");
   int separator=relative.LastIndexOf('/');
   string directory=separator<0?"":relative.Substring(0,separator),name=relative.Substring(separator+1);
   foreach(var asset in Files(directory,null,owner))if(String.Equals(Path.GetFileName(asset.path),name,StringComparison.OrdinalIgnoreCase))return asset.path;
   return null;
  }
  public static bool Managed(string owner){
#if PLAYBACK
   return String.Equals(owner,RuntimePaths.ModId,StringComparison.Ordinal);
#else
   if(String.IsNullOrEmpty(owner))return true;
   if(ModManager.ActiveMods!=null)foreach(var mod in ModManager.ActiveMods)if(mod.id==owner)return !RuntimePaths.HasIndependentRuntime(mod.path);
   return false;
#endif
  }
 }
}
