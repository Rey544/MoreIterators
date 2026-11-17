using System;
using System.Collections.Generic;
using System.Runtime.CompilerServices;
using UnityEngine;

namespace MoreIterators
{
    public sealed class CreatorChamberArea
    {
        const float Clearance = 18f;
        readonly int width,
            height;
        readonly Func<int, int, int> terrain;
        readonly bool[] reachable;
        public readonly Vector2 minimum,
            maximum;
        public readonly bool valid;

        public CreatorChamberArea(int width, int height, Func<int, int, int> terrain, Vector2 preferred)
        {
            this.width = width;
            this.height = height;
            this.terrain = terrain;
            reachable = new bool[width * height];
            var clear = new bool[width * height];
            int start = -1;
            float best = float.MaxValue;
            for (int y = 0; y < height; y++)
                for (int x = 0; x < width; x++)
                {
                    Vector2 point = new Vector2(x * 20 + 10, y * 20 + 10);
                    int index = y * width + x;
                    if (!Clear(point))
                        continue;
                    clear[index] = true;
                    float distance = (point - preferred).sqrMagnitude;
                    if (distance < best)
                    {
                        best = distance;
                        start = index;
                    }
                }
            if (start < 0)
            {
                minimum = maximum = preferred;
                return;
            }
            var queue = new Queue<int>();
            queue.Enqueue(start);
            reachable[start] = true;
            while (queue.Count > 0)
            {
                int index = queue.Dequeue(),
                    x = index % width,
                    y = index / width;
                for (int side = 0; side < 4; side++)
                {
                    int nx =
                            x
                            + (
                                side == 0 ? -1
                                : side == 1 ? 1
                                : 0
                            ),
                        ny =
                            y
                            + (
                                side == 2 ? -1
                                : side == 3 ? 1
                                : 0
                            );
                    if (nx < 0 || ny < 0 || nx >= width || ny >= height)
                        continue;
                    int next = ny * width + nx;
                    if (!clear[next] || reachable[next])
                        continue;
                    reachable[next] = true;
                    queue.Enqueue(next);
                }
            }
            var heights = new int[width];
            var stack = new int[width + 1];
            int area = 0,
                left = 0,
                right = 0,
                bottom = 0,
                top = 0;
            float tie = float.MaxValue;
            for (int y = 0; y < height; y++)
            {
                for (int x = 0; x < width; x++)
                    heights[x] = reachable[y * width + x] ? heights[x] + 1 : 0;
                int count = 0;
                for (int x = 0; x <= width; x++)
                {
                    int current = x == width ? 0 : heights[x];
                    while (count > 0 && heights[stack[count - 1]] > current)
                    {
                        int column = stack[--count],
                            h = heights[column],
                            l = count == 0 ? 0 : stack[count - 1] + 1,
                            w = x - l,
                            a = w * h;
                        if (w < 3 || h < 3)
                            continue;
                        var center = new Vector2((l + x) * 10, (2 * y - h + 2) * 10);
                        float distance = (center - preferred).sqrMagnitude;
                        if (a > area || a == area && distance < tie)
                        {
                            area = a;
                            tie = distance;
                            left = l;
                            right = x - 1;
                            bottom = y - h + 1;
                            top = y;
                        }
                    }
                    stack[count++] = x;
                }
            }
            valid = area > 0;
            minimum = valid ? new Vector2(left * 20 + 10, bottom * 20 + 10) : preferred;
            maximum = valid ? new Vector2(right * 20 + 10, top * 20 + 10) : preferred;
        }

        bool Open(int x, int y)
        {
            return x >= 0 && y >= 0 && x < width && y < height && terrain(x, y) == 0;
        }

        public bool Clear(Vector2 point)
        {
            for (int x = -1; x <= 1; x++)
                for (int y = -1; y <= 1; y++)
                    if (
                        !Open(
                            (int)Math.Floor((point.x + x * Clearance) / 20),
                            (int)Math.Floor((point.y + y * Clearance) / 20)
                        )
                    )
                        return false;
            return true;
        }

        public Vector2 Clamp(Vector2 point)
        {
            return new Vector2(Mathf.Clamp(point.x, minimum.x, maximum.x), Mathf.Clamp(point.y, minimum.y, maximum.y));
        }

        public Vector2 Center
        {
            get
            {
                return (minimum + maximum) * .5f;
            }
        }

        public bool Seat(Vector2 preferred, out Vector2 result)
        {
            return Seat(preferred, 30f, out result);
        }

