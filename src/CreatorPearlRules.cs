namespace MoreIterators {
using System;
using System.Collections.Generic;

public static class CreatorPearlPlacement {
 public static bool TryPosition(float x,float y,float width,float height,float radius,out float px,out float py){
  px=x*width;py=y*height;
  return !Single.IsNaN(px)&&!Single.IsInfinity(px)&&!Single.IsNaN(py)&&!Single.IsInfinity(py)&&!Single.IsNaN(radius)&&!Single.IsInfinity(radius)&&radius>0&&width>=radius*2&&height>=radius*2&&px>=radius&&px<=width-radius&&py>=radius&&py<=height-radius;
 }
}

// One profile belongs to an iterator, not to an individual pearl.
[Serializable] public sealed class CreatorPearlRules {
 public bool greetingEnabled=true,preventSameCycleRepeat=true,manyEnabled=true;
 public float greetingDelay=3,quickReturnWindow=30,returnCooldown=10;public int manyThreshold=3;
 public bool extractStomachPearl;
 public PearlVariant[] firstPreRead=new PearlVariant[0],greetingCreatures=new PearlVariant[0],greetingCorpses=new PearlVariant[0],greetingFood=new PearlVariant[0];
 public CreatorReadingPresentationOptions presentation=new CreatorReadingPresentationOptions();
 public PearlVariant[] quickReturn=new PearlVariant[0],revisit=new PearlVariant[0],greetingPearls=new PearlVariant[0],greetingMixed=new PearlVariant[0],extractedPreRead=new PearlVariant[0];
 public string leavePolicy="resume";
 public PearlVariant[] greetingItems=new PearlVariant[0],greetingWeapons=new PearlVariant[0],preRead=new PearlVariant[0],misc=new PearlVariant[0];
 public PearlVariant[] leaving={new PearlVariant{name="离开",lines=new[]{new CreatorDialogueLine{text="……你要离开了吗？"}}}};
 public PearlVariant[] returning={new PearlVariant{name="回来",lines=new[]{new CreatorDialogueLine{text="那么，接着刚才的内容。"}}}};
 public PearlVariant[] greeting={new PearlVariant{name="带来了什么",lines=new[]{new CreatorDialogueLine{text="小家伙，你这次给我带了什么东西？"}}}};
 public PearlVariant[] repeat={new PearlVariant{name="已经读过",lines=new[]{new CreatorDialogueLine{text="这颗珍珠，我记得。"}}}};
 public PearlVariant[] many={new PearlVariant{name="带来不少",lines=new[]{new CreatorDialogueLine{text="你这一趟带来了不少珍珠。"},new CreatorDialogueLine{text="让我看看这一颗。"}}}};
}

// Persist the last completed cycle per pearl; an interrupted read is not completed.
public sealed class CreatorPearlProgress {
 public readonly HashSet<string> completedMeetings=new HashSet<string>();public readonly Dictionary<string,int> lastObserved=new Dictionary<string,int>();
 public string activeMeeting="";public int meetingEntries;public bool storyComplete;public int lastGreetingCycle=Int32.MinValue;public readonly Dictionary<string,int> lastRead=new Dictionary<string,int>();
 public bool Seen(string uid){return lastRead.ContainsKey(uid);}
 public bool SameCycle(string uid,int cycle){int readCycle;return lastRead.TryGetValue(uid,out readCycle)&&readCycle==cycle;}
 public int Count(int cycle){int result=0;foreach(var value in lastRead.Values)if(value==cycle)result++;return result;}
 public bool ReadBody(string uid,int cycle,bool preventRepeat){return !preventRepeat||!SameCycle(uid,cycle);}
 public bool Many(string uid,int cycle,CreatorPearlRules rules){return rules.manyEnabled&&!SameCycle(uid,cycle)&&Count(cycle)+1>=rules.manyThreshold;}
 public void Complete(string uid,int cycle){lastRead[uid]=cycle;}
 public Dictionary<string,object> Data(){var observations=new Dictionary<string,object>();foreach(var pair in lastObserved)observations[pair.Key]=pair.Value;var reads=new Dictionary<string,object>();foreach(var pair in lastRead)reads[pair.Key]=pair.Value;return new Dictionary<string,object>{{"activeMeeting",activeMeeting},{"meetingEntries",meetingEntries},{"completedMeetings",new List<string>(completedMeetings)},{"lastObserved",observations},{"storyComplete",storyComplete},{"lastGreetingCycle",lastGreetingCycle},{"lastRead",reads}};}
 public static CreatorPearlProgress Load(Dictionary<string,object> data){var p=new CreatorPearlProgress();object raw;if(data!=null){if(data.TryGetValue("activeMeeting",out raw))p.activeMeeting=Convert.ToString(raw);if(data.TryGetValue("meetingEntries",out raw))p.meetingEntries=Math.Max(0,Convert.ToInt32(raw));if(data.TryGetValue("completedMeetings",out raw)){var values=raw as List<object>;if(values!=null)foreach(var value in values)p.completedMeetings.Add(Convert.ToString(value));}if(data.TryGetValue("lastObserved",out raw)){var values=raw as Dictionary<string,object>;if(values!=null)foreach(var pair in values)p.lastObserved[pair.Key]=Convert.ToInt32(pair.Value);}if(data.TryGetValue("storyComplete",out raw))p.storyComplete=Convert.ToBoolean(raw);if(data.TryGetValue("lastGreetingCycle",out raw))p.lastGreetingCycle=Convert.ToInt32(raw);if(data.TryGetValue("lastRead",out raw)){var reads=raw as Dictionary<string,object>;if(reads!=null)foreach(var pair in reads)p.lastRead[pair.Key]=Convert.ToInt32(pair.Value);}}return p;}
}
}
