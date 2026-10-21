namespace MoreIterators {
using UnityEngine;
public class StudioPose {
 public bool animate=true,playMode=true,hasMark=true,manualLeft,manualRight,recording;
 public string pose="idle",bpPearl="none";public float testGravity=-1;
}
public static class StudioRuntime {
 public static string DirectoryPath {get{return RuntimePaths.DataDirectory;}}
 public static StudioPose Pose=new StudioPose();
 public static bool Recording {get{return false;}}
 public static bool Simulating {get{return true;}}
 public static OracleGraphics Graphics;public static RoomCamera.SpriteLeaser Sprites;public static float FaceAngle;
 public static void UpdatePose(OracleGraphics g){}
}
}
