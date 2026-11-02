using System;
using System.IO;
using System.Collections.Generic;

namespace MoreIterators {
 public sealed class ContentAsset {
  public string path,owner;
 }

 // Catalog names are shared across content packs. Keep their provider identity
 // while using the game's actual resource order (including version folders).
 public static class ContentAssets {
  static readonly HashSet<string> warned=new HashSet<string>(StringComparer.OrdinalIgnoreCase);
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
   directory=Relative(directory);
   string[] paths=AssetManager.ListDirectory(directory,false,true);
   string merged=Path.Combine(RWCustom.Custom.RootFolderDirectory(),"mergedmods");
   var result=new List<ContentAsset>();var seen=new HashSet<string>(StringComparer.OrdinalIgnoreCase);
   foreach(string path in paths){
    if(!String.IsNullOrEmpty(extension)&&!String.Equals(Path.GetExtension(path),extension,StringComparison.OrdinalIgnoreCase))continue;
    string provider=Provider(path),name=Path.GetFileName(path);
    if(Within(path,merged)){
     // A merged common filename cannot identify which of several A01/registry
     // files it replaces. Only accept it when its original provider is unique.
     var providers=new HashSet<string>(StringComparer.OrdinalIgnoreCase);
     foreach(string original in paths)if(!Within(original,merged)&&String.Equals(Path.GetFileName(original),name,StringComparison.OrdinalIgnoreCase))providers.Add(Provider(original));
     if(providers.Count!=1){
      if(providers.Count>1&&warned.Add(path))MiDiagnostics.Warn("MI-ASSET-AMBIGUOUS","ContentAssets.Files",UiText.Get("Merged content has multiple providers; keeping each pack's own file."),path);
      continue;
     }
     foreach(string candidate in providers)provider=candidate;
    }
    if(owner!=null&&!String.Equals(owner,provider,StringComparison.Ordinal))continue;
    if(seen.Add(provider+"/"+name))result.Add(new ContentAsset{path=path,owner=provider});
   }
   return result;
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
