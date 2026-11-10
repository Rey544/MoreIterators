using System;
using System.Collections.Generic;
using System.Linq;
using System.IO;
using UnityEngine;

namespace UnityEngine {
 public struct Vector2 {public float x,y;public Vector2(float x,float y){this.x=x;this.y=y;}public static Vector2 zero{get{return new Vector2();}}}
 public struct Color {public static Color black,white;public static Color Lerp(Color a,Color b,float x){return a;}}
 public struct Rect {public float width;}
 public static class Mathf {public static int Clamp(int a,int b,int c){return Math.Max(b,Math.Min(a,c));}public static float Clamp(float a,float b,float c){return Math.Max(b,Math.Min(a,c));}public static float Clamp01(float a){return Clamp(a,0f,1f);}public static float Min(float a,float b){return Math.Min(a,b);}public static float Max(float a,float b){return Math.Max(a,b);}public static float Lerp(float a,float b,float t){return a+(b-a)*Clamp01(t);}public static float InverseLerp(float a,float b,float v){return a==b?0f:Clamp01((v-a)/(b-a));}public static float Pow(float a,float b){return (float)Math.Pow(a,b);}}
 public static class Time {public static float realtimeSinceStartup;}
 public enum KeyCode {Escape}
 public static class Input {public static bool escape,mouseButton;public static bool GetKeyDown(KeyCode key){return escape;}public static bool GetMouseButton(int button){return mouseButton;}}
}
public class FNode {public bool isVisible=true;public FContainer parent;public float scale=1;public void RemoveFromContainer(){if(parent!=null){parent.nodes.Remove(this);parent=null;}}}
public class FContainer:FNode {public readonly List<FNode> nodes=new List<FNode>();public void AddChild(FNode node){node.RemoveFromContainer();nodes.Add(node);node.parent=this;}public int GetChildCount(){return nodes.Count;}public FNode GetChildAt(int i){return nodes[i];}public void RemoveAllChildren(){foreach(var n in nodes.ToArray())n.RemoveFromContainer();}}
public class FShader {}
public class FSprite:FNode {public string name;public Color color;public FShader shader;public float x,y,alpha,anchorX,anchorY,scaleX,scaleY;public FSprite(string name){this.name=name;}}
public enum FLabelAlignment {Left}
public class FLabel:FNode {public string text;public FLabelAlignment alignment;public FLabel(string font,string value){text=value;}public Rect textRect{get{return new Rect{width=text.Split('\n').Max(x=>x.Sum(c=>c>255?14f:7f))};}}}
public static class Futile {public static FContainer stage=new FContainer();}
public static class ModManager {public static bool MMF;}
public class Options {public InGameTranslator.LanguageID language=InGameTranslator.LanguageID.Chinese;public Vector2 ScreenSize=new Vector2(1366,768);public Menu.MenuScene.SceneID subBackground=Menu.MenuScene.SceneID.Landscape_SU;}
public class RainWorld {public Options options=new Options();public Vector2 screenSize{get{return options.ScreenSize;}}public InGameTranslator inGameTranslator;public readonly Dictionary<string,FShader> Shaders=new Dictionary<string,FShader>{{"EdgeFade",new FShader()}};public RainWorld(){inGameTranslator=new InGameTranslator(this);}}
public class ProcessManager {public RainWorld rainWorld=new RainWorld();public object dialog,upcomingProcess,currentMainLoop;public float fadeToBlack;public bool menuesMouseMode=true;}
namespace RWCustom {public static class Custom {public static RainWorld rainWorld;public static string GetFont(){return "font";}}}
namespace On.Menu {
 public static class Menu {
  public delegate void orig_ShutDownProcess(global::Menu.Menu menu);public delegate void hook_ShutDownProcess(orig_ShutDownProcess orig,global::Menu.Menu menu);public static event hook_ShutDownProcess ShutDownProcess;
  public static void Shutdown(global::Menu.Menu menu){Shutdown(menu,m=>m.DisposePages());}
  public static void Shutdown(global::Menu.Menu menu,orig_ShutDownProcess orig){if(ShutDownProcess!=null)ShutDownProcess(orig,menu);else orig(menu);}
  public static int ShutdownSubscribers {get{return ShutDownProcess==null?0:ShutDownProcess.GetInvocationList().Length;}}
  public delegate void orig_GrafUpdate(global::Menu.Menu menu,float t);public delegate void hook_GrafUpdate(orig_GrafUpdate orig,global::Menu.Menu menu,float t);public static event hook_GrafUpdate GrafUpdate;
  public static void Draw(global::Menu.Menu menu,orig_GrafUpdate orig){if(GrafUpdate!=null)GrafUpdate(orig,menu,1f);else orig(menu,1f);}
 }
 public static class MainMenu {
  public delegate void orig_Singal(global::Menu.MainMenu menu,global::Menu.MenuObject sender,string signal);public delegate void hook_Singal(orig_Singal orig,global::Menu.MainMenu menu,global::Menu.MenuObject sender,string signal);public static event hook_Singal Singal;
  public static void Signal(global::Menu.MainMenu menu,global::Menu.MenuObject sender,string signal,orig_Singal orig){if(Singal!=null)Singal(orig,menu,sender,signal);else orig(menu,sender,signal);}
 }
 public static class ButtonBehavior {
  public delegate void orig_Update(global::Menu.ButtonBehavior button);public delegate void hook_Update(orig_Update orig,global::Menu.ButtonBehavior button);public static event hook_Update Update;
  public static void Tick(global::Menu.ButtonBehavior button,orig_Update orig){if(Update!=null)Update(orig,button);else orig(button);}
 }
}
namespace Menu {
 public struct InputPackage {public int x,y;}
 public interface SelectableMenuObject {bool IsMouseOverMe{get;}bool CurrentlySelectableMouse{get;}bool CurrentlySelectableNonMouse{get;}}
 public class RectangularMenuObject:MenuObject {public Vector2 pos,size;public RectangularMenuObject(Menu m,MenuObject o,Vector2 p,Vector2 s):base(m,o){pos=p;size=s;}}
 public class MenuObject {public Menu menu;public MenuObject owner;public readonly List<MenuObject> subObjects=new List<MenuObject>();public MenuObject[] nextSelectable=new MenuObject[4];public bool toggled;public virtual bool Selected{get{return menu.selectedObject==this;}}public Page page{get{return this is Page?(Page)this:owner.page;}}public virtual void GrafUpdate(float t){}protected FContainer myContainer;public MenuObject(Menu m,MenuObject o){menu=m;owner=o;}public virtual FContainer Container{get{return myContainer??(owner==null?menu.container:owner.Container);}set{myContainer=value;}}public virtual void RemoveSprites(){if(myContainer!=null){myContainer.RemoveAllChildren();myContainer.RemoveFromContainer();}foreach(var o in subObjects)o.RemoveSprites();}public void RemoveSubObject(MenuObject o){subObjects.Remove(o);if(o is SelectableMenuObject)page.selectables.Remove((SelectableMenuObject)o);}}
 public class Menu {public readonly ProcessManager manager=new ProcessManager();public readonly FContainer container=new FContainer(),cursorContainer=new FContainer();public readonly List<Page> pages=new List<Page>();public MenuObject selectedObject,backObject;public MenuScene scene;public FLabel infoLabel=new FLabel("font","info");public int currentPage,mouseScrollWheelMovement;public bool mouseDown,lastMouseDown,pressButton,holdButton,lastHoldButton,HoldButtonDisregardingFreeze;public InputPackage input,lastInput;public Vector2 mousePosition;public bool Active=true;public Menu(){manager.currentMainLoop=this;Futile.stage.AddChild(container);Futile.stage.AddChild(cursorContainer);}public void DisposePages(){foreach(var p in pages)p.RemoveSprites();container.RemoveFromContainer();cursorContainer.RemoveFromContainer();}public static float HorizontalMoveToGetCentered(ProcessManager m){return (1366-m.rainWorld.options.ScreenSize.x)/2;}}
 public class MainMenu:Menu {readonly List<SimpleButton> mainMenuButtons=new List<SimpleButton>();readonly Dictionary<SimpleButton,Action> callbacks=new Dictionary<SimpleButton,Action>();public MainMenu(){pages.Add(new Page(this,null,"original",0));scene=new MenuScene(this,pages[0]);pages[0].subObjects.Add(scene);foreach(string id in new[]{"STORY","OTHER_MOD","ARENA","REMIX","OPTIONS","EXIT"})AddMainMenuButton(new SimpleButton(this,pages[0],id,id,Vector2.zero,new Vector2(110,30)),delegate{},0);}public List<SimpleButton> NativeButtons{get{return mainMenuButtons;}}public void AddMainMenuButton(SimpleButton button,Action callback,int index){mainMenuButtons.Insert(Math.Max(0,mainMenuButtons.Count-index),button);callbacks[button]=callback;pages[0].subObjects.Add(button);}public void ClickNative(string signal){callbacks[mainMenuButtons.First(b=>b.signalText==signal)]();}}
 public class Page:MenuObject {public Vector2 pos,lastPos;public int index;public List<SelectableMenuObject> selectables=new List<SelectableMenuObject>();public MenuObject lastSelectedObject;public MouseCursor mouseCursor;public Page(Menu m,MenuObject o,string name,int index):base(m,o){this.index=index;mouseCursor=new MouseCursor(m,this,new Vector2(-100,-100));subObjects.Add(mouseCursor);}}
 public class MouseCursor:MenuObject {readonly FSprite cursor=new FSprite("cursor"),shadow=new FSprite("shadow");public MouseCursor(Menu m,MenuObject o,Vector2 pos):base(m,o){myContainer=m.cursorContainer;Container.AddChild(shadow);Container.AddChild(cursor);}public override void RemoveSprites(){base.RemoveSprites();cursor.RemoveFromContainer();shadow.RemoveFromContainer();}public void BumToFront(){Futile.stage.AddChild(menu.cursorContainer);Container.AddChild(shadow);Container.AddChild(cursor);}}
 public class MenuScene:MenuObject {public enum SceneID{Landscape_SU}public readonly FSprite sceneSprite=new FSprite("scene");public MenuScene(Menu m,MenuObject o):base(m,o){Container.AddChild(sceneSprite);}public override void RemoveSprites(){sceneSprite.RemoveFromContainer();base.RemoveSprites();}}
 public class InteractiveMenuScene:MenuScene {public InteractiveMenuScene(Menu m,MenuObject o,SceneID id):base(m,o){}public void HorizontalDisplace(float value){}}
 public class MenuLabel:MenuObject {public FLabel label;public string text{get{return label.text;}set{label.text=value;}}public Vector2 pos,size;public MenuLabel(Menu m,MenuObject o,string text,Vector2 pos,Vector2 size,bool big):base(m,o){this.pos=pos;this.size=size;label=new FLabel("font",text);Container.AddChild(label);}public override void RemoveSprites(){label.RemoveFromContainer();base.RemoveSprites();}}
 public interface ButtonMenuObject {ButtonBehavior GetButtonBehavior{get;}void Clicked();}
 public class ButtonBehavior {public bool greyedOut,clicked;public MenuObject owner;public ButtonBehavior(){}public ButtonBehavior(MenuObject owner){this.owner=owner;}}
 public class SimpleButton:MenuObject {public string signalText;public Vector2 pos,size;public MenuLabel menuLabel;public ButtonBehavior buttonBehav;public SimpleButton(Menu m,MenuObject o,string label,string signal,Vector2 pos,Vector2 size):base(m,o){buttonBehav=new ButtonBehavior(this);signalText=signal;this.pos=pos;this.size=size;menuLabel=new MenuLabel(m,this,label,pos,size,false);subObjects.Add(menuLabel);}}
}
namespace MoreIterators {
 public class CreatorMenuButton:Menu.SimpleButton {public CreatorMenuButton(Menu.MainMenu m,Menu.MenuObject o,string label,string signal,Vector2 pos,Vector2 size):base(m,o,label,signal,pos,size){}}
 public static class CreatorRuntime {public static bool Mark=true,Reset=true;public static string Mode="story",prepared="",revision="";public static readonly List<Dictionary<string,object>> projects=new List<Dictionary<string,object>>();public static List<Dictionary<string,object>> MenuProjects(){return projects.Select(p=>new Dictionary<string,object>(p)).ToList();}public static string Catalog(){return revision;}public static void Prepare(string room,string mode,bool mark,bool reset){prepared=room;}}
 public static class IteratorCatalog {public static bool enabled=true;public static bool OwnerEnabled(string id){return enabled;}public static string Text(Dictionary<string,object> p,string key){object v;return p.TryGetValue(key,out v)?(string)v:"";}}
 public static class CreatorSlugcatSelection {public static int index;public static string Label(Menu.MainMenu m,string room){return "Slugcat"+index;}public static void Next(RainWorld r){index++;}}
 public class MoreIteratorsPlugin {public static readonly MoreIteratorsPlugin Instance=new MoreIteratorsPlugin();public string launched;public void LaunchPreview(Menu.MainMenu m,string room){launched=room;}}
 public static class StudioLauncher {public static string lastPage,lastProject;public static void Open(Menu.MainMenu m,string page,string project){lastPage=page;lastProject=project;}}
 public class BroadcastLine {public string text;}
 public class BroadcastPage {public BroadcastLine[] lines;}
 public class BroadcastProject {public string id,uid,name,region,room;public BroadcastPage[] pages;}
 public static partial class MiDiagnostics {public static readonly List<Exception> errors=new List<Exception>();public static bool FailReport;public static void Report(string code,string source,Exception error,string context){errors.Add(error);if(FailReport)throw new Exception("diagnostic failure");}public static void Warn(string code,string source,string message,string id){}public static void Hit(string node,string context){}}
 public static class CreatorBroadcastCatalog {public static readonly List<BroadcastProject> items=new List<BroadcastProject>();public static List<BroadcastProject> All(){return items;}}

