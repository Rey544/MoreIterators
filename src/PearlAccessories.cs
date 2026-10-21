namespace MoreIterators {
using System;
using System.Collections.Generic;
using System.Runtime.CompilerServices;
using UnityEngine;

public static class PearlAccessories {
 public const int MaxGroups=8,MaxChildren=8,SlotsPerGroup=29,Slots=MaxGroups*SlotsPerGroup;
 sealed class Group {public PearlAccessoryPhysics physics=new PearlAccessoryPhysics();public Vector2 origin,right,up;public float scale,gravity;public bool active;}
 sealed class State {public State(){}public Group[] groups=new Group[MaxGroups];public HashSet<string> missing=new HashSet<string>();}
 static readonly ConditionalWeakTable<OracleGraphics,State> states=new ConditionalWeakTable<OracleGraphics,State>();
 public static void Update(OracleGraphics g){State state;if(!states.TryGetValue(g,out state))return;foreach(var group in state.groups)if(group!=null&&group.active)group.physics.Step(group.origin,group.right,group.up,group.scale,group.gravity);}
 static FSprite Sprite(RoomCamera.SpriteLeaser s,int slot,string element){var sprite=s.sprites[slot];if(sprite.element.name==element&&!(sprite is TriangleMesh))return sprite;var parent=sprite.container;sprite.RemoveFromContainer();sprite=new FSprite(element);s.sprites[slot]=sprite;parent.AddChild(sprite);return sprite;}
 static TriangleMesh Mesh(RoomCamera.SpriteLeaser s,int slot,int segments){segments=Mathf.Max(1,segments);var mesh=s.sprites[slot] as TriangleMesh;if(mesh!=null&&mesh.vertices.Length==segments*4)return mesh;var parent=s.sprites[slot].container;s.sprites[slot].RemoveFromContainer();mesh=TriangleMesh.MakeLongMesh(segments,false,true);s.sprites[slot]=mesh;parent.AddChild(mesh);return mesh;}
 static Vector2 RenderPoint(Group group,int index,float time,Vector2 camera){
  var p=group.physics;int first=p.pins[0],last=p.pins[p.pins.Count-1];Vector2 a=p.rest[first],b=p.rest[last];
  Vector2 moveA=group.origin+(group.right*a.x+group.up*a.y)*group.scale-p.Sample(first,time);
  Vector2 moveB=group.origin+(group.right*b.x+group.up*b.y)*group.scale-p.Sample(last,time);
  float t=Mathf.Abs(b.x-a.x)<.001f?0:Mathf.Clamp01((p.rest[index].x-a.x)/(b.x-a.x));
  return p.Sample(index,time)-camera+Vector2.Lerp(moveA,moveB,t);
 }
 public static Dictionary<string,List<FSprite>> Draw(OracleGraphics g,RoomCamera.SpriteLeaser s,int start,IteratorDesign d,Vector2 camera,float time,Vector2 up,Vector2 right,Func<string,float,float,Vector2> anchor){
  var result=new Dictionary<string,List<FSprite>>();for(int i=0;i<Slots;i++)s.sprites[start+i].isVisible=false;
  var state=states.GetOrCreateValue(g);foreach(var prior in state.groups)if(prior!=null)prior.active=false;
  if(d.pearlAccessories==null)return result;if(CreatorRuntime.Paused)time=1;
  int count=Mathf.Min(MaxGroups,d.pearlAccessories.Length);
  for(int index=0;index<count;index++){
   var item=d.pearlAccessories[index];if(item==null||!item.enabled||String.IsNullOrEmpty(item.id))continue;
   if(result.ContainsKey(item.id)){if(state.missing.Add("duplicate "+item.id))MiDiagnostics.Warn("MI_PEARL_ACCESSORY_DUPLICATE","PearlAccessories.Draw","A decorative pearl group ID was repeated; the duplicate was not drawn.",item.id);continue;}
   string binding=item.id+" -> "+item.anchor;
   if(!CreatorWardrobe.HasAnchor(item.anchor,g)){if(state.missing.Add(binding))MiDiagnostics.Warn("MI_PEARL_ACCESSORY_BINDING","PearlAccessories.Draw","The decorative pearl group references an unavailable attachment.",binding);continue;}state.missing.Remove(binding);
   var group=state.groups[index];if(group==null)state.groups[index]=group=new Group();
   Vector2 attachmentRight=anchor(item.anchor,Mathf.Clamp01(item.u+.01f),item.v)-anchor(item.anchor,Mathf.Clamp01(item.u-.01f),item.v);
   Vector2 attachmentUp=anchor(item.anchor,item.u,Mathf.Clamp01(item.v-.01f))-anchor(item.anchor,item.u,Mathf.Clamp01(item.v+.01f));
   if(attachmentRight.sqrMagnitude<.00001f)attachmentRight=right;else attachmentRight.Normalize();
   Vector2 orthogonal=new Vector2(-attachmentRight.y,attachmentRight.x);if(attachmentUp.sqrMagnitude<.00001f)attachmentUp=up;if(Vector2.Dot(orthogonal,attachmentUp)<0)orthogonal=-orthogonal;attachmentUp=orthogonal;
   float angle=item.rotation*Mathf.Deg2Rad;group.right=attachmentRight*Mathf.Cos(angle)-attachmentUp*Mathf.Sin(angle);group.up=attachmentUp*Mathf.Cos(angle)+attachmentRight*Mathf.Sin(angle);
   group.origin=anchor(item.anchor,item.u,item.v)+camera+(right*item.x+up*item.y)*d.puppetScale;group.scale=d.puppetScale;group.gravity=g.oracle.room.gravity;group.active=true;
   var physics=group.physics;physics.Configure(item);if(!physics.Ready)physics.Step(group.origin,group.right,group.up,group.scale,group.gravity);
   int slot=start+index*SlotsPerGroup;var sprites=new List<FSprite>();result[item.id]=sprites;
   var mesh=Mesh(s,slot,physics.links.Count);sprites.Add(mesh);mesh.isVisible=physics.links.Count>0&&(item.horizontalChains>0||item.hangingChains>0);mesh.color=Color.white;
   Color wire=IteratorDesign.C(item.stringColor);float width=item.thickness*d.puppetScale*.5f;
   for(int i=0;i<physics.links.Count;i++){var link=physics.links[i];Vector2 a=RenderPoint(group,link.a,time,camera),b=RenderPoint(group,link.b,time,camera),delta=b-a,normal=new Vector2(-delta.y,delta.x).normalized*width;
    mesh.MoveVertice(i*4,a-normal);mesh.MoveVertice(i*4+1,a+normal);mesh.MoveVertice(i*4+2,b-normal);mesh.MoveVertice(i*4+3,b+normal);for(int k=0;k<4;k++)mesh.verticeColors[i*4+k]=wire;
   }
   for(int i=0;i<physics.beadNodes.Length;i++){
    Vector2 position=RenderPoint(group,physics.beadNodes[i],time,camera);var palette=item.BeadColor(i)??new NecklacePearl();float diameter=item.BeadSize(i)*d.puppetScale;Color bodyColor=IteratorDesign.C(palette.color);
    var body=Sprite(s,slot+1+i*2,"JetFishEyeA");var glint=Sprite(s,slot+2+i*2,"tinyStar");sprites.Add(body);sprites.Add(glint);body.isVisible=glint.isVisible=true;
    body.SetPosition(position);body.scaleX=diameter/body.element.sourceSize.x;body.scaleY=diameter/body.element.sourceSize.y;body.rotation=0;body.color=bodyColor;body.alpha=1;
    glint.SetPosition(position+new Vector2(-.125f,.375f)*diameter);glint.scale=diameter/4;glint.rotation=0;glint.color=palette.dual?IteratorDesign.C(palette.highlight):Color.Lerp(bodyColor*1.3f,Color.white,.5f);glint.alpha=1;
   }
   var children=item.children??new PearlAccessoryChild[0];for(int i=0;i<Mathf.Min(MaxChildren,children.Length);i++){
    var child=children[i];if(child==null||!child.enabled||String.IsNullOrEmpty(child.png))continue;
    var texture=CreatorAppearance.Texture(child.png,d.oracleId+"-"+item.id+"-child-"+i);if(texture==null)continue;
    var sprite=Sprite(s,slot+21+i,texture.name);sprites.Add(sprite);sprite.element=texture;sprite.isVisible=true;
    Vector2 position=physics.beadNodes.Length==0?group.origin-camera:RenderPoint(group,physics.beadNodes[Mathf.Clamp(child.bead,0,physics.beadNodes.Length-1)],time,camera);
    sprite.SetPosition(position+(group.right*child.x+group.up*child.y)*d.puppetScale);sprite.rotation=Mathf.Atan2(group.up.x,group.up.y)*Mathf.Rad2Deg+child.rotation;
    sprite.scaleX=child.width*d.puppetScale/texture.sourceSize.x;sprite.scaleY=child.height*d.puppetScale/texture.sourceSize.y;sprite.color=IteratorDesign.C(child.color);sprite.alpha=1;
   }
  }
  return result;
 }
}
}
