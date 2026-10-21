namespace MoreIterators {
using System;
using System.Runtime.CompilerServices;
using UnityEngine;

public static class CreatorNecklaces {
 public const int MaxStrands=5,MaxPearls=32,SlotsPerStrand=1+MaxPearls*2,Slots=MaxStrands*SlotsPerStrand;
 sealed class State {public State(){}public CreatorNecklaceRope[] ropes=new CreatorNecklaceRope[MaxStrands];public readonly Vector2[] points=new Vector2[CreatorNecklaceRope.N];}
 static readonly ConditionalWeakTable<OracleGraphics,State> states=new ConditionalWeakTable<OracleGraphics,State>();
 static Vector2 Map(Vector2 p,Vector2 head,Vector2 up,Vector2 right,IteratorDesign d){Vector2 q=p-head;float y=Vector2.Dot(q,up);return head+(right*Vector2.Dot(q,right)+up*(y< -7?-7+(y+7)*d.torsoLength:y))*d.puppetScale+up*(2-d.neckLength)*d.puppetScale;}
 public static void Anchors(Vector2 center,Vector2 right,Vector2 up,float scale,NecklaceDesign d,out Vector2 a,out Vector2 b){a=center+(right*d.leftX+up*d.leftY)*scale;b=center+(right*(d.symmetric?-d.leftX:d.rightX)+up*(d.symmetric?d.leftY:d.rightY))*scale;}
 public static void Update(OracleGraphics g){
  IteratorDesign d=IteratorDesign.ForRoom(g.oracle.room);State state=states.GetOrCreateValue(g);
  int count=Mathf.Min(Mathf.Clamp(d.necklaceCount,0,5),d.necklaces.Length);
  for(int i=count;i<5;i++)state.ropes[i]=null;
  if(count==0||g.gowns==null||g.gowns.Length==0)return;
  Vector2 head=g.head.pos,up=(head-g.oracle.bodyChunks[0].pos).normalized;if(up.sqrMagnitude<.1f)up=Vector2.up;Vector2 right=new Vector2(up.y,-up.x);
  var cp=g.gowns[0].clothPoints;Vector2 center=(cp[0,0,0]+cp[cp.GetLength(0)-1,0,0])*.5f;if(CreatorRuntime.IsAI(g.oracle.room.abstractRoom.name))center=Map(center,head,up,right,d);
  for(int i=0;i<count;i++){NecklaceDesign strand=d.necklaces[i];if(strand==null)continue;Vector2 a,b;Anchors(center,right,up,d.puppetScale,strand,out a,out b);if(state.ropes[i]==null)state.ropes[i]=new CreatorNecklaceRope();state.ropes[i].Step(a,b,-up,strand.sag*d.puppetScale,g.oracle.room.gravity,strand.softness);}
 }
 static FSprite Replace(RoomCamera.SpriteLeaser s,int index,string element){var old=s.sprites[index];if(old.element.name==element)return old;var container=old.container;old.RemoveFromContainer();var sprite=new FSprite(element);s.sprites[index]=sprite;container.AddChild(sprite);return sprite;}
 public static void Draw(OracleGraphics g,RoomCamera.SpriteLeaser s,int start,IteratorDesign d,Vector2 camera,float time,Vector2 up,Vector2 right){
  for(int i=0;i<Slots;i++)s.sprites[start+i].isVisible=false;
  State state;if(!states.TryGetValue(g,out state))return;if(CreatorRuntime.Paused)time=1;
  var gown=s.sprites[g.robeSprite] as TriangleMesh;if(gown==null)return;int dim=(int)Math.Sqrt(gown.vertices.Length);Vector2 center=(gown.vertices[0]+gown.vertices[(dim-1)*dim])*.5f;
  int count=Mathf.Min(Mathf.Clamp(d.necklaceCount,0,5),d.necklaces.Length);FNode front=s.sprites[g.HeadSprite];
  // Layer 1 is nearest the viewer. Draw 5 to 1 so overlap order stays stable.
  for(int strand=count-1;strand>=0;strand--){
   var rope=state.ropes[strand];if(rope==null)continue;var settings=d.necklaces[strand];Vector2 a,b;Anchors(center,right,up,d.puppetScale,settings,out a,out b);
   for(int i=0;i<CreatorNecklaceRope.N;i++){float u=i/(float)(CreatorNecklaceRope.N-1);state.points[i]=rope.Sample(i,time)-camera+Vector2.Lerp(a-(rope.Sample(0,time)-camera),b-(rope.Sample(CreatorNecklaceRope.N-1,time)-camera),u);}
   int slot=start+strand*SlotsPerStrand;var mesh=s.sprites[slot] as TriangleMesh;
   if(mesh==null){var container=s.sprites[slot].container;s.sprites[slot].RemoveFromContainer();mesh=TriangleMesh.MakeLongMesh(CreatorNecklaceRope.N-1,false,true);s.sprites[slot]=mesh;container.AddChild(mesh);}
   mesh.isVisible=true;mesh.color=Color.white;Color wire=IteratorDesign.C(settings.stringColor);
   for(int i=0;i<CreatorNecklaceRope.N-1;i++){
    Vector2 v0=state.points[i],v1=state.points[i+1],axis=v1-v0,normal=new Vector2(-axis.y,axis.x).normalized*(settings.thickness*d.puppetScale*.5f);
    mesh.MoveVertice(i*4,v0-normal);mesh.MoveVertice(i*4+1,v0+normal);mesh.MoveVertice(i*4+2,v1-normal);mesh.MoveVertice(i*4+3,v1+normal);for(int k=0;k<4;k++)mesh.verticeColors[i*4+k]=wire;
   }mesh.MoveBehindOtherNode(front);
   float total=0;for(int i=1;i<state.points.Length;i++)total+=Vector2.Distance(state.points[i-1],state.points[i]);
   int pearls=Mathf.Clamp(settings.pearls,0,MaxPearls);
   for(int i=0;i<pearls;i++){
    float remaining=total*(i+1f)/(pearls+1f);Vector2 position=state.points[0];for(int j=1;j<state.points.Length;j++){float len=Vector2.Distance(state.points[j-1],state.points[j]);if(remaining<=len||j==state.points.Length-1){position=Vector2.Lerp(state.points[j-1],state.points[j],len>.0001f?remaining/len:0);break;}remaining-=len;}
    var pearl=settings.Pearl(i);Color color=IteratorDesign.C(pearl.color),highlight=pearl.dual?IteratorDesign.C(pearl.highlight):Color.Lerp(color*1.3f,Color.white,.5f);
    var body=Replace(s,slot+1+i*2,"JetFishEyeA");var glint=Replace(s,slot+2+i*2,"tinyStar");float diameter=settings.PearlSize(i)*d.puppetScale;
    body.isVisible=glint.isVisible=true;body.SetPosition(position);body.scaleX=diameter/body.element.sourceSize.x;body.scaleY=diameter/body.element.sourceSize.y;body.color=color;body.alpha=1;
    glint.SetPosition(position+new Vector2(-.125f,.375f)*diameter);glint.scale=diameter/4;glint.color=highlight;glint.alpha=1;
    body.MoveInFrontOfOtherNode(mesh);glint.MoveInFrontOfOtherNode(body);
   }
  }
 }
}
}
