import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'editor'))
import test_standalone_extra_rooms as fixtures
import server
import storage


class LegacyProjectJsonImportTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.ExtraRoomExportTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        change=patch.object(server,'DESIGNS',self.fixture.data/'runtime');change.start();self.addCleanup(change.stop)
        change=patch.object(storage,'settings',{});change.start();self.addCleanup(change.stop)

    def test_old_and_current_json_import_keep_authored_content_and_leave_existing_work_untouched(self):
        original=storage.project_file('selected').read_bytes()
        for index,schema in enumerate(('eoe.creator.v2','moreiterators.project.v1')):
            value=server.default();value.update(schema=schema,projectId='legacy-'+str(index),name='旧作品 '+str(index),authorNotes='原始作者备注')
            value['design']['bodyColor']='#A1B2C3'
            value['design'].pop('sleeveMapping',None)
            value['design'].pop('rightLegLength',None)
            with self.subTest(schema=schema):
                imported=server.import_project(copy.deepcopy(value))
                saved=json.loads(storage.project_file(value['projectId']).read_text('utf-8'))
                self.assertEqual(imported['projectId'],value['projectId'])
                self.assertEqual(saved['schema'],schema)
                self.assertEqual(saved['authorNotes'],value['authorNotes'])
                self.assertEqual(saved['design']['bodyColor'],'#A1B2C3')
                self.assertEqual(saved['textures'],value['textures'])
                self.assertIn('dialogue',saved)
                self.assertEqual(storage.project_file('selected').read_bytes(),original)

    def test_reimport_existing_json_preserves_room_identity_and_records_previous_version(self):
        file=storage.project_file('selected');original=file.read_bytes();previous=json.loads(original)
        incoming=copy.deepcopy(previous);incoming['schema']='eoe.creator.v2';incoming['name']='重新导入的外观'
        incoming['design']['bodyColor']='#A1B2C3'
        incoming['roomBinding'].update(region='YY',ai='YY_OTHER_AI',entry='YY_OTHER_ENTRY')
        result=server.import_project(incoming)
        self.assertEqual(result['roomBinding'],previous['roomBinding'])
        self.assertEqual(result['design']['bodyColor'],'#A1B2C3')
        history=list(storage.history_directory('selected').glob('*.json'))
        self.assertEqual(len(history),1)
        self.assertEqual(json.loads(history[0].read_text('utf-8')),previous)
        self.assertFalse((self.fixture.local/'world/yy-rooms').exists())


if __name__=='__main__':unittest.main()
