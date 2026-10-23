namespace MoreIterators {
using System;
using System.Collections.Generic;
using System.Runtime.CompilerServices;
using System.Text;

// Pure campaign policy. Reading/debugging this object never grants a bonus.
public sealed class CreatorAffinityState {
 public float value;public int cycle;public bool eligible=true;public readonly Dictionary<string,int> gifted=new Dictionary<string,int>();
 public CreatorAffinityState(float initial,int current){value=Clamp(initial);cycle=current;}
 public static float Clamp(float v){return Single.IsNaN(v)||Single.IsInfinity(v)?0:Math.Max(-1,Math.Min(1,v));}
 public string Tier{get{return TierOf(value);}}
 public static string TierOf(float v){return v<-.5f?"notSpeaking":v<0?"dislikes":v<.5f?"neutral":"likes";}
 public bool Advance(int current){if(current<=cycle)return false;if(eligible)value=Clamp(value+.15f);cycle=current;eligible=true;return true;}
 public string Hit(CreatorAffinityRules rules,bool spear){string tier=Tier;if(rules.attackMode=="gradual")value=Clamp(value-Math.Max(0,spear?rules.spearPenalty:rules.rockPenalty));else {value=-1;eligible=false;}return tier;}
 public bool Gift(string pearl,int current,CreatorAffinityRules rules){int previous;if(!rules.enabled||!rules.pearlGiftEnabled||Single.IsNaN(rules.pearlGiftAmount)||Single.IsInfinity(rules.pearlGiftAmount)||rules.pearlGiftAmount<0||rules.pearlGiftAmount>2||value<-.5f||value<rules.refuseBelow||String.IsNullOrEmpty(pearl)||gifted.TryGetValue(pearl,out previous)&&previous>=current)return false;gifted[pearl]=current;value=Clamp(value+Math.Max(0,rules.pearlGiftAmount));return true;}
 public Dictionary<string,object> Data(){var gifts=new Dictionary<string,object>();foreach(var pair in gifted)gifts[pair.Key]=pair.Value;return new Dictionary<string,object>{{"value",value},{"cycle",cycle},{"eligible",eligible},{"gifted",gifts}};}
 public static CreatorAffinityState Load(Dictionary<string,object> data,float initial,int current){var result=new CreatorAffinityState(initial,current);object raw;if(data==null)return result;if(data.TryGetValue("value",out raw))result.value=Clamp(Convert.ToSingle(raw));if(data.TryGetValue("cycle",out raw))result.cycle=Convert.ToInt32(raw);if(data.TryGetValue("eligible",out raw))result.eligible=Convert.ToBoolean(raw);if(data.TryGetValue("gifted",out raw)){var gifts=raw as Dictionary<string,object>;if(gifts!=null)foreach(var pair in gifts)result.gifted[pair.Key]=Convert.ToInt32(pair.Value);}return result;}
}
public static class CreatorAffinity {
 static readonly ConditionalWeakTable<RainWorldGame,Dictionary<string,CreatorAffinityState>> all=new ConditionalWeakTable<RainWorldGame,Dictionary<string,CreatorAffinityState>>();
 // Keep an unreadable record intact for recovery instead of replacing it with
 // defaults when the UI, cycle update, or a gameplay event asks for its state.
 static readonly ConditionalWeakTable<RainWorldGame,HashSet<string>> unreadable=new ConditionalWeakTable<RainWorldGame,HashSet<string>>();
 static string Key(string id){return "MORE_ITERATORS_AFFINITY_"+Convert.ToBase64String(Encoding.UTF8.GetBytes(RuntimePaths.ModId+":"+id))+":";}
 static int Cycle(Oracle o){return o.room.game.IsStorySession?o.room.game.GetStorySession.saveState.cycleNumber:0;}
 public static CreatorAffinityState Get(Oracle o,IteratorDesign design){
  var map=all.GetOrCreateValue(o.room.game);CreatorAffinityState state;if(map.TryGetValue(design.oracleId,out state))return state;
  var rules=CreatorDialogueProfile.For(design).affinity;state=new CreatorAffinityState(rules.initial,Cycle(o));
  if(o.room.game.IsStorySession&&!MoreIteratorsPlugin.Active){string key=Key(design.oracleId);foreach(string record in o.room.game.GetStorySession.saveState.miscWorldSaveData.unrecognizedSaveStrings)if(record.StartsWith(key,StringComparison.Ordinal)){try{var data=Json.Deserialize(Encoding.UTF8.GetString(Convert.FromBase64String(record.Substring(key.Length)))) as Dictionary<string,object>;if(data==null)throw new FormatException("Affinity state must be a JSON object.");state=CreatorAffinityState.Load(data,rules.initial,Cycle(o));}catch(Exception e){unreadable.GetOrCreateValue(o.room.game).Add(design.oracleId);MiDiagnostics.Report("MI-AFFINITY-READ","CreatorAffinity.Get",e,design.oracleId);}break;}}
  map[design.oracleId]=state;Save(o,design,state);return state;
 }
 static void Save(Oracle o,IteratorDesign d,CreatorAffinityState state){if(!o.room.game.IsStorySession||MoreIteratorsPlugin.Active||unreadable.GetOrCreateValue(o.room.game).Contains(d.oracleId))return;string key=Key(d.oracleId);var records=o.room.game.GetStorySession.saveState.miscWorldSaveData.unrecognizedSaveStrings;records.RemoveAll(x=>x.StartsWith(key,StringComparison.Ordinal));records.Add(key+Convert.ToBase64String(Encoding.UTF8.GetBytes(Json.Serialize(state.Data()))));}
 public static void Update(Oracle o,IteratorDesign d){var rules=CreatorDialogueProfile.For(d).affinity;if(!rules.enabled)return;var state=Get(o,d);if(state.Advance(Cycle(o)))Save(o,d,state);}
 public static string Hit(Oracle o,IteratorDesign d,bool spear){var state=Get(o,d);string tier=state.Hit(CreatorDialogueProfile.For(d).affinity,spear);Save(o,d,state);return tier;}
 public static bool Refuses(Oracle o,IteratorDesign d){var rules=CreatorDialogueProfile.For(d).affinity;return rules.enabled&&Get(o,d).value<rules.refuseBelow;}
 public static bool Gift(Oracle o,IteratorDesign d,string pearl){var rules=CreatorDialogueProfile.For(d).affinity;if(!rules.enabled||!rules.pearlGiftEnabled)return false;var state=Get(o,d);if(!state.Gift(pearl,Cycle(o),rules))return false;Save(o,d,state);MiDiagnostics.Info("affinity.gift","oracle="+d.oracleId+" pearl="+pearl+" value="+state.value.ToString("0.00",System.Globalization.CultureInfo.InvariantCulture));return true;}
 static Oracle Find(RainWorldGame game,string room){if(game==null)return null;foreach(var p in game.Players){var player=p.realizedCreature as Player;if(player==null||player.room==null||player.room.abstractRoom.name!=room)continue;foreach(var obj in player.room.updateList){var oracle=obj as Oracle;if(oracle!=null&&oracle.oracleBehavior is IteratorBehavior&&IteratorCatalog.IsAI(room))return oracle;}}return null;}
 public static bool CanAdjust(RainWorldGame game,string room){var o=Find(game,room);return o!=null&&CreatorDialogueProfile.For(IteratorDesign.ForRoom(o.room)).affinity.enabled;}
 public static bool Adjust(RainWorldGame game,string room,float delta){var o=Find(game,room);if(o==null||Single.IsNaN(delta)||Single.IsInfinity(delta))return false;var d=IteratorDesign.ForRoom(o.room);if(!CreatorDialogueProfile.For(d).affinity.enabled)return false;var state=Get(o,d);state.value=CreatorAffinityState.Clamp((float)Math.Round(state.value+delta,4));Save(o,d,state);MiDiagnostics.Info("affinity.adjust","oracle="+d.oracleId+" value="+state.value.ToString("0.00",System.Globalization.CultureInfo.InvariantCulture));return true;}
 public static string Label(RainWorldGame game,string room){var o=Find(game,room);if(o==null)return "";var d=IteratorDesign.ForRoom(o.room);if(!CreatorDialogueProfile.For(d).affinity.enabled)return UiText.Get("game.affinity.disabled");var state=Get(o,d);return UiText.Format("game.panel.affinity",state.value.ToString("0.00",System.Globalization.CultureInfo.InvariantCulture),UiText.Get("game.affinity."+state.Tier));}
}
}
