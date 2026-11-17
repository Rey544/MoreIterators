using System;
using System.Collections;
using System.Collections.Generic;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Globalization;
using MoreIterators;
using BepInEx.Logging;

 
 
 
namespace BepInEx
{
    public static class Paths { public static string BepInExRootPath = "isolated-bepinex"; }
}
namespace BepInEx.Logging
{
    [Flags] public enum LogLevel { Fatal = 1, Error = 2, Warning = 4, Info = 16 }
    public interface ILogSource { string SourceName { get; } }
    public interface ILogListener : IDisposable { void LogEvent(object sender, LogEventArgs args); }
    public sealed class LogEventArgs : EventArgs
    {
        public object Data;
        public LogLevel Level;
        public ILogSource Source;
        public LogEventArgs(object data, LogLevel level, ILogSource source) { Data = data; Level = level; Source = source; }
    }
    public static class Logger
    {
        public static readonly List<ILogListener> Listeners = new List<ILogListener>();
        public static void Emit(LogEventArgs args)
        {
            foreach (ILogListener listener in Listeners.ToArray()) listener.LogEvent(null, args);
        }
    }
    public class ManualLogSource : ILogSource
    {
        public string SourceName { get; private set; }
        public readonly List<string> Infos = new List<string>(), Warnings = new List<string>(), Errors = new List<string>();
        public bool FailInfo, FailError;
        public ManualLogSource(string name) { SourceName = name; }
        public void LogInfo(object value) { if(FailInfo)throw new InvalidOperationException("test info listener failure"); Infos.Add(Convert.ToString(value)); Logger.Emit(new LogEventArgs(value, LogLevel.Info, this)); }
        public void LogWarning(object value) { Warnings.Add(Convert.ToString(value)); Logger.Emit(new LogEventArgs(value, LogLevel.Warning, this)); }
        public void LogError(object value) { if(FailError)throw new InvalidOperationException("test error listener failure"); Errors.Add(Convert.ToString(value)); Logger.Emit(new LogEventArgs(value, LogLevel.Error, this)); }
    }
}
namespace UnityEngine
{
    public struct Vector2 { public float x, y; public Vector2(float x, float y) { this.x = x; this.y = y; } }
    public struct Rect { public float width, height; }
    public enum LogType { Error, Assert, Warning, Log, Exception }
    public enum StackTraceLogType { None, ScriptOnly, Full }
    public static class Application
    {
        public static event Action<string, string, LogType> logMessageReceivedThreaded;
        public static StackTraceLogType ErrorStack = StackTraceLogType.ScriptOnly;
        public static StackTraceLogType GetStackTraceLogType(LogType type) { return ErrorStack; }
        public static void SetStackTraceLogType(LogType type, StackTraceLogType value) { ErrorStack = value; }
        public static int Subscribers { get { return logMessageReceivedThreaded == null ? 0 : logMessageReceivedThreaded.GetInvocationList().Length; } }
        public static void Emit(string message, string stack, LogType type) { if (logMessageReceivedThreaded != null) logMessageReceivedThreaded(message, stack, type); }
    }
}
namespace RWCustom { public static class Custom { public static string GetFont() { return "test-font"; } } }
public class FLabel
{
    public string text;
    public FLabel(string font, string value) { text = value; }
    public UnityEngine.Rect textRect
    {
        get
        {
            float width = 0; string[] lines = (text ?? "").Split('\n');
            foreach (string line in lines)
            {
                float row = 0; var elements = StringInfo.GetTextElementEnumerator(line);
                while (elements.MoveNext()) { string element = (string)elements.Current; row += Char.IsSurrogate(element, 0) ? 24 : element[0] > 127 ? 20 : element[0] == 'W' ? 10 : 7; }
                width = Math.Max(width, row);
            }
            return new UnityEngine.Rect { width = width, height = lines.Length * 22 };
        }
    }
}
public class Options { public UnityEngine.Vector2 ScreenSize = new UnityEngine.Vector2(1366, 768); }
public class RainWorld { public Options options = new Options(); }
public static class ModManager { public static bool InitializationScreenFinished = true; }
public class AbstractRoom { public string name; }
public class Room { public AbstractRoom abstractRoom; }
public class ProcessManager
{
    public RainWorld rainWorld = new RainWorld();
    public object dialog, upcomingProcess;
    public object currentMainLoop = new object();
    public readonly List<Menu.DialogNotify> Shown = new List<Menu.DialogNotify>();
    public bool RejectDialog;
    public void ShowDialog(Menu.DialogNotify value)
    {
        if (RejectDialog) throw new InvalidOperationException("UI unavailable");
        dialog = value; Shown.Add(value);
    }
    public void Close() { var last = dialog as Menu.DialogNotify; dialog = null; if (last != null) last.Closed(); }
}
namespace Menu
{
    public class InitializationScreen { }
    public class DialogNotify
    {
        public string Text;
        public UnityEngine.Vector2 Size;
        public Action Closed;
        public DialogNotify(string text, UnityEngine.Vector2 size, ProcessManager manager, Action closed) { Text = text; Size = size; Closed = closed; }
    }
}
namespace MoreIterators
{
    public static class BuildVersion { public const string Display = "isolated-test"; }
    public static class UiText
    {
        public static void Use(RainWorld game) { }
        public static string Get(string key) { return key; }
        public static string Format(string key, object value) { return key + ": " + value; }
    }
}

