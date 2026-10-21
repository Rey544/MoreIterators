namespace MoreIterators {
using System;
using System.Collections.Generic;
using UnityEngine;
public static class CreatorBroadcastGallery {
 static Menu.MainMenu menu;static int selected,page,textPage;static List<Menu.MenuObject> items=new List<Menu.MenuObject>();static FSprite background;
 static readonly Dictionary<Menu.SimpleButton,bool> disabled=new Dictionary<Menu.SimpleButton,bool>();
 public static void Open(Menu.MainMenu m){Close();menu=m;selected=page=textPage=0;foreach(var o in m.pages[0].subObjects){var b=o as Menu.SimpleButton;if(b!=null){disabled[b]=b.buttonBehav.greyedOut;b.buttonBehav.greyedOut=true;}}Render();}
 static void Clear(){foreach(var o in items){o.RemoveSprites();if(menu!=null)menu.pages[0].RemoveSubObject(o);}items.Clear();if(background!=null)background.RemoveFromContainer();background=null;}
 public static void Close(){Clear();foreach(var p in disabled)p.Key.buttonBehav.greyedOut=p.Value;disabled.Clear();menu=null;}
 static void Label(string text,float x,float y,float w,bool big=false){var l=new Menu.MenuLabel(menu,menu.pages[0],text,new Vector2(x,y),new Vector2(w,30),big);items.Add(l);menu.pages[0].subObjects.Add(l);}
 static void Button(string text,string id,float x,float y,float w){var b=new CreatorMenuButton(menu,menu.pages[0],text,"MI_BROADCAST_"+id,new Vector2(x,y),new Vector2(w,35));items.Add(b);menu.pages[0].subObjects.Add(b);}
 static void Render(){Clear();if(menu==null)return;UiText.Use(menu.manager.rainWorld);float w=menu.manager.rainWorld.options.ScreenSize.x,h=menu.manager.rainWorld.options.ScreenSize.y;
  background=new FSprite("pixel"){color=Color.black,alpha=.96f,anchorX=0,anchorY=0,scaleX=w,scaleY=h};menu.pages[0].Container.AddChild(background);
  Label(UiText.Get("game.gallery.broadcast.title"),35,h-60,w-70,true);Button(UiText.Get("game.gallery.back"),"CLOSE",35,25,200);Button(UiText.Get("game.gallery.broadcast.studio"),"WEB",250,25,180);
  var all=CreatorBroadcastCatalog.All();if(all.Count==0)return;
  selected=Mathf.Clamp(selected,0,all.Count-1);int per=Math.Max(3,(int)((h-210)/43));page=Mathf.Clamp(page,0,(all.Count-1)/per);
  for(int i=page*per;i<Math.Min(all.Count,(page+1)*per);i++)Button(all[i].id+" · "+all[i].name,"SELECT_"+i,35,h-120-(i%per)*43,230);
  if(all.Count>per){Button(UiText.Get("game.gallery.broadcast.previous_group"),"PREV",35,78,110);Button(UiText.Get("game.gallery.broadcast.next_group"),"NEXT",155,78,110);}
  var p=all[selected];Label(p.name+"  ["+p.id+"]",295,h-110,w-330,true);Label(p.region+" / "+p.room,295,h-150,w-330);
  var lines=TextLines(p);
  int size=Math.Max(3,(int)((h-290)/27));textPage=Mathf.Clamp(textPage,0,Math.Max(0,(lines.Count-1)/size));for(int i=0;i<size&&textPage*size+i<lines.Count;i++)Label(lines[textPage*size+i],295,h-202-i*27,w-330);
   Button(UiText.Get("game.gallery.previous_text"),"TEXT_PREV",465,25,110);Button(UiText.Get("game.gallery.next_text"),"TEXT_NEXT",585,25,110);Label((textPage+1)+" / "+Math.Max(1,(lines.Count+size-1)/size),710,28,100);
 }
  internal static List<string> TextLines(BroadcastProject project){
   var result=new List<string>();bool invalid=false;
   if(project.pages==null){MiDiagnostics.Warn("MI_BROADCAST_NULL_TEXT","CreatorBroadcastGallery.TextLines","Null broadcast pages were treated as empty.",project.id);return result;}
   for(int i=0;i<project.pages.Length;i++){
    result.Add(UiText.Format("game.gallery.page_heading",i+1));var page=project.pages[i];
    if(page==null||page.lines==null)invalid=true;
    else foreach(var line in page.lines){
     if(line==null||line.text==null){invalid=true;continue;}
     foreach(string part in line.text.Replace("<LINE>","\n").Split('\n'))for(int j=0;j<part.Length;j+=36)result.Add(part.Substring(j,Math.Min(36,part.Length-j)));
    }
    result.Add("");
   }
   if(invalid)MiDiagnostics.Warn("MI_BROADCAST_NULL_TEXT","CreatorBroadcastGallery.TextLines","Null broadcast text was treated as empty.",project.id);
   return result;
  }
  public static bool Signal(Menu.MainMenu m,string message){if(!message.StartsWith("MI_BROADCAST_"))return false;string s=message.Substring(13);
  if(s=="CLOSE"){Close();CreatorRuntime.Signal(m,"TEST_MENU");return true;}if(s=="WEB"){StudioLauncher.Open(m,"broadcasts");return true;}
  if(s.StartsWith("SELECT_")){int.TryParse(s.Substring(7),out selected);textPage=0;}if(s=="PREV")page--;if(s=="NEXT")page++;if(s=="TEXT_PREV")textPage--;if(s=="TEXT_NEXT")textPage++;Render();return true;
 }
}
}
