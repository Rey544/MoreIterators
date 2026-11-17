using System;
using System.Globalization;
using System.Runtime.CompilerServices;
using System.Text;
using UnityEngine;

namespace MoreIterators
{
    // Read-only snapshots. Coordinates never form the change key: ordinary motion
    // must not produce per-frame logs or recurring diagnostic dialogs.
    public static class OracleSpriteDiagnostics
    {
        public static void OpenReport(string oracleId)
        {
            OracleRenderReport.Open(oracleId);
        }

        [Flags]
        enum Problem
        {
            None = 0,
            MissingSprite = 1,
            NonFinite = 2,
            MissingContainer = 4,
            Hidden = 8,
            Transparent = 16,
            ZeroScale = 32
        }

        struct RenderSample
        {
            public Problem problem;
            public float alpha,
                colorAlpha,
                parentAlpha,
                vertexMin,
                vertexMax;
            public int vertexColors;
            public bool customColor;
            public string shader;

            public bool Same(RenderSample other)
            {
                return problem == other.problem
                    && alpha.Equals(other.alpha)
                    && colorAlpha.Equals(other.colorAlpha)
                    && parentAlpha.Equals(other.parentAlpha)
                    && vertexMin.Equals(other.vertexMin)
                    && vertexMax.Equals(other.vertexMax)
                    && vertexColors == other.vertexColors
                    && customColor == other.customColor
                    && shader == other.shader;
            }
        }

        sealed class State
        {
            public State()
            {
            }

            public string projectId,
                oracleId;
            public RenderSample body0,
                body1,
                gown,
                leftSleeve,
                rightSleeve;
            public bool sampled,
                reportedFailure;
            public DateTime nextWrite;
            public FSprite[] sprites;
        }

        static readonly ConditionalWeakTable<OracleGraphics, State> states =
            new ConditionalWeakTable<OracleGraphics, State>();

        public static void Observe(
            OracleGraphics graphics,
            RoomCamera.SpriteLeaser leaser,
            int extraStart,
            IteratorDesign design
        )
        {
            try
            {
                ObserveAt(graphics, leaser, extraStart, design, DateTime.UtcNow);
            }
            catch (Exception error)
            {
                // Diagnostic observation cannot interrupt the character renderer.
                if (graphics == null)
                    return;
                State state = states.GetOrCreateValue(graphics);
                if (state.reportedFailure)
                    return;
                state.reportedFailure = true;
                MiDiagnostics.Debug(
                    "OracleSpriteDiagnostics",
                    "observation-failed project="
                        + Clean(design == null ? null : design.projectId)
                        + " oracle="
                        + Clean(design == null ? null : design.oracleId)
                        + " error="
                        + error
                );
            }
        }

