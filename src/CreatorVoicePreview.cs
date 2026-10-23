namespace MoreIterators {
 // A transient audition policy, never a change to the story save or editor mark.
 // Standalone content and ordinary campaigns continue to use their real mark.
 public static class CreatorVoicePreview {
  public static bool WithoutMark {
   get{return !PlaybackMode.Enabled&&MoreIteratorsPlugin.Active&&CreatorRuntime.Mode=="story"&&CreatorVoiceControl.Enabled;}
  }
 }
}
