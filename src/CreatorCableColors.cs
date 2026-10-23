using UnityEngine;

namespace MoreIterators {
 // Keep the native cord geometry and colour groups. Only their live tint changes.
 public static class CreatorCableColors {
  public static void Solid(FSprite sprite,Color color){
   if(sprite==null)return;
   var mesh=sprite as TriangleMesh;
   float opacity=sprite.alpha;
   sprite.color=color;
   if(mesh==null)return;
   // A mesh can already be in vertex-colour mode after an enabled gradient.
   // Repaint that same buffer when returning to a solid or editing it again.
   if(mesh.customColor&&mesh.verticeColors!=null){
    color.a*=opacity;
    for(int i=0;i<mesh.verticeColors.Length;i++)mesh.verticeColors[i]=color;
   }
   mesh.Refresh();
  }
  public static void Head(FSprite sprite,IteratorDesign design,int channel){
   Color solid=IteratorDesign.C(channel==1?design.headCableRed:channel==2?design.headCableBlue:design.metalColor);
   ColorGradient ramp=channel==1?design.headCableAGradient:channel==2?design.headCableBGradient:null;
   // The picker is the actual cable colour, not a blend with the ear base.
   Solid(sprite,solid);
   CreatorColorGradient.Paint(sprite,ramp,solid,0,1,1);
  }
 }
}