        internal static void ObserveAt(
            OracleGraphics graphics,
            RoomCamera.SpriteLeaser leaser,
            int extraStart,
            IteratorDesign design,
            DateTime now
        )
        {
            if (graphics == null || leaser == null || design == null)
                return;
            FSprite a = At(leaser, graphics.firstBodyChunkSprite),
                b = At(leaser, graphics.firstBodyChunkSprite + 1);
            RenderSample first = Sample(a),
                second = Sample(b),
                gown = Sample(At(leaser, graphics.robeSprite)),
                leftSleeve = Sample(At(leaser, graphics.HandSprite(0, 1))),
                rightSleeve = Sample(At(leaser, graphics.HandSprite(1, 1)));
            State state = states.GetOrCreateValue(graphics);
            bool changedProject = state.projectId != design.projectId || state.oracleId != design.oracleId;
            bool fresh = !state.sampled || changedProject || state.sprites != leaser.sprites;
            if (
                !fresh
                && (
                    first.Same(state.body0)
                        && second.Same(state.body1)
                        && gown.Same(state.gown)
                        && leftSleeve.Same(state.leftSleeve)
                        && rightSleeve.Same(state.rightSleeve)
                    || now < state.nextWrite
                )
            )
                return;
            state.nextWrite = now.AddSeconds(2);
            state.projectId = design.projectId;
            state.oracleId = design.oracleId;
            state.sprites = leaser.sprites;
            state.body0 = first;
            state.body1 = second;
            state.gown = gown;
            state.leftSleeve = leftSleeve;
            state.rightSleeve = rightSleeve;
            state.sampled = true;
            string identity = "project=" + Clean(design.projectId) + " oracle=" + Clean(design.oracleId);
            string room = MiDiagnostics.Context(graphics.oracle == null ? null : graphics.oracle.room);
            string status = "body0=" + first.problem + " body1=" + second.problem + " culled=" + graphics.culled;
            var sample = new StringBuilder(
                identity
                    + " "
                    + room
                    + " "
                    + status
                    + " robeEnabled="
                    + (design.layers == null ? "<missing>" : design.layers.robe.ToString())
            );
            Describe(sample, "body0", a);
            Describe(sample, "body1", b);
            Describe(sample, "gown", At(leaser, graphics.robeSprite));
            Describe(sample, "sleeveL", At(leaser, graphics.HandSprite(0, 1)));
            Describe(sample, "sleeveR", At(leaser, graphics.HandSprite(1, 1)));
            int front = CreatorWardrobe.Start(extraStart);
            Bounds(sample, "frontL", leaser, front, 1);
            Bounds(sample, "frontR", leaser, front + 6, 1);
            Bounds(sample, "back", leaser, extraStart + 40, 26);
            MiDiagnostics.Debug("OracleSpriteDiagnostics", sample.ToString());
        }

        static FSprite At(RoomCamera.SpriteLeaser leaser, int index)
        {
            return leaser.sprites != null && index >= 0 && index < leaser.sprites.Length ? leaser.sprites[index] : null;
        }

        static bool Finite(float value)
        {
            return !Single.IsNaN(value) && !Single.IsInfinity(value);
        }

        static float Bucket(float value)
        {
            return Finite(value) ? (float)Math.Round(value, 3) : value;
        }

        static RenderSample Sample(FSprite sprite)
        {
            var result = new RenderSample { problem = Classify(sprite) };
            if (sprite == null)
                return result;
            result.alpha = Bucket(sprite.alpha);
            result.colorAlpha = Bucket(sprite.color.a);
            result.parentAlpha = Bucket(ParentAlpha(sprite));
            result.shader = ShaderName(sprite);
            var mesh = sprite as TriangleMesh;
            result.customColor = mesh != null && mesh.customColor;
            float min,
                max;
            result.vertexColors = VertexRange(mesh, out min, out max);
            result.vertexMin = Bucket(min);
            result.vertexMax = Bucket(max);
            return result;
        }

        internal static float ParentAlpha(FSprite sprite)
        {
            return sprite == null || sprite.container == null ? 1 : sprite.container.concatenatedAlpha;
        }

        internal static string ShaderName(FSprite sprite)
        {
            return sprite == null || sprite.shader == null ? "<none>" : Clean(sprite.shader.name);
        }

        static int VertexRange(TriangleMesh mesh, out float min, out float max)
        {
            min = max = 0;
            if (mesh == null || mesh.verticeColors == null || mesh.verticeColors.Length == 0)
                return 0;
            min = Single.PositiveInfinity;
            max = Single.NegativeInfinity;
            foreach (Color color in mesh.verticeColors)
            {
                min = Math.Min(min, color.a);
                max = Math.Max(max, color.a);
            }
            return mesh.verticeColors.Length;
        }

        internal static string VertexAlpha(TriangleMesh mesh)
        {
            float min,
                max;
            int count = VertexRange(mesh, out min, out max);
            return count == 0
                ? "-"
                : Number(min) + ".." + Number(max) + (mesh.customColor ? "" : " [" + UiText.Get("Not enabled") + "]");
        }

