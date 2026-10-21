namespace MoreIterators {
using System;
using System.Collections.Generic;
using UnityEngine;

// Uses the native collection's pearl symbols, column layout and menu controls.
// This local collection is unlocked by import, independent of campaign progression.
public static class CreatorPearlGallery {
 static Menu.MainMenu menu;static int selected,reader,page,textPage,stage;
 static readonly List<Menu.MenuObject> objects=new List<Menu.MenuObject>();static readonly List<FSprite> sprites=new List<FSprite>();
 static readonly Dictionary<Menu.SimpleButton,bool> disabled=new Dictionary<Menu.SimpleButton,bool>();
 public static void Open(Menu.MainMenu m){Close();menu=m;selected=reader=page=textPage=stage=0;foreach(var o in m.pages[0].subObjects){var b=o as Menu.SimpleButton;if(b!=null){disabled[b]=b.buttonBehav.greyedOut;b.buttonBehav.greyedOut=true;}}Render();}
 static void Clear(){foreach(var o in objects){o.RemoveSprites();if(menu!=null)menu.pages[0].RemoveSubObject(o);}objects.Clear();foreach(var s in sprites)s.RemoveFromContainer();sprites.Clear();}
 public static void Close(){Clear();foreach(var pair in disabled)pair.Key.buttonBehav.greyedOut=pair.Value;disabled.Clear();menu=null;}
 static void Label(string text,float x,float y,float w,bool big=false){var l=new Menu.MenuLabel(menu,menu.pages[0],text,new Vector2(x,y),new Vector2(w,30),big);objects.Add(l);menu.pages[0].subObjects.Add(l);}
 static void Button(string text,string signal,float x,float y,float w=150,float h=36){var b=new CreatorMenuButton(menu,menu.pages[0],text,"MI_PEARL_"+signal,new Vector2(x,y),new Vector2(w,h));objects.Add(b);menu.pages[0].subObjects.Add(b);}
 static void Sprite(FSprite s){sprites.Add(s);menu.pages[0].Container.AddChild(s);}
 static void Render(){Clear();if(menu==null)return;UiText.Use(menu.manager.rainWorld);float width=menu.manager.rainWorld.options.ScreenSize.x,height=menu.manager.rainWorld.options.ScreenSize.y;
  var back=new FSprite("pixel"){color=Color.black,alpha=.96f,anchorX=0,anchorY=0,scaleX=width,scaleY=height};Sprite(back);
  Label(UiText.Get("game.gallery.pearl.title"),40,height-55,260,true);Button(UiText.Get("game.gallery.back"),"CLOSE",40,20,210);Button(UiText.Get("game.gallery.pearl.studio"),"WEB",270,20,180);
  var pearls=CreatorPearlCatalog.All();if(pearls.Count==0)return;
  selected=Mathf.Clamp(selected,0,pearls.Count-1);page=Mathf.Clamp(page,0,(pearls.Count-1)/52);int rows=13;
  for(int i=page*52;i<Math.Min(pearls.Count,(page+1)*52);i++){int local=i%52;float x=40+local/rows*62,y=height-115-local%rows*Mathf.Min(42,(height-180)/13);Button("","SELECT_"+i,x,y,56,36);var dot=new FSprite("Symbol_Pearl"){x=x+28,y=y+19,scale=.45f,color=Color.Lerp(IteratorDesign.C(pearls[i].appearance.baseColor),IteratorDesign.C(pearls[i].appearance.highlightColor),.35f)};Sprite(dot);}
  if(pearls.Count>52){Button(UiText.Get("game.gallery.previous_page"),"PREV",40,65,100);Button(UiText.Get("game.gallery.next_page"),"NEXT",150,65,100);}
  var p=pearls[selected];float left=320,span=width-left-35;Label(p.id+" · "+p.name,left,height-110,span,true);
  if(p.readers.Length==0)return;
  reader=Mathf.Clamp(reader,0,p.readers.Length-1);var r=p.readers[reader];
  float stageWidth=Mathf.Min(210,(span-10)*.5f),readerWidth=Mathf.Min(200,span-stageWidth-10);
  float controlsX=width-35-readerWidth-10-stageWidth,controlsY=height-65;
  Button(UiText.Format("game.gallery.pearl.reader",r.name),"READER",controlsX,controlsY,readerWidth,30);
  string[] stageKeys={"game.gallery.pearl.stage.read","game.gallery.pearl.stage.repeat","game.gallery.pearl.stage.leaving","game.gallery.pearl.stage.returning","game.gallery.pearl.stage.many"};Button(UiText.Get(stageKeys[stage])+"  ›","STAGE",controlsX+readerWidth+10,controlsY,stageWidth,30);
  var shared=CreatorDialogueProfile.For(IteratorDesign.ForId(r.oracleId)).pearlReading;
  var lines=new List<string>();if(stage==0)foreach(var line in r.read)Wrap(lines,line.text);else{var pools=stage==1?shared.repeat:stage==2?r.leaving:stage==3?r.returning:shared.many;foreach(var group in pools){Wrap(lines,"〔"+group.name+"〕");foreach(var line in group.lines)Wrap(lines,line.text);lines.Add("");}}
  int perPage=Math.Max(5,(int)((height-210)/29));textPage=Mathf.Clamp(textPage,0,Math.Max(0,(lines.Count-1)/perPage));
  for(int i=0;i<perPage&&textPage*perPage+i<lines.Count;i++)Label(lines[textPage*perPage+i],left,height-170-i*29,span);
  if(lines.Count>perPage){Button(UiText.Get("game.gallery.previous_text"),"TEXT_PREV",left,70,130);Button(UiText.Get("game.gallery.next_text"),"TEXT_NEXT",left+140,70,130);Label((textPage+1)+" / "+((lines.Count+perPage-1)/perPage),left+285,72,120);}
 }
 static void Wrap(List<string> result,string text){if(text==null)return;foreach(var part in text.Replace("<LINE>","\n").Split('\n')){if(part.Length==0){result.Add("");continue;}for(int i=0;i<part.Length;i+=38)result.Add(part.Substring(i,Math.Min(38,part.Length-i)));}}
 public static bool Signal(Menu.MainMenu m,string signal){if(!signal.StartsWith("MI_PEARL_"))return false;string s=signal.Substring(9);if(s=="CLOSE"){Close();CreatorRuntime.Signal(m,"TEST_MENU");return true;}if(s=="WEB"){StudioLauncher.Open(m,"pearls");return true;}if(s.StartsWith("SELECT_")){int.TryParse(s.Substring(7),out selected);reader=textPage=stage=0;}if(s=="READER"){var p=CreatorPearlCatalog.All();if(p.Count>selected&&p[selected].readers.Length>0)reader=(reader+1)%p[selected].readers.Length;textPage=0;}if(s=="STAGE"){stage=(stage+1)%5;textPage=0;}if(s=="PREV")page--;if(s=="NEXT")page++;if(s=="TEXT_PREV")textPage--;if(s=="TEXT_NEXT")textPage++;Render();return true;}
}
}
