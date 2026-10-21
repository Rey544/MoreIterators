using System;
using System.Collections.Generic;
using System.Globalization;
using UnityEngine;

namespace MoreIterators {
 // Uses the game's registered story identities. DMS sees the ordinary player
 // slugcatStats.name and owns its skin lookup; no skin assets/config are copied.
 public static class CreatorSlugcatSelection {
  static string selected="";
  static RainWorld owner;
  static SlugcatStats.Name sessionCharacter,previousInGame;
  static List<Color> previousColors;

  public static List<SlugcatStats.Name> Available(RainWorld game){
   var result=new List<SlugcatStats.Name>();
   if(game==null||game.progression==null)return result;
   foreach(string value in SlugcatStats.Name.values.entries){
    var name=new SlugcatStats.Name(value,false);
    if(SlugcatStats.HiddenOrUnplayableSlugcat(name))continue;
    if(SlugcatStats.IsSlugcatFromMSC(name)&&!ModManager.MSC||value=="Watcher"&&!ModManager.Watcher)continue;
    if(!SlugcatStats.SlugcatUnlocked(name,game)&&!game.progression.IsThereASavedGame(name))continue;
    result.Add(name);
   }
   return result;
  }

  public static bool Select(RainWorld game,string value){
   if(String.IsNullOrEmpty(value)){selected="";return true;}
   foreach(var name in Available(game))if(name.value==value){selected=value;return true;}
   return false;
  }

  public static void Next(RainWorld game){
   var choices=Available(game);int current=-1;
   for(int i=0;i<choices.Count;i++)if(choices[i].value==selected){current=i;break;}
   selected=current+1<choices.Count?choices[current+1].value:"";
  }

  public static SlugcatStats.Name Resolve(RainWorld game,string room){
   if(selected.Length>0){
    foreach(var name in Available(game))if(name.value==selected)return name;
    // A removed/disabled campaign never survives into the next launch.
    selected="";
   }
   return NativeRoomProjects.Character(room);
  }

  public static string Label(Menu.MainMenu menu,string room){
   var name=Resolve(menu.manager.rainWorld,room);
   string display=menu.Translate(SlugcatStats.getSlugcatName(name));
   return UiText.Format(selected.Length==0?"game.menu.slugcat_auto":"game.menu.slugcat",display);
  }

  public static SlugcatStats.Name Begin(RainWorld game,string room){
   if(owner!=null)throw new InvalidOperationException("A temporary story-character session is already active.");
   var character=Resolve(game,room);
   owner=game;previousInGame=game.inGameSlugCat;previousColors=PlayerGraphics.customColors;
   sessionCharacter=character;
   game.inGameSlugCat=character;
   PlayerGraphics.customColors=StoryColors(game,character);
   return character;
  }

  public static SlugcatStats.Name SessionCharacter(string room){return sessionCharacter??NativeRoomProjects.Character(room);}

  public static void Restore(){
   if(owner==null)return;
   owner.inGameSlugCat=previousInGame;PlayerGraphics.customColors=previousColors;
   owner=null;sessionCharacter=previousInGame=null;previousColors=null;
  }

  static List<Color> StoryColors(RainWorld game,SlugcatStats.Name name){
   var progress=game.progression.miscProgressionData;bool enabled;List<string> choices;
   if(!ModManager.MMF||!progress.colorsEnabled.TryGetValue(name.value,out enabled)||!enabled||!progress.colorChoices.TryGetValue(name.value,out choices))return null;
   var colors=new List<Color>();
   foreach(string text in choices){
    string[] values=text.Split(',');float h,s,l;
    if(values.Length!=3||!Single.TryParse(values[0],NumberStyles.Float,CultureInfo.InvariantCulture,out h)||!Single.TryParse(values[1],NumberStyles.Float,CultureInfo.InvariantCulture,out s)||!Single.TryParse(values[2],NumberStyles.Float,CultureInfo.InvariantCulture,out l)||Single.IsNaN(h)||Single.IsNaN(s)||Single.IsNaN(l)||Single.IsInfinity(h)||Single.IsInfinity(s)||Single.IsInfinity(l))return null;
    colors.Add(RWCustom.Custom.HSL2RGB(h,s,l));
   }
   return colors;
  }
 }
}
