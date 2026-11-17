extern alias rwjson;
using System;
using System.Collections.Generic;
using System.Reflection;
using System.Runtime.CompilerServices;
using MoreIterators;
using UnityEngine;

public static class JsonProbe
{
    public static int reads;
    public static bool fail;
    public static object Deserialize(string text)
    {
        reads++;
        if (fail)
            throw new FormatException("Injected JSON parse failure");
        return rwjson::Json.Deserialize(text);
    }
    public static string Serialize(object value)
    {
        return rwjson::Json.Serialize(value);
    }
}

class DialogueMaintenanceCheck
{
    static int assertions;

    static void Check(bool value, string message)
    {
        assertions++;
        if (!value)
            throw new Exception(message);
    }

    static IteratorDesign Design(string extra)
    {
        return new IteratorDesign
        {
            oracleId = Guid.NewGuid().ToString(),
            dialogueJson = "{\"nonce\":\"" + Guid.NewGuid() + "\",\"enabled\":true,\"first\":[{\"text\":\"kept\",\"gap\":0}]" + extra + "}"
        };
    }

    static Oracle Scene(IteratorDesign design, RainWorldGame game = null)
    {
        CreatorLaunch.node = 0;
        CreatorRuntime.Mode = "story";
        var room = new Room { game = game ?? new RainWorldGame(), design = design };
        var oracle = new Oracle { room = room };
        room.updateList.Add(oracle);
        return oracle;
    }

    static object Session(CreatorDialogue dialogue)
    {
        return typeof(CreatorDialogue).GetField("session", BindingFlags.Instance | BindingFlags.NonPublic).GetValue(dialogue);
    }

    static void Profile()
    {
        var design = Design(",\"pearlReading\":{\"greetingEnabled\":false},\"requireMark\":false");
        string original = design.dialogueJson;
        int initial = JsonProbe.reads;
        var profile = CreatorDialogueProfile.For(design);
        Check(JsonProbe.reads == initial + 1, "The complete dialogue document is deserialized once");
        Check(!profile.pearlReading.greetingEnabled && profile.first[0].text == "kept", "The single document supplies dialogue and pearl rules");
        Check(profile.requireMark, "Legacy false requireMark cannot remove the existing mark policy");
        for (int i = 0; i < 5000; i++)
            Check(Object.ReferenceEquals(profile, CreatorDialogueProfile.For(design)), "Unchanged design reuses the same profile");
        Check(JsonProbe.reads == initial + 1 && design.dialogueJson == original, "Hot reads do not parse or alter author JSON");
        design.dialogueJson = original.Replace("kept", "edited");
        var edited = CreatorDialogueProfile.For(design);
        Check(edited.first[0].text == "edited" && !Object.ReferenceEquals(profile, edited), "Editing JSON invalidates the design cache");
        UiText.CurrentLanguage = "Chinese";
        var translated = CreatorDialogueProfile.For(design);
        Check(!Object.ReferenceEquals(edited, translated), "Changing language invalidates the design cache");
        UiText.CurrentLanguage = "English";
        var old = new IteratorDesign { oracleId = "legacy", firstDialogue = "first\nsecond", repeatDialogue = null };
        var legacy = CreatorDialogueProfile.For(old);
        Check(legacy.first.Count == 2 && legacy.repeat.Count == 0, "Old line fields and explicit null keep their existing defaults");
        old.firstDialogue = "changed legacy";
        Check(CreatorDialogueProfile.For(old).first[0].text == "changed legacy", "Editing old line fields invalidates the cache");
        old.dialogueJson = Design("").dialogueJson;
        Check(CreatorDialogueProfile.For(old).first[0].text == "kept", "An old project can switch to structured JSON");
    }

