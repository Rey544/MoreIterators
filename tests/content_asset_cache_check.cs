using System;
using System.IO;
using System.Collections.Generic;
using System.Threading;
using System.Web.Script.Serialization;
using MoreIterators;

public static class ModManager {
 public sealed class Mod {
  public string id,path,basePath,version,targetGameVersion,TargetedPath,NewestPath;public bool enabled=true,hasTargetedVersionFolder,hasNewestFolder;public int loadOrder;
  public Mod(string id,string path){this.id=id;this.path=path;TargetedPath=Path.Combine(path,"targeted");NewestPath=Path.Combine(path,"newest");}
 }
 public static bool InitializationScreenFinished=true;public static List<Mod> ActiveMods=new List<Mod>();
}
namespace RWCustom {public static class Custom {public static string Root;public static string RootFolderDirectory(){return Root;}}}
namespace UnityEngine {
 public static class Time {public static float realtimeSinceStartup;}
 public static class Application {public static string persistentDataPath;}
 public static class Debug {public static void LogWarning(object value){}}
}
namespace BepInEx {public static class Paths {public static string ConfigPath;}}
namespace MoreIterators {
 public static class UiText {public static string Get(string value){return value;}}
 public static class NativeRoomProjects {public static bool Available(Dictionary<string,object> value){return true;}}
 public static class IteratorIntegrations {public static bool Native(string id){return false;}}
 public static class MiDiagnostics {
  public static readonly List<string> Warnings=new List<string>();
  public static void Warn(string code,string member,string detail,string context){Warnings.Add(code);}
  public static void Report(string code,string member,Exception error,string context){Warnings.Add(code);}
 }
}
public static class Json {
 public static int Reads;
 static object ConvertValue(object value){
  var dictionary=value as Dictionary<string,object>;
  if(dictionary!=null){var result=new Dictionary<string,object>();foreach(var pair in dictionary)result[pair.Key]=ConvertValue(pair.Value);return result;}
  var array=value as object[];if(array!=null){var result=new List<object>();foreach(var item in array)result.Add(ConvertValue(item));return result;}return value;
 }
 public static object Deserialize(string text){Reads++;return ConvertValue(new JavaScriptSerializer().DeserializeObject(text));}
}
public static class AssetManager {
 public static int ListCalls;public static bool Fail;public static string ConsoleFolder;
 public static string GetConsoleFilesSubfolder(){return ConsoleFolder;}
  
