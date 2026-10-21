using System;
namespace MoreIterators {
 // Presence is sampled before reception's speech gate; only real room transitions create entries.
 public sealed class CreatorPearlVisits {
  bool present,pending,departed;int leftAt,arrivalAt,lastReturnAt=Int32.MinValue;
  float awaySeconds;
  public void Observe(bool inRoom,int clock){
   if(inRoom==present)return;
   present=inRoom;
   if(inRoom){pending=true;arrivalAt=clock;awaySeconds=departed?Math.Max(0,clock-leftAt)/40f:Single.PositiveInfinity;}
   else {pending=false;departed=true;leftAt=clock;}
  }
  public string Enter(int cycle,int lastGreetingCycle,CreatorPearlRules rules){
   if(!pending)return null;pending=false;
   if(lastGreetingCycle!=cycle)return "greeting";
   if(lastReturnAt!=Int32.MinValue&&arrivalAt-lastReturnAt<Math.Max(0,rules.returnCooldown)*40)return null;
   return departed&&awaySeconds<=Math.Max(0,rules.quickReturnWindow)?"quickReturn":"revisit";
  }
  public void DiscardEntry(){pending=false;}
  public void Greeted(string kind,int clock){if(kind!="greeting")lastReturnAt=clock;}
 }
}
