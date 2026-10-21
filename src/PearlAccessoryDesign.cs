namespace MoreIterators {
using System;

[Serializable] public sealed class PearlAccessoryBead {
 public string color="#c5d6ce",highlight="#b7e5ef";
 public bool dual=false;
 public float size=0,position=.5f;
 public int chain=-1;
}
[Serializable] public sealed class PearlAccessoryChild {
 public string name="",png="",color="#ffffff";
 public bool enabled=true;
 public int bead=0;
 public float x=0,y=0,width=5,height=8,rotation=0;
}
[Serializable] public sealed class PearlAccessoryDesign {
 public string id="",name="",anchor="head",stringColor="#737e78";
 public bool enabled=true;
 public int pearls=5,hangingChains=1,horizontalChains=1,colorMode=0;
 public float u=.5f,v=.5f,x=0,y=0,rotation=0,width=14,length=18,sag=4,thickness=.4f,size=2.2f,softness=.7f,gravity=1;
 public NecklacePearl primary=new NecklacePearl(),alternate=new NecklacePearl{color="#354d45",highlight="#d2ebe2",dual=true};
 public PearlAccessoryBead[] beads=new PearlAccessoryBead[0];
 public PearlAccessoryChild[] children=new PearlAccessoryChild[0];
 public float BeadSize(int i){return beads!=null&&i<beads.Length&&beads[i]!=null&&beads[i].size>0?beads[i].size:size;}
 public NecklacePearl BeadColor(int i){
  if(colorMode==2&&beads!=null&&i<beads.Length&&beads[i]!=null){var b=beads[i];return new NecklacePearl{color=b.color,highlight=b.highlight,dual=b.dual};}
  return colorMode==1&&i%2==1?alternate:primary;
 }
}
}
