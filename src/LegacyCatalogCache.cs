using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Reflection.Emit;
using System.Security.Cryptography;
using System.Text;
using MonoMod.RuntimeDetour;

namespace MoreIterators
{
    public static class LegacyCatalogCache
    {
        internal delegate List<Dictionary<string, object>> Original();
        const string ProjectsFingerprint = "f04743fac3271abb1b4e181e76658c57ed97f0e1b658caa7c62f9fc342574664";
        const string RootFingerprint = "d5707efac5bc2f5e7abb62c2f2c4af1d49aaea0e0e1eb076666044cb533dd694";
        const string ResolveFingerprint = "290195ca569d5e5ab6e5cc5c9cd1752e0807f3ac1337b70ea0141d1a111ac2da";
        static readonly Dictionary<Assembly, Entry> entries = new Dictionary<Assembly, Entry>();
        static readonly HashSet<string> reported = new HashSet<string>(StringComparer.Ordinal);
        static long retiredCalls,
            retiredHits,
            retiredOriginals,
            retiredFailures;
        public static int InstalledCount
        {
            get
            {
                return entries.Count;
            }
        }
        public static long Calls
        {
            get
            {
                long count = retiredCalls;
                foreach (var e in entries.Values)
                    count += e.cache.calls;
                return count;
            }
        }
        public static long Hits
        {
            get
            {
                long count = retiredHits;
                foreach (var e in entries.Values)
                    count += e.cache.hits;
                return count;
            }
        }
        public static long OriginalCalls
        {
            get
            {
                long count = retiredOriginals;
                foreach (var e in entries.Values)
                    count += e.cache.originals;
                return count;
            }
        }
        public static long Failures
        {
            get
            {
                long count = retiredFailures;
                foreach (var e in entries.Values)
                    count += e.cache.failures;
                return count;
            }
        }

        public static void Refresh()
        {
            var keep = new HashSet<Assembly>();
            foreach (var assembly in AppDomain.CurrentDomain.GetAssemblies())
            {
                if (assembly.IsDynamic || !RuntimeName(assembly.GetName().Name))
                    continue;
                try
                {
                    ModManager.Mod owner;
                    MethodInfo method;
                    string reason;
                    if (!Identify(assembly, out owner, out method, out reason))
                    {
                        if (reason != null && reported.Add(assembly.FullName + ":" + reason))
                            MiDiagnostics.Info("legacy.catalog.skipped", assembly.GetName().Name + ": " + reason);
                        continue;
                    }
                    keep.Add(assembly);
                    Entry existing;
                    if (entries.TryGetValue(assembly, out existing))
                    {
                        if (ReferenceEquals(existing.owner, owner))
                            continue;
                        Remove(assembly);
                    }
                    var entry = new Entry(owner, method);
                    entries.Add(assembly, entry);
                    MiDiagnostics.Info(
                        "legacy.catalog.cached",
                        owner.id + "; template=0.3.0-0.4.1; refreshSeconds=0.25"
                    );
                }
                catch (Exception error)
                {
                    MiDiagnostics.Report(
                        "MI-LEGACY-CATALOG",
                        "LegacyCatalogCache.Refresh",
                        error,
                        assembly.GetName().Name
                    );
                }
            }
            foreach (var assembly in new List<Assembly>(entries.Keys))
                if (!keep.Contains(assembly))
                    Remove(assembly);
        }

        public static void RemoveDisabled(ModManager.Mod[] disabled)
        {
            if (disabled == null)
                return;
            foreach (var assembly in new List<Assembly>(entries.Keys))
                foreach (var mod in disabled)
                    if (
                        mod != null
                        && (ReferenceEquals(entries[assembly].owner, mod) || entries[assembly].owner.id == mod.id)
                    )
                    {
                        Remove(assembly);
                        break;
                    }
        }

        public static void Shutdown()
        {
            foreach (var assembly in new List<Assembly>(entries.Keys))
                Remove(assembly);
            reported.Clear();
        }

        static void Remove(Assembly assembly)
        {
            Entry entry;
            if (!entries.TryGetValue(assembly, out entry))
                return;
            entry.Dispose();
            retiredCalls += entry.cache.calls;
            retiredHits += entry.cache.hits;
            retiredOriginals += entry.cache.originals;
            retiredFailures += entry.cache.failures;
            entries.Remove(assembly);
        }

