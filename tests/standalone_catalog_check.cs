using System;
using System.IO;
using System.Collections.Generic;
using MoreIterators;

 
 
public static class ModManager {
 public class Mod {public string id,path,TargetedPath,NewestPath;public bool hasTargetedVersionFolder,hasNewestFolder;public Mod(string id,string path){this.id=id;this.path=path;}}
 public static List<Mod> ActiveMods;
}
namespace UnityEngine {
 public static class Application {public static string persistentDataPath="unused";}
 public static class Debug {public static readonly List<string> Warnings=new List<string>();public static void LogWarning(object value){Warnings.Add(value.ToString());}}
}
namespace MoreIterators {
 public static class IteratorIntegrations {public static bool Native(string id){return false;}}
 public static class MiDiagnostics {public static void Warn(string code,string node,string detail,string context){UnityEngine.Debug.LogWarning(code+": "+detail);}}
}

public static class StandaloneCatalogCheck {
 static int count;
 static void Check(bool value,string label){if(!value)throw new Exception(label);count++;}
 static string Record(string id){return "{\"projectId\":\""+id+"\",\"name\":\""+id+"\",\"ai\":\""+id+"_AI\",\"entry\":\""+id+"_ENTRY\",\"oracleId\":\""+id+"\",\"ownerMod\":\"wrong.owner\"}";}
 static void Write(string root,string json){Directory.CreateDirectory(Path.Combine(root,"moreiterators"));File.WriteAllText(Path.Combine(root,"moreiterators/registry.json"),json);}
 static void Enable(string root){ModManager.ActiveMods=new List<ModManager.Mod>{new ModManager.Mod(RuntimePaths.ModId,root)};}
 static void Main(string[] args){
  string root=args[1],other=Path.Combine(root,"other");AssetManager.Root=Path.Combine(root,"assets");Directory.CreateDirectory(AssetManager.Root);
  switch(args[0]){
   case "early":
    ModManager.ActiveMods=null;Check(IteratorCatalog.Projects().Count==0,"null startup registry is safe");
    ModManager.ActiveMods=new List<ModManager.Mod>();Check(IteratorCatalog.Projects().Count==0,"empty startup registry is safe");
    Write(root,"["+Record("selected")+"]");Enable(root);
    Check(IteratorCatalog.Projects().Count==1,"projects appear after enabling without restarting process");
    Check(IteratorCatalog.Find("selected_ENTRY")!=null,"entry is discoverable after startup");
    Check(IteratorCatalog.IsAI("selected_AI"),"AI is discoverable after startup");
    Check(UnityEngine.Debug.Warnings.Count==0,"normal startup emits no failure warning");break;
   case "missing":
    Enable(root);Check(IteratorCatalog.Projects().Count==0,"missing file does not escape into game hook");
    Check(UnityEngine.Debug.Warnings.Count==1,"missing file is logged");
    Check(UnityEngine.Debug.Warnings[0].Contains(RuntimePaths.ModId)&&UnityEngine.Debug.Warnings[0].Contains(root),"warning identifies package and location");
    Check(IteratorCatalog.Projects().Count==0&&UnityEngine.Debug.Warnings.Count==1,"identical failure does not flood log");
    Write(root,"["+Record("recovered")+"]");System.Threading.Thread.Sleep(300);Check(IteratorCatalog.Find("recovered_ENTRY")!=null,"missing registry is retried after bounded cache refresh");break;
   case "malformed":
    Enable(root);Write(root,"{}");Check(IteratorCatalog.Projects().Count==0,"invalid top-level JSON does not commit cache");
    Write(root,"["+Record("partial")+",false]");Check(IteratorCatalog.Projects().Count==0,"partial project list is not committed");
    Write(root,"["+Record("fixed")+"]");Check(IteratorCatalog.Projects().Count==1,"fixed JSON is retried");
    Check(IteratorCatalog.Find("partial_AI")==null&&IteratorCatalog.Find("fixed_AI")!=null,"only fully loaded registry becomes visible");break;
   case "isolation":
    Write(root,"["+Record("mine")+"]");Write(other,"["+Record("foreign")+"]");
    ModManager.ActiveMods=new List<ModManager.Mod>{new ModManager.Mod("other.content",other)};
    Check(IteratorCatalog.Projects().Count==0,"does not fall back to other enabled content mod");
    ModManager.ActiveMods.Add(new ModManager.Mod(RuntimePaths.ModId,root));
    Check(IteratorCatalog.Projects().Count==1,"only this package projects are loaded");
    Check(IteratorCatalog.Find("foreign_AI")==null,"foreign room cannot be entered from this catalogue");
    Check(IteratorCatalog.Text(IteratorCatalog.Projects()[0],"ownerMod")==RuntimePaths.ModId,"owner is always current content package");
    ModManager.ActiveMods.RemoveAt(1);Check(IteratorCatalog.Projects().Count==0,"disabled package does not retain cached entries");
    bool threw=false;try{var value=RuntimePaths.ContentRoot;}catch(InvalidOperationException){threw=true;}Check(threw,"design lookup cannot fall back while disabled");
    Enable(root);Check(IteratorCatalog.Find("mine_ENTRY")!=null,"reenabling loads own registry");
    Enable(other);Check(IteratorCatalog.Find("foreign_ENTRY")!=null&&IteratorCatalog.Find("mine_ENTRY")==null,"changed active installation path invalidates cache");break;
   case "versions":
    string newest=Path.Combine(root,"newest"),targeted=Path.Combine(root,"targeted");
    Write(root,"["+Record("base")+"]");Write(newest,"["+Record("newest")+"]");Write(targeted,"["+Record("targeted")+"]");Write(other,"["+Record("foreign")+"]");
    Enable(root);var selected=ModManager.ActiveMods[0];selected.NewestPath=newest;selected.TargetedPath=targeted;selected.hasNewestFolder=selected.hasTargetedVersionFolder=true;
    ModManager.ActiveMods.Add(new ModManager.Mod("other.content",other));
    Check(IteratorCatalog.Find("targeted_AI")!=null&&IteratorCatalog.Projects().Count==1,"targeted registry wins within owner despite higher priority foreign package");
    File.Delete(Path.Combine(targeted,"moreiterators/registry.json"));System.Threading.Thread.Sleep(300);Check(IteratorCatalog.Find("newest_AI")!=null&&IteratorCatalog.Find("targeted_AI")==null,"removed targeted registry falls back to newest and invalidates resolved path cache");
    string newestRegistry=Path.Combine(newest,"moreiterators/registry.json");
    Write(newest,"["+Record("edited")+"]");File.SetLastWriteTimeUtc(newestRegistry,new DateTime(2030,1,1));
    Check(IteratorCatalog.Find("edited_AI")!=null&&IteratorCatalog.Find("newest_AI")==null,"changed registry timestamp reloads same path");
    selected.hasNewestFolder=false;Check(IteratorCatalog.Find("base_AI")!=null,"disabling newest version returns to package root");break;
   case "designs":
    string custom="content/selected-design.json",target=Path.Combine(root,"targeted"),foreign=Path.Combine(other,custom);
    Write(root,"["+Record("mine").Replace("\"ownerMod\":", "\"design\":\""+custom+"\",\"ownerMod\":")+"]");
    Directory.CreateDirectory(Path.GetDirectoryName(Path.Combine(root,custom)));File.WriteAllText(Path.Combine(root,custom),"base");
    Directory.CreateDirectory(Path.GetDirectoryName(Path.Combine(target,custom)));File.WriteAllText(Path.Combine(target,custom),"targeted");
    Directory.CreateDirectory(Path.GetDirectoryName(foreign));File.WriteAllText(foreign,"foreign");
    Enable(root);ModManager.ActiveMods[0].TargetedPath=target;ModManager.ActiveMods[0].hasTargetedVersionFolder=true;ModManager.ActiveMods.Add(new ModManager.Mod("other.content",other));
    Check(File.ReadAllText(RuntimePaths.DesignPath("mine"))=="targeted","registry design relative path resolves targeted owner asset");
    File.Delete(Path.Combine(target,custom));System.Threading.Thread.Sleep(300);Check(File.ReadAllText(RuntimePaths.DesignPath("mine"))=="base","custom design falls back inside its owner");
    File.Delete(Path.Combine(root,custom));System.Threading.Thread.Sleep(300);Check(RuntimePaths.DesignPath("mine")==null,"missing own design never falls back to foreign package");
    string legacy=Path.Combine(root,"designs/legacy.json");Directory.CreateDirectory(Path.GetDirectoryName(legacy));File.WriteAllText(legacy,"legacy");
    Check(File.ReadAllText(RuntimePaths.DesignPath("legacy"))=="legacy","legacy package without design field retains designs/id convention");
    ModManager.ActiveMods.RemoveAt(0);bool designThrew=false;try{RuntimePaths.DesignPath("mine");}catch(InvalidOperationException){designThrew=true;}Check(designThrew,"disabled package cannot resolve designs");break;
   default:throw new ArgumentException("Unknown scenario");
  }
  Console.WriteLine(count+" catalogue assertions passed: "+args[0]);
 }
}