        public bool Seat(Vector2 preferred, float clearance, out Vector2 result)
        {
            result = preferred;
            float best = float.MaxValue;
            bool found = false;
            for (int y = 1; y < height - 2; y++)
                for (int x = 1; x < width - 1; x++)
                {
                    int support = terrain(x, y - 1);
                    if (support != 1 && support != 3)
                        continue;
                    if (terrain(x - 1, y - 1) != support || terrain(x + 1, y - 1) != support)
                        continue;
                    var point = new Vector2(x * 20 + 10, y * 20 + clearance);
                    if (point.x < minimum.x || point.x > maximum.x || point.y < minimum.y - 20 || point.y > maximum.y)
                        continue;
                    if (!Clear(point))
                        continue;
                    int cell = (y + 1) * width + x;
                    if (cell < 0 || cell >= reachable.Length || !reachable[cell])
                        continue;
                    float dx = point.x - preferred.x,
                        dy = point.y - preferred.y,
                        score = dx * dx + dy * dy * .25f;
                    if (score >= best)
                        continue;
                    best = score;
                    result = point;
                    found = true;
                }
            return found;
        }

        public bool SupportBelow(Vector2 point, float clearance, out Vector2 result)
        {
            result = point;
            int left = (int)Math.Floor((point.x - 12) / 20),
                right = (int)Math.Floor((point.x + 12) / 20);
            if (left < 0 || right >= width)
                return false;
            for (int y = Math.Min(height - 2, (int)Math.Floor(point.y / 20)); y >= 0; y--)
            {
                bool supported = true;
                for (int x = left; x <= right; x++)
                {
                    int value = terrain(x, y);
                    if (value != 1 && value != 2 && value != 3)
                    {
                        supported = false;
                        break;
                    }
                }
                if (!supported)
                    continue;
                var target = new Vector2(point.x, (y + 1) * 20 + clearance);
                if (!Clear(target))
                    continue;
                result = target;
                return true;
            }
            return false;
        }
    }

    public static class CreatorChamberMotion
    {
        sealed class State
        {
            public Room room;
            public string preset;
            public float width,
                height;
            public CreatorChamberArea area;
            public bool active,
                seated,
                initialized,
                resting,
                moving;
            public Vector2 seat,
                spawn;
            public Oracle.OracleArm arm;
        }

        sealed class ArmBaseline
        {
            public Vector2[] corners;
            public float[] lengths;
            public float frame,
                lastFrame;
        }

        static ConditionalWeakTable<Oracle, State> states = new ConditionalWeakTable<Oracle, State>();
        static ConditionalWeakTable<Oracle.OracleArm, ArmBaseline> arms =
            new ConditionalWeakTable<Oracle.OracleArm, ArmBaseline>();
        static readonly List<WeakReference> tracked = new List<WeakReference>();
        static bool enabled;

        public static void Install(List<Action> remove)
        {
            if (enabled)
                return;
            enabled = true;
            remove.Add(Dispose);
        }

        public static void Dispose()
        {
            enabled = false;
            foreach (var reference in tracked)
            {
                var oracle = reference.Target as Oracle;
                State state;
                if (oracle != null && states.TryGetValue(oracle, out state))
                    Restore(state);
            }
            tracked.Clear();
            states = new ConditionalWeakTable<Oracle, State>();
            arms = new ConditionalWeakTable<Oracle.OracleArm, ArmBaseline>();
        }

        public static bool Template(string value)
        {
            return value == "mi-chamber-pebbles"
                || value == "mi-chamber-moon"
                || value == "mi-chamber-broken"
                || value == "mi-chamber-irregular"
                || value == "mi-chamber-multi-screen";
        }

        static int Terrain(Room room, int x, int y)
        {
            var tile = room.GetTile(new Vector2(x * 20 + 10, y * 20 + 10));
            return tile.Solid ? 1
                : tile.Terrain == Room.Tile.TerrainType.Floor ? 3
                : tile.Terrain == Room.Tile.TerrainType.Slope ? 2
                : tile.Terrain == Room.Tile.TerrainType.ShortcutEntrance ? 4
                : 0;
        }

