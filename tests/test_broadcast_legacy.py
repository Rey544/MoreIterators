import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'editor'))
import broadcasts
import storage


class BroadcastLegacyTests(unittest.TestCase):
    def test_editor_rename_save_compile_preserves_all_legacy_line_fields(self):
        node=shutil.which('node')
        if node is None:self.skipTest('Node.js is not available')
        result=subprocess.run([node,str(Path(__file__).with_name('broadcast_legacy_model.mjs'))],capture_output=True,text=True,check=True)
        values=json.loads(result.stdout)
        with tempfile.TemporaryDirectory() as temporary,patch.object(storage,'DATA',Path(temporary)),patch.object(broadcasts,'room_index',return_value={}):
            saved=broadcasts.save(values['renamed'])
            self.assertEqual(saved['pages'],values['fixture']['pages'])
            self.assertNotIn('style',saved)
            self.assertEqual(broadcasts.compile_project(saved)['pages'],values['fixture']['pages'])
            compiled=broadcasts.compile_project(values['edited'])
            self.assertEqual(compiled['pages'],values['edited']['pages'])

    def test_explicit_color_choice_preserves_individual_timing(self):
        project=dict(pages=[dict(lines=[dict(text='Moon: One',color='#ffaa00',font='display',size=1.5,speed=.5,hold=4)])],useCharacterColors=True,speakers=[dict(name='Moon',aliases=[],color='#445566')])
        before=copy.deepcopy(project);compiled=broadcasts.compile_project(project)
        self.assertEqual(compiled['pages'][0]['lines'][0],dict(text='Moon: One',color='#445566',font='display',size=1.5,speed=.5,hold=4))
        self.assertEqual(project,before)


if __name__=='__main__':unittest.main()
