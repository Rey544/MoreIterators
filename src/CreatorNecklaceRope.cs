namespace MoreIterators {
using System;
using UnityEngine;

// Two pinned ends, freely moving interior. All integration is in game ticks;
// rendering interpolates between states and never advances the simulation.
public sealed class CreatorNecklaceRope {
 public const int N=25;
 public readonly Vector2[] pos=new Vector2[N],last=new Vector2[N];
 readonly Vector2[] previous=new Vector2[N];
 readonly float[] lengths=new float[N-1],reach=new float[N];
 bool initialized;Vector2 oldCenter;float oldSpan,oldSag;
 public Vector2 Sample(int i,float t){return Vector2.Lerp(last[i],pos[i],t);}
 public void Step(Vector2 a,Vector2 b,Vector2 down,float sag,float gravity,float softness){
  Vector2 center=(a+b)*.5f;float span=Vector2.Distance(a,b);
  bool reset=!initialized||Vector2.Distance(center,oldCenter)>90||Mathf.Abs(oldSag-sag)>.02f||Mathf.Abs(oldSpan-span)>3;
  float total=0;Vector2 prior=a;
  for(int i=0;i<N;i++){
   float u=i/(float)(N-1);Vector2 rest=Vector2.Lerp(a,b,u)+down*(4*sag*u*(1-u));
   if(i>0){lengths[i-1]=Mathf.Max(.025f,Vector2.Distance(prior,rest));total+=lengths[i-1];}reach[i]=total;prior=rest;
   if(reset)pos[i]=last[i]=previous[i]=rest;
  }
  initialized=true;oldCenter=center;oldSpan=span;oldSag=sag;
  if(sag<.001f){for(int i=0;i<N;i++){last[i]=pos[i];pos[i]=previous[i]=Vector2.Lerp(a,b,i/(float)(N-1));}return;}
  // A very small local bias keeps a necklace curved in zero gravity; room
  // gravity dominates freely so inverted poses hang toward the world floor.
  Vector2 force=Vector2.down*(.48f*gravity*Mathf.Lerp(1,.55f,softness))+down*.006f;
  for(int i=0;i<N;i++){last[i]=pos[i];Vector2 v=Vector2.ClampMagnitude(pos[i]-previous[i],9);previous[i]=pos[i];if(i>0&&i<N-1)pos[i]+=v*Mathf.Lerp(.94f,.987f,softness)+force;}
  for(int pass=0;pass<16;pass++){
   pos[0]=a;pos[N-1]=b;
   // Alternate sweep direction avoids a persistent bias to one shoulder.
   for(int k=0;k<N-1;k++){int i=pass%2==0?k:N-2-k,j=i+1;Vector2 delta=pos[j]-pos[i];float length=delta.magnitude;if(length<.00001f)continue;
    Vector2 correction=delta*((length-lengths[i])/length);if(i==0)pos[j]-=correction;else if(j==N-1)pos[i]+=correction;else{pos[i]+=correction*.5f;pos[j]-=correction*.5f;}
   }
   for(int i=1;i<N-1;i++){
    Vector2 v=pos[i]-a;float limit=reach[i]*1.035f;if(v.sqrMagnitude>limit*limit)pos[i]=a+v.normalized*limit;
    v=pos[i]-b;limit=(total-reach[i])*1.035f;if(v.sqrMagnitude>limit*limit)pos[i]=b+v.normalized*limit;
   }
  }
  pos[0]=a;pos[N-1]=b;previous[0]=a;previous[N-1]=b;
 }
}
}
