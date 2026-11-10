import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'editor'))
import room_bindings
import project_packages
import chamber_presets
import waiting_room


class UnbakedRoomGeometryTests(unittest.TestCase):
    def raw(self):
        tiles=[['1']*7 for _ in range(8)]
        for x in range(3,7):
            for y in range(3,6):tiles[x][y]='0'
        tiles[3][2]='4,3,6';tiles[3][1]='1,3';tiles[2][1]='1,3';tiles[1][1]='1,4,3'
        rows=['XX_ROOM','8*7','0*1|0|0','0,0','Border: Solid','','','','','0','','']
        return rows,tiles

    def pack(self,rows,tiles):
        rows=list(rows);rows[11]='|'.join(tile for column in tiles for tile in column)+'|'
        return ('\n'.join(rows)+'\n').encode('utf-8')

    def assert_rejected(self,content):
        with self.assertRaises(ValueError):room_bindings.geometry(None,content=content)
        with self.assertRaises(ValueError):project_packages._geometry(content,'XX_ROOM')

    def test_real_templates_and_existing_waiting_assets_are_readonly_valid(self):
        for root,manifest in chamber_presets.templates():
            before={name:(root/name).read_bytes() for name in manifest['files']}
            data=before['chamber.txt'];rows=data.decode('utf-8-sig').splitlines()
            expected=2 if manifest['id']=='mi-chamber-pebbles' else 1
            self.assertEqual(room_bindings.geometry(root/'chamber.txt'),dict(exitCount=expected,width=manifest['width'],height=manifest['height']))
            self.assertEqual(project_packages._geometry(data,rows[0].upper()),(manifest['cameraCount'],expected))
            rows[9]='0';rows[10]=''
            self.assertEqual(room_bindings.geometry(None,content=('\n'.join(rows)+'\n').encode('utf-8'))['exitCount'],expected)
            assets=chamber_presets.validated_assets(root,manifest)
            self.assertEqual(assets['rendered']['.txt'],data)
            self.assertEqual(before,{name:(root/name).read_bytes() for name in manifest['files']})
        assets=chamber_presets.validated_assets(waiting_room.ROOT,waiting_room.manifest())
        self.assertEqual(assets['rendered']['.txt'],(waiting_room.ROOT/'entry.txt').read_bytes())

    def test_native_ordering_gives_only_node_zero(self):
        root,manifest=chamber_presets.get('mi-chamber-broken')
        for node in (1,-1,True):
            changed=copy.deepcopy(manifest);changed['aiNode']=node
            with self.assertRaises(ValueError):chamber_presets.validated_assets(root,changed)
        changed=copy.deepcopy(manifest);changed['aiNode']=0
        self.assertTrue(chamber_presets.validated_assets(root,changed)['rendered'])

    def test_connected_bent_shortcut_and_two_cameras_are_valid(self):
        rows,tiles=self.raw();rows[3]='0,0|200,-30'
        data=self.pack(rows,tiles)
        self.assertEqual(room_bindings.geometry(None,content=data),dict(exitCount=1,width=8,height=7))
        self.assertEqual(project_packages._geometry(data,'XX_ROOM'),(2,1))
        with tempfile.TemporaryDirectory(prefix='mi-raw-room-') as folder:
            path=Path(folder)/'XX_ROOM.txt';path.write_bytes(data)
            self.assertEqual(room_bindings.geometry(path)['exitCount'],1)
            self.assertEqual(path.read_bytes(),data)

    def test_separate_exits_dens_transportation_and_dead_end_do_not_share_nodes(self):
        for end,expected in [('1,4,3',2),('1,5,3',1),('1,9,3',1),('1,12,3',1),('1,3',1)]:
            rows,tiles=self.raw();tiles=tiles+copy.deepcopy(tiles);rows[1]='16*7';tiles[9][1]=end
            content=self.pack(rows,tiles)
            self.assertEqual(room_bindings.geometry(None,content=content),dict(exitCount=expected,width=16,height=7))
            self.assertEqual(project_packages._geometry(content,'XX_ROOM'),(1,expected))

    def test_normal_shortcut_and_isolated_entrance_do_not_add_external_exits(self):
        rows,tiles=self.raw();tiles=tiles+copy.deepcopy(tiles);rows[1]='16*7'
        tiles[9][1]='4,3,6';tiles[9][2]='0'
        self.assertEqual(room_bindings.geometry(None,content=self.pack(rows,tiles))['exitCount'],1)
        tiles[9][1]='1';tiles[10][1]='1';tiles[11][1]='1'
        self.assertEqual(room_bindings.geometry(None,content=self.pack(rows,tiles))['exitCount'],1)

    def test_multi_exit_graphs_still_reject_ambiguous_or_unreachable_tunnels(self):
        for change in (
            lambda tiles:tiles[10].__setitem__(1,'1'),
            lambda tiles:tiles[10].__setitem__(2,'1,3'),
            lambda tiles:tiles[9].__setitem__(1,'1,4,5,3'),
            lambda tiles:tiles[10].__setitem__(1,'4,3,6'),
            lambda tiles:tiles[14].__setitem__(1,'1,4,3'),
        ):
            rows,tiles=self.raw();tiles=tiles+copy.deepcopy(tiles);rows[1]='16*7';change(tiles)
            self.assert_rejected(self.pack(rows,tiles))

    def test_shortcut_requires_exactly_one_unambiguous_connected_exit(self):
        mutations=[
            lambda tiles:tiles[2].__setitem__(1,'1'),
            lambda tiles:tiles[2].__setitem__(2,'1,3'),
            lambda tiles:tiles[6].__setitem__(1,'1,3'),
            lambda tiles:tiles[6].__setitem__(1,'1,4,3'),
            lambda tiles:tiles[1].__setitem__(1,'1,3'),
            lambda tiles:tiles[1].__setitem__(1,'0,4,3'),
            lambda tiles:tiles[3].__setitem__(2,'4,6'),
            lambda tiles:tiles[3].__setitem__(3,'1'),
            lambda tiles:tiles[4].__setitem__(2,'0'),
            lambda tiles:tiles[6].__setitem__(1,'1,5,3'),
            lambda tiles:tiles[6].__setitem__(1,'1,9,3'),
            lambda tiles:tiles[6].__setitem__(1,'1,12,3'),
            lambda tiles:tiles[6].__setitem__(1,'4,3,6'),
        ]
        for mutate in mutations:
            rows,tiles=self.raw();mutate(tiles);self.assert_rejected(self.pack(rows,tiles))

    def test_malformed_dimensions_tiles_cameras_and_mixed_bake_are_rejected(self):
        for index,value in [(1,'0*7'),(1,'8*0'),(1,'10000*10000'),(1,'8*7*2'),(3,''),(3,'nan,0'),(9,'-1'),(9,'0|1'),(10,'old-ai-map')]:
            rows,tiles=self.raw();rows[index]=value;self.assert_rejected(self.pack(rows,tiles))
        for value in ('x','8','1,0','1,99','1,,3'):
            rows,tiles=self.raw();tiles[0][0]=value;self.assert_rejected(self.pack(rows,tiles))
        rows,tiles=self.raw();data=self.pack(rows,tiles)
        for transform in (lambda value:value[:-2],lambda value:value+'1|',lambda value:value.replace('1|','',1)):
            text=data.decode('utf-8').splitlines();text[11]=transform(text[11]);self.assert_rejected(('\n'.join(text)+'\n').encode('utf-8'))

    def test_manifest_hashes_still_detect_changed_render(self):
        root,manifest=chamber_presets.templates()[0]
        changed=copy.deepcopy(manifest);changed['files']['chamber.txt']=hashlib.sha256(b'changed').hexdigest()
        with self.assertRaises(ValueError):chamber_presets.validated_assets(root,changed)


if __name__=='__main__':unittest.main()
