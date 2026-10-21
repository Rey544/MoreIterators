namespace MoreIterators {
using System;
using System.Collections.Generic;
using UnityEngine;

public static class CreatorHeldItems {
 public static bool IsWeapon(PhysicalObject item){return item is Weapon;}
 public static List<PhysicalObject> Visible(Player player){var result=new List<PhysicalObject>();if(player==null)return result;if(player.grasps!=null)foreach(var grasp in player.grasps)if(grasp!=null&&grasp.grabbed!=null&&grasp.grabbed.room==player.room&&!result.Contains(grasp.grabbed))result.Add(grasp.grabbed);if(player.spearOnBack!=null&&player.spearOnBack.spear!=null&&player.spearOnBack.spear.room==player.room&&!result.Contains(player.spearOnBack.spear))result.Add(player.spearOnBack.spear);return result;}
 // Categories are independent; no stomach inventory is visible to an observer.
 public sealed class Tags {public bool weapons,pearls,items,creatures,corpses,food;public int Count{get{return (weapons?1:0)+(pearls?1:0)+(items?1:0)+(creatures?1:0)+(corpses?1:0)+(food?1:0);}}}
 public static bool IsPearl(PhysicalObject item){return item is DataPearl||item!=null&&item.abstractPhysicalObject!=null&&item.abstractPhysicalObject.type!=null&&item.abstractPhysicalObject.type.value=="DataPearl";}
 public static Tags Classify(IEnumerable<PhysicalObject> held){var tags=new Tags();if(held!=null)foreach(var item in held){if(item==null)continue;if(IsWeapon(item))tags.weapons=true;else if(IsPearl(item))tags.pearls=true;else if(item is Creature){if(((Creature)item).dead)tags.corpses=true;else tags.creatures=true;}else if(item is IPlayerEdible&&((IPlayerEdible)item).Edible)tags.food=true;else tags.items=true;}return tags;}
 public static bool Matches(IEnumerable<PhysicalObject> held,string category){var tags=Classify(held);return category=="any"||category=="mixed"&&tags.weapons&&tags.pearls||category=="weapons"&&tags.weapons||category=="pearls"&&tags.pearls||category=="creatures"&&tags.creatures||category=="corpses"&&tags.corpses||category=="food"&&tags.food||category=="items"&&tags.items;}
 public static string Category(IEnumerable<PhysicalObject> held){var tags=Classify(held);return tags.weapons&&tags.pearls?"mixed":tags.weapons?"weapons":tags.pearls?"pearls":tags.corpses?"corpses":tags.creatures?"creatures":tags.food?"food":tags.items?"items":"";}
 public static bool HasLines(PearlVariant[] pool){return pool!=null&&Array.Exists(pool,g=>g!=null&&g.lines!=null&&Array.Exists(g.lines,CreatorDialogueLine.Runnable));}
 public static PearlVariant[] Select(IEnumerable<PhysicalObject> held,PearlVariant[] mixed,PearlVariant[] weapons,PearlVariant[] pearls,PearlVariant[] items){
  var tags=Classify(held);if(tags.weapons&&tags.pearls&&HasLines(mixed))return mixed;
  if(tags.weapons&&HasLines(weapons))return weapons;
  if(tags.pearls&&HasLines(pearls))return pearls;
  return (tags.items||tags.creatures||tags.corpses||tags.food)&&HasLines(items)?items:new PearlVariant[0];
 }
 public static PearlVariant[] Select(IEnumerable<PhysicalObject> held,PearlVariant[] mixed,PearlVariant[] weapons,PearlVariant[] pearls,PearlVariant[] items,PearlVariant[] creatures,PearlVariant[] corpses,PearlVariant[] food){
  string category=Category(held);var specific=category=="creatures"?creatures:category=="corpses"?corpses:category=="food"?food:null;
  return HasLines(specific)?specific:Select(held,mixed,weapons,pearls,items);
 }
}
public static class CreatorMiscPearls {
 public static bool IsOrdinary(DataPearl pearl){if(pearl==null||pearl is CreatorDataPearl||pearl is CreatorWorkPearl)return false;var type=pearl.AbstractPearl.dataPearlType;return type!=null&&(type.value=="Misc"||type.value=="Misc2");}
 sealed class TextLoader:Conversation {
  public TextLoader(RainWorldGame game,DataPearl pearl):base(null,Conversation.ID.None,null){LoadEventsFromFile(38,game.StoryCharacter,true,pearl.abstractPhysicalObject.ID.RandomSeed);}
 }
 public static CreatorDialogueLine[] Load(Oracle oracle,DataPearl pearl){
  try{var conversation=new TextLoader(oracle.room.game,pearl);var result=new List<CreatorDialogueLine>();foreach(var raw in conversation.events){var text=raw as Conversation.TextEvent;if(text==null)continue;if(String.IsNullOrWhiteSpace(text.text)||text.text.IndexOf("TEXT ERROR",StringComparison.OrdinalIgnoreCase)>=0)throw new FormatException("Native miscellaneous pearl text could not be loaded.");result.Add(new CreatorDialogueLine{text=text.text,hold=Math.Max(.1f,text.textLinger/40f),gap=Math.Max(0,text.initialWait/40f)});}if(result.Count==0)throw new FormatException("Native miscellaneous pearl file 38 contained no text.");return result.ToArray();}
  catch(Exception error){MiDiagnostics.Report("MI-MISC-PEARL-TEXT","CreatorMiscPearls.Load",error,MiDiagnostics.Context(oracle.room));return new CreatorDialogueLine[0];}
 }
}
}
