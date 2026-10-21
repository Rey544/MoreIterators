namespace MoreIterators {
using UnityEngine;
using System.Collections.Generic;
// Ordinary pickable work pearls; no BP identity or quest state.
public sealed class CreatorWorkPearl:DataPearl {
 sealed class Record {public World world;public string home;public int index;public AbstractPhysicalObject pearl;}
 static readonly Dictionary<string,Record> records=new Dictionary<string,Record>();
 public readonly int index;public readonly string home;Vector2 target,smoothed;int drive;bool tracked;
 public Vector2 pos{get{return firstChunk.pos;}}
 CreatorWorkPearl(AbstractPhysicalObject a,World w,int i,string homeRoom):base(a,w){index=i;home=homeRoom;}
 public static bool Realize(AbstractPhysicalObject a){Record r;if(!records.TryGetValue(a.ID.ToString(),out r)||r.world!=a.world)return false;a.realizedObject=new CreatorWorkPearl(a,a.world,r.index,r.home);return true;}
 public static CreatorWorkPearl Create(Room room,Vector2 p,int index){
  foreach(var r in records.Values)if(r.world==room.world&&r.home==room.abstractRoom.name&&r.index==index&&r.pearl!=null){
   var existing=r.pearl.realizedObject as CreatorWorkPearl;
   if(existing!=null&&!existing.slatedForDeletetion)return existing;
  }
  foreach(var a in room.abstractRoom.entities){Record r;if(records.TryGetValue(a.ID.ToString(),out r)&&r.world==room.world&&r.home==room.abstractRoom.name&&r.index==index){var obj=a as AbstractPhysicalObject;if(obj!=null){if(obj.realizedObject==null)obj.RealizeInRoom();var existing=obj.realizedObject as CreatorWorkPearl;if(existing!=null)return existing;}}}
  var ap=new DataPearl.AbstractDataPearl(room.world,AbstractPhysicalObject.AbstractObjectType.DataPearl,null,room.GetWorldCoordinate(p),room.game.GetNewID(),-1,-1,null,DataPearl.AbstractDataPearl.DataPearlType.Misc);
  records[ap.ID.ToString()]=new Record{world=room.world,home=room.abstractRoom.name,index=index,pearl=ap};room.abstractRoom.AddEntity(ap);
  var pearl=new CreatorWorkPearl(ap,room.world,index,room.abstractRoom.name);room.AddObject(pearl);pearl.firstChunk.HardSetPosition(p);return pearl;
 }
 public bool CanDrive{get{return !slatedForDeletetion&&room!=null&&room.abstractRoom.name==home&&grabbedBy.Count==0;}}
 public void DriveTo(Vector2 p){if(!CanDrive){StopDriving();return;}target=p;drive=3;}
 public void StopDriving(){drive=0;tracked=false;gravity=.9f;}
 public override void Update(bool eu){
  if(!CanDrive)StopDriving();
  if(slatedForDeletetion||room==null)return;
  if(CreatorRuntime.Paused&&CanDrive)return;bool driven=drive>0;
  if(driven){if(!tracked)smoothed=pos;smoothed=Vector2.MoveTowards(smoothed,target,2.4f);firstChunk.vel=Vector2.ClampMagnitude(Vector2.Lerp(firstChunk.vel,Vector2.ClampMagnitude((smoothed-pos)*.09f,3.5f),.14f),3.5f);gravity=0;}else gravity=.9f;
  tracked=driven;if(drive>0)drive--;base.Update(eu);glimmer=lastGlimmer=0;
 }
 public void Paint(RoomCamera.SpriteLeaser s){if(s.sprites.Length<3)return;Color c=IteratorDesign.ForId(CreatorRuntime.Id(home)).PearlColor(index);if(c==Color.black)c.g=1f/255;
  s.sprites[0].color=c;s.sprites[0].alpha=1;s.sprites[1].color=Color.Lerp(c,Color.white,.4f);s.sprites[2].isVisible=false;s.sprites[0].isVisible=s.sprites[1].isVisible=CreatorRuntime.Pearls;
 }
}
}
