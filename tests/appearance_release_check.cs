public static class ReleaseCheck
{
    static void Require(bool condition, string message) { if (!condition) throw new Exception(message); }
    static string Png(byte value) { return "data:image/png;base64," + Convert.ToBase64String(new byte[] { value, 7, 8, 9 }); }
    static void Owns(FAtlasElement element)
    {
        Require(!element.texture.destroyed, "Unrelated runtime texture was destroyed");
        Require(Object.ReferenceEquals(element, Futile.atlasManager.GetElementWithName(element.name)), "Unrelated runtime atlas was removed");
    }
    static int Main()
    {
        try
        {
            var core = MoreIterators.CreatorAppearance.Texture(Png(1), "same-gown");
            var first = __FIRST__.CreatorAppearance.Texture(Png(2), "same-gown");
            var second = __SECOND__.CreatorAppearance.Texture(Png(3), "same-gown");
            MoreIterators.CreatorAppearance.ReleaseTextures();
            Require(core.texture.destroyed && Futile.atlasManager.Count == 2, "Core cache was not released");
            MoreIterators.CreatorAppearance.ReleaseTextures();
            Owns(first); Owns(second);
            var reloaded = MoreIterators.CreatorAppearance.Texture(Png(1), "same-gown");
            Require(!Object.ReferenceEquals(core, reloaded) && !reloaded.texture.destroyed, "Reload reused a disposed atlas");
            var extra = MoreIterators.CreatorAppearance.Texture(Png(4), "extra-gown");
            Futile.atlasManager.failUnload = reloaded.name;
            int reports = MiDiagnostics.reports;
            MoreIterators.CreatorAppearance.ReleaseTextures();
            Require(MiDiagnostics.reports == reports + 1, "Release failure was not reported");
            Require(!reloaded.texture.destroyed && extra.texture.destroyed, "Failure stopped later cleanup or lost retry state");
            Owns(first); Owns(second);
            Futile.atlasManager.failUnload = null;
            MoreIterators.CreatorAppearance.ReleaseTextures();
            Require(reloaded.texture.destroyed && Futile.atlasManager.Count == 2, "Failed atlas was not retried");
            var manager = Futile.atlasManager;
            Futile.atlasManager = null;
            __FIRST__.CreatorAppearance.ReleaseTextures();
            Futile.atlasManager = manager;
            Owns(first);
            __FIRST__.CreatorAppearance.ReleaseTextures();
            Require(first.texture.destroyed && Futile.atlasManager.Count == 1, "Export cleanup did not use its own cache");
            Owns(second);
            __SECOND__.CreatorAppearance.ReleaseTextures();
            __SECOND__.CreatorAppearance.ReleaseTextures();
            Require(second.texture.destroyed && Futile.atlasManager.Count == 0, "Final export cleanup was not idempotent");
            Console.WriteLine("PASS: owned cache cleanup, retry, null manager and reload"); return 0;
        }
        catch (Exception error) { Console.Error.WriteLine(error.Message); return 1; }
    }
}
