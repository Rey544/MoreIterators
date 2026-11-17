using System;
using System.Collections.Generic;
using System.IO;
using MoreIterators;
namespace UnityEngine { public struct Color {public float a;public Color(float alpha){a=alpha;}} public struct Vector2 { public float x,y; public Vector2(float a,float b){x=a;y=b;} } public static class Application {public static string opened;public static void OpenURL(string url){opened=url;}} }
namespace BepInEx {public static class Paths {public static string BepInExRootPath;}}
public class FContainer {public float concatenatedAlpha=1;}
public class FShader {public string name="Basic";}
public class FAtlasElement { public string name="Circle20"; }
public class FSprite { public float x,y,scaleX=1,scaleY=1,rotation,alpha=1;public UnityEngine.Color color=new UnityEngine.Color(1);public FShader shader=new FShader(); public bool isVisible=true;public bool throwDepth;public int depth { get { if(throwDepth)throw new InvalidOperationException("bad depth");return 1; } }public FContainer container=new FContainer();public FAtlasElement element=new FAtlasElement(); }
public class TriangleMesh:FSprite {public bool customColor=true;public UnityEngine.Color[] verticeColors={new UnityEngine.Color(1),new UnityEngine.Color(1)}; public UnityEngine.Vector2[] vertices={new UnityEngine.Vector2(-3,4),new UnityEngine.Vector2(5,9)}; }
public class AbstractRoom {public string name="TEST_AI";}
public class RainWorldGame {public RoomCamera[] cameras;}
public class Room {public AbstractRoom abstractRoom=new AbstractRoom();public RainWorldGame game;}
public class Oracle { public Room room=new Room();public object[] bodyChunks=new object[2]; }
public class OracleGraphics { public int firstBodyChunkSprite;public bool culled;public Oracle oracle=new Oracle();public int neckSprite=2,HeadSprite=3,ChinSprite=4,robeSprite=5;public int EyeSprite(int side){return 6+side;}public int HandSprite(int side,int part){return 8+side*2+part;}public int FootSprite(int side,int part){return 12+side*2+part;} }
public class RoomCamera { public class SpriteLeaser { public FSprite[] sprites; } public Room room;public int cameraNumber;public FSprite levelGraphic,fullScreenEffect;public Dictionary<string,FContainer> layers=new Dictionary<string,FContainer>();public FContainer ReturnFContainer(string name){FContainer value;return layers.TryGetValue(name,out value)?value:null;} }
namespace MoreIterators {
 public class IteratorLayers { public bool robe=false,body=true; }
 public class IteratorDesign { public string projectId="project-a",oracleId="oracle-a";public IteratorLayers layers=new IteratorLayers();public static IteratorDesign Current;public static IteratorDesign ForRoom(Room room){return Current;} }
 public static class CreatorRuntime {public static string Id(string room){return "oracle-a";}}
 public static class StudioRuntime {public static OracleGraphics Graphics;public static RoomCamera.SpriteLeaser Sprites;}
 public static class UiText {public static string Get(string key){return key;}}
 public static class CreatorWardrobe { public static int Start(int n){return n+70;} }
 public static class MiDiagnostics { public static List<string> info=new List<string>();public static string Context(Room r){return "room=TEST_AI";}public static void Info(string n,string text){info.Add(text);}public static void Debug(string n,string text){info.Add(text);} }
}
static class Check {
 static DateTime now=new DateTime(2026,1,1);static OracleGraphics g=new OracleGraphics();static IteratorDesign d=new IteratorDesign();static RoomCamera.SpriteLeaser s=new RoomCamera.SpriteLeaser();
 static void Assert(bool condition,string error){if(!condition)throw new Exception(error);}
 static void Observe(double seconds){OracleSpriteDiagnostics.ObserveAt(g,s,2,d,now.AddSeconds(seconds));}
 static void Run(string[] args){
  s.sprites=new FSprite[100];for(int i=0;i<100;i++)s.sprites[i]=new FSprite();s.sprites[72]=new TriangleMesh();s.sprites[78]=new TriangleMesh();s.sprites[42]=new TriangleMesh();
  Observe(0);Assert(MiDiagnostics.info.Count==1,"first healthy sample");
  for(int i=1;i<500;i++){s.sprites[0].x=i;s.sprites[1].rotation=i;Observe(i*.001);}
  Assert(MiDiagnostics.info.Count==1,"ordinary animation must not log");
  Assert(MiDiagnostics.info[0].Contains("project=project-a")&&MiDiagnostics.info[0].Contains("frontL{visible=1 bounds=-3,4..5,9"),"identity and cloth bounds");
  s.sprites[0].isVisible=false;Observe(.6);Assert(MiDiagnostics.info.Count==1,"state-change rate limit");Observe(2);
  Assert(MiDiagnostics.info.Count==2&&MiDiagnostics.info[1].Contains("body0=Hidden"),"hidden category");
  Observe(5);Assert(MiDiagnostics.info.Count==2,"persistent failure must not spam");
  s.sprites[0].isVisible=true;Observe(6);s.sprites[0].isVisible=false;Observe(8);
  Assert(MiDiagnostics.info.Count==4,"recovery/reoccurrence recorded");
  s.sprites[0].alpha=0;s.sprites[0].scaleY=0;s.sprites[0].x=Single.NaN;s.sprites[0].container=null;Observe(10);
  string text=MiDiagnostics.info[4];Assert(text.Contains("NonFinite")&&text.Contains("MissingContainer")&&text.Contains("Transparent")&&text.Contains("ZeroScale"),"classify failure boundaries");
  Assert(!s.sprites[0].isVisible&&s.sprites[0].alpha==0&&s.sprites[0].scaleY==0&&Single.IsNaN(s.sprites[0].x)&&s.sprites[0].container==null&&!d.layers.robe,"read-only state");
  s.sprites[1]=null;Observe(12);Assert(MiDiagnostics.info[5].Contains("body1=MissingSprite"),"missing sprite safe");
  d.projectId="project-b";Observe(12.1);Assert(MiDiagnostics.info[6].Contains("project=project-b"),"new project immediate snapshot");
  d.layers=null;d.projectId="null-layers";Observe(14.2);Assert(MiDiagnostics.info[7].Contains("robeEnabled=<missing>"),"missing layers safe");
  var failing=new OracleGraphics();s.sprites[0].throwDepth=true;
  OracleSpriteDiagnostics.Observe(failing,s,2,d);Assert(MiDiagnostics.info.Count==9&&MiDiagnostics.info[8].Contains("observation-failed"),"observation failure logged without escaping renderer");
  d.projectId="project-c";OracleSpriteDiagnostics.Observe(failing,s,2,d);Assert(MiDiagnostics.info.Count==9,"observation failure logged once");
  OracleSpriteDiagnostics.Observe(null,s,2,d);OracleSpriteDiagnostics.Observe(g,null,2,d);OracleSpriteDiagnostics.Observe(g,s,2,null);
  s.sprites[0].throwDepth=false;d.projectId="<script>project</script>";s.sprites[0].element.name="ink<&>";
  string report=OracleRenderReport.Build(g,s,d,now);
  Assert(report.Contains("&lt;script&gt;project&lt;/script&gt;")&&!report.Contains("<script>"),"HTML author values are escaped");
  Assert(report.Contains("ink&lt;&amp;&gt;")&&report.Contains("NaN")&&report.Contains("<td>Torso 1</td>")&&!report.Contains("game.panel."),"report exposes raw diagnostic states with English source labels");
  Assert(!s.sprites[0].isVisible&&s.sprites[0].alpha==0&&s.sprites[0].scaleY==0&&d.layers==null,"report never changes the project or sprites");
  BepInEx.Paths.BepInExRootPath=args[0];StudioRuntime.Graphics=g;StudioRuntime.Sprites=s;IteratorDesign.Current=d;
  bool rejected=false;try{OracleSpriteDiagnostics.OpenReport("wrong-oracle");}catch(InvalidOperationException){rejected=true;}
  Assert(rejected&&UnityEngine.Application.opened==null,"wrong iterator cannot open a stale report");
  OracleSpriteDiagnostics.OpenReport("oracle-a");
  string file=new Uri(UnityEngine.Application.opened).LocalPath;
  Assert(File.Exists(file)&&File.ReadAllText(file).Contains("&lt;script&gt;"),"F8 writes the escaped snapshot and opens its local URI");
  PartialOpacity();
  Console.WriteLine("Sprite diagnostic boundaries passed");
 }
 static void PartialOpacity(){
  g=new OracleGraphics();d=new IteratorDesign();s=new RoomCamera.SpriteLeaser();
  s.sprites=new FSprite[100];for(int i=0;i<s.sprites.Length;i++)s.sprites[i]=new FSprite();
  int start=MiDiagnostics.info.Count;Observe(0);
  s.sprites[0].alpha=.5f;Observe(.5);
  Assert(MiDiagnostics.info.Count==start+1,"partial opacity respects the existing throttle");
  Observe(2);
  Assert(MiDiagnostics.info.Count==start+2&&MiDiagnostics.info[start+1].Contains("alpha=0.5"),"partial opacity changes must be captured");
  Assert(MiDiagnostics.info[start+1].Contains("body0=None"),"partial opacity is diagnostic information, not classified as a failure");
  s.sprites[0].alpha=.5001f;s.sprites[0].x=85;Observe(4);
  Assert(MiDiagnostics.info.Count==start+2,"tiny opacity noise and motion must not spam logs");
  s.sprites[0].container.concatenatedAlpha=.4f;Observe(5);
  Assert(MiDiagnostics.info.Count==start+3&&MiDiagnostics.info[start+2].Contains("parentAlpha=0.4"),"parent opacity changes are captured");
  s.sprites[0].shader.name="CustomDepth";Observe(7);
  Assert(MiDiagnostics.info.Count==start+4&&MiDiagnostics.info[start+3].Contains("shader=CustomDepth"),"shader changes are captured");
  s.sprites[0].color=new UnityEngine.Color(.6f);Observe(9);
  Assert(MiDiagnostics.info.Count==start+5&&MiDiagnostics.info[start+4].Contains("colorAlpha=0.6"),"color alpha changes are captured");
  var gown=new TriangleMesh();gown.verticeColors[0]=new UnityEngine.Color(.2f);gown.verticeColors[1]=new UnityEngine.Color(.8f);s.sprites[g.robeSprite]=gown;Observe(11);
  Assert(MiDiagnostics.info.Count==start+6&&MiDiagnostics.info[start+5].Contains("vertexAlpha=0.2..0.8"),"gown vertex alpha is captured even with opaque body");
  gown.verticeColors[1]=new UnityEngine.Color(.4f);Observe(13);
  Assert(MiDiagnostics.info.Count==start+7&&MiDiagnostics.info[start+6].Contains("vertexAlpha=0.2..0.4"),"vertex-only changes are captured");
  string report=OracleRenderReport.Build(g,s,d,now);
  foreach(string heading in new[]{"Color opacity","Parent opacity","Shader","Vertex opacity"})Assert(report.Contains("<th>"+heading+"</th>"),"report includes "+heading);
  Assert(report.Contains("CustomDepth")&&report.Contains("0.2..0.4"),"report includes raw material and vertex data");
  Assert(s.sprites[0].alpha==.5001f&&s.sprites[0].color.a==.6f&&s.sprites[0].container.concatenatedAlpha==.4f&&s.sprites[0].shader.name=="CustomDepth"&&gown.verticeColors[1].a==.4f,"sampling and report never overwrite authored opacity or render state");
  s.sprites[0].shader.name="shader<&>";report=OracleRenderReport.Build(g,s,d,now);Assert(report.Contains("shader&lt;&amp;&gt;"),"shader labels are escaped in HTML");
  var cam=new RoomCamera{room=g.oracle.room,cameraNumber=1,levelGraphic=new FSprite(),fullScreenEffect=new FSprite()};
  cam.layers["Midground"]=s.sprites[0].container;cam.levelGraphic.shader.name="LevelColor";cam.fullScreenEffect.shader.name="Test<&>";cam.fullScreenEffect.alpha=.5f;
  g.oracle.room.game=new RainWorldGame{cameras=new[]{cam}};report=OracleRenderReport.Build(g,s,d,now);
  Assert(report.Contains("Camera 1 / Midground")&&report.Contains("Room image material")&&report.Contains("LevelColor")&&report.Contains("Test&lt;&amp;&gt;")&&report.Contains("Opacity: 0.5"),"same-room camera materials and named layers are captured");
  Assert(cam.fullScreenEffect.alpha==.5f&&cam.levelGraphic.shader.name=="LevelColor","camera capture is read-only");
 }
 static int Main(string[] args){try{Run(args);return 0;}catch(Exception error){Console.Error.WriteLine(error.GetType().FullName+": "+error.Message);return 1;}}
}
