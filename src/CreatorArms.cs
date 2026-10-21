namespace MoreIterators {
using System;
using System.Collections.Generic;
using System.Runtime.CompilerServices;
using UnityEngine;

// Puppet hands and their sleeves. The mechanical arm (ArmJointGraphics) is untouched.
public static class CreatorArms {
 public const int Slots=6;
 public static int Start(int n){return CreatorHeadSegments.Start(n)+CreatorHeadSegments.Slots+PearlAccessories.Slots+CreatorEyes.Slots;}
 sealed class NativeHand {public NativeHand(){} public FAtlasElement element;public float sx,sy,rotation,ax,ay,alpha;}
 static readonly ConditionalWeakTable<FSprite,NativeHand> originals=new ConditionalWeakTable<FSprite,NativeHand>();
 public static void BeforeDraw(OracleGraphics g,RoomCamera.SpriteLeaser s){for(int side=0;side<2;side++){int slot=g.HandSprite(side,0);if(slot<0||slot>=s.sprites.Length)continue;var hand=s.sprites[slot];NativeHand native;if(hand!=null&&originals.TryGetValue(hand,out native)){hand.element=native.element;hand.scaleX=native.sx;hand.scaleY=native.sy;hand.rotation=native.rotation;hand.anchorX=native.ax;hand.anchorY=native.ay;hand.alpha=native.alpha;}}}
 public static bool Mirror(IteratorDesign d,int index){return index%2==1&&(index<2?d.puppetArmSymmetry:d.puppetExtraArmSymmetry);}
 public static bool SleeveMirror(IteratorDesign d,int index){return index%2==1&&(d.puppetSleeveSyncSeparated?(index<2?d.sleeveSymmetry:d.puppetExtraSleeveSymmetry):(index<2?d.puppetArmSymmetry:d.puppetExtraArmSymmetry));}
 public static PuppetArmDesign Raw(IteratorDesign d,int index){return d.puppetArms!=null&&index<d.puppetArms.Length&&d.puppetArms[index]!=null?d.puppetArms[index]:PuppetArmDesign.Default(index);}
 public static PuppetArmDesign Config(IteratorDesign d,int index){return Raw(d,Mirror(d,index)?index-1:index);}
 public static PuppetArmDesign SleeveConfig(IteratorDesign d,int index){return Raw(d,SleeveMirror(d,index)?index-1:index);}
 static bool Neutral(PuppetArmDesign a,PuppetArmDesign sleeve){return !a.handOwnColor&&!a.handTextureEnabled&&!sleeve.sleeveOwnColor&&sleeve.sleeveTextureEnabled&&a.lengthScale==1&&sleeve.widthScale==1&&a.handSize==1&&a.shoulderX==0&&a.shoulderY==0&&sleeve.sleeveRootX==0&&sleeve.sleeveRootY==0;}
 sealed class Pose {public Vector2 hand,root;public FAtlasElement element;public float sx,sy,rotation,ax,ay,alpha;public Color color;public TriangleMesh sleeve;public Vector2[] vertices;}
 static Pose Capture(FSprite hand,TriangleMesh sleeve){return new Pose{hand=new Vector2(hand.x,hand.y),root=(sleeve.vertices[2]+sleeve.vertices[3])*.5f,element=hand.element,sx=hand.scaleX,sy=hand.scaleY,rotation=hand.rotation,ax=hand.anchorX,ay=hand.anchorY,alpha=hand.alpha,color=hand.color,sleeve=sleeve,vertices=(Vector2[])sleeve.vertices.Clone()};}
 static TriangleMesh CopyMesh(RoomCamera.SpriteLeaser s,int slot,TriangleMesh source){var mesh=s.sprites[slot] as TriangleMesh;if(mesh==null||mesh.vertices.Length!=source.vertices.Length){var container=s.sprites[slot].container;s.sprites[slot].RemoveFromContainer();mesh=new TriangleMesh(source.element.name,source.triangles,true);s.sprites[slot]=mesh;container.AddChild(mesh);}mesh.element=source.element;mesh.shader=source.shader;mesh.color=source.color;mesh.alpha=source.alpha;for(int v=0;v<mesh.vertices.Length;v++){mesh.UVvertices[v]=source.UVvertices[v];mesh.verticeColors[v]=source.verticeColors==null?Color.white:source.verticeColors[v];}return mesh;}
 public static void Draw(OracleGraphics g,RoomCamera.SpriteLeaser s,int n,IteratorDesign d,Vector2 up,Vector2 right){
  int start=Start(n);for(int i=0;i<Slots;i++)s.sprites[start+i].isVisible=false;
  var poses=new Pose[2];for(int side=0;side<2;side++){var hand=s.sprites[g.HandSprite(side,0)];var sleeve=s.sprites[g.HandSprite(side,1)] as TriangleMesh;if(sleeve==null)return;var native=originals.GetOrCreateValue(hand);native.element=hand.element;native.sx=hand.scaleX;native.sy=hand.scaleY;native.rotation=hand.rotation;native.ax=hand.anchorX;native.ay=hand.anchorY;native.alpha=hand.alpha;poses[side]=Capture(hand,sleeve);}
  // Build extra limbs first, so changing/hiding a main hand never becomes the extra pair's source.
  for(int order=0;order<4;order++){
   int index=(order+2)%4,side=index%2;bool extra=index>=2,mirror=Mirror(d,index),sleeveMirror=SleeveMirror(d,index);var own=Raw(d,index);var a=Config(d,index);var sl=SleeveConfig(d,index);var pose=poses[side];
   if(extra&&!own.enabled)continue;if(!extra&&own.enabled&&own.sleeveEnabled&&Neutral(a,sl))continue;
   int handSlot=extra?start+side*3:g.HandSprite(side,0),sleeveSlot=extra?handSlot+1:g.HandSprite(side,1),inkSlot=extra?handSlot+2:n+33+side;
   var hand=s.sprites[handSlot];var sleeve=extra?CopyMesh(s,sleeveSlot,pose.sleeve):pose.sleeve;
   Vector2 shift=(right*(mirror?-a.shoulderX:a.shoulderX)+up*a.shoulderY)*d.puppetScale;
   Vector2 seam=(right*(sleeveMirror?-sl.sleeveRootX:sl.sleeveRootX)+up*sl.sleeveRootY)*d.puppetScale;
   hand.element=pose.element;hand.scaleX=pose.sx*a.handSize;hand.scaleY=pose.sy*a.handSize;hand.rotation=pose.rotation;hand.anchorX=pose.ax;hand.anchorY=pose.ay;hand.color=a.handOwnColor?IteratorDesign.C(a.handColor):pose.color;hand.alpha=pose.alpha;
   Vector2 hp=PuppetArmGeometry.Point(pose.hand,pose.root,shift,a.lengthScale);hand.x=hp.x;hand.y=hp.y;hand.isVisible=own.enabled&&d.layers.hands;
   if(a.handTextureEnabled){var texture=CreatorAppearance.Texture(a.handPng,d.oracleId+"-puppet-hand-"+(mirror?index-1:index));if(texture!=null){hand.element=texture;hand.scaleX=(mirror?-1:1)*6*d.puppetScale*a.handSize/texture.sourceSize.x;hand.scaleY=6*d.puppetScale*a.handSize/texture.sourceSize.y;hand.anchorX=hand.anchorY=.5f;hand.rotation=Mathf.Atan2(up.x,up.y)*Mathf.Rad2Deg;hand.color=a.handTextureTint?(a.handOwnColor?IteratorDesign.C(a.handColor):pose.color):Color.white;}}
   for(int v=0;v<pose.vertices.Length;v+=2){Vector2 center=(pose.vertices[v]+pose.vertices[v+1])*.5f;float t=(v/4)/(float)(pose.vertices.Length/4-1);for(int k=0;k<2;k++){Vector2 point=center+(pose.vertices[v+k]-center)*sl.widthScale;sleeve.MoveVertice(v+k,PuppetArmGeometry.SleevePoint(point,pose.root,shift,seam,a.lengthScale,t));}}
   bool legacySide=side==0?d.sleeveLeftEnabled:d.sleeveRightEnabled;sleeve.isVisible=own.enabled&&own.sleeveEnabled&&d.layers.sleeves&&(extra||legacySide);
   // An extra synchronized right sleeve inherits the left sleeve's material even
   // when the original right sleeve has an independent texture.
   bool ownTexture=extra&&sl.sleeveOwnTexture;
   bool inheritRight=side==1&&!(d.puppetSleeveSyncSeparated?sleeveMirror:mirror)&&!d.sleeveSymmetry;
   string ink=ownTexture?sl.sleevePng:inheritRight?d.sleeveRPng:d.sleevePng;
   string basePng=ownTexture?sl.sleeveBasePng:inheritRight?d.sleeveRBasePng:d.sleeveBasePng;
   bool flip=ownTexture?sleeveMirror:side==1&&!inheritRight;
   if(!sl.sleeveTextureEnabled){CreatorAppearance.PaintMesh(sleeve,null,false);for(int v=0;v<sleeve.vertices.Length;v++)sleeve.verticeColors[v]=sl.sleeveOwnColor?IteratorDesign.C(sl.sleeveColor):d.Cloth((v/4)/(float)(sleeve.vertices.Length/4-1)*.65f);sleeve.color=Color.white;ink="";}
   else{CreatorAppearance.PaintMesh(sleeve,CreatorAppearance.Texture(basePng,d.oracleId+"-puppet-sleeve-"+index),false,flip);}
   if(sl.sleeveOwnColor)Tint(sleeve,IteratorDesign.C(sl.sleeveColor));
   var overlay=CreatorAppearance.Overlay(s,inkSlot,sleeve,CreatorAppearance.Texture(ink,d.oracleId+"-puppet-sleeve-ink-"+index),false,flip);
   if(sl.sleeveOwnColor&&overlay!=null)Tint(overlay,IteratorDesign.C(sl.sleeveColor));
   if(d.sleeveMapping=="front"){SleeveMapping.Apply(sleeve,side,flip);SleeveMapping.Apply(overlay,side,flip);}
   // Match the native cuff: hand behind sleeve and painted sleeve overlay.
   // Both extra arms stay behind the original pair, as in the studio preview.
   if(extra){sleeve.MoveBehindOtherNode(s.sprites[g.HandSprite(0,0)]);overlay.MoveInFrontOfOtherNode(sleeve);hand.MoveBehindOtherNode(sleeve);}
  }
 }
 static void Tint(TriangleMesh mesh,Color color){mesh.color=Color.white;if(mesh.verticeColors!=null)for(int v=0;v<mesh.verticeColors.Length;v++)mesh.verticeColors[v]=color;}
 public static void AddToGroup(List<FSprite> group,OracleGraphics g,RoomCamera.SpriteLeaser s,int n){var extra=new List<FSprite>();for(int side=0;side<2;side++){int slot=Start(n)+side*3;extra.Add(s.sprites[slot]);extra.Add(s.sprites[slot+1]);extra.Add(s.sprites[slot+2]);}group.InsertRange(0,extra);}
}
}