public static class HookDiagnosticsCheck
{
    static int assertions, originalCalls;
    static readonly InvalidOperationException originalFailure = new InvalidOperationException("original game failure");
    static readonly BindingFlags Hidden = BindingFlags.Static | BindingFlags.NonPublic;
    static void Check(bool condition, string label) { if (!condition) throw new Exception(label); assertions++; }
    static IDictionary Issues { get { return (IDictionary)typeof(MiDiagnostics).GetField("issues", Hidden).GetValue(null); } }
    static object Field(object value, string name) { return value.GetType().GetField(name).GetValue(value); }
    static object SingleIssue() { Check(Issues.Count == 1, "exactly one diagnostic issue"); foreach (object value in Issues.Values) return value; throw new Exception("Missing issue"); }
    static void TimeField(string name, DateTime value) { typeof(MiDiagnostics).GetField(name, Hidden).SetValue(null, value); }
    static void RecordOwn(string detail)
    {
        typeof(MiDiagnostics).GetMethod("Record", Hidden).Invoke(null,
            new object[] { "MI-TEST", "MI.Test", detail, "room=TEST_AI", "MI", true, null, null });
    }
    [MethodImpl(MethodImplOptions.NoInlining)] static void OriginalFailure() { originalCalls++; throw originalFailure; }
    static void RequireScenario(ManualLogSource log)
    {
        Check(MiDiagnostics.Require(true, "PASS", "patch", "unused", "unchanged"), "successful precondition is true");
        Check(log.Warnings.Count == 0 && Issues.Count == 0, "successful precondition is silent");
        Check(!MiDiagnostics.Require(false, "MISSING-PATCH", "IL.patch", "Expected instruction was absent.\nPrivate long stack line", "room=TEST_AI"), "failed precondition is false");
        Check(log.Warnings.Count == 1, "failed precondition writes warning");
        Check(log.Warnings[0].Contains("MISSING-PATCH") && log.Warnings[0].Contains("room=TEST_AI"), "warning includes code and context");
        var manager = new ProcessManager(); MiDiagnostics.Tick(manager);
        Check(manager.Shown.Count == 1, "failed precondition schedules visible dialog");
        string text = manager.Shown[0].Text;
        Check(text.Contains("MISSING-PATCH") && text.Contains("IL.patch") && text.Contains("room=TEST_AI"), "dialog identifies failed operation");
        Check(text.Contains("Expected instruction was absent.") && !text.Contains("Private long stack line"), "dialog shows first detail line only");
        Check(text.Contains(MiDiagnostics.LogPath) && text.Contains("MI"), "dialog points to complete log and source");
    }
    static void HookScenario(ManualLogSource log)
    {
        Exception caught = null;
        try { MiDiagnostics.Hook("orig.failure", "room=TEST_AI", OriginalFailure); } catch (Exception error) { caught = error; }
        Check(originalCalls == 1, "original callback is invoked exactly once");
        Check(Object.ReferenceEquals(caught, originalFailure), "the original exception instance escapes");
        Check(caught.StackTrace.Contains("OriginalFailure"), "original throwing frame remains in stack");
        Check(log.Errors.Count == 1 && log.Errors[0].Contains("original game failure"), "original failure is recorded once");
        int after = 0; originalCalls = 0;
        try { MiDiagnostics.Hook("post.failure", "room=TEST_AI", delegate { originalCalls++; after++; throw new Exception("post hook failure"); }); }
        catch (Exception error) { Check(error.Message == "post hook failure", "post-hook failure is rethrown"); }
        Check(originalCalls == 1 && after == 1, "post-hook failure never reruns the original callback");
        int successful = 0; MiDiagnostics.Hook("success", "room=TEST_AI", delegate { successful++; });
        Check(successful == 1 && log.Errors.Count == 2, "successful callback executes once without diagnostic error");
    }
    static void RepeatedScenario(ManualLogSource log)
    {
        for (int i = 0; i < 25; i++) MiDiagnostics.Warn("REPEATED", "update", "Same failure", "room=TEST_AI");
        object issue = SingleIssue();
        Check((int)Field(issue, "Count") == 25, "repeat count is retained");
        Check(log.Warnings.Count == 1, "identical failures do not flood the log");
        var manager = new ProcessManager(); MiDiagnostics.Tick(manager); manager.Close();
        TimeField("nextNotification", DateTime.MinValue); MiDiagnostics.Tick(manager);
        Check(manager.Shown.Count == 1, "repeated failures enqueue one notification");
         
        issue.GetType().GetField("LastWritten").SetValue(issue, DateTime.UtcNow.AddSeconds(-31));
        MiDiagnostics.Warn("REPEATED", "update", "Same failure", "room=TEST_AI");
        Check(log.Warnings.Count == 2 && log.Warnings[1].Contains("count=26"), "periodic summary logs accumulated count");
    }
    static void ExternalScenario(ManualLogSource log)
    {
        var first = new ManualLogSource("ThirdParty.One"); var second = new ManualLogSource("ThirdParty.Two");
        const string detail = "System.Exception: shared message\n at Foreign.Frame()";
        first.LogWarning(detail);
        first.LogError(detail);
        second.LogError(detail);
        Logger.Emit(new LogEventArgs(detail, LogLevel.Fatal, first));
        first.LogError("MoreIterators was mentioned by another plugin");
        Check(Issues.Count == 0 && log.Errors.Count == 0 && log.Warnings.Count == 0, "external warnings, errors and fatal logs never enter MI diagnostics");
        Check(first.Errors[0] == detail && second.Errors[0] == detail, "original third-party messages remain untouched");
        var manager = new ProcessManager(); MiDiagnostics.Tick(manager);
        Check(manager.Shown.Count == 0, "third-party logs do not open MI dialogs");
        MiDiagnostics.Report("MI-OWN-ERROR", "MI.Load", new InvalidOperationException("own failure"), "room=TEST_AI");
        MiDiagnostics.Tick(manager);
        Check(log.Errors.Count == 1 && manager.Shown.Count == 1 && manager.Shown[0].Text.Contains("own failure"), "explicit MI failure still logs and notifies after third-party errors");
    }
    sealed class BadMessage { public override string ToString() { throw new Exception("broken third-party log object"); } }
    sealed class BadSource : ILogSource { public string SourceName { get { throw new Exception("broken third-party source"); } } }
    static void ListenerSafetyScenario(ManualLogSource log)
    {
        Logger.Emit(null);
        Logger.Emit(new LogEventArgs(new BadMessage(), LogLevel.Error, null));
        Logger.Emit(new LogEventArgs("source getter failure", LogLevel.Fatal, new BadSource()));
        Check(Issues.Count == 0, "malformed log objects cannot throw or enqueue corrupted issues");
        Logger.Emit(new LogEventArgs(null, LogLevel.Error, null));
        Logger.Emit(new LogEventArgs("[MI-DIAG] recursive observer marker", LogLevel.Error, null));
        Check(Issues.Count == 0, "missing sources and diagnostic-like text do not create MI issues");
        MiDiagnostics.Tick(null); MiDiagnostics.Tick(new ProcessManager { rainWorld = null });
        Check(log.Errors.Count == 0, "missing UI host does not produce a secondary failure");
    }
    static void SummaryScenario(ManualLogSource log)
    {
        string detail = new string('X', 300) + "\nSECRET STACK SECOND LINE";
        MiDiagnostics.Warn("LONG", "summary", detail, "context");
        var manager = new ProcessManager(); MiDiagnostics.Tick(manager);
        string text = manager.Shown[0].Text;
        Check(text.Replace("\n", "").Contains(new string('X', 197) + "..."), "long first line is visibly truncated and wrapped");
        Check(!text.Replace("\n", "").Contains(new string('X', 198)) && !text.Contains("SECOND LINE"), "UI preview stays bounded while wrapping across readable rows");
        Check(log.Warnings[0].Contains(detail), "complete detail remains in original log");
    }
    sealed class FilteredDiskListener : ILogListener
    {
        public readonly List<string> Errors = new List<string>();
        public void LogEvent(object sender, LogEventArgs args)
        {
             
             
            if (args.Source.SourceName == "Unity Log") return;
            if ((args.Level & (LogLevel.Error | LogLevel.Fatal)) != 0) Errors.Add(Convert.ToString(args.Data));
        }
        public void Dispose() { }
    }
    static void UnityDiskScenario(ManualLogSource log)
    {
        var disk = new FilteredDiskListener(); Logger.Listeners.Add(disk);
        var unity = new ManualLogSource("Unity Log");
        const string original = "Graphics.ConvertTexture(101): failed\n  at DressingRoom.ConvertAtlas()\n  at Game.Update()";
        Logger.Emit(new LogEventArgs(original.Split('\n')[0], LogLevel.Error, unity));
        Check(disk.Errors.Count == 0, "existing disk-listener Unity filter remains effective");
        UnityEngine.Application.Emit(original.Split('\n')[0], original.Substring(original.IndexOf('\n') + 1), UnityEngine.LogType.Error);
        UnityEngine.Application.Emit("foreign exception", "Foreign.Throw()", UnityEngine.LogType.Exception);
        UnityEngine.Application.Emit("foreign assertion", "Foreign.Assert()", UnityEngine.LogType.Assert);
        UnityEngine.Application.Emit("[MI-DIAG] guarded mirror", "internal", UnityEngine.LogType.Error);
        Check(disk.Errors.Count == 0 && Issues.Count == 0 && log.Errors.Count == 0, "Unity events are neither copied nor enqueued by MI");
        Check(UnityEngine.Application.ErrorStack == UnityEngine.StackTraceLogType.ScriptOnly && UnityEngine.Application.Subscribers == 0, "MI does not change Unity stack policy or subscribe to global logs");
        MiDiagnostics.Report("MI-OWN-ERROR", "MI.Load", new InvalidOperationException("own failure"), "room=TEST_AI");
        Check(disk.Errors.Count == 1 && disk.Errors[0].Contains("own failure"), "explicit MI errors still reach the normal disk listener");
        MiDiagnostics.Shutdown();
        Check(UnityEngine.Application.ErrorStack == UnityEngine.StackTraceLogType.ScriptOnly && UnityEngine.Application.Subscribers == 0, "shutdown leaves Unity settings unchanged");
        Check(Logger.Listeners.Count == 1 && Logger.Listeners[0] == disk, "shutdown preserves the game's existing log listener");
        Logger.Listeners.Remove(disk);
    }
    static void WrapScenario(ManualLogSource log)
    {
        var measure = new FLabel("test-font", "");
        string unicode = "English words stay readable " + new string('W', 40) + "\n" + new string('中', 40) + "𠮷é𠮷é\nC:\\long-folder\\" + new string('x', 90) + ".log";
        string wrapped = (string)typeof(MiDiagnostics).GetMethod("Wrap", Hidden).Invoke(null, new object[] { unicode, measure, 180f });
        foreach (string row in wrapped.Split('\n'))
        {
            measure.text = row; Check(measure.textRect.width <= 180, "every Latin, CJK and path row fits measured font width");
            Check(row.Length == 0 || !Char.IsLowSurrogate(row[0]) && !Char.IsHighSurrogate(row[row.Length - 1]) && row[0] != '\u0301', "wrapping preserves surrogate pairs and combining text elements");
        }
        Check(wrapped.Replace("\n", "").Replace(" ", "") == unicode.Replace("\n", "").Replace(" ", ""), "wrapping preserves every non-whitespace character");
        Check(wrapped.StartsWith("English words stay"), "wrapping prefers full words when possible");
        string detail = new string('中', 190) + " Unicode failure\nORIGINAL STACK REMAINS";
        string context = "C:\\" + new string('路', 140) + "\\SomePlugin.dll";
        MiDiagnostics.Warn("LONG-CJK", new string('W', 100), detail, context);
        var manager = new ProcessManager(); manager.rainWorld.options.ScreenSize = new UnityEngine.Vector2(1024, 600); MiDiagnostics.Tick(manager);
        var dialog = manager.Shown[0]; measure.text = dialog.Text;
        Check(measure.textRect.width <= dialog.Size.x * .86f - 20, "actual notification text respects its horizontal inset");
        Check(measure.textRect.height <= dialog.Size.y - 130 && dialog.Size.y <= 540, "notification height fits content and available screen");
        Check(dialog.Text.Contains("…") && dialog.Text.Contains(MiDiagnostics.LogPath), "bounded preview clearly shortens while retaining complete log location");
        Check(log.Warnings[0].Contains(detail) && log.Warnings[0].Contains(context), "popup layout never truncates recorded original error or context");
    }
    static void StartupQueueScenario(ManualLogSource log)
    {
        var manager = new ProcessManager(); manager.currentMainLoop = new Menu.InitializationScreen();
        ModManager.InitializationScreenFinished = false;
        const string original = "Startup failure before font reload\n at Original.Startup()";
        RecordOwn(original);
        Check(log.Errors.Count == 1 && log.Errors[0].EndsWith(original), "startup failure is fully persisted immediately");
        for (int i = 0; i < 20; i++) MiDiagnostics.Tick(manager);
        Check(manager.Shown.Count == 0 && Issues.Count == 1, "loading fonts delays notification without discarding queued issue");
        ModManager.InitializationScreenFinished = true;
        MiDiagnostics.Tick(manager);
        Check(manager.Shown.Count == 0, "WRAP_UP flag alone is insufficient while InitializationScreen can reload fonts");
        manager.currentMainLoop = new object(); manager.upcomingProcess = new object();
        MiDiagnostics.Tick(manager);
        Check(manager.Shown.Count == 0, "process transition preserves queued notification");
        manager.upcomingProcess = null; MiDiagnostics.Tick(manager);
        Check(manager.Shown.Count == 1 && manager.Shown[0].Text.Contains("Startup failure") && manager.Shown[0].Text.Contains("MI.Test"), "stable screen displays the original queued issue once");
        manager.Close(); TimeField("nextNotification", DateTime.MinValue); MiDiagnostics.Tick(manager);
        Check(manager.Shown.Count == 1 && log.Errors.Count == 1, "leaving startup does not duplicate the error or notification");
    }
    static void RethrowIdentityScenario(ManualLogSource log)
    {
        const string failure = "System.NullReferenceException: Object reference not set to an instance of an object";
        const string origin = "Revivify_Meadow.Plugin.UpdatePlr";
        string inner = failure + "\n  at " + origin + " (On.Player+orig_Update orig, Player self, System.Boolean eu) [0x0004c] in <hash>:0\n  at (wrapper dynamic-method) MonoMod.Utils.DynamicMethodDefinition.Hook<Player::Update>(Player,bool)";
        string room = inner + "\n  at MoreIterators.CreatorOverseers.<Install>b__0 (On.Room+orig_Update orig, Room room) [0x00001] in <hash>:0";
        string game = room + "\n  at MoreIterators.MoreIteratorsPlugin.<InstallHooks>b__33 (On.RainWorldGame+orig_Update orig, RainWorldGame g) [0x000ec] in <hash>:0";
        MethodInfo record = typeof(MiDiagnostics).GetMethod("Record", Hidden);
        record.Invoke(null, new object[] { "MI-HOOK-001", "On.Room.Update", room, "room=TEST_AI", "MI", true, null, null });
        record.Invoke(null, new object[] { "MI-HOOK-001", "On.RainWorldGame.Update", game, "room=TEST_AI", "MI", true, null, null });
        Logger.Emit(new LogEventArgs(game, LogLevel.Error, new ManualLogSource("Revivify_Meadow")));
        Logger.Emit(new LogEventArgs(game, LogLevel.Error, new ManualLogSource("RainMeadow")));
        string unityStack = "(wrapper dynamic-method) MonoMod.Utils.DynamicMethodDefinition.Hook<Player::Update>(Player,bool)\n" + origin + " (On.Player+orig_Update orig, Player self, System.Boolean eu) (at <hash>:0)\nMoreIterators.CreatorOverseers.<Install>b__0 (On.Room+orig_Update orig, Room room) (at <hash>:0)";
        UnityEngine.Application.Emit(failure.Substring(7), unityStack, UnityEngine.LogType.Exception);
        object issue = SingleIssue();
        Check((int)Field(issue, "Count") == 2, "two explicit MI reports share one cause; external logs do not increase its count");
        Check((string)Field(issue, "Kind") == "Exception" && (string)Field(issue, "ExceptionType") == "NullReferenceException", "System and Unity exception names are canonicalized");
        Check((string)Field(issue, "Origin") == origin, "first real throwing method survives logger wrappers and rethrows");
        Check((string)Field(issue, "Keywords") == "NullReferenceException / " + origin, "keywords are exact searchable exception and method names");
        Check((string)Field(issue, "Detail") == game, "most complete original stack is retained in memory");
        Check(log.Errors.Count == 2 && log.Errors[0].EndsWith(room) && log.Errors[1].EndsWith(game), "both explicit MI capture variants remain in disk log without external mirrors");
        var manager = new ProcessManager(); MiDiagnostics.Tick(manager);
        string text = manager.Shown[0].Text.Replace("\n", "");
        Check(text.Contains(origin) && text.Contains("NullReferenceException") && text.Contains("Search keywords"), "dialog includes real cause and searchable keywords");
        Check(!text.Contains("On.Room.Update") && !text.Contains("MoreIterators.CreatorOverseers") && !text.Contains("issues in this batch"), "capture chain is not shown as cause or five independent problems");
        Check(text.Contains(MiDiagnostics.LogPath), "dialog points to original full log path");
    }
    static void DistinctIdentityScenario(ManualLogSource log)
    {
        const string header = "NullReferenceException: same message";
        RecordOwn(header + "\n  at MoreIterators.First ()");
        RecordOwn(header + "\n  at MoreIterators.Second ()");
        RecordOwn("InvalidOperationException: same message\n  at MoreIterators.First ()");
        RecordOwn("NullReferenceException: another message\n  at MoreIterators.First ()");
        Check(Issues.Count == 4, "different throwing functions, types and messages remain separate");
        RecordOwn("System.Exception: no stack");
        RecordOwn("System.Exception: another failure without stack");
        Check(Issues.Count == 6, "different no-stack MI failures remain separate");
        foreach (object issue in Issues.Values)
            if ((string)Field(issue, "Message") == "no stack") Check((string)Field(issue, "Origin") == "", "no throwing function is invented when no stack exists");
    }
    static void NestedIdentityScenario(ManualLogSource log)
    {
        const string detail = "System.Reflection.TargetInvocationException: Exception has been thrown by the target of an invocation. ---> System.NullReferenceException: missing\n  at Foreign.Actual () [0x0001] in <hash>:0\n --- End of inner exception stack trace ---\n  at System.Reflection.RuntimeMethodInfo.Invoke () [0x0001] in <hash>:0";
        RecordOwn(detail);
        RecordOwn("NullReferenceException: missing\nForeign.Actual () (at <hash>:0)");
        object issue = SingleIssue();
        Check((string)Field(issue, "ExceptionType") == "NullReferenceException" && (string)Field(issue, "Origin") == "Foreign.Actual", "nested reflection wrapper resolves to actual inner throwing frame");
        RecordOwn("System.IO.IOException: read failed\n  at Foreign.Read ()");
        RecordOwn("IOException: read failed\nForeign.Read () (at <hash>:0)");
        Check(Issues.Count == 2, "System subnamespace names and Unity's short exception type identify the same IO fault");
    }
    static void BehaviorScenario(ManualLogSource log)
    {
        Logger.Emit(new LogEventArgs("new action: ThrowOut_KillOnSight (from General_Idle)", LogLevel.Info, new ManualLogSource("RainMeadow")));
        MiDiagnostics.Info("clone", "Initial native behavior replaced before update");
        Check(Issues.Count == 0, "normal Info actions and successful initial clone adoption are not exceptions");
        MiDiagnostics.Warn("MI-ORACLE-NATIVE-BEHAVIOR", "SSOracleBehavior.NewAction", "发现原版行为残留，已拦截。", "room=TEST_AI; action=ThrowOut_KillOnSight");
        object issue = SingleIssue();
        Check((string)Field(issue, "Kind") == "Behavior" && (string)Field(issue, "ExceptionType") == "", "explicit corrected behavior issue is distinct from thrown exception");
        Check(log.Errors.Count == 0 && log.Warnings.Count == 1, "a prevented action is a warning, not proof that a player died");
        var manager = new ProcessManager(); MiDiagnostics.Tick(manager);
        Check(manager.Shown[0].Text.Contains("Behavior issue") && manager.Shown[0].Text.Contains("已拦截") && !manager.Shown[0].Text.Contains("Runtime exception"), "behavior preview explains intervention without inventing an exception");
    }
    static void BatchLocatorScenario(ManualLogSource log)
    {
        for (int i = 0; i < 8; i++)
            RecordOwn("NullReferenceException: missing\n  at MoreIterators.Throw" + i + " ()");
        var manager = new ProcessManager(); manager.rainWorld.options.ScreenSize = new UnityEngine.Vector2(1024, 600);
        MiDiagnostics.Tick(manager);
        string text = manager.Shown[0].Text.Replace("\n", "");
        Check(text.Contains("MoreIterators.Throw0") && text.Contains("issue="), "primary throwing function and issue locator survive limited height");
        Check(text.Contains("batch=") && text.Contains(MiDiagnostics.LogPath), "remaining independent issues have a retained searchable batch locator");
        string batch = null;
        foreach (string info in log.Infos) if (info.Contains("node=diagnostic.batch")) batch = info;
        Check(batch != null, "batch index is logged");
        foreach (object issue in Issues.Values)
            Check(batch.Contains("issue=" + (string)Field(issue, "Id")) && batch.Contains((string)Field(issue, "Keywords")), "batch index lists every independent issue and search signature");
        Check(log.Errors.Count == 8, "all eight full original stacks remain logged");
        var measure = new FLabel("test-font", manager.Shown[0].Text);
        Check(measure.textRect.height <= manager.Shown[0].Size.y - 130 && manager.Shown[0].Size.y <= 540, "batch footer stays inside screen height");
    }
    static void ManyCaptureVariantsScenario(ManualLogSource log)
    {
        const string top = "System.Exception: same cause\n  at Foreign.Throw () [0x0001] in <hash>:0";
        for (int i = 0; i < 24; i++)
            RecordOwn(top + "\n  at Outer.Layer" + i + " ()");
        object issue = SingleIssue();
        Check(log.Errors.Count == 24 && log.Errors[23].EndsWith("Outer.Layer23 ()"), "new capture variants keep full stacks after bounded memory cache fills");
        var observations = (HashSet<string>)Field(issue, "Observations");
        Check(observations.Count == 16, "capture fingerprints remain bounded");
        RecordOwn(top + "\n  at Outer.Layer23 ()");
        Check(log.Errors.Count == 24, "immediately repeated capture still does not flood disk");
    }
    static void LevelScenario(ManualLogSource log)
    {
        var counts = (IDictionary)typeof(MiDiagnostics).GetField("hits", Hidden).GetValue(null);
        var manager = new ProcessManager();
        Check(MiDiagnostics.Level == "info" && !MiDiagnostics.TraceEnabled, "default spelling and level are info");
        log.Infos.Clear();
        MiDiagnostics.Info("status", "ready"); MiDiagnostics.Debug("detail", "hidden"); MiDiagnostics.Trace("trace", "hidden");
        for (int i = 0; i < 100; i++) MiDiagnostics.Hit("Update", "frame");
        TimeField("nextSummary", DateTime.MinValue); MiDiagnostics.Tick(manager);
        Check(log.Infos.Count == 1 && log.Infos[0].Contains("[MI-INFO]"), "info emits only essential info");
        Check(counts.Count == 0, "info does not count per-frame hits");
        MiDiagnostics.SetLevel("debug"); log.Infos.Clear();
        MiDiagnostics.Info("status", "ready"); MiDiagnostics.Debug("detail", "shown"); MiDiagnostics.Trace("trace", "hidden");
        MiDiagnostics.Hit("Update", "frame"); TimeField("nextSummary", DateTime.MinValue); MiDiagnostics.Tick(manager);
        Check(log.Infos.Count == 2 && log.Infos[1].Contains("[MI-DEBUG]"), "debug uses existing Info output channel");
        Check(counts.Count == 0, "debug does not count per-frame hits");
        MiDiagnostics.SetLevel("trace"); log.Infos.Clear();
        MiDiagnostics.Hit("Update", "frame"); MiDiagnostics.Hit("Update", "frame");
        Check(log.Infos.Count == 1 && log.Infos[0].Contains("[MI-TRACE]") && log.Infos[0].Contains("first-call"), "trace first call written once");
        TimeField("nextSummary", DateTime.MinValue); MiDiagnostics.Tick(manager);
        Check(log.Infos.Count == 2 && log.Infos[1].Contains("node=heartbeat") && log.Infos[1].Contains("Update=2"), "trace heartbeat has interval counts");
        MiDiagnostics.Hit("Update", "frame");
        Check(log.Infos.Count == 2, "interval reset does not repeat first call");
        TimeField("nextSummary", DateTime.MinValue); MiDiagnostics.Tick(manager);
        Check(log.Infos.Count == 3 && log.Infos[2].Contains("Update=1"), "second heartbeat counts only new hits");
        MiDiagnostics.Hit("Update", "frame"); MiDiagnostics.SetLevel("info"); log.Infos.Clear();
        TimeField("nextSummary", DateTime.MinValue); MiDiagnostics.Tick(manager);
        Check(counts.Count == 0 && log.Infos.Count == 0, "leaving trace clears pending heartbeat");
        foreach (string level in new[] { "info", "debug", "trace" })
        {
            MiDiagnostics.SetLevel(level);
            int warnings = log.Warnings.Count, errors = log.Errors.Count, dialogs = manager.Shown.Count;
            MiDiagnostics.Warn("W-" + level, "test", "warning", level);
            MiDiagnostics.Report("E-" + level, "test", new Exception("error " + level), level);
            TimeField("nextNotification", DateTime.MinValue); MiDiagnostics.Tick(manager);
            Check(log.Warnings.Count == warnings + 1 && log.Errors.Count == errors + 1, "warning and error retained at " + level);
            Check(manager.Shown.Count == dialogs + 1, "own error notification retained at " + level);
            manager.Close();
            int issueCount = Issues.Count;
            new ManualLogSource("Other mod").LogError("outside error");
            UnityEngine.Application.Emit("outside Unity error", "outside stack", UnityEngine.LogType.Exception);
            Check(Issues.Count == issueCount && Logger.Listeners.Count == 0 && UnityEngine.Application.Subscribers == 0, "no external error capture at " + level);
        }
        MiDiagnostics.SetLevel("infor");
        Check(MiDiagnostics.Level == "info" && !MiDiagnostics.TraceEnabled, "legacy infor retains info filtering and canonical name");
        MiDiagnostics.SetLevel("debug"); MiDiagnostics.SetLevel("invalid");
        Check(MiDiagnostics.Level == "info", "unknown values return to info");
    }
    public static void Main(string[] args)
    {
        MiDiagnostics.Initialize(null);
        Check(Logger.Listeners.Count == 0, "missing primary logger does not claim listener ownership");
        var log = new ManualLogSource("More Iterators"); MiDiagnostics.Initialize(log);
        Check(Logger.Listeners.Count == 0, "MI does not register a global diagnostic observer");
        Check(UnityEngine.Application.Subscribers == 0 && UnityEngine.Application.ErrorStack == UnityEngine.StackTraceLogType.ScriptOnly, "MI leaves Unity logging unchanged");
        switch (args[0])
        {
            case "require": RequireScenario(log); break;
            case "hook": HookScenario(log); break;
            case "repeated": RepeatedScenario(log); break;
            case "external": ExternalScenario(log); break;
            case "listener-safety": ListenerSafetyScenario(log); break;
            case "summary": SummaryScenario(log); break;
            case "unity-disk": UnityDiskScenario(log); break;
            case "wrap": WrapScenario(log); break;
            case "startup-queue": StartupQueueScenario(log); break;
            case "rethrow-identity": RethrowIdentityScenario(log); break;
            case "distinct-identity": DistinctIdentityScenario(log); break;
            case "nested-identity": NestedIdentityScenario(log); break;
            case "behavior": BehaviorScenario(log); break;
            case "batch-locator": BatchLocatorScenario(log); break;
            case "capture-variants": ManyCaptureVariantsScenario(log); break;
            case "levels": LevelScenario(log); break;
            default: throw new ArgumentException("Unknown scenario");
        }
        MiDiagnostics.Shutdown();
        Console.WriteLine(assertions + " diagnostic assertions passed: " + args[0]);
    }
}
