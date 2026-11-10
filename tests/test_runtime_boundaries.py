
import os
import re
import shutil
import string
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


HARNESS = r'''
using System;
using System.IO;
using System.Collections.Generic;
using MoreIterators;

namespace UnityEngine {
 public class Object {public bool destroyed;public static void Destroy(Object value){if(value!=null)value.destroyed=true;}}
 public class Texture2D:Object {
  public static readonly List<Texture2D> Created=new List<Texture2D>();
  public int width,height;public FilterMode filterMode;public TextureWrapMode wrapMode;Color[] pixels;
  public Texture2D(int w,int h,TextureFormat format,bool mipmap){width=w;height=h;Created.Add(this);}
  public Color[] GetPixels(){if(pixels==null){pixels=new Color[width*height];for(int i=0;i<pixels.Length;i++)pixels[i]=Color.white;}return pixels;}
  public void SetPixels(Color[] value){pixels=value;}public void Apply(){}
 }
 public enum TextureFormat {ARGB32}public enum FilterMode {Point,Bilinear}public enum TextureWrapMode {Clamp}
 public static class ImageConversion {
  // Unity's native decoder is replaced only at this boundary. These markers
  // let the tests fail decoding after earlier atlases have already staged.
  public static bool LoadImage(Texture2D texture,byte[] data){if(data.Length==0||data[0]==0)return false;texture.width=texture.height=data[0];return true;}
 }
 public struct Color {public float r,g,b,a;public Color(float r,float g,float b,float a){this.r=r;this.g=g;this.b=b;this.a=a;}public static Color white{get{return new Color(1,1,1,1);}}public static Color black{get{return new Color(0,0,0,1);}}public static Color Lerp(Color a,Color b,float value){return a;}}
 public static class ColorUtility {public static bool TryParseHtmlString(string value,out Color color){color=Color.white;return !String.IsNullOrEmpty(value);}}
 public struct Rect {public float x,y,width,height;public Rect(float x,float y,float w,float h){this.x=x;this.y=y;width=w;height=h;}}
 public struct Vector2 {
  public float x,y;public Vector2(float x,float y){this.x=x;this.y=y;}
  public static Vector2 operator +(Vector2 a,Vector2 b){return new Vector2(a.x+b.x,a.y+b.y);}
  public static Vector2 operator -(Vector2 a,Vector2 b){return new Vector2(a.x-b.x,a.y-b.y);}
  public static Vector2 operator *(Vector2 a,float b){return new Vector2(a.x*b,a.y*b);}
 }
 public static class Mathf {public static int Clamp(int n,int a,int b){return Math.Max(a,Math.Min(n,b));}public static float Clamp(float n,float a,float b){return Math.Max(a,Math.Min(n,b));}public static float Clamp01(float n){return Clamp(n,0,1);}public static float Pow(float n,float p){return (float)Math.Pow(n,p);}public static float Min(float a,float b){return Math.Min(a,b);}}
 public static class Application {public static string persistentDataPath;}
 public static class Time {public static float realtimeSinceStartup=10;}
 public static class Debug {public static void LogWarning(object value){}public static void Log(object value){}}
}
public sealed class AtlasManager {
 public readonly Dictionary<string,UnityEngine.Texture2D> Atlases=new Dictionary<string,UnityEngine.Texture2D>();
 public int LoadAttempts,FailLoadAttempt=-1;
 public bool DoesContainAtlas(string key){return Atlases.ContainsKey(key);}
 public void LoadAtlasFromTexture(string key,UnityEngine.Texture2D texture,bool asset){LoadAttempts++;if(LoadAttempts==FailLoadAttempt)throw new InvalidOperationException("Injected atlas registration failure");if(Atlases.ContainsKey(key))throw new Exception("Duplicate atlas");Atlases.Add(key,texture);}
 public void UnloadAtlas(string key){UnityEngine.Texture2D texture;if(Atlases.TryGetValue(key,out texture)){UnityEngine.Object.Destroy(texture);Atlases.Remove(key);}}
}
public static class Futile {public static readonly AtlasManager atlasManager=new AtlasManager();}
public sealed class FContainer {public void AddChild(FSprite sprite){}}
public sealed class FSprite {public UnityEngine.Color color;public float alpha,anchorX,anchorY,scaleX,scaleY,x,y,scale;public FSprite(string name){}public void RemoveFromContainer(){}}
public sealed class Room {public AbstractRoom abstractRoom=new AbstractRoom();}
public sealed class AbstractRoom {public string name;}
public sealed class ProcessManager {public RainWorld rainWorld=new RainWorld();public string LastDialog;public void ShowDialog(Menu.DialogNotify dialog){LastDialog=dialog.text;}}
public sealed class RainWorld {public Options options=new Options();public PlayerProgression progression=new PlayerProgression();public InGameTranslator inGameTranslator;public RainWorld(){inGameTranslator=new InGameTranslator(this);}public static Dictionary<string,int> roomNameToIndex=new Dictionary<string,int>();}
namespace RWCustom {public static class Custom {public static RainWorld rainWorld;public static string RootFolderDirectory(){return AssetManager.Root;}}}
public sealed class PlayerProgression {public string[] regionNames=new string[0];}
public sealed class Options {public UnityEngine.Vector2 ScreenSize=new UnityEngine.Vector2(1366,768);public InGameTranslator.LanguageID language=InGameTranslator.LanguageID.Chinese;}
public static class AssetManager {
 public static string Root;public static bool Fail;
 public static string GetConsoleFilesSubfolder(){return "";}
 static IEnumerable<string> Roots(){
  yield return Path.Combine(Root,"mergedmods");
  for(int i=ModManager.ActiveMods.Count-1;i>=0;i--){
   var mod=ModManager.ActiveMods[i];
   if(mod.hasTargetedVersionFolder)yield return mod.TargetedPath;
   if(mod.hasNewestFolder)yield return mod.NewestPath;
   yield return mod.path;
  }
  yield return Root;
 }
 public static string[] ListDirectory(string path,bool directories=false,bool includeAll=false){
  var files=new List<string>();var names=new HashSet<string>(StringComparer.OrdinalIgnoreCase);
  foreach(string root in Roots()){
   string directory=Path.Combine(root,path);if(!Directory.Exists(directory))continue;
   foreach(string file in directories?Directory.GetDirectories(directory):Directory.GetFiles(directory))if(includeAll||names.Add(Path.GetFileName(file)))files.Add(file);
  }
  return files.ToArray();
 }
 public static string ResolveFilePath(string path){
  if(Fail)throw new IOException("原始系统错误");
  foreach(string root in Roots()){string file=Path.Combine(root,path);if(File.Exists(file))return file;}
  return Path.Combine(Root,path);
 }
}
public static class WorldLoader {public static string FindRoomFile(string room,bool root,string suffix,bool warn=true){foreach(string p in new[]{"world/"+room.Split('_')[0].ToLowerInvariant()+"-rooms/"+room+suffix,"levels/"+room+suffix}){string full=AssetManager.ResolveFilePath(p);if(File.Exists(full))return full;}return null;}}
public static class ModManager {public static bool MSC;public sealed class Mod {public string id,path,TargetedPath,NewestPath;public bool hasTargetedVersionFolder,hasNewestFolder;public Mod(string id,string path){this.id=id;this.path=path;}}public static readonly List<Mod> ActiveMods=new List<Mod>();}
namespace BepInEx {public static class Paths {public static string ConfigPath;}}
namespace MoreSlugcats {public sealed class NamespaceMarker {}}
namespace Menu {
 public static class CapturedText {public static readonly List<string> Values=new List<string>();}
 public class MenuObject {public void RemoveSprites(){}}
 public sealed class ButtonBehavior {public bool greyedOut;}
 public class SimpleButton:MenuObject {public ButtonBehavior buttonBehav=new ButtonBehavior();}
 public sealed class MenuLabel:MenuObject {public MenuLabel(MainMenu menu,Page page,string text,UnityEngine.Vector2 position,UnityEngine.Vector2 size,bool large){CapturedText.Values.Add(text);}}
 public sealed class DialogNotify {public string text;public DialogNotify(string text,UnityEngine.Vector2 size,ProcessManager manager,Action callback){this.text=text;}}
 public sealed class Page {public List<MenuObject> subObjects=new List<MenuObject>();public FContainer Container=new FContainer();public void RemoveSubObject(MenuObject obj){subObjects.Remove(obj);}}
 public sealed class MainMenu {public ProcessManager manager=new ProcessManager();public List<Page> pages=new List<Page>{new Page()};}
}
namespace MoreIterators {
 public static class MiDiagnostics {
  public static readonly List<string> Codes=new List<string>();
  public static readonly List<Exception> Errors=new List<Exception>();
  public static readonly List<string> Warnings=new List<string>();
  public static void Info(string node,string context){Codes.Add(node);}
  public static void Report(string code,string node,Exception error,string context){Codes.Add(code);Errors.Add(error);}
  public static void Warn(string code,string node,string detail,string context){Codes.Add(code);Warnings.Add(detail);}
 }
 public sealed class NecklaceDesign {public string name="";}public sealed class NecklacePearl {public string name="";}public sealed class GarmentDesign {public string name="";}
 // Appearance rendering is outside these loader/atlas tests; only serialized dependencies are needed.
 public sealed class GradientStop {public float position;public string color="#ffffff";}
 public sealed class ColorGradient {public bool enabled;public GradientStop[] stops=new GradientStop[0];}
 public sealed class CornerGlow {public bool enabled;public string color="#ffffff";public float opacity=.18f,radius=.5f;}
 public sealed class RoomGradient {public bool enabled;public string direction="radial";public float opacity=.18f;public ColorGradient ramp=new ColorGradient();public CornerGlow[] corners=new CornerGlow[0];}
 public sealed class PearlAccessoryBead {public string color="",highlight="";public bool dual;public float size,position;public int chain=-1;}
 public sealed class PearlAccessoryChild {public string name="",png="",color="";public bool enabled=true;public int bead;public float x,y,width,height,rotation;}
 public sealed class PearlAccessoryDesign {public string id="",name="",anchor="head",stringColor="";public bool enabled=true;public PearlAccessoryBead[] beads=new PearlAccessoryBead[0];public PearlAccessoryChild[] children=new PearlAccessoryChild[0];}
 public class IteratorIntegration {public UnityEngine.Color Cloth(IteratorDesign design,float value){return UnityEngine.Color.white;}}
 public static class IteratorIntegrations {public static bool Native(string id){return false;}public static IteratorIntegration ForId(string id){return null;}}
 public static class NativeRoomProjects {public static bool Available(Dictionary<string,object> value){return true;}public static bool IsNative(Dictionary<string,object> value){return value!=null&&IteratorCatalog.Text(value,"nativeOracle")!="";}}
 public static class CreatorRuntime {public static string Root{get{return RuntimePaths.DataDirectory;}}public static List<Dictionary<string,object>> Projects(){return IteratorCatalog.Projects();}public static string Id(string room){return IteratorCatalog.Id(room);}public static bool Signal(Menu.MainMenu menu,string signal){return false;}}
 public static class PlaybackMode {public static bool Enabled;}
 public sealed class CreatorMenuButton:Menu.SimpleButton {public CreatorMenuButton(Menu.MainMenu menu,Menu.Page owner,string text,string signal,UnityEngine.Vector2 position,UnityEngine.Vector2 size){Menu.CapturedText.Values.Add(text);}}
 public static class CreatorBroadcastCatalog {public static readonly List<BroadcastProject> Items=new List<BroadcastProject>();public static List<BroadcastProject> All(){return Items;}}
 public static class CreatorPearlCatalog {public static readonly List<PearlProject> Items=new List<PearlProject>();public static List<PearlProject> All(){return Items;}}
}

static class BoundaryCheck {
 static int assertions,sequence;static readonly List<string> logs=new List<string>();
 static void Check(bool value,string detail){if(!value)throw new Exception(detail);assertions++;}
 static bool SamePath(string first,string second){return first!=null&&second!=null&&String.Equals(Path.GetFullPath(first),Path.GetFullPath(second),StringComparison.OrdinalIgnoreCase);}
 static string Image(byte marker){return Convert.ToBase64String(new[]{marker});}
 static void Write(string path,string data){Directory.CreateDirectory(Path.GetDirectoryName(path));File.WriteAllText(path,data);}
 static Dictionary<string,object> Design(string face,string antenna,string halo){return new Dictionary<string,object>{{"schema","moreiterators.oracle.v1"},{"oracleId","sample"},{"projectId","test"},{"facePng",face},{"antennaPng",antenna},{"haloPng",halo}};}
 static void Apply(Dictionary<string,object> data){string path=RuntimePaths.DesignPath("sample");Write(path,Json.Serialize(data));File.SetLastWriteTimeUtc(path,new DateTime(2030,1,1).AddSeconds(++sequence));UnityEngine.Time.realtimeSinceStartup+=2;IteratorDesign.Select("sample");IteratorDesign.Poll(logs.Add);}
 static int AliveTextures(){int count=0;foreach(var texture in UnityEngine.Texture2D.Created)if(!texture.destroyed)count++;return count;}
 static IteratorDesign DecodeDesign(Dictionary<string,object> data){
  var design=new IteratorDesign();
  var read=typeof(IteratorDesign).GetMethod("ReadFields",System.Reflection.BindingFlags.Static|System.Reflection.BindingFlags.NonPublic,null,new[]{typeof(object),typeof(Dictionary<string,object>)},null);
  try{read.Invoke(null,new object[]{design,data});}catch(System.Reflection.TargetInvocationException error){throw error.InnerException;}
  return design;
 }
 static object Sample(Type type,int depth){
  if(depth>12)throw new Exception("Recursive model in serialized design: "+type.Name);
  if(type==typeof(string))return "serialized value";
  if(type==typeof(bool))return true;
  if(type==typeof(int))return 17;
  if(type==typeof(float))return 1.25f;
  if(type.IsArray)return new object[]{Sample(type.GetElementType(),depth+1)};
  var fields=type.GetFields(System.Reflection.BindingFlags.Public|System.Reflection.BindingFlags.Instance);
  Check(fields.Length>0,"complex model exposes serialized fields: "+type.Name);
  var result=new Dictionary<string,object>();foreach(var field in fields)result[field.Name]=Sample(field.FieldType,depth+1);return result;
 }
 static object Snapshot(object value){
  if(value==null||value is string||value is bool||value is int||value is float)return value;
  var list=value as System.Collections.IList;if(list!=null){var result=new List<object>();foreach(var item in list)result.Add(Snapshot(item));return result;}
  var fields=new Dictionary<string,object>();foreach(var field in value.GetType().GetFields(System.Reflection.BindingFlags.Public|System.Reflection.BindingFlags.Instance))fields[field.Name]=Snapshot(field.GetValue(value));return fields;
 }
 static void DesignSchema(){
  // Exercise every currently reachable model type, including one entry in each
  // array. A new complex field cannot silently omit its decoder dispatch.
  var expected=(Dictionary<string,object>)Sample(typeof(IteratorDesign),0);
  var data=(Dictionary<string,object>)Json.Deserialize(Json.Serialize(expected));
  var decoded=DecodeDesign(data);
  Check(Json.Serialize(Snapshot(decoded))==Json.Serialize(expected),"every serialized field survives the real design decoder");
  Check(decoded.voice.bank=="serialized value"&&decoded.voice.enabled&&decoded.puppetArms.Length==1,"voice and array object models were decoded");
 }
 static void VoiceDesign(){
  foreach(bool enabled in new[]{false,true}){
   var data=Design("","","");data["headColor"]="#fcfdfd";data["armColor"]="#b93ca8";data["gownBasePng"]="authored robe";
   data["voice"]=new Dictionary<string,object>{{"enabled",enabled},{"bank","moon"},{"speed",1.7},{"pitch",.6},{"echo",.4},{"muffle",.3},{"electric",.2},{"chaos",.1},{"repeat",false},{"reverse",true},{"split",false},{"shortWeight",10},{"mediumWeight",20},{"longWeight",70}};
   data["layers"]=new Dictionary<string,object>{{"robe",true},{"sleeves",true},{"mechanicalArm",false}};
   Apply(data);var d=IteratorDesign.Current;
   Check(d.projectId=="test"&&d.oracleId=="sample"&&d.headColor=="#fcfdfd"&&d.armColor=="#b93ca8"&&d.gownBasePng=="authored robe","voice object does not reject or replace appearance");
   Check(d.layers.robe&&d.layers.sleeves&&!d.layers.mechanicalArm,"appearance layer flags decoded after voice");
   Check(d.voice.enabled==enabled&&d.voice.bank=="moon"&&Math.Abs(d.voice.speed-1.7f)<.001f&&Math.Abs(d.voice.pitch-.6f)<.001f,"voice toggles, bank, speed and pitch retained");
   Check(Math.Abs(d.voice.echo-.4f)<.001f&&Math.Abs(d.voice.muffle-.3f)<.001f&&Math.Abs(d.voice.electric-.2f)<.001f&&Math.Abs(d.voice.chaos-.1f)<.001f&&!d.voice.repeat&&d.voice.reverse&&!d.voice.split,"voice effect and sequencing fields retained");
   Check(d.voice.shortWeight==10&&d.voice.mediumWeight==20&&d.voice.longWeight==70,"voice syllable weights retained");
   Check(Object.ReferenceEquals(d,IteratorDesign.ForId("sample")),"Poll and room cache use the same successfully decoded design");
   string other="voice-for-id-"+enabled;data["oracleId"]=other;Write(RuntimePaths.DesignPath(other),Json.Serialize(data));
   var room=IteratorDesign.ForId(other);Check(room.projectId=="test"&&room.voice.enabled==enabled&&room.voice.bank=="moon"&&room.armColor=="#b93ca8","first ForId read decodes the full appearance and voice");
  }
  Apply(Design("","",""));Check(!IteratorDesign.Current.voice.enabled&&IteratorDesign.Current.voice.bank=="pebbles","legacy design without voice retains disabled defaults");
  Check(!MiDiagnostics.Codes.Contains("MI_DESIGN_READ")&&!MiDiagnostics.Codes.Contains("MI_DESIGN_APPLY"),"valid voice causes no read/apply diagnostic");
 }
 static void InvalidDesignField(){
  var bad=new Dictionary<string,object>();
  bad["voice"]=new Dictionary<string,object>{{"pitch",new Dictionary<string,object>()}};
  try{DecodeDesign(bad);throw new Exception("invalid voice unexpectedly accepted");}catch(FormatException error){Check(error.Message.Contains("IteratorDesign.voice.pitch")&&error.Message.Contains("Single"),"diagnostic names exact nested voice field and expected type");}
  bad.Clear();bad["puppetArms"]=new object[]{new Dictionary<string,object>{{"lengthScale",new object[0]}}};
  try{DecodeDesign(bad);throw new Exception("invalid arm unexpectedly accepted");}catch(FormatException error){Check(error.Message.Contains("IteratorDesign.puppetArms[0].lengthScale"),"diagnostic retains array entry and nested field");}
  bad.Clear();bad["voice"]=null;
  try{DecodeDesign(bad);throw new Exception("null voice unexpectedly accepted");}catch(FormatException error){Check(error.Message.Contains("IteratorDesign.voice"),"null object is diagnosed without silently dropping it");}
 }
 static void DecodeFile(string root,string path){
  var data=Json.Deserialize(File.ReadAllText(path)) as Dictionary<string,object>;
  var decoded=DecodeDesign(data);
  Check(decoded.projectId==data["projectId"].ToString()&&decoded.oracleId==data["oracleId"].ToString(),"compiled identity retained");
  Check(decoded.armColor==data["armColor"].ToString()&&decoded.gownBasePng==data["gownBasePng"].ToString(),"compiled color and complete robe asset retained");
  File.WriteAllText(Path.Combine(root,"decoded.json"),Json.Serialize(Snapshot(decoded)));
  Console.WriteLine("Decoded "+data.Count+" input fields; project="+decoded.projectId+" oracle="+decoded.oracleId+" voice="+decoded.voice.enabled+"/"+decoded.voice.bank);
 }
 static void Initial(){Apply(Design(Image(2),Image(2),Image(2)));Check(Futile.atlasManager.Atlases.Count==3,"initial three atlases");Check(IteratorDesign.Revision==1,"initial revision committed");}
 static void AssertPreserved(IteratorDesign previous,string[] keys,int revision,UnityEngine.Rect ink){
  Check(Object.ReferenceEquals(previous,IteratorDesign.Current),"failed apply retains current design");
  Check(IteratorDesign.Revision==revision,"failed apply does not advance revision");
  Check(IteratorDesign.FaceElement==keys[0]&&IteratorDesign.AntennaElement==keys[1]&&IteratorDesign.HaloElement==keys[2],"failed apply retains element references");
  Check(IteratorDesign.FaceInk.x==ink.x&&IteratorDesign.FaceInk.width==ink.width,"failed apply retains face bounds");
  Check(Futile.atlasManager.Atlases.Count==3,"staged atlas cleanup retains only original three");
  foreach(string key in keys)Check(Futile.atlasManager.DoesContainAtlas(key),"original atlas remains present");
  Check(AliveTextures()==3,"failed decode/registration leaks no staged textures");
  Check(MiDiagnostics.Codes.Contains("MI_DESIGN_APPLY"),"failed apply reports diagnostic code");
  Check(logs.Exists(s=>s.StartsWith("Oracle project read failed:")),"legacy error callback remains supported");
 }
 static void NullDialogue(){
  var data=Design(null,"","");data["firstDialogue"]=null;data["repeatDialogue"]=null;data["dialogueJson"]=null;data["renderOrder"]=new object[]{null,"head"};Apply(data);
  Check(IteratorDesign.Current.firstDialogue==""&&IteratorDesign.Current.repeatDialogue=="","explicit null legacy strings normalized");
  Check(IteratorDesign.Current.facePng==""&&IteratorDesign.Current.dialogueJson=="","optional strings normalized at shared loader");
  Check(IteratorDesign.Current.renderOrder[0]==""&&IteratorDesign.Current.renderOrder[1]=="head","nested string array preserves valid values");
  var profile=CreatorDialogueProfile.For(IteratorDesign.Current);Check(profile.first.Count==0&&profile.repeat.Count==0,"null input becomes empty dialogue without fabricated lines");
  profile=CreatorDialogueProfile.For(new IteratorDesign{oracleId="direct-null",firstDialogue=null,repeatDialogue=null});Check(profile.first.Count==0&&profile.repeat.Count==0,"legacy direct construction is also protected");
  profile=CreatorDialogueProfile.For(new IteratorDesign{oracleId="valid",firstDialogue="first\n\nsecond",repeatDialogue="repeat"});Check(profile.first.Count==2&&profile.first[1].text=="second"&&profile.repeat.Count==1,"nonempty legacy content and sequence preserved");
  Check(new CreatorDialogueLine().text=="","new dialogue lines begin with empty text");Check(MiDiagnostics.Codes.Contains("MI_DESIGN_NULL_STRING")&&MiDiagnostics.Codes.Contains("MI_DIALOGUE_NULL_TEXT"),"null normalization is diagnosed");
  profile=CreatorDialogueProfile.For(new IteratorDesign{oracleId="presentation",dialogueJson="{\"first\":[{\"text\":\"one\",\"presentation\":{\"movement\":\"still\",\"eyes\":\"open\"}},{\"text\":\"two\"}],\"pearlReading\":{\"presentation\":{\"movement\":\"small\",\"eyes\":\"closed\"}}}"});
  Check(profile.first[0].presentation.movement=="still"&&profile.first[0].presentation.eyes=="open","real JSON profile preserves per-line presentation");
  Check(profile.first[1].presentation.movement=="inherit"&&profile.first[1].presentation.eyes=="inherit","old line JSON retains independent inherit defaults");
  Check(profile.pearlReading.presentation.movement=="small"&&profile.pearlReading.presentation.eyes=="closed","real JSON profile preserves iterator reading defaults");
  var pearlReader=PearlProjectCodec.ReadObject<PearlReaderProfile>(Json.Deserialize("{\"presentation\":{\"movement\":\"still\"},\"affinity\":{\"likes\":{\"presentation\":{\"eyes\":\"open\"},\"read\":[]}}}"));
  Check(pearlReader.presentation.movement=="still"&&pearlReader.presentation.eyes=="inherit"&&pearlReader.affinity.likes.presentation.eyes=="open"&&pearlReader.affinity.likes.presentation.movement=="inherit","reader and affinity body independently decode optional presentation fields");
 }
 static void Broadcast(){
  string text="{\"id\":\"B01\",\"pages\":[{\"lines\":[{\"text\":null},{\"text\":\"alpha<LINE>beta\"},{\"text\":\"\"},{\"text\":\"1234567890123456789012345678901234567\"}]}]}";
  var project=PearlProjectCodec.ReadObject<BroadcastProject>(Json.Deserialize(text));var lines=CreatorBroadcastGallery.TextLines(project);
  Check(lines.Count==4,"authored lines without synthetic heading or forced wrapping");Check(lines[0]=="alpha"&&lines[1]=="beta","line break marker retained");
  Check(lines[2]==""&&lines[3].Length==37,"empty author line and full text retained for viewport wrapping");Check(project.pages[0].lines[0].text==null,"display fallback does not rewrite authored model");
  Check(MiDiagnostics.Codes.Contains("MI_BROADCAST_NULL_TEXT"),"null broadcast diagnosed");
  project.pages=new[]{new BroadcastPage{lines=null},null};Check(CreatorBroadcastGallery.TextLines(project).Count==1,"partially missing pages retain only their separator without crash");
 }
 static void DefaultLanguage(string root){
  var game=new RainWorld();UiText.Use(game);game.options.language=InGameTranslator.LanguageID.Chinese;
  var missing=DecodeDesign(new Dictionary<string,object>{{"oracleId","missing-defaults"}});
  var missingProfile=CreatorDialogueProfile.For(missing);
  Check(missing.name=="未命名迭代器"&&missing.firstDialogue=="……你好。","absent legacy fields use current native language");
  Check(missingProfile.pearlReading.greeting[0].lines[0].text=="小家伙，你这次给我带了什么东西？","absent pearl rules use native translated defaults");
  string authoredJson="{\"first\":[{\"text\":\"……你好。\"}],\"repeat\":[],\"pearlReading\":{\"greeting\":[{\"name\":\"问候\",\"lines\":[{\"text\":\"小家伙，你这次给我带了什么东西？\"}]}],\"repeat\":[]}}";
  var authoredData=new Dictionary<string,object>{{"oracleId","authored-default-lookalike"},{"name","未命名迭代器"},{"firstDialogue","……你好。"},{"repeatDialogue","又见面了。"},{"pearlDialogue","……让我看看。"},{"dialogueJson",authoredJson}};
  string path=Path.Combine(root,"authored.json"),saved=Json.Serialize(authoredData);Write(path,saved);byte[] savedBytes=File.ReadAllBytes(path);
  var authored=DecodeDesign(Json.Deserialize(File.ReadAllText(path)) as Dictionary<string,object>);
  var direct=new IteratorDesign{oracleId="programmatic-author",firstDialogue="用户写的台词"};
  foreach(var language in new[]{InGameTranslator.LanguageID.English,InGameTranslator.LanguageID.TraditionalChinese,InGameTranslator.LanguageID.Chinese}){
   game.options.language=language;missingProfile=CreatorDialogueProfile.For(missing);
   Check(missing.firstDialogue==UiText.Get("...Hello.")&&missing.name==UiText.Get("Unnamed iterator"),"missing legacy defaults refresh after language change");
   Check(missingProfile.first[0].text==UiText.Get("...Hello.")&&missingProfile.pearlReading.greeting[0].lines[0].text==UiText.Get("Little creature, what have you brought me this time?"),"cached profile refreshes fallback lines after language change");
   var authoredProfile=CreatorDialogueProfile.For(authored);
   Check(authored.name=="未命名迭代器"&&authored.firstDialogue=="……你好。"&&authored.repeatDialogue=="又见面了。"&&authored.pearlDialogue=="……让我看看。","explicit legacy strings remain authored even if equal to former defaults");
   Check(authoredProfile.first[0].text=="……你好。"&&authoredProfile.pearlReading.greeting[0].name=="问候"&&authoredProfile.pearlReading.greeting[0].lines[0].text=="小家伙，你这次给我带了什么东西？","saved authored JSON is never translated");
   Check(authoredProfile.repeat.Count==0&&authoredProfile.pearlReading.repeat.Length==0,"explicit empty arrays do not receive fabricated defaults");
   Check(authoredProfile.pearlReading.leaving[0].lines[0].text==UiText.Get("...Are you leaving?"),"partial old schemas translate only absent rule fields");
   Check(CreatorDialogueProfile.For(direct).first[0].text=="用户写的台词","programmatically authored values survive language changes");
   Check(authored.dialogueJson==authoredJson&&Convert.ToBase64String(File.ReadAllBytes(path))==Convert.ToBase64String(savedBytes),"runtime defaults do not rewrite authored source bytes");
  }
  game.options.language=InGameTranslator.LanguageID.English;
  Check(CreatorDialogueProfile.For(missing).pearlReading.greeting[0].lines[0].text=="Little creature, what have you brought me this time?","English fallback is an English sentence");
  Check(PearlProjectCodec.ReadObject<CreatorPearlRules>(new Dictionary<string,object>()).greeting[0].lines[0].text=="Little creature, what have you brought me this time?","direct codec defaults also use native language");
 }
 static void WarningLanguage(){
  var game=new RainWorld();UiText.Use(game);
  foreach(var language in new[]{InGameTranslator.LanguageID.Chinese,InGameTranslator.LanguageID.English,InGameTranslator.LanguageID.TraditionalChinese}){
   game.options.language=language;MiDiagnostics.Warnings.Clear();
   var project=new BroadcastProject{id="author-id",pages=null};CreatorBroadcastGallery.TextLines(project);
   Check(MiDiagnostics.Warnings.Count==1&&MiDiagnostics.Warnings[0]==UiText.Get("Null broadcast pages were treated as empty."),"actual broadcast warning uses active native translator");
   Check(project.pages==null,"localized warning leaves authored data unchanged");
   var invalid=Design("not-base64","","");Apply(invalid);
   Exception error=MiDiagnostics.Errors[MiDiagnostics.Errors.Count-1];
   Check(error is FormatException&&!String.IsNullOrEmpty(error.StackTrace)&&error.StackTrace.Contains("FromBase64String"),"original exception type and decoding stack survive localized UI language");
  }
 }
 static Dictionary<string,object> Record(string id){return new Dictionary<string,object>{{"projectId",id},{"oracleId",id},{"ai",id+"_AI"},{"entry",id+"_ENTRY"}};}
 static void WriteVersionedDesign(string path,string id,string name,byte marker,DateTime stamp){
  var data=Design(Image(marker),"","");data["oracleId"]=id;data["name"]=name;
  Write(path,Json.Serialize(data));File.SetLastWriteTimeUtc(path,stamp);
 }
 static void DesignPathChanges(string root){
  string package=Path.Combine(root,"package"),targeted=Path.Combine(package,"versioned");
  ModManager.ActiveMods.Add(new ModManager.Mod("test.owner",package){hasTargetedVersionFolder=true,TargetedPath=targeted});
  var selected=Record("sample");selected["design"]="designs/sample.json";selected["name"]="Selected";
  var cached=Record("cached");cached["design"]="designs/cached.json";cached["name"]="Cached";
  Write(Path.Combine(package,"moreiterators/registry.json"),Json.Serialize(new object[]{selected,cached}));
  string selectedBase=Path.Combine(package,"designs/sample.json"),selectedOverride=Path.Combine(targeted,"designs/sample.json");
  string cachedBase=Path.Combine(package,"designs/cached.json"),cachedOverride=Path.Combine(targeted,"designs/cached.json");
  DateTime stamp=new DateTime(2030,1,1,0,0,0,DateTimeKind.Utc);
  WriteVersionedDesign(selectedBase,"sample","base",2,stamp);WriteVersionedDesign(cachedBase,"cached","base",2,stamp);
  Check(SamePath(RuntimePaths.DesignPath("sample"),selectedBase),"published design resolves inside its owner");
  Check(!RuntimePaths.IsLocalDesignPath(selectedBase)&&RuntimePaths.IsLocalDesignPath(Path.Combine(RuntimePaths.DataDirectory,"sample.json")),"published designs stay separate from the writable local runtime");
  IteratorDesign.Select("sample");IteratorDesign.Poll(logs.Add);
  Check(IteratorDesign.Current.name=="base"&&IteratorDesign.Revision==1&&IteratorDesign.FaceInk.width==2,"selected design loads the base asset");
  Check(IteratorDesign.ForId("cached").name=="base","room design cache loads the base asset");
  WriteVersionedDesign(selectedOverride,"sample","over",3,stamp);WriteVersionedDesign(cachedOverride,"cached","over",3,stamp);
  Check(File.GetLastWriteTimeUtc(selectedBase)==File.GetLastWriteTimeUtc(selectedOverride)&&new FileInfo(selectedBase).Length==new FileInfo(selectedOverride).Length,"override intentionally shares base timestamp and length");
  Check(File.GetLastWriteTimeUtc(cachedBase)==File.GetLastWriteTimeUtc(cachedOverride)&&new FileInfo(cachedBase).Length==new FileInfo(cachedOverride).Length,"cached override intentionally shares base timestamp and length");
  UnityEngine.Time.realtimeSinceStartup+=2;
  System.Threading.Thread.Sleep(300);
  Check(SamePath(RuntimePaths.DesignPath("sample"),selectedOverride),"new versioned asset changes the resolved path");
  IteratorDesign.Poll(logs.Add);
  Check(IteratorDesign.Current.name=="over"&&IteratorDesign.Revision==2&&IteratorDesign.FaceInk.width==3,"selected design reloads equal-timestamp override and updates its atlas");
  Check(IteratorDesign.ForId("cached").name=="over","room cache reloads equal-timestamp override");
  File.Delete(selectedOverride);File.Delete(cachedOverride);UnityEngine.Time.realtimeSinceStartup+=2;System.Threading.Thread.Sleep(300);
  Check(SamePath(RuntimePaths.DesignPath("sample"),selectedBase),"removing override resolves back to the owner's base asset");
  IteratorDesign.Poll(logs.Add);
  Check(IteratorDesign.Current.name=="base"&&IteratorDesign.Revision==3&&IteratorDesign.FaceInk.width==2,"selected design and atlas fall back after override removal");
  Check(IteratorDesign.ForId("cached").name=="base","room cache falls back after override removal");
  WriteVersionedDesign(selectedBase,"sample","longer base",4,stamp);WriteVersionedDesign(cachedBase,"cached","longer base",4,stamp);UnityEngine.Time.realtimeSinceStartup+=2;
  IteratorDesign.Poll(logs.Add);
  Check(IteratorDesign.Current.name=="longer base"&&IteratorDesign.Revision==4&&IteratorDesign.FaceInk.width==4,"same-path same-timestamp length change reloads selected design");
  Check(IteratorDesign.ForId("cached").name=="longer base","same-path same-timestamp length change reloads room cache");
  Check(Futile.atlasManager.Atlases.Count==1&&AliveTextures()==1,"path changes release obsolete selected-design textures");
 }
 static void Registry(string root){
  string package=Path.Combine(root,"package");ModManager.ActiveMods.Add(new ModManager.Mod("test.owner",package));var rows=new List<object>();
  var missing=Record("missing");rows.Add(missing);var nil=Record("null");nil["name"]=null;rows.Add(nil);var wrong=Record("wrong");wrong["name"]=42;rows.Add(wrong);var blank=Record("blank");blank["name"]="  ";rows.Add(blank);var good=Record("valid");good["name"]="  Author title  ";rows.Add(good);
  var invalid=Record("invalid");invalid.Remove("oracleId");rows.Add(invalid);Write(Path.Combine(package,"moreiterators/registry.json"),Json.Serialize(rows));
  var projects=IteratorCatalog.Projects();Check(projects.Count==5,"identity validation unchanged");foreach(var item in projects){string id=(string)item["projectId"];Check(item["name"] is string,"all accepted names are safely indexable strings");Check((string)item["name"]==(id=="valid"?"  Author title  ":id),"fallback uses stable ID and preserves author spelling");Check(IteratorCatalog.Text(item,"name")==item["name"].ToString(),"Text and direct index share normalized name");}
  Check(IteratorCatalog.IsAI("missing_AI"),"name fallback does not remove valid room ownership");Check(MiDiagnostics.Codes.FindAll(s=>s=="MI_REGISTRY_NAME_FALLBACK").Count==4,"one diagnostic for each normalized record");
 }
 static void FailedTexture(string scenario){
  Initial();var previous=IteratorDesign.Current;var keys=new[]{IteratorDesign.FaceElement,IteratorDesign.AntennaElement,IteratorDesign.HaloElement};int revision=IteratorDesign.Revision;var ink=IteratorDesign.FaceInk;
  var next=Design(Image(3),Image(3),Image(3));
  if(scenario=="base64")next["antennaPng"]="invalid-base64";
  if(scenario=="png")next["antennaPng"]=Image(0);
  if(scenario=="registration")Futile.atlasManager.FailLoadAttempt=Futile.atlasManager.LoadAttempts+3;
  if(scenario=="remove-failure"){next["facePng"]="";next["haloPng"]=Image(0);}
  Apply(next);AssertPreserved(previous,keys,revision,ink);
 }
 static void SuccessfulTexture(){
  Initial();var keys=new[]{IteratorDesign.FaceElement,IteratorDesign.AntennaElement,IteratorDesign.HaloElement};var next=Design(Image(3),Image(3),Image(3));next["name"]="new";Apply(next);
  Check(IteratorDesign.Revision==2&&IteratorDesign.Current.name=="new","complete replacement publishes one revision");Check(IteratorDesign.FaceInk.width==3,"new face bounds commit with texture");
  foreach(string key in keys)Check(!Futile.atlasManager.DoesContainAtlas(key),"old atlas released only after successful replacement");Check(Futile.atlasManager.Atlases.Count==3&&AliveTextures()==3,"successful replacement leaves only new textures");
  var halo=Futile.atlasManager.Atlases[IteratorDesign.HaloElement];Check(Math.Abs(halo.GetPixels()[0].a-.34f)<.0001f,"halo opacity behavior retained");
  Apply(Design("","",""));Check(IteratorDesign.Revision==3&&IteratorDesign.FaceElement==null&&IteratorDesign.AntennaElement==null&&IteratorDesign.HaloElement==null,"explicit removals commit together");Check(Futile.atlasManager.Atlases.Count==0&&AliveTextures()==0,"removal disposes prior textures");
 }
 static bool Chinese(string value){foreach(char ch in value)if(ch>='\u4e00'&&ch<='\u9fff')return true;return false;}
 static void NoEmptyGalleryHints(){
  foreach(string original in new[]{"No pearls imported. Save and apply one in the web editor.","Save and apply a broadcast in the web editor to show it here.","No reader is assigned to this pearl.","(Blank)"})Check(!Menu.CapturedText.Values.Contains(UiText.Get(original)),"empty gallery has no placeholder: "+original);
 }
 static void GalleryLanguage(){
  var menu=new Menu.MainMenu();menu.manager.rainWorld.options.language=InGameTranslator.LanguageID.English;Menu.CapturedText.Values.Clear();CreatorPearlGallery.Open(menu);
  Check(Menu.CapturedText.Values.Contains("Pearls")&&Menu.CapturedText.Values.Contains("Open web editor"),"pearl gallery selects actual game English language");Check(!Menu.CapturedText.Values.Exists(Chinese),"empty English pearl UI has no Chinese literals");NoEmptyGalleryHints();CreatorPearlGallery.Close();
  Menu.CapturedText.Values.Clear();CreatorBroadcastGallery.Open(menu);Check(Menu.CapturedText.Values.Contains("Open web editor"),"broadcast UI uses English resource");Check(!Menu.CapturedText.Values.Exists(Chinese),"empty English broadcast UI has no Chinese literals");NoEmptyGalleryHints();CreatorBroadcastGallery.Close();
  menu.manager.rainWorld.options.language=InGameTranslator.LanguageID.Chinese;Menu.CapturedText.Values.Clear();CreatorPearlGallery.Open(menu);Check(Menu.CapturedText.Values.Contains("珍珠")&&Menu.CapturedText.Values.Contains("打开编辑网页"),"returning to Chinese refreshes gallery labels");NoEmptyGalleryHints();CreatorPearlGallery.Close();
  Menu.CapturedText.Values.Clear();CreatorBroadcastGallery.Open(menu);NoEmptyGalleryHints();CreatorBroadcastGallery.Close();
  menu.manager.rainWorld.options.language=InGameTranslator.LanguageID.English;CreatorPearlCatalog.Items.Add(new PearlProject{id="P01",name="作者名称",readers=new[]{new PearlReaderProfile{oracleId="author",name="作者读取者",read=new[]{new CreatorDialogueLine{text="作者台词"}}}}});
  Menu.CapturedText.Values.Clear();CreatorPearlGallery.Open(menu);Check(Menu.CapturedText.Values.Contains("P01 作者名称"),"author pearl name is not translated");Check(Menu.CapturedText.Values.Contains("Reader: 作者读取者  ›"),"only reader label is translated");Check(Menu.CapturedText.Values.Contains("作者台词"),"author dialogue is not translated");CreatorPearlGallery.Close();
  CreatorPearlCatalog.Items[0].readers[0].read=new CreatorDialogueLine[0];Menu.CapturedText.Values.Clear();CreatorPearlGallery.Open(menu);Check(Menu.CapturedText.Values.Contains("Reader: 作者读取者  ›"),"empty text keeps existing reader controls");NoEmptyGalleryHints();CreatorPearlGallery.Close();
  CreatorPearlCatalog.Items[0].readers=new PearlReaderProfile[0];Menu.CapturedText.Values.Clear();CreatorPearlGallery.Open(menu);Check(Menu.CapturedText.Values.Contains("P01 作者名称"),"pearl without readers keeps its actual title");NoEmptyGalleryHints();CreatorPearlGallery.Close();
  UiText.Use(menu.manager.rainWorld);var rows=CreatorBroadcastGallery.TextLines(new BroadcastProject{pages=new[]{new BroadcastPage{lines=new[]{new BroadcastLine{text="作者广播"}}}}});Check(rows.Count==1&&rows[0]=="作者广播","author content retained without synthetic page heading");
 }
 static void LaunchLanguage(string root){
  var menu=new Menu.MainMenu();menu.manager.rainWorld.options.language=InGameTranslator.LanguageID.English;
  Check(!CreatorLaunch.Ensure(menu,"UNKNOWN_AI"),"missing project rejects entry");Check(menu.manager.LastDialog.Contains("Apply the project again")&&!Chinese(menu.manager.LastDialog),"core entry error is English");
  PlaybackMode.Enabled=true;Check(!CreatorLaunch.Ensure(menu,"UNKNOWN_AI"),"playback missing project rejects entry");Check(menu.manager.LastDialog.Contains("Reinstall this content mod")&&!menu.manager.LastDialog.Contains("studio"),"playback recovery text does not require unavailable editor");PlaybackMode.Enabled=false;
  string package=Path.Combine(root,"package");ModManager.ActiveMods.Add(new ModManager.Mod("test.owner",package));var record=Record("sample");record["name"]="Author";Write(Path.Combine(package,"moreiterators/registry.json"),Json.Serialize(new object[]{record}));UnityEngine.Time.realtimeSinceStartup+=2;AssetManager.Fail=true;
  Check(!CreatorLaunch.Ensure(menu,"sample_AI"),"unexpected IO failure rejects entry");Check(menu.manager.LastDialog.Contains("MI_LAUNCH_FAILED")&&!Chinese(menu.manager.LastDialog),"unexpected native error gets English summary, not raw OS text");Check(MiDiagnostics.Errors.Exists(e=>e.Message=="原始系统错误"),"original error remains available to diagnostics");
 }
 static void StudioLanguage(string root){
  var menu=new Menu.MainMenu();menu.manager.rainWorld.options.language=InGameTranslator.LanguageID.English;UiText.Use(menu.manager.rainWorld);
  try{StudioLauncher.StartInfo(root,root,"wrong","");throw new Exception("expected invalid studio");}catch(ArgumentException error){Check(error.Message=="Unknown editor page.","studio argument error uses current language and preserves type");}
  try{StudioLauncher.StartInfo(root,root,"appearance","invalid ID");throw new Exception("expected invalid project");}catch(ArgumentException error){Check(error.Message=="Invalid project ID.","project validation error is localized");}
  StudioLauncher.Open(menu,"appearance");Check(menu.manager.LastDialog.Contains("Could not open the web editor")&&!Chinese(menu.manager.LastDialog),"startup configuration error is English");Check(MiDiagnostics.Codes.Contains("MI_STUDIO_LAUNCH"),"startup failure reports structured diagnostic");
  menu.manager.rainWorld.options.language=InGameTranslator.LanguageID.Chinese;StudioLauncher.Open(menu,"appearance");Check(menu.manager.LastDialog.Contains("无法打开编辑网页"),"studio error language updates from game");
 }
 static void PackagedStudioLauncher(string root){
  string editor=Path.Combine(root,"moved package 编辑网页"),python=Path.Combine(root,"pythonw.exe");Write(python,"fixture, never executed");
  string data=Path.Combine(root,"selected library 作品库");
  Write(Path.Combine(BepInEx.Paths.ConfigPath,"moreiterators.paths.json"),Json.Serialize(new Dictionary<string,object>{{"runtimeDirectory",Path.Combine(data,"runtime")}}));
  Environment.SetEnvironmentVariable("MORE_ITERATORS_DATA",Path.Combine(root,"stale inherited library"));
  Check(File.Exists(Path.Combine(editor,"studio_launcher.py")),"actual packaged launcher is present");
  Check(!File.Exists(Path.Combine(editor,"启动编辑器.pyw")),"old alias deliberately absent");
  foreach(string page in new[]{"appearance","dialogue","pearls","broadcasts"}){
   var start=StudioLauncher.StartInfo(editor,python,page,"new-project");
   Check(start.WorkingDirectory==editor&&start.FileName==python,"configured paths preserved after move");
   Check(start.Arguments=="-B \""+Path.Combine(editor,"studio_launcher.py")+"\" --page "+page+" --project new-project","real C# launcher targets the shipped Python file with page and project");
   Check(!start.UseShellExecute&&start.CreateNoWindow&&start.WindowStyle==System.Diagnostics.ProcessWindowStyle.Hidden,"hidden direct launch, no visible console");
   Check(start.EnvironmentVariables["MORE_ITERATORS_DATA"]==Path.GetFullPath(data),"game-opened editor uses the current game runtime's parent library regardless of editor code location");
   Check(Environment.GetEnvironmentVariable("MORE_ITERATORS_DATA")==Path.Combine(root,"stale inherited library"),"child data selection does not alter the game's own environment");
  }
 }
 static void ExternalEntryLaunch(string root){
  AssetManager.Root=root;AssetManager.Fail=false;var menu=new Menu.MainMenu();menu.manager.rainWorld.progression.regionNames=new[]{"SU"};
  string package=Path.Combine(root,"package");ModManager.ActiveMods.Add(new ModManager.Mod("test.owner",package));
  var record=new Dictionary<string,object>{{"projectId","external"},{"name","External"},{"ai","SU_MI_AI"},{"entry","SU_A01"},{"oracleId","external"},{"ownerMod","test.owner"},{"exitNode",1},{"entryNode",0},{"roomBinding",new Dictionary<string,object>{{"entryMode","existing"}}}};
  Write(Path.Combine(package,"moreiterators/registry.json"),Json.Serialize(new object[]{record}));UnityEngine.Time.realtimeSinceStartup+=2;
  string world="ROOMS\n(White)SU_OTHER : DISCONNECTED\n(Red)SU_OTHER : SU_A02\nSU_MI_AI : DISCONNECTED, SU_A01\nSU_A01 : SU_MI_AI, SU_B01\nEND ROOMS\n";
  Write(Path.Combine(root,"world/su/world_su.txt"),world);
  foreach(string location in new[]{"world/su-rooms/SU_MI_AI","levels/SU_A01"}){Write(Path.Combine(root,location+".txt"),"NAME\n48*36\n\n0,0\n");Write(Path.Combine(root,location+"_settings.txt"),"Template: NONE");Write(Path.Combine(root,location+"_1.png"),"camera");}
  RainWorld.roomNameToIndex["SU_MI_AI"]=400;RainWorld.roomNameToIndex["SU_A01"]=12;
  Check(CreatorLaunch.Ensure(menu,"SU_A01"),"external entry with unrelated conditional rows and native levels assets launches");
  Check(CreatorLaunch.ConnectionsMatch(world,"SU_MI_AI","SU_A01",1,0),"actual chosen exit pair matches");
  Check(!CreatorLaunch.ConnectionsMatch(world,"SU_MI_AI","SU_A01",0,0),"incorrect ai exit rejected");
  Check(!CreatorLaunch.ConnectionsMatch(world,"SU_MI_AI","SU_A01",1,1),"incorrect return exit rejected");
  RainWorld.roomNameToIndex.Remove("SU_MI_AI");Check(!CreatorLaunch.Ensure(menu,"SU_A01"),"new ai missing from startup index requires restart");RainWorld.roomNameToIndex["SU_MI_AI"]=400;
  Write(Path.Combine(root,"world/su/world_su.txt"),world.Replace("SU_A01 : SU_MI_AI","SU_A01 : DISCONNECTED"));Check(!CreatorLaunch.Ensure(menu,"SU_A01"),"broken reciprocal connection rejected");
  Check(!CreatorLaunch.Matches(CreatorLaunch.RoomNames(world),RainWorld.roomNameToIndex,"SU"),"owned-world sequential guard remains strict");
 }
 static int Main(string[] args){try{
  UnityEngine.Application.persistentDataPath=args[1];AssetManager.Root=args[1];BepInEx.Paths.ConfigPath=Path.Combine(args[1],"config");Directory.CreateDirectory(BepInEx.Paths.ConfigPath);
  if(args[0]=="default-language")DefaultLanguage(args[1]);else if(args[0]=="warning-language")WarningLanguage();else if(args[0]=="design-schema")DesignSchema();else if(args[0]=="design-path-changes")DesignPathChanges(args[1]);else if(args[0]=="voice-design")VoiceDesign();else if(args[0]=="invalid-design-field")InvalidDesignField();else if(args[0]=="decode-file")DecodeFile(args[1],args[2]);else if(args[0]=="dialogue")NullDialogue();else if(args[0]=="broadcast")Broadcast();else if(args[0]=="registry")Registry(args[1]);else if(args[0]=="success")SuccessfulTexture();else if(args[0]=="gallery-language")GalleryLanguage();else if(args[0]=="launch-language")LaunchLanguage(args[1]);else if(args[0]=="external-entry")ExternalEntryLaunch(args[1]);else if(args[0]=="studio-language")StudioLanguage(args[1]);else if(args[0]=="studio-package")PackagedStudioLauncher(args[1]);else FailedTexture(args[0]);
  Console.WriteLine(assertions+" boundary assertions passed: "+args[0]);return 0;
 }catch(Exception error){Console.Error.WriteLine(error);return 1;}}
}
'''


class RuntimeBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        compiler = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        assembly = Path(os.environ.get('RAIN_WORLD_GAME', '')) / 'RainWorld_Data/Managed/Assembly-CSharp.dll'
        if not compiler.exists() or not assembly.exists():
            raise unittest.SkipTest('Windows C# compiler and installed Rain World JSON parser are required')
        cls.temp = tempfile.TemporaryDirectory(prefix='mi-boundary-test-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.work = Path(cls.temp.name)
        cls.exe = cls.work / 'runtime-boundaries.exe'
        cls.environment = dict(os.environ, MI_TEST_NATIVE_TEXT_ROOT=str(root / 'mod/text'))
        shutil.copy2(assembly, cls.work / assembly.name)
        
        
        prefix = 'extern alias rwjson;\nusing Json = rwjson::Json;\n'
        sources = [str(root / 'src' / name) for name in
                   ('AudioTrackDesign.cs', 'EyeDesign.cs', 'PuppetArmDesign.cs', 'ContentAssets.cs')]
        for name in ('IteratorDesign.cs', 'RuntimePaths.cs', 'CreatorBroadcastGallery.cs', 'CreatorPearlRules.cs',
                     'CreatorPearlGallery.cs', 'CreatorLaunch.cs', 'StudioLauncher.cs', 'UiText.cs', 'CreatorDialogueModels.cs'):
            target = cls.work / name
            target.write_text(prefix + (root / 'src' / name).read_text('utf-8-sig'), encoding='utf-8')
            sources.append(target)
        
        
        for name, boundary in (
            ('CreatorVoice.cs', '// Uses native SoundIDs'),
            ('CreatorReadingPresentation.cs', '// Presentation owns'),
            ('CreatorDialogue.cs', '// One resumable main sequence'),
            ('CreatorPearls.cs', 'public static class CreatorPearlCatalog'),
            ('CreatorBroadcasts.cs', 'public static class CreatorBroadcastCatalog'),
        ):
            target = cls.work / name
            text = (root / 'src' / name).read_text('utf-8-sig')
            target.write_text(prefix + text.split(boundary, 1)[0] + '\n}\n', encoding='utf-8')
            sources.append(target)
        harness = cls.work / 'BoundaryCheck.cs'
        harness.write_text(prefix + HARNESS, encoding='utf-8')
        result = subprocess.run([
            str(compiler), '/nologo', '/utf8output', '/out:' + str(cls.exe), '/r:rwjson=' + str(assembly),
            '/resource:' + str(root / 'mod/text/text_eng/strings.txt') + ',mi.ui.eng.strings.txt',
            str(root / 'tests/native_translation_stub.cs'),
            *map(str, sources), str(harness),
        ], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)

    def run_scenario(self, scenario):
        directory = self.work / scenario
        directory.mkdir()
        result = subprocess.run([str(self.exe), scenario, str(directory)], capture_output=True,
                                text=True, encoding='utf-8', errors='replace', timeout=15, env=self.environment)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('boundary assertions passed: ' + scenario, result.stdout)

    def test_null_design_strings_and_legacy_dialogue(self):
        self.run_scenario('dialogue')

    def test_missing_defaults_follow_language_without_rewriting_authored_text(self):
        self.run_scenario('default-language')

    def test_warnings_are_localized_and_original_exception_stacks_are_retained(self):
        self.run_scenario('warning-language')

    def test_voice_settings_decode_without_replacing_appearance(self):
        self.run_scenario('voice-design')

    def test_every_complex_design_type_is_decoded(self):
        self.run_scenario('design-schema')

    def test_invalid_nested_design_reports_precise_field_path(self):
        self.run_scenario('invalid-design-field')

    def test_broadcast_null_text_preserves_valid_text_and_wrapping(self):
        self.run_scenario('broadcast')

    def test_registry_display_names_share_one_fallback(self):
        self.run_scenario('registry')

    def test_design_path_changes_reload_same_timestamp_assets_and_fall_back(self):
        self.run_scenario('design-path-changes')

    def test_invalid_base64_retains_previous_atlas_group(self):
        self.run_scenario('base64')

    def test_decoder_failure_retains_previous_atlas_group(self):
        self.run_scenario('png')

    def test_late_atlas_registration_failure_discards_staged_resources(self):
        self.run_scenario('registration')

    def test_texture_removal_is_not_published_before_group_succeeds(self):
        self.run_scenario('remove-failure')

    def test_successful_texture_replacement_and_removal_release_old_resources(self):
        self.run_scenario('success')

    def test_gallery_language_tracks_game_without_translating_author_content(self):
        self.run_scenario('gallery-language')

    def test_launch_errors_select_core_or_playback_resources(self):
        self.run_scenario('launch-language')

    def test_existing_entry_uses_pair_index_and_native_asset_resolution(self):
        self.run_scenario('external-entry')

    def test_studio_errors_track_game_language(self):
        self.run_scenario('studio-language')

    def test_production_launcher_targets_actual_public_package_input(self):
        import importlib.util
        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location('launcher_release_contract', root / 'tools/package_release.py')
        release = importlib.util.module_from_spec(spec)
        previous_path = list(sys.path)
        try:
            sys.path.insert(0, str(root / 'tools'))
            spec.loader.exec_module(release)
        finally:
            sys.path[:] = previous_path
        inputs = release.release_inputs(root)
        self.assertIn('editor/studio_launcher.py', inputs)
        directory = self.work / 'studio-package'
        editor = directory / 'moved package 编辑网页'
        editor.mkdir(parents=True)
        
        shutil.copy2(inputs['editor/studio_launcher.py'], editor / 'studio_launcher.py')
        result = subprocess.run([str(self.exe), 'studio-package', str(directory)], capture_output=True,
                                text=True, encoding='utf-8', errors='replace', timeout=15, env=self.environment)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('boundary assertions passed: studio-package', result.stdout)

    def test_owned_ui_resources_have_matching_keys_and_placeholders(self):
        root = Path(__file__).resolve().parents[1]
        tables = {}
        for locale, folder in (('zh-CN', 'chi'), ('en', 'eng'), ('zh-TW', 'tra')):
            rows = (root / 'mod/text' / ('text_' + folder) / 'strings.txt').read_text('utf-8-sig').splitlines()
            self.assertEqual(rows[0], '0')
            native = dict(row.split('|', 1) for row in rows[1:] if row)
            self.assertTrue(all(not key.startswith('moreiterators.') for key in native))
            tables[locale] = {key: value.replace('<LINE>', '\n') for key, value in native.items()}
        self.assertEqual(set(tables['zh-CN']), set(tables['en']))
        self.assertEqual(set(tables['zh-CN']), set(tables['zh-TW']))
        owned = set(tables['en'])
        self.assertGreaterEqual(len(owned), 44)
        for key in owned:
            self.assertIn(key, tables['en'])
            self.assertEqual(key.replace('<LINE>', '\n'), tables['en'][key], 'English source phrase: ' + key)
            self.assertNotRegex(tables['en'][key], r'[\u4e00-\u9fff]')
            slots = lambda text: sorted(field for _, field, _, _ in string.Formatter().parse(text) if field is not None)
            self.assertEqual(slots(tables['zh-CN'][key]), slots(tables['en'][key]), key)
        used = set()
        for name in ('CreatorPearlGallery.cs', 'CreatorBroadcastGallery.cs', 'CreatorLaunch.cs', 'StudioLauncher.cs'):
            source = (root / 'src' / name).read_text('utf-8-sig')
            used.update(re.findall(r'UiText\.(?:Get|Format)\("([^"\\]+)"', source))
            used.update(original for original in re.findall(r'"([^"\\]+)"', source) if original in owned)
        self.assertGreaterEqual(len(used), 20)
        self.assertFalse(used - owned, 'Undefined UI keys: ' + repr(used - owned))


if __name__ == '__main__':
    unittest.main()
