namespace MoreIterators {
using System;
using System.Runtime.CompilerServices;
using UnityEngine;

public static class CreatorScarf {
 sealed class State {public State(){}public CreatorCloth[] cloth;public int mode;}
 static readonly ConditionalWeakTable<OracleGraphics,State> states=new ConditionalWeakTable<OracleGraphics,State>();
 static Vector2 Map(Vector2 p,Vector2 head,Vector2 up,Vector2 right,IteratorDesign d){Vector2 q=p-head;float y=Vector2.Dot(q,up);return head+(right*Vector2.Dot(q,right)+up*(y< -7?-7+(y+7)*d.torsoLength:y))*d.puppetScale+up*(2-d.neckLength)*d.puppetScale;}
 public static void Bounds(int panel,int count,float gap,out float u0,out float u1){u0=count==1?0:panel==0?0:.5f+gap*.5f;u1=count==1?1:panel==0?.5f-gap*.5f:1;}
 static void Seam(Vector2 a,Vector2 b,IteratorDesign d,float u0,float u1,out Vector2 left,out Vector2 right){Vector2 center=Vector2.Lerp(a,b,(u0+u1)*.5f),axis=(b-a).normalized;float half=d.scarfTopWidth*(u1-u0)*d.puppetScale*.5f;left=center-axis*half;right=center+axis*half;}
 public static void Update(OracleGraphics g){
  if(g.gowns==null||g.gowns.Length==0)return;IteratorDesign d=IteratorDesign.ForRoom(g.oracle.room);State st=states.GetOrCreateValue(g);
  if(d.scarfPanels<=0){st.cloth=null;st.mode=0;return;}int count=Mathf.Clamp(d.scarfPanels,1,2);
  if(st.cloth==null||st.mode!=count){st.cloth=new CreatorCloth[count];for(int i=0;i<count;i++)st.cloth[i]=new CreatorCloth();st.mode=count;}
  Vector2 head=g.head.pos,up=(head-g.oracle.bodyChunks[0].pos).normalized;if(up.sqrMagnitude<.1f)up=Vector2.up;Vector2 right=new Vector2(up.y,-up.x);
  var cp=g.gowns[0].clothPoints;Vector2 a=cp[0,0,0],b=cp[cp.GetLength(0)-1,0,0];if(Vector2.Dot(a-b,right)>0){Vector2 temp=a;a=b;b=temp;}
  a=Map(a,head,up,right,d);b=Map(b,head,up,right,d);
  for(int i=0;i<count;i++){float u0,u1;Bounds(i,count,d.scarfGap,out u0,out u1);Vector2 left,r;Seam(a,b,d,u0,u1,out left,out r);float width=d.scarfShape==1?d.scarfTopWidth:d.scarfWidth;float offset=d.scarfShape==1?0:((u0+u1)*.5f-.5f)*(width*d.puppetScale-Vector2.Distance(a,b));st.cloth[i].Step(left,r,-up,width*(u1-u0)*d.puppetScale,d.scarfLength*d.puppetScale,g.oracle.room.gravity,d.scarfLightness,d.scarfFringeLength*d.puppetScale,i,offset);}
 }
 static TriangleMesh Grid(RoomCamera.SpriteLeaser s,int slot){var mesh=s.sprites[slot] as TriangleMesh;if(mesh==null||mesh.vertices.Length!=121){var container=s.sprites[slot].container;s.sprites[slot].RemoveFromContainer();mesh=TriangleMesh.MakeGridMesh("Futile_White",10);s.sprites[slot]=mesh;container.AddChild(mesh);}return mesh;}
 public static void Draw(OracleGraphics g,RoomCamera.SpriteLeaser s,int n,IteratorDesign d,Vector2 camera,float time,Vector2 right){
  if(d.scarfPanels<=0)return;State st;if(!states.TryGetValue(g,out st)||st.cloth==null)return;if(CreatorRuntime.Paused)time=1;
  var gown=s.sprites[g.robeSprite] as TriangleMesh;if(gown==null)return;int dim=(int)Math.Sqrt(gown.vertices.Length);
  Vector2 a=gown.vertices[0],b=gown.vertices[(dim-1)*dim];if(Vector2.Dot(a-b,right)>0){Vector2 t=a;a=b;b=t;}
  FSprite back=s.sprites[g.robeSprite];int[] body={g.neckSprite,g.HeadSprite,g.ChinSprite,g.firstBodyChunkSprite,g.firstBodyChunkSprite+1,g.HandSprite(0,0),g.HandSprite(0,1),g.HandSprite(1,0),g.HandSprite(1,1),g.FootSprite(0,0),g.FootSprite(1,0)};foreach(int index in body)if(s.sprites[index].depth<back.depth)back=s.sprites[index];
  var material=CreatorAppearance.Texture(d.scarfBasePng,d.oracleId+"-scarf-base");var pattern=CreatorAppearance.Texture(d.scarfPng,d.oracleId+"-scarf-pattern");
  for(int panel=0;panel<st.cloth.Length;panel++){
   float u0,u1;Bounds(panel,st.cloth.Length,d.scarfGap,out u0,out u1);Vector2 left,r;Seam(a,b,d,u0,u1,out left,out r);var cloth=st.cloth[panel];
   var mesh=Grid(s,n+40+panel*2);mesh.isVisible=true;
   for(int x=0;x<11;x++)for(int y=0;y<11;y++){float u=x/10f;Vector2 seam=Vector2.Lerp(left,r,u),anchor=cloth.Sample(x,0,time)-camera;mesh.MoveVertice(x*11+y,cloth.Sample(x,y,time)-camera+(seam-anchor)*Mathf.Max(0,1-y/2f));}
   CreatorAppearance.PaintMesh(mesh,material,true);if(material==null)mesh.color=IteratorDesign.C(d.scarfTopColor);mesh.MoveBehindOtherNode(back);
   var overlay=CreatorAppearance.Overlay(s,n+41+panel*2,mesh,pattern,true,false);
   // The two panels share the left/right halves of one UV canvas.
   if(st.cloth.Length==2){UvHalf(mesh,material,panel);UvHalf(overlay,pattern,panel);}
   for(int x=0;x<11;x++){
    int slot=n+44+panel*11+x;var fringe=s.sprites[slot] as TriangleMesh;
    if(fringe==null||fringe.vertices.Length!=12){var container=s.sprites[slot].container;s.sprites[slot].RemoveFromContainer();fringe=TriangleMesh.MakeLongMesh(3,false,true);s.sprites[slot]=fringe;container.AddChild(fringe);}
    fringe.isVisible=d.scarfFringe&&d.scarfFringeLength>.01f;fringe.color=Color.white;
    for(int k=0;k<3;k++){Vector2 p0=cloth.Fringe(x,k,time)-camera,p1=cloth.Fringe(x,k+1,time)-camera;if(k==0)p0=mesh.vertices[x*11+10];Vector2 v=p1-p0,normal=new Vector2(-v.y,v.x).normalized*(.32f*d.puppetScale);
     fringe.MoveVertice(k*4,p0-normal);fringe.MoveVertice(k*4+1,p0+normal);fringe.MoveVertice(k*4+2,p1-normal);fringe.MoveVertice(k*4+3,p1+normal);
     for(int j=0;j<4;j++)fringe.verticeColors[k*4+j]=IteratorDesign.C(d.scarfBottomColor);
    }fringe.MoveBehindOtherNode(mesh);
   }
  }
 }
 static void UvHalf(TriangleMesh mesh,FAtlasElement texture,int panel){if(mesh==null||texture==null)return;for(int i=0;i<mesh.UVvertices.Length;i++){Vector2 uv=mesh.UVvertices[i];float u=(uv.x-texture.uvBottomLeft.x)/(texture.uvTopRight.x-texture.uvBottomLeft.x);uv.x=Mathf.Lerp(texture.uvBottomLeft.x,texture.uvTopRight.x,(panel+u)*.5f);mesh.UVvertices[i]=uv;}}
}
}
