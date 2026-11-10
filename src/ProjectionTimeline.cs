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
  public static bool IsEase(string kind){return Array.IndexOf(new[]{"linear","smooth","step","quadIn","quadOut","quadInOut","sineInOut","expIn","expOut","expInOut","circIn","circOut","circInOut","backIn","backOut","backInOut","elasticIn","elasticOut","elasticInOut"},kind)>=0;}
  public static float Ease(string kind,float t){
   t=Mathf.Clamp01(t);
   if(kind=="step")return 0;
   if(t==0||t==1)return t;
   switch(kind){
    case "smooth":return t*t*(3-2*t);
    case "quadIn":return RWCustom.Custom.LerpQuadEaseIn(0,1,t);
    case "quadOut":return RWCustom.Custom.LerpQuadEaseOut(0,1,t);
    case "quadInOut":return RWCustom.Custom.LerpQuadEaseInOut(0,1,t);
    case "sineInOut":return RWCustom.Custom.LerpSinEaseInOut(0,1,t);
    case "expIn":return RWCustom.Custom.LerpExpEaseIn(0,1,t);
    case "expOut":return RWCustom.Custom.LerpExpEaseOut(0,1,t);
    case "expInOut":return RWCustom.Custom.LerpExpEaseInOut(0,1,t);
    case "circIn":return RWCustom.Custom.LerpCircEaseIn(0,1,t);
    case "circOut":return RWCustom.Custom.LerpCircEaseOut(0,1,t);
    case "circInOut":return RWCustom.Custom.LerpCircEaseInOut(0,1,t);
    case "backIn":return RWCustom.Custom.LerpBackEaseIn(0,1,t);
    case "backOut":return RWCustom.Custom.LerpBackEaseOut(0,1,t);
    case "backInOut":return RWCustom.Custom.LerpBackEaseInOut(0,1,t);
    case "elasticIn":return RWCustom.Custom.LerpElasticEaseIn(0,1,t);
    case "elasticOut":return RWCustom.Custom.LerpElasticEaseOut(0,1,t);
    case "elasticInOut":return RWCustom.Custom.LerpElasticEaseInOut(0,1,t);
    default:return t;
   }
  }
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
    if(time<b.duration){float f=Ease(b.ease,time/b.duration);
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
