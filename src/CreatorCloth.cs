namespace MoreIterators {
using System;
using UnityEngine;

// A one-sided sheet with a pinned shoulder seam. Simulation runs once per game
// tick; drawing only interpolates it. Front/back switching is deliberately absent.
public sealed class CreatorCloth {
 public const int N=11;
 public readonly Vector2[] pos=new Vector2[N*N],last=new Vector2[N*N];
 readonly Vector2[] previous=new Vector2[N*N];
 readonly Vector2[,] tassel=new Vector2[N,4],tasselLast=new Vector2[N,4],tasselPrevious=new Vector2[N,4];
 Vector2 oldCenter;bool initialized;float oldWidth,oldLength;
 public Vector2 Sample(int x,int y,float t){return Vector2.Lerp(last[x*N+y],pos[x*N+y],t);}
 public Vector2 Fringe(int x,int y,float t){return Vector2.Lerp(tasselLast[x,y],tassel[x,y],t);}
 public static float FringeFactor(int x,int panel){return .55f+((x*37+panel*17)%13)/20f;}
 public void Step(Vector2 a,Vector2 b,Vector2 down,float width,float length,float gravity,float lightness,float fringeLength,int panel,float bottomOffset=0){
  Vector2 center=(a+b)*.5f,right=(b-a).normalized;if(right.sqrMagnitude<.1f)right=new Vector2(-down.y,down.x);
  float topWidth=Vector2.Distance(a,b);
  bool reset=!initialized||Vector2.Distance(center,oldCenter)>90||Math.Abs(width-oldWidth)>.1f||Math.Abs(length-oldLength)>.1f;
  if(reset){for(int x=0;x<N;x++)for(int y=0;y<N;y++){float u=x/(float)(N-1),v=y/(float)(N-1);Vector2 q=center+right*((u-.5f)*Mathf.Lerp(topWidth,width,v)+bottomOffset*v)+down*(length*v);pos[x*N+y]=last[x*N+y]=previous[x*N+y]=q;}
   for(int x=0;x<N;x++)for(int y=0;y<4;y++)tassel[x,y]=tasselLast[x,y]=tasselPrevious[x,y]=pos[x*N+N-1]+down*(fringeLength*FringeFactor(x,panel)*y/3f);
  }
  initialized=true;oldCenter=center;oldWidth=width;oldLength=length;
  float damping=Mathf.Lerp(.975f,.995f,lightness);Vector2 acceleration=Vector2.down*(.9f*gravity*Mathf.Lerp(1,.45f,lightness))+down*.013f;
  for(int i=0;i<pos.Length;i++){last[i]=pos[i];Vector2 velocity=Vector2.ClampMagnitude(pos[i]-previous[i],12);previous[i]=pos[i];if(i%N!=0)pos[i]+=velocity*damping+acceleration;}
  for(int pass=0;pass<6;pass++){
   Pin(a,b);
   for(int x=0;x<N;x++)for(int y=0;y<N;y++){
    int i=x*N+y;float v=y/(float)(N-1),dx=Mathf.Lerp(topWidth,width,v)/(N-1),dy=length/(N-1),slant=((x/(float)(N-1)-.5f)*(width-topWidth)+bottomOffset)/(N-1);
    if(x<N-1)Link(i,i+N,dx,.8f,.12f);
    if(y<N-1)Link(i,i+1,Mathf.Sqrt(dy*dy+slant*slant),.8f,.12f);
    if(x<N-1&&y<N-1){float nextDx=Mathf.Lerp(topWidth,width,(y+1f)/(N-1))/(N-1);Link(i,i+N+1,Mathf.Sqrt(dy*dy+(slant+nextDx)*(slant+nextDx)),.08f,0);Link(i+N,i+1,Mathf.Sqrt(dy*dy+(slant-dx)*(slant-dx)),.08f,0);}
    if(y<N-2)Link(i,i+2,2*Mathf.Sqrt(dy*dy+slant*slant),.018f);
   }
   // Compression and curved rows are allowed: preserving each whole row at full
   // width turned the mesh into a board. Only resist complete collapse/stretch.
   for(int y=1;y<N;y++){
    float span=Mathf.Lerp(topWidth,width,y/(float)(N-1));
    float distance=Vector2.Distance(pos[y],pos[(N-1)*N+y]);
    if(distance<span*.35f)Link(y,(N-1)*N+y,span*.35f,.04f);
    else if(distance>span*1.05f)Link(y,(N-1)*N+y,span*1.05f,.1f);
   }
   // Long-range stretch limits keep a short panel from stretching under room
   // gravity. They do not prescribe its direction or straighten curved rows.
   for(int x=0;x<N;x++)for(int y=1;y<N;y++){
    float u=x/(float)(N-1),v=y/(float)(N-1),lean=((u-.5f)*(width-topWidth)+bottomOffset)*v;
    float reach=Mathf.Sqrt(length*length*v*v+lean*lean)*1.06f;
    Vector2 anchor=Vector2.Lerp(a,b,u),delta=pos[x*N+y]-anchor;
    if(delta.sqrMagnitude>reach*reach)pos[x*N+y]=anchor+delta.normalized*reach;
   }
  }
  Pin(a,b);
  for(int x=0;x<N;x++){
   for(int y=0;y<4;y++){tasselLast[x,y]=tassel[x,y];Vector2 v=Vector2.ClampMagnitude(tassel[x,y]-tasselPrevious[x,y],12);tasselPrevious[x,y]=tassel[x,y];if(y>0)tassel[x,y]+=v*.96f+acceleration;}
   float rest=Mathf.Max(.1f,fringeLength*FringeFactor(x,panel)/3);
   for(int pass=0;pass<6;pass++){tassel[x,0]=pos[x*N+N-1];for(int y=1;y<4;y++){Vector2 delta=tassel[x,y]-tassel[x,y-1];float mag=delta.magnitude;if(mag<.0001f)continue;Vector2 correction=delta*(1-rest/mag);if(y==1)tassel[x,y]-=correction;else{tassel[x,y]-=correction*.5f;tassel[x,y-1]+=correction*.5f;}}}
  }
 }
 void Pin(Vector2 a,Vector2 b){for(int x=0;x<N;x++){int i=x*N;pos[i]=Vector2.Lerp(a,b,x/(float)(N-1));previous[i]=pos[i];}}
 void Link(int i,int j,float distance,float stiffness,float compression=-1){Vector2 delta=pos[j]-pos[i];float mag=delta.magnitude;if(mag<.0001f)return;if(mag<distance&&compression>=0)stiffness=compression;float a=i%N==0?0:1,b=j%N==0?0:1;if(a+b==0)return;Vector2 correction=delta*((mag-distance)/mag*stiffness/(a+b));pos[i]+=correction*a;pos[j]-=correction*b;}
}
}