 public static string[] ListDirectory(string path,bool directories,bool includeAll){
  if(Fail)throw new IOException("fixture enumeration failure");
  ListCalls++;var roots=new List<string>{Path.Combine(RWCustom.Custom.Root,"mergedmods")};
  if(ModManager.ActiveMods!=null)for(int i=ModManager.ActiveMods.Count-1;i>=0;i--){var mod=ModManager.ActiveMods[i];if(mod.hasTargetedVersionFolder)roots.Add(mod.TargetedPath);if(mod.hasNewestFolder)roots.Add(mod.NewestPath);roots.Add(mod.path);}
  if(ConsoleFolder!=null)roots.Add(Path.Combine(RWCustom.Custom.Root,"consolefiles",ConsoleFolder));
  roots.Add(RWCustom.Custom.Root);
  var result=new List<string>();var names=new HashSet<string>();
  foreach(string root in roots){string folder=Path.Combine(root,path.ToLowerInvariant());if(!Directory.Exists(folder))continue;
   foreach(string file in directories?Directory.GetDirectories(folder):Directory.GetFiles(folder))if(includeAll||names.Add(Path.GetFileName(file)))result.Add(file.ToLowerInvariant());
  }
  return result.ToArray();
 }
}
public static class ContentAssetCacheCheck {
 static string fixtureRoot;static int assertions;
 static void Check(bool value,string message){if(!value)throw new Exception(message);assertions++;}
 static void Write(string file,string text){
  string target=Path.GetFullPath(file),root=Path.GetFullPath(fixtureRoot)+Path.DirectorySeparatorChar;
  if(!target.StartsWith(root,StringComparison.OrdinalIgnoreCase))throw new Exception("fixture write escaped temporary directory");
  Directory.CreateDirectory(Path.GetDirectoryName(target));File.WriteAllText(target,text);
 }
 static string Read(string file){return file==null?null:File.ReadAllText(file);}
 static string Registry(string name){return "[{\"projectId\":\"shared-id\",\"name\":\""+name+"\",\"ai\":\"SHARED_AI\",\"entry\":\"SHARED_ENTRY\",\"oracleId\":\"shared\"}]";}
 static void Refresh(){Thread.Sleep(300);}
 static ModManager.Mod Add(string id){var mod=new ModManager.Mod(id,Path.Combine(fixtureRoot,"mods",id));ModManager.ActiveMods.Add(mod);return mod;}
 static void Run(){
  RWCustom.Custom.Root=Path.Combine(fixtureRoot,"game");Directory.CreateDirectory(RWCustom.Custom.Root);
  UnityEngine.Application.persistentDataPath=Path.Combine(fixtureRoot,"user");BepInEx.Paths.ConfigPath=Path.Combine(fixtureRoot,"config");
  var a=Add("pack.a");var b=Add("pack.b");const string folder="moreiterators/pearls",relative="moreiterators/pearls/a01.json";
  Write(Path.Combine(a.path,relative),"a-root");Write(Path.Combine(b.path,relative),"b-root");
  Write(Path.Combine(a.path,folder,"readme.txt"),"text");
  var first=ContentAssets.Files(folder,".json");Check(first.Count==2&&first[0].owner=="pack.b","native mod priority and distinct owners retained");
  int scans=AssetManager.ListCalls;
  for(int i=0;i<50;i++){
   Check(Read(ContentAssets.ResolveOwnedFile("pack.a",relative))=="a-root","owned A stays isolated");
   Check(Read(ContentAssets.ResolveOwnedFile("pack.b",relative))=="b-root","owned B stays isolated");
  }
  Check(ContentAssets.Files(folder,".txt","pack.a").Count==1,"extension filters use same directory");
  Check(AssetManager.ListCalls==scans,"repeat owner/extension queries enumerate once");
  first[0].owner="mutated";first[0].path="mutated";first.Clear();
  Check(Read(ContentAssets.ResolveOwnedFile("pack.b",relative))=="b-root","mutating result list or item cannot poison cache");

  int generation=ContentAssets.Generation;scans=AssetManager.ListCalls;a.enabled=false;
  Check(ContentAssets.Generation>generation,"enabled flag invalidates directory generation immediately");ContentAssets.Files(folder,".json");Check(AssetManager.ListCalls>scans,"enabled change re-enters original native enumeration");a.enabled=true;
  generation=ContentAssets.Generation;a.loadOrder++;Check(ContentAssets.Generation>generation,"load order value invalidates generation");
  generation=ContentAssets.Generation;ModManager.ActiveMods=new List<ModManager.Mod>(ModManager.ActiveMods);Check(ContentAssets.Generation>generation,"same-sized active list replacement invalidates generation");
  generation=ContentAssets.Generation;var replacement=new ModManager.Mod(b.id,b.path);ModManager.ActiveMods[1]=replacement;b=replacement;Check(ContentAssets.Generation>generation,"same-id same-path replacement instance invalidates generation");
  generation=ContentAssets.Generation;a.basePath="changed-base";Check(ContentAssets.Generation>generation,"base path metadata invalidates generation");
  generation=ContentAssets.Generation;a.version="changed-version";Check(ContentAssets.Generation>generation,"mod version invalidates generation");
  generation=ContentAssets.Generation;a.targetGameVersion="changed-target";Check(ContentAssets.Generation>generation,"target game version invalidates generation");
  generation=ContentAssets.Generation;ModManager.InitializationScreenFinished=false;Check(ContentAssets.Generation>generation,"unready transition invalidates generation");
  scans=AssetManager.ListCalls;ContentAssets.Files(folder,".json");ContentAssets.Files(folder,".json");Check(AssetManager.ListCalls==scans+2,"unready directory results are not cached");
  generation=ContentAssets.Generation;ModManager.InitializationScreenFinished=true;Check(ContentAssets.Generation>generation,"ready transition invalidates startup snapshot");

  ModManager.ActiveMods.Reverse();Check(ContentAssets.Files(folder,".json")[0].owner=="pack.a","mod reorder invalidates immediately");
  ModManager.ActiveMods.Remove(a);Check(ContentAssets.ResolveOwnedFile("pack.a",relative)==null,"disabled owner cannot read B");
  ModManager.ActiveMods.Add(a);Check(Read(ContentAssets.ResolveOwnedFile("pack.a",relative))=="a-root","reenabled owner resolves immediately");
  a.hasTargetedVersionFolder=a.hasNewestFolder=true;
  Write(Path.Combine(a.TargetedPath,relative),"targeted");Write(Path.Combine(a.NewestPath,relative),"newest");
  Check(Read(ContentAssets.ResolveOwnedFile("pack.a",relative))=="targeted","targeted version wins immediately");
  a.TargetedPath=Path.Combine(a.path,"targeted-second");Write(Path.Combine(a.TargetedPath,relative),"second");
  Check(Read(ContentAssets.ResolveOwnedFile("pack.a",relative))=="second","version path changes invalidate immediately");
  a.hasTargetedVersionFolder=false;Check(Read(ContentAssets.ResolveOwnedFile("pack.a",relative))=="newest","version flag changes invalidate immediately");
  a.NewestPath=Path.Combine(a.path,"newest-second");Write(Path.Combine(a.NewestPath,relative),"newest-second");
  Check(Read(ContentAssets.ResolveOwnedFile("pack.a",relative))=="newest-second","newest path changes invalidate immediately");
  File.Delete(Path.Combine(a.NewestPath,relative));Refresh();
  Check(Read(ContentAssets.ResolveOwnedFile("pack.a",relative))=="a-root","deleted version falls back after bounded refresh");
  string added=folder+"/added.json";Check(ContentAssets.ResolveOwnedFile("pack.a",added)==null,"missing lookup initially empty");
  Write(Path.Combine(a.path,added),"added");Refresh();
  Check(Read(ContentAssets.ResolveOwnedFile("pack.a",added))=="added","new file discovered without advancing game Time");
  Check(UnityEngine.Time.realtimeSinceStartup==0,"test game clock remained stopped");
  string oldPath=a.path;a.path=Path.Combine(fixtureRoot,"moved","pack.a");a.hasNewestFolder=false;
  Write(Path.Combine(a.path,relative),"moved");Check(Read(ContentAssets.ResolveOwnedFile("pack.a",relative))=="moved","owner installation path invalidates immediately");
  Check(Read(Path.Combine(oldPath,relative))=="a-root","old source untouched");
  a.id="pack.renamed";Check(ContentAssets.ResolveOwnedFile("pack.a",relative)==null&&Read(ContentAssets.ResolveOwnedFile("pack.renamed",relative))=="moved","owner identity change invalidates immediately");
  a.id="pack.a";

  string unique=folder+"/unique.json";Write(Path.Combine(a.path,unique),"unique-original");
  Write(Path.Combine(RWCustom.Custom.Root,"mergedmods",unique),"unique-merged");
  Write(Path.Combine(RWCustom.Custom.Root,"mergedmods",relative),"ambiguous-merged");Refresh();
  Check(Read(ContentAssets.ResolveOwnedFile("pack.a",unique))=="unique-merged","unique merged file keeps owner");
  Check(Read(ContentAssets.ResolveOwnedFile("pack.a",relative))=="moved"&&Read(ContentAssets.ResolveOwnedFile("pack.b",relative))=="b-root","ambiguous merged filename never mixes owners");
  Check(MiDiagnostics.Warnings.Contains("MI-ASSET-AMBIGUOUS"),"ambiguous merge remains visible in diagnostics");
  ModManager.ActiveMods.Remove(b);Check(Read(ContentAssets.ResolveOwnedFile("pack.a",relative))=="ambiguous-merged","provider removal recomputes merged ownership immediately");ModManager.ActiveMods.Add(b);
  string baseAsset="native/sample.json";Write(Path.Combine(RWCustom.Custom.Root,baseAsset),"base");
  Check(Read(ContentAssets.ResolveOwnedFile("",baseAsset))=="base","base resources retain empty owner");
  Write(Path.Combine(RWCustom.Custom.Root,"consolefiles","watcher",baseAsset),"console");AssetManager.ConsoleFolder="watcher";
  Check(Read(ContentAssets.ResolveOwnedFile("",baseAsset))=="console","console/DLC root change invalidates immediately");
  AssetManager.ConsoleFolder=null;string originalRoot=RWCustom.Custom.Root;RWCustom.Custom.Root=Path.Combine(fixtureRoot,"second-game");Write(Path.Combine(RWCustom.Custom.Root,baseAsset),"other-base");
  Check(Read(ContentAssets.ResolveOwnedFile("",baseAsset))=="other-base","base game root change invalidates immediately");RWCustom.Custom.Root=originalRoot;
  AssetManager.Fail=true;bool failed=false;try{ContentAssets.Files("not-cached",".json");}catch(IOException){failed=true;}
  Check(failed,"enumeration errors are not silently converted to empty results");AssetManager.Fail=false;
  Write(Path.Combine(a.path,"not-cached/test.json"),"retry");Check(ContentAssets.Files("not-cached",".json").Count==1,"failed enumeration is retried without cached emptiness");

  string manifest=Path.Combine(a.path,"content-manifest.json"),other=Path.Combine(b.path,"content-manifest.json");
  const string yes="{\"independentMod\":true }",no="{\"independentMod\":false}";
  Check(yes.Length==no.Length,"fixture bool documents have equal lengths");Write(manifest,yes);Write(other,no);
  Json.Reads=0;Check(RuntimePaths.HasIndependentRuntime(a.path),"A independent manifest loaded");scans=AssetManager.ListCalls;
  for(int i=0;i<50;i++)Check(RuntimePaths.HasIndependentRuntime(a.path),"repeated independent result retained");
  Check(Json.Reads==1&&AssetManager.ListCalls==scans,"unchanged manifest parsed and root enumerated once");
  Check(!RuntimePaths.HasIndependentRuntime(b.path)&&Json.Reads==2,"same manifest filename from B remains separate");
  DateTime stamp=File.GetLastWriteTimeUtc(manifest);Write(manifest,no);File.SetLastWriteTimeUtc(manifest,stamp.AddSeconds(5));
  Check(!RuntimePaths.HasIndependentRuntime(a.path),"equal-length manifest edit reloads by timestamp immediately");
  stamp=File.GetLastWriteTimeUtc(manifest);Write(manifest,"{\"independentMod\":true}");File.SetLastWriteTimeUtc(manifest,stamp);
  Check(RuntimePaths.HasIndependentRuntime(a.path),"equal-timestamp manifest edit reloads by length immediately");
  File.Delete(manifest);Check(!RuntimePaths.HasIndependentRuntime(a.path),"deleted manifest cannot keep stale true result");
  Write(manifest,yes);Check(RuntimePaths.HasIndependentRuntime(a.path),"recreated manifest reloads");
  a.hasTargetedVersionFolder=true;Write(Path.Combine(a.TargetedPath,"content-manifest.json"),yes);
  Check(RuntimePaths.HasIndependentRuntime(a.path),"targeted manifest resolves");
  string target=Path.Combine(a.TargetedPath,"content-manifest.json");File.Delete(target);Refresh();Check(RuntimePaths.HasIndependentRuntime(a.path),"removed override falls back to root");
  stamp=File.GetLastWriteTimeUtc(manifest);Write(target,no);File.SetLastWriteTimeUtc(target,stamp);Refresh();
  Check(!RuntimePaths.HasIndependentRuntime(a.path),"new override with equal timestamp and length reloads by resolved path");
  ModManager.ActiveMods.Remove(a);Check(!RuntimePaths.HasIndependentRuntime(a.path)&&!ContentAssets.Managed("pack.a"),"disabled mod cannot read its old fixed-path manifest or be managed");
  ModManager.ActiveMods.Add(a);Check(!RuntimePaths.HasIndependentRuntime(a.path)&&ContentAssets.Managed("pack.a"),"reenable resets manifest ownership state");
  var active=ModManager.ActiveMods;ModManager.ActiveMods=null;
  Check(ContentAssets.ResolveOwnedFile("pack.a",relative)==null&&!RuntimePaths.HasIndependentRuntime(a.path),"early null active list never falls through to a content pack");
  ModManager.ActiveMods=active;
  Check(!RuntimePaths.HasIndependentRuntime(a.path),"active list restoration resolves current manifest");
  Write(Path.Combine(a.path,"moreiterators/registry.json"),Registry("from-a"));Write(Path.Combine(b.path,"moreiterators/registry.json"),Registry("from-b"));
  IteratorCatalog.Reset();var catalogue=IteratorCatalog.Projects();
  Check(catalogue.Count==1&&IteratorCatalog.Text(catalogue[0],"name")=="from-a","core registry uses original highest-priority provider for conflicting project ID");
  var timer=System.Diagnostics.Stopwatch.StartNew();for(int i=0;i<5000;i++)Check(Object.ReferenceEquals(catalogue,IteratorCatalog.Projects()),"core unchanged context retains cached list");timer.Stop();
  Console.WriteLine("TIMING core_warm_5000_ms="+timer.Elapsed.TotalMilliseconds.ToString("F3",System.Globalization.CultureInfo.InvariantCulture));
  a.enabled=false;Check(IteratorCatalog.Text(IteratorCatalog.Projects()[0],"name")=="from-b","core enabled flag change invalidates within old half-second cache window");
  a.enabled=true;Check(IteratorCatalog.Text(IteratorCatalog.Projects()[0],"name")=="from-a","core reenabling makes original priority visible immediately");
  Write(Path.Combine(a.path,"moreiterators/registry.json"),Registry("changed-a"));a.loadOrder++;
  Check(IteratorCatalog.Text(IteratorCatalog.Projects()[0],"name")=="changed-a","core metadata order change refreshes before game clock advances");
  ModManager.ActiveMods.Reverse();Check(IteratorCatalog.Text(IteratorCatalog.Projects()[0],"name")=="from-b","core reorder immediately uses current native priority");
  Check(UnityEngine.Time.realtimeSinceStartup==0,"core context regression did not advance game clock to conceal stale cache");
  Console.WriteLine("PASS "+assertions+" actual-method assertions; native ordering, mutable results, lifecycle and manifest invalidation");
 }
 public static int Main(){
  fixtureRoot=Path.Combine(Path.GetTempPath(),"MI-content-cache-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(fixtureRoot);
  Console.WriteLine("FIXTURE "+fixtureRoot);
  try{Run();return 0;}catch(Exception error){Console.Error.WriteLine(error);return 1;}
 }
}
