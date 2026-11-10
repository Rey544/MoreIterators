using System;
using System.Collections.Generic;
namespace UnityEngine {}
public class AbstractRoom {public string name="XX_AI";}
public class Room {public float gravity=1;public AbstractRoom abstractRoom=new AbstractRoom();public List<object> updateList=new List<object>();public RoomSettings roomSettings=new RoomSettings();public MoreIterators.IteratorDesign design=new MoreIterators.IteratorDesign();}
public class AntiGravity {public bool active=true;}
public class RoomSettings {public int Palette=7;public Fade fadePalette;public class Fade {public int palette=8;public float[] fades={.2f,.8f};}}
public class RoomCamera {public Room room;public int paletteA,paletteB,currentCameraPosition;public float paletteBlend;public int changes;public void ChangeMainPalette(int a){paletteA=a;changes++;}public void ChangeBothPalettes(int a,int b,float blend){paletteA=a;paletteB=b;paletteBlend=blend;changes++;}}
namespace MoreIterators {
 public class IteratorDesign {public string roomPaletteMode="mi",roomGravityMode="mi",entryGravityMode="zero";public static int Revision;public static IteratorDesign ForRoom(Room room){return room.design;}}
 public static class IteratorCatalog {public static bool IsAI(string name){return name.EndsWith("_AI");}}
}
public static class RoomControlsCheck {
 static void Check(bool test,string why){if(!test)throw new Exception(why);}
 public static void Main(){
  var room=new Room();var native=new AntiGravity();room.updateList.Add(native);
  MoreIterators.CreatorRoomSettings.CaptureGravity(room);room.gravity=0;native.active=false;
  MoreIterators.CreatorRoomSettings.PrepareGravity(room,false);Check(room.gravity==0&&!native.active,"legacy constructor behavior changed");
  room.design.roomGravityMode="room";MoreIterators.CreatorRoomSettings.PrepareGravity(room,true);
  Check(room.gravity==1&&native.active,"native AntiGravity disabled by oracle constructor was not restored");
  room.gravity=.575f;MoreIterators.CreatorRoomSettings.PrepareGravity(room,true);Check(room.gravity==.575f,"native effect was overwritten every frame");
  MoreIterators.CreatorRoomSettings.PreviewGravity(room,0);Check(room.gravity==0,"F8 override did not win");
  room.gravity=.575f;MoreIterators.CreatorRoomSettings.PreviewGravity(room,-1);Check(room.gravity==.575f,"F8 release overwrote active native effect");
  MoreIterators.CreatorRoomSettings.PrepareGravity(room,false);Check(!native.active,"switching back to MI left native anti-gravity competing");
  var plain=new Room();plain.design.roomGravityMode="room";MoreIterators.CreatorRoomSettings.PrepareGravity(plain,true);
  MoreIterators.CreatorRoomSettings.PreviewGravity(plain,.4f);MoreIterators.CreatorRoomSettings.PreviewGravity(plain,.4f);MoreIterators.CreatorRoomSettings.PreviewGravity(plain,-1);Check(plain.gravity==1,"F8 release left gravity behind without an effect");
  var entry=new Room();entry.abstractRoom.name="XX_ENTRY";entry.gravity=.7f;MoreIterators.CreatorRoomSettings.WaitingGravity(entry);Check(entry.gravity==0,"old waiting room lost zero gravity");
  entry.design.entryGravityMode="room";MoreIterators.CreatorRoomSettings.WaitingGravity(entry);Check(entry.gravity==.7f,"native waiting setting was overwritten");
  entry.gravity=.3f;MoreIterators.CreatorRoomSettings.WaitingGravity(entry);Check(entry.gravity==.3f,"native waiting live gravity not left alone");
  var camera=new RoomCamera{room=room};MoreIterators.CreatorRoomSettings.Palette(camera,room.design,.5f);Check(camera.paletteA==25&&camera.paletteB==26,"legacy palette changed");
  int miChanges=camera.changes;
  for(int i=0;i<240;i++)MoreIterators.CreatorRoomSettings.Palette(camera,room.design,.5f);
  Check(camera.changes==miChanges,"stable MI palette repeatedly reapplied all room drawables");
  for(int i=1;i<=20;i++){float blend=.5f+i*.001f;MoreIterators.CreatorRoomSettings.Palette(camera,room.design,blend);Check(camera.changes==miChanges+i&&camera.paletteBlend==blend,"gradient sample was skipped or quantized");}
  miChanges=camera.changes;camera.paletteA=42;MoreIterators.CreatorRoomSettings.Palette(camera,room.design,.52f);Check(camera.changes==miChanges+1&&camera.paletteA==25,"external main palette change was not restored");
  miChanges=camera.changes;camera.paletteB=43;MoreIterators.CreatorRoomSettings.Palette(camera,room.design,.52f);Check(camera.changes==miChanges+1&&camera.paletteB==26,"external fade palette change was not restored");
  miChanges=camera.changes;camera.paletteBlend=.8f;MoreIterators.CreatorRoomSettings.Palette(camera,room.design,.52f);Check(camera.changes==miChanges+1&&camera.paletteBlend==.52f,"external blend change was not restored");
  miChanges=camera.changes;MoreIterators.IteratorDesign.Revision++;MoreIterators.CreatorRoomSettings.Palette(camera,room.design,.52f);Check(camera.changes==miChanges+1,"design revision did not reload the same palette IDs");
  miChanges=camera.changes;camera.room=new Room();MoreIterators.CreatorRoomSettings.Palette(camera,camera.room.design,.52f);Check(camera.changes==miChanges+1,"new room with matching palette did not reload");
  camera.room=room;MoreIterators.CreatorRoomSettings.Palette(camera,room.design,.52f);
  room.design.roomPaletteMode="room";room.roomSettings.fadePalette=new RoomSettings.Fade();camera.currentCameraPosition=1;
  MoreIterators.CreatorRoomSettings.Palette(camera,room.design,.9f);Check(camera.paletteA==7&&camera.paletteB==8&&camera.paletteBlend==.8f,"native per-camera fade not restored");
  camera.paletteA=42;int changes=camera.changes;MoreIterators.CreatorRoomSettings.Palette(camera,room.design,0);Check(camera.paletteA==42&&camera.changes==changes,"native DevTools/day-night palette was overwritten");
  room.roomSettings.fadePalette=null;MoreIterators.IteratorDesign.Revision++;MoreIterators.CreatorRoomSettings.Palette(camera,room.design,1);Check(camera.paletteA==7&&camera.paletteBlend==0,"native single palette not restored");
  camera.paletteA=25;camera.paletteB=26;camera.paletteBlend=.52f;miChanges=camera.changes;room.design.roomPaletteMode="mi";
  MoreIterators.CreatorRoomSettings.Palette(camera,room.design,.52f);Check(camera.changes==miChanges+1,"switching to MI mode did not reload matching palette IDs");
  Console.WriteLine("room controls passed");
 }
}
