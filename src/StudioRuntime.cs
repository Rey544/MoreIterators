namespace MoreIterators {
using System;
using System.IO;
using System.Collections;
using UnityEngine;
[Serializable]public class StudioPose {public string pose="idle",bpPearl="stomach";public bool playMode=false,hasMark=true,recording=false;public bool animate=true,manualLeft,manualRight,captureMotion;public float leftX=-20,leftY=-15,rightX=20,rightY=-15,bodyAngle=0,testGravity=-1;}
public static class StudioRuntime {
 public static string DirectoryPath {get{return RuntimePaths.DataDirectory;}}
 public static StudioPose Pose=new StudioPose();static string poseJson;static float nextPoll;static int settleFrames=100;
 public static bool Recording {get{return Pose.recording&&!Pose.playMode;}}
 static bool recordingDisplay;
 public static void UpdateDisplay(){
  bool full=Pose.playMode||Recording;
  if(Recording&&!recordingDisplay){var resolution=Screen.currentResolution;Screen.SetResolution(resolution.width,resolution.height,true);}
  else if(Screen.fullScreen!=full)Screen.fullScreen=full;
  recordingDisplay=Recording;
 }
 public static bool Simulating {get{return Pose.playMode||Pose.animate||settleFrames>0;}}
 static readonly System.Reflection.FieldInfo LookDirection=typeof(OracleGraphics).GetField("lookDir",System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic|System.Reflection.BindingFlags.Public); public static OracleGraphics Graphics;public static RoomCamera.SpriteLeaser Sprites;public static float FaceAngle;
 public static void UpdatePose(OracleGraphics g){if(g.oracle.room==null||!MoreIteratorsPlugin.IsChamber(g.oracle.room.abstractRoom.name))return;
  PollPose();
  if(settleFrames>0)settleFrames--;
  if(!Pose.animate&&!Pose.playMode){var chest=g.oracle.bodyChunks[0];Vector2 up=new Vector2(Mathf.Sin(Pose.bodyAngle*Mathf.Deg2Rad),Mathf.Cos(Pose.bodyAngle*Mathf.Deg2Rad));g.oracle.bodyChunks[1].HardSetPosition(chest.pos-up*9);g.head.pos=chest.pos+up*12;g.head.lastPos=g.head.pos;g.head.vel=Vector2.zero;if(LookDirection!=null)LookDirection.SetValue(g,Vector2.zero);}
  // Quiet viewing leaves the native hands, gaze, direction and motion alone.
  if(Pose.playMode||Recording)return;
  Vector2 bodyUp=(g.head.pos-g.oracle.firstChunk.pos).normalized;if(bodyUp.sqrMagnitude<.1f)bodyUp=Vector2.up;
  Vector2 bodyRight=new Vector2(bodyUp.y,-bodyUp.x);
  for(int i=0;i<2;i++){
   bool manual=i==0?Pose.manualLeft:Pose.manualRight;if(Pose.pose=="idle"&&!manual)continue;
   float sign=i==0?-1:1;Vector2 offset=Pose.pose=="work"?new Vector2(sign*17,-4):new Vector2(sign*26,-12);
   if(manual)offset=i==0?new Vector2(Pose.leftX,Pose.leftY):new Vector2(Pose.rightX,Pose.rightY);
   else offset=bodyRight*offset.x+bodyUp*offset.y;
   Vector2 target=g.head.pos+offset;
   // Keep the preceding simulation position for render interpolation. Presets
   // are body-local, so rotating the puppet cannot close its outstretched arms.
   if(!Pose.animate)g.hands[i].lastPos=target;
   g.hands[i].pos=target;g.hands[i].vel=Vector2.zero;
  }
 }
 internal static void PollPose(){
  if(Time.realtimeSinceStartup<=nextPoll)return;nextPoll=Time.realtimeSinceStartup+.1f;
  string file=Path.Combine(DirectoryPath,"studio-control.json");
  try{if(File.Exists(file)){string json=File.ReadAllText(file);if(json!=poseJson){
   var candidate=JsonUtility.FromJson<StudioPose>(json);if(candidate==null)throw new FormatException("Studio control must contain a pose object.");
   Pose=candidate;poseJson=json;settleFrames=100;
  }}}catch(Exception error){MiDiagnostics.Report("MI-STUDIO-POSE","StudioRuntime.PollPose",error,file);}
 }
 static Texture2D captureTexture;
 public static void ReleaseCapture(){if(captureTexture!=null)UnityEngine.Object.Destroy(captureTexture);captureTexture=null;}
 public static IEnumerator Capture(Action<string> log){float next=0,ioFailureSince=0,nextIOReport=0;int ioFailures=0;
  try{
  while(true){yield return new WaitForEndOfFrame();if(Time.realtimeSinceStartup<next)continue;next=Time.realtimeSinceStartup+(Pose.playMode?.25f:.05f);
   if(Recording||Graphics==null||Sprites==null||Graphics.oracle.room==null||Graphics.oracle.slatedForDeletetion||!(Graphics.oracle.room.game.manager.currentMainLoop is RainWorldGame))continue;
   try{Directory.CreateDirectory(DirectoryPath);var head=Sprites.sprites[Graphics.HeadSprite];Vector2 h=head.LocalToScreen(Vector2.zero);float scale=1f/Futile.displayScaleInverse;int w=(int)(140*scale),ht=(int)(150*scale);int x=Mathf.Clamp((int)(h.x-w*.5f),0,Screen.width-w),y=Mathf.Clamp((int)(h.y-ht*.65f),0,Screen.height-ht);
    if(captureTexture==null||captureTexture.width!=w||captureTexture.height!=ht){ReleaseCapture();captureTexture=new Texture2D(w,ht,TextureFormat.RGB24,false);}captureTexture.ReadPixels(new Rect(x,y,w,ht),0,0,false);captureTexture.Apply(false);var png=ImageConversion.EncodeToPNG(captureTexture);string dest=Path.Combine(DirectoryPath,"studio-frame.png");File.WriteAllBytes(dest+".tmp",png);if(File.Exists(dest))File.Replace(dest+".tmp",dest,null);else File.Move(dest+".tmp",dest);
    Vector2 left=Sprites.sprites[Graphics.HandSprite(0,0)].LocalToScreen(Vector2.zero),right=Sprites.sprites[Graphics.HandSprite(1,0)].LocalToScreen(Vector2.zero);string meta="{\"oracleId\":\""+IteratorDesign.Current.oracleId+"\",\"faceAngle\":"+FaceAngle.ToString(System.Globalization.CultureInfo.InvariantCulture)+",\"previewToken\":\""+IteratorDesign.Current.previewToken+"\",\"width\":"+w+",\"height\":"+ht+",\"scale\":"+scale.ToString(System.Globalization.CultureInfo.InvariantCulture)+",\"headX\":"+(h.x-x).ToString(System.Globalization.CultureInfo.InvariantCulture)+",\"headY\":"+(ht-h.y+y).ToString(System.Globalization.CultureInfo.InvariantCulture)+",\"leftX\":"+(left.x-x).ToString(System.Globalization.CultureInfo.InvariantCulture)+",\"leftY\":"+(ht-left.y+y).ToString(System.Globalization.CultureInfo.InvariantCulture)+",\"rightX\":"+(right.x-x).ToString(System.Globalization.CultureInfo.InvariantCulture)+",\"rightY\":"+(ht-right.y+y).ToString(System.Globalization.CultureInfo.InvariantCulture)+"}";File.WriteAllText(Path.Combine(DirectoryPath,"studio-frame.json"),meta);
    ioFailures=0;ioFailureSince=0;nextIOReport=0;
   }catch(IOException error){
    float now=Time.realtimeSinceStartup;if(ioFailures++==0)ioFailureSince=now;
    next=now+Mathf.Min(1f,.1f*ioFailures);
    if(ioFailures>=3&&now-ioFailureSince>=3&&now>=nextIOReport){MiDiagnostics.Report("MI-STUDIO-CAPTURE-IO","StudioRuntime.Capture",error,"Studio frame writes have failed for at least three seconds; retrying.");nextIOReport=now+30;}
   }
   catch(Exception e){MiDiagnostics.Report("MI-STUDIO-CAPTURE","StudioRuntime.Capture",e,DirectoryPath);if(log!=null)log("Studio frame: "+e.Message);next=Time.realtimeSinceStartup+1;}
  }
  }finally{ReleaseCapture();}
 }
}
}
