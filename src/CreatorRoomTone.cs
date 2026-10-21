namespace MoreIterators {
using UnityEngine;
public static class CreatorRoomTone {
 public static void Apply(Texture2D t,RoomCamera cam){
  var room=MoreIteratorsPlugin.PaletteRoom(cam);if(room==null||!MoreIteratorsPlugin.IsChamber(room.abstractRoom.name))return;
  var d=IteratorDesign.ForRoom(room);
  // Only terrain colour banks; never touch encoded depth/effect/control pixels.
  for(int y=0;y<t.height;y++)for(int x=0;x<Mathf.Min(30,t.width);x++){
   if(y%8>5)continue;Color c=t.GetPixel(x,y);float grey=c.r*.2126f+c.g*.7152f+c.b*.0722f;
   c=Color.LerpUnclamped(new Color(grey,grey,grey,c.a),c,d.roomSaturation);
   c.r=Mathf.Clamp01(((c.r-.25f)*d.roomContrast+.25f)*d.roomBrightness);
   c.g=Mathf.Clamp01(((c.g-.25f)*d.roomContrast+.25f)*d.roomBrightness);
   c.b=Mathf.Clamp01(((c.b-.25f)*d.roomContrast+.25f)*d.roomBrightness);t.SetPixel(x,y,c);
  }t.Apply(false);
 }
}
}
