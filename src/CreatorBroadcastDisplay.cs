namespace MoreIterators {
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;
using UnityEngine;
using RWCustom;

// Native HUD slot and fonts, with explicit pages and broadcast-wide timing. No change
// to ordinary Spearmaster broadcasts, progression counters or their collection.
public sealed class CreatorBroadcastDisplay:MoreSlugcats.ChatLogDisplay {
 sealed class Row {public BroadcastLine style;public string text;public float height;public int[] chars;}
 readonly List<List<Row>> pages=new List<List<Row>>();int pageIndex,lineIndex,shown;float elapsed,hold;bool completed,disposed;
 RainWorldGame Game {get{var p=hud.owner as Player;return p==null?null:p.room==null?null:p.room.game;}}
 public CreatorBroadcastDisplay(HUD.HUD hud,BroadcastProject project):base(hud,new string[]{"…"}){
  base.ClearSprites();
  float width=hud.rainWorld.options.ScreenSize.x-160,height=hud.rainWorld.options.ScreenSize.y-150;
  foreach(var page in project.pages){var rows=new List<Row>();float used=0;
   foreach(var source in page.lines){if(source==null||String.IsNullOrWhiteSpace(source.text))continue;var l=CreatorBroadcastStyle.Resolve(project,source);var measure=new FLabel(FontName(l),"");measure.scale=Mathf.Clamp(l.size,.5f,2);
    string wrapped=Wrap(measure,l.text,width);foreach(string part in SplitHeight(measure,wrapped,height)){
     measure.text=part;float h=Mathf.Max(15,measure.textRect.height*measure.scaleY)+15;
     if(used+h>height&&rows.Count>0){pages.Add(rows);rows=new List<Row>();used=0;}
     rows.Add(new Row{style=l,text=part,height=h,chars=StringInfo.ParseCombiningCharacters(part)});used+=h;
    }
   }
   if(rows.Count>0)pages.Add(rows);
  }
  if(pages.Count==0){pages.Add(new List<Row>{new Row{style=new BroadcastLine(),text="…",height=30,chars=new[]{0}}});}
  BuildPage();
 }
 static string FontName(BroadcastLine l){return l.font=="display"?Custom.GetDisplayFont():Custom.GetFont();}
 static string Wrap(FLabel measure,string text,float width){
  var output=new StringBuilder();foreach(string paragraph in text.Replace("<LINE>","\n").Replace("\r","").Split('\n')){
   string row="";var chars=StringInfo.GetTextElementEnumerator(paragraph);
   while(chars.MoveNext()){string ch=(string)chars.Current;measure.text=row+ch;
    if(row.Length>0&&measure.textRect.width*measure.scaleX>width){int space=row.LastIndexOf(' ');if(space>row.Length/2){output.Append(row.Substring(0,space)).Append('\n');row=row.Substring(space+1);}else{output.Append(row).Append('\n');row="";}}
    row+=ch;
   }output.Append(row).Append('\n');
  }return output.ToString().TrimEnd('\n');
 }
 static IEnumerable<string> SplitHeight(FLabel measure,string text,float height){string block="";foreach(string row in text.Split('\n')){string next=block.Length==0?row:block+"\n"+row;measure.text=next;if(block.Length>0&&measure.textRect.height*measure.scaleY+15>height){yield return block;block=row;}else block=next;}if(block.Length>0)yield return block;}
 void RemovePage(){if(label!=null)foreach(var l in label)l.RemoveFromContainer();if(sprites!=null)foreach(var s in sprites)s.RemoveFromContainer();}
 void BuildPage(){RemovePage();var rows=pages[pageIndex];label=new FLabel[rows.Count];sprites=new FSprite[rows.Count];messageWidths=new float[rows.Count];
  for(int i=0;i<rows.Count;i++){var row=rows[i];var l=new FLabel(FontName(row.style),row.text){anchorX=.5f,anchorY=1,alignment=FLabelAlignment.Center,scale=Mathf.Clamp(row.style.size,.5f,2),color=IteratorDesign.C(row.style.color)};messageWidths[i]=l.textRect.width*l.scaleX;l.text="";label[i]=l;hud.fContainers[1].AddChild(l);
   sprites[i]=new FSprite("pixel"){color=Color.black,alpha=.75f,scaleX=messageWidths[i]+30,scaleY=row.height+8,anchorY=1};hud.fContainers[1].AddChild(sprites[i]);sprites[i].MoveBehindOtherNode(l);
  }lineIndex=shown=0;elapsed=hold=0;
 }
 public override void Update(){if(!completed&&Game!=null)Game.pauseUpdate=true;}
 public override void Draw(float timeStacker){if(completed||disposed)return;var game=Game;if(game!=null&&game.pauseMenu!=null)return;
  float dt=Mathf.Min(Time.deltaTime,.1f);var rows=pages[pageIndex];var current=rows[lineIndex];
  if(shown<current.chars.Length){elapsed+=dt*Mathf.Clamp(current.style.speed,.25f,4)*(Input.GetKey(KeyCode.Space)?5:1);float step=(HUD.DialogBox.GetDelay()+1)/60f;
   while(elapsed>=step&&shown<current.chars.Length){shown++;elapsed-=step;}
   label[lineIndex].text=current.text.Substring(0,shown==current.chars.Length?current.text.Length:current.chars[shown]);
  }else{hold+=dt;if(hold>=current.style.hold){hold=elapsed=0;shown=0;lineIndex++;if(lineIndex>=rows.Count){pageIndex++;if(pageIndex>=pages.Count){completed=true;slatedForDeletion=true;if(game!=null)game.pauseUpdate=false;return;}BuildPage();rows=pages[pageIndex];}}}
  float total=0;foreach(var row in rows)total+=row.height+15;float y=(hud.rainWorld.options.ScreenSize.y+total)*.5f,x=hud.rainWorld.options.ScreenSize.x*.5f;
  for(int i=0;i<rows.Count;i++){label[i].SetPosition(x,y);sprites[i].SetPosition(x,y+5);label[i].isVisible=sprites[i].isVisible=i<=lineIndex;y-=rows[i].height+15;}
 }
 public override void ClearSprites(){if(disposed)return;disposed=true;RemovePage();if(Game!=null)Game.pauseUpdate=false;}
}
}
