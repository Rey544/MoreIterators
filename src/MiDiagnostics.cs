using System;
using System.Collections.Generic;
using System.IO;
using System.Globalization;
using System.Text.RegularExpressions;
using System.Security.Cryptography;
using System.Text;
using BepInEx.Logging;

namespace MoreIterators
{
    public static class MiDiagnostics
    {
        const int MaximumIssues = 100;
        static readonly object gate = new object();
        static readonly Queue<Issue> pending = new Queue<Issue>();
        static readonly Dictionary<string, Issue> issues = new Dictionary<string, Issue>();
        static readonly Dictionary<string, int> hits = new Dictionary<string, int>();
        static readonly HashSet<string> seenHits = new HashSet<string>();
        static readonly string session = Guid.NewGuid().ToString("N").Substring(0, 12);
        static ManualLogSource log;
        static DateTime nextSummary = DateTime.UtcNow.AddSeconds(30);
        static DateTime nextNotification = DateTime.MinValue;
        static bool dialogOpen;
        static int nextIssueId,
            nextBatchId;
        static volatile int verbosity;

        public static string Level
        {
            get
            {
                return verbosity == 2 ? "trace"
                    : verbosity == 1 ? "debug"
                    : "info";
            }
        }
        public static bool TraceEnabled
        {
            get
            {
                return verbosity == 2;
            }
        }

        public static void SetLevel(string value)
        {
            int selected =
                value == "trace" ? 2
                : value == "debug" ? 1
                : 0;
            lock (gate)
            {
                if (selected == verbosity)
                    return;
                verbosity = selected;
                hits.Clear();
                nextSummary = DateTime.UtcNow.AddSeconds(30);
            }
            Info("diagnostics.level", "level=" + Level);
        }

        sealed class Issue
        {
            public string Code,
                Node,
                Context,
                Detail,
                Source,
                Severity;
            public string Kind,
                ExceptionType,
                Origin,
                Message,
                Keywords,
                Id;
            public readonly HashSet<string> Observations = new HashSet<string>();
            public readonly Queue<string> ObservationOrder = new Queue<string>();
            public int Count = 1;
            public DateTime LastWritten = DateTime.UtcNow;
        }

        public static void Initialize(ManualLogSource source)
        {
            if (source == null)
                return;
            log = source;
            Info("startup", "version=" + BuildVersion.Display + "; log=" + LogPath);
        }

        public static string LogPath
        {
            get
            {
                return Path.Combine(BepInEx.Paths.BepInExRootPath, "LogOutput.log");
            }
        }

        public static string Context(Room room)
        {
            return room == null || room.abstractRoom == null ? "room=<unavailable>" : "room=" + room.abstractRoom.name;
        }

        public static void Info(string node, string context)
        {
            Write("MI-INFO", node, context);
        }

        public static void Debug(string node, string context)
        {
            if (verbosity >= 1)
                Write("MI-DEBUG", node, context);
        }

        public static void Trace(string node, string context)
        {
            if (TraceEnabled)
                Write("MI-TRACE", node, context);
        }

        static void Write(string tag, string node, string context)
        {
            var target = log;
            if (target != null)
                target.LogInfo("[" + tag + "] session=" + session + " node=" + node + " " + context);
        }

        public static void Hit(string node, string context)
        {
            if (!TraceEnabled || log == null)
                return;
            bool first;
            lock (gate)
            {
                if (!TraceEnabled)
                    return;
                int count;
                hits.TryGetValue(node, out count);
                hits[node] = count + 1;
                first = seenHits.Add(node);
            }
            if (first)
                Trace(node, "first-call " + context);
        }

        // Hook failures are logged, then rethrown with the original stack. We never
        // rerun orig after a partial invocation or silently claim that it succeeded.
        public static void Hook(string node, string context, Action action)
        {
            Hit(node, context);
            try
            {
                action();
            }
            catch (Exception error)
            {
                Report("MI-HOOK-001", node, error, context);
                throw;
            }
        }

