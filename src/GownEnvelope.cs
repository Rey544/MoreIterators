namespace MoreIterators {
using System;
using UnityEngine;

// The outer panels sample the final rendered gown, including its current swing.
// This is independent of the cloth solver, so interpolation cannot expose the hem.
public static class GownEnvelope {
 static Vector2 Edge(Vector2[] gown,int n,bool right,float v){float y=Mathf.Clamp01(v)*(n-1);int k=Math.Min(n-2,(int)y),col=right?n-1:0;return Vector2.Lerp(gown[col*n+k],gown[col*n+k+1],y-k);}
 public static void Apply(Vector2[] panel,Vector2[] gown,int side,Vector2 axis,float scale){
  int n=(int)Math.Sqrt(gown.Length);if(n*n!=gown.Length||panel.Length!=121||n<2)return;
  bool reverse=Vector2.Dot(Edge(gown,n,true,0)-Edge(gown,n,false,0),axis)<0;
  for(int y=0;y<11;y++){
   float v=y/10f;Vector2 left=Edge(gown,n,reverse,v),right=Edge(gown,n,!reverse,v),center=(left+right)*.5f;
   Vector2 outer=(side==0?left:right)+axis*(side==0?-.6f:.6f)*scale;
   float outward=Vector2.Dot(panel[(side==0?0:10)*11+y]-outer,axis)*(side==0?-1:1);
   outer+=axis*(side==0?-1:1)*Mathf.Clamp(outward,0,5*scale)*v;
   Vector2 inner=center+axis*(side==0?-.25f:.25f)*scale;
   for(int x=0;x<11;x++)panel[x*11+y]=side==0?Vector2.Lerp(outer,inner,x/10f):Vector2.Lerp(inner,outer,x/10f);
  }
 }
}
}
