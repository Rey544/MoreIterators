namespace MoreIterators {
using UnityEngine;
public static class SleeveMapping {
 // Front projection of templates/native-preset.json's left sleeve bind pose (28 vertices).
 static readonly float[] Front={1.00000000f,0.39316639f,1.00000000f,0.00000000f,0.95251286f,0.39316639f,0.95251286f,0.00000000f,0.95623269f,0.40856541f,0.70106846f,0.04549497f,0.90320538f,0.42162415f,0.64796201f,0.05855371f,0.94586466f,0.43510414f,0.40997230f,0.20238708f,0.90399683f,0.46880412f,0.36818362f,0.23608706f,0.86671943f,0.53597004f,0.25326474f,0.38441376f,0.83411159f,0.58212029f,0.22065691f,0.43061081f,0.78678275f,0.68022467f,0.14950534f,0.56817224f,0.76137713f,0.73068102f,0.12409972f,0.61867540f,0.71784725f,0.83215539f,0.07368421f,0.73484671f,0.69774436f,0.87877370f,0.05358132f,0.78151182f,0.65563910f,0.96541072f,0.01685793f,0.85635385f,0.63870202f,1.00000000f,0.00000000f,0.89094313f};
 public static void Apply(TriangleMesh mesh,int side,bool mirror){
  if(mesh==null||mesh.vertices.Length*2!=Front.Length)return;var e=mesh.element;
  for(int i=0;i<mesh.vertices.Length;i++){float u=Front[i*2];if(side==1)u=1-u;if(mirror)u=1-u;
   mesh.UVvertices[i]=new Vector2(Mathf.Lerp(e.uvBottomLeft.x,e.uvTopRight.x,u),Mathf.Lerp(e.uvBottomLeft.y,e.uvTopRight.y,1-Front[i*2+1]));}
  mesh.Refresh();
 }
}
}
