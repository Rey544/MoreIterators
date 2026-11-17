namespace MoreIterators
{
    using System;
    using System.Collections.Generic;
    using System.Runtime.CompilerServices;
    using UnityEngine;

    public static class NativePearlReaders
    {
        static bool installed;

        sealed class Visit
        {
            public HashSet<EntityID> offered = new HashSet<EntityID>();
            public DataPearl pearl;
            public Reading reading;
        }

        static ConditionalWeakTable<Oracle, Visit> visits = new ConditionalWeakTable<Oracle, Visit>();
        static readonly List<WeakReference> active = new List<WeakReference>();

        public static void Install()
        {
            if (installed)
                return;
            installed = true;
            On.SSOracleBehavior.StartItemConversation += StartSS;
            On.SSOracleBehavior.Update += UpdateSS;
            On.SLOracleBehaviorHasMark.GrabObject += GrabSL;
            On.SLOracleBehaviorHasMark.WillingToInspectItem += WillingSL;
            On.MoreSlugcats.CLOracleBehavior.Update += UpdateCL;
        }

        public static void Remove()
        {
            if (!installed)
                return;
            installed = false;
            On.SSOracleBehavior.StartItemConversation -= StartSS;
            On.SSOracleBehavior.Update -= UpdateSS;
            On.SLOracleBehaviorHasMark.GrabObject -= GrabSL;
            On.SLOracleBehaviorHasMark.WillingToInspectItem -= WillingSL;
            On.MoreSlugcats.CLOracleBehavior.Update -= UpdateCL;
            foreach (var weak in active)
            {
                var reading = weak.Target as Reading;
                if (reading != null)
                    reading.Detach();
            }
            active.Clear();
            visits = new ConditionalWeakTable<Oracle, Visit>();
        }

        static bool Supported(string id)
        {
            return id == "DM" || id == "CL" || id == "SL" || id == "SS";
        }

        static PearlReaderProfile Binding(Oracle oracle, DataPearl pearl)
        {
            if (oracle == null || pearl == null || pearl.AbstractPearl == null || !Supported(oracle.ID.value))
                return null;
            var project = CreatorPearlCatalog.Find(pearl.AbstractPearl.dataPearlType.value);
            if (project == null || project.readers == null)
                return null;
            return Array.Find(
                project.readers,
                r =>
                    r != null
                    && String.IsNullOrEmpty(r.projectId)
                    && r.nativeOracleId == oracle.ID.value
                    && r.oracleId == oracle.ID.value
            );
        }

        static bool Ready(OracleBehavior behavior)
        {
            var oracle = behavior.oracle;
            var room = oracle.room;
            if (room == null || oracle.slatedForDeletetion || !oracle.Consious || !room.game.IsStorySession)
                return false;
            if (!room.game.GetStorySession.saveState.deathPersistentSaveData.theMark)
                return false;
            foreach (var abstractPlayer in room.game.Players)
            {
                var player = abstractPlayer.realizedCreature as Player;
                if (player != null && !player.dead && player.room == room)
                    return true;
            }
            return false;
        }

        static DataPearl Offer(OracleBehavior behavior, Visit visit)
        {
            if (!Ready(behavior))
                return null;
            DataPearl nearest = null;
            float distance = 160f;
            foreach (var layer in behavior.oracle.room.physicalObjects)
                foreach (var item in layer)
                {
                    var pearl = item as DataPearl;
                    if (
                        pearl == null
                        || pearl.slatedForDeletetion
                        || pearl.grabbedBy.Count != 0
                        || visit.offered.Contains(pearl.abstractPhysicalObject.ID)
                        || Binding(behavior.oracle, pearl) == null
                    )
                        continue;
                    float d = Vector2.Distance(behavior.oracle.firstChunk.pos, pearl.firstChunk.pos);
                    if (d < distance)
                    {
                        nearest = pearl;
                        distance = d;
                    }
                }
            return nearest;
        }

        static Reading Begin(OracleBehavior behavior, DataPearl pearl, PearlReaderProfile profile)
        {
            var visit = visits.GetOrCreateValue(behavior.oracle);
            var reading = new Reading(behavior, pearl, profile);
            visit.reading = reading;
            visit.pearl = pearl;
            visit.offered.Add(pearl.abstractPhysicalObject.ID);
            active.RemoveAll(w => !w.IsAlive);
            active.Add(new WeakReference(reading));
            return reading;
        }

        static void StartSS(On.SSOracleBehavior.orig_StartItemConversation orig, SSOracleBehavior self, DataPearl item)
        {
            var profile = Binding(self.oracle, item);
            if (profile == null)
            {
                orig(self, item);
                return;
            }
            if (!Ready(self))
                return;
            if (self.conversation != null || self.pearlConversation != null)
                return;
            try
            {
                self.pearlConversation = Begin(self, item, profile);
                self.talkedAboutThisSession.Add(item.abstractPhysicalObject.ID);
            }
            catch (Exception error)
            {
                MiDiagnostics.Report(
                    "MI-NATIVE-PEARL",
                    "NativePearlReaders.StartSS",
                    error,
                    MiDiagnostics.Context(self.oracle.room)
                );
                self.inspectPearl = null;
            }
        }

        static void UpdateSS(On.SSOracleBehavior.orig_Update orig, SSOracleBehavior self, bool eu)
        {
            orig(self, eu);
            if (!ModManager.MSC)
            {
                var reading = self.pearlConversation as Reading;
                if (reading != null)
                {
                    if (reading.slatedForDeletion)
                    {
                        reading.Detach();
                        return;
                    }
                    if (self.inspectPearl != null && Ready(self))
                    {
                        self.inspectPearl.firstChunk.vel = Vector2.zero;
                        self.inspectPearl.firstChunk.MoveFromOutsideMyUpdate(
                            eu,
                            self.oracle.firstChunk.pos + new Vector2(-18, 7)
                        );
                    }
                    reading.Update();
                    return;
                }
            }
            if (
                !Ready(self)
                || self.inspectPearl != null
                || self.pearlConversation != null
                || self.conversation != null
                || self.currSubBehavior == null
                || self.currSubBehavior.CurrentlyCommunicating
            )
                return;
            if (self.action != SSOracleBehavior.Action.General_Idle)
                return;
            try
            {
                var visit = visits.GetOrCreateValue(self.oracle);
                var pearl = Offer(self, visit);
                if (pearl != null)
                {
                    self.inspectPearl = pearl;
                    if (!ModManager.MSC)
                        self.pearlConversation = Begin(self, pearl, Binding(self.oracle, pearl));
                }
            }
            catch (Exception error)
            {
                MiDiagnostics.Report(
                    "MI-NATIVE-PEARL",
                    "NativePearlReaders.UpdateSS",
                    error,
                    MiDiagnostics.Context(self.oracle.room)
                );
            }
        }

        static bool WillingSL(
            On.SLOracleBehaviorHasMark.orig_WillingToInspectItem orig,
            SLOracleBehaviorHasMark self,
            PhysicalObject item
        )
        {
            if (Binding(self.oracle, item as DataPearl) == null)
                return orig(self, item);
            return Ready(self) && self.currentConversation == null && orig(self, item);
        }

        static void GrabSL(
            On.SLOracleBehaviorHasMark.orig_GrabObject orig,
            SLOracleBehaviorHasMark self,
            PhysicalObject item
        )
        {
            var pearl = item as DataPearl;
            var profile = Binding(self.oracle, pearl);
            if (profile == null || !Ready(self) || !self.State.SpeakingTerms || self.State.neuronsLeft < 4)
            {
                orig(self, item);
                return;
            }
            if (self.currentConversation != null)
                return;
            try
            {
                if (!self.pickedUpItemsThisRealization.Contains(item.abstractPhysicalObject.ID))
                    self.pickedUpItemsThisRealization.Add(item.abstractPhysicalObject.ID);
                if (item.graphicsModule != null)
                    item.graphicsModule.BringSpritesToFront();
                var drawable = item as IDrawable;
                if (drawable != null)
                    foreach (var camera in self.oracle.room.game.cameras)
                    {
                        camera.MoveObjectToContainer(drawable, null);
                        var custom = item as CreatorDataPearl;
                        if (custom != null)
                            custom.RestoreAfterNativePickup(camera);
                    }
                self.holdingObject = item;
                self.currentConversation = Begin(self, pearl, profile);
                if (!self.talkedAboutThisSession.Contains(item.abstractPhysicalObject.ID))
                    self.talkedAboutThisSession.Add(item.abstractPhysicalObject.ID);
            }
            catch (Exception error)
            {
                MiDiagnostics.Report(
                    "MI-NATIVE-PEARL",
                    "NativePearlReaders.GrabSL",
                    error,
                    MiDiagnostics.Context(self.oracle.room)
                );
                self.holdingObject = null;
            }
        }

        static void UpdateCL(
            On.MoreSlugcats.CLOracleBehavior.orig_Update orig,
            MoreSlugcats.CLOracleBehavior self,
            bool eu
        )
        {
            bool noticedBefore = self.hasNoticedPlayer;
            orig(self, eu);
            try
            {
                var visit = visits.GetOrCreateValue(self.oracle);
                if (visit.reading != null)
                {
                    if (
                        self.currentConversation != visit.reading
                        || visit.reading.slatedForDeletion
                        || visit.pearl == null
                        || visit.pearl.slatedForDeletetion
                        || visit.pearl.room != self.oracle.room
                        || visit.pearl.grabbedBy.Count > 0
                    )
                    {
                        visit.reading.Destroy();
                        if (self.currentConversation == visit.reading)
                            self.currentConversation = null;
                        visit.reading = null;
                        visit.pearl = null;
                        return;
                    }
                    if (Ready(self))
                    {
                        visit.pearl.firstChunk.vel = Vector2.zero;
                        visit.pearl.firstChunk.MoveFromOutsideMyUpdate(
                            eu,
                            self.oracle.firstChunk.pos + new Vector2(-18, 7)
                        );
                    }
                    visit.reading.Update();
                    return;
                }

                if (!noticedBefore && self.hasNoticedPlayer)
                    return;
                if (
                    !Ready(self)
                    || !self.hasNoticedPlayer
                    || self.currentConversation != null
                    || self.conversationCooldown > 0
                    || self.dialogBox.messages.Count > 0
                )
                    return;
                var pearl = Offer(self, visit);
                if (pearl != null)
                    self.currentConversation = Begin(self, pearl, Binding(self.oracle, pearl));
            }
            catch (Exception error)
            {
                MiDiagnostics.Report(
                    "MI-NATIVE-PEARL",
                    "NativePearlReaders.UpdateCL",
                    error,
                    MiDiagnostics.Context(self.oracle.room)
                );
            }
        }

        sealed class Reading : SLOracleBehaviorHasMark.MoonConversation
        {
            readonly DataPearl pearl;
            readonly string progressKey;
            readonly bool hasText;
            bool completed;

            public Reading(OracleBehavior behavior, DataPearl pearl, PearlReaderProfile profile)
                : base(Conversation.ID.None, behavior, SLOracleBehaviorHasMark.MiscItemType.NA)
            {
                this.pearl = pearl;
                progressKey =
                    "MI_NATIVE_PEARL:"
                    + RuntimePaths.ModId
                    + ":"
                    + profile.nativeOracleId
                    + ":"
                    + pearl.AbstractPearl.dataPearlType.value;
                bool repeated =
                    behavior.oracle.room.game.GetStorySession.saveState.miscWorldSaveData.unrecognizedSaveStrings.Contains(
                        progressKey
                    );
                var lines = profile.read;
                if (repeated && profile.repeatEnabled && profile.repeat != null && profile.repeat.Length > 0)
                    lines = profile.repeat[UnityEngine.Random.Range(0, profile.repeat.Length)].lines;
                int wait = 0;
                if (lines != null)
                    foreach (var line in lines)
                        if (line != null && !String.IsNullOrWhiteSpace(line.text))
                        {
                            events.Add(
                                new Conversation.TextEvent(
                                    this,
                                    wait,
                                    line.text,
                                    Mathf.RoundToInt(Mathf.Clamp(line.hold, .1f, 60) * 40)
                                )
                            );
                            wait = Mathf.RoundToInt(Mathf.Clamp(line.gap, 0, 60) * 40);
                        }
                hasText = events.Count > 0;
                if (hasText && wait > 0)
                    events.Add(new Conversation.WaitEvent(this, wait));
            }

            protected override void AddEvents()
            {
            }

            public void Detach()
            {
                Destroy();
                var ss = myBehavior as SSOracleBehavior;
                if (ss != null && ss.pearlConversation == this)
                {
                    ss.pearlConversation = null;
                    if (ss.inspectPearl == pearl)
                        ss.inspectPearl = null;
                }
                var sl = myBehavior as SLOracleBehaviorHasMark;
                if (sl != null && sl.currentConversation == this)
                {
                    sl.currentConversation = null;
                    if (sl.holdingObject == pearl)
                        sl.holdingObject = null;
                }
                var cl = myBehavior as MoreSlugcats.CLOracleBehavior;
                if (cl != null && cl.currentConversation == this)
                    cl.currentConversation = null;
            }

            public override void Update()
            {
                if (slatedForDeletion)
                    return;
                if (
                    pearl == null
                    || pearl.slatedForDeletetion
                    || pearl.room != myBehavior.oracle.room
                    || pearl.grabbedBy.Count > 0
                )
                {
                    Destroy();
                    return;
                }
                if (!Ready(myBehavior) || paused)
                    return;
                if (events.Count == 0 && !completed)
                {
                    completed = true;
                    var records = myBehavior
                        .oracle
                        .room
                        .game
                        .GetStorySession
                        .saveState
                        .miscWorldSaveData
                        .unrecognizedSaveStrings;
                    if (hasText && !records.Contains(progressKey))
                        records.Add(progressKey);
                }
                base.Update();
            }
        }
    }
}
