using System;
using System.Reflection;
using Mono.Cecil;
using Mono.Cecil.Cil;
using MonoMod.Cil;
using MonoMod.RuntimeDetour;

namespace MoreIterators
{
    // Optional compatibility for Revivify Meadow. Its own original Player.Update
    // and every unrelated exception remain untouched; only its dead-player scan
    // is skipped when that player no longer has a complete room to scan.
    public static class RevivifyCompatibility
    {
        const string LeaseKey = "MoreIterators.RevivifyRoomGuard.v1";
        const string TargetName = "Revivify_Meadow.Plugin.UpdatePlr";
        static readonly object owner = new object();
        static ILHook hook;
        static DateTime nextWarning;

        public static bool Installed { get { return hook != null; } }

        public static bool Install()
        {
            if (hook != null) return true;
            Type plugin = null;
            foreach (Assembly assembly in AppDomain.CurrentDomain.GetAssemblies())
            {
                Type candidate = assembly.GetType("Revivify_Meadow.Plugin", false);
                if (candidate == null) continue;
                if (plugin != null)
                {
                    MiDiagnostics.Warn("MI-REVIVIFY-VERSION", TargetName,
                        UiText.Get("Multiple copies of Revivify Meadow were detected. The room-scan guard was not installed."), "Revivify Meadow");
                    return false;
                }
                plugin = candidate;
            }
            // No dependency: normal when the player does not use Revivify.
            if (plugin == null) return false;

            lock (AppDomain.CurrentDomain)
            {
                if (AppDomain.CurrentDomain.GetData(LeaseKey) != null) return false;
                AppDomain.CurrentDomain.SetData(LeaseKey, owner);
                try
                {
                    MethodInfo target = plugin.GetMethod("UpdatePlr", BindingFlags.Instance | BindingFlags.NonPublic,
                        null, new Type[] { typeof(On.Player.orig_Update), typeof(Player), typeof(bool) }, null);
                    if (target == null || target.ReturnType != typeof(void))
                        throw new InvalidOperationException(UiText.Get("The expected dead-player update method was not found."));
                    hook = new ILHook(target, Patch);
                    MiDiagnostics.Debug("RevivifyCompatibility", "已安装复活模组房间扫描保护；module=" + target.Module.ModuleVersionId);
                    return true;
                }
                catch (Exception error)
                {
                    AppDomain.CurrentDomain.SetData(LeaseKey, null);
                    MiDiagnostics.Report("MI-REVIVIFY-VERSION", TargetName, error,
                        UiText.Get("The Revivify Meadow version or method structure did not match. The room-scan guard was not enabled."));
                    return false;
                }
            }
        }

        public static void Dispose()
        {
            lock (AppDomain.CurrentDomain)
            {
                if (hook != null)
                {
                    hook.Dispose();
                    hook = null;
                }
                if (ReferenceEquals(AppDomain.CurrentDomain.GetData(LeaseKey), owner))
                    AppDomain.CurrentDomain.SetData(LeaseKey, null);
                nextWarning = DateTime.MinValue;
            }
        }

        internal static bool CanScan(Player player)
        {
            // Do not catch exceptions from properties: a different broken hook
            // must retain its original stack and must not be silently hidden.
            Room room = player.room;
            AbstractRoom abstractRoom = room == null ? null : room.abstractRoom;
            if (abstractRoom != null && abstractRoom.entities != null) return true;
            DateTime now = DateTime.UtcNow;
            if (now >= nextWarning)
            {
                nextWarning = now.AddSeconds(30);
                string missing = room == null ? "room" : abstractRoom == null ? "abstractRoom" : "entities";
                MiDiagnostics.Warn("MI-REVIVIFY-ROOM", TargetName,
                    UiText.Get("The dead player's room data is incomplete. This revival scan was skipped."), UiText.Format("Missing: {0}", missing));
            }
            return false;
        }

