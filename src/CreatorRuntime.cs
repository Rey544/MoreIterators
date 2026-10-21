namespace MoreIterators
{
    using System;
    using System.IO;
    using System.Collections.Generic;
    using UnityEngine;
    // Preview projects are catalogued separately from optional content integrations.
    public static class CreatorRuntime
    {
        public static bool IsRoom(string room)
        {
            return IteratorCatalog.IsGenericRoom(room);
        }
        public static bool IsAI(string room)
        {
            return IsRoom(room)&&IteratorCatalog.IsAI(room);
        }
        public static bool UsesDialogue(string room)
        {
            return IsAI(room)||IteratorCatalog.IsAI(room)&&CreatorDialogueProfile.For(IteratorDesign.ForId(Id(room))).enabled;
        }
        public static string Id(string room)
        {
            return IteratorCatalog.Id(room);
        }
        public static string Root
        {
            get
            {
                return Path.Combine(StudioRuntime.DirectoryPath,"creator");
            }
        }
        public static string Selected="",Mode="silent",Behavior="work",CurrentRoom="";
        public static bool CanControl
        {
            get
            {
                return MoreIteratorsPlugin.IsChamber(CurrentRoom);
            }
        }
        public static bool Paused,Panel,Mark=true,Reset=true,RearGlow=true,Lightning=true,Pearls=true,Glyphs=true;
        public static float PalettePreview=-1;
        static float nextPoll,nextHeartbeat;
        static string control="";
        static bool startupApplyRequested;
        public static void ApplyPendingPreviewUpdate(Menu.InitializationScreen screen)
        {
            // A creator launch may already be queued while the native mod updater is waiting.
            // Use its regular apply operation only when our preview is the sole changed mod.
            if(startupApplyRequested||!File.Exists(Path.Combine(StudioRuntime.DirectoryPath,"launch-room.txt")))return;
            bool ours=false;
            foreach(var mod in ModManager.InstalledMods)if(mod.enabled&&mod.checksumChanged)
            {
                if(mod.id!="moreiterators.core"&&mod.id!="moreiterators.local"&&IteratorIntegrations.FindMod(mod.id)==null)return;
                ours=true;
            }
            if(!ours)return;
            var flags=System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic;
            var prompt=typeof(Menu.InitializationScreen).GetField("needsReapplyDialog",flags);
            var applyer=typeof(Menu.InitializationScreen).GetField("modApplyer",flags);
            if(prompt==null||applyer==null||prompt.GetValue(screen)==null||applyer.GetValue(screen)!=null)return;
            startupApplyRequested=true;
            screen.Singal(null,"REAPPLY");
            UnityEngine.Debug.Log("[More Iterators] Applying queued creator update through the native mod updater.");
        }
        public static readonly Dictionary<string,int> Visits=new Dictionary<string,int>();
        public static List<Dictionary<string,object>> Projects()
        {
            return IteratorCatalog.Projects();
        }
        public static void Menu(Menu.MainMenu m)
        {
            CreatorPearlGallery.Close();
            CreatorBroadcastGallery.Close();
            CreatorStudioMenu.Install(m);
        }
        internal static List<Dictionary<string,object>> MenuProjects()
        {
            var items=Projects().FindAll(p=>IteratorCatalog.Text(p,"ownerMod")=="moreiterators.local"||NativeRoomProjects.IsNative(p));
            foreach(var pending in IteratorCatalog.PendingLocalProjects())if(!items.Exists(p=>IteratorCatalog.Text(p,"projectId")==IteratorCatalog.Text(pending,"projectId")))items.Add(pending);
            items.Sort((a,b)=>String.CompareOrdinal(IteratorCatalog.Text(a,"projectId"),IteratorCatalog.Text(b,"projectId")));return items;
        }
        internal static string Catalog()
        {
            string file=Path.Combine(Root,"registry.json");
            if(!File.Exists(file))return "";
            try
            {
                return File.ReadAllText(file);
            }
            catch(FileNotFoundException)
            {
                // An unapplied/removed preview catalogue is an expected empty state.
                return "";
            }
            catch(Exception error)
            {
                MiDiagnostics.Report("MI-CREATOR-CATALOG","CreatorRuntime.Catalog",error,file);
                return "";
            }
        }
        public static void MenuUpdate(Menu.MainMenu m)
        {
            CreatorStudioMenu.Update(m);
        }
        public static bool Signal(Menu.MainMenu m,string s)
        {
            return CreatorStudioMenu.Signal(m,s);
        }
        public static void Prepare(string entry,string mode,bool mark,bool reset)
        {
            try
            {
                string f=Path.Combine(Root,"launch.json");
                if(File.Exists(f))
                {
                    var v=Json.Deserialize(File.ReadAllText(f)) as Dictionary<string,object>;
                    if(v==null)throw new InvalidDataException("Launch request must be a JSON object.");
                    object requestedEntry;
                    if(!v.TryGetValue("entry",out requestedEntry)||!(requestedEntry is string)||String.IsNullOrEmpty((string)requestedEntry))throw new InvalidDataException("Launch request requires an entry room.");
                    if(Get(v,"entry","")==entry)
                    {
                        mode=Get(v,"mode",mode);
                        mark=Get(v,"hasMark",mark);
                        reset=Get(v,"reset",reset);
                        File.Delete(f);
                    }
                }
            }
            catch(FileNotFoundException)
            {
                // The optional one-shot request can be removed by another reader.
            }
            catch(Exception error)
            {
                MiDiagnostics.Report("MI-LAUNCH-REQUEST","CreatorRuntime.Prepare",error,"entry="+entry);
            }
            Selected=entry;
            CurrentRoom=""; // No camera owns the new preview until its first game tick.
            Mode=mode;
            Mark=mark;
            Reset=reset;
            Behavior="work";
            Paused=false;
            Panel=false;
            if(reset)
            {
                Visits.Remove(Id(entry));
                CreatorDialogue.Reset(Id(entry));
                CreatorPearlReader.Reset(Id(entry));
            }
            Directory.CreateDirectory(Root);
            SaveControl();
            StudioRuntime.Pose=new StudioPose
            {
                animate=true,playMode=true,bpPearl="none",hasMark=mark,pose="idle",recording=false
            }
            ;
            File.WriteAllText(Path.Combine(StudioRuntime.DirectoryPath,"studio-control.json"),JsonUtility.ToJson(StudioRuntime.Pose));
        }
        public static void SaveControl()
        {
            Directory.CreateDirectory(Root);
            var d=new Dictionary<string,object>
            {
                {
                    "projectId",IteratorDesign.ForId(Id(String.IsNullOrEmpty(CurrentRoom)?Selected:CurrentRoom)).projectId
                }
                ,
                {
                    "mode",Mode
                }
                ,
                {
                    "behavior",Behavior
                }
                ,
                {
                    "paused",Paused
                }
                ,
                {
                    "hasMark",Mark
                }
                ,
                {
                    "rearGlow",RearGlow
                }
                ,
                {
                    "lightning",Lightning
                }
                ,
                {
                    "pearls",Pearls
                }
                ,
                {
                    "glyphs",Glyphs
                }
                ,
                {
                    "palettePreview",PalettePreview
                }
            }
            ;
            control=Json.Serialize(d);
            File.WriteAllText(Path.Combine(Root,"control.json"),control);
            SyncPose();
        }
        static T Get<T>(Dictionary<string,object> d,string k,T fallback)
        {
            if(d==null)return fallback;
            object v;
            try
            {
                return d.TryGetValue(k,out v)?(T)Convert.ChangeType(v,typeof(T)):fallback;
            }
            catch(Exception error)
            {
                MiDiagnostics.Report("MI-CONTROL-FIELD","CreatorRuntime.Get",error,"field="+k+" expected="+typeof(T).Name);
                return fallback;
            }
        }
        public static void Tick(RainWorldGame g)
        {
            CurrentRoom=g.cameras.Length>0&&g.cameras[0].room!=null?g.cameras[0].room.abstractRoom.name:"";
            if(!CanControl)Panel=false;
            if(!CanControl&&!MoreIteratorsPlugin.Active)return;
            if(Time.realtimeSinceStartup>nextHeartbeat)
            {
                nextHeartbeat=Time.realtimeSinceStartup+1;
                try
                {
                    var r=g.cameras[0].room;
                    var d=IteratorDesign.ForRoom(r);
                    File.WriteAllText(Path.Combine(Root,"heartbeat.json"),Json.Serialize(new Dictionary<string,object>
                    {
                        {
                            "project",d.projectId
                        }
                        ,
                        {
                            "room",r.abstractRoom.name
                        }
                        ,
                        {
                            "paused",Paused
                        }
                        ,
                        {
                            "panel",Panel
                        }
                        ,
                        {
                            "time",DateTime.UtcNow.ToString("o")
                        }
                    }
                    ));
                }
                catch(Exception error)
                {
                    MiDiagnostics.Report("MI-HEARTBEAT-001","CreatorRuntime.Tick",error,CurrentRoom);
                }
            }
            if(!CanControl&&IteratorCatalog.Find(MoreIteratorsPlugin.SelectedRoom)==null)return;
            if(Time.realtimeSinceStartup>nextPoll)
            {
                nextPoll=Time.realtimeSinceStartup+.2f;
                try
                {
                    string controlFile=Path.Combine(Root,"control.json");
                    if(!File.Exists(controlFile))return;
                    string s=File.ReadAllText(controlFile);
                    if(s!=control)
                    {
                        control=s;
                        var d=Json.Deserialize(s) as Dictionary<string,object>;
                        if(d==null)throw new InvalidDataException("Creator control must be a JSON object.");
                        Mode=Get(d,"mode",Mode);
                        Behavior=Get(d,"behavior",Behavior);
                        Paused=Get(d,"paused",Paused);
                        Mark=Get(d,"hasMark",Mark);
                        RearGlow=Get(d,"rearGlow",RearGlow);
                        Lightning=Get(d,"lightning",Lightning);
                        Pearls=Get(d,"pearls",Pearls);
                        Glyphs=Get(d,"glyphs",Glyphs);
                        PalettePreview=Get(d,"palettePreview",-1f);
                        StudioRuntime.Pose.hasMark=Mark;
                        SyncPose();
                    }
                }
                catch(Exception error)
                {
                    MiDiagnostics.Report("MI-CONTROL-001","CreatorRuntime.Tick",error,CurrentRoom);
                }
            }
        }
        public static void GrantMark()
        {
            Mark=true;
            StudioRuntime.Pose.hasMark=true;
            // Keep preview commands in sync, so the next unrelated control refresh
            // cannot restore the pre-action mark flag. Authored project data is untouched.
            string file=Path.Combine(Root,"control.json");
            try
            {
                Directory.CreateDirectory(Root);
                var state=File.Exists(file)?Json.Deserialize(File.ReadAllText(file)) as Dictionary<string,object>:new Dictionary<string,object>();
                if(state==null)throw new InvalidDataException("Creator control must be a JSON object.");
                state["hasMark"]=true;
                File.WriteAllText(file,Json.Serialize(state));
            }
            catch(Exception error){MiDiagnostics.Report("MI-MARK-CONTROL","CreatorRuntime.GrantMark",error,file);}
            try{SyncPose();}
            catch(Exception error){MiDiagnostics.Report("MI-MARK-POSE","CreatorRuntime.GrantMark",error,CurrentRoom);}
        }
        public static void SyncPose()
        {
            // Control commands must also leave any old offline/static pose preset.
            StudioRuntime.Pose.animate=true;
            StudioRuntime.Pose.playMode=true;
            StudioRuntime.Pose.recording=false;
            StudioRuntime.Pose.manualLeft=StudioRuntime.Pose.manualRight=false;
            StudioRuntime.Pose.pose="idle";
            StudioRuntime.Pose.hasMark=Mark;
            File.WriteAllText(Path.Combine(StudioRuntime.DirectoryPath,"studio-control.json"),JsonUtility.ToJson(StudioRuntime.Pose));
        }
        public static void ToggleLayer(string name)
        {
            var design=IteratorDesign.ForId(Id(CurrentRoom));
            var field=typeof(IteratorLayers).GetField(name);
            if(field==null||field.FieldType!=typeof(bool))return;
            field.SetValue(design.layers,!(bool)field.GetValue(design.layers));
            var file=RuntimePaths.DesignPath(design.oracleId);
            var json=Json.Deserialize(File.ReadAllText(file)) as Dictionary<string,object>;
            json["layers"]=Json.Deserialize(JsonUtility.ToJson(design.layers));
            File.WriteAllText(file,Json.Serialize(json));
        }
        public static void Palette(Texture2D t,RoomCamera cam,int palette)
        {
            var room=MoreIteratorsPlugin.PaletteRoom(cam);
            if(room==null||!IsAI(room.abstractRoom.name))return;
            var d=IteratorDesign.ForRoom(room);
            Color theme=IteratorDesign.C(palette==25?d.roomReceptionColor:d.roomWorkColor);
            for(int y=0;y<t.height;y++)for(int x=0;x<Mathf.Min(30,t.width);x++)
            {
                if(y%8>5)continue;
                Color c=t.GetPixel(x,y);
                float v=c.grayscale;
                Color tint=Color.Lerp(new Color(v,v,v,c.a),theme*v*1.6f,.55f);
                t.SetPixel(x,y,tint);
            }
            t.Apply(false);
        }
    }
    public class CreatorEncounter:UpdatableAndDeletable
    {
        public static int Restart;
        int restart;
        readonly Oracle oracle;
        readonly List<CreatorWorkPearl> pearls=new List<CreatorWorkPearl>();
        readonly List<WorkPearlGlyph> labels=new List<WorkPearlGlyph>();
        readonly CreatorWorkPearlBounds pearlBounds;
        readonly HashSet<string> read=new HashSet<string>();
        readonly CreatorDialogue dialogue;
        readonly CreatorPearlReader reader;
        readonly CreatorAudioChannel music=new CreatorAudioChannel();
        int tick,workTick,revision;Weapon lastHitWeapon;int lastHitFrame=-1;
        CreatorReceptionMotion reception=new CreatorReceptionMotion();
        int receptionPhase=-1;
        static bool HasEncounter(Oracle o){foreach(var item in o.room.updateList){var encounter=item as CreatorEncounter;if(encounter!=null&&encounter.oracle==o&&!encounter.slatedForDeletetion)return true;}return false;}
        public static bool HandlesHit(Oracle o,Weapon weapon){return o!=null&&o.room!=null&&o.oracleBehavior is IteratorBehavior&&IteratorCatalog.IsAI(o.room.abstractRoom.name)&&CreatorRuntime.UsesDialogue(o.room.abstractRoom.name)&&weapon!=null&&weapon.thrownBy is Player&&(weapon is Rock||weapon is Spear)&&CreatorDialogueProfile.For(IteratorDesign.ForRoom(o.room)).affinity.enabled&&(CreatorRuntime.Mode=="story"||CreatorRuntime.Mode=="read")&&!StudioRuntime.Recording&&HasEncounter(o);}
        public static void Hit(Oracle o,Weapon weapon){foreach(var item in o.room.updateList){var encounter=item as CreatorEncounter;if(encounter!=null&&encounter.oracle==o){encounter.ReactToHit(weapon);return;}}MiDiagnostics.Warn("MI-AFFINITY-NO-ENCOUNTER","CreatorEncounter.Hit","Owned hit arrived before encounter creation.",IteratorDesign.ForRoom(o.room).oracleId);}
        void ReactToHit(Weapon weapon){if(lastHitWeapon==weapon&&lastHitFrame==Time.frameCount)return;lastHitWeapon=weapon;lastHitFrame=Time.frameCount;var d=D;bool spear=weapon is Spear;CreatorAffinity.Update(oracle,d);string tier=CreatorAffinity.Hit(oracle,d,spear);var rules=CreatorDialogueProfile.For(d).affinity;bool responding=reader.TryRespond((spear?rules.attackSpear:rules.attackRock).For(tier),(spear?"attackSpear:":"attackRock:")+tier,weapon.thrownBy as Player);if(responding)dialogue.Suspend();MiDiagnostics.Info("affinity.hit","oracle="+d.oracleId+" weapon="+(spear?"spear":"rock")+" preTier="+tier+" value="+CreatorAffinity.Get(oracle,d).value+" response="+responding);}
        float blend=1f;
        public bool Working=true;
        IteratorDesign D
        {
            get
            {
                return IteratorDesign.ForRoom(room);
            }
        }
        public CreatorEncounter(Oracle o)
        {
            oracle=o;
            room=o.room;
            restart=Restart;
            dialogue=new CreatorDialogue(o);
            reader=new CreatorPearlReader(o);
            pearlBounds=new CreatorWorkPearlBounds(room,oracle.firstChunk.pos);
            Resize();
        }
        void Resize()
        {
            int count=Mathf.Clamp(D.pearlCount,0,80);
            while(pearls.Count>count)
            {
                int i=pearls.Count-1;
                var removed=pearls[i];
                if(removed.grabbedBy.Count>0)break;
                room.abstractRoom.RemoveEntity(removed.abstractPhysicalObject);
                removed.Destroy();
                labels[i].Destroy();
                pearls.RemoveAt(i);
                labels.RemoveAt(i);
            }
            while(pearls.Count<count)
            {
                int i=pearls.Count;
                Vector2 p;
                if(!pearlBounds.TryResolve(CreatorWorkPearlMotion.RestPosition(D,i,count,pearlBounds),out p))break;
                var pearl=CreatorWorkPearl.Create(room,p,i);
                pearls.Add(pearl);
                var g=new WorkPearlGlyph(p,D.PearlGlyph(i));
                labels.Add(g);
                room.AddObject(g);
            }
        }
        public override void Destroy()
        {
            music.Stop();
            if(reader!=null)reader.Cancel();
            foreach(var pearl in pearls)pearl.StopDriving();
            CreatorReadingPresentation.Clear(oracle);
            base.Destroy();
            CreatorOracleLifecycle.ReleaseEncounter(oracle);
        }
        public override void Update(bool eu)
        {
            base.Update(eu);
            if(oracle.slatedForDeletetion)
            {
                CreatorDialogueActions.For(oracle).Cancel();
                foreach(var g in labels)g.Destroy();
                Destroy();
                return;
            }
            CreatorDialogueActions.For(oracle).Update();
            CreatorPearlOffers.Pending(oracle); // Invalidate queued offers even while encounter playback is paused.
            if(CreatorRuntime.Paused){music.Update(room,CreatorMusicSettings.Select(D,Working,reader.Active||reader.Receiving),true);return;}
            tick++;
            var d=D;
            if(tick%20==0)Resize();
            Player player=null;
            foreach(var a in room.game.Players)
            {
                var p=a.realizedCreature as Player;
                if(p!=null&&p.room==room&&!p.dead)
                {
                    player=p;
                    break;
                }
            }
            dialogue.ObservePresence(player);
            reader.ObservePresence(player);
            if(restart!=Restart){restart=Restart;reception=new CreatorReceptionMotion();}
            bool communicationMark=IteratorBehavior.HasCommunicationMark(oracle);
            reception.BeginFrame(player!=null,CreatorRuntime.Mode,communicationMark);
            CreatorAffinity.Update(oracle,d);
            bool actionActive=CreatorDialogueActions.For(oracle).Active;
            if(!actionActive&&!reader.Active&&reception.CanSpeak)dialogue.Update(player,pearls,d);
            actionActive=CreatorDialogueActions.For(oracle).Active;
            bool reading=actionActive||((reception.CanSpeak||reader.Active)&&reader.Update(player,d,!dialogue.Speaking,dialogue.InitialStoryComplete||CreatorRuntime.Mode=="read"||!CreatorDialogueProfile.For(d).enabled));
            if(reading)dialogue.ObserveHeld(pearls);
            bool speaking=reading||reader.Receiving||dialogue.Speaking;
            reception.FinishFrame(speaking,CreatorRuntime.Behavior=="reception");
            Working=reception.Working;
            music.Update(room,CreatorMusicSettings.Select(d,Working,reader.Active||reader.Receiving),player!=null);
            int nextPhase=Working?0:reception.EncounterTicks<(communicationMark?40:120)?1:!communicationMark&&reception.EncounterTicks<480?2:3;
            if(nextPhase!=receptionPhase){
                receptionPhase=nextPhase;
                MiDiagnostics.Info("encounter.phase","oracle="+d.oracleId+" phase="+(nextPhase==0?"work":nextPhase==1?"approach":nextPhase==2?"investigate":"reception")+" ticks="+reception.EncounterTicks+" mark="+communicationMark);
            }
            CreatorProjections.SetWorking(oracle,Working);
            var b=oracle.oracleBehavior as IteratorBehavior;
            if(b!=null)
            {
                b.encounterActive=!Working;
                b.encounterTicks=reception.EncounterTicks;
                b.requestedGravity=Mathf.MoveTowards(b.requestedGravity,Working?0:.18f,.002f);
                if(!CreatorDialogueActions.For(oracle).Active){b.killFac=0;b.lastKillFac=0;}
            }
            if(Working)workTick++;
            room.gravity=b==null?Mathf.MoveTowards(room.gravity,Working?0:.18f,.002f):b.requestedGravity;
            float target=CreatorRuntime.PalettePreview>=0?CreatorRuntime.PalettePreview:Working?1:0;
            blend=Mathf.MoveTowards(blend,target,1f/Mathf.Max(1,d.roomTransition*40));
            var cam=room.game.cameras[0];
            if(cam.room==room&&(tick%5==0||revision!=IteratorDesign.Revision))
            {
                if(revision!=IteratorDesign.Revision)
                {
                    cam.paletteA=-1;
                    cam.paletteB=-1;
                }
                revision=IteratorDesign.Revision;
                cam.ChangeBothPalettes(25,26,blend);
            }
            for(int i=0;i<pearls.Count;i++)
            {
                var p=pearls[i];
                if(Working&&p.CanDrive&&p.room==room)
                {
                    bool look;Vector2 pearlTarget;
                    var requested=CreatorWorkPearlMotion.WorkingPosition(d,i,pearls.Count,workTick,oracle.firstChunk.pos,pearlBounds,out look);
                    if(pearlBounds.TryResolve(requested,out pearlTarget))p.DriveTo(pearlTarget);else p.StopDriving();
                    if(look)oracle.oracleBehavior.lookPoint=p.pos;
                }
                else p.StopDriving();
                labels[i].setPos=p.pos+Vector2.up*12;
                labels[i].setScale=!p.slatedForDeletetion&&p.room==room?.6f:0;
                labels[i].color=IteratorDesign.C(d.pearlGlyphColor);
                labels[i].opacity=d.pearlGlyphOpacity;
                labels[i].glyphs[0]=d.PearlGlyph(i);
            }
            if(!PlaybackMode.Enabled&&tick%40==0)File.WriteAllText(Path.Combine(CreatorRuntime.Root,"status.json"),Json.Serialize(new Dictionary<string,object>
            {
                {
                    "project",d.projectId
                }
                ,
                {
                    "room",room.abstractRoom.name
                }
                ,
                {
                    "mode",CreatorRuntime.Mode
                }
                ,
                {
                    "working",Working
                }
                ,
                {
                    "dialogueLine",reading?reader.CurrentText:dialogue.CurrentText
                }
                ,
                {
                    "readingPearl",reader.PearlId
                }
                ,
                {
                    "awaitingReturn",dialogue.AwaitingReturn
                }
                ,
                {
                    "receiving",reader.Receiving
                }
                ,
                {
                    "firstComplete",dialogue.InitialStoryComplete
                }
                ,
                {
                    "pearls",pearls.Count
                }
                ,
                {
                    "revision",IteratorDesign.Revision
                }
                ,
                {
                    "time",DateTime.UtcNow.ToString("o")
                }
            }
            ));
        }
    }
}
