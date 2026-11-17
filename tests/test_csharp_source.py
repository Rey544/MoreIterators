import ast
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'editor'))
import csharp_source as source
import playback_adapters


def token_values(text):
    return [(item.kind, item.value) for item in source.tokens(text)]


class CSharpSourceTests(unittest.TestCase):
    def test_literals_and_comments_do_not_supply_braces_or_code(self):
        text = '/* class Wrong { */ public class Wanted { string a="} /* fake */ \\\" {"; string b=@"{ "" }"; char c=\'}\'; // }\n void M(){} } // }'
        result = source.extract_class(text, 'Wanted')
        self.assertTrue(result.startswith('public class Wanted'))
        self.assertTrue(result.endswith('void M(){} }'))
        self.assertIn('string b=@"{ "" }";', result)
        with self.assertRaises(source.SourceError):source.extract_class(text, 'Wrong')

    def test_class_extraction_accepts_compact_allman_and_comments(self):
        for header in ('public class CreatorEncounter:Base{', 'public /*a*/ class\nCreatorEncounter : Base\n{'):
            text = 'namespace X { class Before {} '+header+'void M(){if(true){}} } class After {} }'
            result = source.extract_class(text,'CreatorEncounter')
            self.assertNotIn('Before',result)
            self.assertNotIn('After',result)
            self.assertEqual(token_values(result),token_values('public class CreatorEncounter:Base{void M(){if(true){}}}'))

    def test_missing_duplicate_or_broken_class_is_rejected(self):
        for text in ('public class Other {}', 'public class Wanted{} public class Wanted{}', 'public class Wanted { void M(){', 'public class Wanted;'):
            with self.subTest(text=text),self.assertRaises(source.SourceError):source.extract_class(text,'Wanted')

    def test_code_replacement_ignores_decoys_and_accepts_whitespace(self):
        pattern = 'RuntimePaths.Initialize();'
        text = '/* RuntimePaths.Initialize(); */ string a="RuntimePaths.Initialize();"; RuntimePaths /*x*/ .\nInitialize ( ) ;'
        result = source.replace_code(text,pattern,'Ready();','initialize')
        self.assertEqual(result.count('Ready();'),1)
        self.assertIn('/* RuntimePaths.Initialize(); */',result)
        self.assertIn('"RuntimePaths.Initialize();"',result)
        self.assertTrue(result.endswith('Ready();'))

    def test_code_replacement_requires_unique_unqualified_token_boundary(self):
        for text in ('OtherRuntimePaths.Initialize();','other.RuntimePaths.Initialize();','RuntimePaths.Initialize(); RuntimePaths.Initialize();','string a="RuntimePaths.Initialize();";'):
            with self.subTest(text=text),self.assertRaises(source.SourceError):
                source.replace_code(text,'RuntimePaths.Initialize();','Ready();','initialize')

    def test_plugin_attribute_handles_comments_newlines_and_escaped_name(self):
        text = '/* [BepInPlugin("fake","fake",BuildVersion.Plugin)] */ [\nBepInPlugin /*x*/ ( @"moreiterators.core", "old", BuildVersion\n. Plugin )\n] class P{}'
        result = source.replace_plugin_identity(text,'author.sample','名字 "quoted"\nsecond','0.5.1')
        self.assertIn('"author.sample", "名字 \\"quoted\\"\\nsecond", "0.5.1"',result)
        self.assertIn('/* [BepInPlugin("fake","fake",BuildVersion.Plugin)] */',result)

    def test_plugin_attribute_missing_duplicate_or_wrong_arguments_fail(self):
        valid = '[BepInPlugin("moreiterators.core","old",BuildVersion.Plugin)]'
        for text in ('class P{}',valid+valid,valid.replace('moreiterators.core','other'),valid.replace('BuildVersion.Plugin','"1"'),valid.replace(')]',',1)]')):
            with self.subTest(text=text),self.assertRaises(source.SourceError):source.replace_plugin_identity(text,'a.b','Name','1')

    def test_namespace_and_identifier_replacements_do_not_touch_literals(self):
        text = '/* namespace MoreIterators */ namespace /*n*/ MoreIterators\n{string a="namespace MoreIterators __ENCOUNTER__"; __ENCOUNTER__}'
        result = source.replace_namespace(text,'MoreIterators','Content_A')
        result = source.replace_identifier(result,'__ENCOUNTER__','class Added{}',required=True)
        self.assertIn('/* namespace MoreIterators */',result)
        self.assertIn('"namespace MoreIterators __ENCOUNTER__"',result)
        self.assertIn('class Added{}',result)
        self.assertIn('namespace /*n*/ Content_A',result)
        for text in ('namespace Other{}','namespace MoreIterators{} namespace MoreIterators{}','namespace MoreIterators.Other{}'):
            with self.assertRaises(source.SourceError):source.replace_namespace(text,'MoreIterators','Content_A')
        for text in ('string a="__ENCOUNTER__";','__ENCOUNTER__ __ENCOUNTER__'):
            with self.assertRaises(source.SourceError):source.replace_identifier(text,'__ENCOUNTER__','class Added{}',required=True)

    def test_string_resources_preserve_comments_and_literal_shapes(self):
        text = '// "MoreIterators_A" 请重新应用项目。\nstring a="MoreIterators_A"; string b=@"moreiterators_B"; string c="请重新应用项目。"; const string id="__MOD_ID__";'
        result = source.replace_string_resources(text,replacements=(('请重新应用项目。','请重新安装此内容模组。'),),prefixes=(('MoreIterators_','IC_hash_'),('moreiterators_','ic_hash_')),placeholder=('__MOD_ID__','author.sample'))
        self.assertIn('// "MoreIterators_A" 请重新应用项目。',result)
        self.assertIn('"IC_hash_A"',result)
        self.assertIn('@"ic_hash_B"',result)
        self.assertIn('"请重新安装此内容模组。"',result)
        self.assertIn('"author.sample"',result)
        for text in ('// "__MOD_ID__"','string a="__MOD_ID____MOD_ID__";'):
            with self.assertRaises(source.SourceError):source.replace_string_resources(text,placeholder=('__MOD_ID__','x'))

    def test_invalid_or_unsupported_lexical_input_fails_explicitly(self):
        for text in ('/* unclosed','"unclosed','"newline\n"',"'unclosed",'$"interpolated"','"""raw"""'):
            with self.subTest(text=text),self.assertRaises(source.SourceError):source.tokens(text)


class StandaloneFormattingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='mi-source-reader-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        tree = ast.parse((ROOT/'editor/standalone.py').read_text('utf-8'))
        names = {'_runtime_source_plan','compiler_sources'}
        extracted = ast.Module(body=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in names],type_ignores=[])
        self.globals = dict(Path=Path,re=re,json=json,hashlib=hashlib,csharp_source=source,
                            storage=SimpleNamespace(WORKSPACE=self.root),playback_adapters=playback_adapters,
                            SOURCE_MANIFEST='templates/standalone/sources.json')
        exec(compile(extracted,str(ROOT/'editor/standalone.py'),'exec'),self.globals)
        self.meta = {'id':'author.sample','name':'作者 "名字"','version':'0.5.1'}

    def fixture(self, expanded=False):
        namespace = 'namespace MoreIterators\n{\n' if expanded else 'namespace MoreIterators{'
        encounter = 'public /*c*/ class\nCreatorEncounter : Base\n{' if expanded else 'public class CreatorEncounter:Base{'
        attribute = '[ BepInPlugin\n( "moreiterators.core", "旧名", BuildVersion /*v*/ . Plugin ) ]' if expanded else '[BepInPlugin("moreiterators.core","旧名",BuildVersion.Plugin)]'
        initialize = 'RuntimePaths /*call*/ . Initialize ( ) ;' if expanded else 'RuntimePaths.Initialize();'
        palette = 'orig ( cam , extension == null ? pal : extension . BasePalette ( cam , pal ) , ref texture ) ;' if expanded else 'orig(cam,extension==null?pal:extension.BasePalette(cam,pal),ref texture);'
        files = {
            'src/CreatorRuntime.cs':namespace+'class Before{} '+encounter+'string braces=@"{ "" }"; void M(){if(true){}} } class After{} }',
            'src/MoreIteratorsPlugin.cs':namespace+attribute+'class Plugin{void OnEnable(){Instance=this; '+initialize+'}void Palette(){'+palette+'}string atlas="MoreIterators_Atlas";} }',
            'templates/standalone/CreatorRuntime.cs':namespace+'__ENCOUNTER__ }',
            'templates/standalone/RuntimePaths.cs':namespace+'class RuntimePaths{public const string ModId="__MOD_ID__";} }',
            'src/CreatorLaunch.cs':namespace+'class CreatorLaunch{string text="请重新应用项目。";} }'}
        for name,text in files.items():
            path = self.root/name
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(text,'utf-8')
        manifest = {'schema':'moreiterators.standalone-sources.v1','sources':[name for name in files if name!='src/CreatorRuntime.cs'],
                    'fragments':{'encounter':'src/CreatorRuntime.cs'},'excluded':{}}
        (self.root/'templates/standalone/sources.json').write_text(json.dumps(manifest),'utf-8')
        return {name:hashlib.sha256((self.root/name).read_bytes()).hexdigest() for name in files}

    def generate(self, name, projects=()):
        output = self.root/name
        output.mkdir()
        files,suffix = self.globals['compiler_sources'](output,self.meta,projects)
        return {file.name:file.read_text('utf-8') for file in files},suffix

    def test_compact_and_allman_generation_preserve_inputs_and_same_tokens(self):
        compressed = self.fixture(False)
        first,suffix = self.generate('compressed')
        self.assertEqual(compressed,{name:hashlib.sha256((self.root/name).read_bytes()).hexdigest() for name in compressed})
        expanded = self.fixture(True)
        second,other_suffix = self.generate('allman')
        self.assertEqual(expanded,{name:hashlib.sha256((self.root/name).read_bytes()).hexdigest() for name in expanded})
        self.assertEqual(suffix,other_suffix)
        self.assertEqual({key:token_values(value) for key,value in first.items()},{key:token_values(value) for key,value in second.items()})
        self.assertNotIn('After',second['CreatorRuntime.cs'])
        self.assertIn('"IC_'+suffix+'_Atlas"',second['MoreIteratorsPlugin.cs'])
        self.assertIn('roomTemplate=="ir"?13:pal',second['MoreIteratorsPlugin.cs'])
        self.assertIn('"author.sample"',second['RuntimePaths.cs'])
        self.assertIn('"请重新安装此内容模组。"',second['CreatorLaunch.cs'])

    def test_missing_palette_or_duplicate_attribute_stops_generation(self):
        for case in ('palette','attribute'):
            self.fixture(True)
            path = self.root/'src/MoreIteratorsPlugin.cs'
            text = path.read_text('utf-8')
            if case=='palette':text=text.replace('orig ( cam','different ( cam')
            else:text=text.replace('class Plugin','[BepInPlugin("moreiterators.core","x",BuildVersion.Plugin)] class Plugin')
            path.write_text(text,'utf-8')
            with self.subTest(case=case),self.assertRaises(source.SourceError):self.generate('invalid-'+case)

    def test_legacy_injection_is_located_but_public_export_remains_unsupported(self):
        self.fixture(True)
        projects = [{'legacyOracle':'fixture-original-author'}]
        original = json.dumps(projects)
        with self.assertRaisesRegex(ValueError,'original author workspace'):
            self.generate('legacy',projects)
        plugin = (self.root/'legacy/MoreIteratorsPlugin.cs').read_text('utf-8')
        self.assertIn('IteratorIntegrations.Register(new PlaybackAppearanceIntegration());',plugin)
        self.assertEqual(json.dumps(projects),original)


if __name__ == '__main__':
    unittest.main()
