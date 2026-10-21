namespace MoreIterators {
using System;
using System.Collections.Generic;
using System.Runtime.CompilerServices;
using UnityEngine;

public static class CreatorWardrobe {
 public const int Max=19,Slots=Max*6+12;
 sealed class Piece {public GarmentPhysics cloth=new GarmentPhysics(),mirrorCloth=new GarmentPhysics();public GarmentDesign design;public Vector2 a,b,ma,mb,right,down;public float scale,gravity;public bool ready,wasCloth;}
 sealed class State {public State(){}public Piece[] parts=new Piece[Max];public Dictionary<string,TriangleMesh> meshes=new Dictionary<string,TriangleMesh>();public CreatorLegPhysics[] leg=new CreatorLegPhysics[]{new CreatorLegPhysics(),new CreatorLegPhysics()};public Vector2[] hip=new Vector2[2],nativeFoot=new Vector2[2];public Vector2 down;public IteratorDesign legDesign;public float legGravity;public bool legs;public string bindingError="";public IteratorDesign design;}
 static readonly ConditionalWeakTable<OracleGraphics,State> states=new ConditionalWeakTable<OracleGraphics,State>();
 public static int Start(int n){return n+110+CreatorNecklaces.Slots+IteratorSprites.IntegrationSlots+CreatorHeadphones.Slots;}
 public static void Update(OracleGraphics g){State st;if(!states.TryGetValue(g,out st))return;foreach(var p in st.parts)if(p!=null&&p.ready&&p.design.type=="cloth"){p.cloth.Step(p.a,p.b,p.right,p.down,p.design,p.scale,p.gravity);if(p.design.mirror)p.mirrorCloth.Step(p.ma,p.mb,-p.right,p.down,p.design,p.scale,p.gravity);}if(st.legs&&st.legDesign!=null)for(int side=0;side<2;side++){var d=st.legDesign;Vector2 origin=d.legSymmetry?(st.hip[0]+st.hip[1])*.5f:st.hip[side];if(side==1&&d.legSymmetry)st.leg[1].FollowParallel(st.leg[0],origin,st.hip[1]);else st.leg[side].Step(origin,st.down,st.nativeFoot[side],d.ThighLength(side)*d.puppetScale,d.ShinLength(side)*d.puppetScale,d.LegElasticity(side),st.legGravity);}}
 public static TriangleMesh Grid(RoomCamera.SpriteLeaser s,int slot){var mesh=s.sprites[slot] as TriangleMesh;if(mesh==null||mesh.vertices.Length!=121){var container=s.sprites[slot].container;s.sprites[slot].RemoveFromContainer();mesh=TriangleMesh.MakeGridMesh("Futile_White",10);s.sprites[slot]=mesh;container.AddChild(mesh);}return mesh;}
 public static Vector2 At(TriangleMesh mesh,float u,float v){return GarmentGeometry.Surface(mesh==null?null:mesh.vertices,u,v);}

 static Vector2 Position(FSprite s){return new Vector2(s.x,s.y);}
 static Vector2 Anchor(string id,float u,float v,OracleGraphics g,RoomCamera.SpriteLeaser s,State st,Vector2 right,int n){TriangleMesh mesh=null;if(id=="gown"||id=="shoulders")mesh=s.sprites[g.robeSprite] as TriangleMesh;else if(id=="sleeveL"||id=="sleeveR")mesh=s.sprites[g.HandSprite(id=="sleeveL"?0:1,1)] as TriangleMesh;else if(id=="collar")mesh=s.sprites[n+31] as TriangleMesh;else st.meshes.TryGetValue(id??"",out mesh);
  if(mesh!=null){if(id=="shoulders"||id=="gown"||id=="collar"){if(Vector2.Dot(At(mesh,1,0)-At(mesh,0,0),right)<0)u=1-u;if(id=="shoulders")v=0;}return At(mesh,u,v);}
  Vector2 hardware;if(CreatorHeadSegments.TryAnchor(g,s,n,st.design??IteratorDesign.ForRoom(g.oracle.room),id,u,v,out hardware))return hardware;
  if(id=="neck")return SpriteAnchor(s.sprites[g.neckSprite],u,v);
  if(id=="head")return SpriteAnchor(s.sprites[g.HeadSprite],u,v);
  if(id=="handL"||id=="handR")return SpriteAnchor(s.sprites[g.HandSprite(id=="handL"?0:1,0)],u,v);
  if(id=="legL"||id=="legR"){int side=id=="legL"?0:1;if(st.legs){int slot=Start(n)+Max*6+side*6;var thigh=s.sprites[slot] as TriangleMesh;var shin=s.sprites[slot+4] as TriangleMesh;float split=st.legDesign.ThighLength(side)/(st.legDesign.ThighLength(side)+st.legDesign.ShinLength(side));if(thigh!=null&&shin!=null)return v<split?At(thigh,u,v/split):At(shin,u,(v-split)/(1-split));}return At(s.sprites[g.FootSprite(side,1)] as TriangleMesh,u,v);}
  return SpriteAnchor(s.sprites[g.firstBodyChunkSprite],u,v);
 }
 public static bool HasAnchor(string id,OracleGraphics g){State state;return GarmentBindings.BuiltIn(id)||(id!=null&&states.TryGetValue(g,out state)&&state.meshes.ContainsKey(id));}
 public static Vector2 ResolveAnchor(string id,float u,float v,OracleGraphics g,RoomCamera.SpriteLeaser sprites,Vector2 right,int n){
  if(!HasAnchor(id,g))throw new InvalidOperationException("Accessory binding target is unavailable: "+id);
  State state=states.GetOrCreateValue(g);return Anchor(id,Mathf.Clamp01(u),Mathf.Clamp01(v),g,sprites,state,right,n);
 }
 public static void ResolveAnchorFrame(string id,OracleGraphics g,RoomCamera.SpriteLeaser sprites,Vector2 fallbackRight,int n,out Vector2 right,out Vector2 up){
  right=ResolveAnchor(id,1,.5f,g,sprites,fallbackRight,n)-ResolveAnchor(id,0,.5f,g,sprites,fallbackRight,n);
  Vector2 vertical=ResolveAnchor(id,.5f,0,g,sprites,fallbackRight,n)-ResolveAnchor(id,.5f,1,g,sprites,fallbackRight,n);
  right=right.sqrMagnitude>.0001f?right.normalized:fallbackRight.normalized;up=new Vector2(-right.y,right.x);
  if(vertical.sqrMagnitude>.0001f&&Vector2.Dot(up,vertical)<0)up=-up;
 }
 static Vector2 SpriteAnchor(FSprite sprite,float u,float v){float a=sprite.rotation*Mathf.Deg2Rad;Vector2 up=new Vector2(Mathf.Sin(a),Mathf.Cos(a)),right=new Vector2(up.y,-up.x);return Position(sprite)+right*((u-sprite.anchorX)*sprite.width)+up*((1-v-sprite.anchorY)*sprite.height);}
 static bool Enabled(GarmentDesign a,int index,IteratorDesign d){return index>=2&&index<7?index-2<d.shawlCount:a.enabled;}
 // Missing legacy arrays contain no garments. Keep their sprite slots reserved
 // separately so real custom pieces still start at slot 7.
 static List<GarmentDesign> Designs(IteratorDesign d,out List<int> slots){
  var list=new List<GarmentDesign>();slots=new List<int>();
  AddDesigns(d.frontPanels,2,0,list,slots);AddDesigns(d.shawls,5,2,list,slots);AddDesigns(d.accessories,12,7,list,slots);
  return list;
 }
 static void AddDesigns(GarmentDesign[] source,int limit,int offset,List<GarmentDesign> designs,List<int> slots){
  if(source==null)return;
  for(int i=0;i<source.Length&&i<limit;i++){designs.Add(source[i]);slots.Add(offset+i);}
 }
 public static void Draw(OracleGraphics g,RoomCamera.SpriteLeaser s,int n,IteratorDesign d,Vector2 camera,float time,Vector2 up,Vector2 right){
  int start=Start(n);for(int i=0;i<Slots;i++)s.sprites[start+i].isVisible=false;
  State st=states.GetOrCreateValue(g);st.design=d;st.meshes.Clear();if(CreatorRuntime.Paused)time=1;
  DrawSleeves(g,s,n,d);CreatorArms.Draw(g,s,n,d,up,right);DrawLegs(g,s,start+Max*6,d,camera,time,up,right,st);
  List<int> slots;var list=Designs(d,out slots);var done=new HashSet<string>();var groups=new Dictionary<string,List<FSprite>>();
  // Binding order and draw order are independent; invalid imported graphs are
  // reported once and their affected branches are hidden instead of reattached.
  string bindingError;var bindingOrder=GarmentBindings.Order(list,out bindingError);
  if(bindingError!=st.bindingError){st.bindingError=bindingError;if(bindingError.Length>0)MiDiagnostics.Warn("MI-ACCESSORY-BINDING","CreatorWardrobe.Draw",bindingError,d.oracleId);}
  foreach(int bindingIndex in bindingOrder){
   int index=slots[bindingIndex];var a=list[bindingIndex];done.Add(a.id);bool visible=Enabled(a,index,d),cloth=a.type=="cloth";
   Vector2 p0=Anchor(a.anchor,a.u,a.v,g,s,st,right,n)+(right*a.x+up*a.y)*d.puppetScale,p1=Anchor(a.anchor2,a.u2,a.v2,g,s,st,right,n)+(right*a.x2+up*a.y2)*d.puppetScale;
   if(cloth&&a.topWidth>0){Vector2 c=(p0+p1)*.5f,axis=p1-p0;if(axis.sqrMagnitude<.01f)axis=right;else axis.Normalize();p0=c-axis*a.topWidth*d.puppetScale*.5f;p1=c+axis*a.topWidth*d.puppetScale*.5f;}
   Piece p=st.parts[index];if(p==null)st.parts[index]=p=new Piece();p.design=a;p.right=right;p.down=-up;p.scale=d.puppetScale;p.gravity=g.oracle.room.gravity;
   p.a=p0+camera;p.b=p1+camera;Vector2 mirrorCenter=Position(s.sprites[g.firstBodyChunkSprite])+camera;p.ma=p.a-right*2*Vector2.Dot(p.a-mirrorCenter,right);p.mb=p.b-right*2*Vector2.Dot(p.b-mirrorCenter,right);if(cloth&&(!p.ready||!p.wasCloth)){p.cloth=new GarmentPhysics();p.mirrorCloth=new GarmentPhysics();p.cloth.Step(p.a,p.b,right,-up,a,p.scale,p.gravity);p.mirrorCloth.Step(p.ma,p.mb,-right,-up,a,p.scale,p.gravity);}p.ready=true;p.wasCloth=cloth;
   Vector2 rigidRight,rigidUp;ResolveAnchorFrame(a.anchor,g,s,right,n,out rigidRight,out rigidUp);
   var mesh=Grid(s,start+index*6);mesh.isVisible=visible;
   for(int x=0;x<11;x++)for(int y=0;y<11;y++){float u=x/10f,v=y/10f;Vector2 seam=GarmentPhysics.Seam(p0,p1,(right*a.midX+up*a.midY)*d.puppetScale,u);Vector2 pt;
    if(!cloth)pt=GarmentGeometry.RigidPoint(p0,p1,rigidRight,rigidUp,a,d.puppetScale,u,v);
    else pt=p.cloth.Sample(x,y,time)-camera+(seam-(p.cloth.Sample(x,Mathf.Clamp(a.bindRow,0,10),time)-camera))*BindWeight(y,a.bindRow);
    mesh.MoveVertice(x*11+y,pt);
   }
   if(cloth&&index<2&&a.lockGown)WrapGown(mesh,s.sprites[g.robeSprite] as TriangleMesh,index,right,d.puppetScale);
   st.meshes[a.id]=mesh;var material=CreatorAppearance.Texture(a.basePng,d.oracleId+"-"+a.id+"-base");CreatorAppearance.PaintMesh(mesh,material,true);if(material==null)mesh.color=IteratorDesign.C(a.topColor);
   var pattern=CreatorAppearance.Overlay(s,start+index*6+1,mesh,CreatorAppearance.Texture(a.patternPng,d.oracleId+"-"+a.id+"-pattern"),true,false);
   var fringe=Fringes(s,start+index*6+2,p.cloth,p.down,mesh,a,camera,time,d.puppetScale);pattern.isVisible=visible&&pattern.isVisible;fringe.isVisible=visible&&fringe.isVisible;groups[a.id]=new List<FSprite>{mesh,pattern,fringe};
   if(a.mirror){Vector2 center=Position(s.sprites[g.firstBodyChunkSprite]);var mirrored=Clone(s,start+index*6+3,mesh);for(int x=0;x<11;x++)for(int y=0;y<11;y++){int k=x*11+y;Vector2 q=mesh.vertices[k];if(a.type=="cloth"){Vector2 seam=GarmentPhysics.Seam(p.ma-camera,p.mb-camera,(-right*a.midX+up*a.midY)*d.puppetScale,x/10f);q=p.mirrorCloth.Sample(x,y,time)-camera+(seam-(p.mirrorCloth.Sample(x,Mathf.Clamp(a.bindRow,0,10),time)-camera))*BindWeight(y,a.bindRow);}else q-=right*2*Vector2.Dot(q-center,right);mirrored.MoveVertice(k,q);}var mirrorPattern=Clone(s,start+index*6+4,pattern);for(int k=0;k<mirrored.vertices.Length;k++)mirrorPattern.MoveVertice(k,mirrored.vertices[k]);var mirrorFringe=Fringes(s,start+index*6+5,p.mirrorCloth,p.down,mirrored,a,camera,time,d.puppetScale);groups[a.id].Add(mirrored);groups[a.id].Add(mirrorPattern);groups[a.id].Add(mirrorFringe);}
  }
  foreach(var p in st.parts)if(p!=null&&(p.design==null||!done.Contains(p.design.id)))p.ready=false;
  foreach(var group in PearlAccessories.Draw(g,s,CreatorHeadSegments.Start(n)+CreatorHeadSegments.Slots,d,camera,time,up,right,(id,u,v)=>ResolveAnchor(id,u,v,g,s,right,n)))groups[group.Key]=group.Value;
  LayerOrder(g,s,n,d,groups,start);
 }
 // Use final animated gown rows, including its current hem and scale. Never infer
 // the boundary from a bind pose or from the last simulation tick.
 public static void WrapGown(TriangleMesh panel,TriangleMesh gown,int side,Vector2 right,float scale){if(gown==null)return;GownEnvelope.Apply(panel.vertices,gown.vertices,side,right,scale);for(int i=0;i<panel.vertices.Length;i++)panel.MoveVertice(i,panel.vertices[i]);}

 static float BindWeight(int row,int pin){pin=Mathf.Clamp(pin,0,10);return 1-Mathf.Abs(row-pin)/(float)Mathf.Max(pin,10-pin);}
 static TriangleMesh Clone(RoomCamera.SpriteLeaser s,int slot,TriangleMesh source){var m=s.sprites[slot] as TriangleMesh;if(m==null||m.vertices.Length!=source.vertices.Length){var c=s.sprites[slot].container;s.sprites[slot].RemoveFromContainer();m=new TriangleMesh(source.element.name,source.triangles,true);s.sprites[slot]=m;c.AddChild(m);}m.element=source.element;m.color=source.color;m.isVisible=source.isVisible;for(int i=0;i<m.vertices.Length;i++){m.UVvertices[i]=source.UVvertices[i];m.verticeColors[i]=source.verticeColors==null?Color.white:source.verticeColors[i];}return m;}
 static TriangleMesh Fringes(RoomCamera.SpriteLeaser s,int slot,GarmentPhysics cloth,Vector2 down,TriangleMesh panel,GarmentDesign a,Vector2 camera,float time,float scale){var mesh=s.sprites[slot] as TriangleMesh;if(mesh==null||mesh.vertices.Length!=132){var c=s.sprites[slot].container;s.sprites[slot].RemoveFromContainer();var tris=new TriangleMesh.Triangle[66];for(int i=0;i<33;i++){tris[i*2]=new TriangleMesh.Triangle(i*4,i*4+1,i*4+2);tris[i*2+1]=new TriangleMesh.Triangle(i*4+1,i*4+2,i*4+3);}mesh=new TriangleMesh("Futile_White",tris,true);s.sprites[slot]=mesh;c.AddChild(mesh);}mesh.isVisible=panel.isVisible&&a.type=="cloth"&&a.fringe&&a.fringeLength>.01f;mesh.color=Color.white;if(!mesh.isVisible)return mesh;
  for(int x=0;x<11;x++){Vector2 shift=panel.vertices[x*11+10]-(cloth.Sample(x,10,time)-camera);for(int j=0;j<3;j++){Vector2 b0=cloth.Fringe(x,j,time)-camera+shift,b1=cloth.Fringe(x,j+1,time)-camera+shift;if(a.type=="rigid"){float len=a.fringeLength*(.55f+(x*37%13)/20f)*scale;b0=panel.vertices[x*11+10]+down*len*j/3f;b1=panel.vertices[x*11+10]+down*len*(j+1)/3f;}Vector2 normal=new Vector2(-(b1-b0).y,(b1-b0).x).normalized*.3f*scale;int i=(x*3+j)*4;mesh.MoveVertice(i,b0-normal);mesh.MoveVertice(i+1,b0+normal);mesh.MoveVertice(i+2,b1-normal);mesh.MoveVertice(i+3,b1+normal);for(int k=0;k<4;k++)mesh.verticeColors[i+k]=IteratorDesign.C(a.fringeColor);}}
  return mesh;
 }
 static void DrawSleeves(OracleGraphics g,RoomCamera.SpriteLeaser s,int n,IteratorDesign d){for(int side=0;side<2;side++){bool visible=d.layers.sleeves&&(side==0?d.sleeveLeftEnabled:d.sleeveRightEnabled);var mesh=s.sprites[g.HandSprite(side,1)] as TriangleMesh;if(mesh==null)continue;mesh.isVisible=visible;if(d.sleeveMapping!="front"&&!CreatorRuntime.IsAI(g.oracle.room.abstractRoom.name)&&!d.legacySleeveUV&&d.sleeveSymmetry){s.sprites[n+33+side].isVisible=visible&&s.sprites[n+33+side].isVisible;continue;}bool separate=side==1&&!d.sleeveSymmetry;string tex=separate?d.sleeveRBasePng:d.sleeveBasePng;string ink=separate?d.sleeveRPng:d.sleevePng;CreatorAppearance.PaintMesh(mesh,CreatorAppearance.Texture(tex,d.oracleId+"-sleeve-final-"+side),false,side==1&&!separate);CreatorAppearance.Overlay(s,n+33+side,mesh,CreatorAppearance.Texture(ink,d.oracleId+"-sleeve-ink-final-"+side),false,side==1&&!separate);if(d.sleeveMapping=="front"){SleeveMapping.Apply(mesh,side,side==1&&!separate);SleeveMapping.Apply(s.sprites[n+33+side] as TriangleMesh,side,side==1&&!separate);}}}
 static void LayerOrder(OracleGraphics g,RoomCamera.SpriteLeaser s,int n,IteratorDesign d,Dictionary<string,List<FSprite>> groups,int start){
  groups["gown"]=new List<FSprite>{s.sprites[g.robeSprite],s.sprites[n+32]};groups["sleeves"]=new List<FSprite>{s.sprites[g.HandSprite(0,0)],s.sprites[g.HandSprite(0,1)],s.sprites[n+33],s.sprites[g.HandSprite(1,0)],s.sprites[g.HandSprite(1,1)],s.sprites[n+34]};groups["collar"]=new List<FSprite>{s.sprites[n+31],s.sprites[n+35]};groups["head"]=new List<FSprite>{s.sprites[g.HeadSprite],s.sprites[g.ChinSprite],s.sprites[g.EyeSprite(0)],s.sprites[g.EyeSprite(1)],s.sprites[n+8],s.sprites[n+30]};groups["body"]=new List<FSprite>{s.sprites[g.firstBodyChunkSprite],s.sprites[g.firstBodyChunkSprite+1]};
  CreatorArms.AddToGroup(groups["sleeves"],g,s,n);
  groups["neck"]=new List<FSprite>{s.sprites[g.neckSprite]};
  groups["back"]=new List<FSprite>();for(int k=40;k<66;k++)groups["back"].Add(s.sprites[n+k]);
  for(int k=0;k<4;k++)groups["head"].Add(s.sprites[n+k]);for(int k=36;k<=37;k++)groups["head"].Add(s.sprites[n+k]);for(int k=9;k<=10;k++)groups["head"].Add(s.sprites[n+k]);int earStart=n+110+CreatorNecklaces.Slots+IteratorSprites.IntegrationSlots;for(int k=0;k<CreatorHeadphones.Slots;k++)groups["head"].Add(s.sprites[earStart+k]);
  for(int k=0;k<CreatorHeadSegments.Slots;k++)groups["head"].Add(s.sprites[CreatorHeadSegments.Start(n)+k]);
  CreatorEyes.AddToHeadGroup(s,n,groups["head"]);
  groups["legs"]=new List<FSprite>();if(!d.straightLegs)for(int side=0;side<2;side++)for(int k=0;k<2;k++)groups["legs"].Add(s.sprites[g.FootSprite(side,k)]);for(int k=0;k<12;k++)groups["legs"].Add(s.sprites[start+Max*6+k]);
  groups["necklaces"]=new List<FSprite>();for(int k=0;k<CreatorNecklaces.Slots;k++)groups["necklaces"].Add(s.sprites[n+110+k]);
  // Only legacy designs without an explicit layer order retain native ordering.
  // A saved order also applies when the design has hands but no extra garments.
  bool any=false;foreach(var pair in groups)if(pair.Key.StartsWith("front")||pair.Key.StartsWith("shawl")||pair.Key.StartsWith("custom")||pair.Key.StartsWith("pearlAccessory:")){foreach(var sprite in pair.Value)if(sprite.isVisible){any=true;break;}}if(!any&&d.renderOrder.Length==0){PlaceNeck(g,s,d,groups);return;}
  string[] defaults={"back","legs","body","neck","gown","sleeves","collar","shawl1","shawl2","shawl3","shawl4","shawl5","frontL","frontR","necklaces","head"};var order=new List<string>(d.renderOrder.Length==0?defaults:d.renderOrder);foreach(var k in groups.Keys)if(!order.Contains(k))order.Add(k);
  FSprite previous=null;foreach(string id in order){List<FSprite> sprites;if(!groups.TryGetValue(id,out sprites))continue;foreach(var sprite in sprites){if(previous!=null&&sprite!=previous&&sprite.container==previous.container)sprite.MoveInFrontOfOtherNode(previous);previous=sprite;}}
  PlaceNeck(g,s,d,groups);
 }
 // Transform binding and draw order are separate: the neck bridges head/chest,
 // but every front garment must cover it, including after custom layer moves.
 static void PlaceNeck(OracleGraphics g,RoomCamera.SpriteLeaser s,IteratorDesign d,Dictionary<string,List<FSprite>> groups){
  var neck=s.sprites[g.neckSprite];neck.isVisible=d.layers.neck;var container=neck.container;if(container==null)return;
  FSprite first=null;int firstIndex=int.MaxValue;
  // Futile depth is cached until Redraw; use the current sibling order after this frame's moves.
  foreach(var pair in groups){string id=pair.Key;if(id!="gown"&&id!="sleeves"&&id!="collar"&&id!="head"&&!id.StartsWith("front")&&!id.StartsWith("shawl"))continue;
   foreach(var sprite in pair.Value){if(sprite==null||sprite==neck||!sprite.isVisible||sprite.container!=container)continue;int index=container.GetChildIndex(sprite);if(index>=0&&index<firstIndex){first=sprite;firstIndex=index;}}
  }
  if(first!=null)neck.MoveBehindOtherNode(first);
 }
 static void Segment(RoomCamera.SpriteLeaser s,int slot,Vector2 a,Vector2 b,float width,string png,string pattern,string key,bool flip){var m=s.sprites[slot] as TriangleMesh;if(m==null||m.vertices.Length!=4){var c=s.sprites[slot].container;s.sprites[slot].RemoveFromContainer();m=TriangleMesh.MakeLongMesh(1,false,true);s.sprites[slot]=m;c.AddChild(m);}Vector2 v=b-a,normal=new Vector2(-v.y,v.x).normalized*width*.5f;m.MoveVertice(0,a-normal);m.MoveVertice(1,a+normal);m.MoveVertice(2,b-normal);m.MoveVertice(3,b+normal);m.isVisible=true;CreatorAppearance.PaintMesh(m,CreatorAppearance.Texture(png,key),false,flip);CreatorAppearance.Overlay(s,slot+1,m,CreatorAppearance.Texture(pattern,key+"-pattern"),false,flip);}
 static void DrawLegs(OracleGraphics g,RoomCamera.SpriteLeaser s,int start,IteratorDesign d,Vector2 camera,float t,Vector2 up,Vector2 right,State st){
  // Offsets use the animated body's axes and the final sprites, including accessories bound to legs.
  if(!d.straightLegs){for(int side=0;side<2;side++){
   Vector2 offset=right*d.LegShift(side)*d.puppetScale;
   float length=CreatorRuntime.IsAI(g.oracle.room.abstractRoom.name)?1:d.LegLength(side);
   Vector2 pivot=Position(s.sprites[g.firstBodyChunkSprite]);
   for(int k=0;k<2;k++){var foot=s.sprites[g.FootSprite(side,k)];var mesh=foot as TriangleMesh;
    if(mesh!=null)for(int i=0;i<mesh.vertices.Length;i++)mesh.MoveVertice(i,pivot+(mesh.vertices[i]-pivot)*length+offset);
    else {Vector2 point=pivot+(Position(foot)-pivot)*length+offset;foot.x=point.x;foot.y=point.y;}
   }
  }st.legs=false;return;}
  if(!d.layers.feet){st.legs=false;return;}
  for(int side=0;side<2;side++){
   for(int k=0;k<2;k++)s.sprites[g.FootSprite(side,k)].isVisible=false;
   Vector2 hip=Position(s.sprites[g.firstBodyChunkSprite+1])+right*((side==0?-3:3)+d.LegShift(side))*d.puppetScale;
   Vector2 foot=Vector2.Lerp(g.feet[side].lastPos,g.feet[side].pos,t)-camera+right*d.LegShift(side)*d.puppetScale;
   float thigh=d.ThighLength(side)*d.puppetScale,shin=d.ShinLength(side)*d.puppetScale;
   st.hip[side]=hip+camera;st.nativeFoot[side]=foot+camera;st.down=-up;st.legDesign=d;st.legGravity=g.oracle.room.gravity;
   if(!st.legs){Vector2 origin=d.legSymmetry?Position(s.sprites[g.firstBodyChunkSprite+1])+camera+right*(d.LegShift(0)+d.LegShift(1))*.5f*d.puppetScale:st.hip[side];if(side==1&&d.legSymmetry)st.leg[1].FollowParallel(st.leg[0],origin,st.hip[1]);else st.leg[side].Step(origin,-up,st.nativeFoot[side],thigh,shin,d.LegElasticity(side),st.legGravity);}
   // Interpolate directions, then reconstruct the chain from the current hip.
   // Linear interpolation of positions would briefly shorten bones or detach the knee.
   Vector2 thighDirection=st.leg[d.legSymmetry?0:side].ThighDirection(t),shinDirection=st.leg[d.legSymmetry?0:side].ShinDirection(t);
   Vector2 knee=hip+thighDirection*thigh,ankle=knee+shinDirection*shin;
   float width=d.LegWidth(side)*d.puppetScale,kneeWidth=d.KneeSize(side)*d.puppetScale;bool separate=d.SeparateLeg(side),flip=side==1&&!separate;
   Segment(s,start+side*6,hip,knee,width,separate?d.legThighRBasePng:d.legThighBasePng,separate?d.legThighRPng:d.legThighPng,d.oracleId+"-thigh-"+side,flip);
   Segment(s,start+side*6+2,knee+up*kneeWidth*.5f,knee-up*kneeWidth*.5f,kneeWidth,separate?d.legKneeRBasePng:d.legKneeBasePng,separate?d.legKneeRPng:d.legKneePng,d.oracleId+"-knee-"+side,flip);
   Segment(s,start+side*6+4,knee,ankle,width,separate?d.legShinRBasePng:d.legShinBasePng,separate?d.legShinRPng:d.legShinPng,d.oracleId+"-shin-"+side,flip);
   for(int k=0;k<6;k++)s.sprites[start+side*6+k].MoveBehindOtherNode(s.sprites[g.robeSprite]);
  }st.legs=true;
 }
}
}