        public static void Cleanup(string code, string node, Action action, string context)
        {
            try
            {
                action();
            }
            catch (Exception error)
            {
                try
                {
                    Report(code, node, error, context);
                }
                catch (Exception) { }
            }
        }

        public static void CloseProcess(string node, string context, Action cleanup, Action original)
        {
            Cleanup(
                "MI-SHUTDOWN-TRACE",
                node,
                delegate
                {
                    Hit(node, context);
                },
                context
            );
            Cleanup("MI-SHUTDOWN-CLEANUP", node, cleanup, context);
            try
            {
                original();
            }
            catch (Exception error)
            {
                try
                {
                    Report("MI-HOOK-001", node, error, context);
                }
                catch (Exception) { }
                throw;
            }
        }

        public static bool Require(bool condition, string code, string node, string explanation, string context)
        {
            if (!condition)
                Warn(code, node, explanation, context);
            return condition;
        }

        public static void Warn(string code, string node, string detail, string context)
        {
            Record(
                code,
                node,
                detail,
                context,
                "MI",
                false,
                null,
                code == "MI-ORACLE-NATIVE-BEHAVIOR" ? "Behavior" : "Warning"
            );
        }

        // Explicit behavior faults are not exceptions. Normal Info/trace messages,
        // including ordinary game actions, never become error notifications.
        public static void Behavior(string code, string node, string detail, string context)
        {
            Record(code, node, detail, context, "MI", false, null, "Behavior");
        }

        public static void Report(string code, string node, Exception error, string context)
        {
            Record(
                code,
                node,
                error == null ? "No exception details were supplied." : error.ToString(),
                context,
                "MI",
                true
            );
        }

        static void Record(
            string code,
            string node,
            string detail,
            string context,
            string source,
            bool error,
            string severity = null,
            string kind = null
        )
        {
            severity = severity ?? (error ? "Error" : "Warning");
            string exceptionType,
                origin,
                message;
            IdentifyException(detail, out exceptionType, out origin, out message);
            bool isException = exceptionType.Length != 0;
            kind = isException ? "Exception" : kind ?? "Log";

            // If no throwing frame is available we retain the reporting source:
            // matching generic messages alone is insufficient to identify it.
            string key = isException
                ? "Exception|"
                    + exceptionType
                    + "|"
                    + message
                    + "|"
                    + (origin.Length == 0 ? "unlocated:" + source : origin)
                : source + "|" + severity + "|" + code + "|" + node + "|" + context + "|" + detail;
            string observation = Fingerprint(
                source + "|" + severity + "|" + code + "|" + node + "|" + context + "|" + detail
            );
            Issue issue;
            bool write = false;
            lock (gate)
            {
                if (issues.TryGetValue(key, out issue))
                {
                    issue.Count++;
                    // Keep the longest original stack in memory. New capture
                    // variants are also written verbatim for exported disk logs.
                    if ((detail ?? "").Length > (issue.Detail ?? "").Length)
                        issue.Detail = detail;
                    bool newObservation = !issue.Observations.Contains(observation);
                    if (newObservation)
                    {
                        if (issue.ObservationOrder.Count >= 16)
                            issue.Observations.Remove(issue.ObservationOrder.Dequeue());
                        issue.Observations.Add(observation);
                        issue.ObservationOrder.Enqueue(observation);
                    }
                    if (newObservation || (DateTime.UtcNow - issue.LastWritten).TotalSeconds >= 30)
                    {
                        issue.LastWritten = DateTime.UtcNow;
                        write = true;
                    }
                }
                else
                {
                    if (issues.Count >= MaximumIssues)
                    {
                        // Bound memory, never discard the original error from the disk log.
                        string oldest = null;
                        foreach (string existing in issues.Keys)
                        {
                            oldest = existing;
                            break;
                        }
                        if (oldest != null)
                            issues.Remove(oldest);
                    }
                    issue = new Issue
                    {
                        Code = code,
                        Node = node,
                        Detail = detail,
                        Context = context,
                        Source = source,
                        Severity = severity,
                        Kind = kind,
                        ExceptionType = exceptionType,
                        Origin = origin,
                        Message = message,
                        Id = session + "-" + (++nextIssueId).ToString(CultureInfo.InvariantCulture),
                        Keywords = isException ? exceptionType + (origin.Length == 0 ? "" : " / " + origin) : code
                    };
                    issue.Observations.Add(observation);
                    issue.ObservationOrder.Enqueue(observation);
                    issues.Add(key, issue);
                    if (pending.Count >= MaximumIssues)
                        pending.Dequeue();
                    pending.Enqueue(issue);
                    write = true;
                }
            }

            if (write && log != null)
            {
                string text =
                    "[MI-DIAG] session="
                    + session
                    + " code="
                    + code
                    + " node="
                    + node
                    + " issue="
                    + issue.Id
                    + " source="
                    + source
                    + " severity="
                    + severity
                    + " count="
                    + issue.Count
                    + " kind="
                    + issue.Kind
                    + " exception="
                    + issue.ExceptionType
                    + " origin="
                    + issue.Origin
                    + " keywords="
                    + issue.Keywords
                    + " context="
                    + context
                    + "\n"
                    + detail;
                if (error)
                    log.LogError(text);
                else
                    log.LogWarning(text);
            }
        }