        sealed class Entry : IDisposable
        {
            internal readonly ModManager.Mod owner;
            internal readonly Cache cache;
            Hook hook;

            internal Entry(ModManager.Mod owner, MethodInfo method)
            {
                this.owner = owner;
                cache = new Cache(
                    Now,
                    delegate
                    {
                        return ContentAssets.Generation;
                    },
                    Available
                );
                hook = new Hook(method, new Func<Original, List<Dictionary<string, object>>>(cache.Invoke));
            }

            bool Available()
            {
                return ModManager.InitializationScreenFinished
                    && owner.enabled
                    && ModManager.ActiveMods != null
                    && ModManager.ActiveMods.Contains(owner);
            }

            public void Dispose()
            {
                if (hook != null)
                {
                    hook.Dispose();
                    hook = null;
                }
                cache.Clear();
            }
        }

        static double Now()
        {
            return Stopwatch.GetTimestamp() / (double)Stopwatch.Frequency;
        }

        internal sealed class Cache
        {
            readonly Func<double> clock;
            readonly Func<int> generation;
            readonly Func<bool> available;
            List<Dictionary<string, object>> cached;
            double readAt,
                expires;
            int loadedGeneration;
            internal long calls,
                hits,
                originals,
                failures;

            internal Cache(Func<double> clock, Func<int> generation, Func<bool> available)
            {
                this.clock = clock;
                this.generation = generation;
                this.available = available;
            }

            internal void Clear()
            {
                cached = null;
                readAt = expires = 0;
            }

            internal List<Dictionary<string, object>> Invoke(Original original)
            {
                calls++;
                try
                {
                    if (!available())
                    {
                        Clear();
                        originals++;
                        var unavailable = original();
                        if (unavailable == null || unavailable.Count == 0)
                            failures++;
                        return unavailable;
                    }
                    int context = generation();
                    double now = clock();
                    if (cached != null && context == loadedGeneration && now >= readAt && now < expires)
                    {
                        hits++;
                        return cached;
                    }
                    Clear();
                    originals++;
                    var result = original();
                    if (result == null || result.Count == 0)
                    {
                        failures++;
                        return result;
                    }
                    if (available() && context == generation())
                    {
                        cached = result;
                        loadedGeneration = context;
                        readAt = clock();
                        expires = readAt + .25;
                    }
                    return result;
                }
                catch
                {
                    Clear();
                    failures++;
                    throw;
                }
            }
        }

        internal static bool RuntimeName(string name)
        {
            const string prefix = "IteratorContent_";
            if (name == null || !name.StartsWith(prefix, StringComparison.Ordinal) || name.Length != prefix.Length + 12)
                return false;
            for (int i = prefix.Length; i < name.Length; i++)
                if (!((name[i] >= '0' && name[i] <= '9') || (name[i] >= 'a' && name[i] <= 'f')))
                    return false;
            return true;
        }

