namespace MoreIterators {
using System;
using UnityEngine;

public static class CreatorHeadSegments {
 public const int Slots=8;
 public static int Start(int n){return CreatorWardrobe.Start(n)+CreatorWardrobe.Slots;}

 // Geometry is evaluated from the final head pose. These sprites have no cloth state.
 public static void Draw(OracleGraphics g,RoomCamera.SpriteLeaser s,int n,IteratorDesign d,Vector2 up,Vector2 right){
  if(g==null||s==null||d==null||s.sprites==null)return;
  int start=Start(n);if(start+Slots>s.sprites.Length)return;
  var headSprite=s.sprites[g.HeadSprite];
  Vector2 head=new Vector2(headSprite.x,headSprite.y);
  float scale=Finite(d.puppetScale,1,.1f,4),rotation=Mathf.Atan2(up.x,up.y)*Mathf.Rad2Deg;
  for(int side=0;side<2;side++){
   if(!d.antennaUpperEnabled){s.sprites[n+side].isVisible=false;s.sprites[n+9+side].isVisible=false;s.sprites[n+36+side].isVisible=false;}
   if(!d.earBodyEnabled){s.sprites[n+2+side].isVisible=false;int earStart=n+110+CreatorNecklaces.Slots+IteratorSprites.IntegrationSlots;for(int layer=0;layer<2;layer++)s.sprites[earStart+side*2+layer].isVisible=false;}
  }
  for(int part=0;part<2;part++)for(int side=0;side<2;side++){
   bool lower=part==0,enabled=lower?d.antennaLowerEnabled&&d.layers.antenna:d.earDecorationEnabled&&d.layers.ears;
   bool custom=lower?d.antennaLowerCustom:d.earDecorationCustom;
   float width=Finite(lower?d.antennaLowerWidth:d.earDecorationWidth,3,.2f,24)*scale;
   float height=Finite(lower?d.antennaLowerHeight:d.earDecorationHeight,10,.2f,40)*scale;
   float spread=Finite(lower?d.antennaLowerSpread:d.earDecorationSpread,8,0,40)*scale;
   float y=Finite(lower?d.antennaLowerOffsetY:d.earDecorationOffsetY,0,-80,40)*scale;
   Vector2 center=head+right*(side==0?-spread:spread)+up*y;
   for(int layer=0;layer<2;layer++){
    var sprite=s.sprites[start+part*4+side*2+layer];
    string png=lower?(side==0?(layer==0?d.antennaLowerLeftInnerPng:d.antennaLowerLeftPng):(layer==0?d.antennaLowerRightInnerPng:d.antennaLowerRightPng)):
     (side==0?(layer==0?d.earDecorationLeftInnerPng:d.earDecorationLeftPng):(layer==0?d.earDecorationRightInnerPng:d.earDecorationRightPng));
    var texture=custom?CreatorAppearance.Texture(png,d.oracleId+"-head-segment-"+part+"-"+side+"-"+layer):null;
    sprite.isVisible=enabled&&(custom?texture!=null:layer==0);
    if(!sprite.isVisible)continue;
    sprite.element=texture??Futile.atlasManager.GetElementWithName("pixel");
    sprite.anchorX=sprite.anchorY=.5f;sprite.SetPosition(center);sprite.rotation=rotation;
    sprite.scaleX=width/sprite.element.sourceSize.x;sprite.scaleY=height/sprite.element.sourceSize.y;
    sprite.color=custom?Color.white:IteratorDesign.C(lower?d.antennaLowerColor:d.earDecorationColor);sprite.alpha=1;
   }
  }
 }

 static float Finite(float value,float fallback,float min,float max){return Single.IsNaN(value)||Single.IsInfinity(value)?fallback:Mathf.Clamp(value,min,max);}

 // UV origin is the top-left of each whole rigid piece, matching the PNG editor.
 public static bool TryAnchor(OracleGraphics g,RoomCamera.SpriteLeaser s,int n,IteratorDesign d,string target,float u,float v,out Vector2 anchor){
  anchor=Vector2.zero;
  if(g==null||s==null||s.sprites==null||d==null||String.IsNullOrEmpty(target))return false;
  int side=target.EndsWith("R",StringComparison.Ordinal)?1:0;
  string key=target.Substring(0,target.Length-1);
  FSprite sprite=null;
  if(key=="ear"||key=="headphone")sprite=s.sprites[n+2+side];
  else if(key=="antennaLower"||key=="earDecoration"||key=="headphoneDecoration"){
   int index=Start(n)+(key=="antennaLower"?0:4)+side*2;
   if(index>=s.sprites.Length)return false;
   // Hidden material can still be used as a stable binding surface.
   bool lower=key=="antennaLower";
   var head=s.sprites[g.HeadSprite];var ear=s.sprites[n+2+side];
   float angle=ear.rotation*Mathf.Deg2Rad;Vector2 up=new Vector2(Mathf.Sin(angle),Mathf.Cos(angle)),right=new Vector2(up.y,-up.x);
   float width=lower?d.antennaLowerWidth:d.earDecorationWidth,height=lower?d.antennaLowerHeight:d.earDecorationHeight;
   float spread=lower?d.antennaLowerSpread:d.earDecorationSpread,y=lower?d.antennaLowerOffsetY:d.earDecorationOffsetY;
   anchor=new Vector2(head.x,head.y)+(right*((side==0?-spread:spread)+(Mathf.Clamp01(u)-.5f)*width)+up*(y+(.5f-Mathf.Clamp01(v))*height))*d.puppetScale;
   return true;
  }else if(key=="antennaUpper"||key=="antenna"){
   var outer=s.sprites[n+9+side];var inner=s.sprites[n+36+side];
   if(outer.isVisible)sprite=outer;else if(inner.isVisible)sprite=inner;
   else{
    var mesh=s.sprites[n+side] as TriangleMesh;
    if(mesh==null||mesh.vertices.Length<4)return false;
    int count=mesh.vertices.Length/4;float progress=(1-Mathf.Clamp01(v))*count;int segment=Mathf.Min(count-1,(int)progress);float t=progress-segment;
    anchor=Vector2.Lerp(Vector2.Lerp(mesh.vertices[segment*4],mesh.vertices[segment*4+1],Mathf.Clamp01(u)),Vector2.Lerp(mesh.vertices[segment*4+2],mesh.vertices[segment*4+3],Mathf.Clamp01(u)),t);return true;
   }
  }else return false;
  if(sprite==null||sprite.element==null)return false;
  float radians=sprite.rotation*Mathf.Deg2Rad;Vector2 axisY=new Vector2(Mathf.Sin(radians),Mathf.Cos(radians)),axisX=new Vector2(axisY.y,-axisY.x);
  anchor=new Vector2(sprite.x,sprite.y)+axisX*((Mathf.Clamp01(u)-sprite.anchorX)*sprite.element.sourceSize.x*sprite.scaleX)+axisY*((1-Mathf.Clamp01(v)-sprite.anchorY)*sprite.element.sourceSize.y*sprite.scaleY);
  return true;
 }
}
}
