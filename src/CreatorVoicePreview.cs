namespace MoreIterators
{
    // A transient audition policy, never a change to the story save or editor mark.
    // Standalone content and ordinary campaigns continue to use their real mark.
    public static class CreatorVoicePreview
    {
#if !PLAYBACK
        static System.WeakReference requestedGame;
#endif

        internal static void Request(RainWorldGame game, bool enabled)
        {
#if !PLAYBACK
            requestedGame = enabled && game != null ? new System.WeakReference(game) : null;
#endif
        }

        public static bool WithoutMark(Oracle oracle)
        {
#if PLAYBACK
            return false;
#else
            if (
                !MoreIteratorsPlugin.Active
                || CreatorRuntime.Mode != "story"
                || !CreatorVoiceControl.Enabled
                || oracle == null
                || oracle.room == null
                || oracle.room.game == null
                || requestedGame == null
                || !System.Object.ReferenceEquals(requestedGame.Target, oracle.room.game)
            )
                return false;
            var design = IteratorDesign.ForRoom(oracle.room);
            return design != null && design.voice != null && design.voice.enabled && design.voice.volume > 0;
#endif
        }
    }
}
