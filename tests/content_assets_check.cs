using System;
using System.IO;
using System.Collections.Generic;
using MoreIterators;

 
 
public static class ModManager {
 public sealed class Mod {
  public string id,path,basePath,version,targetGameVersion,TargetedPath,NewestPath;public int loadOrder;
  public bool enabled=true,hasTargetedVersionFolder,hasNewestFolder;
  public Mod(string id,string path){this.id=id;this.path=path;TargetedPath=Path.Combine(path,"targeted");NewestPath=Path.Combine(path,"newest");}
 }
 public static bool InitializationScreenFinished=true;public static List<Mod> ActiveMods=new List<Mod>();
}
namespace RWCustom {public static class Custom {public static string Root;public static string RootFolderDirectory(){return Root;}}}
namespace UnityEngine {public static class Debug {public static void LogWarning(object value){Console.WriteLine(value);}}}
namespace MoreIterators {
 public static class PlaybackMode {
#if PLAYBACK
  public const bool Enabled=true;
#else
  public const bool Enabled=false;
#endif
 }
 public static class RuntimePaths {
  public const string ModId="pack.a";
  public static bool HasIndependentRuntime(string path){return File.Exists(Path.Combine(path,"independent.marker"));}
 }
 public static class MiDiagnostics {
  public static readonly List<string> Warnings=new List<string>();
  public static void Warn(string code,string node,string detail,string context){Warnings.Add(code+":"+context);}
  public static void Report(string code,string node,Exception error,string context){Warnings.Add(code+":"+context);}
 }
}
public static class AssetManager {
 public static int ListCalls;public static bool AllCallsIncluded=true;
 public static string ConsoleRoot;
 public static string GetConsoleFilesSubfolder(){return ConsoleRoot??"";}
 static List<string> Roots(bool moddedOnly){
  var roots=new List<string>();roots.Add(Path.Combine(RWCustom.Custom.RootFolderDirectory(),"mergedmods"));
  if(ModManager.ActiveMods!=null)for(int i=ModManager.ActiveMods.Count-1;i>=0;i--){var mod=ModManager.ActiveMods[i];if(mod.hasTargetedVersionFolder)roots.Add(mod.TargetedPath);if(mod.hasNewestFolder)roots.Add(mod.NewestPath);roots.Add(mod.path);}
  if(ConsoleRoot!=null)roots.Add(ConsoleRoot);
  if(!moddedOnly)roots.Add(RWCustom.Custom.RootFolderDirectory());return roots;
 }
 public static string[] ListDirectory(string path,bool directories=false,bool includeAll=false,bool moddedOnly=false){
  ListCalls++;AllCallsIncluded&=includeAll;var result=new List<string>();var names=new List<string>();
  foreach(string root in Roots(moddedOnly)){string folder=Path.Combine(root,path.ToLowerInvariant());if(!Directory.Exists(folder))continue;
   foreach(string file in directories?Directory.GetDirectories(folder):Directory.GetFiles(folder)){string name=Path.GetFileName(file);if(includeAll||!names.Contains(name)){result.Add(file.ToLowerInvariant());if(!includeAll)names.Add(name);}}
  }return result.ToArray();
 }
 public static string ResolveFilePath(string path,bool skipMergedMods=false,bool skipConsoleFiles=false){
  foreach(string root in Roots(false)){if(skipMergedMods&&root==Path.Combine(RWCustom.Custom.RootFolderDirectory(),"mergedmods"))continue;if(skipConsoleFiles&&root==ConsoleRoot)continue;
   string file=Path.Combine(root,path.ToLowerInvariant());if(File.Exists(file))return file;}
  return Path.Combine(RWCustom.Custom.RootFolderDirectory(),path.ToLowerInvariant());
 }
 public static List<string> ResolveAllFilePaths(string path){
   
  var roots=new List<string>{Path.Combine(RWCustom.Custom.RootFolderDirectory(),"mergedmods")};
  if(ModManager.ActiveMods!=null)foreach(var mod in ModManager.ActiveMods){if(mod.hasTargetedVersionFolder)roots.Add(mod.TargetedPath);if(mod.hasNewestFolder)roots.Add(mod.NewestPath);roots.Add(mod.path);}
  if(ConsoleRoot!=null)roots.Add(ConsoleRoot);roots.Add(RWCustom.Custom.RootFolderDirectory());
  var result=new List<string>();foreach(string root in roots){string file=Path.Combine(root,path.ToLowerInvariant());if(File.Exists(file))result.Add(file);}return result;
 }
}
public static class ContentAssetsCheck {
 static int count;
 static void Check(bool condition,string message){if(!condition)throw new Exception(message);count++;}
 static void Write(string file,string text){Directory.CreateDirectory(Path.GetDirectoryName(file));File.WriteAllText(file,text);}
 static string Text(string file){return file==null?null:File.ReadAllText(file);}
 static ModManager.Mod Package(string root,string id){var m=new ModManager.Mod(id,Path.Combine(root,"mods",id));ModManager.ActiveMods.Add(m);return m;}
 static bool Rejects(Action action){try{action();return false;}catch(ArgumentException){return true;}catch(InvalidDataException){return true;}catch(InvalidOperationException){return true;}}
 static void Run(string scenario,string root){
  RWCustom.Custom.Root=root;var a=Package(root,"pack.a");var b=Package(root,"pack.b");
  const string folder="moreiterators/pearls",pearl="moreiterators/pearls/a01.json";
  Write(Path.Combine(a.path,pearl),"a-root");Write(Path.Combine(b.path,pearl),"b-root");
  switch(scenario){
   case "same-name":
    Write(Path.Combine(a.path,"moreiterators/registry.json"),"a-registry");Write(Path.Combine(b.path,"moreiterators/registry.json"),"b-registry");
    Write(Path.Combine(a.path,"moreiterators/pearls/readme.txt"),"not-a-pearl");
    var files=ContentAssets.Files(folder,".json");Check(files.Count==2,"two providers with A01 must both survive");
    Check(files[0].owner=="pack.b"&&Text(files[0].path)=="b-root","native higher mod priority must come first");
    Check(files[1].owner=="pack.a"&&Text(files[1].path)=="a-root","lower mod's distinct provider must remain");
    Check(Text(ContentAssets.ResolveOwnedFile("pack.a",pearl))=="a-root","owned pearl resolves A");
    Check(Text(ContentAssets.ResolveOwnedFile("pack.b",pearl))=="b-root","owned pearl resolves B");
    Check(Text(ContentAssets.ResolveOwnedFile("pack.a","moreiterators/registry.json"))=="a-registry","shared registry name must stay owned");
    Check(Text(ContentAssets.ResolveOwnedFile("pack.b","moreiterators/registry.json"))=="b-registry","second registry must stay owned");
    Check(ContentAssets.Files(folder,".json","pack.a").Count==1,"owner-filtered enumeration returns only A");
    Check(AssetManager.ListCalls>0&&AssetManager.AllCallsIncluded,"native directory enumeration must preserve all providers");break;
   case "versions":
    a.hasTargetedVersionFolder=a.hasNewestFolder=true;
    Write(Path.Combine(a.TargetedPath,pearl),"a-targeted");Write(Path.Combine(a.NewestPath,pearl),"a-newest");
    Write(Path.Combine(a.NewestPath,"moreiterators/pearls/a02.json"),"new-only");
    Check(ContentAssets.Files(folder,".json","pack.a").Count==2,"version duplicates collapse while unique files remain");
    Check(Text(ContentAssets.ResolveOwnedFile("pack.a",pearl))=="a-targeted","targeted beats newest and root");
    a.hasTargetedVersionFolder=false;Check(Text(ContentAssets.ResolveOwnedFile("pack.a",pearl))=="a-newest","inactive targeted folder cannot supply assets");
    File.Delete(Path.Combine(a.NewestPath,pearl));System.Threading.Thread.Sleep(300);Check(Text(ContentAssets.ResolveOwnedFile("pack.a",pearl))=="a-root","missing version asset falls through to root after bounded cache refresh");
    Check(Text(ContentAssets.ResolveOwnedFile("pack.a","moreiterators/pearls/a02.json"))=="new-only","newest-only asset remains available");break;
   case "merged":
    Write(Path.Combine(a.path,"moreiterators/pearls/unique.json"),"unique-original");
    Write(Path.Combine(root,"mergedmods/moreiterators/pearls/unique.json"),"unique-merged");
    Write(Path.Combine(root,"mergedmods/"+pearl),"ambiguous-merged");
    Check(Text(ContentAssets.ResolveOwnedFile("pack.a","moreiterators/pearls/unique.json"))=="unique-merged","unique merged file must retain its original provider");
    Check(Text(ContentAssets.ResolveOwnedFile("pack.a",pearl))=="a-root","ambiguous merged A01 cannot replace A");
    Check(Text(ContentAssets.ResolveOwnedFile("pack.b",pearl))=="b-root","ambiguous merged A01 cannot replace B");
    Check(ContentAssets.Files(folder,".json").Count==3,"ambiguous merged source must not create an extra unowned pearl");
    Check(MiDiagnostics.Warnings.Count>0,"ambiguous merged source must report a diagnostic");break;
   case "lifecycle":
    Check(Text(ContentAssets.ResolveOwnedFile("pack.a",pearl))=="a-root","initial package resolves");
    ModManager.ActiveMods.Remove(a);Check(ContentAssets.ResolveOwnedFile("pack.a",pearl)==null,"disabled package cannot fall through to B");
    ModManager.ActiveMods.Add(a);Check(Text(ContentAssets.ResolveOwnedFile("pack.a",pearl))=="a-root","re-enabled package resolves again");
    string oldPath=a.path;a.path=Path.Combine(root,"moved","pack.a");Write(Path.Combine(a.path,pearl),"a-moved");
    Check(Text(ContentAssets.ResolveOwnedFile("pack.a",pearl))=="a-moved","changed installation path invalidates previous resolution");
    Check(Text(Path.Combine(oldPath,pearl))=="a-root","resolution never mutates the old package");
    Check(ContentAssets.ResolveOwnedFile("not-enabled",pearl)==null,"unknown owner must not read a matching active mod");
    ModManager.ActiveMods=null;Check(ContentAssets.ResolveOwnedFile("pack.a",pearl)==null,"early null mod list cannot claim another provider");break;
   case "paths":
    Write(Path.Combine(a.path,"secret.json"),"private");
    Check(Rejects(()=>ContentAssets.ResolveOwnedFile("pack.a","../secret.json")),"parent path rejected");
    Check(Rejects(()=>ContentAssets.ResolveOwnedFile("pack.a","moreiterators/../secret.json")),"internal traversal rejected");
    Check(Rejects(()=>ContentAssets.ResolveOwnedFile("pack.a",Path.Combine(a.path,"secret.json"))),"absolute path rejected");
    Check(Rejects(()=>ContentAssets.Files("../", ".json")),"directory traversal rejected");
    Check(Text(ContentAssets.ResolveOwnedFile("pack.a","MOREITERATORS/PEARLS/A01.JSON"))=="a-root","logical paths use the game's case-insensitive convention");
    Check(Text(ContentAssets.ResolveOwnedFile("pack.a","moreiterators\\pearls\\a01.json"))=="a-root","native slash conventions resolve the same asset");break;
   case "base":
    ModManager.ActiveMods.Clear();Write(Path.Combine(root,"moreiterators/pearls/base.json"),"base-game");
    var baseFiles=ContentAssets.Files(folder,".json");Check(baseFiles.Count==1&&Text(baseFiles[0].path)=="base-game","base-game resource is discoverable");
    Check(String.IsNullOrEmpty(baseFiles[0].owner),"base-game resource has no fabricated mod owner");
    AssetManager.ConsoleRoot=Path.Combine(root,"consolefiles","watcher");Write(Path.Combine(AssetManager.ConsoleRoot,"moreiterators/pearls/base.json"),"dlc-override");
    baseFiles=ContentAssets.Files(folder,".json");Check(baseFiles.Count==1&&Text(baseFiles[0].path)=="dlc-override","console/DLC fallback precedes native base for the same resource");break;
   case "managed":
    Write(Path.Combine(b.path,"independent.marker"),"true");
#if PLAYBACK
    Check(ContentAssets.Managed("pack.a"),"playback accepts its own provider");Check(!ContentAssets.Managed("pack.b"),"playback rejects another provider");Check(!ContentAssets.Managed(""),"playback rejects unowned content");
#else
    Check(ContentAssets.Managed("pack.a"),"core accepts ordinary registered content");Check(!ContentAssets.Managed("pack.b"),"core excludes an independent runtime");Check(ContentAssets.Managed(""),"core permits unowned native resources");
#endif
    break;
   default:throw new ArgumentException(scenario);
  }
  Console.WriteLine("content asset assertions passed: "+scenario+" ("+count+")");
 }
 public static int Main(string[] args){try{Run(args[0],args[1]);return 0;}catch(Exception e){Console.Error.WriteLine(e);return 1;}}
}
