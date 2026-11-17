using System;
using System.IO;
using System.Collections.Generic;

namespace UnityEngine { public static class Time { public static float realtimeSinceStartup=1; } }
public class AbstractRoom { public string name="TEST_AI"; }
public class Room { public AbstractRoom abstractRoom=new AbstractRoom(); }
public class Camera { public Room room=new Room(); }
public class RainWorldGame { public Camera[] cameras={new Camera()}; }
public static class Json
{
    public static int Reads;
    public static object Deserialize(string text){Reads++;return new System.Web.Script.Serialization.JavaScriptSerializer().DeserializeObject(text);}
    public static string Serialize(object value){return new System.Web.Script.Serialization.JavaScriptSerializer().Serialize(value);}
}
namespace MoreIterators
{
    using UnityEngine;
    public static class MoreIteratorsPlugin {public static bool Active=true;public static string SelectedRoom="TEST_AI";}
    public static class IteratorCatalog {public static object Find(string room){return new object();}}
    public class IteratorDesign {public string projectId="sample";public static IteratorDesign ForRoom(Room room){return new IteratorDesign();}}
    public class Pose {public bool hasMark;}
    public static class StudioRuntime {public static Pose Pose=new Pose();}
    public static class MiDiagnostics {public static List<string> Errors=new List<string>();public static void Report(string code,string method,Exception error,string context){Errors.Add(code);}}
    public static class CreatorRuntime
    {
        public static string Root,CurrentRoom="TEST_AI",Mode="silent",Behavior="work";
        public static bool Paused,Panel=true,Mark=true,RearGlow=true,Lightning=true,Pearls=true,Glyphs=true;
        public static float PalettePreview=-1;
        static float nextPoll,nextHeartbeat;
        static string control="";
        public static bool FailPose;
        public static int PoseAttempts;
        public static bool CanControl {get{return CurrentRoom=="TEST_AI";}}
        public static void SyncPose(){PoseAttempts++;if(FailPose)throw new IOException("fixture pose handoff failed");}
        __GET__
        __TICK__
    }
}
public static class CreatorControlRetryCheck
{
    static int checks;
    static void Check(bool value,string message){checks++;if(!value)throw new Exception(message);}
    static void Tick(RainWorldGame game){UnityEngine.Time.realtimeSinceStartup+=1;MoreIterators.CreatorRuntime.Tick(game);}
    public static int Main(string[] args)
    {
        try
        {
            MoreIterators.CreatorRuntime.Root=args[1];Directory.CreateDirectory(args[1]);var game=new RainWorldGame();
            if(args[0]=="parse")
            {
                File.WriteAllText(Path.Combine(args[1],"control.json"),"{broken");Tick(game);Tick(game);
                Check(Json.Reads==2,"failed unchanged JSON is retried rather than cached");Check(MoreIterators.MiDiagnostics.Errors.FindAll(x=>x=="MI-CONTROL-001").Count==2,"failed parse keeps diagnostics");
                File.WriteAllText(Path.Combine(args[1],"control.json"),"{\"mode\":\"story\"}");Tick(game);Tick(game);
                Check(MoreIterators.CreatorRuntime.Mode=="story"&&MoreIterators.CreatorRuntime.PoseAttempts==1,"corrected control applies once");Check(Json.Reads==3,"successful text is cached");
            }
            else if(args[0]=="apply")
            {
                File.WriteAllText(Path.Combine(args[1],"control.json"),"{\"mode\":\"story\",\"hasMark\":false}");MoreIterators.CreatorRuntime.FailPose=true;Tick(game);
                MoreIterators.CreatorRuntime.FailPose=false;Tick(game);Tick(game);
                Check(MoreIterators.CreatorRuntime.PoseAttempts==2,"same command retries after pose application failed");Check(Json.Reads==2,"successful application ends retries");Check(!MoreIterators.CreatorRuntime.Mark&&!MoreIterators.StudioRuntime.Pose.hasMark,"control fields still apply through existing Get logic");
            }
            else if(args[0]=="empty")
            {
                var variants=new RainWorldGame[]{null,new RainWorldGame{cameras=null},new RainWorldGame{cameras=new Camera[0]},new RainWorldGame{cameras=new Camera[]{null}},new RainWorldGame{cameras=new[]{new Camera{room=null}}},new RainWorldGame{cameras=new[]{new Camera{room=new Room{abstractRoom=null}}}}};
                foreach(var value in variants){MoreIterators.CreatorRuntime.Panel=true;MoreIterators.CreatorRuntime.CurrentRoom="old";Tick(value);Check(!MoreIterators.CreatorRuntime.Panel&&MoreIterators.CreatorRuntime.CurrentRoom=="","missing view clears stale control ownership");}
                Check(Json.Reads==0&&MoreIterators.MiDiagnostics.Errors.Count==0,"expected missing game state returns before file IO or exception reporting");
            }
            else throw new ArgumentException();
            Console.WriteLine("control checks passed: "+checks);return 0;
        }
        catch(Exception error){Console.Error.WriteLine(error);return 1;}
    }
}
