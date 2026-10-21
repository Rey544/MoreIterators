using System.Collections.Generic;
using UnityEngine;

namespace MoreIterators {
 // Lights remain after the native terrain/object grab. The lighting mode uses
 // the game's depth/shadow-aware light shader without introducing another grab.
 public sealed class CreatorRoomGradient:CosmeticSprite {
  const int LightCount=5;
  readonly Vector2[] vertices;readonly TriangleMesh.Triangle[] triangles;readonly Rect bounds;
  IteratorDesign cached;string cachedMode;Color[][] colors;
  public CreatorRoomGradient(Room owner){
   room=owner;var points=new List<Vector2>();var faces=new List<TriangleMesh.Triangle>();var areas=ProjectionClip.Areas(owner);
   float minX=float.MaxValue,minY=float.MaxValue,maxX=0,maxY=0;
   foreach(var area in areas){minX=Mathf.Min(minX,area.xMin);minY=Mathf.Min(minY,area.yMin);maxX=Mathf.Max(maxX,area.xMax);maxY=Mathf.Max(maxY,area.yMax);
    int columns=Mathf.Max(1,Mathf.CeilToInt(area.width/40)),rows=Mathf.Max(1,Mathf.CeilToInt(area.height/40));
    for(int x=0;x<columns;x++)for(int y=0;y<rows;y++){
     int k=points.Count;float x0=area.x+area.width*x/columns,x1=area.x+area.width*(x+1)/columns,y0=area.y+area.height*y/rows,y1=area.y+area.height*(y+1)/rows;
     points.Add(new Vector2(x0,y0));points.Add(new Vector2(x1,y0));points.Add(new Vector2(x0,y1));points.Add(new Vector2(x1,y1));faces.Add(new TriangleMesh.Triangle(k,k+1,k+2));faces.Add(new TriangleMesh.Triangle(k+1,k+3,k+2));
    }
   }
   vertices=points.ToArray();triangles=faces.ToArray();bounds=areas.Length==0?new Rect(0,0,1,1):new Rect(minX,minY,maxX-minX,maxY-minY);
  }
  public override void InitiateSprites(RoomCamera.SpriteLeaser s,RoomCamera camera){
   s.sprites=new FSprite[LightCount];
   for(int i=0;i<LightCount;i++){s.sprites[i]=triangles.Length==0?new FSprite("pixel"):(FSprite)new TriangleMesh("Futile_White",triangles,true);s.sprites[i].shader=camera.game.rainWorld.Shaders["LightSource"];s.sprites[i].isVisible=false;}
   AddToContainer(s,camera,null);
  }
  public override void AddToContainer(RoomCamera.SpriteLeaser s,RoomCamera camera,FContainer container){
   // Base gradient, then the four corner lights, all behind existing foreground lights.
   for(int i=s.sprites.Length-1;i>=0;i--){var sprite=s.sprites[i];sprite.RemoveFromContainer();camera.ReturnFContainer("ForegroundLights").AddChild(sprite);sprite.MoveToBack();}
  }
  static CornerGlow Corner(RoomGradient settings,int index){return settings!=null&&settings.corners!=null&&index<settings.corners.Length?settings.corners[index]:null;}
  void Cache(IteratorDesign d,RoomGradient settings,bool lighting){
   cached=d;cachedMode=lighting?"lighting":"overlay";colors=new Color[LightCount][];
   for(int layer=0;layer<LightCount;layer++){
    colors[layer]=new Color[vertices.Length];var corner=layer==0?null:Corner(settings,layer-1);
    for(int i=0;i<vertices.Length;i++){
     float x=(vertices[i].x-bounds.xMin)/bounds.width,y=1-(vertices[i].y-bounds.yMin)/bounds.height;
     Color color=Color.clear;
     if(settings!=null){if(!lighting&&layer==0)color=settings.Sample(x,y);else if(layer==0)color=settings.BaseSample(x,y);else if(corner!=null&&corner.enabled){color=IteratorDesign.C(corner.color);color.a=Mathf.Clamp01(corner.opacity);}}
     colors[layer][i]=lighting?RoomGradient.NativeLight(color):color;
    }
   }
  }
  public override void DrawSprites(RoomCamera.SpriteLeaser s,RoomCamera camera,float timeStacker,Vector2 cameraPos){
   if(slatedForDeletetion||room!=camera.room){s.CleanSpritesAndRemove();return;}
   var d=IteratorDesign.ForRoom(room);var settings=d.roomGradient;bool lighting=settings!=null&&settings.renderMode!="overlay";
   if(cached!=d||cachedMode!=(lighting?"lighting":"overlay"))Cache(d,settings,lighting);
   for(int layer=0;layer<LightCount;layer++){
    var mesh=s.sprites[layer] as TriangleMesh;if(mesh==null){s.sprites[layer].isVisible=false;continue;}
    var corner=layer==0?null:Corner(settings,layer-1);
    bool enabled=settings!=null&&(layer==0?(settings.enabled||!lighting&&System.Array.Exists(settings.corners??new CornerGlow[0],c=>c!=null&&c.enabled)):lighting&&corner!=null&&corner.enabled);
    mesh.isVisible=enabled;if(!enabled)continue;
    if(mesh.container!=camera.ReturnFContainer("ForegroundLights"))AddToContainer(s,camera,null);
    mesh.shader=camera.game.rainWorld.Shaders[lighting?"LightSource":"FlatLightBehindTerrain"];
    Vector2 center=layer==0?bounds.center:new Vector2((layer-1)%2==0?bounds.xMin:bounds.xMax,(layer-1)/2==0?bounds.yMax:bounds.yMin);
    float radius=layer==0?Mathf.Sqrt(bounds.width*bounds.width+bounds.height*bounds.height)*.7f:Mathf.Max(bounds.width,bounds.height)*Mathf.Max(.05f,corner.radius);
    radius=Mathf.Max(1,radius);
    float lightStrength=lighting?Mathf.Clamp01(1-room.darkenLightsFactor):1;
    mesh.color=Color.white;
    for(int i=0;i<vertices.Length;i++){
     mesh.MoveVertice(i,vertices[i]-cameraPos);Color color=colors[layer][i];color.a*=lightStrength;mesh.verticeColors[i]=color;
     // Native lights derive their shadow direction and radial falloff from UV.
     // Each corner must retain its own light centre rather than reusing a flat disc.
     mesh.UVvertices[i]=lighting?new Vector2(.5f+(vertices[i].x-center.x)/(2*radius),.5f+(vertices[i].y-center.y)/(2*radius)):new Vector2(.5f,.5f);
    }
    mesh.Refresh();
   }
  }
 }
}


