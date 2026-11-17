using System;
using System.Collections.Generic;
using MoreIterators;
using UnityEngine;

class EncounterFlowCheck {
 static int checks;
 static void Check(bool value,string name){if(!value)throw new Exception(name);checks++;}
 static CreatorDialogueLine Line(string text,float gap=0){return new CreatorDialogueLine{text=text,hold=.1f,gap=gap};}
 static PearlVariant Group(string text){return new PearlVariant{lines=new[]{Line(text)}};}
 static Oracle NewOracle(string id=null){var game=new RainWorldGame();var room=new Room{game=game,design=new IteratorDesign{oracleId=id??Guid.NewGuid().ToString(),dialogueJson="{\"nonce\":\""+Guid.NewGuid().ToString()+"\",\"enabled\":true,\"first\":[],\"pearlReading\":{\"greetingEnabled\":false,\"manyEnabled\":false}}"}};var oracle=new Oracle{room=room};room.updateList.Add(oracle);return oracle;}
 static Player PlayerFor(Oracle o){var player=new Player{room=o.room};player.firstChunk.pos=new Vector2(300,300);o.room.game.Players.Add(new AbstractCreature{realizedCreature=player});return player;}
 static List<string> Said(Oracle o){return o.room.game.cameras[0].hud.dialogBox.said;}
 static CreatorDialogueProfile Profile(Oracle o){return CreatorDialogueProfile.For(o.room.design);}
 static void SetGreeting(Oracle o){var rules=Profile(o).pearlReading;rules.greetingEnabled=true;rules.greetingDelay=0;rules.greeting=new[]{Group("second encounter")};rules.quickReturn=new[]{Group("quick return")};rules.revisit=new[]{Group("long return")};rules.misc=new[]{Group("pearl body")};}
 static void Frame(Oracle o,Player player,CreatorDialogue dialogue,CreatorPearlReader reader,bool finishHud=true){
  o.room.game.clock++;
  if(finishHud)o.room.game.cameras[0].hud.dialogBox.ShowingAMessage=false;
  var actions=CreatorDialogueActions.For(o);actions.Update();
  var listener=player!=null&&!player.dead&&player.room==o.room?player:null;
  dialogue.ObservePresence(listener);reader.ObservePresence(listener);
  if(!actions.Active&&!reader.Active)dialogue.Update(listener,new List<CreatorWorkPearl>(),o.room.design);
  if(!actions.Active)reader.Update(listener,o.room.design,!dialogue.Speaking,dialogue.InitialStoryComplete);
 }
 static void Drain(Oracle o,Player player,CreatorDialogue dialogue,CreatorPearlReader reader,int frames=100){for(int i=0;i<frames;i++)Frame(o,player,dialogue,reader);}
 static void Offer(Oracle o,Player player,DataPearl pearl){
  o.firstChunk.pos=player.mainBodyChunk.pos+new Vector2(200,0);pearl.room=o.room;pearl.firstChunk.pos=player.mainBodyChunk.pos;
  var grasp=new Grasp{grabber=player,grabbed=pearl};pearl.grabbedBy.Add(grasp);player.grasps=new[]{grasp};
  On.Player.Invoke(delegate(Player p,int index,bool eu){pearl.grabbedBy.Clear();p.grasps=new Grasp[0];pearl.firstChunk.vel=new Vector2(10,0);},player,0,false);
 }
 static void DeathAfterFinalLine(bool preview,int kind){
  MoreIteratorsPlugin.Active=preview;var o=NewOracle();var player=PlayerFor(o);SetGreeting(o);var profile=Profile(o);
  var final=Line("first final",.6f);if(kind!=1)final.action=new CreatorGroupAction{type="killPlayer"};profile.first=new List<CreatorDialogueLine>{final};if(kind!=0)profile.firstAction=new CreatorGroupAction{type="killPlayer",delay=1.8f};
  var dialogue=new CreatorDialogue(o);var reader=new CreatorPearlReader(o);
  Frame(o,player,dialogue,reader);Check(!dialogue.InitialStoryComplete&&Said(o).Count==1,"first line starts without completing");
  Frame(o,player,dialogue,reader);Check(dialogue.InitialStoryComplete&&CreatorPearlReader.CompletedStory(o,o.room.design.oracleId),"final line commits before its post-line gap and action");
  Check(!Said(o).Contains("second encounter"),"finishing initial story does not append a greeting");
  Drain(o,player,dialogue,reader,180);Check(player.dead&&player.deaths==1,"authored first completion action kills exactly once");
  Check(o.room.game.GetStorySession.saveState.deathPersistentSaveData.unrecognizedSaveStrings.FindAll(x=>x.EndsWith(":COMPLETE")).Count==(preview?0:1),"only campaign completion receives death-persistent token");
  player.dead=false;Drain(o,player,dialogue,reader);Check(Said(o).Contains("second encounter")&&!Said(o).Contains("quick return"),"same-cycle return after final-line death uses second encounter");
  int count=Said(o).Count;Drain(o,player,dialogue,reader,200);Check(Said(o).Count==count,"idle updates never repeat an encounter");
  Offer(o,player,new DataPearl());Drain(o,player,dialogue,reader,150);Check(Said(o).Contains("pearl body"),"completed first story naturally accepts an offered pearl");
  var retry=NewOracle(o.room.design.oracleId);var visitor=PlayerFor(retry);Profile(retry).first=new List<CreatorDialogueLine>{Line("must not replay first")};SetGreeting(retry);
   
  retry.room.game.GetStorySession.saveState.deathPersistentSaveData.unrecognizedSaveStrings=new List<string>(o.room.game.GetStorySession.saveState.deathPersistentSaveData.unrecognizedSaveStrings);
  var resumed=new CreatorDialogue(retry);Drain(retry,visitor,resumed,new CreatorPearlReader(retry));
  Check(resumed.InitialStoryComplete&&Said(retry).Contains("second encounter")&&!Said(retry).Contains("must not replay first"),"new room/game retry restores completed-first fact without cycle world state");
  if(!preview){var separate=NewOracle(o.room.design.oracleId);var fresh=new CreatorDialogue(separate);Check(!fresh.InitialStoryComplete,"another campaign without completion token cannot inherit global session");}
  CreatorDialogue.Reset(o.room.design.oracleId);CreatorPearlReader.Reset(retry.room.game,o.room.design.oracleId);
  var reset=new CreatorDialogue(retry);Check(!reset.InitialStoryComplete,"explicit replay/reset clears preview and native completion");
  MoreIteratorsPlugin.Active=false;
 }
 static void InterruptedFirst(){
  var o=NewOracle();var player=PlayerFor(o);SetGreeting(o);Profile(o).first=new List<CreatorDialogueLine>{Line("unfinished first")};var dialogue=new CreatorDialogue(o);var reader=new CreatorPearlReader(o);
  Frame(o,player,dialogue,reader);player.dead=true;Frame(o,player,dialogue,reader);Drain(o,player,dialogue,reader,80);
  Check(!dialogue.InitialStoryComplete&&!CreatorPearlReader.CompletedStory(o,o.room.design.oracleId)&&o.room.game.GetStorySession.saveState.deathPersistentSaveData.unrecognizedSaveStrings.FindAll(x=>x.EndsWith(":COMPLETE")).Count==0,"death clearing a visible unfinished line does not complete first story");
  player.dead=false;Frame(o,player,dialogue,reader);Check(Said(o).Count==2&&Said(o)[1]=="unfinished first","surviving room resumes the interrupted line once");
  Drain(o,player,dialogue,reader);Check(dialogue.InitialStoryComplete&&!Said(o).Contains("second encounter"),"resumed final line completes without a same-visit greeting");
  o=NewOracle();player=PlayerFor(o);var first=Line("early lethal line");first.action=new CreatorGroupAction{type="killPlayer"};Profile(o).first=new List<CreatorDialogueLine>{first,Line("not reached")};dialogue=new CreatorDialogue(o);reader=new CreatorPearlReader(o);Drain(o,player,dialogue,reader,100);
  Check(player.dead&&!dialogue.InitialStoryComplete&&!CreatorPearlReader.CompletedStory(o,o.room.design.oracleId)&&!Said(o).Contains("not reached"),"death from an earlier line never completes remaining first dialogue");
  var retry=NewOracle(o.room.design.oracleId);Profile(retry).first=new List<CreatorDialogueLine>{Line("first after retry")};var resumed=new CreatorDialogue(retry);Frame(retry,PlayerFor(retry),resumed,new CreatorPearlReader(retry));Check(!resumed.InitialStoryComplete&&Said(retry).Contains("first after retry"),"unfinished first sequence restarts after room/game reconstruction");
 }
 static void AliveReturnAndReset(){
  var o=NewOracle();var player=PlayerFor(o);SetGreeting(o);Profile(o).first=new List<CreatorDialogueLine>{Line("initial")};var dialogue=new CreatorDialogue(o);var reader=new CreatorPearlReader(o);Drain(o,player,dialogue,reader);
  Check(dialogue.InitialStoryComplete&&Said(o).Count==1,"completed alive first story stays quiet on its original visit");
  player.room=new Room();Frame(o,player,dialogue,reader);player.room=o.room;Drain(o,player,dialogue,reader);Check(Said(o).Contains("second encounter"),"alive same-cycle second arrival uses authored greeting");
  player.room=new Room();Frame(o,player,dialogue,reader);player.room=o.room;Drain(o,player,dialogue,reader);Check(Said(o).Contains("quick return"),"subsequent quick return follows dedicated return pool");
  CreatorEncounter.Restart++;Frame(o,player,dialogue,reader);Check(!dialogue.InitialStoryComplete,"explicit replay restarts actual first line");Frame(o,player,dialogue,reader);Check(dialogue.InitialStoryComplete&&CreatorPearlReader.CompletedStory(o,o.room.design.oracleId),"reader cannot reset again after the replayed final line commits");
 }
 static void MarkPrelude(){
  var o=NewOracle();var player=PlayerFor(o);MoreIteratorsPlugin.Active=true;CreatorRuntime.Mark=false;o.room.game.GetStorySession.saveState.deathPersistentSaveData.theMark=false;SetGreeting(o);
  var prelude=Line("untranslated prelude");prelude.action=new CreatorGroupAction{type="liftAndGiveMark",duration=.25f};Profile(o).first=new List<CreatorDialogueLine>{prelude,Line("after mark")};var dialogue=new CreatorDialogue(o);var reader=new CreatorPearlReader(o);
  Frame(o,player,dialogue,reader);Check(Said(o).Count==0&&!CreatorDialogueActions.For(o).Active,"unmarked first prelude advances silently before explicit grant");Drain(o,player,dialogue,reader,250);
  Check(CreatorRuntime.Mark&&Said(o).Contains("after mark")&&!Said(o).Contains("untranslated prelude")&&!Said(o).Contains("second encounter"),"explicit first-story grant enables later text without same-visit greeting");
  MoreIteratorsPlugin.Active=false;CreatorRuntime.Mark=true;
 }
 static void InterruptedMarkGrant(){
  foreach(bool group in new[]{false,true}){
   MoreIteratorsPlugin.Active=true;CreatorRuntime.Mark=false;var o=NewOracle();o.room.game.GetStorySession.saveState.deathPersistentSaveData.theMark=false;var player=PlayerFor(o);var profile=Profile(o);var line=Line("hidden grant");var grant=new CreatorGroupAction{type="liftAndGiveMark",duration=1};
   profile.first=new List<CreatorDialogueLine>{line};if(group)profile.firstAction=grant;else {line.action=grant;profile.first.Add(Line("after interrupted grant"));}
   var dialogue=new CreatorDialogue(o);var reader=new CreatorPearlReader(o);var actions=CreatorDialogueActions.For(o);
   for(int i=0;i<200&&!actions.Active;i++)Frame(o,player,dialogue,reader);
   Check(actions.Active&&!dialogue.InitialStoryComplete,"unmarked final/middle grant stays incomplete while action runs");
   player.room=new Room();Frame(o,player,dialogue,reader);Check(!actions.Active&&!dialogue.InitialStoryComplete&&!CreatorPearlReader.CompletedStory(o,o.room.design.oracleId),"cancelled unmarked grant is not persisted as finished first story");
   player.room=o.room;Drain(o,player,dialogue,reader,300);Check(CreatorRuntime.Mark&&dialogue.InitialStoryComplete,"return replays cancelled line/group grant and can actually obtain mark");
   MoreIteratorsPlugin.Active=false;CreatorRuntime.Mark=true;
  }
 }