        static State For(Oracle oracle)
        {
            if (
                !enabled
                || oracle == null
                || oracle.room == null
                || oracle.arm == null
                || !CreatorOracleLifecycle.Owns(oracle)
            )
                return null;
            string preset = IteratorDesign.ForRoom(oracle.room).chamberPreset;
            State state;
            if (
                states.TryGetValue(oracle, out state)
                && state.room == oracle.room
                && state.preset == preset
                && state.width == oracle.room.PixelWidth
                && state.height == oracle.room.PixelHeight
            )
                return state.active ? state : null;
            if (state != null)
                Restore(state);
            else
            {
                tracked.RemoveAll(
                    delegate (WeakReference reference)
                    {
                        return !reference.IsAlive;
                    }
                );
                tracked.Add(new WeakReference(oracle));
            }
            var room = oracle.room;
            bool seated = preset == "mi-chamber-broken" || preset == "mi-chamber-moon";
            state = new State
            {
                room = room,
                preset = preset,
                width = room.PixelWidth,
                height = room.PixelHeight,
                seated = seated,
                resting = seated
            };
            states.Remove(oracle);
            states.Add(oracle, state);
            if (!Template(preset) && room.PixelWidth == 960 && room.PixelHeight == 720)
                return null;
            Vector2 preferred =
                !Template(preset) ? oracle.firstChunk.pos
                : preset == "mi-chamber-moon" ? new Vector2(room.PixelWidth * .81f, room.PixelHeight * .27f)
                : new Vector2(room.PixelWidth * .5f, room.PixelHeight * .5f);
            var area = new CreatorChamberArea(
                Math.Max(1, (int)(room.PixelWidth / 20)),
                Math.Max(1, (int)(room.PixelHeight / 20)),
                delegate (int x, int y)
                {
                    return Terrain(room, x, y);
                },
                preferred
            );
            state.area = area;
            state.spawn = Template(preset) ? area.Center : area.Clamp(oracle.firstChunk.pos);
            if (seated)
            {
                if (preset != "mi-chamber-moon")
                    preferred = new Vector2(area.Center.x, area.minimum.y);
                if (!area.Seat(preferred, SeatHeight(oracle), out state.seat))
                    return null;
                state.spawn = state.seat;
            }
            if (!area.valid)
                return null;
            state.active = true;
            return state;
        }

        static ArmBaseline Baseline(Oracle.OracleArm arm)
        {
            return arms.GetValue(
                arm,
                delegate (Oracle.OracleArm value)
                {
                    var result = new ArmBaseline
                    {
                        corners = (Vector2[])value.cornerPositions.Clone(),
                        lengths = new float[value.joints.Length],
                        frame = value.framePos,
                        lastFrame = value.lastFramePos
                    };
                    for (int i = 0; i < value.joints.Length; i++)
                        result.lengths[i] = value.joints[i].totalLength;
                    return result;
                }
            );
        }

        static void Restore(State state)
        {
            if (state.arm == null)
                return;
            var saved = Baseline(state.arm);
            state.arm.cornerPositions = (Vector2[])saved.corners.Clone();
            for (int i = 0; i < state.arm.joints.Length; i++)
                state.arm.joints[i].totalLength = saved.lengths[i];
            state.arm.framePos = saved.frame;
            state.arm.lastFramePos = saved.lastFrame;
            state.arm.baseMoving = false;
        }

        static void Frame(Oracle oracle, State state)
        {
            if (state.arm == oracle.arm)
                return;
            Restore(state);
            state.arm = oracle.arm;
            var arm = oracle.arm;
            var saved = Baseline(arm);
            var min = state.area.minimum;
            var max = state.area.maximum;
            arm.cornerPositions = new[]
            {
                new Vector2(min.x, max.y),
                new Vector2(max.x, max.y),
                new Vector2(max.x, min.y),
                new Vector2(min.x, min.y)
            };
            float stretch = Math.Max(1, Math.Min(max.x - min.x, max.y - min.y) / 560f);
            for (int i = 0; i < arm.joints.Length; i++)
                arm.joints[i].totalLength = saved.lengths[i] * stretch;
            if (state.seated)
                arm.framePos = arm.lastFramePos = 10002.5f;
            for (int i = 0; i < arm.joints.Length; i++)
            {
                var joint = arm.joints[i];
                joint.pos = joint.lastPos = Vector2.Lerp(
                    arm.BasePos(1),
                    oracle.firstChunk.pos,
                    (float)i / Math.Max(1, arm.joints.Length - 1)
                );
                joint.vel = Vector2.zero;
            }
        }

        static float SeatHeight(Oracle oracle)
        {
            var d = IteratorDesign.ForRoom(oracle.room);
            return Math.Max(30, (11 + 14 * d.torsoLength + d.neckLength) * d.puppetScale - 9);
        }

        static Vector2 RestTarget(Oracle oracle, State state)
        {
            Vector2 target;
            return state.area.SupportBelow(oracle.firstChunk.pos, SeatHeight(oracle), out target)
                ? target
                : oracle.firstChunk.pos;
        }

