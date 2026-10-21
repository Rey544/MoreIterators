namespace MoreIterators {
using System;
using System.Collections.Generic;
using UnityEngine;

// One connected graph: beads are weighted rope particles, not independently
// animated sprites. Geometry is rebuilt only when its parameters change.
public sealed class PearlAccessoryPhysics {
 public struct Link {public int a,b;public float length;public Link(int a,int b,float length){this.a=a;this.b=b;this.length=length;}}
 public readonly List<Vector2> rest=new List<Vector2>();
 public readonly List<Link> links=new List<Link>();
 public readonly List<int[]> chains=new List<int[]>();
 public readonly List<int> pins=new List<int>();
 public int[] beadNodes=new int[0];
 public Vector2[] pos=new Vector2[0],last=new Vector2[0];
 Vector2[] previous=new Vector2[0];float[] inverseMass=new float[0];
 PearlAccessoryDesign design;string key="";bool initialized;Vector2 center;
 public Vector2 Sample(int index,float time){return Vector2.Lerp(last[index],pos[index],time);}
 public bool Ready{get{return initialized;}}
 int Node(Vector2 point){rest.Add(point);return rest.Count-1;}
 void Join(int a,int b){if(a!=b)links.Add(new Link(a,b,Mathf.Max(.025f,Vector2.Distance(rest[a],rest[b]))));}
 int[] Path(int first,Vector2 end,int steps,int final=-1){var path=new int[steps+1];path[0]=first;Vector2 start=rest[first];for(int j=1;j<=steps;j++){path[j]=j==steps&&final>=0?final:Node(Vector2.Lerp(start,end,j/(float)steps));Join(path[j-1],path[j]);}return path;}
 string GeometryKey(PearlAccessoryDesign d){
  string value=d.pearls+"/"+d.hangingChains+"/"+d.horizontalChains+"/"+d.width+"/"+d.length+"/"+d.sag+"/"+d.size;
  if(d.beads!=null)foreach(var bead in d.beads)if(bead!=null)value+="/"+bead.chain+":"+bead.position+":"+bead.size;
  return value;
 }
 public void Configure(PearlAccessoryDesign d){
  design=d;string next=GeometryKey(d);if(next==key)return;key=next;initialized=false;rest.Clear();links.Clear();chains.Clear();pins.Clear();
  int horizontal=Mathf.Clamp(d.horizontalChains,0,5),hanging=Mathf.Clamp(d.hangingChains,0,5);int[] previousRow=null;
  for(int row=0;row<horizontal;row++){
   var current=new int[13];float top=-d.length*.55f*row/Mathf.Max(1,horizontal-1);
   for(int j=0;j<13;j++){float u=j/12f;current[j]=Node(new Vector2((u-.5f)*d.width,top-4*d.sag*u*(1-u)));if(j>0)Join(current[j-1],current[j]);}
   chains.Add(current);
   if(previousRow==null){pins.Add(current[0]);pins.Add(current[12]);}
   else {Path(previousRow[0],rest[current[0]],4,current[0]);Path(previousRow[12],rest[current[12]],4,current[12]);}
   previousRow=current;
  }
  int root=-1;if(horizontal==0){root=Node(Vector2.zero);pins.Add(root);}
  for(int c=0;c<hanging;c++){
   float t=(c+1f)/(hanging+1f);int start=previousRow==null?root:previousRow[Mathf.RoundToInt(t*12)];Vector2 origin=rest[start];
   Vector2 end=origin+new Vector2(previousRow==null?(t-.5f)*d.width:0,-d.length*(.72f+(c*7%5)*.07f));chains.Add(Path(start,end,10));
  }
  if(chains.Count==0&&d.pearls>0){chains.Add(Path(root,new Vector2(0,-d.length),10));}
  var candidates=new List<int>();foreach(var chain in chains)foreach(int node in chain)if(!pins.Contains(node)&&!candidates.Contains(node))candidates.Add(node);
  int count=candidates.Count==0?0:Mathf.Clamp(d.pearls,0,10);beadNodes=new int[count];var used=new HashSet<int>();
  for(int i=0;i<count;i++){
   PearlAccessoryBead bead=d.beads!=null&&i<d.beads.Length?d.beads[i]:null;int node;
   if(bead!=null&&bead.chain>=0&&bead.chain<chains.Count){var chain=chains[bead.chain];int end=pins.Contains(chain[chain.Length-1])?chain.Length-2:chain.Length-1;node=chain[Mathf.Clamp(Mathf.RoundToInt(Mathf.Clamp01(bead.position)*(chain.Length-1)),1,end)];}
   else node=candidates[Mathf.Clamp((int)((i+.5f)*candidates.Count/count),0,candidates.Count-1)];
   // Nearby pearls never silently occupy the same simulation particle.
   if(used.Contains(node)){int index=candidates.IndexOf(node);for(int j=1;j<=candidates.Count;j++){int other=candidates[(Mathf.Max(0,index)+j)%candidates.Count];if(!used.Contains(other)){node=other;break;}}}
   beadNodes[i]=node;used.Add(node);
  }
  pos=new Vector2[rest.Count];last=new Vector2[rest.Count];previous=new Vector2[rest.Count];inverseMass=new float[rest.Count];for(int i=0;i<rest.Count;i++)inverseMass[i]=pins.Contains(i)?0:1;
  for(int i=0;i<count;i++)inverseMass[beadNodes[i]]=1/Mathf.Max(1,d.BeadSize(i)*d.BeadSize(i)*.4f);
 }
 static Vector2 World(Vector2 p,Vector2 origin,Vector2 right,Vector2 up,float scale){return origin+(right*p.x+up*p.y)*scale;}
 public void Step(Vector2 origin,Vector2 right,Vector2 up,float scale,float roomGravity){
  if(design==null||pos.Length==0)return;
  if(!initialized||Vector2.Distance(center,origin)>120){for(int i=0;i<pos.Length;i++){Vector2 point=World(rest[i],origin,right,up,scale);if(inverseMass[i]>0)point+=right*((float)Math.Sin(i*1.7f)*.02f*scale);pos[i]=last[i]=previous[i]=point;}initialized=true;}
  center=origin;float drag=Mathf.Lerp(.93f,.987f,Mathf.Clamp01(design.softness));Vector2 force=Vector2.down*(.44f*Mathf.Max(0,roomGravity)*design.gravity);
  for(int i=0;i<pos.Length;i++){last[i]=pos[i];Vector2 velocity=Vector2.ClampMagnitude(pos[i]-previous[i],12);previous[i]=pos[i];if(inverseMass[i]>0)pos[i]+=velocity*drag+force;}
  for(int pass=0;pass<20;pass++){
   foreach(int pin in pins)pos[pin]=World(rest[pin],origin,right,up,scale);
   for(int k=0;k<links.Count;k++){Link link=links[pass%2==0?k:links.Count-1-k];Vector2 delta=pos[link.b]-pos[link.a];float distance=delta.magnitude,total=inverseMass[link.a]+inverseMass[link.b];if(distance<.00001f||total<=0)continue;Vector2 correction=delta*((distance-link.length*scale)/distance);pos[link.a]+=correction*(inverseMass[link.a]/total);pos[link.b]-=correction*(inverseMass[link.b]/total);}
  }
  foreach(int pin in pins)pos[pin]=previous[pin]=World(rest[pin],origin,right,up,scale);
 }
}
}
