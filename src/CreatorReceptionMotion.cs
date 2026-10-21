using System;

namespace MoreIterators
{
    // Motion is independent of text, so appearance-only projects still greet visitors.
    public sealed class CreatorReceptionMotion
    {
        const int WorkLeadIn = 40;
        const int MarkedReceptionEnd = 160;
        const int UnmarkedReceptionEnd = 640;
        const int ReleaseDelay = 100;

        string mode = "";
        bool present, hasMark;
        int arrival, quiet = ReleaseDelay + 1;

        public bool Working { get; private set; }
        public int EncounterTicks { get; private set; }
        public bool CanSpeak { get; private set; }

        public CreatorReceptionMotion()
        {
            Working = true;
            EncounterTicks = -1;
            CanSpeak = true;
        }

        public void BeginFrame(bool playerPresent, string nextMode, bool communicationMark = true)
        {
            hasMark = communicationMark;
            if (mode != nextMode)
            {
                mode = nextMode;
                present = false;
                arrival = 0;
                quiet = ReleaseDelay + 1;
            }
            if (playerPresent && !present)
            {
                arrival = 0;
                quiet = 0;
            }
            present = playerPresent;
            arrival = present ? Math.Min(36000, arrival + 1) : 0;

            // Native KeepDistance/Investigate must finish before the first line.
            int approachEnd = WorkLeadIn + (hasMark ? 40 : 480);
            CanSpeak = mode != "story" || !present || arrival > approachEnd;
        }

        public void FinishFrame(bool responseActive, bool manualReception)
        {
            quiet = responseActive ? 0 : Math.Min(ReleaseDelay + 1, quiet + 1);
            int entryEnd = hasMark ? MarkedReceptionEnd : UnmarkedReceptionEnd;
            bool entryReception = mode == "story" && present
                && arrival > WorkLeadIn && arrival <= entryEnd;
            bool finishingResponse = CanSpeak && present && quiet <= ReleaseDelay;
            bool active = manualReception || (mode != "silent"
                && (responseActive || entryReception || finishingResponse));

            Working = !active;
            EncounterTicks = active ? Math.Min(36000, EncounterTicks + 1) : -1;
        }
    }
}
