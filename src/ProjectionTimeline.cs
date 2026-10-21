using System;
using UnityEngine;

namespace MoreIterators {
 [Serializable] public sealed class ProjectionFrame {
  public float duration=1,x=.5f,y=.4f,scale=1,rotation,opacity=1,brightness=1,flicker;
  public string ease="smooth";
 }
 [Serializable] public sealed class ProjectionMask {
  public bool enabled;public float x,y,width=1,height=1;
 }
 [Serializable] public sealed class ProjectionTrack {
  public string id="",name="",kind="image",imageId="",color="#ffffff",style="native";
  public string maskMode="inherit";public ProjectionMask mask=new ProjectionMask();
  public float delay;
  public int glyphIndex;
  public ProjectionFrame[] frames=new ProjectionFrame[0];
 }
 [Serializable] public sealed class ProjectionImage {
  public string id="",name="",png="";public int width,height;
 }
 [Serializable] public sealed class ProjectionTrigger {
  public string kind="work",source="",pearlUid="",startLineId="",endLineId="";
  public string[] lineIds=new string[0];
  public float beforeSeconds,afterSeconds;
 }
 [Serializable] public sealed class ProjectionGroup {
  public string schema="",uid="",name="",projectId="",oracleId="",ownerMod="";
  public int revision;public bool enabled=true,loop,confineToRoom;
  public ProjectionMask projectMask=new ProjectionMask();
  public ProjectionTrigger trigger=new ProjectionTrigger();
  public ProjectionImage[] images=new ProjectionImage[0];
  public ProjectionTrack[] tracks=new ProjectionTrack[0];
 }
 // Pure timeline sampling is shared conceptually with the editor. Room positions
 // use a top-left normalized origin; conversion to game coordinates is at draw.
 public static class ProjectionTimeline {
  public static float Duration(ProjectionTrack track){float n=track.delay;for(int i=0;i<track.frames.Length;i++)n+=track.frames[i].duration;return n;}
  public static float Duration(ProjectionGroup group){float n=0;foreach(var t in group.tracks)n=Math.Max(n,Duration(t));return Math.Max(.025f,n);}
  public static ProjectionFrame Sample(ProjectionTrack track,float time){
   if(track.frames.Length==0)return new ProjectionFrame{opacity=0};
   ProjectionFrame a=track.frames[0];time-=track.delay;
   if(time<0)return Copy(a,0);
   if(time<a.duration)return Copy(a,a.opacity);
   time-=a.duration;
   for(int i=1;i<track.frames.Length;i++){
    ProjectionFrame b=track.frames[i];
    if(b.duration<=0){a=b;continue;}
    if(time<b.duration){float f=b.ease=="step"?0:Mathf.Clamp01(time/b.duration);if(b.ease=="smooth")f=f*f*(3-2*f);
     return new ProjectionFrame{x=Mix(a.x,b.x,f),y=Mix(a.y,b.y,f),scale=Mix(a.scale,b.scale,f),rotation=Mix(a.rotation,b.rotation,f),opacity=Mix(a.opacity,b.opacity,f),brightness=Mix(a.brightness,b.brightness,f),flicker=Mix(a.flicker,b.flicker,f)};
    }time-=b.duration;a=b;
   }
   return Copy(a,a.opacity);
  }
  static float Mix(float a,float b,float f){return a+(b-a)*f;}
  static ProjectionFrame Copy(ProjectionFrame a,float opacity){return new ProjectionFrame{x=a.x,y=a.y,scale=a.scale,rotation=a.rotation,opacity=opacity,brightness=a.brightness,flicker=a.flicker};}
  public static bool Contains(ProjectionGroup group,string id){return !String.IsNullOrEmpty(id)&&Array.IndexOf(group.trigger.lineIds,id)>=0;}
 }
}
