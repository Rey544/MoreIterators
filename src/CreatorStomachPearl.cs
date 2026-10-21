using System;
namespace MoreIterators {
 public static class CreatorStomachPearl {
  public static DataPearl.AbstractDataPearl Candidate(Player player,Oracle oracle,IteratorDesign design){
   if(player==null||player.dead||player.room!=oracle.room||player.inShortcut||player.enteringShortCut.HasValue)return null;
   // Native Spearmaster regurgitation replaces stomach contents with its story pearl.
   if(player.SlugCatClass!=null&&player.SlugCatClass.value=="Spear")return null;
   var pearl=player.objectInStomach as DataPearl.AbstractDataPearl;
   if(pearl==null||pearl.dataPearlType==null)return null;
   string type=pearl.dataPearlType.value;
   if(type=="Misc"||type=="Misc2")return pearl;
   var project=CreatorPearlCatalog.Find(type);var profile=project==null?null:project.Reader(design.projectId);
   if(profile==null)return null;
   var rules=CreatorDialogueProfile.For(design).affinity;
   var body=profile.Select(rules.enabled?CreatorAffinity.Get(oracle,design).Tier:null);
   return body!=null&&body.read!=null&&Array.Exists(body.read,CreatorDialogueLine.Runnable)?pearl:null;
  }
  public static DataPearl Extract(Player player,Oracle oracle,DataPearl.AbstractDataPearl expected){
   if(expected==null||player.objectInStomach!=expected||player.room!=oracle.room)return null;
   try {
    player.Regurgitate();
    player.Blink(35);
    var pearl=expected.realizedObject as DataPearl;
    if(player.objectInStomach==expected||pearl==null||pearl.room!=oracle.room||pearl.slatedForDeletetion){
     MiDiagnostics.Warn("MI-PEARL-EXTRACT","CreatorStomachPearl.Extract","Native regurgitation did not release the requested pearl; this request will not retry.",MiDiagnostics.Context(oracle.room));return null;
    }
    for(int i=pearl.grabbedBy.Count-1;i>=0;i--)pearl.grabbedBy[i].Release();
    MiDiagnostics.Info("pearl.extract","oracle="+IteratorDesign.ForRoom(oracle.room).oracleId+" pearl="+expected.ID);
    return pearl;
   } catch(Exception error) {
    MiDiagnostics.Report("MI-PEARL-EXTRACT","CreatorStomachPearl.Extract",error,MiDiagnostics.Context(oracle.room));
    throw;
   }
  }
 }
}
