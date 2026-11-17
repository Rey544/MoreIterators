using System;

public struct Color
{
    public float r, g, b, a;
    public Color(float r, float g, float b, float a) { this.r = r; this.g = g; this.b = b; this.a = a; }
    public static Color white { get { return new Color(1, 1, 1, 1); } }
}
public struct Vector2
{
    public float x, y;
    public Vector2(float x, float y) { this.x = x; this.y = y; }
    public static Vector2 operator +(Vector2 a, Vector2 b) { return new Vector2(a.x + b.x, a.y + b.y); }
    public static Vector2 operator -(Vector2 a, Vector2 b) { return new Vector2(a.x - b.x, a.y - b.y); }
    public static Vector2 operator *(Vector2 a, float b) { return new Vector2(a.x * b, a.y * b); }
}
public static class Mathf
{
    public static float Sqrt(float x) { return (float)Math.Sqrt(x); }
    public static float Clamp(float x, float min, float max) { return Math.Min(max, Math.Max(min, x)); }
}
public class FAtlasElement { public string name; }
public class FContainer
{
    public int added;
    public void AddChild(FSprite sprite) { added++; sprite.container = this; }
}
public class FSprite
{
    public FContainer container;
    public FAtlasElement element = new FAtlasElement();
    public object shader;
    public Color color;
    public float alpha;
    public bool removed;
    public void RemoveFromContainer() { removed = true; container = null; }
}
public class TriangleMesh : FSprite
{
    public Vector2[] vertices, UVvertices;
    public Color[] verticeColors;
    public int[] triangles;
    public TriangleMesh(string name, int[] triangles, bool customColors)
    {
        this.triangles = triangles;
        element.name = name;
        vertices = new Vector2[triangles[0]];
        UVvertices = new Vector2[vertices.Length];
        if (customColors) verticeColors = new Color[vertices.Length];
    }
    public void MoveVertice(int index, Vector2 point) { vertices[index] = point; }
}
public class RoomCamera { public class SpriteLeaser { public FSprite[] sprites; } }
public class IteratorDesign { public string hemProfile = "1,1,1,1,1,1,1,1,1,1,1"; }

public static class AppearanceCheck
{
    __COPY_MESH__
    static void Hem(TriangleMesh gown, IteratorDesign d)
    {
        if (gown != null)
        {
            __HEM_BODY__
    }
    static void Require(bool value, string message) { if (!value) throw new Exception(message); }
    static TriangleMesh Mesh(bool colors)
    {
        var mesh = new TriangleMesh("sample", new[] { 4 }, colors);
        mesh.shader = new object(); mesh.color = new Color(.1f, .2f, .3f, .4f); mesh.alpha = .6f;
        for (int i = 0; i < 4; i++)
        {
            mesh.vertices[i] = new Vector2(i / 2, i % 2);
            mesh.UVvertices[i] = new Vector2(i * .2f, i * .1f);
            if (colors) mesh.verticeColors[i] = new Color(.2f * i, .1f, .5f, .25f * i);
        }
        return mesh;
    }
    static void Copy(string mode)
    {
        var source = Mesh(mode != "white");
        var previous = Mesh(mode != "null-colors");
        if (mode == "short-colors") previous.verticeColors = new Color[1];
        if (mode == "different-size") previous = new TriangleMesh("other", new[] { 6 }, true);
        var container = new FContainer(); previous.container = container;
        var leaser = new RoomCamera.SpriteLeaser { sprites = new FSprite[] { previous } };
        var result = CopyMesh(leaser, 0, source);
        bool recreate = mode == "null-colors" || mode == "short-colors" || mode == "different-size";
        Require(Object.ReferenceEquals(result, previous) != recreate, "Wrong mesh reuse decision");
        Require(container.added == (recreate ? 1 : 0) && previous.removed == recreate, "Wrong container ownership");
        Require(Object.ReferenceEquals(leaser.sprites[0], result), "Leaser did not retain replacement");
        Require(result.vertices.Length == 4 && result.verticeColors.Length == 4, "Invalid destination arrays");
        Require(Object.ReferenceEquals(result.element, source.element) && Object.ReferenceEquals(result.shader, source.shader), "Material changed");
        Require(result.alpha == .6f && result.color.a == .4f, "Sprite alpha changed");
        for (int i = 0; i < 4; i++)
        {
            Require(result.UVvertices[i].x == source.UVvertices[i].x && result.UVvertices[i].y == source.UVvertices[i].y, "UV changed");
            Color expected = source.verticeColors == null ? Color.white : source.verticeColors[i];
            Color actual = result.verticeColors[i];
            Require(actual.r == expected.r && actual.g == expected.g && actual.b == expected.b && actual.a == expected.a, "Vertex color changed");
        }
    }
    static void Profiles()
    {
        foreach (string profile in new string[] { null, "", "1,1,1,1,1,1,1,1,1,1,1", "bad,1", "0,2" })
        {
            var gown = Mesh(true);
            var design = new IteratorDesign { hemProfile = profile };
            Hem(gown, design);
            Require(design.hemProfile == profile, "Author profile was rewritten");
            for (int i = 0; i < 4; i++)
            {
                float expected = i % 2;
                if (profile == "0,2" && i % 2 == 1) expected = i < 2 ? .6f : 1.4f;
                Require(Math.Abs(gown.vertices[i].y - expected) < .00001f, "Hem shape changed");
                Require(gown.vertices[i].x == i / 2, "Hem horizontal position changed");
            }
        }
        Hem(null, new IteratorDesign());
    }
    public static int Main(string[] args)
    {
        try
        {
            if (args[0] == "hem") Profiles(); else Copy(args[0]);
            Console.WriteLine("PASS: " + args[0]); return 0;
        }
        catch (Exception error) { Console.Error.WriteLine(error.GetType().Name + ": " + error.Message); return 1; }
    }
}