        static Problem Classify(FSprite sprite)
        {
            if (sprite == null)
                return Problem.MissingSprite;
            Problem result = Problem.None;
            if (
                !Finite(sprite.x)
                || !Finite(sprite.y)
                || !Finite(sprite.scaleX)
                || !Finite(sprite.scaleY)
                || !Finite(sprite.rotation)
                || !Finite(sprite.alpha)
            )
                result |= Problem.NonFinite;
            if (sprite.container == null)
                result |= Problem.MissingContainer;
            if (!sprite.isVisible)
                result |= Problem.Hidden;
            if (sprite.alpha <= .0001f)
                result |= Problem.Transparent;
            if (Math.Abs(sprite.scaleX) <= .0001f || Math.Abs(sprite.scaleY) <= .0001f)
                result |= Problem.ZeroScale;
            return result;
        }

        static string Number(float value)
        {
            return value.ToString("0.####", CultureInfo.InvariantCulture);
        }

        static string Clean(string value)
        {
            return (value ?? "<none>").Replace('\r', ' ').Replace('\n', ' ');
        }

        static void Describe(StringBuilder output, string name, FSprite sprite)
        {
            output.Append("; ").Append(name).Append("{");
            if (sprite == null)
            {
                output.Append("missing}");
                return;
            }
            output
                .Append("visible=")
                .Append(sprite.isVisible)
                .Append(" alpha=")
                .Append(Number(sprite.alpha))
                .Append(" colorAlpha=")
                .Append(Number(sprite.color.a))
                .Append(" parentAlpha=")
                .Append(Number(ParentAlpha(sprite)))
                .Append(" shader=")
                .Append(ShaderName(sprite))
                .Append(" vertexAlpha=")
                .Append(VertexAlpha(sprite as TriangleMesh))
                .Append(" scale=")
                .Append(Number(sprite.scaleX))
                .Append(',')
                .Append(Number(sprite.scaleY))
                .Append(" xy=")
                .Append(Number(sprite.x))
                .Append(',')
                .Append(Number(sprite.y))
                .Append(" rotation=")
                .Append(Number(sprite.rotation))
                .Append(" element=")
                .Append(sprite.element == null ? "<none>" : Clean(sprite.element.name))
                .Append(" container=")
                .Append(
                    sprite.container == null
                        ? "<none>"
                        : sprite.container.GetType().Name
                            + "#"
                            + RuntimeHelpers.GetHashCode(sprite.container).ToString("x")
                )
                .Append(" depth=")
                .Append(sprite.depth)
                .Append('}');
        }

        static void Bounds(StringBuilder output, string name, RoomCamera.SpriteLeaser leaser, int start, int count)
        {
            int visible = 0,
                points = 0,
                invalid = 0;
            float minX = Single.PositiveInfinity,
                minY = minX,
                maxX = Single.NegativeInfinity,
                maxY = maxX;
            for (int i = 0; i < count; i++)
            {
                var sprite = At(leaser, start + i);
                if (sprite == null || !sprite.isVisible)
                    continue;
                visible++;
                var mesh = sprite as TriangleMesh;
                if (mesh == null || mesh.vertices == null)
                    continue;
                foreach (Vector2 p in mesh.vertices)
                {
                    if (!Finite(p.x) || !Finite(p.y))
                    {
                        invalid++;
                        continue;
                    }
                    points++;
                    minX = Math.Min(minX, p.x);
                    minY = Math.Min(minY, p.y);
                    maxX = Math.Max(maxX, p.x);
                    maxY = Math.Max(maxY, p.y);
                }
            }
            output.Append("; ").Append(name).Append("{visible=").Append(visible).Append(" bounds=");
            if (points == 0)
                output.Append("<none>");
            else
                output
                    .Append(Number(minX))
                    .Append(',')
                    .Append(Number(minY))
                    .Append("..")
                    .Append(Number(maxX))
                    .Append(',')
                    .Append(Number(maxY));
            output.Append(" invalidVertices=").Append(invalid).Append('}');
        }
    }
}
