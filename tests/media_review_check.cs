using System;
using System.IO;
using System.Collections.Generic;
using System.Reflection;
using System.Security.Cryptography;
using UnityEngine;
using MoreIterators;

namespace UnityEngine
{
    public static class Time { public static float realtimeSinceStartup; }
    public static class Mathf { public static float Clamp01(float v) { return Math.Max(0, Math.Min(1, v)); } }
    public struct Vector2 { public float x,y; public Vector2(float a,float b) { x=a;y=b; } }
    public static class Debug { public static void Log(object value) {} }
}
public static class ModManager { public static object ActiveMods = new object(); public static bool MSC = true; }
public static class AssetManager { public static string Root; public static string ResolveFilePath(string path) { return Path.Combine(Root,path); } }
public static class Json
{
    public static int Reads;
    public static object Deserialize(string text) { Reads++; return new System.Web.Script.Serialization.JavaScriptSerializer().DeserializeObject(text); }
}
namespace MoreSlugcats
{
    public static class MoreSlugcatsEnums { public static class PlacedObjectType { public static readonly object WhiteToken = new object(); } }
    public static class ChatlogData
    {
        public sealed class ChatlogID
        {
            public sealed class Entries { public readonly List<string> entries = new List<string>(); }
            public static readonly Entries values = new Entries();
            public static int Created, Removed;
            public readonly string value;
            public ChatlogID(string id,bool register) { value=id;Created++;if(register&&!values.entries.Contains(id))values.entries.Add(id); }
            public void Unregister() { values.entries.Remove(value);Removed++; }
        }
    }
}
public class PlacedObject { public Vector2 pos; public object data; public PlacedObject(object type,object unused) {} }
public class CollectToken
{
    public class CollectTokenData { public bool isWhite; public string tokenString; public Vector2 handlePos; public CollectTokenData(PlacedObject p,bool b) {} }
    public class Stalk { public int Destroyed; public void Destroy() { Destroyed++; } }
    public Stalk stalk;
    public bool destroyed;
    public static readonly List<CollectToken> Created = new List<CollectToken>();
    public CollectToken(Room room,PlacedObject data) { Created.Add(this); }
    public void Destroy() { destroyed=true; }
}
public class Room
{
    public AbstractRoom abstractRoom = new AbstractRoom();
    public RainWorldGame game = new RainWorldGame();
    public float PixelWidth=960, PixelHeight=720;
    public void AddObject(object item) {}
}
public class AbstractRoom { public string name = "TEST_AI"; }
public class RainWorldGame { public bool IsStorySession=true; public Camera[] cameras = {new Camera()}; public List<AbstractPlayer> Players = new List<AbstractPlayer>(); }
public class Camera { public HUD.HUD hud = new HUD.HUD(); }
public class AbstractPlayer { public Player realizedCreature; }
public class Player
{
    public MoreSlugcats.ChatlogData.ChatlogID chatlogID;
    public bool chatlog;
    public Room room;
    public int mushroomCounter,chatlogCounter;
    public void Stun(int frames) {}
}
namespace HUD { public class HUD { public object chatLog;public List<object> parts=new List<object>(); } }
namespace Music
{
    public class Source { public float volume=1; }
    public class Track { public Source source=new Source(); }
    public class Song { public Track[] subTracks={new Track()}; }
    public class MusicPlayer { public Song song=new Song(),proceduralMusic=new Song(); }
}
namespace On
{
    public static class Player { public delegate void orig_ProcessChatLog(global::Player player); }
    namespace Music
    {
        public static class MusicPlayer
        {
            public delegate void orig_Update(global::Music.MusicPlayer player);
            public delegate void hook_Update(orig_Update orig,global::Music.MusicPlayer player);
            public static event hook_Update Update;
            public static int Originals;
            public static void Run(global::Music.MusicPlayer player) { if(Update!=null)Update(delegate { Originals++; },player); }
        }
    }
}
namespace MoreIterators
{
    public class BroadcastPage { public object[] lines=new object[0]; }
    public class BroadcastProject { public string id,schema,uid,runtimeId,room; public int revision;public float x,y;public BroadcastPage[] pages; }
    public class CreatorBroadcastDisplay { public CreatorBroadcastDisplay(HUD.HUD hud,BroadcastProject project) {} }
    public static class PearlProjectCodec { public static T ReadObject<T>(object value) { return new System.Web.Script.Serialization.JavaScriptSerializer().ConvertToType<T>(value); } }
    public static class PlaybackMode { public static bool Enabled; }
    public static class RuntimePaths { public static string DataDirectory,ModId="own"; }
    public class ContentAsset { public string path,owner; }
    public static class ContentAssets
    {
        public static int Generation;
        public static readonly List<ContentAsset> Assets=new List<ContentAsset>();
        public static List<ContentAsset> Files(string directory,string extension,string owner=null)
        {
            return Assets.FindAll(a => a.path.Replace('\\','/').Contains(directory+"/")&&a.path.EndsWith(extension)&& (owner==null||a.owner==owner));
        }
        public static bool Managed(string owner) { return PlaybackMode.Enabled?owner==RuntimePaths.ModId:owner!="foreign"; }
    }
    public static class MiDiagnostics { public static readonly List<string> Errors=new List<string>();public static void Report(string code,string method,Exception error,string context) { Errors.Add(code+":"+error.GetType().Name); } }
    public class CreatorAudioChannel
    {
        public Music.MusicPlayer Player;
        public int Priority,Polls,Applications,Stops;
        public bool Alive=true,CanPlay=true,StopOnPoll,Selected;
        public bool Live(Music.MusicPlayer player) { return Alive&&Player==player; }
        public void Poll() { Polls++;if(StopOnPoll)Stop(); }
        public void Apply(bool selected) { Applications++;Selected=selected; }
        public void Stop() { Stops++;CanPlay=false;Player=null;CreatorAudio.Remove(this); }
    }
}
public static class MediaReviewCheck
{
    static int checks;
    static void Check(bool value,string reason) { checks++;if(!value)throw new Exception(reason); }
    static string Id(char c) { return "MoreIterators_Broadcast_"+new string(c,32); }
    static string Broadcast(char c,int revision) { return "{\"schema\":\"moreiterators.broadcast.v1\",\"id\":\""+c+"\",\"uid\":\""+new string(c,32)+"\",\"runtimeId\":\""+Id(c)+"\",\"room\":\"TEST_AI\",\"revision\":"+revision+",\"pages\":[{\"lines\":[]}]}"; }
    static string Write(string root,string name,string content) { string path=Path.Combine(root,name);Directory.CreateDirectory(Path.GetDirectoryName(path));File.WriteAllText(path,content);return path; }
    static void Advance() { Time.realtimeSinceStartup+=2; }
    static object Field(Type type,string name) { return type.GetField(name,BindingFlags.NonPublic|BindingFlags.Static).GetValue(null); }
    static void Cache(string root)
    {
        string path=Write(root,"broadcasts/a.json",Broadcast('a',1));
        var original=CreatorBroadcastCatalog.All()[0];int reads=Json.Reads;
        Advance();Check(Object.ReferenceEquals(original,CreatorBroadcastCatalog.All()[0]),"unchanged broadcast reuses parsed project");
        Check(Json.Reads==reads,"unchanged broadcast body not read again");
        Check(MoreSlugcats.ChatlogData.ChatlogID.Created==1,"unchanged ID creates no new enum object");
        File.WriteAllText(path,Broadcast('a',22));Advance();Check(CreatorBroadcastCatalog.All()[0].revision==22,"changed file reloads revision");
        Check(Json.Reads==reads+1,"only modified file is parsed");
        File.Delete(path);Advance();Check(CreatorBroadcastCatalog.All().Count==0,"deleted file is absent");
        Check(MoreSlugcats.ChatlogData.ChatlogID.values.entries.Contains(Id('a'))&&MoreSlugcats.ChatlogData.ChatlogID.Removed==0,"deleted broadcast keeps enum identity for live objects and saves");
        Check(((System.Collections.IDictionary)Field(typeof(CreatorBroadcastCatalog),"files")).Count==0,"deleted file cache removed");
        Write(root,"broadcasts/b.json",Broadcast('b',1));new MoreSlugcats.ChatlogData.ChatlogID(Id('b'),true);Advance();CreatorBroadcastCatalog.All();
        File.Delete(Path.Combine(root,"broadcasts/b.json"));Advance();CreatorBroadcastCatalog.All();
        Check(MoreSlugcats.ChatlogData.ChatlogID.values.entries.Contains(Id('b')),"foreign existing registration is never unregistered");
        string owned=Write(root,"pack/moreiterators/broadcasts/c.json",Broadcast('c',1));
        ContentAssets.Assets.Add(new ContentAsset{path=owned,owner="own"});ContentAssets.Generation++;Check(CreatorBroadcastCatalog.All().Count==1,"context change refreshes without waiting one second");
        ContentAssets.Assets.Clear();ContentAssets.Generation++;Check(CreatorBroadcastCatalog.All().Count==0,"removed provider has no stale cached broadcasts");
    }
    static void Token(string root)
    {
        string path=Write(root,"broadcasts/a.json",Broadcast('a',1));var room=new Room();
        CreatorBroadcastRuntime.Tick(room);var first=CollectToken.Created[0];Check(first.stalk==null,"fixture starts partially constructed token");
        File.WriteAllText(path,Broadcast('a',22));Advance();CreatorBroadcastRuntime.Tick(room);Check(first.destroyed,"revision removes token with null stalk");
        var second=CollectToken.Created[1];File.Delete(path);Advance();CreatorBroadcastRuntime.Tick(room);Check(second.destroyed,"deletion removes token with null stalk");
        var table=Field(typeof(CreatorBroadcastRuntime),"rooms");object[] arguments={room,null};Check((bool)table.GetType().GetMethod("TryGetValue").Invoke(table,arguments),"room state exists");
        var state=arguments[1];Check(((System.Collections.IDictionary)state.GetType().GetField("revisions").GetValue(state)).Count==0,"deleted revision entries are removed");
        CreatorBroadcastRuntime.Tick(null);room.abstractRoom=null;CreatorBroadcastRuntime.Tick(room);checks+=2;
    }
    static string Audio(string root,byte[] bytes,string owner)
    {
        string id;using(var hash=SHA256.Create())id=BitConverter.ToString(hash.ComputeHash(bytes)).Replace("-","").ToLowerInvariant();
        string path=Path.Combine(root,owner,"mi_audio",id+".mp3");Directory.CreateDirectory(Path.GetDirectoryName(path));File.WriteAllBytes(path,bytes);ContentAssets.Assets.Add(new ContentAsset{path=path,owner=owner});return id;
    }
    static void Asset(string root)
    {
        byte[] bytes=new byte[40];bytes[0]=73;bytes[1]=68;bytes[2]=51;string id=Audio(root,bytes,"own");
        string path=CreatorAudio.Resolve(id);
        using(var locked=new FileStream(path,FileMode.Open,FileAccess.ReadWrite,FileShare.None))Check(CreatorAudio.Resolve(id)==path,"verified unchanged audio does not reopen or hash its bytes");
        File.WriteAllBytes(path,new byte[41]);bool bad=false;try{CreatorAudio.Resolve(id);}catch(InvalidDataException){bad=true;}Check(bad,"changed audio is rehashed and rejected");
        File.WriteAllBytes(path,bytes);File.SetLastWriteTimeUtc(path,DateTime.UtcNow.AddSeconds(4));CreatorAudio.Resolve(id);
        using(var locked=new FileStream(path,FileMode.Open,FileAccess.ReadWrite,FileShare.None))
        { ContentAssets.Generation++;bad=false;try{CreatorAudio.Resolve(id);}catch(IOException){bad=true;}Check(bad,"changed provider context invalidates hash cache"); }
        ContentAssets.Assets.Clear();string foreign=Audio(root,bytes,"foreign");bad=false;try{CreatorAudio.Resolve(foreign);}catch(FileNotFoundException){bad=true;}Check(bad,"main runtime cannot take another independent pack audio");
        Audio(root,bytes,"own");PlaybackMode.Enabled=true;ContentAssets.Generation++;Check(CreatorAudio.Resolve(id).Contains("own"),"playback resolves its own matching asset");
        ContentAssets.Assets.RemoveAll(a=>a.owner=="own");ContentAssets.Generation++;bad=false;try{CreatorAudio.Resolve(id);}catch(FileNotFoundException){bad=true;}Check(bad,"playback refuses another pack fallback");
    }
    static void Snapshot(string root)
    {
        CreatorAudio.Enable();var player=new Music.MusicPlayer();var a=new CreatorAudioChannel{Player=player,Priority=10};var b=new CreatorAudioChannel{Player=player,Priority=20};CreatorAudio.Register(a);CreatorAudio.Register(b);
        On.Music.MusicPlayer.Run(player);object first=Field(typeof(CreatorAudio),"channelSnapshot");On.Music.MusicPlayer.Run(player);
        Check(Object.ReferenceEquals(first,Field(typeof(CreatorAudio),"channelSnapshot")),"stable channels reuse snapshot between frames");Check(b.Selected&&!a.Selected,"priority winner preserved");Check(On.Music.MusicPlayer.Originals==2,"native update executes exactly once each frame");
        a.StopOnPoll=true;On.Music.MusicPlayer.Run(player);Check(a.Stops==1&&b.Applications==3,"removing during poll safely finishes snapshot iteration");
        On.Music.MusicPlayer.Run(player);Check(!Object.ReferenceEquals(first,Field(typeof(CreatorAudio),"channelSnapshot")),"membership change rebuilds snapshot");Check(b.Applications==4,"remaining channel continues");
        CreatorAudio.Shutdown();Check(b.Stops==1,"shutdown stops remaining channel");Check(((System.Collections.ICollection)Field(typeof(CreatorAudio),"channels")).Count==0,"shutdown clears channel list");
    }
    public static int Main(string[] args)
    {
        RuntimePaths.DataDirectory=args[1];AssetManager.Root=args[1];
        try { if(args[0]=="cache")Cache(args[1]);else if(args[0]=="token")Token(args[1]);else if(args[0]=="asset")Asset(args[1]);else if(args[0]=="snapshot")Snapshot(args[1]);else throw new ArgumentException();Console.WriteLine("media checks passed: "+checks);return 0; }
        catch(Exception error) { Console.Error.WriteLine(error);return 1; }
    }
}