        internal static bool Identify(
            Assembly assembly,
            out ModManager.Mod owner,
            out MethodInfo projects,
            out string reason
        )
        {
            owner = null;
            projects = null;
            reason = null;
            string name = assembly.GetName().Name;
            if (!RuntimeName(name) || assembly.IsDynamic || ModManager.ActiveMods == null)
                return false;
            var paths = assembly.GetType(name + ".RuntimePaths", false);
            var catalog = assembly.GetType(name + ".IteratorCatalog", false);
            var assets = assembly.GetType(name + ".ContentAssets", false);
            var plugin = assembly.GetType(name + ".MoreIteratorsPlugin", false);
            if (paths == null || catalog == null || assets == null || plugin == null)
            {
                reason = "not a known MI export shape";
                return false;
            }
            if (
                catalog.GetField(
                    "ProjectsCacheVersion",
                    BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic
                ) != null
            )
                return false;
            var idField = paths.GetField("ModId", BindingFlags.Static | BindingFlags.Public);
            if (idField == null || !idField.IsLiteral || idField.FieldType != typeof(string))
            {
                reason = "missing literal runtime owner";
                return false;
            }
            string id = idField.GetRawConstantValue() as string;
            if (String.IsNullOrEmpty(id))
                return false;
            foreach (var mod in ModManager.ActiveMods)
                if (mod != null && mod.enabled && mod.id == id)
                {
                    if (owner != null)
                    {
                        reason = "ambiguous enabled owner";
                        return false;
                    }
                    owner = mod;
                }
            if (owner == null)
                return false;
            if (!PluginOwner(plugin, id) || !OwnedPlugin(assembly.Location, owner))
            {
                reason = "runtime plugin ownership does not match the enabled export";
                return false;
            }
            string manifest = ContentAssets.ResolveOwnedFile(id, "content-manifest.json");
            if (String.IsNullOrEmpty(manifest) || !File.Exists(manifest))
            {
                reason = "independent export manifest missing";
                return false;
            }
            var data = Json.Deserialize(File.ReadAllText(manifest)) as Dictionary<string, object>;
            object value;
            if (
                data == null
                || !data.TryGetValue("schema", out value)
                || !(value is string)
                || (string)value != "moreiterators.playback-export.v1"
                || !data.TryGetValue("independentMod", out value)
                || !(value is bool)
                || !(bool)value
                || !data.TryGetValue("runtimeVersion", out value)
                || !(value is string)
            )
            {
                reason = "not an explicit MI independent export";
                return false;
            }
            string version = (string)value;
            if (
                (version != "0.3.0" && version != "0.4.0" && version != "0.4.1")
                || !new Version(version + ".0").Equals(assembly.GetName().Version)
            )
            {
                reason = "runtime version outside the verified legacy family";
                return false;
            }
            projects = catalog.GetMethod(
                "Projects",
                BindingFlags.Static | BindingFlags.Public,
                null,
                Type.EmptyTypes,
                null
            );
            var root = paths.GetMethod(
                "TryContentRoot",
                BindingFlags.Static | BindingFlags.Public,
                null,
                new Type[] { typeof(string).MakeByRefType() },
                null
            );
            var resolve = assets.GetMethod(
                "ResolveOwnedFile",
                BindingFlags.Static | BindingFlags.Public,
                null,
                new Type[] { typeof(string), typeof(string) },
                null
            );
            if (
                projects == null
                || projects.ReturnType != typeof(List<Dictionary<string, object>>)
                || root == null
                || root.ReturnType != typeof(bool)
                || resolve == null
                || resolve.ReturnType != typeof(string)
            )
            {
                reason = "legacy catalogue signatures differ";
                return false;
            }
            if (
                Fingerprint(projects, name, id) != ProjectsFingerprint
                || Fingerprint(root, name, id) != RootFingerprint
                || Fingerprint(resolve, name, id) != ResolveFingerprint
            )
            {
                reason = "unrecognized catalogue template; no hook installed";
                return false;
            }
            return true;
        }

        static bool PluginOwner(Type plugin, string owner)
        {
            foreach (var attribute in CustomAttributeData.GetCustomAttributes(plugin))
                if (
                    attribute.Constructor.DeclaringType.FullName == "BepInEx.BepInPlugin"
                    && attribute.Constructor.DeclaringType.Assembly.GetName().Name == "BepInEx"
                    && attribute.ConstructorArguments.Count == 3
                    && attribute.ConstructorArguments[0].ArgumentType == typeof(string)
                )
                    return (string)attribute.ConstructorArguments[0].Value == owner;
            return false;
        }

        internal static bool OwnedPlugin(string file, ModManager.Mod owner)
        {
            return InPlugins(file, owner.path)
                || (owner.hasTargetedVersionFolder && InPlugins(file, owner.TargetedPath))
                || (owner.hasNewestFolder && InPlugins(file, owner.NewestPath));
        }

        static bool InPlugins(string file, string root)
        {
            if (String.IsNullOrEmpty(file) || String.IsNullOrEmpty(root))
                return false;
            string directory =
                Path.GetFullPath(Path.Combine(root, "plugins"))
                    .TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar) + Path.DirectorySeparatorChar;
            return Path.GetFullPath(file).StartsWith(directory, StringComparison.OrdinalIgnoreCase);
        }

