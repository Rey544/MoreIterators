namespace MoreIterators
{
    using System;
    using System.Collections.Generic;
    using BepInEx;
    using UnityEngine;
    using MonoMod.Cil;
    [BepInPlugin("moreiterators.core", "更多迭代器", BuildVersion.Plugin)]
    public class MoreIteratorsPlugin : BaseUnityPlugin
    {
        public static MoreIteratorsPlugin Instance;
        public static bool Active;
        public static string SelectedRoom="";
        public static bool IsChamber(string name)
        {
            return IteratorCatalog.IsAI(name);
        }
        static bool constructingCustomOracle;
        bool previewSessionCaptured;
        RainWorld previewOwner;
        bool hooksInstalled;
        static bool markPatchReady;
        readonly List<System.Action> removeHooks = new List<System.Action>();
        bool PreviewSessionActive
        {
            get
            {
                return Active && previewSessionCaptured;
            }
        }
        SaveState previousSave, previousStarved;
        SlugcatStats.Name previousCharacter;
        bool previousRain;
        int appliedRoomPalette=-1,appliedRoomRevision=-1;
        readonly Dictionary<RoomCamera,Room> paletteRooms=new Dictionary<RoomCamera,Room>();
        readonly Dictionary<OracleGraphics,int> extras=new Dictionary<OracleGraphics,int>();
        void OnEnable()
        {
            Instance=this;
            MiDiagnostics.Initialize(Logger);
            if(hooksInstalled)
            {
                MiDiagnostics.Warn("MI-HOOK-REPEAT","OnEnable","Hooks are already installed.","No duplicate hooks added.");
                return;
            }
            try
            {
                RuntimePaths.Initialize();
                InstallHooks();
                hooksInstalled=true;
            }
            catch(Exception error)
            {
                MiDiagnostics.Report("MI-STARTUP-001","OnEnable",error,"Hook installation rolled back.");
                StopCapture();
                RemoveHooks();
            }
        }
        void StopCapture()
        {
#if !PLAYBACK
            try { StopAllCoroutines(); }
            catch(Exception error) { MiDiagnostics.Report("MI-CAPTURE-STOP","StopCapture",error,"Stopping studio capture."); }
            try { StudioRuntime.ReleaseCapture(); }
            catch(Exception error) { MiDiagnostics.Report("MI-CAPTURE-RELEASE","StopCapture",error,"Releasing studio capture texture."); }
#endif
        }
        void RemoveHooks()
        {
            for(int i=removeHooks.Count-1;i>=0;i--)try
            {
                removeHooks[i]();
            }
            catch(Exception error)
            {
                MiDiagnostics.Report("MI-HOOK-REMOVE","OnDisable",error,"index="+i);
            }
            removeHooks.Clear();
            hooksInstalled=false;
        }
        void OnDisable()
        {
            try
            {
                RestorePreviewSession();
            }
            catch(Exception error)
            {
                MiDiagnostics.Report("MI-PREVIEW-RESTORE","OnDisable",error,"Hook removal continues even if an extension reset fails.");
            }
            finally
            {
                StopCapture();
                try { CreatorOverseers.Shutdown(); }
                catch(Exception error) { MiDiagnostics.Report("MI-OVERSEER-SHUTDOWN","OnDisable",error,"Cleaning project observers."); }
                try { CreatorProjections.Shutdown(); }
                catch(Exception error) { MiDiagnostics.Report("MI-PROJECTION-SHUTDOWN","OnDisable",error,"Cleaning owned projections."); }
                try { RemoveHooks(); }
                finally { MiDiagnostics.Shutdown(); }
            }
        }
        void InstallHooks()
        {
            // Optional third-party compatibility is installed after mod startup,
            // so the target assembly is present regardless of plugin load order.
            removeHooks.Add(RevivifyCompatibility.Dispose);
            var revivifyReady=new On.RainWorld.hook_PostModsInit((orig,rainWorld)=>
            {
                orig(rainWorld);
                RevivifyCompatibility.Install();
            });
            On.RainWorld.PostModsInit+=revivifyReady;
            removeHooks.Add(delegate { On.RainWorld.PostModsInit-=revivifyReady; });
            if(ModManager.InitializationScreenFinished)RevivifyCompatibility.Install();
            CreatorOracleLifecycle.Install(removeHooks);
            CreatorNativeVoiceGuard.Install(removeHooks);
            CreatorOverseers.Install(removeHooks);
            CreatorPearlOffers.Install(removeHooks);
            WarpRoomLabels.Install(removeHooks);
#if !PLAYBACK
            CreatorStudioMenu.InstallHooks(removeHooks);
#endif
#if !PLAYBACK
            var registeredHook0=new On.Menu.InitializationScreen.hook_Update((orig,s)=>
            {
                MiDiagnostics.Hit("On.Menu.InitializationScreen.Update",CreatorRuntime.CurrentRoom);
                try
                {
                    orig(s);
                    MiDiagnostics.Tick(s.manager);
                    CreatorRuntime.ApplyPendingPreviewUpdate(s);
                }
                catch(Exception error)
                {
                    MiDiagnostics.Report("MI-HOOK-001","On.Menu.InitializationScreen.Update",error,CreatorRuntime.CurrentRoom);
                    throw;
                }
            }
            );
            On.Menu.InitializationScreen.Update += registeredHook0;
            removeHooks.Add(delegate
            {
                On.Menu.InitializationScreen.Update -= registeredHook0;
            }
            );
            MiDiagnostics.Info("hook.install","On.Menu.InitializationScreen.Update");
#endif
            var registeredHook1=new On.AbstractPhysicalObject.hook_Realize((orig,a)=>
            {
                MiDiagnostics.Hit("On.AbstractPhysicalObject.Realize",CreatorRuntime.CurrentRoom);
                try
                {
                    if(a.realizedObject==null&&(CreatorDataPearl.Realize(a)||CreatorWorkPearl.Realize(a)))return;
                    orig(a);
                }
                catch(Exception error)
                {
                    MiDiagnostics.Report("MI-HOOK-001","On.AbstractPhysicalObject.Realize",error,CreatorRuntime.CurrentRoom);
                    throw;
                }
            }
            );
            On.AbstractPhysicalObject.Realize += registeredHook1;
            removeHooks.Add(delegate
            {
                On.AbstractPhysicalObject.Realize -= registeredHook1;
            }
            );
            MiDiagnostics.Info("hook.install","On.AbstractPhysicalObject.Realize");
            var registeredHook2=new On.OracleGraphics.Halo.hook_Update((orig,halo)=>
            {
                MiDiagnostics.Hit("On.OracleGraphics.Halo.Update",CreatorRuntime.CurrentRoom);
                try { IteratorHalo.Update(orig,halo); }
                catch(Exception error)
                {
                    MiDiagnostics.Report("MI-HOOK-001","On.OracleGraphics.Halo.Update",error,CreatorRuntime.CurrentRoom);
                    throw;
                }
            });
            On.OracleGraphics.Halo.Update += registeredHook2;
            removeHooks.Add(delegate
            {
                On.OracleGraphics.Halo.Update -= registeredHook2;
            }
            );
            MiDiagnostics.Info("hook.install","On.OracleGraphics.Halo.Update");
            var registeredHook3=new On.SSOracleBehavior.hook_SeePlayer((orig,b)=>
            {
                MiDiagnostics.Hit("On.SSOracleBehavior.SeePlayer",CreatorRuntime.CurrentRoom);
                try
                {
                    if(CreatorOracleLifecycle.SuppressNativeStory(b,"SSOracleBehavior.SeePlayer",true))return;
                    if(!(b is IteratorBehavior)||(!StudioRuntime.Recording&&!CreatorRuntime.UsesDialogue(b.oracle.room.abstractRoom.name)))orig(b);
                }
                catch(Exception error)
                {
                    MiDiagnostics.Report("MI-HOOK-001","On.SSOracleBehavior.SeePlayer",error,CreatorRuntime.CurrentRoom);
                    throw;
                }
            }
            );
            On.SSOracleBehavior.SeePlayer += registeredHook3;
            removeHooks.Add(delegate
            {
                On.SSOracleBehavior.SeePlayer -= registeredHook3;
            }
            );
            MiDiagnostics.Info("hook.install","On.SSOracleBehavior.SeePlayer");
            var registeredHook4=new On.SSOracleBehavior.hook_NewAction((orig,b,a)=>
            {
                MiDiagnostics.Hit("On.SSOracleBehavior.NewAction",CreatorRuntime.CurrentRoom);
                try
                {
                    if(CreatorOracleLifecycle.SuppressNativeStory(b,"SSOracleBehavior.NewAction",false))return;
                    if(!(b is IteratorBehavior)||(!StudioRuntime.Recording&&!CreatorRuntime.UsesDialogue(b.oracle.room.abstractRoom.name)))orig(b,a);
                }
                catch(Exception error)
                {
                    MiDiagnostics.Report("MI-HOOK-001","On.SSOracleBehavior.NewAction",error,CreatorRuntime.CurrentRoom);
                    throw;
                }
            }
            );
            On.SSOracleBehavior.NewAction += registeredHook4;
            removeHooks.Add(delegate
            {
                On.SSOracleBehavior.NewAction -= registeredHook4;
            }
            );
            MiDiagnostics.Info("hook.install","On.SSOracleBehavior.NewAction");
            Application.runInBackground=true;
            var registeredHook5=new On.DataPearl.hook_ApplyPalette((orig,p,s,c,pal)=>
            {
                MiDiagnostics.Hit("On.DataPearl.ApplyPalette",CreatorRuntime.CurrentRoom);
                try
                {
                    orig(p,s,c,pal);
                    var creator=p as CreatorWorkPearl;
                    if(creator!=null)creator.Paint(s);
                }
                catch(Exception error)
                {
                    MiDiagnostics.Report("MI-HOOK-001","On.DataPearl.ApplyPalette",error,CreatorRuntime.CurrentRoom);
                    throw;
                }
            }
            );
            On.DataPearl.ApplyPalette += registeredHook5;
            removeHooks.Add(delegate
            {
                On.DataPearl.ApplyPalette -= registeredHook5;
            }
            );
            MiDiagnostics.Info("hook.install","On.DataPearl.ApplyPalette");
            var registeredHook6=new On.DataPearl.hook_DrawSprites((orig,p,s,c,t,pos)=>
            {
                MiDiagnostics.Hit("On.DataPearl.DrawSprites",CreatorRuntime.CurrentRoom);
                try
                {
                    orig(p,s,c,t,pos);
                    var creator=p as CreatorWorkPearl;
                    if(creator!=null&&!creator.slatedForDeletetion&&creator.room==c.room)creator.Paint(s);
                }
                catch(Exception error)
                {
                    MiDiagnostics.Report("MI-HOOK-001","On.DataPearl.DrawSprites",error,CreatorRuntime.CurrentRoom);
                    throw;
                }
            }
            );
            On.DataPearl.DrawSprites += registeredHook6;
            removeHooks.Add(delegate
            {
                On.DataPearl.DrawSprites -= registeredHook6;
            }
            );
            MiDiagnostics.Info("hook.install","On.DataPearl.DrawSprites");
            var registeredHook7=new On.OverseerAbstractAI.hook_RoomAllowed((orig,ai,room)=>
            {
                MiDiagnostics.Hit("On.OverseerAbstractAI.RoomAllowed",CreatorRuntime.CurrentRoom);
                try
                {
                    bool ownedAllowed;if(CreatorOverseers.RoomAllowed(ai,room,out ownedAllowed))return ownedAllowed;
                    if(room>=ai.world.firstRoomIndex&&room<ai.world.firstRoomIndex+ai.world.NumberOfRooms&&CreatorRuntime.IsRoom(ai.world.GetAbstractRoom(room).name))return false;
                    return orig(ai,room);
                }
                catch(Exception error)
                {
                    MiDiagnostics.Report("MI-HOOK-001","On.OverseerAbstractAI.RoomAllowed",error,CreatorRuntime.CurrentRoom);
                    throw;
                }
            }
            );
            On.OverseerAbstractAI.RoomAllowed += registeredHook7;
            removeHooks.Add(delegate
            {
                On.OverseerAbstractAI.RoomAllowed -= registeredHook7;
            }
            );
            MiDiagnostics.Info("hook.install","On.OverseerAbstractAI.RoomAllowed");
            var registeredHook8=new On.OverseerAbstractAI.hook_PlayerGuideUpdate((orig,ai,time)=>
            {
                MiDiagnostics.Hit("On.OverseerAbstractAI.PlayerGuideUpdate",CreatorRuntime.CurrentRoom);
                try
                {
                    if(ai.world.game.Players.Count>0&&CreatorRuntime.IsRoom(ai.world.game.Players[0].Room.name))
                    {
                        ai.PlayerGuideGoAway(400);
                        return;
                    }
                    orig(ai,time);
                }
                catch(Exception error)
                {
                    MiDiagnostics.Report("MI-HOOK-001","On.OverseerAbstractAI.PlayerGuideUpdate",error,CreatorRuntime.CurrentRoom);
                    throw;
                }
            }
            );
            On.OverseerAbstractAI.PlayerGuideUpdate += registeredHook8;
            removeHooks.Add(delegate
            {
                On.OverseerAbstractAI.PlayerGuideUpdate -= registeredHook8;
            }
            );
            MiDiagnostics.Info("hook.install","On.OverseerAbstractAI.PlayerGuideUpdate");
            var registeredHook9=new On.Menu.MainMenu.hook_ctor(MenuCtor);
            On.Menu.MainMenu.ctor += registeredHook9;
            removeHooks.Add(delegate
            {
                On.Menu.MainMenu.ctor -= registeredHook9;
            }
            );
            MiDiagnostics.Info("hook.install","On.Menu.MainMenu.ctor");
            var registeredHook10=new On.RoomCamera.hook_LoadPalette(LoadRoomPalette);
            On.RoomCamera.LoadPalette += registeredHook10;
            removeHooks.Add(delegate
            {
                On.RoomCamera.LoadPalette -= registeredHook10;
            }
            );
            MiDiagnostics.Info("hook.install","On.RoomCamera.LoadPalette");
            var registeredHook11=new On.RoomCamera.hook_ChangeRoom(ChangeCameraRoom);
            On.RoomCamera.ChangeRoom += registeredHook11;
            removeHooks.Add(delegate
            {
                On.RoomCamera.ChangeRoom -= registeredHook11;
            }
            );
            MiDiagnostics.Info("hook.install","On.RoomCamera.ChangeRoom");
#if PLAYBACK
            var registeredHook12=new On.Menu.MainMenu.hook_Update((orig,m)=>
            {
                MiDiagnostics.Hit("On.Menu.MainMenu.Update",CreatorRuntime.CurrentRoom);
                try
                {
                    orig(m);
                    MiDiagnostics.Tick(m.manager);
                    CreatorRuntime.MenuUpdate(m);
                }
                catch(Exception error)
                {
                    MiDiagnostics.Report("MI-HOOK-001","On.Menu.MainMenu.Update",error,CreatorRuntime.CurrentRoom);
                    throw;
                }
            }
            );
            On.Menu.MainMenu.Update += registeredHook12;
            removeHooks.Add(delegate
            {
                On.Menu.MainMenu.Update -= registeredHook12;
            }
            );
            MiDiagnostics.Info("hook.install","On.Menu.MainMenu.Update");
#else
            var registeredHook13=new On.Menu.MainMenu.hook_Update((orig,m)=>
            {
                MiDiagnostics.Hit("On.Menu.MainMenu.Update",CreatorRuntime.CurrentRoom);
                try
                {
                    orig(m);
                    MiDiagnostics.Tick(m.manager);
                    CreatorRuntime.MenuUpdate(m);
                    string f=System.IO.Path.Combine(StudioRuntime.DirectoryPath,"launch-room.txt");
                    if(System.IO.File.Exists(f))
                    {
                        string room=CreatorLaunch.Normalize(System.IO.File.ReadAllText(f).Trim());
                        System.IO.File.Delete(f);
                        if(!IteratorIntegrations.Launch(m,room))
                        {
                            CreatorRuntime.Prepare(room,CreatorRuntime.Mode,CreatorRuntime.Mark,CreatorRuntime.Reset);
                            LaunchPreview(m,room);
                        }
                    }
                }
                catch(Exception error)
                {
                    MiDiagnostics.Report("MI-HOOK-001","On.Menu.MainMenu.Update",error,CreatorRuntime.CurrentRoom);
                    throw;
                }
            }
            );
            On.Menu.MainMenu.Update += registeredHook13;
            removeHooks.Add(delegate
            {
                On.Menu.MainMenu.Update -= registeredHook13;
            }
            );
            MiDiagnostics.Info("hook.install","On.Menu.MainMenu.Update");
#endif
            var registeredHook14=new On.Menu.MainMenu.hook_Singal(Signal);
            On.Menu.MainMenu.Singal += registeredHook14;
            removeHooks.Add(delegate
            {
                On.Menu.MainMenu.Singal -= registeredHook14;
            }
            );
            MiDiagnostics.Info("hook.install","On.Menu.MainMenu.Singal");
            var registeredHook15=new On.Room.hook_ReadyForAI(Ready);
            On.Room.ReadyForAI += registeredHook15;
            removeHooks.Add(delegate
            {
                On.Room.ReadyForAI -= registeredHook15;
            }
            );
            MiDiagnostics.Info("hook.install","On.Room.ReadyForAI");
            var registeredHook16=new On.Room.hook_Update((orig,r)=>
            {
                MiDiagnostics.Hit("On.Room.Update",CreatorRuntime.CurrentRoom);
                try
                {
                    orig(r);
                    CreatorBroadcastRuntime.Tick(r);
                }
                catch(Exception error)
                {
                    MiDiagnostics.Report("MI-HOOK-001","On.Room.Update",error,CreatorRuntime.CurrentRoom);
                    throw;
                }
            }
            );
            On.Room.Update += registeredHook16;
            removeHooks.Add(delegate
            {
                On.Room.Update -= registeredHook16;
            }
            );
            MiDiagnostics.Info("hook.install","On.Room.Update");
            var registeredHook17=new On.Player.hook_ProcessChatLog((orig,player)=>
            {
                MiDiagnostics.Hit("On.Player.ProcessChatLog",CreatorRuntime.CurrentRoom);
                try { CreatorBroadcastRuntime.Process(orig,player); }
                catch(Exception error)
                {
                    MiDiagnostics.Report("MI-HOOK-001","On.Player.ProcessChatLog",error,CreatorRuntime.CurrentRoom);
                    throw;
                }
            });
            On.Player.ProcessChatLog += registeredHook17;
            removeHooks.Add(delegate
            {
                On.Player.ProcessChatLog -= registeredHook17;
            }
            );
            MiDiagnostics.Info("hook.install","On.Player.ProcessChatLog");
            var registeredHook18=new On.OracleGraphics.hook_SkinColor(Skin);
            On.OracleGraphics.SkinColor += registeredHook18;
            removeHooks.Add(delegate
            {
                On.OracleGraphics.SkinColor -= registeredHook18;
            }
            );
            MiDiagnostics.Info("hook.install","On.OracleGraphics.SkinColor");
            var registeredHook19=new On.RoomCamera.hook_ChangeBothPalettes((orig,cam,a,b,mix)=>
            {
                MiDiagnostics.Hit("On.RoomCamera.ChangeBothPalettes",CreatorRuntime.CurrentRoom);
                try
                {
                    if(cam.room!=null&&IsChamber(cam.room.abstractRoom.name)&&!CreatorRuntime.UsesDialogue(cam.room.abstractRoom.name))return;
                    if(IteratorBehavior.SuppressNativePalette(cam.room,a,b))return;
                    orig(cam,a,b,mix);
                }
                catch(Exception error)
                {
                    MiDiagnostics.Report("MI-HOOK-001","On.RoomCamera.ChangeBothPalettes",error,CreatorRuntime.CurrentRoom);
                    throw;
                }
            }
            );
            On.RoomCamera.ChangeBothPalettes += registeredHook19;
            removeHooks.Add(delegate
            {
                On.RoomCamera.ChangeBothPalettes -= registeredHook19;
            }
            );
            MiDiagnostics.Info("hook.install","On.RoomCamera.ChangeBothPalettes");
            var registeredHook20=new On.OracleGraphics.hook_ApplyPalette(Palette);
            On.OracleGraphics.ApplyPalette += registeredHook20;
            removeHooks.Add(delegate
            {
                On.OracleGraphics.ApplyPalette -= registeredHook20;
            }
            );
            MiDiagnostics.Info("hook.install","On.OracleGraphics.ApplyPalette");
            var registeredHook21=new On.OracleGraphics.hook_InitiateSprites(Sprites);
            On.OracleGraphics.InitiateSprites += registeredHook21;
            removeHooks.Add(delegate
            {
                On.OracleGraphics.InitiateSprites -= registeredHook21;
            }
            );
            MiDiagnostics.Info("hook.install","On.OracleGraphics.InitiateSprites");
            var registeredHook22=new On.OracleGraphics.hook_DrawSprites(Draw);
            On.OracleGraphics.DrawSprites += registeredHook22;
            removeHooks.Add(delegate
            {
                On.OracleGraphics.DrawSprites -= registeredHook22;
            }
            );
            MiDiagnostics.Info("hook.install","On.OracleGraphics.DrawSprites");
            var registeredHook23=new ILContext.Manipulator(SafeMark);
            IL.SSOracleBehavior.ctor += registeredHook23;
            removeHooks.Add(delegate
            {
                IL.SSOracleBehavior.ctor -= registeredHook23;
            }
            );
            MiDiagnostics.Info("hook.install","IL.SSOracleBehavior.ctor");
            var registeredHook24=new On.PlayerProgression.hook_GetOrInitiateSaveState(PreviewSave);
            On.PlayerProgression.GetOrInitiateSaveState += registeredHook24;
            removeHooks.Add(delegate
            {
                On.PlayerProgression.GetOrInitiateSaveState -= registeredHook24;
            }
            );
            MiDiagnostics.Info("hook.install","On.PlayerProgression.GetOrInitiateSaveState");
            var registeredHook25=new On.PlayerProgression.hook_SaveToDisk((orig,p,a,b,c)=>
            {
                MiDiagnostics.Hit("On.PlayerProgression.SaveToDisk",CreatorRuntime.CurrentRoom);
                try
                {
                    MiDiagnostics.Hit("save.disk","preview="+PreviewSessionActive);
                    return PreviewSessionActive?false:orig(p,a,b,c);
                }
                catch(Exception error)
                {
                    MiDiagnostics.Report("MI-HOOK-001","On.PlayerProgression.SaveToDisk",error,CreatorRuntime.CurrentRoom);
                    throw;
                }
            }
            );
            On.PlayerProgression.SaveToDisk += registeredHook25;
            removeHooks.Add(delegate
            {
                On.PlayerProgression.SaveToDisk -= registeredHook25;
            }
            );
            MiDiagnostics.Info("hook.install","On.PlayerProgression.SaveToDisk");
            var registeredHook26=new On.PlayerProgression.hook_SaveDeathPersistentDataOfCurrentState((orig,p,a,b)=>
            {
                MiDiagnostics.Hit("On.PlayerProgression.SaveDeathPersistentDataOfCurrentState",CreatorRuntime.CurrentRoom);
                try
                {
                    MiDiagnostics.Hit("save.death-persistent","preview="+PreviewSessionActive);
                    if(!PreviewSessionActive)orig(p,a,b);
                }
                catch(Exception error)
                {
                    MiDiagnostics.Report("MI-HOOK-001","On.PlayerProgression.SaveDeathPersistentDataOfCurrentState",error,CreatorRuntime.CurrentRoom);
                    throw;
                }
            }
            );
            On.PlayerProgression.SaveDeathPersistentDataOfCurrentState += registeredHook26;
            removeHooks.Add(delegate
            {
                On.PlayerProgression.SaveDeathPersistentDataOfCurrentState -= registeredHook26;
            }
            );
            MiDiagnostics.Info("hook.install","On.PlayerProgression.SaveDeathPersistentDataOfCurrentState");
            var registeredHook27=new On.OracleGraphics.Gown.hook_Color(GownColor);
            On.OracleGraphics.Gown.Color += registeredHook27;
            removeHooks.Add(delegate
            {
                On.OracleGraphics.Gown.Color -= registeredHook27;
            }
            );
            MiDiagnostics.Info("hook.install","On.OracleGraphics.Gown.Color");
            var affinityHitHook=new On.Oracle.hook_HitByWeapon((orig,o,weapon)=>
            {
                // Native Oracle.HitByWeapon is reactions only (base is empty).
                // Fully replace verified MI reactions, including Artificer's
                // direct HUD speech; every other oracle/disabled case runs once.
                if(!CreatorEncounter.HandlesHit(o,weapon)){orig(o,weapon);return;}
                try { CreatorEncounter.Hit(o,weapon); }
                catch(Exception error){MiDiagnostics.Report("MI-AFFINITY-HIT","On.Oracle.HitByWeapon",error,MiDiagnostics.Context(o.room));throw;}
            });
            On.Oracle.HitByWeapon+=affinityHitHook;
            removeHooks.Add(delegate {On.Oracle.HitByWeapon-=affinityHitHook;});
            MiDiagnostics.Info("hook.install","On.Oracle.HitByWeapon");
            var registeredHook28=new On.Oracle.hook_Update((orig,o,eu)=>
            {
                MiDiagnostics.Hit("On.Oracle.Update",CreatorRuntime.CurrentRoom);
                try
                {
                    if(CreatorOracleLifecycle.Owns(o))
                    {
                        if(!CreatorOracleLifecycle.EnsureBehavior(o,true))return;
                        if(o.room.readyForAI)AttachCustomOracle(o);
                    }
                    if(o.room!=null&&IsChamber(o.room.abstractRoom.name)){CreatorProjections.For(o);if(CreatorRuntime.Paused)return;}
                    if(o.room==null||!IsChamber(o.room.abstractRoom.name)||StudioRuntime.Simulating)orig(o,eu);
                }
                catch(Exception error)
                {
                    MiDiagnostics.Report("MI-HOOK-001","On.Oracle.Update",error,CreatorRuntime.CurrentRoom);
                    throw;
                }
            }
            );
            On.Oracle.Update += registeredHook28;
            removeHooks.Add(delegate
            {
                On.Oracle.Update -= registeredHook28;
            }
            );
            MiDiagnostics.Info("hook.install","On.Oracle.Update");
            var registeredHook29=new On.OracleGraphics.hook_Update((orig,g)=>
            {
                MiDiagnostics.Hit("On.OracleGraphics.Update",CreatorRuntime.CurrentRoom);
                try
                {
                    if(g.oracle.room!=null&&IsChamber(g.oracle.room.abstractRoom.name)&&CreatorRuntime.Paused)return;
                    if(!IsCustomOracle(g)||StudioRuntime.Simulating)orig(g);
                    StudioRuntime.UpdatePose(g);
                    var b=g.oracle.oracleBehavior as IteratorBehavior;
                    if(b!=null&&b.PersonalSpace!=null)b.PersonalSpace.Hands(g);
                    if(g.oracle.room!=null&&CreatorRuntime.IsAI(g.oracle.room.abstractRoom.name))CreatorScarf.Update(g);
                    if(IsCustomOracle(g))
                    {
                        CreatorRearGlow.Update(g);
                        CreatorNecklaces.Update(g);
                        CreatorWardrobe.Update(g);
                        PearlAccessories.Update(g);
                        IteratorIntegrations.Update(g);
                    }
                }
                catch(Exception error)
                {
                    MiDiagnostics.Report("MI-HOOK-001","On.OracleGraphics.Update",error,CreatorRuntime.CurrentRoom);
                    throw;
                }
            }
            );
            On.OracleGraphics.Update += registeredHook29;
            removeHooks.Add(delegate
            {
                On.OracleGraphics.Update -= registeredHook29;
            }
            );
            MiDiagnostics.Info("hook.install","On.OracleGraphics.Update");
#if !PLAYBACK
            StartCoroutine(StudioRuntime.Capture(x=>Logger.LogWarning(x)));
#endif
            var registeredHook30=new On.Oracle.hook_SetUpMarbles((orig,o)=>
            {
                MiDiagnostics.Hit("On.Oracle.SetUpMarbles",CreatorRuntime.CurrentRoom);
                try
                {
                    if(!constructingCustomOracle&&!CreatorOracleLifecycle.Owns(o)&&!NativeRoomProjects.Editing(o.room.abstractRoom.name))orig(o);
                }
                catch(Exception error)
                {
                    MiDiagnostics.Report("MI-HOOK-001","On.Oracle.SetUpMarbles",error,CreatorRuntime.CurrentRoom);
                    throw;
                }
            }
            );
            On.Oracle.SetUpMarbles += registeredHook30;
            removeHooks.Add(delegate
            {
                On.Oracle.SetUpMarbles -= registeredHook30;
            }
            );
            MiDiagnostics.Info("hook.install","On.Oracle.SetUpMarbles");
#if PLAYBACK
            var registeredHook31=new On.RainWorldGame.hook_Update((orig,g)=>
            {
                MiDiagnostics.Hit("On.RainWorldGame.Update",CreatorRuntime.CurrentRoom);
                try
                {
                    MiDiagnostics.Tick(g.manager);
                    orig(g);
                    CreatorRuntime.Tick(g);
                    CreatorPearlRuntime.Tick(g);
                    CreatorControlPanel.Tick(g);
                }
                catch(Exception error)
                {
                    MiDiagnostics.Report("MI-HOOK-001","On.RainWorldGame.Update",error,CreatorRuntime.CurrentRoom);
                    throw;
                }
            }
            );
            On.RainWorldGame.Update += registeredHook31;
            removeHooks.Add(delegate
            {
                On.RainWorldGame.Update -= registeredHook31;
            }
            );
            MiDiagnostics.Info("hook.install","On.RainWorldGame.Update");
#else
            var registeredHook32=new On.RainWorldGame.hook_Update((orig,g)=>
            {
                MiDiagnostics.Hit("On.RainWorldGame.Update",CreatorRuntime.CurrentRoom);
                try
                {
                    MiDiagnostics.Tick(g.manager);
                    orig(g);
                    if(Active&&StudioRuntime.Pose.testGravity>=0&&StudioRuntime.Graphics!=null)StudioRuntime.Graphics.oracle.room.gravity=StudioRuntime.Pose.testGravity;
                    if(Active)StudioRuntime.UpdateDisplay();
                    if(Active&&System.IO.File.Exists(System.IO.Path.Combine(StudioRuntime.DirectoryPath,"launch-room.txt")))g.manager.RequestMainProcessSwitch(ProcessManager.ProcessID.MainMenu);
                    RoomCatalogSnapshot.Tick(g);
                    CreatorRuntime.Tick(g);
                    CreatorPearlRuntime.Tick(g);
                    CreatorControlPanel.Tick(g);
                }
                catch(Exception error)
                {
                    MiDiagnostics.Report("MI-HOOK-001","On.RainWorldGame.Update",error,CreatorRuntime.CurrentRoom);
                    throw;
                }
            }
            );
            On.RainWorldGame.Update += registeredHook32;
            removeHooks.Add(delegate
            {
                On.RainWorldGame.Update -= registeredHook32;
            }
            );
            MiDiagnostics.Info("hook.install","On.RainWorldGame.Update");
#endif
            var registeredHook33=new On.RainWorldGame.hook_GrafUpdate((orig,g,t)=>
            {
                MiDiagnostics.Hit("On.RainWorldGame.GrafUpdate",CreatorRuntime.CurrentRoom);
                try
                {
                    orig(g,t);
                    CreatorControlPanel.Draw(g,t);
                }
                catch(Exception error)
                {
                    MiDiagnostics.Report("MI-HOOK-001","On.RainWorldGame.GrafUpdate",error,CreatorRuntime.CurrentRoom);
                    throw;
                }
            }
            );
            On.RainWorldGame.GrafUpdate += registeredHook33;
            removeHooks.Add(delegate
            {
                On.RainWorldGame.GrafUpdate -= registeredHook33;
            }
            );
            MiDiagnostics.Info("hook.install","On.RainWorldGame.GrafUpdate");
            var registeredHook34=new On.Player.hook_checkInput((orig,p)=>
            {
                MiDiagnostics.Hit("On.Player.checkInput",CreatorRuntime.CurrentRoom);
                try
                {
                    orig(p);
                    CreatorControlPanel.FilterInput(p);
                }
                catch(Exception error)
                {
                    MiDiagnostics.Report("MI-HOOK-001","On.Player.checkInput",error,CreatorRuntime.CurrentRoom);
                    throw;
                }
            }
            );
            On.Player.checkInput += registeredHook34;
            removeHooks.Add(delegate
            {
                On.Player.checkInput -= registeredHook34;
            }
            );
            MiDiagnostics.Info("hook.install","On.Player.checkInput");
            var registeredHook35=new On.RainWorldGame.hook_ShutDownProcess((orig,g)=>
            {
                MiDiagnostics.Hit("On.RainWorldGame.ShutDownProcess",CreatorRuntime.CurrentRoom);
                try
                {
                    CreatorControlPanel.Close();
                    orig(g);
                }
                catch(Exception error)
                {
                    MiDiagnostics.Report("MI-HOOK-001","On.RainWorldGame.ShutDownProcess",error,CreatorRuntime.CurrentRoom);
                    throw;
                }
            }
            );
            On.RainWorldGame.ShutDownProcess += registeredHook35;
            removeHooks.Add(delegate
            {
                On.RainWorldGame.ShutDownProcess -= registeredHook35;
            }
            );
            MiDiagnostics.Info("hook.install","On.RainWorldGame.ShutDownProcess");
            Logger.LogInfo("More Iterators core hooks installed");
        }
        void ChangeCameraRoom(On.RoomCamera.orig_ChangeRoom orig,RoomCamera cam,Room next,int position)
        {
            MiDiagnostics.Hit("ChangeCameraRoom",CreatorRuntime.CurrentRoom);
            try
            {
                // Native ChangeRoom loads the destination palette before assigning cam.room.
                // Scope the destination to palette loading, and discard banks from the previous room.
                Room previousTarget;
                bool nested=paletteRooms.TryGetValue(cam,out previousTarget);
                paletteRooms[cam]=next;
                try
                {
                    if((cam.room!=null&&IsChamber(cam.room.abstractRoom.name))||(next!=null&&IsChamber(next.abstractRoom.name)))
                    {
                        cam.paletteA=-1;
                        cam.paletteB=-1;
                    }
                    orig(cam,next,position);
                }
                finally
                {
                    if(nested)paletteRooms[cam]=previousTarget;
                    else paletteRooms.Remove(cam);
                }
            }
            catch(Exception error)
            {
                MiDiagnostics.Report("MI-HOOK-001","ChangeCameraRoom",error,CreatorRuntime.CurrentRoom);
                throw;
            }
        }
        public static Room PaletteRoom(RoomCamera cam)
        {
            Room target;
            return Instance!=null&&Instance.paletteRooms.TryGetValue(cam,out target)?target:cam.room;
        }
        void LoadRoomPalette(On.RoomCamera.orig_LoadPalette orig,RoomCamera cam,int pal,ref Texture2D texture)
        {
            MiDiagnostics.Hit("LoadRoomPalette",CreatorRuntime.CurrentRoom);
            try
            {
                var target=PaletteRoom(cam);
                var extension=IteratorIntegrations.ForRoom(target==null?null:target.abstractRoom.name);
                orig(cam,extension==null?pal:extension.BasePalette(cam,pal),ref texture);
                CreatorRuntime.Palette(texture,cam,pal);
                if(extension!=null)extension.Palette(texture,cam,pal);
                CreatorRoomTone.Apply(texture,cam);
            }
            catch(Exception error)
            {
                MiDiagnostics.Report("MI-HOOK-001","LoadRoomPalette",error,CreatorRuntime.CurrentRoom);
                throw;
            }
        }
        void SafeMark(ILContext il)
        {
            markPatchReady=false;bool reused;
            markPatchReady=CreatorMarkGuard.TryApply(il,out reused);
            if(!MiDiagnostics.Require(markPatchReady,"MI-IL-MARK","SSOracleBehavior.ctor","Expected native mark check or compatible V1 guard was not found; custom spawning is disabled.","Original IL left unchanged."))return;
            MiDiagnostics.Info("il.mark.install",reused?"Compatible V1 mark guard reused from an enabled content runtime.":"Native mark check replaced with the V1 static guard.");
        }
        void MenuCtor(On.Menu.MainMenu.orig_ctor orig, Menu.MainMenu self, ProcessManager manager, bool bg)
        {
            MiDiagnostics.Hit("MenuCtor",CreatorRuntime.CurrentRoom);
            try
            {
                UiText.Use(manager.rainWorld);
                RestorePreviewSession();
                orig(self,manager,bg);
                CreatorPearlCatalog.All();
                CreatorRuntime.Menu(self);
                IteratorIntegrations.Menu(self);
            }
            catch(Exception error)
            {
                MiDiagnostics.Report("MI-HOOK-001","MenuCtor",error,CreatorRuntime.CurrentRoom);
                throw;
            }
        }
        public void Signal(On.Menu.MainMenu.orig_Singal orig,Menu.MainMenu self,Menu.MenuObject sender,string message)
        {
            MiDiagnostics.Hit("Signal",CreatorRuntime.CurrentRoom);
            try
            {
                if(CreatorBroadcastGallery.Signal(self,message)||CreatorPearlGallery.Signal(self,message))return;
                if(CreatorRuntime.Signal(self,message)||IteratorIntegrations.Signal(self,sender,message))return;
                if(message=="MI_ENTER")
                {
                    LaunchPreview(self,CreatorRuntime.Selected);
                    return;
                }
                if(orig!=null)orig(self,sender,message);
            }
            catch(Exception error)
            {
                MiDiagnostics.Report("MI-HOOK-001","Signal",error,CreatorRuntime.CurrentRoom);
                throw;
            }
        }
        public void LaunchPreview(Menu.MainMenu self,string room)
        {
            MiDiagnostics.Hit("LaunchPreview",CreatorRuntime.CurrentRoom);
            try
            {
                if(!MiDiagnostics.Require(!previewSessionCaptured,"MI-PREVIEW-REPEAT","LaunchPreview","A preview transition is already active.","Original state backup retained; repeated launch ignored."))return;
                if(room!="SS_AI"&&!CreatorLaunch.Ensure(self,room))return;
                try
                {
                    var manager=self.manager;
                    var p=manager.rainWorld.progression;
                    previousSave=p.currentSaveState;
                    previousStarved=p.starvedSaveState;
                    previousCharacter=p.miscProgressionData.currentlySelectedSinglePlayerSlugcat;
                    previousRain=manager.rainWorld.setup.disableRain;
                    previewOwner=manager.rainWorld;
                    previewSessionCaptured=true;
                    p.currentSaveState=null;
                    p.starvedSaveState=null;
                    manager.arenaSitting=null;
                    Active=true;
                    SelectedRoom=room;
                    IteratorDesign.Select(CreatorRuntime.Id(room));
                    p.miscProgressionData.currentlySelectedSinglePlayerSlugcat=CreatorSlugcatSelection.Begin(manager.rainWorld,room);
                    manager.menuSetup.startGameCondition=ProcessManager.MenuSetup.StoryGameInitCondition.Load;
                    manager.rainWorld.setup.disableRain=true;
                    manager.RequestMainProcessSwitch(ProcessManager.ProcessID.Game);
                    Logger.LogInfo("Opening temporary preview: "+SelectedRoom+"; save writes disabled");
                }
                catch(Exception e)
                {
                    MiDiagnostics.Report("MI-PREVIEW-001","LaunchPreview",e,"room="+room);
                    RestorePreviewSession();
                }
            }
            catch(Exception error)
            {
                MiDiagnostics.Report("MI-HOOK-001","LaunchPreview",error,CreatorRuntime.CurrentRoom);
                throw;
            }
        }
        void RestorePreviewSession()
        {
            if(!previewSessionCaptured)
            {
                Active=false;
                return;
            }
            var game=previewOwner;
            if(game==null||game.progression==null||game.progression.miscProgressionData==null)
            {
                MiDiagnostics.Warn("MI-SAVE-RESTORE","RestorePreviewSession","Original progression is unavailable.","Backup retained.");
                return;
            }
            var progression=game.progression;
            CreatorSlugcatSelection.Restore();
            progression.currentSaveState=previousSave;
            progression.starvedSaveState=previousStarved;
            progression.miscProgressionData.currentlySelectedSinglePlayerSlugcat=previousCharacter;
            game.setup.disableRain=previousRain;
            previewSessionCaptured=false;
            Active=false;
            previousSave=null;
            previousStarved=null;
            previousCharacter=null;
            previewOwner=null;
            extras.Clear();
            IteratorIntegrations.Reset();
            MiDiagnostics.Info("preview.restore","Original save and character restored.");
        }
        SaveState PreviewSave(On.PlayerProgression.orig_GetOrInitiateSaveState orig,PlayerProgression p,SlugcatStats.Name name,RainWorldGame g,ProcessManager.MenuSetup setup,bool death)
        {
            MiDiagnostics.Hit("PreviewSave",CreatorRuntime.CurrentRoom);
            try
            {
                if(!PreviewSessionActive)return orig(p,name,g,setup,death);
                var s=new SaveState(CreatorSlugcatSelection.SessionCharacter(SelectedRoom),p);
                s.LoadGame("",g);
                s.denPosition=SelectedRoom;
                s.cycleNumber=1;
                s.deathPersistentSaveData.theMark=SelectedRoom!="SS_AI"&&StudioRuntime.Pose.hasMark;
                p.currentSaveState=s;
                return s;
            }
            catch(Exception error)
            {
                MiDiagnostics.Report("MI-HOOK-001","PreviewSave",error,CreatorRuntime.CurrentRoom);
                throw;
            }
        }
        static readonly System.Reflection.FieldInfo GownOwner=typeof(OracleGraphics.Gown).GetField("owner",System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic|System.Reflection.BindingFlags.Public);
        Color GownColor(On.OracleGraphics.Gown.orig_Color orig,OracleGraphics.Gown gown,float f)
        {
            MiDiagnostics.Hit("GownColor",CreatorRuntime.CurrentRoom);
            try
            {
                if(!MiDiagnostics.Require(GownOwner!=null,"MI-REFLECTION-GOWN","Gown.Color","The game's Gown.owner field was not found.","Native color retained."))return orig(gown,f);
                var owner=GownOwner.GetValue(gown) as OracleGraphics;
                return IsCustomOracle(owner)?IteratorDesign.ForRoom(owner.oracle.room).Cloth(f):orig(gown,f);
            }
            catch(Exception error)
            {
                MiDiagnostics.Report("MI-HOOK-001","GownColor",error,CreatorRuntime.CurrentRoom);
                throw;
            }
        }
        void Ready(On.Room.orig_ReadyForAI orig,Room room)
        {
            MiDiagnostics.Hit("Ready",CreatorRuntime.CurrentRoom);
            try
            {
                orig(room);
                IteratorIntegrations.BeforeRoom(room);
                CreatorPearlRuntime.Ready(room);
                if(room.game==null||!IsChamber(room.abstractRoom.name))return;
                bool hasGradient=false;foreach(var item in room.updateList)if(item is CreatorRoomGradient){hasGradient=true;break;}
                if(!hasGradient)room.AddObject(new CreatorRoomGradient(room));
                IteratorDesign.Select(CreatorRuntime.Id(room.abstractRoom.name));
                IteratorDesign.Poll(x=>Logger.LogInfo(x));
                var roomOracles=new List<Oracle>();
                foreach(var item in room.updateList)if(item is Oracle)roomOracles.Add((Oracle)item);
                foreach(var existing in roomOracles)
                {
                    if(CreatorOracleLifecycle.Owns(existing))AttachCustomOracle(existing);
                    else if(existing==roomOracles[0])NativeRoomProjects.Attach(existing);
                }
                if(roomOracles.Count>0)return;
                if(!MiDiagnostics.Require(markPatchReady,"MI-ORACLE-PATCH","ReadyForAI","Oracle constructor compatibility check failed.",MiDiagnostics.Context(room)))return;
                try
                {
#if !PLAYBACK
                    if(Active&&Screen.fullScreen)Screen.fullScreen=false;
#endif
                    Oracle o;
                    try
                    {
                        constructingCustomOracle=true;
                        o=new Oracle(new AbstractPhysicalObject(room.world,AbstractPhysicalObject.AbstractObjectType.Oracle,null,new WorldCoordinate(room.abstractRoom.index,24,18,-1),room.game.GetNewID()),room);
                    }
                    finally
                    {
                        constructingCustomOracle=false;
                    }
                    for(int i=0;i<o.bodyChunks.Length;i++)o.bodyChunks[i].HardSetPosition(new Vector2(480,350-i*9));
                    room.AddObject(o);
                    AttachCustomOracle(o);
                    Logger.LogInfo("Iterator spawned in registered chamber");
                }
                catch(Exception e)
                {
                    MiDiagnostics.Report("MI-ORACLE-SPAWN","ReadyForAI",e,MiDiagnostics.Context(room));
                }
            }
            catch(Exception error)
            {
                MiDiagnostics.Report("MI-HOOK-001","Ready",error,CreatorRuntime.CurrentRoom);
                throw;
            }
        }
        static void AttachCustomOracle(Oracle oracle)
        {
            if(!CreatorOracleLifecycle.EnsureBehavior(oracle,true)||!CreatorOracleLifecycle.ClaimEncounter(oracle))return;
            try
            {
                oracle.room.gravity=0;
                if(CreatorRuntime.UsesDialogue(oracle.room.abstractRoom.name))oracle.room.AddObject(new CreatorEncounter(oracle));
                else IteratorIntegrations.CreateEncounter(oracle);
            }
            catch {CreatorOracleLifecycle.ReleaseEncounter(oracle);throw;}
        }
        Color Skin(On.OracleGraphics.orig_SkinColor orig,OracleGraphics self)
        {
            MiDiagnostics.Hit("Skin",CreatorRuntime.CurrentRoom);
            try
            {
                return IsCustomOracle(self)?IteratorDesign.C(IteratorDesign.ForRoom(self.oracle.room).headColor):orig(self);
            }
            catch(Exception error)
            {
                MiDiagnostics.Report("MI-HOOK-001","Skin",error,CreatorRuntime.CurrentRoom);
                throw;
            }
        }
        bool IsCustomOracle(OracleGraphics g)
        {
            return g!=null&&g.oracle!=null&&g.oracle.room!=null&&g.oracle.room.abstractRoom!=null&&IsChamber(g.oracle.room.abstractRoom.name);
        }
        void Palette(On.OracleGraphics.orig_ApplyPalette orig,OracleGraphics self,RoomCamera.SpriteLeaser s,RoomCamera cam,RoomPalette p)
        {
            MiDiagnostics.Hit("Palette",CreatorRuntime.CurrentRoom);
            try
            {
                orig(self,s,cam,p);
                if(!IsCustomOracle(self))return;
                s.sprites[self.EyeSprite(0)].color=Color.white;
                s.sprites[self.EyeSprite(1)].color=Color.white;
                s.sprites[self.robeSprite].color=Color.white;
            }
            catch(Exception error)
            {
                MiDiagnostics.Report("MI-HOOK-001","Palette",error,CreatorRuntime.CurrentRoom);
                throw;
            }
        }
        void Sprites(On.OracleGraphics.orig_InitiateSprites orig,OracleGraphics self,RoomCamera.SpriteLeaser s,RoomCamera cam)
        {
            MiDiagnostics.Hit("Sprites",CreatorRuntime.CurrentRoom);
            try
            {
                orig(self,s,cam);
                if(!IsCustomOracle(self))return;
                int first=s.sprites.Length;
                extras[self]=first;
                int count=110+CreatorNecklaces.Slots+IteratorSprites.IntegrationSlots+CreatorHeadphones.Slots+CreatorWardrobe.Slots+CreatorHeadSegments.Slots+PearlAccessories.Slots+CreatorEyes.Slots+CreatorArms.Slots;
                Array.Resize(ref s.sprites,first+count);
                for(int i=0;i<count;i++)
                {
                    s.sprites[first+i]=i<2?(FSprite)TriangleMesh.MakeLongMesh(8,false,true):new FSprite("pixel",true);
                    if(i>=110)s.sprites[first+i].isVisible=false;
                    cam.ReturnFContainer("Midground").AddChild(s.sprites[first+i]);
                }
                IteratorIntegrations.Sprites(self,s,cam,first);
            }
            catch(Exception error)
            {
                MiDiagnostics.Report("MI-HOOK-001","Sprites",error,CreatorRuntime.CurrentRoom);
                throw;
            }
        }
        void Draw(On.OracleGraphics.orig_DrawSprites orig,OracleGraphics self,RoomCamera.SpriteLeaser s,RoomCamera cam,float stack,Vector2 camera)
        {
            MiDiagnostics.Hit("Draw",CreatorRuntime.CurrentRoom);
            try
            {
                CreatorArms.BeforeDraw(self,s);
                CreatorAppearance.BeforeDraw(s);
                if(IsCustomOracle(self)&&(!StudioRuntime.Simulating||CreatorRuntime.Paused))stack=1f;
                orig(self,s,cam,stack,camera);
                if(!IsCustomOracle(self)||self.oracle.room!=cam.room||!extras.ContainsKey(self))return;
                bool culled=(CreatorRuntime.Paused||!StudioRuntime.Simulating)?self.ShouldBeCulled:self.culled;
                if(CreatorSpriteVisibility.HideIfCulled(culled,s.sprites))return;
                IteratorDesign.Select(CreatorRuntime.Id(self.oracle.room.abstractRoom.name));
                IteratorDesign.Poll(x=>Logger.LogInfo(x));
                var d=IteratorDesign.Current;
                StudioRuntime.Graphics=self;
                StudioRuntime.Sprites=s;
                if(!CreatorRuntime.IsAI(self.oracle.room.abstractRoom.name)&&(appliedRoomPalette!=d.roomPalette||appliedRoomRevision!=IteratorDesign.Revision))
                {
                    appliedRoomPalette=d.roomPalette;
                    appliedRoomRevision=IteratorDesign.Revision;
                    self.oracle.room.roomSettings.Palette=d.roomPalette;
                    cam.ChangeMainPalette(d.roomPalette);
                }
                int n=extras[self];
                var head=s.sprites[self.HeadSprite];
                var teal=IteratorDesign.C(d.antennaColor);
                var metal=IteratorDesign.C(d.metalColor);
                Vector2 chest=Vector2.Lerp(self.oracle.bodyChunks[0].lastPos,self.oracle.bodyChunks[0].pos,stack)-camera;
                Vector2 center=new Vector2(head.x,head.y),up=(center-chest).normalized;
                if(up.sqrMagnitude<.1f)up=Vector2.up;
                Vector2 right=new Vector2(up.y,-up.x);
                float rotation=Mathf.Atan2(up.x,up.y)*Mathf.Rad2Deg;
                StudioRuntime.FaceAngle=rotation;
                for(int side=0;side<2;side++)
                {
                    float sign=side==0?-1:1;
                    var antenna=(TriangleMesh)s.sprites[n+side];
                    for(int j=0;j<8;j++)
                    {
                        float a=j/8f,b=(j+1)/8f;
                        float wa=d.antennaWidth*(j>=5&&j%2==1?.48f:1f),wb=d.antennaWidth*(j>=5&&j%2==1?.48f:1f);
                        Vector2 pa=center+right*sign*(d.antennaSpread+a*.8f)+up*(2+a*d.antennaHeight),pb=center+right*sign*(d.antennaSpread+b*.8f)+up*(2+b*d.antennaHeight);
                        antenna.MoveVertice(j*4,pa-right*wa);
                        antenna.MoveVertice(j*4+1,pa+right*wa);
                        antenna.MoveVertice(j*4+2,pb-right*wb);
                        antenna.MoveVertice(j*4+3,pb+right*wb);
                        for(int k=0;k<4;k++)antenna.verticeColors[j*4+k]=Color.Lerp(metal,teal,Mathf.SmoothStep(0,1,(k<2?a:b))*.9f);
                    }
                    antenna.isVisible=d.layers.antenna&&IteratorDesign.AntennaElement==null;
                    Vector2 ear=center+right*sign*8+up*.5f;
                    Set(s.sprites[n+2+side],ear.x,ear.y,d.earWidth,d.earHeight,metal,rotation);
                    s.sprites[n+2+side].isVisible=d.layers.ears;
                    Vector2 mark=center+right*(sign*2.3f+d.faceOffsetX)+up*(4+d.faceOffsetY);
                    Set(s.sprites[n+4+side],mark.x,mark.y,2.3f*d.faceScale,1.3f*d.faceScale,teal,rotation+sign*25);
                    s.sprites[n+4+side].isVisible=d.layers.face&&IteratorDesign.FaceElement==null;
                    var custom=s.sprites[n+9+side];
                    custom.isVisible=d.layers.antenna&&IteratorDesign.AntennaElement!=null;
                    if(custom.isVisible)
                    {
                        custom.element=Futile.atlasManager.GetElementWithName(IteratorDesign.AntennaElement);
                        Vector2 ap=center+right*sign*d.antennaSpread+up*d.antennaHeight*.5f;
                        Set(custom,ap.x,ap.y,sign*d.antennaWidth*4/24f,(d.antennaHeight+4)/48f,Color.white,rotation);
                    }
                    for(int k=0;k<3;k++)s.sprites[self.PhoneSprite(side,k)].isVisible=false;
                }
                Set(s.sprites[n+6],chest.x-2,chest.y-4,1.1f,10,teal,-40);
                Set(s.sprites[n+7],chest.x+2,chest.y-4,1.1f,10,teal,40);
                IteratorHalo.Draw(self,s,cam,stack,camera,d,s.sprites[n+11]);
                CreatorArmAppearance.Apply(self,s,d);
                if(self.umbCord!=null)
                {
                    ShowRange(s,self.umbCord.firstSprite,self.umbCord.totalSprites,d.layers.cables);
                }
                if(self.discUmbCord!=null)
                {
                    ShowRange(s,self.discUmbCord.firstSprite,self.discUmbCord.totalSprites,d.layers.cables);
                }
                TintCords(self,s,d);
                s.sprites[n+6].isVisible=s.sprites[n+7].isVisible=d.layers.collar;
                var face=s.sprites[n+8];
                face.isVisible=d.layers.face&&IteratorDesign.FaceElement!=null;
                if(face.isVisible)
                {
                    face.element=Futile.atlasManager.GetElementWithName(IteratorDesign.FaceElement);
                    float faceY=Mathf.Min(d.faceOffsetY,4.2f-IteratorDesign.FaceInk.yMax*24*d.faceScale/32f);
                    Vector2 fp=center+right*d.faceOffsetX+up*faceY;
                    Set(face,fp.x,fp.y,24*d.faceScale/32f,24*d.faceScale/32f,Color.white,rotation);
                }
                head.color=IteratorDesign.C(d.headColor);
                head.isVisible=d.layers.head;
                s.sprites[self.ChinSprite].color=head.color;
                s.sprites[self.ChinSprite].isVisible=d.layers.head;
                CreatorSpriteVisibility.ApplyBody(s.sprites,self.firstBodyChunkSprite,self.oracle.bodyChunks.Length,d.layers.body,head.color);
                var neck=s.sprites[self.neckSprite];
                neck.color=head.color*.88f;
                neck.alpha=1;
                neck.isVisible=d.layers.neck;
                neck.MoveBehindOtherNode(head);
                Vector2 neckStart=chest+up;
                neck.x=neckStart.x;
                neck.y=neckStart.y;
                neck.rotation=rotation;
                neck.scaleX=3;
                neck.scaleY=Mathf.Clamp(Vector2.Distance(chest,center)-7,2,6);
                for(int side=0;side<2;side++)
                {
                    var eye=s.sprites[self.EyeSprite(side)];
                    eye.color=IteratorDesign.C(d.eyeColor);
                    eye.isVisible=d.layers.eyes;
                    Vector2 ep=center+right*(side==0?-d.eyeSpacing:d.eyeSpacing)-up;
                    eye.x=ep.x;
                    eye.y=ep.y;
                    eye.scaleX*=d.eyeSize/1.35f;
                    eye.scaleY*=d.eyeSize/1.35f;
                    s.sprites[self.HandSprite(side,0)].color=head.color;
                    s.sprites[self.HandSprite(side,0)].isVisible=d.layers.hands;
                    var sleeve=s.sprites[self.HandSprite(side,1)];
                    sleeve.isVisible=d.layers.sleeves;
                    TintMesh(sleeve,d,false);
                    for(int k=0;k<2;k++)
                    {
                        s.sprites[self.FootSprite(side,k)].color=head.color;
                        s.sprites[self.FootSprite(side,k)].isVisible=d.layers.feet;
                    }
                }
                if(self.gowns!=null)
                {
                    int offset=0;
                    foreach(var gown in self.gowns)
                    {
                        for(int k=0;k<gown.totalSprites;k++)
                        {
                            var robe=s.sprites[self.robeSprite+offset+k];
                            robe.isVisible=d.layers.robe;
                            TintMesh(robe,d,true);
                        }
                        offset+=gown.totalSprites;
                    }
                }
                if(CreatorRuntime.IsAI(self.oracle.room.abstractRoom.name))CreatorAppearance.Draw(self,s,n,d,chest,center,up,right,camera,stack);
                else IteratorIntegrations.Draw(self,s,n,d,chest,center,up,right,camera,stack);
                CreatorHeadphones.Draw(self,s,n,d);
                CreatorHeadSegments.Draw(self,s,n,d,up,right);
                CreatorEyes.Draw(self,s,n,d,up,right);
                CreatorWardrobe.Draw(self,s,n,d,camera,stack,up,right);
                OracleSpriteDiagnostics.Observe(self,s,n,d);
                CreatorRearGlow.Draw(self,s);
            }
            catch(Exception error)
            {
                MiDiagnostics.Report("MI-HOOK-001","Draw",error,CreatorRuntime.CurrentRoom);
                throw;
            }
        }
        void Line(FSprite s,Vector2 a,Vector2 b,Color color)
        {
            Vector2 mid=(a+b)*.5f;
            Set(s,mid.x,mid.y,.6f,Vector2.Distance(a,b),color,Mathf.Atan2(b.x-a.x,b.y-a.y)*Mathf.Rad2Deg);
        }
        void ColorCord(FSprite sprite,Color c)
        {
            CreatorCableColors.Solid(sprite,c);
        }
        void TintCords(OracleGraphics g,RoomCamera.SpriteLeaser s,IteratorDesign d)
        {
            Color dark=IteratorDesign.C(d.cableColorA),light=IteratorDesign.C(d.cableColorB);
            if(g.umbCord!=null)
            {
                var c=g.umbCord;
                ColorCord(s.sprites[c.firstSprite],dark);
                CreatorColorGradient.Paint(s.sprites[c.firstSprite],d.cableThinGradient,dark,0,1,1);
                for(int i=0;i<c.coord.GetLength(0);i++)
                {
                    ColorCord(s.sprites[c.SegmentSprite(i,0)],light);
                    ColorCord(s.sprites[c.SegmentSprite(i,1)],Color.Lerp(light,Color.white,.17f));
                    Color color=d.cableThickGradient.Sample(i/(float)Math.Max(1,c.coord.GetLength(0)-1),light);
                    if(d.cableThickGradient.enabled){ColorCord(s.sprites[c.SegmentSprite(i,0)],color);ColorCord(s.sprites[c.SegmentSprite(i,1)],Color.Lerp(color,Color.white,.17f));}
                }
                for(int i=0;i<c.smallCords.GetLength(0);i++)CreatorCableColors.Head(s.sprites[c.SmallCordSprite(i)],d,c.smallCoordColors[i]);
            }
            if(g.discUmbCord!=null)
            {
                var c=g.discUmbCord;
                for(int i=0;i<c.smallCords.GetLength(0);i++)CreatorCableColors.Head(s.sprites[c.SmallCordSprite(i)],d,c.smallCoordColors[i]);
            }
        }
        void ShowRange(RoomCamera.SpriteLeaser s,int start,int count,bool show)
        {
            for(int i=start;i<start+count&&i<s.sprites.Length;i++)s.sprites[i].isVisible=show;
        }
        void TintMesh(FSprite sprite,IteratorDesign d,bool robe)
        {
            var mesh=sprite as TriangleMesh;
            if(mesh==null)
            {
                sprite.color=d.Cloth(.3f);
                return;
            }
            sprite.color=Color.white;
            float min=float.MaxValue,max=float.MinValue;
            foreach(var v in mesh.vertices)
            {
                min=Mathf.Min(min,v.y);
                max=Mathf.Max(max,v.y);
            }
            if(robe)
            {
                int divs=(int)Mathf.Sqrt(mesh.vertices.Length);
                if(divs*divs==mesh.vertices.Length)
                {
                    for(int row=0;row<divs;row++)
                    {
                        Vector2 left=mesh.vertices[row],right=mesh.vertices[(divs-1)*divs+row],mid=(left+right)*.5f,axis=(right-left).normalized;
                        float factor=Mathf.Lerp(1,Mathf.Clamp(d.robeHemWidth,.45f,2.2f),Mathf.SmoothStep(0,1,row/(float)(divs-1)));
                        for(int col=0;col<divs;col++)
                        {
                            int idx=col*divs+row;
                            Vector2 v=mesh.vertices[idx];
                            mesh.MoveVertice(idx,v+axis*Vector2.Dot(v-mid,axis)*(factor-1));
                        }
                    }
                }
                for(int i=0;i<mesh.vertices.Length;i++)
                {
                    var v=mesh.vertices[i];
                    int grid=(int)Mathf.Sqrt(mesh.vertices.Length);
                    Vector2 top=mesh.vertices[(i/grid)*grid];
                    mesh.MoveVertice(i,top+(v-top)*d.robeLength/29f);
                }
            }
            else
            {
                for(int i=0;i+1<mesh.vertices.Length;i+=2)
                {
                    Vector2 a=mesh.vertices[i],b=mesh.vertices[i+1],mid=(a+b)*.5f;
                    mesh.MoveVertice(i,mid+(a-mid)*d.sleeveWidth/4f);
                    mesh.MoveVertice(i+1,mid+(b-mid)*d.sleeveWidth/4f);
                }
            }
            if(mesh.verticeColors==null)return;
            for(int i=0;i<mesh.verticeColors.Length;i++)
            {
                float f=robe?(i%(int)Mathf.Sqrt(mesh.vertices.Length))/(float)((int)Mathf.Sqrt(mesh.vertices.Length)-1):Mathf.InverseLerp(max,min,mesh.vertices[i].y);
                mesh.verticeColors[i]=d.Cloth(robe?f:f*.65f);
            }
        }
        void Set(FSprite s,float x,float y,float w,float h,Color c,float r)
        {
            s.x=x;
            s.y=y;
            s.scaleX=w;
            s.scaleY=h;
            s.color=c;
            s.rotation=r;
        }
    }
    public class IteratorBehavior : SSOracleBehavior
    {
        static Room nativePaletteUpdateRoom;
        public static bool HasCommunicationMark(Oracle oracle)
        {
            var game=oracle==null||oracle.room==null?null:oracle.room.game;
            if(game!=null&&CreatorVoicePreview.WithoutMark)return false;
            // Story/co-op players share this save flag. Another grant path can set
            // it before the preview control file has refreshed its cached mark.
            return MoreIteratorsPlugin.Active&&CreatorRuntime.Mark||CreatorMarkGuard.HasMarkV1(game);
        }
        public static bool SuppressNativePalette(Room room,int first,int second)
        {
            return room!=null&&room==nativePaletteUpdateRoom&&first==25&&second==26;
        }
        bool HasReceptionController()
        {
            if(oracle==null||oracle.room==null||oracle.oracleBehavior!=this||!IteratorCatalog.IsAI(oracle.room.abstractRoom.name))return false;
            foreach(var item in oracle.room.updateList)if(item is CreatorEncounter&&!item.slatedForDeletetion)return true;
            return false;
        }
        int workMoveTick;
        public readonly IOraclePersonalSpace PersonalSpace;
        public void GoTo(Vector2 target)
        {
            if(Destination!=null)Destination.Invoke(this,new object[]
            {
                target
            }
            );
        }
        static readonly System.Reflection.MethodInfo Destination=typeof(SSOracleBehavior).GetMethod("SetNewDestination",System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic);
        public int encounterTicks=-1;
        public bool encounterActive;
        public float requestedGravity;
        static readonly Action MeetingAction=new Action("MoreIterators_Encounter",true);
        public IteratorBehavior(Oracle o):base(o)
        {
            working=1f;
            getToWorking=1f;
            killFac=0;
            action=MeetingAction;
            currSubBehavior=new WorkSubBehavior(this);
            allSubBehaviors.Add(currSubBehavior);
            PersonalSpace=IteratorIntegrations.PersonalSpace(this);
        }
        public override Vector2 OracleGetToPos
        {
            get
            {
                return CreatorReadingPresentation.Target(oracle,StudioRuntime.Pose.playMode||StudioRuntime.Pose.animate?base.OracleGetToPos:new Vector2(480,350));
            }
        }
        public override bool EyesClosed { get { return CreatorReadingPresentation.EyesClosed(oracle,base.EyesClosed); } }
        public override Vector2 BaseGetToPos
        {
            get
            {
                return StudioRuntime.Pose.playMode||StudioRuntime.Pose.animate?base.BaseGetToPos:new Vector2(480,600);
            }
        }
        public override Vector2 GetToDir
        {
            get
            {
                return StudioRuntime.Pose.playMode||StudioRuntime.Pose.animate?base.GetToDir:Vector2.up;
            }
        }
        public override void Update(bool eu)
        {
            CreatorReadingPresentation.Tick(oracle,StudioRuntime.Pose.playMode||StudioRuntime.Pose.animate?base.OracleGetToPos:new Vector2(480,350));
            if(StudioRuntime.Recording)
            {
                encounterActive=false;
                killFac=0;
                requestedGravity=0;
            }
            if(StudioRuntime.Pose.playMode||StudioRuntime.Pose.animate)
            {
                if(PersonalSpace!=null)PersonalSpace.Sense();
                // SS.Update writes its own fast palette blend. The live MI encounter owns
                // this chamber's slower transition; suppress only that exact native call scope.
                Room previousPaletteRoom=nativePaletteUpdateRoom;
                nativePaletteUpdateRoom=HasReceptionController()?oracle.room:null;
                bool controlsRoom=CreatorOracleLifecycle.ControlsRoom(oracle);
                float previousGravity=oracle.room.gravity;
                try { base.Update(eu); }
                finally { nativePaletteUpdateRoom=previousPaletteRoom;if(!controlsRoom)oracle.room.gravity=previousGravity; }
                if(controlsRoom)oracle.room.gravity=requestedGravity;
                if(PersonalSpace!=null)PersonalSpace.Move();
                if(!CreatorReadingPresentation.ControlsMovement(oracle)&&(PersonalSpace==null||!PersonalSpace.Avoiding)&&!encounterActive&&++workMoveTick%240==1&&Destination!=null)
                {
                    Vector2 target=new Vector2(oracle.room.PixelWidth*.5f+Mathf.Sin(workMoveTick*.003f)*85,oracle.room.PixelHeight*.52f+Mathf.Cos(workMoveTick*.005f)*40);
                    if(!oracle.room.GetTile(target).Solid)Destination.Invoke(this,new object[]
                    {
                        target
                    }
                    );
                }
                return;
            }
            FindPlayer();
            lookPoint=OracleGetToPos+Vector2.up*20;
            for(int i=0;i<oracle.bodyChunks.Length;i++)
            {
                var b=oracle.bodyChunks[i];
                b.vel*=.9f;
                b.vel+=Vector2.ClampMagnitude(OracleGetToPos-new Vector2(0,i*9)-b.pos,40)*.025f;
            }
        }
        public class WorkSubBehavior:SubBehavior
        {
            readonly IteratorBehavior behavior;
            public WorkSubBehavior(IteratorBehavior b):base(b,SubBehavID.General)
            {
                behavior=b;
            }
            public override float LowGravity
            {
                get
                {
                    return behavior.encounterActive?.18f*Mathf.SmoothStep(0,1,Mathf.InverseLerp(30,180,behavior.encounterTicks)):0;
                }
            }
            public override void Update()
            {
                owner.getToWorking=behavior.encounterActive?0:1;
                int t=behavior.encounterTicks;
                bool hasMark=HasCommunicationMark(behavior.oracle);
                owner.movementBehavior=behavior.PersonalSpace!=null&&behavior.PersonalSpace.Avoiding?MovementBehavior.Idle:!behavior.encounterActive?MovementBehavior.Idle:t<(hasMark?40:120)?MovementBehavior.KeepDistance:!hasMark&&t<480?MovementBehavior.Investigate:MovementBehavior.Talk;
            }
        }
    }
    public class CreatorMenuButton:Menu.SimpleButton
    {
        public CreatorMenuButton(Menu.MainMenu m,Menu.MenuObject owner,string text,string signal,Vector2 pos,Vector2 size):base(m,owner,text,signal,pos,size)
        {
        }
        public override void Clicked()
        {
            MoreIteratorsPlugin.Instance.Signal(null,(Menu.MainMenu)menu,this,signalText);
        }
    }
}