        public static void Tick(ProcessManager manager)
        {
            if (manager == null || manager.rainWorld == null)
                return;
            UiText.Use(manager.rainWorld);
            if (TraceEnabled && DateTime.UtcNow >= nextSummary)
            {
                nextSummary = DateTime.UtcNow.AddSeconds(30);
                var values = new List<string>();
                lock (gate)
                {
                    foreach (var item in hits)
                        values.Add(item.Key + "=" + item.Value);
                    hits.Clear();
                }
                if (values.Count > 0)
                    Trace("heartbeat", String.Join(",", values.ToArray()));
            }
            // InitializationScreen reloads font atlases in LOAD_FONTS and
            // again in WRAP_UP, which sets InitializationScreenFinished before
            // that final reload. Keep queued issues until the screen has left;
            // existing FLabels cannot safely survive those atlas replacements.
            if (!ModManager.InitializationScreenFinished || manager.currentMainLoop is Menu.InitializationScreen)
                return;
            if (
                dialogOpen
                || manager.dialog != null
                || manager.upcomingProcess != null
                || DateTime.UtcNow < nextNotification
            )
                return;
            Issue issue;
            Issue[] additional;
            lock (gate)
            {
                if (pending.Count == 0)
                    return;
                issue = pending.Dequeue();
                additional = pending.ToArray();
                pending.Clear();
            }
            try
            {
                var screen = manager.rainWorld.options.ScreenSize;
                float panelWidth = Math.Max(320, Math.Min(720, screen.x - 60));
                float maximumHeight = Math.Max(260, Math.Min(620, screen.y - 60));
                var measure = new FLabel(RWCustom.Custom.GetFont(), "");
                string batch = session + "-b" + (++nextBatchId).ToString(CultureInfo.InvariantCulture);
                var entries = new List<string>();
                entries.Add("issue=" + issue.Id + " " + issue.Keywords);
                foreach (Issue item in additional)
                    entries.Add("issue=" + item.Id + " " + item.Keywords);
                Info("diagnostic.batch", "batch=" + batch + "\n" + String.Join("\n", entries.ToArray()));
                string message = Notification(
                    issue,
                    additional,
                    batch,
                    measure,
                    panelWidth * .86f - 20,
                    maximumHeight - 130
                );
                measure.text = message;
                float panelHeight = Math.Max(300, measure.textRect.height + 130);
                dialogOpen = true;
                nextNotification = DateTime.UtcNow.AddSeconds(15);
                manager.ShowDialog(
                    new Menu.DialogNotify(
                        message,
                        new UnityEngine.Vector2(panelWidth, panelHeight),
                        manager,
                        delegate
                        {
                            dialogOpen = false;
                        }
                    )
                );
            }
            catch (Exception error)
            {
                dialogOpen = false;
                // Do not recursively enqueue errors caused by the error display itself.
                if (log != null)
                    log.LogError("[MI-DIAG] code=MI-DIAGNOSTIC-UI node=notification\n" + error);
            }
        }