    static void ProfileErrors()
    {
        var design = Design("");
        int reports = MiDiagnostics.codes.Count, warnings = UnityEngine.Debug.warnings, reads = JsonProbe.reads;
        JsonProbe.fail = true;
        var failed = CreatorDialogueProfile.For(design);
        JsonProbe.fail = false;
        Check(JsonProbe.reads == reads + 1, "Failed JSON is not parsed twice");
        Check(MiDiagnostics.codes.Count == reports + 1 && MiDiagnostics.codes[reports] == "MI_DIALOGUE_PROFILE_READ", "A parser fault retains one precise diagnostic");
        Check(UnityEngine.Debug.warnings == warnings, "Diagnostics are not duplicated as Unity warnings");
        CreatorDialogueProfile.For(design);
        Check(MiDiagnostics.codes.Count == reports + 1, "Cached invalid input does not emit a per-frame error");
        design.dialogueJson = Design("").dialogueJson;
        Check(CreatorDialogueProfile.For(design).first[0].text == "kept", "Editing malformed input allows parsing to recover");
        var independent = new IteratorDesign
        {
            oracleId = Guid.NewGuid().ToString(),
            dialogueJson = "{\"enabled\":true,\"first\":[{\"action\":[]}],\"pearlReading\":{\"greetingEnabled\":false}}"
        };
        reports = MiDiagnostics.codes.Count;
        var partial = CreatorDialogueProfile.For(independent);
        Check(MiDiagnostics.codes.Count == reports + 1 && !partial.pearlReading.greetingEnabled, "Independent pearl parsing survives a dialogue conversion fault");
        var badPearl = Design(",\"pearlReading\":[]");
        reports = MiDiagnostics.codes.Count;
        Check(CreatorDialogueProfile.For(badPearl).first[0].text == "kept", "Bad pearl rules retain valid dialogue");
        Check(MiDiagnostics.codes.Count == reports + 1 && MiDiagnostics.codes[reports] == "MI_PEARL_RULES_READ", "Bad pearl rules keep their precise diagnostic");
    }

    [MethodImpl(MethodImplOptions.NoInlining)]
    static WeakReference[] Abandoned()
    {
        var oracle = Scene(Design(""));
        var dialogue = new CreatorDialogue(oracle);
        return new[] { new WeakReference(oracle.room.game), new WeakReference(oracle), new WeakReference(Session(dialogue)), new WeakReference(dialogue) };
    }

    [MethodImpl(MethodImplOptions.NoInlining)]
    static WeakReference Retained(RainWorldGame game, string id)
    {
        var design = Design("");
        design.oracleId = id;
        var dialogue = new CreatorDialogue(Scene(design, game));
        return new WeakReference(Session(dialogue));
    }

    static void Collect()
    {
        for (int i = 0; i < 3; i++)
        {
            GC.Collect();
            GC.WaitForPendingFinalizers();
            GC.Collect();
        }
    }

    static void Sessions()
    {
        var dead = Abandoned();
        Collect();
        foreach (var weak in dead)
            Check(!weak.IsAlive, "A static dialogue cache must not retain an abandoned game/room/oracle/session");
        var firstGame = new RainWorldGame();
        string id = Guid.NewGuid().ToString();
        var first = Retained(firstGame, id);
        Collect();
        Check(first.IsAlive, "The live game retains session state even after its dialogue caller is released");
        var secondGame = new RainWorldGame();
        var second = Retained(secondGame, id);
        var firstAgain = Retained(firstGame, id);
        Check(Object.ReferenceEquals(first.Target, firstAgain.Target), "The same project in another game does not replace the first game's session");
        Check(!Object.ReferenceEquals(first.Target, second.Target), "Separate games have separate sessions");
        CreatorDialogue.Reset(id);
        var resetFirst = Retained(firstGame, id);
        var resetSecond = Retained(secondGame, id);
        Check(!Object.ReferenceEquals(first.Target, resetFirst.Target) && !Object.ReferenceEquals(second.Target, resetSecond.Target), "Reset clears the selected id from every still-live game");
        GC.KeepAlive(firstGame);
        GC.KeepAlive(secondGame);
    }

