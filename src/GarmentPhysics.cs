namespace MoreIterators {
using System;
using System.Collections.Generic;
using UnityEngine;

[Serializable] public sealed class GarmentDesign {
 public string id="",name="",type="cloth",anchor="shoulders",anchor2="shoulders",basePng="",patternPng="";
 public bool enabled=false,mirror=false,fringe=false,lockGown=false;
 public float width=10,length=27,topWidth=5,u=0,v=0,u2=1,v2=0,x=0,y=0,x2=0,y2=0,midX=0,midY=0,sag=2,roundness=.65f,elasticity=.65f,gravity=1,fringeLength=5,grain=.1f;
 public string topColor="#303a40",middleColor="#667079",bottomColor="#abb5bc",fringeColor="#bbc4c7";
 public float rigidRotation=0;
 public int canvasWidth=64,canvasHeight=96,bindRow=0;
}


// Hardware uses one affine rectangle. Transparent pixels define its silhouette;
// cloth-only parameters cannot bend, taper, or add fringe to this rectangle.
public static class GarmentGeometry {
 public static Vector2 Surface(Vector2[] vertices,float u,float v){
  if(vertices==null||vertices.Length<4)return Vector2.zero;u=Mathf.Clamp01(u);v=Mathf.Clamp01(v);
  int n=(int)Math.Sqrt(vertices.Length);
  // Native limbs and straight-leg segments store pairs along their length.
  if(n*n!=vertices.Length||vertices.Length==4){int rows=vertices.Length/2;float y=v*(rows-1);int row=Math.Min(rows-2,(int)y);return Vector2.Lerp(Vector2.Lerp(vertices[row*2],vertices[row*2+1],u),Vector2.Lerp(vertices[(row+1)*2],vertices[(row+1)*2+1],u),y-row);}
  float xx=u*(n-1),yy=v*(n-1);int x=Math.Min(n-2,(int)xx),iy=Math.Min(n-2,(int)yy);
  return Vector2.Lerp(Vector2.Lerp(vertices[x*n+iy],vertices[(x+1)*n+iy],xx-x),Vector2.Lerp(vertices[x*n+iy+1],vertices[(x+1)*n+iy+1],xx-x),yy-iy);
 }
 public static Vector2 RigidPoint(Vector2 a,Vector2 b,Vector2 right,Vector2 up,GarmentDesign d,float scale,float u,float v){
  float angle=d.rigidRotation*Mathf.Deg2Rad,c=Mathf.Cos(angle),s=Mathf.Sin(angle);
  Vector2 axis=right*c+up*s,vertical=up*c-right*s;
  return (a+b)*.5f+axis*((u-.5f)*d.width*scale)-vertical*(v*d.length*scale);
 }
}

public static class GarmentBindings {
 static readonly HashSet<string> builtIn=new HashSet<string>{"head","body","neck","gown","shoulders","sleeveL","sleeveR","collar","handL","handR","legL","legR","earL","earR","earDecorationL","earDecorationR","antennaL","antennaR","antennaUpperL","antennaUpperR","antennaLowerL","antennaLowerR"};
 public static bool BuiltIn(string id){return id!=null&&builtIn.Contains(id);}
 public static List<int> Order(IList<GarmentDesign> pieces,out string error){
  var index=new Dictionary<string,int>();var duplicates=new HashSet<string>();var result=new List<int>();var errors=new List<string>();
  for(int i=0;i<pieces.Count;i++){
   var piece=pieces[i];if(piece==null){errors.Add("missing accessory data at entry "+(i+1));continue;}if(String.IsNullOrWhiteSpace(piece.id)){errors.Add("missing accessory ID at entry "+(i+1));continue;}
   if(index.ContainsKey(piece.id)){duplicates.Add(piece.id);errors.Add("duplicate accessory ID: "+piece.id);}else index.Add(piece.id,i);
  }
  var marks=new Dictionary<string,int>();
  for(int i=0;i<pieces.Count;i++)if(pieces[i]!=null&&!String.IsNullOrWhiteSpace(pieces[i].id))Visit(pieces[i].id,pieces,index,duplicates,marks,result,errors);
  error=String.Join("; ",errors.ToArray());return result;
 }
 static bool Visit(string id,IList<GarmentDesign> pieces,Dictionary<string,int> index,HashSet<string> duplicates,Dictionary<string,int> marks,List<int> result,List<string> errors){
  if(BuiltIn(id))return true;
  int slot,mark;if(String.IsNullOrWhiteSpace(id)||!index.TryGetValue(id,out slot)){string missing="missing binding target: "+(String.IsNullOrWhiteSpace(id)?"<empty>":id);if(!errors.Contains(missing))errors.Add(missing);return false;}
  if(duplicates.Contains(id))return false;
  if(marks.TryGetValue(id,out mark)){if(mark==1)errors.Add("cyclic accessory binding: "+id);return mark==2;}
  marks[id]=1;var piece=pieces[slot];bool left=Visit(piece.anchor,pieces,index,duplicates,marks,result,errors),right=Visit(piece.anchor2,pieces,index,duplicates,marks,result,errors);
  if(!left||!right){marks[id]=3;return false;}
  marks[id]=2;result.Add(slot);return true;
 }
}

// Fixed topology, continuous Verlet state. Rotation never switches to another mesh.
public sealed class GarmentPhysics {
 public const int N=11;
 public readonly Vector2[] pos=new Vector2[N*N],last=new Vector2[N*N];
 readonly Vector2[] old=new Vector2[N*N],rest=new Vector2[N*N];
 readonly Vector2[,] tassel=new Vector2[N,4],tasselLast=new Vector2[N,4],tasselOld=new Vector2[N,4];
 bool initialized;int boundRow;Vector2 center;float length,width;
 public Vector2 Sample(int x,int y,float t){return Vector2.Lerp(last[x*N+y],pos[x*N+y],t);}
 public Vector2 Fringe(int x,int y,float t){return Vector2.Lerp(tasselLast[x,y],tassel[x,y],t);}
 public static Vector2 Seam(Vector2 a,Vector2 b,Vector2 middle,float u){return Vector2.Lerp(a,b,u)+middle*(4*u*(1-u));}
 public static float Hem(float u,float smooth){return Mathf.Lerp(1-Mathf.Abs(u*2-1),Mathf.Sin(u*Mathf.PI),smooth);}
 public void Step(Vector2 a,Vector2 b,Vector2 right,Vector2 down,GarmentDesign d,float scale,float roomGravity){
  int nextRow=Mathf.Clamp(d.bindRow,0,10);bool rebind=boundRow!=nextRow;boundRow=nextRow;Vector2 mid=right*d.midX*scale-down*d.midY*scale;float span=Vector2.Distance(a,b);
  for(int x=0;x<N;x++)for(int y=0;y<N;y++){float u=x/10f,v=(y-boundRow)/10f;rest[x*N+y]=Seam(a,b,mid,u)+right*((u-.5f)*(d.width*scale-span)*v)+down*((d.length+d.sag*Hem(u,d.roundness))*scale*v);}
  Vector2 c=(a+b)*.5f;bool reset=!initialized||rebind||Vector2.Distance(c,center)>120||Math.Abs(d.length-length)>10||Math.Abs(d.width-width)>20;
  if(reset){for(int i=0;i<pos.Length;i++)pos[i]=last[i]=old[i]=rest[i];for(int x=0;x<N;x++)for(int j=0;j<4;j++)tassel[x,j]=tasselLast[x,j]=tasselOld[x,j]=pos[x*N+10]+Vector2.down*(j*d.fringeLength/3f*scale);}
  initialized=true;center=c;length=d.length;width=d.width;
  Vector2 acc=Vector2.down*(.65f*roomGravity*d.gravity)+down*.012f;
  float damping=Mathf.Lerp(.93f,.986f,d.elasticity),stiffness=Mathf.Lerp(.94f,.62f,d.elasticity);
  for(int i=0;i<pos.Length;i++){last[i]=pos[i];Vector2 velocity=Vector2.ClampMagnitude(pos[i]-old[i],12*scale);old[i]=pos[i];if(i%N!=boundRow)pos[i]+=velocity*damping+acc;}
  for(int pass=0;pass<7;pass++){
   Pin();
   for(int x=0;x<N;x++)for(int y=0;y<N;y++){int i=x*N+y;if(x<N-1)Link(i,i+N,stiffness);if(y<N-1)Link(i,i+1,stiffness);if(x<N-1&&y<N-1){Link(i,i+N+1,.12f);Link(i+N,i+1,.12f);}if(y<N-2)Link(i,i+2,.015f);}
   for(int x=0;x<N;x++)for(int y=0;y<N;y++){if(y==boundRow)continue;int i=x*N+y;Vector2 anchor=rest[x*N+boundRow],delta=pos[i]-anchor;float reach=Vector2.Distance(rest[i],anchor)*1.07f;if(delta.magnitude>reach)pos[i]=anchor+delta.normalized*reach;}
  }
  Pin();
  for(int x=0;x<N;x++){
   for(int j=0;j<4;j++){tasselLast[x,j]=tassel[x,j];Vector2 speed=Vector2.ClampMagnitude(tassel[x,j]-tasselOld[x,j],10);tasselOld[x,j]=tassel[x,j];if(j>0)tassel[x,j]+=speed*.965f+acc;}
   float segment=Mathf.Max(.05f,d.fringeLength*scale*CreatorCloth.FringeFactor(x,0)/3f);
   for(int pass=0;pass<6;pass++){tassel[x,0]=pos[x*N+10];for(int j=1;j<4;j++){Vector2 delta=tassel[x,j]-tassel[x,j-1];if(delta.sqrMagnitude<.0001f)delta=Vector2.down*.01f;Vector2 correction=delta*(1-segment/delta.magnitude);if(j==1)tassel[x,j]-=correction;else{tassel[x,j]-=correction*.5f;tassel[x,j-1]+=correction*.5f;}}}
  }
 }
 void Pin(){for(int x=0;x<N;x++){int i=x*N+boundRow;pos[i]=rest[i];old[i]=pos[i];}}
 void Link(int i,int j,float stiffness){Vector2 delta=pos[j]-pos[i];float mag=delta.magnitude;if(mag<.00001f)return;float distance=Vector2.Distance(rest[i],rest[j]);if(mag<distance)stiffness*=.18f;float a=i%N==boundRow?0:1,b=j%N==boundRow?0:1;if(a+b==0)return;Vector2 correction=delta*((mag-distance)/mag*stiffness/(a+b));pos[i]+=correction*a;pos[j]-=correction*b;}
}
}
