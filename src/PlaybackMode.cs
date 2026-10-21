namespace MoreIterators {
// Export builds replace this flag and include only the playback control surface.
public static class PlaybackMode {
#if PLAYBACK
 public const bool Enabled=true;
#else
 public const bool Enabled=false;
#endif
}

public sealed class CreatorSpeech {
 readonly Oracle oracle;readonly CreatorVoice voice;int hiddenTicks,pendingTicks;string currentLine="";bool wasShowing,cancelled,pendingHidden;
 CreatorDialogueLine pending;
 public CreatorSpeech(Oracle o){oracle=o;voice=new CreatorVoice(o);}
 public void Tick(){
  voice.Tick(wasShowing&&Showing,CreatorRuntime.Paused);
  if(CreatorRuntime.Paused)return;
  if(pending!=null){if(--pendingTicks<=0){var ready=pending;pending=null;Show(ready,pendingHidden);}return;}
  if(hiddenTicks>0)hiddenTicks--;
  if(wasShowing&&!Showing){voice.Stop();CreatorProjections.EndLine(oracle,this,currentLine);CreatorReadingPresentation.ClearLine(oracle,this);wasShowing=false;}
 }
 bool HasCamera{get{return oracle!=null&&oracle.room!=null&&oracle.room.game!=null&&oracle.room.game.cameras!=null&&oracle.room.game.cameras.Length>0&&oracle.room.game.cameras[0]!=null;}}
 public bool Showing {get{if(pending!=null||hiddenTicks>0)return true;if(!HasCamera)return false;var h=oracle.room.game.cameras[0].hud;return h!=null&&h.dialogBox!=null&&h.dialogBox.ShowingAMessage;}}
 public void Clear(){voice.Stop();pending=null;pendingTicks=0;hiddenTicks=0;wasShowing=false;cancelled=true;CreatorProjections.Pause(oracle,this);CreatorReadingPresentation.ClearLine(oracle,this);if(!HasCamera)return;var h=oracle.room.game.cameras[0].hud;if(h!=null&&h.dialogBox!=null&&h.dialogBox.ShowingAMessage)h.dialogBox.Interrupt("",1);}
 public void Finish(){voice.Stop();pending=null;pendingTicks=0;wasShowing=false;CreatorProjections.Finish(oracle,this,!cancelled);CreatorReadingPresentation.ClearLine(oracle,this);}
 public void Say(CreatorDialogueLine line,bool hide=false){
  if(line==null||System.String.IsNullOrWhiteSpace(line.text))return;
  if(pending!=null&&pending.lineId==line.lineId)return;
  voice.Stop();pending=null;pendingTicks=0;cancelled=false;float before=CreatorProjections.Prepare(oracle,this,line.lineId);
  if(before>0){pending=line;pendingHidden=hide;pendingTicks=UnityEngine.Mathf.Max(1,(int)System.Math.Ceiling(before*40-.0001f));return;}
  Show(line,hide);
 }
 void Show(CreatorDialogueLine line,bool hide){
  currentLine=line.lineId;wasShowing=true;CreatorProjections.Line(oracle,this,currentLine);CreatorReadingPresentation.SetLine(oracle,this,line.presentation);
  bool withoutMark=hide||PlaybackMode.Enabled&&!CreatorRuntime.Mark;
  if(withoutMark){hiddenTicks=UnityEngine.Mathf.Max(1,UnityEngine.Mathf.RoundToInt((line.hold+line.text.Length*.07f)*40));voice.Begin(line,true);return;}
  var h=oracle.room.game.cameras[0].hud;if(h==null)return;if(h.dialogBox==null)h.InitDialogBox();h.dialogBox.Interrupt(line.text,UnityEngine.Mathf.RoundToInt(line.hold*40));voice.Begin(line,false);
 }
}
}
