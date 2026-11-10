using System;
using System.Collections.Generic;
using MoreIterators;
public abstract class ConfigAcceptableBase {public abstract object Clamp(object value);}
 
public class ConfigAcceptableList<T>:ConfigAcceptableBase {public T[] Values;public ConfigAcceptableList(params T[] values){Values=values;}public override object Clamp(object value){foreach(T allowed in Values)if(Object.Equals(allowed,value))return value;return Values[0];}}
public class ConfigurableInfo {public string Description;public ConfigAcceptableBase Acceptable;public ConfigurableInfo(string description,ConfigAcceptableBase acceptable=null,string autoTab="",params object[] tags){Description=description;Acceptable=acceptable;}}
public class Configurable<T> {T current;public Menu.Remix.MixedUI.OnEventHandler OnChange;public ConfigurableInfo Info;public Configurable(T value,ConfigurableInfo info){Info=info;Value=value;}public T Value{get{return current;}set{value=Info.Acceptable==null?value:(T)Info.Acceptable.Clamp(value);if(EqualityComparer<T>.Default.Equals(current,value))return;current=value;if(OnChange!=null)OnChange();}}}
public class ConfigHolder {public string Key;public Configurable<T> Bind<T>(string name,T value,ConfigurableInfo info){Key=name;return new Configurable<T>(value,info);}}
public class OptionInterface {public ConfigHolder config=new ConfigHolder();public Menu.Remix.MixedUI.OpTab[] Tabs;public virtual void Initialize(){}}
public class RainWorld {}
public static class ModManager {public static bool InitializationScreenFinished;}
public enum FLabelAlignment {Left}
namespace UnityEngine {public struct Vector2{public float x,y;public Vector2(float a,float b){x=a;y=b;}}}
namespace RWCustom {public static class Custom {public static RainWorld rainWorld=new RainWorld();}}
namespace Menu.Remix.MixedUI {
 public delegate void OnEventHandler();
 public class OpTab {public List<object> Items=new List<object>();public string Name;public OpTab(OptionInterface owner,string name){Name=name;}public void AddItems(params object[] values){Items.AddRange(values);}}
 public class OpLabel {public string Text;public OpLabel(UnityEngine.Vector2 p,UnityEngine.Vector2 s,string text,FLabelAlignment align){Text=text;}}
 public class OpComboBox {public string[] Values;public OpComboBox(Configurable<string> value,UnityEngine.Vector2 pos,float width,string[] values){Values=values;}}
}
public static class MachineConnector {
 public static int Registrations,Reloads;public static string Id,Saved="trace";public static bool Accept=true;
 public static OptionInterface Registered;
 public static bool SetRegisteredOI(string id,OptionInterface options){Registrations++;if(!Accept)return false;Id=id;Registered=options;return true;}
 public static void ReloadConfig(OptionInterface options){Reloads++;((MiOptions)options).DiagnosticLevel.Value=Saved;}
 public static void SaveConfig(OptionInterface options){Saved=((MiOptions)options).DiagnosticLevel.Value;}
}
namespace On {public static class RainWorld {
 public delegate void orig_OnModsInit(global::RainWorld self);public delegate void hook_OnModsInit(orig_OnModsInit orig,global::RainWorld self);
 public static event hook_OnModsInit OnModsInit;public static int Calls;
 public static void Raise(){orig_OnModsInit orig=self=>Calls++;if(OnModsInit!=null)OnModsInit(orig,RWCustom.Custom.rainWorld);else orig(RWCustom.Custom.rainWorld);}
}}
namespace MoreIterators {
 public static class RuntimePaths {public const string ModId="moreiterators.core";}
 public static class UiText {public static string Get(string value){return "translated:"+value;}public static void Use(RainWorld rw){}}
 public static class MiDiagnostics {public static string Level="info";public static int Errors;public static void SetLevel(string level){Level=level;}public static void Report(string code,string operation,Exception error,string context){Errors++;}}
}
class DiagnosticOptionsCheck {
 static int checks;static void Check(bool value,string label){if(!value)throw new Exception(label);checks++;}
 static void Main(string[] args){
  string stored=args.Length==0?"trace":args[0];MachineConnector.Saved=stored;
  string expected=stored=="infor"?"info":stored;
  var blank=new MiOptions();Check(blank.DiagnosticLevel.Value=="info","default");
  Check(blank.config.Key=="DiagnosticLevel","existing configuration key retained");
  var acceptable=(ConfigAcceptableList<string>)blank.DiagnosticLevel.Info.Acceptable;Check(String.Join(",",acceptable.Values)=="info,debug,trace","exact choices");
  blank.Initialize();Check(blank.Tabs.Length==1&&blank.Tabs[0].Items.Count==2,"only label and one control");
  Check(((Menu.Remix.MixedUI.OpLabel)blank.Tabs[0].Items[0]).Text=="translated:Diagnostic level","native translation wrapper");
  Check(String.Join(",",((Menu.Remix.MixedUI.OpComboBox)blank.Tabs[0].Items[1]).Values)=="info,debug,trace","dropdown contains no legacy spelling");
  var cleanup=new List<Action>();MiOptions.Install(cleanup);Check(MachineConnector.Registrations==0,"wait for ModsInit");
  On.RainWorld.Raise();Check(On.RainWorld.Calls==1,"original once");Check(MachineConnector.Id==RuntimePaths.ModId&&MachineConnector.Registrations==1&&MachineConnector.Reloads==1,"native registration and config loading");
  var live=(MiOptions)MachineConnector.Registered;
  Check(MiDiagnostics.Level==expected&&live.DiagnosticLevel.Value==expected,"saved setting loaded and normalized");
  MachineConnector.SaveConfig(live);Check(MachineConnector.Saved==expected,"new save uses normalized value");
  foreach(string level in new[]{"info","debug","trace"}){
   live.DiagnosticLevel.Value=level;Check(MiDiagnostics.Level==level,"change event applied for "+level);
   MachineConnector.SaveConfig(live);var reloaded=new MiOptions();MachineConnector.ReloadConfig(reloaded);
   Check(reloaded.DiagnosticLevel.Value==level,"saved choice reloads as "+level);
  }
  live.DiagnosticLevel.Value="debug";
  On.RainWorld.Raise();Check(On.RainWorld.Calls==2&&MachineConnector.Registrations==1&&MiDiagnostics.Level=="debug","no duplicate registration or reload over current choice");
  cleanup[0]();On.RainWorld.Raise();Check(On.RainWorld.Calls==3&&MachineConnector.Registrations==1,"unsubscribe leaves original callback");
  Check(MiDiagnostics.Errors==0,"no diagnostic failures");Console.WriteLine(checks+" options assertions passed");
 }
}
