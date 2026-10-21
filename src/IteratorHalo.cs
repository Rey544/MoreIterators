namespace MoreIterators {
using UnityEngine;
using System.Runtime.CompilerServices;
public static class IteratorHalo {
 // CustomDepth renders after the terrain grab, yet masks against actors and
 // nearer terrain. Vertex alpha is depth here; opacity belongs to the texture.
 public const float ProjectionDepth=.70f;
 static readonly FAtlasElement[] opacityPixels=new FAtlasElement[65];
 public static FAtlasElement OpacityPixel(float opacity){
  int i=Mathf.Clamp(Mathf.RoundToInt(opacity*64),0,64);if(opacityPixels[i]!=null)return opacityPixels[i];
  var tex=new Texture2D(1,1,TextureFormat.ARGB32,false);tex.filterMode=FilterMode.Point;tex.wrapMode=TextureWrapMode.Clamp;tex.SetPixel(0,0,new Color(1,1,1,i/64f));tex.Apply();
  string name="eoe_projection_alpha_"+i;Futile.atlasManager.LoadAtlasFromTexture(name,tex,false);return opacityPixels[i]=Futile.atlasManager.GetElementWithName(name);
 }
 static void Project(FSprite sprite,RoomCamera cam){
  sprite.shader=cam.game.rainWorld.Shaders["CustomDepth"];sprite.alpha=ProjectionDepth;
  var container=cam.ReturnFContainer("ForegroundLights");if(sprite.container!=container){sprite.RemoveFromContainer();container.AddChild(sprite);}
 }
 static void Ring(RoomCamera.SpriteLeaser s,int index,RoomCamera cam,Vector2 center,float radius,float width,Color color,float opacity){
  var mesh=s.sprites[index] as TriangleMesh;if(mesh==null){s.sprites[index].RemoveFromContainer();mesh=TriangleMesh.MakeLongMesh(96,false,false);s.sprites[index]=mesh;}
  mesh.x=mesh.y=mesh.rotation=0;mesh.scale=1;mesh.element=OpacityPixel(opacity);mesh.color=color;mesh.isVisible=true;Project(mesh,cam);
  var uv=mesh.element.uvBottomLeft;for(int v=0;v<mesh.UVvertices.Length;v++)mesh.UVvertices[v]=uv;
  for(int j=0;j<96;j++){float a=j*Mathf.PI*2/96,b=(j+1)*Mathf.PI*2/96;Vector2 u=new Vector2(Mathf.Cos(a),Mathf.Sin(a)),w=new Vector2(Mathf.Cos(b),Mathf.Sin(b));mesh.MoveVertice(j*4,center+u*Mathf.Max(0,radius-width));mesh.MoveVertice(j*4+1,center+u*radius);mesh.MoveVertice(j*4+2,center+w*Mathf.Max(0,radius-width));mesh.MoveVertice(j*4+3,center+w*radius);}
 }
 class Clock {public int remaining=280;}
 static readonly ConditionalWeakTable<OracleGraphics.Halo,Clock> clocks=new ConditionalWeakTable<OracleGraphics.Halo,Clock>();
 static readonly System.Reflection.FieldInfo ownerField=typeof(OracleGraphics.Halo).GetField("owner",System.Reflection.BindingFlags.NonPublic|System.Reflection.BindingFlags.Instance);
 public static void Update(On.OracleGraphics.Halo.orig_Update orig,OracleGraphics.Halo halo){
  var g=ownerField==null?null:ownerField.GetValue(halo) as OracleGraphics;
  if(g==null||g.oracle.room==null||!MoreIteratorsPlugin.IsChamber(g.oracle.room.abstractRoom.name)){orig(halo);return;}
  // Keep the native ring motion and bolt decay, replace only its burst scheduler.
  if(MoreIteratorsPlugin.IsChamber(g.oracle.room.abstractRoom.name)&&CreatorRuntime.Paused)return;halo.connectionsFireChance=0;orig(halo);halo.connectionsFireChance=0;
  var clock=clocks.GetOrCreateValue(halo);if(--clock.remaining>0)return;clock.remaining=Random.Range(240,441);
  if((MoreIteratorsPlugin.IsChamber(g.oracle.room.abstractRoom.name)&&!CreatorRuntime.Lightning)||!g.oracle.Consious||halo.connections.Length==0||!IteratorDesign.ForRoom(g.oracle.room).layers.halo)return;
  halo.connections[Random.Range(0,halo.connections.Length)].lightUp=.7f;
  g.oracle.room.PlaySound(SoundID.SS_AI_Halo_Connection_Light_Up,0f,.16f,.9f);
 }
 public static void Draw(OracleGraphics g,RoomCamera.SpriteLeaser s,RoomCamera cam,float t,Vector2 camera,IteratorDesign d,FSprite custom){
  var h=g.halo;if(h==null){custom.isVisible=false;return;}bool visible=d.layers.halo&&g.oracle.Consious;
  bool native=d.haloPreset=="original",painted=!native&&IteratorDesign.HaloElement!=null;Color color=IteratorDesign.C(d.haloColor);Vector2 center=h.Center(t)-camera;
  // Preserve FP's radii, memory-bit dimensions, rotations and occasional fill.
  // The annulus is meshed only so CustomDepth can mask it behind the puppet.
  for(int k=0;k<2;k++){s.sprites[h.firstSprite+k].isVisible=visible&&!painted;if(visible&&!painted){float radius=Mathf.Max(3,(3+k+Mathf.Lerp(h.lastPush,h.push,t)-.5f*g.averageVoice)*Mathf.Lerp(h.lastExpand,h.expand,t)*10*d.haloScale);float width=native?(k==0?Mathf.Lerp(3,radius,Mathf.Lerp(h.lastWhite,h.white,t)):3):1.25f;Ring(s,h.firstSprite+k,cam,center,radius,width,color,d.haloOpacity*.68f);}}
  int firstBit=h.firstSprite+2+h.connections.Length;
  for(int k=0;k<100;k++){var bit=s.sprites[firstBit+k];bit.isVisible=visible;bit.x=center.x+(bit.x-center.x)*d.haloScale;bit.y=center.y+(bit.y-center.y)*d.haloScale;bit.color=color;bit.element=OpacityPixel(d.haloOpacity*.62f);bit.scaleX=native?4:d.haloPreset=="bits"?2:1.2f;if(!native)bit.scaleY*=.6f;Project(bit,cam);}
  for(int k=0;k<h.connections.Length;k++){var bolt=(TriangleMesh)s.sprites[h.firstSprite+2+k];float light=Mathf.Lerp(h.connections[k].lastLightUp,h.connections[k].lightUp,t);bolt.isVisible=visible&&light>.05f;bolt.color=color;bolt.element=OpacityPixel(Mathf.Clamp01(light)*.65f);Project(bolt,cam);for(int v=0;v<bolt.UVvertices.Length;v++)bolt.UVvertices[v]=bolt.element.uvBottomLeft;
   if(bolt.isVisible)for(int v=0;v+1<bolt.vertices.Length;v+=2){Vector2 mid=(bolt.vertices[v]+bolt.vertices[v+1])*.5f;bolt.MoveVertice(v,Vector2.Lerp(mid,bolt.vertices[v],.55f));bolt.MoveVertice(v+1,Vector2.Lerp(mid,bolt.vertices[v+1],.55f));}
  }
  custom.isVisible=visible&&painted;
  if(custom.isVisible){
   custom.element=Futile.atlasManager.GetElementWithName(IteratorDesign.HaloElement);Project(custom,cam);
   // Fit the custom drawing to the same expanding radii as the native memory bits.
   float outer=(5.5f+Mathf.Lerp(h.lastPush,h.push,t)-.5f*g.averageVoice)*Mathf.Lerp(h.lastExpand,h.expand,t)*10*d.haloScale;
   custom.x=center.x;custom.y=center.y;custom.scale=Mathf.Max(12,outer)/115f;custom.color=color;
   custom.rotation=Mathf.Lerp(h.ringRotations[0,1],h.ringRotations[0,0],t)*.25f*d.haloSpeed;
  }
 }
}
}
