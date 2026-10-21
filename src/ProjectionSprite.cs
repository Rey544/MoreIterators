using System;
using UnityEngine;

namespace MoreIterators {
 // An owned CosmeticSprite uses the same Projection shader and
 // image-size encoding as ProjectedImage. Original atlas ownership is untouched.
 public sealed class ProjectionSprite:CosmeticSprite {
  readonly CreatorProjections owner;readonly ProjectionTrack track;
  readonly string atlas;Texture2D texture;bool released;
  readonly Rect[] clipAreas;
  public float time;public bool visible=true;
  public ProjectionSprite(CreatorProjections owner,ProjectionGroup group,ProjectionTrack track){
   this.owner=owner;this.track=track;room=owner.room;
   clipAreas=ProjectionClip.Resolve(room,group,track);
   if(track.kind!="image")return;
   var image=Array.Find(group.images,i=>i.id==track.imageId);
   if(image==null)throw new InvalidOperationException("Projection image is not in the animation group.");
   byte[] png=Convert.FromBase64String(image.png.Substring("data:image/png;base64,".Length));
   if(png.Length>4194304)throw new InvalidOperationException("Projection PNG exceeds 4 MB.");
   // Read IHDR before decoding; untrusted runtime JSON cannot allocate a huge texture.
   if(png.Length<24||png[0]!=137||png[1]!=80||png[2]!=78||png[3]!=71||Dimension(png,16)!=image.width||Dimension(png,20)!=image.height)throw new InvalidOperationException("Projection PNG dimensions do not match its document.");
   atlas="mi-projection-"+Guid.NewGuid().ToString("N");
   try{texture=new Texture2D(2,2,TextureFormat.ARGB32,false);if(!texture.LoadImage(png))throw new InvalidOperationException("Projection PNG decode failed.");texture.filterMode=FilterMode.Point;texture.wrapMode=TextureWrapMode.Clamp;Futile.atlasManager.LoadAtlasFromTexture(atlas,texture,false);}
   catch{if(texture!=null)UnityEngine.Object.Destroy(texture);texture=null;throw;}
  }
  static int Dimension(byte[] bytes,int p){return (bytes[p]<<24)|(bytes[p+1]<<16)|(bytes[p+2]<<8)|bytes[p+3];}
  public override void InitiateSprites(RoomCamera.SpriteLeaser s,RoomCamera camera){
   int count=track.kind=="circle"?64:track.kind=="grid"?18:track.kind=="matrix"?16:track.kind=="cursor"?5:1;s.sprites=new FSprite[count];
   bool glyph=track.kind=="glyph"||track.kind=="matrix";
   // Reuse the native glyph mask baker: stock glyph shaders use alpha as an
   // index, which would otherwise make animation opacity a different character.
   for(int i=0;i<count;i++){string element=track.kind=="image"?atlas:glyph?WorkPearlGlyph.Element((track.glyphIndex+i)%50):"pixel";s.sprites[i]=clipAreas==null?new FSprite(element):ProjectionClip.Create(element,clipAreas.Length);}
   string shaderName=track.kind=="image"&&track.style!="plain"?"Projection":"";
   if(shaderName!=""){FShader shader;if(camera.game.rainWorld.Shaders.TryGetValue(shaderName,out shader)){foreach(var sprite in s.sprites)sprite.shader=shader;}else MiDiagnostics.Warn("MI-PROJECTION-SHADER","ProjectionSprite.InitiateSprites","Shader unavailable: "+shaderName,track.name);}
   AddToContainer(s,camera,null);
  }
  public override void AddToContainer(RoomCamera.SpriteLeaser s,RoomCamera camera,FContainer container){
   // Native Projection reads the grab texture produced by the foreground level
   // pass. Plain art and primitives stay behind puppet/item sprites.
   container=container??camera.ReturnFContainer(track.kind=="image"&&track.style=="native"?"Foreground":"BackgroundShortcuts");
   foreach(var sprite in s.sprites){sprite.RemoveFromContainer();container.AddChild(sprite);}
  }
  public override void DrawSprites(RoomCamera.SpriteLeaser s,RoomCamera camera,float timeStacker,Vector2 cameraPos){
   if(slatedForDeletetion||owner.slatedForDeletetion||room!=camera.room){s.CleanSpritesAndRemove();return;}
   var frame=ProjectionTimeline.Sample(track,time+(CreatorRuntime.Paused?0:timeStacker/40f));
   float blink=1-frame.flicker*(.5f+.5f*Mathf.Sin(time*91f)*Mathf.Sin(time*37f));
   float alpha=Mathf.Clamp01(frame.opacity*frame.brightness*blink);Color color=IteratorDesign.C(track.color)*Mathf.Min(frame.brightness,2);color.a=1;
   Vector2 center=new Vector2(frame.x*room.PixelWidth,(1-frame.y)*room.PixelHeight)-cameraPos;
   foreach(var sprite in s.sprites){sprite.isVisible=visible&&alpha>.001f;sprite.alpha=alpha;sprite.color=color;}
   float size=140*frame.scale;
   if(track.kind=="image"){
    var sprite=s.sprites[0];sprite.SetPosition(center);sprite.scale=frame.scale;sprite.rotation=frame.rotation;
    if(track.style=="native")sprite.color=new Color(Mathf.InverseLerp(1,1000,texture.width),Mathf.InverseLerp(1,1000,texture.height),0);
   }else if(track.kind=="glyph"||track.kind=="matrix"){
    for(int i=0;i<s.sprites.Length;i++){var sprite=s.sprites[i];Vector2 offset=track.kind=="matrix"?new Vector2((i%4-1.5f)*size/4,(1.5f-i/4)*size/4):Vector2.zero;sprite.SetPosition(center+Rotate(offset,frame.rotation));float glyphSize=track.kind=="matrix"?size/5:size;sprite.scaleX=glyphSize/sprite.element.sourceSize.x;sprite.scaleY=glyphSize/sprite.element.sourceSize.y;sprite.rotation=frame.rotation;
     sprite.alpha=alpha;
    }
   }else if(track.kind=="cursor"){
    for(int i=0;i<4;i++){Vector2 a=new Vector2(i<2?-size/2:size/2,(i==0||i==3)?-size/2:size/2);int j=(i+1)%4;Vector2 b=new Vector2(j<2?-size/2:size/2,(j==0||j==3)?-size/2:size/2);Segment(s.sprites[i],center+Rotate(a,frame.rotation),center+Rotate(b,frame.rotation),1.5f);}
    s.sprites[4].SetPosition(center);s.sprites[4].scaleX=s.sprites[4].scaleY=size;s.sprites[4].rotation=frame.rotation;s.sprites[4].alpha=alpha*.08f;
   }else if(track.kind=="line"||track.kind=="scanline"){float length=track.kind=="scanline"?size*2:size;Segment(s.sprites[0],center+Rotate(new Vector2(-length/2,0),frame.rotation),center+Rotate(new Vector2(length/2,0),frame.rotation),1.5f);}
   else if(track.kind=="circle")for(int i=0;i<s.sprites.Length;i++){
    float a=i*Mathf.PI*2/s.sprites.Length,b=(i+1)*Mathf.PI*2/s.sprites.Length;
    Segment(s.sprites[i],center+new Vector2(Mathf.Cos(a),Mathf.Sin(a))*size/2,center+new Vector2(Mathf.Cos(b),Mathf.Sin(b))*size/2,1.4f);
   }else if(track.kind=="grid")for(int i=0;i<9;i++){
    float offset=(i/8f-.5f)*size;
    Segment(s.sprites[i],center+Rotate(new Vector2(offset,-size/2),frame.rotation),center+Rotate(new Vector2(offset,size/2),frame.rotation),1);
    Segment(s.sprites[i+9],center+Rotate(new Vector2(-size/2,offset),frame.rotation),center+Rotate(new Vector2(size/2,offset),frame.rotation),1);
   }
   if(clipAreas!=null)foreach(var sprite in s.sprites)ProjectionClip.Apply((TriangleMesh)sprite,clipAreas,cameraPos);
  }
  static Vector2 Rotate(Vector2 p,float degrees){float r=-degrees*Mathf.Deg2Rad;return new Vector2(p.x*Mathf.Cos(r)-p.y*Mathf.Sin(r),p.x*Mathf.Sin(r)+p.y*Mathf.Cos(r));}
  static void Segment(FSprite sprite,Vector2 a,Vector2 b,float width){sprite.SetPosition((a+b)/2);sprite.scaleX=width;sprite.scaleY=Vector2.Distance(a,b)+.4f;sprite.rotation=Mathf.Atan2(b.x-a.x,b.y-a.y)*Mathf.Rad2Deg;}
  public override void Destroy(){if(!released){released=true;if(atlas!=null)Futile.atlasManager.UnloadAtlas(atlas);if(texture!=null)UnityEngine.Object.Destroy(texture);texture=null;}base.Destroy();}
 }
}
