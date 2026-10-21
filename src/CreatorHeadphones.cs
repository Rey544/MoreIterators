namespace MoreIterators {
using UnityEngine;
// Reuse the final animated ear bases, after head/puppet transforms.
public static class CreatorHeadphones {
 public const int Slots=4;
 public static void Draw(OracleGraphics g,RoomCamera.SpriteLeaser s,int n,IteratorDesign d){
  int start=n+110+CreatorNecklaces.Slots+IteratorSprites.IntegrationSlots;
  for(int side=0;side<2;side++){
   var ear=s.sprites[n+2+side];
   if(!CreatorRuntime.IsAI(g.oracle.room.abstractRoom.name)){
    float angle=ear.rotation*Mathf.Deg2Rad;var up=new Vector2(Mathf.Sin(angle),Mathf.Cos(angle));var right=new Vector2(up.y,-up.x);
    ear.SetPosition(new Vector2(ear.x,ear.y)+right*(side==0?-d.earOffsetX:d.earOffsetX)+up*d.earOffsetY);
   }
   for(int layer=0;layer<2;layer++){
    var sprite=s.sprites[start+side*2+layer];
    string png=side==0?(layer==0?d.earLeftInnerPng:d.earLeftPng):(layer==0?d.earRightInnerPng:d.earRightPng);
    var e=CreatorAppearance.Texture(png,d.oracleId+"-ear-"+side+"-"+layer);
    sprite.isVisible=d.earCustom&&d.layers.ears&&e!=null;
    if(!sprite.isVisible)continue;
    sprite.element=e;sprite.SetPosition(new Vector2(ear.x,ear.y));sprite.rotation=ear.rotation;
    sprite.scaleX=ear.scaleX*ear.element.sourceSize.x/e.sourceSize.x;
    sprite.scaleY=ear.scaleY*ear.element.sourceSize.y/e.sourceSize.y;sprite.color=Color.white;sprite.alpha=1;
    sprite.MoveInFrontOfOtherNode(layer==0?ear:s.sprites[start+side*2]);
   }
   if(d.earCustom)ear.isVisible=false;
  }
 }
}
}
