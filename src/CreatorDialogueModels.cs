namespace MoreIterators {
using System;
using System.Collections.Generic;

[Serializable] public sealed class CreatorGroupAction {
 public string type="none";public float delay,duration=3;public int exitNode;
 public float offsetX,offsetY=70,radius=14,endAngle=360;
 public CreatorGroupAction[] actions=new CreatorGroupAction[0];
 static bool Atomic(CreatorGroupAction action){return action!=null&&(action.type=="killPlayer"||action.type=="liftSpinPlayer"||action.type=="liftAndGiveMark"||action.type=="giveMark"||action.type=="movePlayerToExit");}
 public static bool Usable(CreatorGroupAction action){
  if(Atomic(action))return true;
  return action!=null&&action.type=="sequence"&&action.actions!=null&&action.actions.Length>0&&action.actions.Length<=16&&Array.TrueForAll(action.actions,Atomic);
 }
 public static bool Contains(CreatorGroupAction action,string type){
  if(!Usable(action))return false;
  return action.type==type||action.type=="sequence"&&Array.Exists(action.actions,child=>child.type==type);
 }
 public static bool GrantsMark(CreatorGroupAction action){return Contains(action,"giveMark")||Contains(action,"liftAndGiveMark");}
 public static CreatorGroupAction[] Flatten(CreatorGroupAction action){if(!Usable(action))return new CreatorGroupAction[0];return action.type=="sequence"?action.actions:new[]{action};}
}
public sealed class CreatorDialogueGroup:List<CreatorDialogueLine> {
 public CreatorGroupAction action=new CreatorGroupAction();
 public CreatorDialogueGroup(IEnumerable<CreatorDialogueLine> lines):base(lines){}
}
[Serializable] public sealed class CreatorAffinityTiers {
 public PearlVariant[] notSpeaking=new PearlVariant[0],dislikes=new PearlVariant[0],neutral=new PearlVariant[0],likes=new PearlVariant[0];
 public PearlVariant[] For(string tier){return tier=="notSpeaking"?notSpeaking:tier=="dislikes"?dislikes:tier=="likes"?likes:neutral;}
}
[Serializable] public sealed class CreatorAffinityRules {
 public bool enabled=true,pearlGiftEnabled;public float initial=.3f,rockPenalty=.2f,spearPenalty=.5f,refuseBelow=-.5f,pearlGiftAmount=.1f;public string attackMode="vanilla";
 public CreatorAffinityTiers attackRock=new CreatorAffinityTiers(),attackSpear=new CreatorAffinityTiers();public PearlVariant[] refusal=new PearlVariant[0];
}
[Serializable] public sealed class CreatorMeetingCondition {public int minEntries,minCycle;public string held="any";}
[Serializable] public sealed class CreatorMeeting {public CreatorMeetingCondition condition=new CreatorMeetingCondition();public string id="",name="";public CreatorDialogueLine[] lines=new CreatorDialogueLine[0];public CreatorGroupAction action=new CreatorGroupAction();}
[Serializable] public sealed class CreatorObservationRules {
 public bool enabled=true;public float cooldown=4;
 public PearlVariant[] items=new PearlVariant[0],weapons=new PearlVariant[0],pearls=new PearlVariant[0],mixed=new PearlVariant[0],creatures=new PearlVariant[0],corpses=new PearlVariant[0],food=new PearlVariant[0];
 public PearlVariant[] repeatItems=new PearlVariant[0],repeatWeapons=new PearlVariant[0],repeatPearls=new PearlVariant[0],repeatMixed=new PearlVariant[0],repeatCreatures=new PearlVariant[0],repeatCorpses=new PearlVariant[0],repeatFood=new PearlVariant[0];
 public PearlVariant[] For(string category,bool repeat){
  PearlVariant[] initial=category=="weapons"?weapons:category=="pearls"?pearls:category=="mixed"?mixed:category=="creatures"?creatures:category=="corpses"?corpses:category=="food"?food:items;
  PearlVariant[] later=category=="weapons"?repeatWeapons:category=="pearls"?repeatPearls:category=="mixed"?repeatMixed:category=="creatures"?repeatCreatures:category=="corpses"?repeatCorpses:category=="food"?repeatFood:repeatItems;
  return repeat&&later!=null&&Array.Exists(later,g=>g!=null&&g.lines!=null&&Array.Exists(g.lines,CreatorDialogueLine.Runnable))?later:initial;
 }
}
}
