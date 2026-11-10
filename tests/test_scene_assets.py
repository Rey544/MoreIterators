import base64
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'editor'))
import scene_assets as scenes


def png(color=(255,0,0,255),size=(8,6)):
    out=io.BytesIO();Image.new('RGBA',size,color).save(out,'PNG');return out.getvalue()


def data(raw):return 'data:image/png;base64,'+base64.b64encode(raw).decode()


def draft():
    return dict(schema=scenes.SCHEMA,scenes=[dict(kind='select_menu_scene',idle_depths=[2.8],select_menu_pos=[-10,100],
        glow_pos=[730,335],mark_pos=[740,575],slugcat_depth=2.8,images=[
        dict(name='background',png=data(png()),pos=[442,134],depth=3.5,shader='Basic',flatmode=False),
        dict(name='foreground',png=data(png((0,255,0,128))),pos=[301,18],depth=1.5,shader='Normal',flatmode=False)])])


class SceneAssetTests(unittest.TestCase):
    def test_native_export_reimport_preserves_pixels_order_coordinates_depth_and_fields(self):
        original=draft()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);written=scenes.write(root,'author.test',original)
            self.assertEqual(scenes.audit(root,'author.test',original),written)
            self.assertEqual(scenes.audit_export(root,'author.test',written['features'],written['files']),written)
            doc_path=next(name for name in written['files'] if name.endswith('.json'))
            document=json.loads((root/doc_path).read_text('utf-8'))
            assets={name:(root/name).read_bytes() for name in written['files'] if name.endswith('.png')}
            imported=scenes.import_scene(document,assets)
            self.assertEqual(imported,original['scenes'][0])
            self.assertEqual([image['name'] for image in document['images']],['background','foreground'])
            self.assertNotIn('png',document['images'][0]);self.assertNotIn('kind',document)
            self.assertTrue(all(not Path(name).is_absolute() and '..' not in name.split('/') for name in written['files']))

    def test_all_five_native_feature_bindings_have_separate_namespaces(self):
        value=draft();value['scenes']=[dict(copy.deepcopy(value['scenes'][0]),kind=kind) for kind in scenes.KINDS]
        with tempfile.TemporaryDirectory() as folder:
            result=scenes.write(folder,'author.test',value)
            self.assertEqual(set(result['features']),set(scenes.KINDS));self.assertEqual(len(set(result['features'].values())),5)
            self.assertEqual(len(result['files']),15)
            other=scenes._planned('author.other',value)[0]
            self.assertFalse(set(result['features'].values())&set(other.values()))

    def test_real_slugbase_defaults_and_required_fields(self):
        native=dict(id='Example',scene_folder='scenes/example',images=[dict(name='layer',pos=[0,0])],idle_depths=[2.8])
        result=scenes.import_scene(native,{'example-mod/scenes/example/layer.png':png()})
        self.assertEqual(result['images'][0]['depth'],-1);self.assertEqual(result['images'][0]['shader'],'Normal')
        self.assertFalse(result['images'][0]['flatmode'])
        for key in ('idle_depths','images'):
            invalid=copy.deepcopy(native);del invalid[key]
            with self.assertRaises(ValueError):scenes.import_scene(invalid,{'layer.png':png()})
        invalid=copy.deepcopy(native);del invalid['images'][0]['pos']
        with self.assertRaises(ValueError):scenes.import_scene(invalid,{'layer.png':png()})

    def test_unsafe_paths_duplicates_invalid_depth_and_image_are_rejected_before_writing(self):
        values=[]
        for name in ('../escape','C:/escape','/escape','a\\b','a//b','CON','space.','layer.png'):
            value=draft();value['scenes'][0]['images'][0]['name']=name;values.append(value)
        for depth in (0,-2,float('nan'),float('inf'),True):
            value=draft();value['scenes'][0]['images'][0]['depth']=depth;values.append(value)
        value=draft();value['scenes'][0]['images'][1]['name']='BACKGROUND';values.append(value)
        value=draft();value['scenes'][0]['images'][0]['png']=data(b'not png');values.append(value)
        value=draft();value['scenes'][0]['images'][0]['shader']='unknown';values.append(value)
        with tempfile.TemporaryDirectory() as folder:
            for value in values:
                with self.subTest(value=value['scenes'][0]['images'][0].get('name')):
                    with self.assertRaises(ValueError):scenes.write(folder,'author.test',value)
                    self.assertEqual(list(Path(folder).iterdir()),[])

    def test_depth_texture_half_height_is_required_only_for_native_depth_shaders(self):
        value=draft();value['scenes'][0]['images']=[dict(name='odd',png=data(png(size=(8,5))),pos=[0,0],depth=2.8,shader='Basic')]
        scenes.validate(value)
        value['scenes'][0]['images'][0]['shader']='Normal'
        with self.assertRaises(ValueError):scenes.validate(value)
        value['scenes'][0]['images'][0]['depth']=-1;scenes.validate(value)

    def test_missing_ambiguous_and_traversal_imports_fail_without_guessing(self):
        native=dict(id='Example',images=[dict(name='layer',pos=[0,0])],idle_depths=[2.8])
        for assets in ({},{'a/layer.png':png(),'b/layer.png':png()},{'../layer.png':png()}):
            with self.assertRaises(ValueError):scenes.import_scene(native,assets)

    def test_final_audit_rejects_mutation_extra_paths_and_wrong_binding(self):
        with tempfile.TemporaryDirectory() as folder:
            stage=Path(folder);result=scenes.write(stage,'author.test',draft())
            wrong=dict(result['features']);wrong['sleep_scene']=wrong.pop('select_menu_scene')
            with self.assertRaises(ValueError):scenes.audit_export(stage,'author.test',wrong,result['files'])
            with self.assertRaises(ValueError):scenes.audit_export(stage,'author.test',result['features'],result['files']+['../extra.png'])
            doc=next(stage/name for name in result['files'] if name.endswith('.json'));value=json.loads(doc.read_text('utf-8'));value['scene_folder']='../outside';doc.write_text(json.dumps(value),'utf-8')
            with self.assertRaises(ValueError):scenes.audit_export(stage,'author.test',result['features'],result['files'])

    def test_existing_nonmatching_assets_are_never_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            result=scenes.write(folder,'author.test',draft());file=Path(folder)/next(p for p in result['files'] if p.endswith('.png'));file.write_bytes(b'keep')
            with self.assertRaises(ValueError):scenes.write(folder,'author.test',draft())
            self.assertEqual(file.read_bytes(),b'keep')


if __name__=='__main__':unittest.main()
