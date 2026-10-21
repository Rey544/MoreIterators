namespace MoreIterators {
using System;

[Serializable] public sealed class NecklacePearl {
 public string color="#c5d6ce",highlight="#b7e5ef";
 public bool dual=false;
 // Zero inherits the strand diameter; color selection is independent of size.
 public float size=0;
}
[Serializable] public sealed class NecklaceDesign {
 public int pearls=9,colorMode=0;
 public float size=2.2f,thickness=.4f,leftX=-5,leftY=0,rightX=5,rightY=0,sag=8,softness=.7f;
 public bool symmetric=true;
 public string stringColor="#737e78";
 public NecklacePearl primary=new NecklacePearl();
 public NecklacePearl alternate=new NecklacePearl{color="#354d45",highlight="#d2ebe2",dual=true};
 public NecklacePearl[] beads=new NecklacePearl[0];
 public NecklacePearl Pearl(int i){if(colorMode==2&&beads!=null&&i<beads.Length&&beads[i]!=null)return beads[i];return colorMode==1&&i%2==1?alternate:primary;}
 public float PearlSize(int i){return beads!=null&&i<beads.Length&&beads[i]!=null&&beads[i].size>0?beads[i].size:size;}
}
}
