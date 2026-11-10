using System;
using System.IO;
using System.Collections;
namespace UnityEngine {
 public class Object {public static int destroyed;public static void Destroy(object value){destroyed++;}}
 public class Texture2D {public int width,height;public static int reads;public Texture2D(int w,int h,TextureFormat f,bool mip){width=w;height=h;}public void ReadPixels(Rect r,int x,int y,bool mip){reads++;}public void Apply(bool mip){}}
 public enum TextureFormat {RGB24}
 public static class ImageConversion {public static byte[] EncodeToPNG(Texture2D value){return new byte[]{1,2,3};}}
 public struct Rect {public Rect(float x,float y,float w,float h){}}
 public struct Vector2 {public float x,y;public Vector2(float x,float y){this.x=x;this.y=y;}public static Vector2 zero{get{return new Vector2();}}public static Vector2 up{get{return new Vector2(0,1);}}public Vector2 normalized{get{return this;}}public float sqrMagnitude{get{return x*x+y*y;}}public static Vector2 operator +(Vector2 a,Vector2 b){return new Vector2(a.x+b.x,a.y+b.y);}public static Vector2 operator -(Vector2 a,Vector2 b){return new Vector2(a.x-b.x,a.y-b.y);}public static Vector2 operator *(Vector2 a,float n){return new Vector2(a.x*n,a.y*n);}}
 public static class Mathf {public const float Deg2Rad=.01745329f;public static float Sin(float n){return (float)Math.Sin(n);}public static float Cos(float n){return (float)Math.Cos(n);}public static int Clamp(int n,int min,int max){return Math.Max(min,Math.Min(max,n));}public static float Min(float a,float b){return Math.Min(a,b);}}
 public static class Time {public static float realtimeSinceStartup;}
 public class WaitForEndOfFrame {}
 public struct Resolution {public int width,height;}
 public static class Screen {public static int width=1000,height=800;public static bool fullScreen;public static Resolution currentResolution;public static void SetResolution(int w,int h,bool f){}}
 public static class JsonUtility {public static T FromJson<T>(string s){return default(T);}}
}
public static class Futile {public static float displayScaleInverse=1;}
public class FSprite {public UnityEngine.Vector2 LocalToScreen(UnityEngine.Vector2 v){return new UnityEngine.Vector2(400,400);}}
public class RoomCamera {public class SpriteLeaser {public FSprite[] sprites={new FSprite(),new FSprite(),new FSprite()};}}
public class BodyChunk {public UnityEngine.Vector2 pos,lastPos,vel;public void HardSetPosition(UnityEngine.Vector2 p){pos=p;}}
public class AbstractRoom {public string name="XX_AI";}
public class ProcessManager {public object currentMainLoop=new RainWorldGame(false);}
public class RainWorldGame {public ProcessManager manager;public RainWorldGame(bool withManager=true){if(withManager)manager=new ProcessManager();}}
public class Room {public AbstractRoom abstractRoom=new AbstractRoom();public RainWorldGame game=new RainWorldGame();}
public class Oracle {public Room room=new Room();public bool slatedForDeletetion;public BodyChunk[] bodyChunks={new BodyChunk(),new BodyChunk()};public BodyChunk firstChunk{get{return bodyChunks[0];}}}
public class OracleGraphics {public Oracle oracle=new Oracle();public BodyChunk head=new BodyChunk();public BodyChunk[] hands={new BodyChunk(),new BodyChunk()};public int HeadSprite=0;public int HandSprite(int side,int index){return side+1;}}
namespace MoreIterators {
 public static class RuntimePaths {public static string DataDirectory;}
 public static class MoreIteratorsPlugin {public static bool IsChamber(string n){return true;}}
 public class IteratorDesign {public static IteratorDesign Current=new IteratorDesign();public string oracleId="test",previewToken="token";}
 public static class MiDiagnostics {public static void Report(string a,string b,Exception e,string c){throw new Exception(a,e);}}
}
public static class StudioCaptureCheck {
 static void Check(bool value,string why){if(!value)throw new Exception(why);}
 static void Step(IEnumerator capture,float time){UnityEngine.Time.realtimeSinceStartup=time;capture.MoveNext();}
 public static void Main(string[] args){
  string root=args[0];MoreIterators.RuntimePaths.DataDirectory=root;Directory.CreateDirectory(root);
  string request=Path.Combine(root,"studio-frame-request");var now=DateTime.UtcNow;
  var demand=new MoreIterators.StudioCaptureDemand();Check(!demand.WantsFrame(root,0,now),"no consumer should be idle");
  File.WriteAllText(request,"");File.SetLastWriteTimeUtc(request,now);
  Check(demand.WantsFrame(root,1,now),"new consumer did not activate");
  Check(!demand.WantsFrame(root,5,now.AddSeconds(4)),"closed consumer did not expire");
  File.SetLastWriteTimeUtc(request,now.AddSeconds(5));Check(demand.WantsFrame(root,6,now.AddSeconds(5)),"new request did not resume");
  Check(!demand.WantsFrame(root,7,now),"future timestamp must not keep capture active");File.Delete(request);
  MoreIterators.StudioRuntime.Graphics=new OracleGraphics();MoreIterators.StudioRuntime.Sprites=new RoomCamera.SpriteLeaser();
  var capture=MoreIterators.StudioRuntime.Capture(null);capture.MoveNext();
  for(int i=1;i<=80;i++)Step(capture,i*.1f);
  Check(UnityEngine.Texture2D.reads==0&&!File.Exists(Path.Combine(root,"studio-frame.png")),"idle capture still reads GPU or writes frame");
  File.WriteAllText(request,"");Step(capture,9);Check(UnityEngine.Texture2D.reads==1&&File.Exists(Path.Combine(root,"studio-frame.png")),"consumer did not receive actual capture");
  File.SetLastWriteTimeUtc(request,DateTime.UtcNow.AddSeconds(-4));Step(capture,10);int reads=UnityEngine.Texture2D.reads;
  for(int i=1;i<=40;i++)Step(capture,10+i*.1f);
  Check(UnityEngine.Texture2D.reads==reads&&UnityEngine.Object.destroyed==1,"expired consumer still captures or retains GPU buffer");
  File.SetLastWriteTimeUtc(request,DateTime.UtcNow);Step(capture,15);Check(UnityEngine.Texture2D.reads==reads+1,"capture did not resume after timeout");
  MoreIterators.StudioRuntime.Pose.recording=true;Step(capture,16);Check(UnityEngine.Texture2D.reads==reads+1,"recording exclusion changed");
  ((IDisposable)capture).Dispose();Check(UnityEngine.Object.destroyed==2,"capture shutdown did not release buffer");
  Console.WriteLine("studio capture demand and actual coroutine passed");
 }
}
