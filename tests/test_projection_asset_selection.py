import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'editor'))
import projections,room_bindings,storage


class ProjectionAssetSelectionTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.game=self.root/'game'
        self.assets=self.game/'RainWorld_Data/StreamingAssets'
        self.assets.mkdir(parents=True)
        self.own=self.assets/'mods/own-project'
        self.options=self.root/'options'
        self.project=dict(projectId='selected',design=dict(roomWorkColor='#476d67'))
        self.source=self.root/'ROOM_AI'
        self.user=self.root/'projects/selected/project.json'
        self.user.parent.mkdir(parents=True)
        self.user.write_text('{"images":[{"png":"data:image/png;base64,private"}]}','utf-8')
        self.original=self.user.read_bytes()
        for context in (
            patch.object(storage,'GAME',self.game),
            patch.object(storage,'RUNTIME',self.root/'runtime'),
            patch.object(storage,'available_game_root',return_value=self.game),
            patch.object(storage,'target_mod',return_value=self.own),
            patch.object(room_bindings,'_options_paths',return_value=[self.options]),
            patch.object(room_bindings,'_selection_key',None),
            patch.object(room_bindings,'_selection_cache',None),
        ):
            context.start();self.addCleanup(context.stop)
        self.enabled()

    def tearDown(self):
        self.assertEqual(self.user.read_bytes(),self.original)

    def enabled(self,*ids):
        self.options.write_text('EnabledMods<optB>'+'<optC>'.join(ids)+'<optA>','utf-8')
        room_bindings._selection_key=None

    def mod(self,name):
        root=self.assets/'mods'/name;root.mkdir(parents=True,exist_ok=True)
        (root/'modinfo.json').write_text(json.dumps(dict(id=name)),'utf-8')
        return root

    def png(self,root,relative,color):
        file=root/relative;file.parent.mkdir(parents=True,exist_ok=True)
        Image.new('RGB',(32,8),color).save(file)
        return file

    def available(self,key):
        return next(row['available'] for row in projections.reference()['assets'] if row['id']==key)

    def test_installed_disabled_dlc_reference_is_not_listed_or_read(self):
        root=self.mod('moreslugcats')
        file=self.png(root,'illustrations/aiimg1_dm.png','red')
        before=file.read_bytes()
        self.assertFalse(self.available('aiimg1_dm'))
        with self.assertRaises(ValueError):projections.reference_image('aiimg1_dm')
        self.assertEqual(file.read_bytes(),before)

    def test_dlc_reference_tracks_enable_disable_without_restart(self):
        root=self.mod('moreslugcats')
        file=self.png(root,'illustrations/aiimg1_dm.png','red')
        self.enabled('moreslugcats')
        self.assertTrue(self.available('aiimg1_dm'))
        self.assertEqual(projections.reference_image('aiimg1_dm'),file.read_bytes())
        self.enabled()
        self.assertFalse(self.available('aiimg1_dm'))
        with self.assertRaises(ValueError):projections.reference_image('aiimg1_dm')

    def test_explicit_remix_variant_never_falls_back_to_base(self):
        base=self.png(self.assets,'projections/str_proj.png','blue')
        self.png(self.mod('rwremix'),'projections/str_proj.png','red')
        self.assertEqual(projections.reference_image('str_proj'),base.read_bytes())
        with self.assertRaises(ValueError):projections.reference_image('str_proj_remix')

    def test_explicit_dlc_reference_uses_selected_version_then_newest_then_owner_base(self):
        root=self.mod('moreslugcats');relative='illustrations/aiimg1_dm.png'
        base=self.png(root,relative,'red')
        newest=self.png(root/'newest',relative,'blue')
        current=self.png(root/'v1.11.0',relative,'green')
        self.png(root/'v1.10.4',relative,'yellow')
        self.png(self.mod('other-content')/'v1.11.0',relative,'purple')
        (self.assets/'GameVersion.txt').write_text('v1.11.0','utf-8')
        self.enabled('moreslugcats','other-content')
        self.assertEqual(projections.reference_image('aiimg1_dm'),current.read_bytes())
        current.unlink()
        self.assertEqual(projections.reference_image('aiimg1_dm'),newest.read_bytes())
        newest.unlink()
        self.assertEqual(projections.reference_image('aiimg1_dm'),base.read_bytes())
        self.enabled('other-content')
        self.assertFalse(self.available('aiimg1_dm'))
        with self.assertRaises(ValueError):projections.reference_image('aiimg1_dm')

    def test_base_reference_respects_enabled_override_and_reverts_when_disabled(self):
        base=self.png(self.assets,'illustrations/aiimg1.png','blue')
        override=self.png(self.mod('enabled-content'),'illustrations/aiimg1.png','red')
        self.enabled('enabled-content')
        self.assertEqual(projections.reference_image('aiimg1'),override.read_bytes())
        self.enabled()
        self.assertEqual(projections.reference_image('aiimg1'),base.read_bytes())

    def test_palette_ignores_disabled_dlc_and_third_party(self):
        self.png(self.assets,'palettes/palette26.png','blue')
        self.png(self.mod('moreslugcats'),'palettes/palette26.png','red')
        self.png(self.mod('disabled-content'),'palettes/palette26.png','green')
        self.assertEqual(projections.room_palette(self.project,self.source).getpixel((0,0)),(0,0,255))

    def test_palette_uses_enabled_override_then_base(self):
        self.png(self.assets,'palettes/palette26.png','blue')
        self.png(self.mod('enabled-content'),'palettes/palette26.png','red')
        self.enabled('enabled-content')
        self.assertEqual(projections.room_palette(self.project,self.source).getpixel((0,0)),(255,0,0))
        self.enabled()
        self.assertEqual(projections.room_palette(self.project,self.source).getpixel((0,0)),(0,0,255))

    def test_missing_enabled_palette_does_not_read_installed_disabled_palette(self):
        self.png(self.mod('moreslugcats'),'palettes/palette26.png','red')
        with self.assertRaises(ValueError):projections.room_palette(self.project,self.source)

    def test_unenabled_current_project_remains_editable(self):
        self.mod('own-project')
        file=self.png(self.own,'palettes/palette26.png','purple')
        self.png(self.assets,'palettes/palette26.png','blue')
        before=file.read_bytes()
        self.assertFalse(room_bindings.is_enabled_asset(file))
        self.assertEqual(projections.room_palette(self.project,self.source).getpixel((0,0)),(128,0,128))
        self.assertEqual(file.read_bytes(),before)

    def test_palette_rows_match_unity_bottom_left_coordinates(self):
        theme=tuple(int(self.project['design']['roomWorkColor'][i:i+2],16)/255 for i in (1,3,5))
        for height in (8,16):
            with self.subTest(height=height):
                original=Image.new('RGB',(32,height))
                for y in range(height):
                    for x in range(32):original.putpixel((x,y),((x*7+y*3)%256,(x*11+y*17)%256,(x*13+y*23)%256))
                file=self.own/'palettes/palette26.png';file.parent.mkdir(parents=True,exist_ok=True);original.save(file)
                actual=projections.room_palette(self.project,self.source)
                for y in range(8):
                    unity_y=height-1-y
                    for x in range(32):
                        expected=original.getpixel((x,y))
                        if x<30 and unity_y%8<=5:
                            r,g,b=expected;v=.299*r+.587*g+.114*b
                            expected=tuple(round(max(0,min(255,v*(.45+.55*c*1.6)))) for c in theme)
                        self.assertEqual(actual.getpixel((x,y)),expected,(x,y,unity_y))


if __name__=='__main__':unittest.main()