 public class PearlAppearance {public string baseColor,highlightColor;}
 public class CreatorDialogueLine {public string text;}
 public class Group {public string name;public CreatorDialogueLine[] lines;}
 public class PearlReaderProfile {public string name,oracleId,nativeOracleId="";public bool repeatEnabled;public CreatorDialogueLine[] read;public Group[] leaving,returning,repeat=new Group[0];}
 public class PearlProject {public string uid,name;public PearlAppearance appearance;public PearlReaderProfile[] readers;}
 public static class CreatorPearlCatalog {public static readonly List<PearlProject> items=new List<PearlProject>();public static List<PearlProject> All(){return items;}}
 public static class IteratorDesign {public static Color C(string s){return new Color();}public static object ForId(string s){return null;}}
 public class CreatorDialogueProfile {public Reading pearlReading=new Reading();public class Reading {public Group[] repeat=new Group[0],many=new Group[0];}public static CreatorDialogueProfile For(object o){return new CreatorDialogueProfile();}}

 static class Check {
  static int assertions;
  static void Assert(bool ok,string message){assertions++;if(!ok)throw new Exception(message);}
  static Menu.SimpleButton Button(Menu.MainMenu m,string action){return m.pages[0].subObjects.OfType<Menu.SimpleButton>().First(x=>x.signalText=="MI_STUDIO_"+action);}
  static void Advance(Menu.MainMenu m,float seconds){Time.realtimeSinceStartup+=seconds;CreatorStudioMenu.Update(m);}
  static void FinishTransition(Menu.MainMenu m){for(int i=0;i<30&&CreatorStudioMenu.IsTransitioning(m);i++)Advance(m,.05f);Assert(!CreatorStudioMenu.IsTransitioning(m),"transition finishes within bounded time");}
  static void OpenAndFinish(Menu.MainMenu m,int tab){CreatorStudioMenu.Open(m,tab);FinishTransition(m);}
  static void Cleanup(List<Action> cleanup){for(int i=cleanup.Count-1;i>=0;i--)cleanup[i]();}
  static void Press(Menu.MainMenu m,string action){m.selectedObject=Button(m,action);CreatorStudioMenu.Signal(m,"MI_STUDIO_"+action);}
  static bool HasText(Menu.MainMenu m,string text){return m.pages[0].subObjects.OfType<Menu.MenuLabel>().Any(x=>x.label.text==text);}
  static Dictionary<string,object> Project(string id,string name){return new Dictionary<string,object>{{"projectId",id},{"name",name},{"entry","TEST_"+id+"_ENTRY"},{"ai","TEST_"+id+"_AI"}};}
  static FSprite Fade(){return Futile.stage.nodes.OfType<FSprite>().SingleOrDefault(n=>n.name=="Futile_White");}
  static void BeginPhase(Menu.MainMenu m,int phase){
   CreatorStudioMenu.Open(m,0);
   if(phase==0){Advance(m,.2f);return;}
   if(phase==1){Advance(m,.46f);return;}
   FinishTransition(m);CreatorStudioMenu.Signal(m,"MI_STUDIO_CLOSE");Advance(m,phase==2?.2f:.46f);
  }
  static void AssertButtonGate(Menu.MainMenu m){
   var own=new Menu.ButtonBehavior(new Menu.MenuObject(m,m.pages[0])){clicked=true};int ownCalls=0;
   On.Menu.ButtonBehavior.Tick(own,b=>ownCalls++);Assert(ownCalls==0&&!own.clicked,"transition stops own button update and pending click");
   var other=new Menu.MainMenu();var foreign=new Menu.ButtonBehavior(new Menu.MenuObject(other,other.pages[0])){clicked=true};int foreignCalls=0;
   On.Menu.ButtonBehavior.Tick(foreign,b=>foreignCalls++);Assert(foreignCalls==1&&foreign.clicked,"other menu button orig still called once");
   var ownerless=new Menu.ButtonBehavior();int ownerlessCalls=0;On.Menu.ButtonBehavior.Tick(ownerless,b=>ownerlessCalls++);Assert(ownerlessCalls==1,"ownerless button orig still called once");
   int draws=0;var lateNode=new FSprite("native-late-draw");On.Menu.Menu.Draw(m,(owner,t)=>{draws++;Futile.stage.AddChild(lateNode);});
   Assert(draws==1&&Futile.stage.nodes.Last()==Fade(),"draw orig runs once and fade returns above native cursor");lateNode.RemoveFromContainer();other.DisposePages();
  }
  static void TransitionLifecycle(){
   CreatorStudioMenu.Close();CreatorRuntime.projects.Clear();CreatorRuntime.projects.Add(Project("transition","Transition project"));IteratorCatalog.enabled=true;
   var cleanup=new List<Action>();CreatorStudioMenu.InstallHooks(cleanup);
   var m=new Menu.MainMenu();CreatorStudioMenu.Install(m);var original=m.pages[0];var cursor=original.mouseCursor;var scene=m.scene;
   var selection=m.NativeButtons.First(b=>b.signalText=="TEST_MENU");var back=m.NativeButtons.First(b=>b.signalText=="EXIT");m.selectedObject=selection;m.backObject=back;
   var hidden=new FSprite("already-hidden"){isVisible=false};m.container.AddChild(hidden);var nodes=m.container.nodes.ToArray();
   m.pressButton=true;m.mouseScrollWheelMovement=3;m.HoldButtonDisregardingFreeze=true;m.input=new Menu.InputPackage{x=1,y=-1};Input.mouseButton=true;
   m.ClickNative("TEST_MENU");Assert(CreatorStudioMenu.IsTransitioning(m)&&!CreatorStudioMenu.IsOpen&&m.pages[0]==original,"native callback starts fade before swapping page");
   Assert(Fade()!=null&&Fade().shader==m.manager.rainWorld.Shaders["EdgeFade"]&&Fade().alpha==0,"one native EdgeFade overlay starts transparent");
   Assert(!m.pressButton&&m.holdButton&&m.lastHoldButton&&m.mouseDown&&m.lastMouseDown&&m.mouseScrollWheelMovement==0&&m.lastInput.x==m.input.x&&m.lastInput.y==m.input.y,"transition consumes pending click and scroll without synthesizing held-input edges");Input.mouseButton=false;
   var overlay=Fade();Advance(m,.2f);Assert(m.pages[0]==original&&overlay.alpha>0&&overlay.alpha<1,"first half fades existing main menu");
   for(int i=0;i<3;i++){m.ClickNative("TEST_MENU");CreatorStudioMenu.Signal(m,"TEST_MENU");CreatorStudioMenu.Signal(m,"TEST_PEARLS");}
   string prepared=CreatorRuntime.prepared,launched=MoreIteratorsPlugin.Instance.launched;CreatorStudioMenu.Signal(m,"MI_STUDIO_ENTER");Assert(CreatorRuntime.prepared==prepared&&MoreIteratorsPlugin.Instance.launched==launched,"preview signal cannot run during entry fade");
   Assert(Fade()==overlay&&m.pages[0]==original,"repeated entry preserves one overlay and original page");AssertButtonGate(m);
   Advance(m,.26f);var studio=m.pages[0];Assert(CreatorStudioMenu.IsOpen&&studio!=original&&Fade()==overlay&&overlay.alpha==1,"one swap at full black despite repeated clicks");
   Assert(nodes.All(n=>!n.isVisible)&&m.cursorContainer.nodes.Count==2&&cursor.owner==studio,"midpoint preserves native scene and single shared cursor");AssertButtonGate(m);
   CreatorStudioMenu.Signal(m,"MI_STUDIO_ENTER");Assert(CreatorRuntime.prepared==prepared&&MoreIteratorsPlugin.Instance.launched==launched,"preview remains blocked while new page fades in");
   Advance(m,.46f);Assert(!CreatorStudioMenu.IsTransitioning(m)&&Fade()==null&&m.pages[0]==studio,"fade-in completes without another page swap");
   int normalCalls=0;On.Menu.ButtonBehavior.Tick(new Menu.ButtonBehavior(Button(m,"ENTER")),b=>normalCalls++);Assert(normalCalls==1,"normal own button update resumes");
   CreatorStudioMenu.Open(m,1);Assert(!CreatorStudioMenu.IsTransitioning(m)&&m.pages[0]==studio&&Fade()==null&&Button(m,"TAB_1").toggled,"same-page category change stays immediate");
   CreatorStudioMenu.Open(m,0);CreatorStudioMenu.Signal(m,"MI_STUDIO_CLOSE");Assert(CreatorStudioMenu.IsTransitioning(m)&&m.pages[0]==studio,"return begins on studio page");Advance(m,.2f);
   for(int i=0;i<3;i++)CreatorStudioMenu.Signal(m,"MI_STUDIO_CLOSE");Advance(m,.26f);
   Assert(!CreatorStudioMenu.IsOpen&&CreatorStudioMenu.IsTransitioning(m)&&m.pages[0]==original&&m.scene==scene&&m.selectedObject==selection&&m.backObject==back,"return midpoint restores original page scene and focus once");
   Assert(!hidden.isVisible&&scene.sceneSprite.isVisible&&cursor.owner==original&&original.subObjects.Count(x=>x==cursor)==1,"return restores original visibility and cursor ownership");Advance(m,.46f);Assert(Fade()==null&&!CreatorStudioMenu.IsTransitioning(m),"return fade removes overlay");
   m.manager.fadeToBlack=.2f;CreatorStudioMenu.Open(m,0);Assert(!CreatorStudioMenu.IsTransitioning(m)&&m.pages[0]==original,"existing native fade prevents competing transition");m.manager.fadeToBlack=0;
   m.manager.dialog=new object();CreatorStudioMenu.Open(m,0);Assert(!CreatorStudioMenu.IsTransitioning(m),"modal dialog prevents opening");m.manager.dialog=null;
   m.manager.upcomingProcess=new object();CreatorStudioMenu.Open(m,0);Assert(!CreatorStudioMenu.IsTransitioning(m),"queued native process prevents opening");m.manager.upcomingProcess=null;
   m.manager.currentMainLoop=new object();CreatorStudioMenu.Open(m,0);Assert(!CreatorStudioMenu.IsTransitioning(m),"stale menu cannot start transition");m.manager.currentMainLoop=m;
   CreatorStudioMenu.Open(m,0);var otherMenu=new Menu.MainMenu();Advance(otherMenu,.5f);Assert(CreatorStudioMenu.IsTransitioning(m)&&!CreatorStudioMenu.IsTransitioning(otherMenu)&&m.pages[0]==original,"unrelated menu update cannot advance or cancel owner's transition");CreatorStudioMenu.Update(m);Assert(m.pages[0]!=original,"owner update alone swaps page");
   CreatorStudioMenu.Install(otherMenu);Assert(!CreatorStudioMenu.IsOpen&&!CreatorStudioMenu.IsTransitioning(m)&&Fade()==null&&m.pages[0]==original,"installing a new menu cancels old transition");Advance(m,1f);Assert(!CreatorStudioMenu.IsOpen&&m.pages[0]==original,"old update cannot resurrect disposed transition");OpenAndFinish(otherMenu,0);CreatorStudioMenu.Close();otherMenu.DisposePages();m.DisposePages();
   foreach(int phase in new[]{0,1,2,3}){
    var candidate=new Menu.MainMenu();var home=candidate.pages[0];var nativeScene=candidate.scene;var nativeCursor=home.mouseCursor;BeginPhase(candidate,phase);AssertButtonGate(candidate);
    CreatorStudioMenu.Close();Assert(!CreatorStudioMenu.IsOpen&&!CreatorStudioMenu.IsTransitioning(candidate)&&Fade()==null&&candidate.pages[0]==home&&candidate.scene==nativeScene,"immediate close restores page in phase "+phase);
    Assert(nativeCursor.owner==home&&candidate.cursorContainer.nodes.Count==2,"immediate close preserves cursor in phase "+phase);Advance(candidate,2f);Assert(candidate.pages[0]==home&&!CreatorStudioMenu.IsOpen,"cancelled phase cannot later reopen "+phase);candidate.DisposePages();
    candidate=new Menu.MainMenu();home=candidate.pages[0];BeginPhase(candidate,phase);On.Menu.Menu.Shutdown(candidate);Assert(!CreatorStudioMenu.IsOpen&&!CreatorStudioMenu.IsTransitioning(candidate)&&Fade()==null&&candidate.pages[0]==home&&candidate.cursorContainer.parent==null,"shutdown cleans opened or pending page in phase "+phase);Advance(candidate,2f);Assert(!CreatorStudioMenu.IsOpen&&Fade()==null,"shutdown cannot resurrect phase "+phase);
    foreach(string reason in new[]{"process","owner","dialog","native-fade"}){
     candidate=new Menu.MainMenu();home=candidate.pages[0];BeginPhase(candidate,phase);if(reason=="process")candidate.manager.upcomingProcess=new object();else if(reason=="owner")candidate.manager.currentMainLoop=new object();else if(reason=="dialog")candidate.manager.dialog=new object();else candidate.manager.fadeToBlack=.3f;
     Advance(candidate,.01f);Assert(!CreatorStudioMenu.IsOpen&&!CreatorStudioMenu.IsTransitioning(candidate)&&Fade()==null&&candidate.pages[0]==home,"external "+reason+" safely preempts phase "+phase);candidate.DisposePages();
    }
   }
   Cleanup(cleanup);
   foreach(int phase in new[]{0,1,2,3}){
    cleanup=new List<Action>();CreatorStudioMenu.InstallHooks(cleanup);var candidate=new Menu.MainMenu();var home=candidate.pages[0];BeginPhase(candidate,phase);Cleanup(cleanup);Assert(!CreatorStudioMenu.IsOpen&&!CreatorStudioMenu.IsTransitioning(candidate)&&Fade()==null&&candidate.pages[0]==home,"plugin cleanup cancels phase "+phase);Advance(candidate,2f);Assert(!CreatorStudioMenu.IsOpen&&Fade()==null,"unloaded plugin phase stays cancelled "+phase);
    int calls=0;On.Menu.ButtonBehavior.Tick(new Menu.ButtonBehavior(new Menu.MenuObject(candidate,home)),b=>calls++);Assert(calls==1,"unloaded input hook calls orig once in phase "+phase);candidate.DisposePages();
   }
  }
  public static int Main(string[] args){try{Run(args);return 0;}catch(Exception error){Console.Error.WriteLine(error.Message);return 1;}}
  sealed class ThrowingCleanup:Menu.MenuObject {public bool fail=true;public ThrowingCleanup(Menu.Menu m):base(m,m.pages[0]){}public override void RemoveSprites(){if(fail){fail=false;throw new InvalidOperationException("own menu cleanup failed");}}}
  static void AddCleanupFailure(Menu.MainMenu m){var values=(List<Menu.MenuObject>)typeof(CreatorStudioMenu).GetField("controls",System.Reflection.BindingFlags.Static|System.Reflection.BindingFlags.NonPublic).GetValue(null);values.Insert(0,new ThrowingCleanup(m));}
  static void ShutdownFailures(){
   foreach(bool failLog in new[]{false,true}){
    var hooks=new List<Action>();CreatorStudioMenu.InstallHooks(hooks);var m=new Menu.MainMenu();OpenAndFinish(m,0);AddCleanupFailure(m);MiDiagnostics.FailReport=failLog;int calls=0,errors=MiDiagnostics.errors.Count;
    On.Menu.Menu.Shutdown(m,owner=>{calls++;Assert(owner==m,"menu original receives same instance");owner.DisposePages();});
    Assert(calls==1&&MiDiagnostics.errors.Count==errors+1,"menu cleanup/log failure cannot skip native shutdown");
    Assert(!CreatorStudioMenu.IsOpen&&m.pages[0].nameForTest()=="original","cleanup failure still restores native page and drops static ownership");
    MiDiagnostics.FailReport=false;CreatorStudioMenu.Close();Cleanup(hooks);Assert(On.Menu.Menu.ShutdownSubscribers==0,"normal removal unsubscribes shutdown hook");
   }
   var cleanup=new List<Action>();CreatorStudioMenu.InstallHooks(cleanup);var current=new Menu.MainMenu();OpenAndFinish(current,0);AddCleanupFailure(current);int native=0;var expected=new InvalidOperationException("native menu close failed");Exception caught=null;
   try{On.Menu.Menu.Shutdown(current,owner=>{native++;throw expected;});}catch(Exception error){caught=error;}
   Assert(native==1&&Object.ReferenceEquals(caught,expected),"native menu error propagates unchanged after cleanup failure");CreatorStudioMenu.Close();current.DisposePages();Cleanup(cleanup);
   cleanup=new List<Action>();CreatorStudioMenu.InstallHooks(cleanup);current=new Menu.MainMenu();OpenAndFinish(current,0);AddCleanupFailure(current);Cleanup(cleanup);
   Assert(On.Menu.Menu.ShutdownSubscribers==0,"close failure cannot retain removed hook subscription");CreatorStudioMenu.Close();current.DisposePages();
  }
  static void Run(string[] args){
   var a=Project("oc-000101010203","同名项目");var b=Project("oc-000102040506","同名项目");CreatorRuntime.projects.Add(a);CreatorRuntime.projects.Add(b);for(int i=0;i<30;i++)CreatorRuntime.projects.Add(Project("item"+i,"project "+i));
   Assert(CreatorStudioMenu.ProjectDetail(a,CreatorRuntime.projects)=="2000-01-01 01:02:03","valid duplicate creation date");Assert(CreatorStudioMenu.ProjectDetail(b,CreatorRuntime.projects)=="2000-01-02 04:05:06","second duplicate differs");
   var invalid=Project("oc-001332040506","同名项目");Assert(CreatorStudioMenu.ProjectDetail(invalid,CreatorRuntime.projects)==(string)invalid["entry"],"invalid date uses actual room");Assert(CreatorStudioMenu.ProjectDetail(CreatorRuntime.projects[2],CreatorRuntime.projects)=="","unique names not cluttered");
   var cleanup=new List<Action>();CreatorStudioMenu.InstallHooks(cleanup);var m=new Menu.MainMenu();var original=m.pages[0];var cursor=original.mouseCursor;var originalScene=m.scene;var invisible=new FSprite("hidden"){isVisible=false};m.container.AddChild(invisible);var originalNodes=m.container.nodes.ToArray();
   CreatorStudioMenu.Install(m);int index=m.NativeButtons.FindIndex(x=>x.signalText=="TEST_MENU");Assert(m.NativeButtons[index+1].signalText=="REMIX","native order before Remix");Assert(m.NativeButtons[index-1].signalText=="ARENA","after modes and extra mod");Assert(m.NativeButtons[index].size.x==110&&m.NativeButtons[index].size.y==30,"native size");m.selectedObject=m.NativeButtons[index];var originalSelection=m.selectedObject;
   CreatorStudioMenu.Signal(m,"TEST_MENU");FinishTransition(m);Assert(CreatorStudioMenu.IsOpen&&m.pages[0]!=original,"dedicated page");Assert(m.scene!=originalScene,"native background scene");Assert(originalNodes.All(n=>!n.isVisible),"underlying graphics hidden");Assert(m.cursorContainer.parent==Futile.stage&&m.cursorContainer.nodes.Count==2,"shared cursor alive exactly once");Assert(m.pages[0].mouseCursor==cursor&&cursor.owner==m.pages[0],"original cursor reused");Assert(!original.subObjects.Contains(cursor),"cursor not updated twice");
   Assert(Button(m,"PROJECT_oc-000101010203").menuLabel.label.text.Contains("2000-01-01"),"duplicate date visible");Assert(Button(m,"PROJECT_oc-000101010203").toggled,"selection stable with fresh catalog objects");Assert(Button(m,"ENTER").size.x<=400,"compact controls");Assert(Bar(m,"LIST")!=null,"overflow has native selectable scrollbar");
   Press(m,"MARK");Assert(!CreatorRuntime.Mark&&((Menu.SimpleButton)m.selectedObject).signalText=="MI_STUDIO_MARK","mark preserves focus");Press(m,"KEEP");Assert(!CreatorRuntime.Reset&&((Menu.SimpleButton)m.selectedObject).signalText=="MI_STUDIO_KEEP","progress preserves focus");Press(m,"SLUGCAT");Assert(CreatorSlugcatSelection.index==1,"character choice");
   Press(m,"PROJECT_oc-000102040506");Press(m,"ENTER");Assert(MoreIteratorsPlugin.Instance.launched==(string)b["entry"],"selected new project waiting room");Assert(CreatorRuntime.prepared==(string)b["entry"],"prepare target matches launch");Press(m,"SPAWN");Press(m,"ENTER");Assert(MoreIteratorsPlugin.Instance.launched==(string)b["ai"],"explicit chamber target");Press(m,"WEB");Assert(StudioLauncher.lastProject==(string)b["projectId"],"editor opens selected project");
   Bar(m,"LIST").Move(1);Assert(!m.pages[0].subObjects.OfType<Menu.SimpleButton>().Any(x=>x.signalText=="MI_STUDIO_PROJECT_oc-000101010203"),"scroll moves first project offscreen");
   CreatorBroadcastCatalog.items.Add(Broadcast("broadcast","Local broadcast"));Press(m,"TAB_1");Assert(Button(m,"BROADCAST_0").menuLabel.label.text==""&&HasText(m,"Local broadcast"),"broadcast uses icon with detail name");Press(m,"TEXT_DOWN");Assert(((Menu.SimpleButton)m.selectedObject).signalText=="MI_STUDIO_TEXT_UP","last source page focuses enabled previous button");
   CreatorPearlCatalog.items.Add(new PearlProject{uid="pearl",name="Local pearl",readers=new[]{new PearlReaderProfile{name="Reader A",read=new[]{new CreatorDialogueLine{text=new string('文',100)}}},new PearlReaderProfile{name="Reader B",read=new CreatorDialogueLine[0]}}});Press(m,"TAB_2");Assert(Button(m,"PEARL_0").menuLabel.label.text==""&&HasText(m,"Local pearl"),"pearl uses icon with detail name");Press(m,"READER");Assert(Button(m,"READER").menuLabel.label.text.Contains("Reader B"),"reader switch");Assert(m.cursorContainer.nodes.Count==2,"renders never duplicate/remove shared cursor");
   Input.escape=true;m.manager.dialog=new object();CreatorStudioMenu.Update(m);Assert(CreatorStudioMenu.IsOpen,"modal dialog blocks escape");m.manager.dialog=null;CreatorStudioMenu.Update(m);Input.escape=false;FinishTransition(m);Assert(!CreatorStudioMenu.IsOpen&&m.pages[0]==original&&m.scene==originalScene,"return restores page and scene");Assert(m.selectedObject==originalSelection,"return restores selection");Assert(!invisible.isVisible&&originalScene.sceneSprite.isVisible,"restores original visibility states");Assert(cursor.owner==original&&original.subObjects.Count(x=>x==cursor)==1,"return restores original cursor once");Assert(m.cursorContainer.parent==Futile.stage&&m.cursorContainer.nodes.Count==2,"return cursor attached");
   OpenAndFinish(m,0);Assert(!CreatorRuntime.Mark&&!CreatorRuntime.Reset&&CreatorRuntime.Mode=="story","reopen retains user settings");Press(m,"ENTER");Assert(MoreIteratorsPlugin.Instance.launched==(string)b["ai"],"reopen preserves chosen spawn");
   foreach(var size in new[]{new Vector2(960,540),new Vector2(1024,600),new Vector2(1366,768)}){m.manager.rainWorld.options.ScreenSize=size;Press(m,"TAB_0");var labels=m.pages[0].subObjects.OfType<Menu.MenuLabel>().Where(l=>l.label.text.Contains("TEST_")).ToArray();Assert(labels.Length==2&&labels.Min(l=>l.pos.y)>124,"room labels clear bottom action at "+size.y);Assert(m.pages[0].subObjects.OfType<Menu.SimpleButton>().All(x=>x.pos.x>=0&&x.pos.x+x.size.x<=size.x&&x.pos.y>=0&&x.pos.y+x.size.y<=size.y),"controls inside viewport");}
   On.Menu.Menu.Shutdown(m);Assert(!CreatorStudioMenu.IsOpen,"shutdown releases static page");Assert(m.pages[0]==original&&originalScene.sceneSprite.parent==null,"shutdown cleans original scene");Assert(m.cursorContainer.parent==null,"shutdown clears shared cursor normally");
   var fresh=new Menu.MainMenu();OpenAndFinish(fresh,0);Cleanup(cleanup);Assert(!CreatorStudioMenu.IsOpen&&fresh.pages[0].nameForTest()=="original","plugin cleanup restores original page");
   CreatorRuntime.projects.Clear();CreatorRuntime.projects.Add(Project("pending","Applied local project"));IteratorCatalog.enabled=false;OpenAndFinish(fresh,0);
   Assert(Button(fresh,"PROJECT_pending").menuLabel.label.text=="Applied local project","disabled applied project stays discoverable");Assert(Button(fresh,"ENTER").buttonBehav.greyedOut,"disabled content cannot enter");Assert(HasText(fresh,UiText.Get("Local content is disabled"))&&HasText(fresh,UiText.Get("Enable moreiterators.local in Remix.<LINE>Apply the changes and restart the game.")),"existing disabled project shows actionable state");Footer(fresh,"disabled project");
   MoreIteratorsPlugin.Instance.launched=null;CreatorRuntime.prepared="";CreatorStudioMenu.Signal(fresh,"MI_STUDIO_ENTER");Assert(MoreIteratorsPlugin.Instance.launched==null&&CreatorRuntime.prepared=="","direct signal also cannot launch disabled rooms");Press(fresh,"WEB");Assert(StudioLauncher.lastProject=="pending","disabled project opens its own editor");
   IteratorCatalog.enabled=true;Press(fresh,"TAB_0");Assert(!Button(fresh,"ENTER").buttonBehav.greyedOut,"enabled project restores normal controls");Press(fresh,"ENTER");Assert(MoreIteratorsPlugin.Instance.launched!=null,"enabled project can launch");
   CreatorRuntime.projects.Clear();CreatorBroadcastCatalog.items.Clear();CreatorPearlCatalog.items.Clear();
   for(int tab=0;tab<3;tab++){OpenAndFinish(fresh,tab);Assert(!fresh.pages[0].subObjects.OfType<Menu.SimpleButton>().Any(x=>x.signalText=="MI_STUDIO_ENTER"),"empty catalog cannot launch");Assert(!fresh.pages[0].subObjects.OfType<Menu.MenuLabel>().Any(x=>x.label.text.Contains("apply_first")||x.label.text.EndsWith(".empty")||x.label.text.EndsWith(".blank")),"empty tab has no placeholder explanation "+tab);Assert(Button(fresh,"WEB")!=null,"empty tab still opens editor "+tab);Footer(fresh,"empty tab "+tab);}
   CreatorPearlCatalog.items.Add(new PearlProject{uid="no-readers",name="Pearl without readers",readers=new PearlReaderProfile[0]});Press(fresh,"TAB_2");Assert(HasText(fresh,"Pearl without readers")&&!HasText(fresh,UiText.Get("No reader is assigned to this pearl.")),"readerless pearl keeps name without placeholder");
   CreatorPearlCatalog.items[0].readers=new[]{new PearlReaderProfile{name="Empty reader",read=new CreatorDialogueLine[0]}};Press(fresh,"TAB_2");Assert(Button(fresh,"READER")!=null&&!HasText(fresh,UiText.Get("(Blank)")),"empty text preserves reader controls without placeholder");
   CreatorStudioMenu.Close();
   foreach(string locale in args)Collections(locale);
   TransitionLifecycle();
   ShutdownFailures();
   Console.WriteLine(assertions+" studio menu assertions passed");
  }
  static Menu.SimpleButton[] Grid(Menu.MainMenu m,string prefix){return m.pages[0].subObjects.OfType<Menu.SimpleButton>().Where(x=>x.signalText.StartsWith("MI_STUDIO_"+prefix+"_")).ToArray();}
  static void Bounds(Menu.MainMenu m,string context){
   var all=m.pages[0].subObjects.OfType<Menu.SimpleButton>().ToArray();var size=m.manager.rainWorld.options.ScreenSize;
   Assert(all.All(x=>x.pos.x>=0&&x.pos.y>=0&&x.pos.x+x.size.x<=size.x&&x.pos.y+x.size.y<=size.y),"inside viewport "+context);
   for(int i=0;i<all.Length;i++)for(int j=i+1;j<all.Length;j++)Assert(!(all[i].pos.x<all[j].pos.x+all[j].size.x&&all[i].pos.x+all[i].size.x>all[j].pos.x&&all[i].pos.y<all[j].pos.y+all[j].size.y&&all[i].pos.y+all[i].size.y>all[j].pos.y),"buttons do not overlap "+context+" "+all[i].signalText+" "+all[j].signalText);
   Assert(all.All(x=>x.menuLabel.label.textRect.width*x.menuLabel.label.scale<=x.size.x-23.9f),"labels fit "+context);
   Assert(all.All(x=>x.nextSelectable.All(n=>n==null||m.pages[0].subObjects.Contains(n))),"navigation never references removed controls "+context);
   Footer(m,context);
  }
  static void Footer(Menu.MainMenu m,string context){
   var back=Button(m,"CLOSE");var web=Button(m,"WEB");var enter=m.pages[0].subObjects.OfType<Menu.SimpleButton>().FirstOrDefault(b=>b.signalText=="MI_STUDIO_ENTER");
   Assert(back.pos.y==web.pos.y&&back.size.y==web.size.y,"back and editor share one footer baseline and height "+context);
   Assert(back.nextSelectable[2]==web&&web.nextSelectable[0]==back,"footer can be crossed with controller "+context);
   if(enter==null)return;
   Assert(enter.pos.y==web.pos.y&&enter.size.y==web.size.y&&enter.size.x==web.size.x,"preview and editor use aligned equal-sized buttons "+context);
   Assert(enter.pos.x-web.pos.x-web.size.x==12,"preview follows editor with compact gap "+context);
   if(!enter.buttonBehav.greyedOut)Assert(web.nextSelectable[2]==enter&&enter.nextSelectable[0]==web,"preview is reachable from editor "+context);
  }
  static CreatorMenuScrollBar Bar(Menu.MainMenu m,string key){return m.pages[0].subObjects.OfType<CreatorMenuScrollBar>().FirstOrDefault(b=>b.key==key);}
  static BroadcastProject Broadcast(string id,string name){return new BroadcastProject{uid=id,id=id,name=name,region="TEST",room="TEST_AI",pages=new[]{new BroadcastPage{lines=Enumerable.Range(0,60).Select(i=>new BroadcastLine{text="source A line "+i}).ToArray()},new BroadcastPage{lines=new[]{new BroadcastLine{text="source B only"}}}}};}
  static void Wheel(Menu.MainMenu m,float x,float y,int delta){m.mousePosition=new Vector2(x,y);m.mouseScrollWheelMovement=delta;CreatorStudioMenu.Update(m);m.mouseScrollWheelMovement=0;}
  static void ScrollInput(Menu.MainMenu m,CreatorMenuScrollBar bar){
   bar.SetOffset(0);m.manager.menuesMouseMode=true;m.mousePosition=new Vector2(bar.pos.x+8,bar.pos.y+1);m.lastMouseDown=false;m.mouseDown=true;CreatorStudioMenu.Update(m);
   Assert(Bar(m,bar.key)==bar&&bar.Offset==bar.Maximum&&bar.Dragging&&m.selectedObject==bar,"click track reaches bottom without replacing scrollbar");
   m.lastMouseDown=true;m.mousePosition=new Vector2(bar.pos.x+8,bar.pos.y+bar.size.y);CreatorStudioMenu.Update(m);Assert(bar.Offset==0&&m.selectedObject==bar,"drag thumb reaches top with stable focus");
   m.mouseDown=false;CreatorStudioMenu.Update(m);Assert(!bar.Dragging,"release ends drag");
   m.manager.menuesMouseMode=false;m.selectedObject=bar;m.input.y=-1;CreatorStudioMenu.Update(m);Assert(bar.Offset==1&&m.selectedObject==bar,"controller down scrolls while preserving focus");
   for(int frame=0;frame<20;frame++)CreatorStudioMenu.Update(m);Assert(bar.Offset>1&&m.selectedObject==bar,"controller held direction repeats");
   m.input.y=0;CreatorStudioMenu.Update(m);m.input.y=1;int prior=bar.Offset;CreatorStudioMenu.Update(m);Assert(bar.Offset==prior-1,"controller reversal scrolls immediately");m.input.y=0;CreatorStudioMenu.Update(m);m.manager.menuesMouseMode=true;bar.SetOffset(0);
  }
  static void Collections(string locale){
   var raw=Broadcast("raw","Raw");var last=CreatorBroadcastGallery.TextLines(raw,1);Assert(last.Count==1&&last[0]=="source B only","single source page contains only authored lines");Assert(CreatorBroadcastGallery.TextLines(raw,99).Count==0,"missing source page has no fabricated heading");
   raw.pages=new[]{new BroadcastPage{lines=null},null};Assert(CreatorBroadcastGallery.TextLines(raw,0).Count==0&&CreatorBroadcastGallery.TextLines(raw,1).Count==0,"empty or null source pages remain empty");
   CreatorPearlCatalog.items.Clear();CreatorBroadcastCatalog.items.Clear();
   for(int i=0;i<203;i++){
    CreatorPearlCatalog.items.Add(new PearlProject{uid="grid-pearl-"+i,name="珍珠 Pearl "+i,readers=new[]{new PearlReaderProfile{name="FOS",read=Enumerable.Range(0,60).Select(n=>new CreatorDialogueLine{text="pearl line "+n}).ToArray()},new PearlReaderProfile{name=new string('名',80),read=new CreatorDialogueLine[0]}}});
    CreatorBroadcastCatalog.items.Add(Broadcast("grid-broadcast-"+i,"广播 Broadcast "+i));
   }
   var m=new Menu.MainMenu();m.manager.rainWorld.options.language=(InGameTranslator.LanguageID)Enum.Parse(typeof(InGameTranslator.LanguageID),locale);UiText.Use(m.manager.rainWorld);
   foreach(var size in new[]{new Vector2(640,480),new Vector2(960,540),new Vector2(1024,600),new Vector2(1366,768),new Vector2(1920,1080)}){
    m.manager.rainWorld.options.ScreenSize=size;
    foreach(int tab in new[]{1,2}){
     OpenAndFinish(m,tab);string prefix=tab==1?"BROADCAST":"PEARL",sprite=tab==1?"Symbol_Satellite":"Symbol_Pearl";var bar=Bar(m,"LIST");bar.SetOffset(0);var cells=Grid(m,prefix);int capacity=cells.Length;
     Assert(capacity>5&&capacity<203,"scrollable collection "+locale);
     Assert(cells.All(b=>b.size.x==42&&b.size.y==42&&b.menuLabel.label.text==""),"native square icon buttons "+locale);
     int columns=cells.Select(b=>b.pos.x).Distinct().Count();Assert(columns==(size.x>=960?5:3),"five columns where viewport permits "+size.x);
     var dots=m.pages[0].Container.nodes.OfType<FSprite>().Where(s=>s.name==sprite).ToArray();Assert(dots.Length==cells.Length,"exactly one icon per button");
     for(int i=0;i<cells.Length;i++)Assert(dots[i].scale==1&&dots[i].x==cells[i].pos.x+21&&dots[i].y==cells[i].pos.y+21,"native sprite centered in clickable frame");
     Assert(cells[1].pos.x-cells[0].pos.x==50&&cells[0].pos.y-cells[columns].pos.y==50,"scrolling grid retains 50px pitch");
     Assert(cells[0].nextSelectable[0]==cells[0]&&cells[0].nextSelectable[1]==Button(m,"TAB_"+tab)&&cells[0].nextSelectable[2]==cells[1]&&cells[0].nextSelectable[3]==cells[columns],"row-major four-direction navigation");
     Assert(cells[columns-1].nextSelectable[2]==bar&&cells.Last().nextSelectable[3]==bar,"scrollbar reachable from edge and bottom");
     Press(m,prefix+"_1");Assert(Grid(m,prefix).Single(b=>b.toggled).signalText=="MI_STUDIO_"+prefix+"_1","selection updates exactly one frame");
     Assert(HasText(m,tab==1?"广播 Broadcast 1":"珍珠 Pearl 1"),"name appears only in selected details");Bounds(m,locale+" "+size.x+" tab"+tab);
     Assert(!m.pages[0].subObjects.OfType<Menu.SimpleButton>().Any(b=>b.signalText=="MI_STUDIO_UP"||b.signalText=="MI_STUDIO_DOWN"),"list pagination buttons removed");
     var textBar=Bar(m,"TEXT");Assert(textBar!=null,"long text scrolls");var oldLabels=m.pages[0].subObjects.OfType<Menu.MenuLabel>().ToArray();var readerOrNext=Button(m,tab==1?"TEXT_DOWN":"READER");
     Wheel(m,textBar.pos.x-20,textBar.pos.y+20,1);Assert(textBar.Offset==3&&Bar(m,"TEXT")==textBar&&oldLabels.All(l=>m.pages[0].subObjects.Contains(l))&&m.pages[0].subObjects.Contains(readerOrNext),"text wheel updates lines without replacing controls");
     textBar.SetOffset(textBar.Maximum);Assert(HasText(m,tab==1?"source A line 59":"pearl line 59"),"last authored line is reachable by scrolling");
     ScrollInput(m,textBar);
     if(tab==1){
      Assert(Button(m,"TEXT_UP").buttonBehav.greyedOut&&!Button(m,"TEXT_DOWN").buttonBehav.greyedOut&&HasText(m,"source A line 0")&&!HasText(m,"source B only"),"source first page and disabled previous");
      Assert(Button(m,"TEXT_DOWN").nextSelectable[1]==textBar&&textBar.nextSelectable[0]==Button(m,"TEXT_DOWN"),"controller can enter and leave broadcast text scrollbar");
      Press(m,"TEXT_DOWN");Assert(HasText(m,"source B only")&&!HasText(m,"source A line 0")&&Bar(m,"TEXT")==null,"next shows actual source page rather than screenful");
      Assert(m.selectedObject==Button(m,"TEXT_UP")&&Button(m,"TEXT_DOWN").buttonBehav.greyedOut,"last source page has disabled next and enabled previous focus");
      var prev=Button(m,"TEXT_UP");var next=Button(m,"TEXT_DOWN");var web=Button(m,"WEB");Assert(Math.Abs((prev.pos.x+next.pos.x+next.size.x)*.5f-(web.pos.x+web.size.x*.5f))<.1,"source navigation centered with editor button");Press(m,"TEXT_UP");Assert(HasText(m,"source A line 0")&&Bar(m,"TEXT").Offset==0,"returning to source page starts at top");
     }else{
      Assert(!m.pages[0].subObjects.OfType<Menu.SimpleButton>().Any(b=>b.signalText=="MI_STUDIO_TEXT_UP"||b.signalText=="MI_STUDIO_TEXT_DOWN"),"pearl has continuous scroll without page buttons");
      var r=Button(m,"READER");var stage=Button(m,"STAGE");Assert(r.pos.y==stage.pos.y&&stage.pos.x==r.pos.x+r.size.x+12,"short reader controls adjacent");var web=Button(m,"WEB");Assert(Math.Abs((r.pos.x+stage.pos.x+stage.size.x)*.5f-(web.pos.x+web.size.x*.5f))<.1,"reader controls centered");
      for(int n=0;n<5;n++){Press(m,"STAGE");Bounds(m,"localized stage "+locale+" "+n);}
      Press(m,"READER");r=Button(m,"READER");stage=Button(m,"STAGE");Assert(stage.pos.y==r.pos.y-42&&Math.Abs(stage.pos.x+stage.size.x*.5f-r.pos.x-r.size.x*.5f)<.1,"long reader wraps into two centered rows");Assert(r.menuLabel.label.text.Contains(new string('名',80)),"full reader name retained");Bounds(m,"long reader "+size.x);Press(m,"READER");
     }
     bar=Bar(m,"LIST");var detailButtons=new[]{Button(m,"WEB"),Button(m,tab==1?"TEXT_DOWN":"READER")};var oldIcons=m.pages[0].Container.nodes.OfType<FSprite>().Where(s=>s.name==sprite).ToArray();m.selectedObject=bar;bar.Move(1);
     Assert(Grid(m,prefix)[0].signalText=="MI_STUDIO_"+prefix+"_"+columns,"list advances one row");Assert(oldIcons.All(i=>i.parent==null),"old viewport icons released");Assert(m.selectedObject==bar&&detailButtons.All(b=>m.pages[0].subObjects.Contains(b)),"list scroll preserves scrollbar and detail controls");
     bar.SetOffset(bar.Maximum);cells=Grid(m,prefix);Assert(cells.Length<=capacity&&cells.Last().signalText=="MI_STUDIO_"+prefix+"_202","last partial row accessible");Bounds(m,"last row "+locale);Wheel(m,cells[0].pos.x+10,cells[0].pos.y+10,-1);Assert(bar.Offset==bar.Maximum-1,"wheel scrolls one collection row");ScrollInput(m,bar);
    }
   }
   CreatorRuntime.projects.Add(Project("compact-options","Options"));
   foreach(var size in new[]{new Vector2(640,480),new Vector2(960,540),new Vector2(1024,600),new Vector2(1366,768),new Vector2(1920,1080)}){
    m.manager.rainWorld.options.ScreenSize=size;Press(m,"TAB_0");var optionButtons=new[]{"SLUGCAT","SPAWN","MARK","KEEP","MODE"}.Select(v=>Button(m,v)).ToArray();Assert(optionButtons.Select(b=>b.size.x).Distinct().Count()==1&&optionButtons[0].size.x<400,"chamber options use aligned content width");Bounds(m,"chamber "+locale+" "+size.x);
    string markText=locale=="English"?(CreatorRuntime.Mark?"Mark: Yes":"Mark: No"):locale=="TraditionalChinese"?(CreatorRuntime.Mark?"印記：有":"印記：無"):(CreatorRuntime.Mark?"印记：有":"印记：无");Assert(Button(m,"MARK").menuLabel.label.text==markText,"mark uses a complete localized sentence "+locale);
    var footerTop=Button(m,"ENTER").pos.y+Button(m,"ENTER").size.y;Assert(m.pages[0].subObjects.OfType<Menu.MenuLabel>().Where(l=>l.label.text.Contains("TEST_")).All(l=>l.pos.y>=footerTop+12),"room identifiers do not overlap compact footer "+locale+" "+size.x);
   }
   m.manager.rainWorld.options.ScreenSize=new Vector2(1366,768);Press(m,"TAB_0");
   for(int i=0;i<40;i++)CreatorRuntime.projects.Add(Project("scroll-project-"+i,"Room "+i));Press(m,"TAB_0");var projectBar=Bar(m,"LIST");var launch=Button(m,"ENTER");ScrollInput(m,projectBar);Assert(m.pages[0].subObjects.Contains(launch),"project drag leaves selected room controls stable");
   CreatorStudioMenu.Close();Assert(m.cursorContainer.nodes.Count==2,"grid closes without removing original cursor");
  }
  static string nameForTest(this Menu.Page p){return p.subObjects.OfType<Menu.SimpleButton>().Any(x=>x.signalText=="STORY")?"original":"studio";}
 }
}
