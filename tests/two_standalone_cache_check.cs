using System;
using System.IO;
using System.Collections.Generic;
using System.Threading;

public static class ModManager {
 public sealed class Mod {
  public string id,path,basePath,version,targetGameVersion,TargetedPath,NewestPath;
  public bool enabled=true,hasTargetedVersionFolder,hasNewestFolder;public int loadOrder;
  public Mod(string id,string path){this.id=id;this.path=path;}
 }
 public static bool InitializationScreenFinished=true;
 public static List<Mod> ActiveMods=new List<Mod>();
}
namespace UnityEngine {
 public static class Application {public static string persistentDataPath="unused";}
 public static class Debug {public static void LogWarning(object value){}}
}
public static class UiText {public static string Get(string value){return value;}}
public static class MiDiagnostics {public static void Warn(string code,string node,string detail,string context){}}
public static class IteratorIntegrations {public static bool Native(string id){return false;}}
public static class TwoStandaloneCacheCheck {
 static int assertions;
 static void Check(bool value,string message){if(!value)throw new Exception(message);assertions++;}
 static void Write(string root,string name){Directory.CreateDirectory(Path.Combine(root,"moreiterators"));File.WriteAllText(Path.Combine(root,"moreiterators/registry.json"),"[{\"projectId\":\"same-id\",\"name\":\""+name+"\",\"ai\":\"SAME_AI\",\"entry\":\"SAME_ENTRY\",\"oracleId\":\"same-oracle\"}]");}
 static string NameA(){var p=PackA.IteratorCatalog.Projects();return p.Count==0?"":PackA.IteratorCatalog.Text(p[0],"name");}
 static string NameB(){var p=PackB.IteratorCatalog.Projects();return p.Count==0?"":PackB.IteratorCatalog.Text(p[0],"name");}
 public static int Main(string[] args){
  try{
   string a=Path.Combine(args[1],"pack-a"),b=Path.Combine(args[1],"pack-b");AssetManager.Root=Path.Combine(args[1],"game");Directory.CreateDirectory(AssetManager.Root);
   Write(a,"A original");Write(b,"B original");var ma=new ModManager.Mod("pack.a",a);var mb=new ModManager.Mod("pack.b",b);ModManager.ActiveMods.Add(ma);ModManager.ActiveMods.Add(mb);
   Check(NameA()=="A original"&&NameB()=="B original","two production templates keep same filenames and record IDs isolated");
   var pa=PackA.IteratorCatalog.Projects();var pb=PackB.IteratorCatalog.Projects();
   Check(!Object.ReferenceEquals(pa,pb),"generated namespaces hold separate cache objects");
   Check(PackA.IteratorCatalog.Text(pa[0],"ownerMod")=="pack.a"&&PackB.IteratorCatalog.Text(pb[0],"ownerMod")=="pack.b","both production templates keep their owner identity");
   for(int i=0;i<1000;i++)Check(Object.ReferenceEquals(pa,PackA.IteratorCatalog.Projects())&&Object.ReferenceEquals(pb,PackB.IteratorCatalog.Projects()),"interleaved hot calls do not cross package caches");
   Write(a,"A edited longer");Thread.Sleep(300);Check(NameA()=="A edited longer"&&NameB()=="B original","editing A refreshes A without substituting B");
   ModManager.ActiveMods.Reverse();Check(NameA()=="A edited longer"&&NameB()=="B original","native load reorder preserves each independent owner");
   ma.enabled=false;Check(NameA()==""&&NameB()=="B original","disabling A immediately empties only A");
   ma.enabled=true;Check(NameA()=="A edited longer"&&NameB()=="B original","reenabling A restores only A");
   string moved=Path.Combine(args[1],"moved-b");Write(moved,"B moved");mb.path=moved;
   Check(NameA()=="A edited longer"&&NameB()=="B moved","moving B invalidates its own root while A stays isolated");
   File.WriteAllText(Path.Combine(moved,"moreiterators/registry.json"),"{}");Thread.Sleep(300);
   Check(NameB()==""&&NameA()=="A edited longer","failed B refresh never falls back to A or stale B");
   Write(moved,"B recovered");Check(NameB()=="B recovered","B parser failure retries without cached empty result");
   ModManager.InitializationScreenFinished=false;Check(NameA()==""&&NameB()=="","unready initialization invalidates both runtime caches");
   ModManager.InitializationScreenFinished=true;Check(NameA()=="A edited longer"&&NameB()=="B recovered","both generated runtimes recover when initialization is ready");
   Console.WriteLine("PASS "+assertions+" two-production-runtime assertions");return 0;
  }catch(Exception error){Console.Error.WriteLine("FAIL "+error.Message);return 1;}
 }
}
