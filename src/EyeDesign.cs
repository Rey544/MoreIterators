namespace MoreIterators {
using System;

// Empty IteratorDesign.eyes retains the original two eyes without migration.
// Positions are offsets in the animated head's local axes, in game pixels.
[Serializable] public class EyeDesign {
 public string id="eye",color="",texturePng="",mirrorOf="";
 public bool enabled=true,textureEnabled=false,textureTint=false,textureMirrorX=false;
 public int sourceSide=0;
 public float offsetX=0,offsetY=0,scale=1;
}
}
