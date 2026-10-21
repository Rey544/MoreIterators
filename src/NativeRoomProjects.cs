using System;
using System.Collections.Generic;
using UnityEngine;

namespace MoreIterators {
 // Native rooms are editable only in the creator's temporary session.
 public static class NativeRoomProjects {
  public static bool IsNative(Dictionary<string,object> p){return p!=null&&!String.IsNullOrEmpty(IteratorCatalog.Text(p,"nativeOracle"));}
  public static bool Available(Dictionary<string,object> p){
   if(!IsNative(p))return true;
   var selected=IteratorCatalog.Find(MoreIteratorsPlugin.SelectedRoom);
   return MoreIteratorsPlugin.Active&&selected!=null&&IteratorCatalog.Text(selected,"projectId")==IteratorCatalog.Text(p,"projectId");
  }
  public static bool Editing(string room){var p=IteratorCatalog.Find(room);return IsNative(p)&&Available(p)&&IteratorCatalog.Text(p,"ai")==room;}
  public static SlugcatStats.Name Character(string room){
   var p=IteratorCatalog.Find(room);
   return p!=null&&IteratorCatalog.Text(p,"timeline")=="Spear"?MoreSlugcats.MoreSlugcatsEnums.SlugcatStatsName.Spear:SlugcatStats.Name.White;
  }
  public static void Attach(Oracle oracle){
   if(!Editing(oracle.room.abstractRoom.name)||oracle.oracleBehavior is IteratorBehavior)return;
   // Keep DM's native oracle identity, arm, body and room. Replace only this
   // temporary preview's story controller, so F8/editor modes share one owner.
   oracle.oracleBehavior=new IteratorBehavior(oracle);
   oracle.room.AddObject(new CreatorEncounter(oracle));
   Debug.Log("[More Iterators] Native preview attached: "+oracle.ID+" in "+oracle.room.abstractRoom.name);
  }
 }
}
