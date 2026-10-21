namespace MoreIterators {
using System;
using UnityEngine;
[Serializable] public class PuppetArmDesign {
 public bool enabled=true,sleeveEnabled=true,handOwnColor=false,handTextureEnabled=false,handTextureTint=false,sleeveTextureEnabled=true,sleeveOwnColor=false,sleeveOwnTexture=false;
 public string handColor="#a6aaa9",sleeveColor="#b68b8e",handPng="",sleeveBasePng="",sleevePng="";
 public float lengthScale=1,widthScale=1,handSize=1,shoulderX=0,shoulderY=0,sleeveRootX=0,sleeveRootY=0;
 public static PuppetArmDesign Default(int index){return new PuppetArmDesign{enabled=index<2,shoulderY=index>=2?-8:0};}
}
public static class PuppetArmGeometry {
 public static Vector2 Point(Vector2 point,Vector2 root,Vector2 shift,float length){return root+(point-root)*length+shift;}
 // Slide the shoulder seam without detaching the wrist end of the native Bezier sleeve.
 public static Vector2 SleevePoint(Vector2 point,Vector2 root,Vector2 shift,Vector2 seam,float length,float t){return Point(point,root,shift,length)+seam*(1-t);}
}
}
