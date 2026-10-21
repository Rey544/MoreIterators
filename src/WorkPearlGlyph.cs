namespace MoreIterators {
using System.Collections.Generic;
using UnityEngine;
// The vanilla SingleGlyph shader encodes the glyph number in sprite.alpha and
// then outputs alpha=1. Bake its original mask once so opacity remains independent.
public sealed class WorkPearlGlyph : GlyphLabel {
 static readonly Dictionary<int,string> elements=new Dictionary<int,string>();
 static Texture2D source;
 public float opacity=.68f;
 public WorkPearlGlyph(Vector2 p,int glyph):base(p,new[]{glyph}){}
 internal static string Element(int glyph){
  glyph=Mathf.Clamp(glyph,0,49);string name;if(elements.TryGetValue(glyph,out name))return name;
  var e=Futile.atlasManager.GetElementWithName("glyphs");
  if(source==null){
   Texture texture=e.atlas.texture;var rt=RenderTexture.GetTemporary(texture.width,texture.height,0);var old=RenderTexture.active;
   try{Graphics.Blit(texture,rt);RenderTexture.active=rt;source=new Texture2D(texture.width,texture.height,TextureFormat.ARGB32,false);source.ReadPixels(new Rect(0,0,texture.width,texture.height),0,0);source.Apply(false);}
   finally{RenderTexture.active=old;RenderTexture.ReleaseTemporary(rt);}
  }
  int width=15,height=Mathf.Max(1,Mathf.RoundToInt(e.sourcePixelSize.y));
  var mask=new Texture2D(width,height,TextureFormat.ARGB32,false);mask.filterMode=FilterMode.Point;mask.wrapMode=TextureWrapMode.Clamp;
  for(int y=0;y<height;y++)for(int x=0;x<width;x++){
   float u=(glyph+Mathf.Lerp(e.uvBottomLeft.x,e.uvBottomRight.x,(x+.5f)/width))/50f;
   float v=Mathf.Lerp(e.uvBottomLeft.y,e.uvTopLeft.y,(y+.5f)/height);
   Color pixel=source.GetPixel(Mathf.Clamp((int)(u*source.width),0,source.width-1),Mathf.Clamp((int)(v*source.height),0,source.height-1));
   mask.SetPixel(x,y,pixel.r<.5f?Color.white:Color.clear);
  }
  mask.Apply(false);name="eoe_work_glyph_"+glyph;Futile.atlasManager.LoadAtlasFromTexture(name,mask,false);elements[glyph]=name;return name;
 }
 public override void InitiateSprites(RoomCamera.SpriteLeaser s,RoomCamera cam){
  s.sprites=new[]{new FSprite(Element(glyphs[0]))};s.sprites[0].anchorX=s.sprites[0].anchorY=0;AddToContainer(s,cam,null);
 }
 public override void DrawSprites(RoomCamera.SpriteLeaser s,RoomCamera cam,float t,Vector2 camera){
  if(slatedForDeletetion||room!=cam.room){s.CleanSpritesAndRemove();return;}
  Vector2 p=Vector2.Lerp(lastPos,pos,t)-camera;var sprite=s.sprites[0];
  sprite.element=Futile.atlasManager.GetElementWithName(Element(glyphs[0]));sprite.x=p.x;sprite.y=p.y;
  sprite.scale=Mathf.Lerp(lastScale,scale,t);sprite.color=color;sprite.alpha=Mathf.Clamp01(opacity);sprite.isVisible=visibleGlyphs>0&&glyphs[0]>=0&&sprite.scale>0&&CreatorRuntime.Pearls&&CreatorRuntime.Glyphs;
 }
}
}
