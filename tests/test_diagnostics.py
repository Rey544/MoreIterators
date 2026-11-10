import json,tempfile,unittest,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'editor'))
import diagnostics,storage

class DiagnosticsTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
  self.game=self.root/'game';self.archive=self.root/'archive'
  self.patches=[patch.object(storage,'GAME',self.game),patch.object(storage,'DATA',self.root/'data'),patch.object(storage,'archive_root',return_value=self.archive)]
  for context in self.patches:context.start()
  self.project=self.root/'data/projects/selected/project.json';self.project.parent.mkdir(parents=True)
  self.project.write_text(json.dumps({'dialogue':{'first':[{'text':'PRIVATE CREATION MUST STAY IN PROJECT'}]}}),'utf-8')
  self.original=self.project.read_bytes()
 def tearDown(self):
  self.assertEqual(self.project.read_bytes(),self.original)
  for context in reversed(self.patches):context.stop()
  self.temp.cleanup()
 def log(self,name,text):
  file=self.game/'BepInEx'/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_text(text,'utf-8');return file
 def test_missing_log_is_available_as_a_read_only_status(self):
  result=diagnostics.snapshot()
  self.assertFalse(result['available']);self.assertEqual(result['errors'],[]);self.assertEqual(result['tail'],'')
  self.assertFalse(self.game.exists());self.assertFalse(self.archive.exists())
 def test_prefers_log_and_falls_back_to_txt_without_mutating_either(self):
  fallback=self.log('LogOutput.txt','[Error : More Iterators] fallback exception\n')
  self.assertEqual(diagnostics.snapshot()['errors'][0]['source'],'More Iterators')
  preferred=self.log('LogOutput.log','[Fatal : 更多迭代器] current exception\n')
  before={file:file.read_bytes() for file in (fallback,preferred)}
  result=diagnostics.snapshot()
  self.assertTrue(result['available']);self.assertEqual(result['logPath'],str(preferred));self.assertEqual(result['errors'][0]['source'],'更多迭代器')
  self.assertIsNotNone(result['modified'])
  for file,data in before.items():self.assertEqual(file.read_bytes(),data)
 def test_preserves_multiline_stack_and_stops_at_next_log_entry(self):
  self.log('LogOutput.log','[Error : MoreIterators] Failure\nSystem.InvalidOperationException: broken\n  at Example.Run()\n[Info : Loader] resumed\nnot part of stack\n[Warning : 更多迭代器] caution\n  detail\n')
  result=diagnostics.snapshot()
  self.assertEqual([entry['source'] for entry in result['errors']],['MoreIterators','更多迭代器'])
  self.assertIn('System.InvalidOperationException: broken\n  at Example.Run()',result['errors'][0]['text'])
  self.assertNotIn('resumed',result['errors'][0]['text']);self.assertNotIn('not part of stack',result['errors'][0]['text'])
  self.assertIn('\n  detail',result['errors'][1]['text'])
 def test_reads_bounded_tail_and_keeps_recent_errors(self):
  self.log('LogOutput.log','discarded prefix '*100+'\n[Error : MoreIterators] retained\n  at Recent.Frame()\n')
  with patch.object(diagnostics,'MAX_LOG_BYTES',128):result=diagnostics.snapshot()
  self.assertTrue(result['truncated']);self.assertLessEqual(len(result['tail'].encode('utf-8')),128)
  self.assertEqual(result['errors'][0]['source'],'MoreIterators');self.assertNotIn('discarded prefix',result['tail'])
  self.log('LogOutput.log',''.join('[Error : MoreIterators] exception '+str(index)+'\n' for index in range(40)))
  result=diagnostics.snapshot()
  self.assertEqual(len(result['errors']),30);self.assertTrue(result['errors'][0]['text'].endswith('exception 10'));self.assertTrue(result['errors'][-1]['text'].endswith('exception 39'))
 def test_third_party_issues_remain_only_in_original_export_tail(self):
  text='[Error : RCS] expected condition\n  at RCS.Load()\n[Warning : ThirdParty] MoreIterators is mentioned here\n[Error : MoreIterators.Helper] MI failure mention\n[Error : 更多迭代器] own failure\n  at MoreIterators.Load()\n[Fatal : Foreign] external fatal\n  at Foreign.Run()\n'
  file=self.log('LogOutput.log',text)
  result=diagnostics.snapshot()
  self.assertEqual(result['tail'],file.read_bytes().decode('utf-8'))
  self.assertEqual(file.read_text('utf-8'),text)
  self.assertEqual(len(result['errors']),1)
  self.assertEqual(result['errors'][0]['source'],'更多迭代器')
  self.assertNotIn('external fatal',result['errors'][0]['text'])
 def test_old_external_mirrors_do_not_count_as_mi_errors(self):
  text='[Error : 更多迭代器] [MI-DIAG] session=012345abcdef code=EXTERNAL-LOG node=BepInEx issue=012345abcdef-1 source=RCS severity=Error count=1 kind=Log context=external\nold foreign error\n[Error : More Iterators] [MI-DIAG] session=012345abcdef code=EXTERNAL-UNITY node=UnityEngine issue=012345abcdef-2 source=Unity Log severity=Exception count=1 kind=Exception context=external\nNullReferenceException: foreign\n[Error : MoreIterators] [MI-DIAG] code=MI-OWN node=load\nown error\n'
  file=self.log('LogOutput.log',text)
  result=diagnostics.snapshot()
  self.assertEqual(result['tail'],file.read_bytes().decode('utf-8'))
  self.assertEqual(len(result['errors']),1)
  self.assertIn('code=MI-OWN',result['errors'][0]['text'])
 def test_standalone_runtime_uses_structured_ownership_with_custom_mod_name(self):
  text='[Error : My Exported OC] [MI-DIAG] session=012345abcdef code=MI-PEARL-DATA node=CreatorPearlCatalog.Read issue=012345abcdef-1 source=MI severity=Error count=1 kind=Exception exception=IOException origin=Reader.Run keywords=IOException context=fixture\nSystem.IO.IOException: missing file\n  at Reader.Run()\n[Warning : My Exported OC] [MI-DIAG] session=012345abcdef code=MI_BROADCAST_NULL_TEXT node=TextLines issue=012345abcdef-2 source=MI severity=Warning count=1 kind=Warning context=fixture\n[Error : My Exported OC] [MI-DIAG] code=MI-DIAGNOSTIC-UI node=notification\nSystem.Exception: failed popup\n'
  self.log('LogOutput.log',text)
  result=diagnostics.snapshot()
  self.assertEqual(len(result['errors']),3)
  self.assertEqual([x['source'] for x in result['errors']],['My Exported OC']*3)
  self.assertIn('  at Reader.Run()',result['errors'][0]['text'])
 def test_incidental_or_incomplete_markers_do_not_claim_external_logs(self):
  rows=[
   '[Error : Foreign] documentation mentions [MI-DIAG] code=MI-TEST node=test',
   '[Error : Foreign] [MI-DIAG] session=012345abcdef code=MI-TEST node=test source=MI',
   '[Error : Foreign] [MI-DIAG] session=012345abcdef code=MI-TEST node=test issue=000000000000-1 source=MI severity=Error count=1 kind=Log',
   '[Error : Foreign] [MI-DIAG] session=012345abcdef code=MI-TEST node=test issue=012345abcdef-1 source=Foreign severity=Error count=1 kind=Log',
   '[Error : Foreign] [MI-DIAG] session=012345abcdef code=OTHER node=test issue=012345abcdef-1 source=MI severity=Error count=1 kind=Log',
  ]
  text='\n'.join(rows)+'\n';file=self.log('LogOutput.log',text)
  result=diagnostics.snapshot()
  self.assertEqual(result['errors'],[]);self.assertEqual(result['tail'],file.read_bytes().decode('utf-8'))
 def test_error_payload_has_stable_codes_and_keeps_exception_trace(self):
  for error,code in [(ValueError('Invalid field'),'error.request.invalid'),(KeyError('missing'),'error.request.invalid'),(TypeError('Wrong field type'),'error.request.invalid'),(OSError('Cannot read file'),'error.request.io'),(RuntimeError('Unexpected failure'),'error.request.internal')]:
   with self.subTest(error=type(error).__name__):
    try:raise error
    except Exception as caught:payload=diagnostics.error_payload(caught,'/api/example')
    self.assertEqual(payload['code'],code);self.assertEqual(payload['params'],{'operation':'/api/example'});self.assertEqual(payload['details'],str(error))
  written=(self.archive/'logs/studio-errors.log').read_text('utf-8')
  self.assertIn('Traceback (most recent call last)',written);self.assertIn('RuntimeError: Unexpected failure',written)
  self.assertNotIn('PRIVATE CREATION',written)
  self.assertNotIn('PRIVATE CREATION',json.dumps(diagnostics.snapshot()))

if __name__=='__main__':unittest.main()