        static string Notification(
            Issue issue,
            Issue[] additional,
            string batch,
            FLabel measure,
            float width,
            float height
        )
        {
            string body;
            if (issue.Kind == "Exception")
                body =
                    UiText.Get("Runtime exception")
                    + ": "
                    + issue.ExceptionType
                    + "\n"
                    + UiText.Get("Throwing function")
                    + ": "
                    + (
                        String.IsNullOrEmpty(issue.Origin)
                            ? UiText.Get("No stack supplied")
                            : Shorten(issue.Origin, 180)
                    );
            else
                body =
                    UiText.Get(
                        issue.Kind == "Behavior"
                            ? "Behavior issue"
                            : "A runtime error was detected. The current operation may be incomplete."
                    )
                    + "\n"
                    + Summary(issue.Detail)
                    + "\n"
                    + UiText.Get("Recorded by")
                    + ": "
                    + Shorten(issue.Source + " (" + issue.Node + ")", 160);
            body +=
                "\n"
                + UiText.Get("Search keywords")
                + ": "
                + (issue.Kind == "Exception" ? "" : issue.Code + " / ")
                + "issue="
                + issue.Id;
            if (issue.Kind == "Exception")
                body += "\n" + Shorten(issue.Message, 200);
            if (issue.Source == "MI" && !String.IsNullOrEmpty(issue.Context))
                body += "\n" + Shorten(issue.Context, 160);
            if (additional.Length > 0)
            {
                body += "\n" + UiText.Format("{0} issues in this batch; see the full log.", additional.Length + 1);
                for (int i = 0; i < Math.Min(2, additional.Length); i++)
                    body += "\n" + Shorten(additional[i].Keywords, 120);
            }
            // Keep a searchable batch locator even if available height cuts the
            // other previews. The batch in the full log lists every issue ID.
            string footer = Wrap(
                (additional.Length > 0 ? UiText.Get("Find all issues") + ": batch=" + batch + "\n" : "")
                    + UiText.Get("Full exception log:")
                    + "\n"
                    + LogPath,
                measure,
                width
            );
            var rows = new List<string>(Wrap(body, measure, width).Split('\n'));
            bool shortened = false;
            while (true)
            {
                string result = String.Join("\n", rows.ToArray()) + (shortened ? "\n…" : "") + "\n" + footer;
                measure.text = result;
                if (measure.textRect.height <= height || rows.Count <= 1)
                    return result;
                // Only the notification preview is shortened. The complete
                // exception, source and context have already been logged.
                rows.RemoveAt(rows.Count - 1);
                shortened = true;
            }
        }

        static string Wrap(string text, FLabel measure, float width)
        {
            var rows = new List<string>();
            foreach (string paragraph in (text ?? "").Replace("\r\n", "\n").Replace('\r', '\n').Split('\n'))
            {
                int[] boundaries = StringInfo.ParseCombiningCharacters(paragraph);
                if (boundaries.Length == 0)
                {
                    rows.Add("");
                    continue;
                }
                int offset = 0;
                while (offset < boundaries.Length)
                {
                    int low = offset + 1,
                        high = boundaries.Length,
                        fit = offset + 1;
                    while (low <= high)
                    {
                        int count = (low + high) / 2;
                        int end = count == boundaries.Length ? paragraph.Length : boundaries[count];
                        measure.text = paragraph.Substring(boundaries[offset], end - boundaries[offset]);
                        if (measure.textRect.width <= width)
                        {
                            fit = count;
                            low = count + 1;
                        }
                        else
                            high = count - 1;
                    }
                    int next = fit;
                    if (fit < boundaries.Length)
                    {
                        // Prefer a complete word; long identifiers, paths and
                        // CJK are split only at Unicode text-element boundaries.
                        for (int i = fit - 1; i > offset; i--)
                            if (Char.IsWhiteSpace(paragraph, boundaries[i]))
                            {
                                fit = i;
                                next = i + 1;
                                break;
                            }
                    }
                    int stop = fit == boundaries.Length ? paragraph.Length : boundaries[fit];
                    rows.Add(paragraph.Substring(boundaries[offset], stop - boundaries[offset]).TrimEnd());
                    offset = next;
                }
            }
            return String.Join("\n", rows.ToArray());
        }

