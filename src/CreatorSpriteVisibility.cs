using UnityEngine;

namespace MoreIterators
{
    public static class CreatorSpriteVisibility
    {
        public static bool HideIfCulled(bool culled, FSprite[] sprites)
        {
            if (!culled) return false;
            // The native renderer uses sprite 0 as its culling sentinel. Custom
            // layer visibility must not reopen any sprite while it is culled.
            foreach (FSprite sprite in sprites)
                if (sprite != null) sprite.isVisible = false;
            return true;
        }

        public static void ApplyBody(FSprite[] sprites, int first, int count, bool enabled, Color color)
        {
            for (int i = 0; i < count; i++)
            {
                FSprite body = sprites[first + i];
                body.color = color;
                body.isVisible = enabled;
            }
        }
    }
}
