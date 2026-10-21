namespace MoreIterators {
using UnityEngine;

// Preserve the original arm's wide shadow mesh and narrow lit mesh.
public static class CreatorArmAppearance {
 public static Color Shadow(Color body,float strength){float value=1f-.7f*Mathf.Clamp01(strength);return new Color(body.r*value,body.g*value,body.b*value,body.a);}
 static void Paint(RoomCamera.SpriteLeaser s,int index,Color color){
  var sprite=s.sprites[index];sprite.color=color;
  var mesh=sprite as TriangleMesh;
  if(mesh!=null&&mesh.verticeColors!=null)for(int i=0;i<mesh.verticeColors.Length;i++)mesh.verticeColors[i]=color;
  if(mesh!=null)mesh.Refresh();
 }
 public static void Apply(OracleGraphics g,RoomCamera.SpriteLeaser s,IteratorDesign d){
  Color body=IteratorDesign.C(d.armColor),shadow=Shadow(body,d.armShadowStrength),joint=IteratorDesign.C(d.armJointColor);
  int index=0,total=g.armJointGraphics==null?1:g.armJointGraphics.Length;
  if(g.armJointGraphics!=null)foreach(var arm in g.armJointGraphics){
   for(int i=0;i<arm.totalSprites;i++)s.sprites[arm.firstSprite+i].isVisible=d.layers.mechanicalArm;
   for(int i=0;i<3;i++)Paint(s,arm.CogSprite(i),joint);
   for(int i=0;i<4;i++)Paint(s,arm.MetalPartSprite(i),shadow);
   for(int i=0;i<2;i++){
    Paint(s,arm.SegmentSprite(i,0),shadow);Paint(s,arm.SegmentSprite(i,1),body);
    float start=(index+i*.5f)/Mathf.Max(1,total),end=(index+(i+1)*.5f)/Mathf.Max(1,total);
    CreatorColorGradient.Paint(s.sprites[arm.SegmentSprite(i,0)],d.armGradient,body,start,end,1-.7f*Mathf.Clamp01(d.armShadowStrength));
    CreatorColorGradient.Paint(s.sprites[arm.SegmentSprite(i,1)],d.armGradient,body,start,end,1);
    Paint(s,arm.JointSprite(i,0),joint);Paint(s,arm.JointSprite(i,1),Color.Lerp(joint,body,.65f));
   }
   index++;
  }
  if(g.armBase==null)return;var b=g.armBase;
  for(int i=0;i<b.totalSprites;i++)s.sprites[b.firstSprite+i].isVisible=d.layers.mechanicalArm;
  for(int i=0;i<2;i++){
   for(int p=0;p<3;p++)Paint(s,b.SupportSprite(i,p),shadow);
   Paint(s,b.CircleSprite(i,0),shadow);Paint(s,b.CircleSprite(i,1),body);
  }
  Paint(s,b.firstSprite+6,shadow);Paint(s,b.firstSprite+7,body);Paint(s,b.firstSprite+8,shadow);
 }
}
}