    static void Affinity()
    {
        var design = Design(",\"affinity\":{\"enabled\":false,\"initial\":0.7}");
        var oracle = Scene(design);
        var records = oracle.room.game.GetStorySession.saveState.miscWorldSaveData.unrecognizedSaveStrings;
        records.Add("foreign-original");
        string tier = CreatorAffinity.Hit(oracle, design, true);
        Check(tier == "likes" && records.Count == 1 && records[0] == "foreign-original", "Disabled hit does not create an affinity save record");
        design.dialogueJson = Design(",\"affinity\":{\"enabled\":true,\"attackMode\":\"gradual\"}").dialogueJson;
        var state = CreatorAffinity.Get(oracle, design);
        float value = state.value;
        string saved = String.Join("\n", records);
        design.dialogueJson = Design(",\"affinity\":{\"enabled\":false}").dialogueJson;
        Check(CreatorAffinity.Hit(oracle, design, false) == state.Tier, "Disabled hit reports the pre-existing tier");
        Check(state.value == value && String.Join("\n", records) == saved, "Disabled hit preserves cached state and existing save bytes");
        var rules = new CreatorAffinityRules { enabled = false };
        var pure = new CreatorAffinityState(.3f, 1);
        pure.Hit(rules, false);
        Check(pure.value == .3f && pure.eligible, "Disabled pure policy cannot apply a penalty");
        Check(CreatorAffinity.Hit(null, design, false) == "neutral", "A missing owner is handled before reading save state");
        design.dialogueJson = Design(",\"affinity\":{\"enabled\":true,\"attackMode\":\"gradual\",\"rockPenalty\":0.2}").dialogueJson;
        tier = CreatorAffinity.Hit(oracle, design, false);
        Check(tier == "neutral" && Math.Abs(state.value - (value - .2f)) < .0001f && String.Join("\n", records) != saved, "Re-enabling affinity retains the normal penalty and save behavior");
    }

    static void Tick(CreatorDialogue dialogue, Oracle oracle, Player player)
    {
        oracle.room.game.clock++;
        dialogue.Update(player, new List<CreatorWorkPearl>(), oracle.room.design);
    }

    static void Exits()
    {
        var oracle = Scene(Design(""));
        var player = new Player { room = oracle.room };
        player.firstChunk.pos = new Vector2(300, 300);
        var dialogue = new CreatorDialogue(oracle);
        oracle.room.shortCutsReady = false;
        for (int i = 0; i < 5; i++) Tick(dialogue, oracle, player);
        Check(oracle.room.shortcutLookups == 0, "Unready shortcut data is not queried");
        oracle.room.shortCutsReady = true;
        var nodes = oracle.room.abstractRoom.nodes;
        oracle.room.abstractRoom.nodes = null;
        Tick(dialogue, oracle, player);
        oracle.room.abstractRoom.nodes = nodes;
        CreatorLaunch.node = 9;
        Tick(dialogue, oracle, player);
        CreatorLaunch.node = -1;
        Tick(dialogue, oracle, player);
        Check(oracle.room.shortcutLookups == 0, "Missing and out-of-range nodes return before native lookup");
        CreatorLaunch.node = 0;
        oracle.room.shortcutThrows = true;
        for (int i = 0; i < 120; i++) Tick(dialogue, oracle, player);
        Check(oracle.room.shortcutLookups > 0 && oracle.room.shortcutLookups <= 3, "Unexpected native failures are not retried each frame");
        player.inShortcut = true;
        Tick(dialogue, oracle, player);
        Check(dialogue.AwaitingReturn, "Native transit still counts as departure during retry backoff");
        player.inShortcut = false;
        oracle.room.shortcutThrows = false;
        int calls = oracle.room.shortcutLookups;
        for (int i = 0; i < 42; i++) Tick(dialogue, oracle, player);
        Check(oracle.room.shortcutLookups > calls && !dialogue.AwaitingReturn, "A repaired shortcut resumes normal proximity checks");
        player.firstChunk.pos = new Vector2(1010, 1010);
        Tick(dialogue, oracle, player);
        Check(dialogue.AwaitingReturn, "Walking to the recovered exit still pauses the unfinished meeting");
    }

    static int Main(string[] args)
    {
        try
        {
            switch (args[0])
            {
                case "profile": Profile(); break;
                case "profile-errors": ProfileErrors(); break;
                case "sessions": Sessions(); break;
                case "affinity": Affinity(); break;
                case "exits": Exits(); break;
                default: throw new ArgumentException("Unknown scenario");
            }
            Console.WriteLine("PASS " + args[0] + " " + assertions + " assertions");
            return 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(error);
            return 1;
        }
    }
}