 static void Reenter(Oracle o,Player player,CreatorDialogue dialogue,CreatorPearlReader reader){player.room=new Room();Frame(o,player,dialogue,reader);player.room=o.room;}
 static void MeetingSequence(){
  var o=NewOracle();var player=PlayerFor(o);var p=Profile(o);p.first=new List<CreatorDialogueLine>{Line("chapter one")};p.repeat=new List<CreatorDialogueLine>{Line("chapter two")};p.meetings=new[]{new CreatorMeeting{id="33333333333333333333333333333333",lines=new[]{Line("chapter three")}}};p.loop=new List<CreatorDialogueLine>{Line("loop")};
  var d=new CreatorDialogue(o);var r=new CreatorPearlReader(o);Drain(o,player,d,r);Check(String.Join(",",Said(o))=="chapter one","one fixed chapter per arrival");
  Reenter(o,player,d,r);Frame(o,player,d,r);Check(Said(o)[1]=="chapter two","second story starts on a real return");player.dead=true;Frame(o,player,d,r);Check(!CreatorPearlReader.CompletedMeeting(o,o.room.design.oracleId,"repeat"),"incomplete second story death does not skip chapter");player.dead=false;Drain(o,player,d,r);Check(CreatorPearlReader.CompletedMeeting(o,o.room.design.oracleId,"repeat"),"resumed second story commits only when complete");
  Reenter(o,player,d,r);Drain(o,player,d,r);Check(Said(o)[Said(o).Count-1]=="chapter three","third story follows completed second");Check(CreatorPearlReader.CompletedMeeting(o,o.room.design.oracleId,p.meetings[0].id),"third story uses stable completion id");
  int count=Said(o).Count;Drain(o,player,d,r);Check(Said(o).Count==count,"idle does not advance meeting sequence");Reenter(o,player,d,r);Drain(o,player,d,r);Check(Said(o)[Said(o).Count-1]=="loop","explicit loop after all fixed chapters");
  var retry=NewOracle(o.room.design.oracleId);retry.room.game.GetStorySession.saveState.deathPersistentSaveData.unrecognizedSaveStrings=new List<string>(o.room.game.GetStorySession.saveState.deathPersistentSaveData.unrecognizedSaveStrings);var rp=Profile(retry);rp.repeat=p.repeat;rp.meetings=p.meetings;rp.loop=p.loop;var rd=new CreatorDialogue(retry);Drain(retry,PlayerFor(retry),rd,new CreatorPearlReader(retry));Check(String.Join(",",Said(retry))=="loop","death reload restores completed fixed chapter ids");
  o=NewOracle();player=PlayerFor(o);p=Profile(o);p.storyMode="firstThenLoop";p.first=new List<CreatorDialogueLine>{Line("first only")};p.repeat=new List<CreatorDialogueLine>{Line("retained second")};p.meetings=new[]{new CreatorMeeting{id="44444444444444444444444444444444",lines=new[]{Line("retained third")}}};p.loop=new List<CreatorDialogueLine>{Line("chosen loop")};d=new CreatorDialogue(o);r=new CreatorPearlReader(o);Drain(o,player,d,r);Reenter(o,player,d,r);Drain(o,player,d,r);Check(String.Join(",",Said(o))=="first only,chosen loop","first then loop keeps fixed chapter data without playing it");
  o=NewOracle();player=PlayerFor(o);p=Profile(o);p.first=new List<CreatorDialogueLine>{Line("fixed")};SetGreeting(o);d=new CreatorDialogue(o);r=new CreatorPearlReader(o);Drain(o,player,d,r);Reenter(o,player,d,r);Drain(o,player,d,r);Check(Said(o).Contains("second encounter"),"no explicit loop resumes ordinary per-cycle reception");
  int beforeEntries=CreatorPearlReader.MeetingEntries(o,o.room.design.oracleId);o.room.design.dialogueJson+=" ";Profile(o).meetings=new[]{new CreatorMeeting{id="66666666666666666666666666666666",lines=new[]{Line("newly appended chapter")}}};Drain(o,player,d,r);Check(!Said(o).Contains("newly appended chapter")&&CreatorPearlReader.MeetingEntries(o,o.room.design.oracleId)==beforeEntries,"hot edit does not fake a room entry or start an appended chapter during this visit");Reenter(o,player,d,r);Drain(o,player,d,r);Check(Said(o).Contains("newly appended chapter"),"new chapter after finished sequence starts on next eligible real entry");
 }
 static void ItemCategoriesAndDailyReading(){
  Check(CreatorHeldItems.Category(new PhysicalObject[]{new Creature()})=="creatures","living creature category");Check(CreatorHeldItems.Category(new PhysicalObject[]{new Creature{dead=true}})=="corpses","corpse category");Check(CreatorHeldItems.Category(new PhysicalObject[]{new EdibleItem()})=="food","food category");
  var fallback=new[]{Group("generic")};Check(CreatorHeldItems.Select(new PhysicalObject[]{new Creature()},null,null,null,fallback,null,null,null)==fallback,"new categories retain generic item fallback");
  var o=NewOracle();var player=PlayerFor(o);var p=Profile(o);p.pearlReading.misc=new[]{Group("body")};p.pearlReading.firstPreRead=new[]{Group("long first")};p.pearlReading.preRead=new[]{Group("short later")};var d=new CreatorDialogue(o);var r=new CreatorPearlReader(o);Drain(o,player,d,r);
  Offer(o,player,new DataPearl());Drain(o,player,d,r,180);Check(Said(o).Contains("long first")&&!Said(o).Contains("short later"),"first completed pearl read uses first-cycle prelude");Offer(o,player,new DataPearl());Drain(o,player,d,r,180);Check(Said(o).Contains("short later"),"later pearl uses regular shorter prelude");
  int before=Said(o).FindAll(x=>x=="long first").Count;o.room.game.GetStorySession.saveState.cycleNumber++;Offer(o,player,new DataPearl());Drain(o,player,d,r,180);Check(Said(o).FindAll(x=>x=="long first").Count==before+1,"new rain cycle restores first pearl prelude");
  o=NewOracle();player=PlayerFor(o);p=Profile(o);o.firstChunk.pos=player.mainBodyChunk.pos;p.observation.cooldown=0;p.observation.food=new[]{Group("first food")};p.observation.repeatFood=new[]{Group("later food")};d=new CreatorDialogue(o);r=new CreatorPearlReader(o);Drain(o,player,d,r);player.grasps=new[]{new Grasp{grabber=player,grabbed=new EdibleItem{room=o.room}}};Drain(o,player,d,r);Check(Said(o).Contains("first food"),"first visible food observation");player.grasps=new[]{new Grasp{grabber=player,grabbed=new EdibleItem{room=o.room}}};Drain(o,player,d,r);Check(Said(o).Contains("later food"),"later newly held food uses later pool");
 }