        internal static string Fingerprint(MethodInfo method, string runtime, string owner)
        {
            var body = method.GetMethodBody();
            if (body == null)
                return "";
            byte[] il = body.GetILAsByteArray();
            var instructions = new List<Instruction>();
            var positions = new Dictionary<int, int>();
            int offset = 0;
            while (offset < il.Length)
            {
                int start = offset;
                ushort code = il[offset++];
                if (code == 0xfe)
                    code = (ushort)(0xfe00 | il[offset++]);
                OpCode op;
                if (!opcodes.TryGetValue(code, out op))
                    throw new InvalidDataException("Unknown IL opcode.");
                object operand = null;
                switch (op.OperandType)
                {
                    case OperandType.InlineNone:
                        break;
                    case OperandType.ShortInlineI:
                        operand = (sbyte)il[offset++];
                        break;
                    case OperandType.InlineI:
                        operand = BitConverter.ToInt32(il, offset);
                        offset += 4;
                        break;
                    case OperandType.InlineI8:
                        operand = BitConverter.ToInt64(il, offset);
                        offset += 8;
                        break;
                    case OperandType.ShortInlineR:
                        operand = BitConverter.ToSingle(il, offset);
                        offset += 4;
                        break;
                    case OperandType.InlineR:
                        operand = BitConverter.ToDouble(il, offset);
                        offset += 8;
                        break;
                    case OperandType.ShortInlineVar:
                        operand = il[offset++];
                        break;
                    case OperandType.InlineVar:
                        operand = BitConverter.ToUInt16(il, offset);
                        offset += 2;
                        break;
                    case OperandType.ShortInlineBrTarget:
                        {
                            int delta = (sbyte)il[offset++];
                            operand = offset + delta;
                            break;
                        }
                    case OperandType.InlineBrTarget:
                        {
                            int delta = BitConverter.ToInt32(il, offset);
                            offset += 4;
                            operand = offset + delta;
                            break;
                        }
                    case OperandType.InlineSwitch:
                        {
                            int count = BitConverter.ToInt32(il, offset);
                            offset += 4;
                            int end = offset + count * 4;
                            var targets = new int[count];
                            for (int i = 0; i < count; i++)
                            {
                                targets[i] = end + BitConverter.ToInt32(il, offset);
                                offset += 4;
                            }
                            operand = targets;
                            break;
                        }
                    case OperandType.InlineString:
                    case OperandType.InlineMethod:
                    case OperandType.InlineField:
                    case OperandType.InlineType:
                    case OperandType.InlineTok:
                        operand = BitConverter.ToInt32(il, offset);
                        offset += 4;
                        break;
                    default:
                        throw new InvalidDataException("Unsupported catalogue IL operand.");
                }
                positions.Add(start, instructions.Count);
                instructions.Add(new Instruction { op = op, operand = operand });
            }
            positions.Add(il.Length, instructions.Count);
            var text = new StringBuilder();
            Assembly candidate = method.Module.Assembly;
            Add(text, "method", Member(method, runtime, candidate));
            Add(text, "init", body.InitLocals.ToString());
            foreach (var local in body.LocalVariables)
                Add(text, "local", TypeName(local.LocalType, runtime, candidate) + ":" + local.IsPinned);
            foreach (var instruction in instructions)
            {
                object value = instruction.operand;
                string token = "";
                switch (instruction.op.OperandType)
                {
                    case OperandType.InlineString:
                        token = method.Module.ResolveString((int)value);
                        if (token == owner)
                            token = "$OWNER$";
                        else if (token == "[More Iterators content " + owner + "] Cannot load registry at ")
                            token = "[More Iterators content $OWNER$] Cannot load registry at ";
                        break;
                    case OperandType.InlineMethod:
                    case OperandType.InlineField:
                    case OperandType.InlineType:
                    case OperandType.InlineTok:
                        token = Member(method.Module.ResolveMember((int)value), runtime, candidate);
                        break;
                    case OperandType.ShortInlineBrTarget:
                    case OperandType.InlineBrTarget:
                        token = positions[(int)value].ToString(CultureInfo.InvariantCulture);
                        break;
                    case OperandType.InlineSwitch:
                        foreach (int target in (int[])value)
                            token += positions[target].ToString(CultureInfo.InvariantCulture) + ",";
                        break;
                    default:
                        if (value != null)
                            token = Convert.ToString(value, CultureInfo.InvariantCulture);
                        break;
                }
                Add(text, instruction.op.Name, token);
            }
            foreach (var clause in body.ExceptionHandlingClauses)
            {
                string item =
                    clause.Flags
                    + ":"
                    + positions[clause.TryOffset]
                    + ":"
                    + positions[clause.TryOffset + clause.TryLength]
                    + ":"
                    + positions[clause.HandlerOffset]
                    + ":"
                    + positions[clause.HandlerOffset + clause.HandlerLength];
                if (clause.Flags == ExceptionHandlingClauseOptions.Clause)
                    item += ":" + TypeName(clause.CatchType, runtime, candidate);
                if (clause.Flags == ExceptionHandlingClauseOptions.Filter)
                    item += ":" + positions[clause.FilterOffset];
                Add(text, "eh", item);
            }
            using (var sha = SHA256.Create())
                return BitConverter
                    .ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(text.ToString())))
                    .Replace("-", "")
                    .ToLowerInvariant();
        }

        sealed class Instruction
        {
            internal OpCode op;
            internal object operand;
        }

        static readonly Dictionary<ushort, OpCode> opcodes = ReadOpcodes();

        static Dictionary<ushort, OpCode> ReadOpcodes()
        {
            var result = new Dictionary<ushort, OpCode>();
            foreach (var field in typeof(OpCodes).GetFields(BindingFlags.Static | BindingFlags.Public))
                if (field.FieldType == typeof(OpCode))
                {
                    var value = (OpCode)field.GetValue(null);
                    result[(ushort)value.Value] = value;
                }
            return result;
        }

        static void Add(StringBuilder text, string key, string value)
        {
            text.Append(key).Append(':').Append(value.Length).Append(':').Append(value).Append('\n');
        }

        static string TypeName(Type type, string runtime, Assembly candidate)
        {
            if (type.IsByRef)
                return TypeName(type.GetElementType(), runtime, candidate) + "&";
            if (type.IsPointer)
                return TypeName(type.GetElementType(), runtime, candidate) + "*";
            if (type.IsArray)
                return TypeName(type.GetElementType(), runtime, candidate)
                    + "["
                    + new string(',', type.GetArrayRank() - 1)
                    + "]";
            if (type.IsGenericParameter)
                return "!" + type.GenericParameterPosition;
            string name = type.IsGenericType ? type.GetGenericTypeDefinition().FullName : type.FullName;
            if (type.Assembly == candidate && name.StartsWith(runtime + ".", StringComparison.Ordinal))
                name = "$RUNTIME$" + name.Substring(runtime.Length);
            else
                name = "[" + type.Assembly.GetName().Name + "]" + name;
            if (type.IsGenericType)
            {
                name += "<";
                foreach (var arg in type.GetGenericArguments())
                    name += TypeName(arg, runtime, candidate) + ";";
                name += ">";
            }
            return name;
        }

        static string Member(MemberInfo member, string runtime, Assembly candidate)
        {
            var type = member as Type;
            if (type != null)
                return TypeName(type, runtime, candidate);
            var field = member as FieldInfo;
            if (field != null)
                return TypeName(field.DeclaringType, runtime, candidate)
                    + "::"
                    + field.Name
                    + ":"
                    + TypeName(field.FieldType, runtime, candidate);
            var method = member as MethodBase;
            if (method == null)
                throw new InvalidDataException("Unsupported metadata reference.");
            string text =
                TypeName(method.DeclaringType, runtime, candidate)
                + "::"
                + method.Name
                + ":"
                + (method.IsStatic ? "static" : "instance")
                + "(";
            foreach (var parameter in method.GetParameters())
                text += TypeName(parameter.ParameterType, runtime, candidate) + ";";
            text += ")";
            var info = method as MethodInfo;
            if (info != null)
                text += "->" + TypeName(info.ReturnType, runtime, candidate);
            return text;
        }
    }
}
