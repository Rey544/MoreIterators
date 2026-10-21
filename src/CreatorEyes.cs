namespace MoreIterators {
using System;
using System.Collections.Generic;
using UnityEngine;

public static class CreatorEyes {
 public const int Slots=16;
 public static int Start(int n){return CreatorHeadSegments.Start(n)+CreatorHeadSegments.Slots+PearlAccessories.Slots;}
 public static bool Custom(IteratorDesign d){return d.eyes!=null&&d.eyes.Length>0;}
 public static EyeDesign Resolved(EyeDesign[] eyes,int index){
  var own=eyes[index];if(own==null||String.IsNullOrEmpty(own.mirrorOf))return own;
  EyeDesign source=null;foreach(var candidate in eyes)if(candidate!=null&&candidate.id==own.mirrorOf){source=candidate;break;}
  if(source==null||source==own||!String.IsNullOrEmpty(source.mirrorOf))return own;
  return new EyeDesign{id=own.id,enabled=own.enabled,sourceSide=source.sourceSide==1?0:1,offsetX=-source.offsetX,offsetY=source.offsetY,scale=source.scale,
   color=source.color,textureEnabled=source.textureEnabled,textureTint=source.textureTint,texturePng=source.texturePng,textureMirrorX=!source.textureMirrorX,mirrorOf=own.mirrorOf};
 }
 static float Finite(float value,float fallback,float min,float max){return float.IsNaN(value)||float.IsInfinity(value)?fallback:Mathf.Clamp(value,min,max);}

 // Run after the native DrawSprites and appearance transform. Native eyes remain
 // untouched templates: their geometry, alpha and rotation already contain the
 // game's interpolated eye state (including dialogue-driven EyesClosed).
 public static void Draw(OracleGraphics g,RoomCamera.SpriteLeaser s,int n,IteratorDesign d,Vector2 up,Vector2 right){
  int start=Start(n);if(s==null||s.sprites==null||start+Slots>s.sprites.Length)return;
  for(int i=0;i<Slots;i++)s.sprites[start+i].isVisible=false;
  if(!Custom(d))return;
  float bodyScale=Finite(d.puppetScale,1,.1f,4);
  for(int i=0;i<Math.Min(Slots,d.eyes.Length);i++){
   var eye=Resolved(d.eyes,i);if(eye==null)continue;
   var source=s.sprites[g.EyeSprite(eye.sourceSide==1?1:0)];
   var sprite=s.sprites[start+i];
   sprite.isVisible=eye.enabled&&d.layers.eyes&&source.isVisible;
   if(!sprite.isVisible)continue;
   var texture=eye.textureEnabled?CreatorAppearance.Texture(eye.texturePng,d.oracleId+"-eye-"+i):null;
   sprite.element=texture??source.element;sprite.shader=source.shader;
   float size=Finite(eye.scale,1,.1f,8);
   sprite.scaleX=source.scaleX*source.element.sourceSize.x/sprite.element.sourceSize.x*size;
   if(texture!=null&&eye.textureMirrorX)sprite.scaleX=-sprite.scaleX;
   sprite.scaleY=source.scaleY*source.element.sourceSize.y/sprite.element.sourceSize.y*size;
   sprite.anchorX=source.anchorX;sprite.anchorY=source.anchorY;
   sprite.rotation=source.rotation;sprite.alpha=source.alpha;
   Vector2 offset=(right*Finite(eye.offsetX,0,-40,40)+up*Finite(eye.offsetY,0,-40,40))*bodyScale;
   sprite.x=source.x+offset.x;sprite.y=source.y+offset.y;
   sprite.color=texture!=null&&!eye.textureTint?Color.white:IteratorDesign.C(String.IsNullOrEmpty(eye.color)?d.eyeColor:eye.color);
   if(sprite.container!=source.container){sprite.RemoveFromContainer();source.container.AddChild(sprite);}
   sprite.MoveInFrontOfOtherNode(s.sprites[g.ChinSprite]);
   sprite.MoveBehindOtherNode(s.sprites[n+8]);
  }
  // Hide only after every extra eye has sampled its own native template.
  s.sprites[g.EyeSprite(0)].isVisible=false;s.sprites[g.EyeSprite(1)].isVisible=false;
  if(g.IsPastMoon)s.sprites[g.MoonThirdEyeSprite].isVisible=false;
 }

 public static void AddToHeadGroup(RoomCamera.SpriteLeaser s,int n,List<FSprite> group){
  int start=Start(n);if(start+Slots>s.sprites.Length)return;
  // Place all eyes above the head/chin and below forehead/cheek artwork.
  for(int i=0;i<Slots;i++)group.Insert(Math.Min(4+i,group.Count),s.sprites[start+i]);
 }
}
}