 static void MeetingConditions(){
  var o=NewOracle();var player=PlayerFor(o);var p=Profile(o);p.first=new List<CreatorDialogueLine>{Line("intro")};p.repeat=new List<CreatorDialogueLine>{Line("conditional second")};p.repeatCondition=new CreatorMeetingCondition{minEntries=3,minCycle=2,held="pearls"};p.meetings=new[]{new CreatorMeeting{id="55555555555555555555555555555555",lines=new[]{Line("later chapter")}}};var d=new CreatorDialogue(o);var r=new CreatorPearlReader(o);Drain(o,player,d,r);Check(CreatorPearlReader.MeetingEntries(o,o.room.design.oracleId)==1,"idle frames do not increase real entry count");
  Reenter(o,player,d,r);Drain(o,player,d,r);Check(Said(o).Count==1,"unmet conditions neither play nor skip fixed chapter");o.room.game.GetStorySession.saveState.cycleNumber=2;player.grasps=new[]{new Grasp{grabber=player,grabbed=new DataPearl{room=o.room}},new Grasp{grabber=player,grabbed=new Spear{room=o.room}}};Reenter(o,player,d,r);Frame(o,player,d,r);Check(Said(o)[Said(o).Count-1]=="conditional second","all entry conditions start next chapter; pearl with spear still matches pearl condition");
  player.dead=true;Frame(o,player,d,r);Check(CreatorPearlReader.StartedMeeting(o,o.room.design.oracleId,"repeat")&&!CreatorPearlReader.CompletedMeeting(o,o.room.design.oracleId,"repeat"),"unfinished chapter persists its start without completion");
  var retry=NewOracle(o.room.design.oracleId);retry.room.game.GetStorySession.saveState.deathPersistentSaveData.unrecognizedSaveStrings=new List<string>(o.room.game.GetStorySession.saveState.deathPersistentSaveData.unrecognizedSaveStrings);Profile(retry).repeat=p.repeat;Profile(retry).repeatCondition=p.repeatCondition;Profile(retry).meetings=p.meetings;var visitor=PlayerFor(retry);var resumed=new CreatorDialogue(retry);Drain(retry,visitor,resumed,new CreatorPearlReader(retry));Check(Said(retry).Contains("conditional second")&&!Said(retry).Contains("later chapter"),"death reload replays started chapter even after carried item/cycle conditions change");Check(!CreatorPearlReader.StartedMeeting(retry,retry.room.design.oracleId,"repeat")&&CreatorPearlReader.CompletedMeeting(retry,retry.room.design.oracleId,"repeat"),"completed retry clears active lock");
 }
 static void DetachedReader(){
  var o=NewOracle();var player=PlayerFor(o);var room=o.room;var reader=new CreatorPearlReader(o);SetGreeting(o);var d=new CreatorDialogue(o);Drain(o,player,d,reader);
  reader.TryRespond(new[]{Group("unfinished response")},"test",player);Check(reader.Active,"reader is active before detaching");CreatorDialogueActions.For(o).Schedule(new CreatorGroupAction{type="killPlayer",delay=2},player,null);
  o.room=null;d.Suspend();CreatorDialogueActions.For(o).Cancel();for(int i=0;i<120;i++){reader.ObservePresence(player);Check(!reader.Update(player,room.design,true),"clipboard-detached reader stays inactive without dereferencing a room");}Check(!reader.Active&&!CreatorDialogueActions.For(o).Active&&!player.dead,"detaching cancels pending reading and actions without completion");
  o.room=room;var game=room.game;room.game=null;reader.ObservePresence(player);Check(!reader.Update(player,room.design,true),"reader waits for a live room game");room.game=game;
  Offer(o,player,new DataPearl());Drain(o,player,d,reader,180);Check(Said(o).Contains("pearl body"),"pasted reader can receive and finish a new pearl");
 }
 static void StaleReaderCleanup(){
  var o=NewOracle();var player=PlayerFor(o);var oldRoom=o.room;var oldDialogue=new CreatorDialogue(o);var oldReader=new CreatorPearlReader(o);oldReader.TryRespond(new[]{Group("old room response")},"test",player);
  o.room=new Room{game=oldRoom.game,design=new IteratorDesign{oracleId=Guid.NewGuid().ToString(),dialogueJson="{\"enabled\":true,\"first\":[],\"pearlReading\":{\"greetingEnabled\":false,\"manyEnabled\":false}}"}};o.room.updateList.Add(o);player.room=o.room;var newDialogue=new CreatorDialogue(o);var newReader=new CreatorPearlReader(o);Profile(o).pearlReading.misc=new[]{Group("new room pearl")};
  Offer(o,player,new DataPearl());newReader.Update(player,o.room.design,true);Check(newReader.Active&&Said(o).Contains("new room pearl")&&CreatorReadingPresentation.active.Contains(o),"new room reader displays its pearl before old cleanup");
  Offer(o,player,new DataPearl());Check(CreatorPearlOffers.Pending(o),"new room has a queued second offer");var actions=CreatorDialogueActions.For(o);actions.Schedule(new CreatorGroupAction{type="killPlayer",delay=2},player,null);int interrupted=o.room.game.cameras[0].hud.dialogBox.blankInterruptions;
  oldReader.Cancel(false,false);oldDialogue.Suspend(false,false);
  Check(newReader.Active&&actions.Active&&CreatorReadingPresentation.active.Contains(o)&&CreatorPearlOffers.Pending(o),"stale cleanup preserves current reading actions presentation and queue");Check(o.room.game.cameras[0].hud.dialogBox.ShowingAMessage&&o.room.game.cameras[0].hud.dialogBox.blankInterruptions==interrupted,"stale cleanup does not clear new room subtitles");
  actions.Cancel();newReader.Cancel();
 }
 public static int Main(){try{CreatorPearlOffers.Install(new List<Action>());foreach(bool preview in new[]{false,true})for(int kind=0;kind<3;kind++)DeathAfterFinalLine(preview,kind);InterruptedFirst();AliveReturnAndReset();MarkPrelude();InterruptedMarkGrant();MeetingSequence();MeetingConditions();ItemCategoriesAndDailyReading();DetachedReader();StaleReaderCleanup();Console.WriteLine(checks+" encounter flow assertions passed");return 0;}catch(Exception error){Console.Error.WriteLine(error);return 1;}}
}
