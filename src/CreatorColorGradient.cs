using System;
using UnityEngine;

namespace MoreIterators {
 [Serializable] public sealed class GradientStop {
  public float position;public string color="#ffffff";
 }
 [Serializable] public sealed class ColorGradient {
  public bool enabled;public GradientStop[] stops=new GradientStop[0];
  public Color Sample(float f,Color solid){
   if(!enabled||stops==null||stops.Length==0)return solid;
   f=Mathf.Clamp01(f);GradientStop before=null,after=null;
   for(int i=0;i<Math.Min(5,stops.Length);i++){
    var stop=stops[i];if(stop==null)continue;
    if(stop.position<=f&&(before==null||stop.position>before.position))before=stop;
    if(stop.position>=f&&(after==null||stop.position<after.position))after=stop;
   }
   if(before==null&&after==null)return solid;
   if(before==null)return IteratorDesign.C(after.color);
   if(after==null)return IteratorDesign.C(before.color);
   float span=after.position-before.position;
   return Color.Lerp(IteratorDesign.C(before.color),IteratorDesign.C(after.color),span<.00001f?0:(f-before.position)/span);
  }
 }
 [Serializable] public sealed class RoomGradient {
  public bool enabled;public string direction="radial",renderMode="lighting";public float opacity=.18f;
  public ColorGradient ramp=new ColorGradient();
  public CornerGlow[] corners=new CornerGlow[0];
  public Color BaseSample(float x,float y){
   float f=direction=="horizontal"?x:direction=="vertical"?y:Mathf.Clamp01(new Vector2((x-.5f)*2,(y-.5f)*2).magnitude);
   Color result=ramp==null?Color.white:ramp.Sample(f,Color.white);result.a=enabled?Mathf.Clamp01(opacity):0;
   return result;
  }
  public static Color NativeLight(Color color){float peak=Mathf.Max(color.r,Mathf.Max(color.g,color.b));return peak<=0?new Color(0,0,0,0):new Color(color.r/peak,color.g/peak,color.b/peak,color.a*peak);}
  public Color Sample(float x,float y){
   Color result=BaseSample(x,y);
   if(corners==null)return result;
   for(int i=0;i<Math.Min(4,corners.Length);i++){
    var corner=corners[i];if(corner==null||!corner.enabled)continue;
    float cx=i%2,cy=i/2;float radius=Mathf.Max(.05f,corner.radius);
    float weight=Mathf.Clamp01(corner.opacity)*Mathf.Exp(-((x-cx)*(x-cx)+(y-cy)*(y-cy))/(radius*radius));
    float alpha=result.a+weight*(1-result.a);Color c=IteratorDesign.C(corner.color);
    if(alpha>0){result.r=(result.r*result.a*(1-weight)+c.r*weight)/alpha;result.g=(result.g*result.a*(1-weight)+c.g*weight)/alpha;result.b=(result.b*result.a*(1-weight)+c.b*weight)/alpha;}result.a=alpha;
   }
   return result;
  }
 }
 [Serializable] public sealed class CornerGlow {
  public bool enabled;public string color="#ffffff";public float opacity=.18f,radius=.5f;
 }
 public static class CreatorColorGradient {
  public static void Paint(FSprite sprite,ColorGradient gradient,Color solid,float start,float end,float shade){
   if(sprite==null||gradient==null||!gradient.enabled)return;
   var mesh=sprite as TriangleMesh;
   if(mesh==null){Color color=gradient.Sample((start+end)*.5f,solid);sprite.color=new Color(color.r*shade,color.g*shade,color.b*shade,color.a);return;}
   if(mesh.vertices==null||mesh.vertices.Length==0)return;
   // Native FP cords and arm segments use customColor=false. Enable the existing
   // mesh's public vertex-colour path; geometry, UVs, shader and layer stay intact.
   if(mesh.verticeColors==null||mesh.verticeColors.Length!=mesh.vertices.Length)mesh.verticeColors=new Color[mesh.vertices.Length];
   float opacity=mesh.alpha;mesh.customColor=true;
   sprite.color=Color.white;
   // Native cord and support meshes store pairs of vertices in length order.
   int rows=Math.Max(1,(mesh.verticeColors.Length+1)/2-1);
   for(int i=0;i<mesh.verticeColors.Length;i++){Color c=gradient.Sample(Mathf.Lerp(start,end,(i/2)/(float)rows),solid);mesh.verticeColors[i]=new Color(c.r*shade,c.g*shade,c.b*shade,c.a*opacity);}mesh.Refresh();
  }
 }
}