        internal static void Patch(ILContext il)
        {
            var instructions = il.Body.Instructions;
            // Verify that the original update is still the first operation and
            // occurs exactly once. Refuse unknown implementations before editing.
            if (instructions.Count < 20 || instructions[0].OpCode != OpCodes.Ldarg_1 ||
                instructions[1].OpCode != OpCodes.Ldarg_2 || instructions[2].OpCode != OpCodes.Ldarg_3 ||
                !Method(instructions[3], OpCodes.Callvirt, "On.Player/orig_Update", "Invoke"))
                throw new InvalidOperationException(UiText.Get("Revivify Meadow's original player-update entry point has changed."));
            int originalCalls = 0, match = -1;
            for (int i = 0; i < instructions.Count; i++)
            {
                if (Method(instructions[i], OpCodes.Callvirt, "On.Player/orig_Update", "Invoke")) originalCalls++;
                if (i < 3 || i + 10 >= instructions.Count) continue;
                if (instructions[i - 3].OpCode != OpCodes.Ldarg_2 ||
                    !Method(instructions[i - 2], OpCodes.Callvirt, "Creature", "get_dead") ||
                    !Branch(instructions[i - 1], OpCodes.Brfalse, OpCodes.Brfalse_S) ||
                    instructions[i].OpCode != OpCodes.Ldarg_2 ||
                    !Field(instructions[i + 1], "UpdatableAndDeletable", "room") ||
                    instructions[i + 2].OpCode != OpCodes.Dup ||
                    !Branch(instructions[i + 3], OpCodes.Brtrue, OpCodes.Brtrue_S) ||
                    instructions[i + 3].Operand != instructions[i + 7] ||
                    instructions[i + 4].OpCode != OpCodes.Pop || instructions[i + 5].OpCode != OpCodes.Ldnull ||
                    !Branch(instructions[i + 6], OpCodes.Br, OpCodes.Br_S) ||
                    instructions[i + 6].Operand != instructions[i + 9] ||
                    !Method(instructions[i + 7], OpCodes.Call, "Room", "get_abstractRoom") ||
                    !Field(instructions[i + 8], "AbstractRoom", "entities") ||
                    !Method(instructions[i + 9], OpCodes.Callvirt, "System.Collections.Generic.List`1<AbstractWorldEntity>", "GetEnumerator")) continue;
                Instruction aliveExit = instructions[i - 1].Operand as Instruction;
                if (aliveExit == null || aliveExit.OpCode != OpCodes.Ret || match != -1)
                    throw new InvalidOperationException(UiText.Get("Revivify Meadow's death check or scan entry point is not unique."));
                match = i;
            }
            if (originalCalls != 1 || match < 0)
                throw new InvalidOperationException(UiText.Get("The expected dead-player room-scan instructions were not found. Revivify Meadow was left unchanged."));
            Instruction scanStart = instructions[match];
            var cursor = new ILCursor(il);
            cursor.Index = match;
            cursor.Emit(OpCodes.Ldarg_2);
            cursor.EmitDelegate<Func<Player, bool>>(CanScan);
            cursor.Emit(OpCodes.Brtrue, scanStart);
            cursor.Emit(OpCodes.Ret);
        }

        static bool Method(Instruction instruction, OpCode opcode, string type, string name)
        {
            MethodReference method = instruction.Operand as MethodReference;
            return instruction.OpCode == opcode && method != null && method.DeclaringType.FullName == type && method.Name == name;
        }

        static bool Field(Instruction instruction, string type, string name)
        {
            FieldReference field = instruction.Operand as FieldReference;
            return instruction.OpCode == OpCodes.Ldfld && field != null && field.DeclaringType.FullName == type && field.Name == name;
        }

        static bool Branch(Instruction instruction, OpCode longForm, OpCode shortForm)
        {
            return instruction.OpCode == longForm || instruction.OpCode == shortForm;
        }
    }
}
