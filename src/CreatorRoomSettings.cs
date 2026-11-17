using System.Collections.Generic;
using System.Runtime.CompilerServices;
using UnityEngine;

namespace MoreIterators
{
    public static class CreatorRoomSettings
    {
        sealed class GravityState
        {
            public float original;
            public bool restored;
            public bool preview;
            public float beforePreview;
            public readonly Dictionary<AntiGravity, bool> effects = new Dictionary<AntiGravity, bool>();
        }

        sealed class CameraState
        {
            public Room room;
            public bool native;
            public int revision = -1;
        }

        static readonly ConditionalWeakTable<Room, GravityState> gravity =
            new ConditionalWeakTable<Room, GravityState>();
        static readonly ConditionalWeakTable<RoomCamera, CameraState> cameras =
            new ConditionalWeakTable<RoomCamera, CameraState>();

        public static bool RoomPalette(IteratorDesign design)
        {
            return design != null && design.roomPaletteMode == "room";
        }

        public static bool RoomGravity(IteratorDesign design)
        {
            return design != null && design.roomGravityMode == "room";
        }

        public static bool EntryGravity(IteratorDesign design)
        {
            return design != null && design.entryGravityMode == "room";
        }

        public static void CaptureGravity(Room room)
        {
            gravity.GetValue(
                room,
                delegate (Room owner)
                {
                    var state = new GravityState { original = owner.gravity };
                    foreach (var item in owner.updateList)
                    {
                        var effect = item as AntiGravity;
                        if (effect != null)
                            state.effects[effect] = effect.active;
                    }
                    return state;
                }
            );
        }

        public static void PrepareGravity(Room room, bool useRoom)
        {
            CaptureGravity(room);
            var state = gravity.GetOrCreateValue(room);
            if (!useRoom)
            {
                if (state.restored && IteratorCatalog.IsAI(room.abstractRoom.name))
                    foreach (var item in room.updateList)
                    {
                        var effect = item as AntiGravity;
                        if (effect != null)
                            effect.active = false;
                    }
                state.restored = false;
                return;
            }
            if (state.restored)
                return;

            foreach (var item in room.updateList)
            {
                var effect = item as AntiGravity;
                if (effect != null)
                {
                    bool active;
                    effect.active = state.effects.TryGetValue(effect, out active) ? active : true;
                }
            }
            room.gravity = state.original;
            state.restored = true;
        }

        public static void WaitingGravity(Room room)
        {
            bool useRoom = EntryGravity(IteratorDesign.ForRoom(room));
            PrepareGravity(room, useRoom);
            if (!useRoom)
                room.gravity = 0;
        }

        public static void PreviewGravity(Room room, float amount)
        {
            CaptureGravity(room);
            var state = gravity.GetOrCreateValue(room);
            if (amount >= 0)
            {
                if (!state.preview)
                    state.beforePreview = room.gravity;
                state.preview = true;
                room.gravity = amount;
                return;
            }
            if (!state.preview)
                return;
            state.preview = false;
            if (!RoomGravity(IteratorDesign.ForRoom(room)))
                return;
            foreach (var item in room.updateList)
            {
                var effect = item as AntiGravity;
                if (effect != null && effect.active)
                    return;
            }
            room.gravity = state.beforePreview;
        }

        public static void Palette(RoomCamera cam, IteratorDesign design, float blend)
        {
            if (cam == null || cam.room == null)
                return;
            var state = cameras.GetOrCreateValue(cam);
            bool native = RoomPalette(design);
            bool reload = state.room != cam.room || state.native != native || state.revision != IteratorDesign.Revision;
            state.room = cam.room;
            state.native = native;
            state.revision = IteratorDesign.Revision;
            if (native)
            {
                if (!reload)
                    return;
                cam.paletteA = -1;
                cam.paletteB = -1;
                var settings = cam.room.roomSettings;
                if (settings.fadePalette == null)
                {
                    cam.paletteBlend = 0;
                    cam.ChangeMainPalette(settings.Palette);
                }
                else
                {
                    var fade = settings.fadePalette;
                    int index = cam.currentCameraPosition;
                    float amount = index >= 0 && index < fade.fades.Length ? fade.fades[index] : 0;
                    cam.ChangeBothPalettes(settings.Palette, fade.palette, amount);
                }
                return;
            }

            if (!reload && cam.paletteA == 25 && cam.paletteB == 26 && cam.paletteBlend == blend)
                return;
            if (reload)
            {
                cam.paletteA = -1;
                cam.paletteB = -1;
            }
            cam.ChangeBothPalettes(25, 26, blend);
        }
    }
}
