using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Runtime.CompilerServices;
using BepInEx.Logging;
using MoreIterators;

public class RainWorldGame {}
public static class ShutdownFaults {
 public static readonly List<string> Calls=new List<string>();
 public static readonly HashSet<string> Fail=new HashSet<string>();
 public static void Run(string name){Calls.Add(name);if(Fail.Contains(name))throw new InvalidOperationException("cleanup failure: "+name);}
 public static void Reset(){Calls.Clear();Fail.Clear();}
}
namespace MoreIterators {
 public static class CreatorRuntime {public static bool Panel=true;public static string CurrentRoom="TEST_AI";}
 public static class StudioRuntime {public static void ReleaseCapture(){ShutdownFaults.Run("capture");}}
 public static class CreatorVoice {public static void Shutdown(){ShutdownFaults.Run("voice");}}
 public static class CreatorAudio {public static void Shutdown(){ShutdownFaults.Run("audio");}}
 public static class CreatorOverseers {public static void Shutdown(){ShutdownFaults.Run("overseers");}}
 public static class CreatorProjections {public static void Shutdown(){ShutdownFaults.Run("projections");}}
 public static partial class CreatorControlPanel {
  public sealed class Overlay {public void ShutDownProcess(){ShutdownFaults.Run("panel");}}
  static Overlay overlay;static object game;static string room;
  public static void Prepare(){overlay=new Overlay();game=new object();room="TEST_AI";CreatorRuntime.Panel=true;}
  public static bool Released {get{return overlay==null&&game==null&&room==null&&!CreatorRuntime.Panel;}}
 }
 public partial class ShutdownPlugin {
  readonly List<Action> removeHooks=new List<Action>();bool hooksInstalled=true;
  void RestorePreviewSession(){ShutdownFaults.Run("restore");}
  void StopAllCoroutines(){ShutdownFaults.Run("coroutines");}
  public void Prepare(){hooksInstalled=true;removeHooks.Add(()=>ShutdownFaults.Run("hook-first"));removeHooks.Add(()=>ShutdownFaults.Run("hook-last"));}
  public void Disable(){OnDisable();}
  public bool Released {get{return removeHooks.Count==0&&!hooksInstalled;}}
 }
}
public static class ShutdownCleanupCheck {
 static int checks;
 static readonly Exception NativeError=new InvalidOperationException("native shutdown error");
 static void Check(bool value,string label){checks++;if(!value)throw new Exception(label);}
 [MethodImpl(MethodImplOptions.NoInlining)] static void NativeFailure(RainWorldGame game){ShutdownFaults.Run("native");throw NativeError;}
 static ManualLogSource Logger(){var log=new ManualLogSource("More Iterators");MiDiagnostics.Initialize(log);return log;}
 static void GameShutdown(){
  foreach(bool fail in new[]{false,true}){
   ShutdownFaults.Reset();var log=Logger();CreatorControlPanel.Prepare();if(fail)ShutdownFaults.Fail.Add("panel");
   var game=new RainWorldGame();ShutdownPlugin.GameClose(g=>{Check(g==game,"same native game argument");ShutdownFaults.Run("native");},game);
   Check(String.Join(",",ShutdownFaults.Calls)=="panel,native","panel failure never skips/repeats original");
   Check(CreatorControlPanel.Released,"panel references detached before native close");
   CreatorControlPanel.Close();Check(ShutdownFaults.Calls.Count==2,"failed panel is not closed again");
   Check(log.Errors.Count==(fail?1:0),"only actual MI cleanup failure logged");
  }
  foreach(bool failLog in new[]{false,true}){
   ShutdownFaults.Reset();var log=Logger();log.FailError=failLog;CreatorControlPanel.Prepare();ShutdownFaults.Fail.Add("panel");
   Exception caught=null;try{ShutdownPlugin.GameClose(NativeFailure,new RainWorldGame());}catch(Exception error){caught=error;}
   Check(Object.ReferenceEquals(caught,NativeError),"native exception survives cleanup and log failures");
   Check(caught.StackTrace.Contains("NativeFailure"),"original throwing location preserved");
   Check(String.Join(",",ShutdownFaults.Calls)=="panel,native","native failure invoked exactly once");
  }
  ShutdownFaults.Reset();var brokenLog=Logger();MiDiagnostics.SetLevel("trace");brokenLog.FailInfo=brokenLog.FailError=true;CreatorControlPanel.Prepare();
  ShutdownPlugin.GameClose(g=>ShutdownFaults.Run("native"),new RainWorldGame());
  Check(String.Join(",",ShutdownFaults.Calls)=="panel,native","trace log failure cannot prevent cleanup/native close");
  brokenLog.FailInfo=brokenLog.FailError=false;MiDiagnostics.SetLevel("info");
 }
 static void Disable(){
  string[] stages={"restore","coroutines","capture","panel","overseers","projections","voice","audio","hook-last","hook-first"};
#if PLAYBACK
  stages=stages.Where(s=>s!="coroutines"&&s!="capture").ToArray();
#endif
  foreach(bool failLog in new[]{false,true}){
   ShutdownFaults.Reset();var log=Logger();log.FailError=failLog;var plugin=new ShutdownPlugin();plugin.Prepare();CreatorControlPanel.Prepare();
   foreach(string stage in stages)ShutdownFaults.Fail.Add(stage);
   plugin.Disable();Check(ShutdownFaults.Calls.SequenceEqual(stages),"every cleanup stage runs despite all earlier failures");
   Check(plugin.Released&&CreatorControlPanel.Released,"hooks/panel ownership cleared");
   Check(log.Errors.Count==(failLog?0:stages.Length),"all cleanup failures logged when logger works");
   Check(typeof(MiDiagnostics).GetField("log",BindingFlags.Static|BindingFlags.NonPublic).GetValue(null)==null,"diagnostic logger released last");
   ShutdownFaults.Reset();plugin.Disable();Check(!ShutdownFaults.Calls.Any(x=>x.StartsWith("hook-")||x=="panel"),"repeat disable does not remove old hooks or close panel twice");
  }
 }
 public static void Main(){GameShutdown();Disable();Console.WriteLine(checks+" shutdown cleanup assertions passed");}
}
