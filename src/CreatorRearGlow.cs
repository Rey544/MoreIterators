using UnityEngine;

namespace MoreIterators {
 // Native OracleGraphics.Update queues its own radius and working-light alpha.
 // Apply after that update, and again when drawing for a paused studio, so the
 // pending native values cannot replace the selected project's current light.
 public static class CreatorRearGlow {
  static IteratorDesign Design(OracleGraphics graphics){
   return graphics==null||graphics.oracle==null||graphics.oracle.room==null?null:IteratorDesign.ForRoom(graphics.oracle.room);
  }
  static bool Visible(IteratorDesign design){return design.rearGlowEnabled&&CreatorRuntime.RearGlow;}
  static void Light(OracleGraphics graphics,IteratorDesign design){
   if(graphics.lightsource==null)return;
   graphics.lightsource.color=IteratorDesign.C(design.rearGlowColor);
   graphics.lightsource.HardSetRad(Mathf.Max(0,design.rearGlowRadius));
   graphics.lightsource.HardSetAlpha(Visible(design)?Mathf.Clamp01(design.rearGlowOpacity*2):0);
  }
  public static void Update(OracleGraphics graphics){
   var design=Design(graphics);if(design!=null)Light(graphics,design);
  }
  public static void Draw(OracleGraphics graphics,RoomCamera.SpriteLeaser leaser){
   var design=Design(graphics);if(design==null)return;
   Light(graphics,design);
   if(leaser==null||leaser.sprites==null||graphics.fadeSprite<0||graphics.fadeSprite>=leaser.sprites.Length)return;
   var glow=leaser.sprites[graphics.fadeSprite];if(glow==null)return;
   bool visible=Visible(design);
   glow.isVisible=visible;glow.color=IteratorDesign.C(design.rearGlowColor);
   glow.alpha=visible?Mathf.Clamp01(design.rearGlowOpacity):0;
   glow.scale=Mathf.Max(0,design.rearGlowRadius)/20f;
  }
 }
}
