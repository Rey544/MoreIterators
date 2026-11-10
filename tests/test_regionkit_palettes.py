import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'editor'))
import project_packages
import standalone


class RegionKitPaletteTests(unittest.TestCase):
    def fixture(self,kind='standalone'):
        if kind=='project':
            from test_project_packages import ProjectPackageTests
            fixture=ProjectPackageTests()
        elif kind=='region':
            from test_region_packages import RegionPackageTests
            fixture=RegionPackageTests()
        else:
            from test_standalone_extra_rooms import ExtraRoomExportTests
            fixture=ExtraRoomExportTests()
        fixture.setUp();self.addCleanup(fixture.doCleanups)
        return fixture

    def install_regionkit(self,fixture,with_pom=True):
        for identifier,name,requirements in [('regionkit','RegionKit',['pom'])]+([('pom','POM',[])] if with_pom else []):
            root=fixture.assets/'mods'/identifier;root.mkdir(parents=True)
            (root/'modinfo.json').write_text(json.dumps(dict(id=identifier,name=name,requirements=requirements)),'utf-8')
            fixture.roots.insert(0,root)

    def extra_settings(self,fixture,room='ZX_AI'):
        file=Path(str(fixture.source(room))+'_settings.txt')
        text='Template: NONE\nPalette: 26\nFadePalette: 9100, 0.3\nMorePalette0: 9101, 0.5\nMorePalette1: 9102, 1\n'
        file.write_text(text,'utf-8')
        for index,color in [(9100,'red'),(9101,'blue'),(9102,'green')]:
            fixture.image(fixture.data/'projects/selected/rooms/palettes'/('palette'+str(index)+'.png'),color)
        return file,text

    def test_numbered_extra_references_preserve_native_palette_fields(self):
        text='Palette: 26\nFadePalette: 8, 0.3, 1\nMorePalette0: 14, 1, 1\nMorePalette12:\t9102, 0, 0.5\nMorePalette1: 14, 0.5, 1\n'
        self.assertEqual(standalone.room_palette_ids(text),{26,8,14,9102})
        self.assertTrue(standalone.uses_more_palettes(text))
        self.assertFalse(standalone.uses_more_palettes('Palette: 26\nFadePalette: 8, 0.5\n'))
        self.assertEqual(standalone.room_palette_ids('MorePalette: 9\nMorePaletteOther: 7\n# MorePalette0: 6\n'),set())

    def test_unused_room_does_not_add_dependency_or_asset(self):
        f=self.fixture();self.install_regionkit(f)
        self.extra_settings(f,'ZX_UNUSED')
        with f.archive() as archive:
            info=json.loads(f.read(archive,'modinfo.json'))
            self.assertNotIn('regionkit',info['requirements']);self.assertNotIn('pom',info['requirements'])
            self.assertFalse(any('palette910' in name for name in archive.namelist()))

    def test_selected_room_exports_all_fades_once_and_preserves_settings(self):
        f=self.fixture();self.install_regionkit(f);file,text=self.extra_settings(f)
        other=Path(str(f.source('ZX_ENTRY'))+'_settings.txt')
        other.write_text('Template: NONE\nMorePalette0: 9102, 1\n','utf-8')
        with f.archive() as archive:
            info=json.loads(f.read(archive,'modinfo.json'))
            self.assertEqual(info['requirements'].count('regionkit'),1)
            self.assertEqual(info['requirements'].count('pom'),1)
            self.assertEqual(dict(zip(info['requirements'],info['requirements_names']))['regionkit'],'RegionKit')
            for number in (26,9100,9101,9102):self.assertIn(f.request['id']+'/palettes/palette'+str(number)+'.png',archive.namelist())
            self.assertEqual(f.read(archive,'world/zx-rooms/ZX_AI_settings.txt').decode('utf-8').splitlines(),text.splitlines())
            self.assertFalse(any(name.endswith('RegionKit.dll') for name in archive.namelist()))
        self.assertEqual(file.read_text('utf-8'),text)

    def test_selected_extra_room_adds_dependency(self):
        f=self.fixture();self.install_regionkit(f);self.extra_settings(f,'ZX_EXTRA')
        with f.archive(['ZX_EXTRA']) as archive:
            self.assertIn('regionkit',json.loads(f.read(archive,'modinfo.json'))['requirements'])
            self.assertIn(f.request['id']+'/palettes/palette9102.png',archive.namelist())

    def test_registered_template_collects_extra_palette_and_dependency(self):
        f=self.fixture();self.install_regionkit(f)
        folder=f.local/'world/zx'
        (folder/'properties.txt').write_text('Palette: 26\nRoom Setting Templates: Extra\n','utf-8')
        text='Palette: 26\nMorePalette0: 9102, 1\n'
        (folder/'zx_settingstemplate_extra.txt').write_text(text,'utf-8')
        f.image(f.local/'palettes/palette9102.png','blue')
        with f.archive() as archive:
            self.assertIn('regionkit',json.loads(f.read(archive,'modinfo.json'))['requirements'])
            self.assertEqual(f.read(archive,'world/zx/zx_settingstemplate_extra.txt').decode().splitlines(),text.splitlines())
            self.assertIn(f.request['id']+'/palettes/palette9102.png',archive.namelist())

    def test_missing_framework_or_transitive_dependency_is_not_silently_ignored(self):
        f=self.fixture();self.extra_settings(f)
        with self.assertRaisesRegex(ValueError,'regionkit'):f.archive()
        self.install_regionkit(f,with_pom=False)
        with self.assertRaisesRegex(ValueError,'pom'):f.archive()

    def test_missing_custom_extra_palette_blocks_export(self):
        f=self.fixture();self.install_regionkit(f);self.extra_settings(f)
        (f.data/'projects/selected/rooms/palettes/palette9102.png').unlink()
        with self.assertRaisesRegex(ValueError,'palette9102'):f.archive()

    def test_audit_rejects_removed_regionkit_requirement(self):
        f=self.fixture();self.install_regionkit(f);self.extra_settings(f)
        with f.archive() as archive,tempfile.TemporaryDirectory() as folder:
            archive.extractall(folder);stage=Path(folder)/f.request['id'];file=stage/'modinfo.json'
            info=json.loads(file.read_text('utf-8'));index=info['requirements'].index('regionkit')
            info['requirements'].pop(index);info['requirements_names'].pop(index)
            file.write_text(json.dumps(info),'utf-8')
            with self.assertRaisesRegex(ValueError,'RegionKit'):standalone.audit(stage,['selected'])

    def test_audit_requires_transitive_dependency_and_rejects_unrelated_dependencies(self):
        f=self.fixture();self.install_regionkit(f);self.extra_settings(f)
        with f.archive() as archive,tempfile.TemporaryDirectory() as folder:
            archive.extractall(folder);stage=Path(folder)/f.request['id'];file=stage/'modinfo.json'
            original=json.loads(file.read_text('utf-8'));info=json.loads(json.dumps(original))
            index=info['requirements'].index('pom');info['requirements'].pop(index);info['requirements_names'].pop(index)
            file.write_text(json.dumps(info),'utf-8')
            with self.assertRaisesRegex(ValueError,'pom'):standalone.audit(stage,['selected'])
            original['requirements'].append('unrelated.mod');original['requirements_names'].append('Unrelated')
            file.write_text(json.dumps(original),'utf-8')
            with self.assertRaisesRegex(ValueError,'未被已选内容引用'):standalone.audit(stage,['selected'])

    def test_project_roundtrip_collects_all_extra_palettes(self):
        f=self.fixture('project');file=f.local/'world/xx-rooms/XX_AI_settings.txt'
        text=file.read_text('utf-8')+'FadePalette: 9101, 0, 1\nMorePalette0: 9102, 0.5, 1\nMorePalette1: 9103, 1, 0\n'
        file.write_text(text,'utf-8')
        for number in (9101,9102,9103):f.palette(f.local/('palettes/palette'+str(number)+'.png'),'blue')
        payload=f.payload();files=f.unpack(payload)
        self.assertEqual(json.loads(files['manifest.json'])['palettes'],[9100,9101,9102,9103])
        for number in (9100,9101,9102,9103):self.assertIn('palettes/palette'+str(number)+'.png',files)
        f.target();project_packages.import_package(payload,f.server)
        imported=project_packages._project_dir('selected')
        self.assertEqual((imported/'rooms/rendered/XX_AI_settings.txt').read_text('utf-8'),text)

    def test_whole_region_collects_extra_fades_and_recursive_dependencies(self):
        f=self.fixture('region');self.install_regionkit(f)
        file=f.owner/'world/zz-rooms/ZZ_A01_settings.txt'
        text=file.read_text('utf-8')+'MorePalette0: 9102, 0.5\nMorePalette1: 9103, 1\n';file.write_text(text,'utf-8')
        for number in (9102,9103):f.image(f.owner/('palettes/palette'+str(number)+'.png'),'green')
        with f.archive() as archive:
            self.assertEqual({item['id'] for item in json.loads(archive.read('region-manifest.json'))['dependencies']},{'author.map','regionkit','pom'})
            self.assertEqual(archive.read('world/zz-rooms/ZZ_A01_settings.txt').decode().splitlines(),text.splitlines())
            for number in (9102,9103):self.assertIn('palettes/palette'+str(number)+'.png',archive.namelist())


if __name__=='__main__':unittest.main()