        static string Shorten(string text, int maximum)
        {
            if (String.IsNullOrEmpty(text))
                return "";
            int[] characters = StringInfo.ParseCombiningCharacters(text);
            return characters.Length <= maximum ? text : text.Substring(0, characters[maximum - 3]) + "...";
        }

        static string Summary(string detail)
        {
            if (String.IsNullOrEmpty(detail))
                return "";
            string[] lines = detail.Split(new[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries);
            return Shorten(lines.Length == 0 ? "" : lines[0], 200);
        }

        static string Fingerprint(string text)
        {
            using (var hash = SHA256.Create())
                return Convert.ToBase64String(hash.ComputeHash(Encoding.UTF8.GetBytes(text)));
        }

        static void IdentifyException(string detail, out string type, out string origin, out string message)
        {
            type = origin = message = "";
            foreach (string raw in (detail ?? "").Replace("\r\n", "\n").Split('\n'))
            {
                string line = raw.Trim();
                // Handles System.XException, Unity's XException and nested
                // exceptions printed after '--->'. The deepest header before
                // the first real stack frame is the useful cause, not Invoke().
                Match header = Regex.Match(line, @"(?:^|--->\s*)([A-Za-z_][\w.`+]*Exception|Exception):\s*(.*)$");
                if (header.Success)
                {
                    type = header.Groups[1].Value;
                    if (type.StartsWith("System.", StringComparison.Ordinal))
                        type = type.Substring(type.LastIndexOf('.') + 1);
                    message = header.Groups[2].Value.Trim();
                    // A wrapper and its inner header can be on one line.
                    int inner = line.LastIndexOf("--->", StringComparison.Ordinal);
                    if (inner >= 0)
                    {
                        Match nested = Regex.Match(
                            line.Substring(inner + 4).Trim(),
                            @"^([A-Za-z_][\w.`+]*Exception|Exception):\s*(.*)$"
                        );
                        if (nested.Success)
                        {
                            type = nested.Groups[1].Value;
                            if (type.StartsWith("System.", StringComparison.Ordinal))
                                type = type.Substring(type.LastIndexOf('.') + 1);
                            message = nested.Groups[2].Value.Trim();
                        }
                    }
                    continue;
                }
                if (
                    type.Length == 0
                    || line.StartsWith("(wrapper", StringComparison.Ordinal)
                    || line.StartsWith("at (wrapper", StringComparison.Ordinal)
                )
                    continue;
                bool dotnet = line.StartsWith("at ", StringComparison.Ordinal);
                if (dotnet)
                    line = line.Substring(3).TrimStart();
                int parameters = line.IndexOf('(');
                if (parameters <= 0)
                    continue;
                if (!dotnet && line.IndexOf(" (at ", StringComparison.Ordinal) < 0)
                    continue;
                string candidate = line.Substring(0, parameters).Trim();
                if (
                    candidate.IndexOf('.') < 0
                    || candidate.StartsWith("MonoMod.Utils.DynamicMethodDefinition", StringComparison.Ordinal)
                )
                    continue;
                origin = candidate;
                break;
            }
        }

        public static void Shutdown()
        {
            log = null;
        }
    }
}
