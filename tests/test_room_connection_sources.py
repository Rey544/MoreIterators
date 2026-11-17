import json
import os
import shutil
import time
import unittest
from unittest.mock import patch
from test_project_packages import ProjectPackageTests
import project_packages
import room_bindings
import room_source_choices
import room_workflow


class RoomConnectionSourceTests(unittest.TestCase):
    setUp=ProjectPackageTests.setUp
    validate=ProjectPackageTests.validate
    render=ProjectPackageTests.render
    palette=ProjectPackageTests.palette
    payload=ProjectPackageTests.payload
    unpack=ProjectPackageTests.unpack

    def test_strict_collection_rejects_mismatch_in_second_room(self):
        world=self.local/'world/xx/world_xx.txt'
        world.write_text('ROOMS\nXX_AI : DISCONNECTED, XX_ENTRY\nXX_ENTRY : XX_AI\nEND ROOMS\n','utf-8')
        selected=[dict(name='XX_AI',kind='ai'),dict(name='XX_ENTRY',kind='entry')]
        with self.assertRaises(room_bindings.RoomBindingError) as caught:
            project_packages.collect_rooms(self.project,selected,self.server)
        self.assertEqual(caught.exception.code,'rooms.error.workflowGeometryDetails')
        self.assertEqual(caught.exception.params['room'],'XX_ENTRY')

    def newer_geometry(self):
        source=self.local/'world/xx-rooms/XX_AI.txt'
        target=self.installed/'world/xx-rooms/XX_AI.txt'
        target.parent.mkdir(parents=True)
        for file in source.parent.glob('XX_AI*'):shutil.copy2(file,target.parent/file.name)
        shutil.copytree(self.local/'palettes',self.installed/'palettes')
        lines=target.read_text('utf-8').splitlines()
        lines[9]='20|4|15|0,1,0,0,1,|0,1,0,0,1,|0,1,0,0,1,|1,1,0,0,1,|'
        target.write_text('\n'.join(lines)+'\n','utf-8')
        stamp=time.time_ns()+1000000000;os.utime(target,ns=(stamp,stamp))
        return source,target

    def test_new_geometry_old_world_is_same_issue_in_ui_and_editable_export(self):
        old,new=self.newer_geometry()
        self.assertEqual(room_bindings.source_for(self.project,'ai'),new.with_suffix(''))
        state=room_workflow.load('selected')
        row=next(row for row in state['rooms'] if row['name']=='XX_AI')
        self.assertEqual(row['actualExitCount'],3);self.assertEqual(row['connectionSlotCount'],2)
        self.assertFalse(row['verified'])
        files=self.unpack(self.payload());manifest=json.loads(files['manifest.json'])
        self.assertEqual(manifest['connectionState'],'pending')
        self.assertEqual(files['rooms/XX_AI/rendered/XX_AI.txt'],new.read_bytes())
        self.assertEqual(manifest['rooms'][0]['connections'],['DISCONNECTED','XX_ENTRY'])

    def test_explicit_source_choice_has_priority_over_newer_geometry(self):
        old,new=self.newer_geometry()
        with patch.object(room_source_choices,'selected_source',side_effect=lambda pid,name:old.with_suffix('') if name=='XX_AI' else None):
            self.assertEqual(room_bindings.source_for(self.project,'ai'),old.with_suffix(''))
            row=next(row for row in room_workflow.load('selected')['rooms'] if row['name']=='XX_AI')
            self.assertEqual(row['actualExitCount'],2);self.assertTrue(row['verified'])
            files=self.unpack(self.payload())
            self.assertEqual(files['rooms/XX_AI/rendered/XX_AI.txt'],old.read_bytes())
            self.assertNotIn('connectionState',json.loads(files['manifest.json']))


if __name__=='__main__':unittest.main()
