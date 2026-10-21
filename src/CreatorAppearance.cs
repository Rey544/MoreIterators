namespace MoreIterators {
using System;
using System.Collections.Generic;
using UnityEngine;

public static class CreatorAppearance {
 class Cached {public string data,key,failed;}
 static readonly Dictionary<string,Cached> textures=new Dictionary<string,Cached>();
 static int serial;
 sealed class NativeScale {public NativeScale(){} public float x,y;}
 static readonly System.Runtime.CompilerServices.ConditionalWeakTable<FSprite,NativeScale> nativeScales=new System.Runtime.CompilerServices.ConditionalWeakTable<FSprite,NativeScale>();
 public static void BeforeDraw(RoomCamera.SpriteLeaser s){foreach(var sprite in s.sprites){NativeScale saved;if(sprite!=null&&nativeScales.TryGetValue(sprite,out saved)){sprite.scaleX=saved.x;sprite.scaleY=saved.y;}}}
 public static FAtlasElement Texture(string png,string slot){
  if(String.IsNullOrEmpty(png))return null;
  if(!MiDiagnostics.Require(!String.IsNullOrEmpty(slot),"MI-TEXTURE-SLOT","CreatorAppearance.Texture","Texture slot is missing.","Texture not applied."))return null;
  Cached c;
  if(!textures.TryGetValue(slot,out c)){c=new Cached();textures[slot]=c;}
  if(c.data!=png&&c.failed!=png){
   Texture2D texture=null;
   string key="mi_creator_"+(++serial);
   try{
    texture=new Texture2D(2,2,TextureFormat.ARGB32,false);
    texture.filterMode=FilterMode.Point;
    texture.wrapMode=TextureWrapMode.Clamp;
    if(!ImageConversion.LoadImage(texture,Convert.FromBase64String(png.Substring(png.IndexOf(',')+1))))throw new FormatException("Invalid PNG");
    Futile.atlasManager.LoadAtlasFromTexture(key,texture,false);
    // Commit only after decode and registration both succeed.
    var element=Futile.atlasManager.GetElementWithName(key);
    string old=c.key;
    c.key=key;c.data=png;c.failed=null;
    if(old!=null)try{Futile.atlasManager.UnloadAtlas(old);}catch(Exception error){MiDiagnostics.Report("MI-TEXTURE-RELEASE","CreatorAppearance.Texture",error,slot);}
    return element;
   }catch(Exception error){
    c.failed=png;
    try{
     if(Futile.atlasManager.DoesContainAtlas(key))Futile.atlasManager.UnloadAtlas(key);
     else if(texture!=null)UnityEngine.Object.Destroy(texture);
    }catch(Exception cleanup){MiDiagnostics.Report("MI-TEXTURE-ROLLBACK","CreatorAppearance.Texture",cleanup,slot);}
    MiDiagnostics.Report("MI-TEXTURE-READ","CreatorAppearance.Texture",error,slot+"; previous valid texture retained.");
   }
  }
  return c.key==null?null:Futile.atlasManager.GetElementWithName(c.key);
 }
 public static void PaintMesh(TriangleMesh mesh,FAtlasElement e,bool grid,bool flipU=false){if(mesh==null)return;bool painted=e!=null;if(e==null)e=Futile.atlasManager.GetElementWithName("Futile_White");mesh.element=e;if(painted)mesh.color=Color.white;int n=(int)Mathf.Sqrt(mesh.vertices.Length);for(int i=0;i<mesh.vertices.Length;i++){float u=grid?(i/n)/(float)(n-1):(i%2),v=grid?1-(i%n)/(float)(n-1):1-(i/2)/(float)(mesh.vertices.Length/2-1);if(flipU)u=1-u;mesh.UVvertices[i]=new Vector2(Mathf.Lerp(e.uvBottomLeft.x,e.uvTopRight.x,u),Mathf.Lerp(e.uvBottomLeft.y,e.uvTopRight.y,v));if(painted&&mesh.verticeColors!=null)mesh.verticeColors[i]=Color.white;}}
 public static TriangleMesh Overlay(RoomCamera.SpriteLeaser s,int slot,TriangleMesh baseMesh,FAtlasElement texture,bool grid,bool flipU){
  if(baseMesh==null)return null;
  var mesh=s.sprites[slot] as TriangleMesh;
  if(mesh==null||mesh.vertices.Length!=baseMesh.vertices.Length){var container=s.sprites[slot].container;s.sprites[slot].RemoveFromContainer();mesh=new TriangleMesh("Futile_White",baseMesh.triangles,true);s.sprites[slot]=mesh;container.AddChild(mesh);}
  mesh.isVisible=baseMesh.isVisible&&texture!=null;
  for(int i=0;i<baseMesh.vertices.Length;i++)mesh.MoveVertice(i,baseMesh.vertices[i]);
  PaintMesh(mesh,texture,grid,flipU);mesh.MoveInFrontOfOtherNode(baseMesh);return mesh;
 }
 static void Image(FSprite sprite,FAtlasElement e,Vector2 pos,float w,float h,float rot,bool visible){sprite.isVisible=visible&&e!=null;if(!sprite.isVisible)return;sprite.element=e;sprite.x=pos.x;sprite.y=pos.y;sprite.scaleX=w/e.sourceSize.x;sprite.scaleY=h/e.sourceSize.y;sprite.rotation=rot;sprite.color=Color.white;sprite.alpha=1;}
 static void Transform(FSprite s,Vector2 pivot,Vector2 up,Vector2 right,float scale,float torso){
  var mesh=s as TriangleMesh;if(mesh!=null){for(int i=0;i<mesh.vertices.Length;i++)mesh.MoveVertice(i,Map(mesh.vertices[i],pivot,up,right,scale,torso));}else{var p=Map(new Vector2(s.x,s.y),pivot,up,right,scale,torso);s.x=p.x;s.y=p.y;NativeScale saved=nativeScales.GetOrCreateValue(s);saved.x=s.scaleX;saved.y=s.scaleY;s.scaleX*=scale;s.scaleY*=scale;}
 }
 static Vector2 Map(Vector2 v,Vector2 pivot,Vector2 up,Vector2 right,float scale,float torso){Vector2 q=v-pivot;float y=Vector2.Dot(q,up);return pivot+(right*Vector2.Dot(q,right)+up*(y< -7?-7+(y+7)*torso:y))*scale;}
 static void Translate(FSprite sprite,Vector2 offset){var mesh=sprite as TriangleMesh;if(mesh!=null){for(int i=0;i<mesh.vertices.Length;i++)mesh.MoveVertice(i,mesh.vertices[i]+offset);}else{sprite.x+=offset.x;sprite.y+=offset.y;}}
 public static void Draw(OracleGraphics g,RoomCamera.SpriteLeaser s,int n,IteratorDesign d,Vector2 chest,Vector2 head,Vector2 up,Vector2 right,Vector2 camera,float timeStacker){
  for(int i=12;i<110;i++)s.sprites[n+i].isVisible=false;s.sprites[n+6].isVisible=s.sprites[n+7].isVisible=false;
  float rotation=Mathf.Atan2(up.x,up.y)*Mathf.Rad2Deg;
  for(int side=0;side<2;side++){
   var ear=s.sprites[n+2+side];ear.x+=right.x*(side==0?-d.earOffsetX:d.earOffsetX)+up.x*d.earOffsetY;ear.y+=right.y*(side==0?-d.earOffsetX:d.earOffsetX)+up.y*d.earOffsetY;
   string png=side==0?d.antennaLeftPng:d.antennaRightPng,innerPng=side==0?d.antennaLeftInnerPng:d.antennaRightInnerPng;
   var e=Texture(png,d.oracleId+"-antenna"+side);var inner=Texture(innerPng,d.oracleId+"-antenna-inner"+side);
   Vector2 antennaCenter=head+right*(side==0?-d.antennaSpread:d.antennaSpread)+up*(2+d.antennaHeight*.5f+d.antennaOffsetY);
   Image(s.sprites[n+36+side],inner,antennaCenter,d.antennaWidth*4,d.antennaHeight+4,rotation,d.layers.antenna);
   Image(s.sprites[n+9+side],e,antennaCenter,d.antennaWidth*4,d.antennaHeight+4,rotation,d.layers.antenna);
   s.sprites[n+36+side].MoveBehindOtherNode(s.sprites[n+9+side]);
   if(e!=null||inner!=null)s.sprites[n+side].isVisible=false;
   else{var mesh=s.sprites[n+side] as TriangleMesh;if(mesh!=null)for(int j=0;j<mesh.vertices.Length;j++)mesh.MoveVertice(j,mesh.vertices[j]+up*d.antennaOffsetY);}
   var sleeve=s.sprites[g.HandSprite(side,1)] as TriangleMesh;Vector2 shoulder=chest+right*(side==0?-4:4);if(sleeve!=null){for(int i=0;i<sleeve.vertices.Length;i++)sleeve.MoveVertice(i,shoulder+(sleeve.vertices[i]-shoulder)*d.armLength);PaintMesh(sleeve,Texture(d.sleeveBasePng,d.oracleId+"-sleeve-base"),false,side==1);Overlay(s,n+33+side,sleeve,Texture(d.sleevePng,d.oracleId+"-sleeve"),false,side==1);}
   var hand=s.sprites[g.HandSprite(side,0)];var hp=shoulder+(new Vector2(hand.x,hand.y)-shoulder)*d.armLength;hand.x=hp.x;hand.y=hp.y;
   for(int k=0;k<2;k++){var foot=s.sprites[g.FootSprite(side,k)];var mesh=foot as TriangleMesh;if(mesh!=null)for(int i=0;i<mesh.vertices.Length;i++)mesh.MoveVertice(i,chest+(mesh.vertices[i]-chest)*d.LegLength(side));else{foot.x=chest.x+(foot.x-chest.x)*d.LegLength(side);foot.y=chest.y+(foot.y-chest.y)*d.LegLength(side);}}
  }
  var gown=s.sprites[g.robeSprite] as TriangleMesh;PaintMesh(gown,Texture(d.gownBasePng,d.oracleId+"-gown-base"),true,true);
  if(gown!=null){string[] profile=d.hemProfile.Split(',');int grid=(int)Mathf.Sqrt(gown.vertices.Length);for(int x=0;x<grid;x++){float f;if(x<profile.Length&&float.TryParse(profile[x],System.Globalization.NumberStyles.Float,System.Globalization.CultureInfo.InvariantCulture,out f)){for(int y=1;y<grid;y++){int k=x*grid+y;Vector2 a=gown.vertices[x*grid];float t=y/(float)(grid-1);gown.MoveVertice(k,gown.vertices[k]+(gown.vertices[k]-a)*(Mathf.Clamp(f,.6f,1.4f)-1)*t*t);}}}}
  s.sprites[n+4].isVisible=s.sprites[n+5].isVisible=false;
  Image(s.sprites[n+8],Texture(d.facePng,d.oracleId+"-forehead"),head+right*d.faceOffsetX+up*d.faceOffsetY,24*d.faceScale,24*d.faceScale,rotation,d.layers.face);
  Image(s.sprites[n+30],Texture(d.cheekPng,d.oracleId+"-cheek"),head+right*d.cheekOffsetX+up*d.cheekOffsetY,24*d.cheekScale,24*d.cheekScale,rotation,d.layers.face);s.sprites[n+8].MoveInFrontOfOtherNode(s.sprites[g.HeadSprite]);s.sprites[n+30].MoveInFrontOfOtherNode(s.sprites[n+8]);
  Overlay(s,n+32,gown,Texture(d.gownPng,d.oracleId+"-gown"),true,true);
  const int collarSegments=12;
  var collar=s.sprites[n+31] as TriangleMesh;if(collar==null||collar.vertices.Length!=169){var container=s.sprites[n+31].container;s.sprites[n+31].RemoveFromContainer();collar=TriangleMesh.MakeGridMesh("Futile_White",collarSegments);s.sprites[n+31]=collar;container.AddChild(collar);}collar.isVisible=d.layers.collar&&d.collarHeight>.01f;
  if(gown!=null){
   int grid=(int)Mathf.Sqrt(gown.vertices.Length);Vector2 a=gown.vertices[0],b=gown.vertices[(grid-1)*grid];
   Vector2 left=Vector2.Dot(a-b,right)<0?a:b,r=Vector2.Dot(a-b,right)<0?b:a,mid=(left+r)*.5f;
   for(int x=0;x<=collarSegments;x++)for(int y=0;y<=collarSegments;y++){
    float u=x/(float)collarSegments,v=y/(float)collarSegments;
    float shape=Mathf.Lerp(1-Mathf.Abs(2*u-1),Mathf.Sin(Mathf.PI*u)*Mathf.Sin(Mathf.PI*u),d.collarRoundness);
    float lower=d.collarNotch*shape,upper=Mathf.Max(lower+.1f,d.collarHeight-d.collarTopNotch*shape);
    float rounding=1-d.collarRoundness*.12f*(1-Mathf.Sqrt(Mathf.Max(0,1-(2*v-1)*(2*v-1))));
    Vector2 edge=Vector2.Lerp(left,r,u);edge=mid+(edge-mid)*d.collarWidth*Mathf.Lerp(d.collarTaper,1,v)*rounding;
    collar.MoveVertice(x*(collarSegments+1)+y,edge+up*(d.collarOffsetY+Mathf.Lerp(upper,lower,v)));
   }
   var collarBase=Texture(d.collarBasePng,d.oracleId+"-collar-base");PaintMesh(collar,collarBase,true);collar.color=collarBase==null?IteratorDesign.C(d.collarColor):Color.white;
   // Collar wraps above the robe and sleeves; head and chin cover its upper rim.
   s.sprites[g.neckSprite].MoveBehindOtherNode(gown);
   collar.MoveInFrontOfOtherNode(s.sprites[n+34]);
   s.sprites[g.HeadSprite].MoveInFrontOfOtherNode(collar);s.sprites[g.ChinSprite].MoveInFrontOfOtherNode(s.sprites[g.HeadSprite]);
   Overlay(s,n+35,collar,Texture(d.collarPng,d.oracleId+"-collar"),true,false);
   for(int side=0;side<2;side++)s.sprites[g.EyeSprite(side)].MoveInFrontOfOtherNode(s.sprites[g.ChinSprite]);
   s.sprites[n+8].MoveInFrontOfOtherNode(s.sprites[g.EyeSprite(1)]);s.sprites[n+30].MoveInFrontOfOtherNode(s.sprites[n+8]);
  }
  var chosen=new HashSet<int>();chosen.Add(g.HeadSprite);chosen.Add(g.ChinSprite);chosen.Add(g.neckSprite);chosen.Add(g.robeSprite);for(int i=0;i<g.oracle.bodyChunks.Length;i++)chosen.Add(g.firstBodyChunkSprite+i);for(int side=0;side<2;side++){chosen.Add(g.EyeSprite(side));chosen.Add(g.HandSprite(side,0));chosen.Add(g.HandSprite(side,1));for(int k=0;k<2;k++)chosen.Add(g.FootSprite(side,k));}for(int i=0;i<=10;i++)chosen.Add(n+i);chosen.Add(n+30);chosen.Add(n+31);
  for(int i=32;i<=37;i++)chosen.Add(n+i);
  var bodyParts=new HashSet<int>();bodyParts.Add(g.robeSprite);
  if(g.IsPastMoon){
   chosen.Add(g.MoonThirdEyeSprite);chosen.Add(g.MoonSigilSprite);
   s.sprites[g.MoonThirdEyeSprite].isVisible=d.layers.head&&d.layers.face&&String.IsNullOrEmpty(d.facePng);
   s.sprites[g.MoonSigilSprite].isVisible=d.layers.head&&d.layers.face&&d.layers.halo;
   s.sprites[g.MoonThirdEyeSprite].MoveInFrontOfOtherNode(s.sprites[g.ChinSprite]);
   s.sprites[g.MoonSigilSprite].MoveInFrontOfOtherNode(s.sprites[g.MoonThirdEyeSprite]);
  }
  for(int i=0;i<g.oracle.bodyChunks.Length;i++)bodyParts.Add(g.firstBodyChunkSprite+i);
  for(int side=0;side<2;side++){for(int k=0;k<2;k++){bodyParts.Add(g.HandSprite(side,k));bodyParts.Add(g.FootSprite(side,k));}}
  for(int i=31;i<=35;i++)bodyParts.Add(n+i);
  // The body, sleeves, collar and all garment overlays move together. Keep the
  // head/face/antenna and head cable anchors fixed; never shorten the neck sprite alone.
  Vector2 neckOffset=up*(2-Mathf.Clamp(d.neckLength,0,8))*d.puppetScale;
  foreach(int i in chosen){Transform(s.sprites[i],head,up,right,d.puppetScale,d.torsoLength);if(bodyParts.Contains(i))Translate(s.sprites[i],neckOffset);}
  // Bind both ends after the nonuniform body transform. The short legacy neck
  // cannot bridge a stretched torso; overlap the head and chest beneath clothing.
  var neck=s.sprites[g.neckSprite];
  Vector2 neckBase=Map(chest,head,up,right,d.puppetScale,d.torsoLength)+neckOffset;
  Vector2 neckTip=Map(head,head,up,right,d.puppetScale,d.torsoLength),neckAxis=neckTip-neckBase;
  neck.SetPosition(neckBase);neck.anchorY=0;neck.rotation=Mathf.Atan2(neckAxis.x,neckAxis.y)*Mathf.Rad2Deg;
  neck.scaleX=3*d.puppetScale;neck.scaleY=neckAxis.magnitude;
  CreatorScarf.Draw(g,s,n,d,camera,timeStacker,right);
  CreatorNecklaces.Draw(g,s,n+110,d,camera,timeStacker,up,right);
  if(!CreatorRuntime.RearGlow)s.sprites[g.fadeSprite].isVisible=false;else s.sprites[g.fadeSprite].isVisible=true;
 }
}
}
