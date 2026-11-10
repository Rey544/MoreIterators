import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'editor'))
import room_bindings
import standalone
import storage


class ExportRoomVersionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.game = self.root / 'steamapps/common/Rain World'
        self.assets = self.game / 'RainWorld_Data/StreamingAssets'
        self.assets.mkdir(parents=True)
        (self.assets / 'GameVersion.txt').write_text('v1.11.8', encoding='utf-8')
        self.target = self.root / 'own-project'
        self.target.mkdir()
        self.roots = [self.assets, self.target]
        self.source = self.assets / 'world/su-rooms/SU_A01'
        for replacement in (
            patch.object(storage, 'GAME', self.game),
            patch.object(storage, 'target_mod', return_value=self.target),
            patch.object(room_bindings, '_asset_roots', side_effect=lambda: list(self.roots)),
            patch.object(room_bindings, 'resolve_room_source', side_effect=lambda room: self.source),
        ):
            replacement.start()
            self.addCleanup(replacement.stop)
        self.project = {'projectId': 'selected'}

    def mod(self, name):
        root = self.assets / 'mods' / name
        root.mkdir(parents=True)
        (root / 'modinfo.json').write_text(json.dumps({'id': name, 'name': name}), encoding='utf-8')
        self.roots.append(root)
        return root

    def version(self, root, version):
        result = root / version
        result.mkdir()
        self.roots.append(result)
        return result

    def palette(self, root, content):
        path = root / 'palettes/palette9100.png'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path.resolve()

    def test_dlc_current_version_is_official(self):
        owner = self.mod('moreslugcats')
        current = self.version(owner, 'v1.11.8')
        self.source = current / 'world/dm-rooms/DM_AI'
        self.assertEqual(standalone.official_room_requirement('DM_AI'), 'moreslugcats')

    def test_watcher_newest_is_official(self):
        owner = self.mod('watcher')
        self.source = self.version(owner, 'newest') / 'world/wa-rooms/WA_A01'
        self.assertEqual(standalone.official_room_requirement('WA_A01'), 'watcher')

    def test_same_named_third_party_room_is_not_official(self):
        self.mod('moreslugcats')
        self.source = self.version(self.mod('custom-map'), 'newest') / 'world/dm-rooms/DM_AI'
        with self.assertRaisesRegex(ValueError, '第三方内容'):
            standalone.official_room_requirement('DM_AI')

    def test_base_room_has_no_dlc_requirement(self):
        self.assertIsNone(standalone.official_room_requirement('SU_A01'))

    def test_versioned_room_falls_back_to_own_root_palette(self):
        owner = self.mod('map-one')
        self.source = self.version(owner, 'newest') / 'world/aa-rooms/AA_A01'
        expected = self.palette(owner, b'owner')
        self.palette(self.assets, b'base')
        self.palette(self.mod('unrelated'), b'unrelated')
        self.assertEqual(standalone.room_palette_source(self.project, self.source, 9100), expected)

    def test_current_version_then_newest_then_owner_palette(self):
        owner = self.mod('map-one')
        current = self.version(owner, 'v1.11.8')
        newest = self.version(owner, 'newest')
        self.source = owner / 'world/aa-rooms/AA_A01'
        base = self.palette(owner, b'owner')
        recent = self.palette(newest, b'newest')
        exact = self.palette(current, b'current')
        self.assertEqual(standalone.room_palette_source(self.project, self.source, 9100), exact)
        exact.unlink()
        self.assertEqual(standalone.room_palette_source(self.project, self.source, 9100), recent)
        recent.unlink()
        self.assertEqual(standalone.room_palette_source(self.project, self.source, 9100), base)

    def test_unknown_palette_never_uses_unrelated_mod(self):
        owner = self.mod('map-one')
        self.source = self.version(owner, 'newest') / 'world/aa-rooms/AA_A01'
        self.palette(self.mod('other'), b'unrelated')
        with self.assertRaisesRegex(ValueError, '来源无法确定'):
            standalone.room_palette_source(self.project, self.source, 9100)

    def test_project_render_uses_project_palette(self):
        expected = self.palette(self.target, b'own')
        self.assertEqual(standalone.room_palette_source(self.project, self.root / 'render/AA_AI', 9100), expected)

    def test_base_palette_fallback(self):
        owner = self.mod('map-one')
        self.source = self.version(owner, 'newest') / 'world/aa-rooms/AA_A01'
        expected = self.palette(self.assets, b'base')
        self.assertEqual(standalone.room_palette_source(self.project, self.source, 9100), expected)

    def test_copy_includes_only_explicit_palette_and_preserves_existing_conflict(self):
        owner = self.mod('map-one')
        self.source = self.version(owner, 'newest') / 'world/aa-rooms/AA_A01'
        palette = self.palette(owner, b'placeholder')
        Image.new('RGB', (32, 16), 'red').save(palette)
        unused = owner / 'palettes/palette9999.png'
        Image.new('RGB', (32, 16), 'green').save(unused)
        settings = self.root / 'room_settings.txt'
        settings.write_text('Palette: 9100\n', encoding='utf-8')
        stage = self.root / 'export'
        standalone.copy_room_palettes(self.project, self.source, settings, stage)
        output = stage / 'palettes/palette9100.png'
        original = output.read_bytes()
        self.assertEqual(original, palette.read_bytes())
        self.assertFalse((stage / 'palettes/palette9999.png').exists())
        Image.new('RGB', (32, 16), 'blue').save(palette)
        with self.assertRaisesRegex(ValueError, '同号但内容不同'):
            standalone.copy_room_palettes(self.project, self.source, settings, stage)
        self.assertEqual(output.read_bytes(), original)

    def test_palette_symlink_cannot_escape_owner(self):
        owner = self.mod('map-one')
        self.source = owner / 'world/aa-rooms/AA_A01'
        outside = self.palette(self.root / 'outside', b'outside')
        link = owner / 'palettes/palette9100.png'
        link.parent.mkdir()
        try:
            link.symlink_to(outside)
        except OSError:
            self.skipTest('This account cannot create symlinks')
        with self.assertRaisesRegex(ValueError, '路径越界'):
            standalone.room_palette_source(self.project, self.source, 9100)

    def test_unknown_old_dlc_version_is_not_auto_trusted(self):
        owner = self.mod('watcher')
        self.source = self.version(owner, 'v0.9.0') / 'world/wa-rooms/WA_A01'
        with self.assertRaisesRegex(ValueError, '第三方内容'):
            standalone.official_room_requirement('WA_A01')


if __name__ == '__main__':
    unittest.main()
