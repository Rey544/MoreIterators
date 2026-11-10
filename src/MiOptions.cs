#if !PLAYBACK
using System;
using System.Collections.Generic;
using Menu.Remix.MixedUI;
using UnityEngine;

namespace MoreIterators
{
    public sealed class MiOptions : OptionInterface
    {
        static MiOptions instance;
        static bool registered;
        public readonly Configurable<string> DiagnosticLevel;
         
        static readonly string[] Levels = { "info", "debug", "trace" };

        public MiOptions()
        {
            DiagnosticLevel = config.Bind("DiagnosticLevel", "info",
                new ConfigurableInfo(UiText.Get("Diagnostic level"), new ConfigAcceptableList<string>(Levels)));
            DiagnosticLevel.OnChange += ApplyLevel;
        }

        public override void Initialize()
        {
            base.Initialize();
            Tabs = new[] { new OpTab(this, UiText.Get("Settings")) };
            Tabs[0].AddItems(
                new OpLabel(new Vector2(40f, 510f), new Vector2(240f, 30f), UiText.Get("Diagnostic level"), FLabelAlignment.Left),
                new OpComboBox(DiagnosticLevel, new Vector2(300f, 510f), 160f, Levels));
        }

        void ApplyLevel() { MiDiagnostics.SetLevel(DiagnosticLevel.Value); }

        public static void Install(List<Action> cleanup)
        {
            On.RainWorld.OnModsInit += AfterModsInit;
            cleanup.Add(delegate { On.RainWorld.OnModsInit -= AfterModsInit; });
            if (ModManager.InitializationScreenFinished) Register(RWCustom.Custom.rainWorld);
        }

        static void AfterModsInit(On.RainWorld.orig_OnModsInit orig, RainWorld rainWorld)
        {
            orig(rainWorld);
            Register(rainWorld);
        }

        static void Register(RainWorld rainWorld)
        {
            UiText.Use(rainWorld);
            try
            {
                if (instance == null) instance = new MiOptions();
                if (!registered)
                {
                    if (!MachineConnector.SetRegisteredOI(RuntimePaths.ModId, instance))
                        throw new InvalidOperationException("Remix settings registration was rejected.");
                    registered = true;
                    MachineConnector.ReloadConfig(instance);
                }
                instance.ApplyLevel();
            }
            catch (Exception error)
            {
                MiDiagnostics.Report("MI-OPTIONS-001", "MiOptions.Register", error, "Remix diagnostic settings");
            }
        }
    }
}
#endif