        static void Position(Oracle oracle, Vector2 point)
        {
            for (int i = 0; i < oracle.bodyChunks.Length; i++)
            {
                oracle.bodyChunks[i].HardSetPosition(point - new Vector2(0, i * 9));
                oracle.bodyChunks[i].vel = Vector2.zero;
            }
        }

        public static void Prepare(Oracle oracle, bool initialSpawn = false)
        {
            State state = For(oracle);
            if (state == null)
                return;
            if (!state.initialized)
            {
                bool initial = CreatorOracleLifecycle.ConsumeInitialPlacement(oracle);
                if (initialSpawn || initial || !state.area.Clear(oracle.firstChunk.pos))
                    Position(oracle, state.spawn);
                state.initialized = true;
            }
            Frame(oracle, state);
        }

        public static void After(Oracle oracle)
        {
            State state = For(oracle);
            if (state == null)
                return;
            if (state.seated)
                return;
            Vector2 safe = state.area.Clamp(oracle.firstChunk.pos);
            if ((safe - oracle.firstChunk.pos).sqrMagnitude > .01f)
                Position(oracle, safe);
        }

        public static Vector2 Target(Oracle oracle, Vector2 native, bool rest = true)
        {
            State state = For(oracle);
            if (state == null)
                return native;
            state.resting = state.seated && rest && !state.moving;
            return state.resting ? RestTarget(oracle, state) : state.area.Clamp(native);
        }

        public static Vector2 MoveTarget(Oracle oracle, Vector2 target)
        {
            State state = For(oracle);
            if (state == null)
                return target;
            state.moving = true;
            state.resting = false;
            return state.area.Clamp(target);
        }

        public static Vector2 BaseTarget(Oracle oracle, Vector2 native)
        {
            State state = For(oracle);
            return state == null ? native
                : state.resting ? oracle.arm.BasePos(1)
                : state.area.Clamp(native);
        }

        public static Vector2 ArmPosition(Oracle.OracleArm arm, Vector2 native)
        {
            State state = For(arm.oracle);
            return state == null ? native : state.area.Clamp(native);
        }

        public static Vector2 Direction(Oracle oracle, Vector2 native)
        {
            State state = For(oracle);
            return state != null && state.resting ? Vector2.up : native;
        }

        public static Vector2 WorkTarget(Oracle oracle, int tick, Vector2 native)
        {
            State state = For(oracle);
            if (state == null)
                return native;
            state.moving = false;
            state.resting = state.seated;
            if (state.seated)
                return RestTarget(oracle, state);
            var size = state.area.maximum - state.area.minimum;
            return state.area.Center
                + new Vector2(Mathf.Sin(tick * .003f) * size.x * .38f, Mathf.Cos(tick * .005f) * size.y * .32f);
        }

        public static bool Seated(Oracle oracle)
        {
            State state = For(oracle);
            return state != null && state.seated;
        }

        public static void Graphics(OracleGraphics graphics)
        {
            State state = For(graphics.oracle);
            if (state == null || !state.resting || graphics.feet == null)
                return;
            var oracle = graphics.oracle;
            var chest = oracle.firstChunk;
            var hip = oracle.bodyChunks[oracle.bodyChunks.Length - 1];
            var d = IteratorDesign.ForRoom(oracle.room);
            Vector2 up = (chest.pos - hip.pos).normalized,
                lastUp = (chest.lastPos - hip.lastPos).normalized;
            if (up.sqrMagnitude < .01f)
                up = Vector2.up;
            if (lastUp.sqrMagnitude < .01f)
                lastUp = up;
            Vector2 right = new Vector2(up.y, -up.x),
                lastRight = new Vector2(lastUp.y, -lastUp.x);
            float drop = Math.Max(
                12,
                ((SeatHeight(oracle) + 6) / Math.Max(.1f, d.puppetScale) - 5 - d.neckLength)
                    / Math.Max(.1f, d.torsoLength)
                    - 5
            );
            for (int side = 0; side < graphics.feet.Length; side++)
            {
                float sign = side == 0 ? -1 : 1;
                var foot = graphics.feet[side];
                foot.pos = chest.pos + right * (sign * 12) - up * drop;
                foot.lastPos = chest.lastPos + lastRight * (sign * 12) - lastUp * drop;
                foot.vel = chest.vel;
                if (graphics.knees != null)
                {
                    graphics.knees[side, 0] = chest.pos + right * (sign * 10) - up * 7;
                    graphics.knees[side, 1] = chest.lastPos + lastRight * (sign * 10) - lastUp * 7;
                }
            }
        }
    }
}
