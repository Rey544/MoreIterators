
from pathlib import Path
from unittest.mock import patch
import json
import os
import subprocess
import sys
import threading
import time
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'editor'))
import install_picker as picker


@unittest.skipUnless(os.name=='nt','Windows picker process lifecycle')
class PickerLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.children=[]
        self.actual_popen=subprocess.Popen
        with picker._state_lock:
            self.assertIsNone(picker._pending)
            picker._closing=False
        self.addCleanup(self.cleanup)

    def cleanup(self):
        
        for child in self.children:
            if child.poll() is None:child.terminate()
            child.communicate(timeout=5)
        with picker._state_lock:
            self.assertIsNone(picker._pending)
            picker._closing=False
        self.assertFalse(picker._active.locked())

    def launch(self,script,kwargs):
        child=self.actual_popen([sys.executable,'-B','-c',script],**kwargs)
        self.children.append(child)
        return child

    def wait_child(self):
        deadline=time.monotonic()+3
        while not self.children and time.monotonic()<deadline:time.sleep(.01)
        self.assertTrue(self.children,'isolated picker child started')
        return self.children[-1]

    def start_choose(self):
        result=[];errors=[]
        def work():
            try:result.append(picker.choose('rained'))
            except BaseException as error:errors.append(error)
        thread=threading.Thread(target=work)
        thread.start()
        return thread,result,errors

    def test_normal_choice_and_user_cancel_keep_desktop_behavior(self):
        for value in ('C:/Tools/Rained.exe',None):
            def spawn(args,**kwargs):
                self.assertEqual(kwargs['env']['MI_PATH_PICKER_NAME'],'Rained.exe')
                return self.launch('print('+repr(json.dumps(value))+')',kwargs)
            with patch.object(picker.subprocess,'Popen',side_effect=spawn):
                self.assertEqual(picker.choose('rained'),value)
            self.assertFalse(picker._closing)
            self.assertIsNone(picker._pending)

    def test_cancel_live_picker_reaps_only_owned_process(self):
        unrelated=self.launch('import threading;threading.Event().wait(60)',dict(stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW))
        before=len(self.children)
        with patch.object(picker.subprocess,'Popen',side_effect=lambda args,**kwargs:self.launch('import threading;threading.Event().wait(60)',kwargs)):
            thread,result,errors=self.start_choose()
            deadline=time.monotonic()+3
            while len(self.children)==before and time.monotonic()<deadline:time.sleep(.01)
            self.assertEqual(len(self.children),before+1)
            owned=self.children[-1];picker.cancel_pending();thread.join(3)
            self.assertFalse(thread.is_alive());self.assertEqual(errors,[]);self.assertEqual(result,[None])
            self.assertIsNotNone(owned.poll());self.assertTrue(owned.stdout.closed and owned.stderr.closed)
            self.assertIsNone(unrelated.poll())

    def test_cancel_during_process_creation_is_not_lost(self):
        started=threading.Event();publish=threading.Event()
        def spawn(args,**kwargs):
            child=self.launch('import threading;threading.Event().wait(60)',kwargs)
            started.set();self.assertTrue(publish.wait(3));return child
        with patch.object(picker.subprocess,'Popen',side_effect=spawn):
            thread,result,errors=self.start_choose()
            try:
                self.assertTrue(started.wait(3));self.assertIsNone(picker._pending.process)
                picker.cancel_pending();publish.set();thread.join(3)
                self.assertFalse(thread.is_alive());self.assertEqual(errors,[]);self.assertEqual(result,[None])
                self.assertIsNotNone(self.children[-1].poll())
            finally:publish.set();thread.join(3)

    def test_shutdown_before_choose_prevents_late_window(self):
        picker.cancel_pending()
        with patch.object(picker.subprocess,'Popen',side_effect=AssertionError('late picker launched')):
            self.assertIsNone(picker.choose('game'))

    def test_completed_choice_survives_shutdown_before_result_return(self):
        real_loads=json.loads
        def finish(value):
            self.assertIsNotNone(picker._pending.process.poll())
            picker.cancel_pending()
            return real_loads(value)
        with patch.object(picker.subprocess,'Popen',side_effect=lambda args,**kwargs:self.launch('print('+repr(json.dumps('C:/Tools/Rained.exe'))+')',kwargs)),patch.object(picker.json,'loads',side_effect=finish):
            self.assertEqual(picker.choose('rained'),'C:/Tools/Rained.exe')

    def test_busy_picker_still_reports_busy_without_second_child(self):
        with patch.object(picker.subprocess,'Popen',side_effect=lambda args,**kwargs:self.launch('import threading;threading.Event().wait(60)',kwargs)):
            thread,result,errors=self.start_choose();self.wait_child()
            try:
                with self.assertRaises(picker.PickerError) as caught:picker.choose('game')
                self.assertEqual(caught.exception.code,'paths.pickerBusy');self.assertEqual(len(self.children),1)
            finally:picker.cancel_pending();thread.join(3)
            self.assertEqual(result,[None]);self.assertEqual(errors,[])

    def test_timeout_terminates_and_reaps_child_with_original_error_code(self):
        with patch.object(picker,'_TIMEOUT_SECONDS',.15),patch.object(picker.subprocess,'Popen',side_effect=lambda args,**kwargs:self.launch('import threading;threading.Event().wait(60)',kwargs)):
            with self.assertRaises(picker.PickerError) as caught:picker.choose('game')
            self.assertEqual(caught.exception.code,'paths.pickerTimeout')
        self.assertIsNotNone(self.children[0].poll());self.assertTrue(self.children[0].stdout.closed)

    def test_spawn_failure_and_malformed_output_keep_failure_code_and_unlock(self):
        with patch.object(picker.subprocess,'Popen',side_effect=OSError('injected launch failure')):
            with self.assertRaises(picker.PickerError) as caught:picker.choose('game')
            self.assertEqual(caught.exception.code,'paths.pickerFailed')
        for script in ('print("not-json")','import sys;print("failure",file=sys.stderr);sys.exit(2)'):
            with patch.object(picker.subprocess,'Popen',side_effect=lambda args,**kwargs:self.launch(script,kwargs)):
                with self.assertRaises(picker.PickerError) as caught:picker.choose('game')
                self.assertEqual(caught.exception.code,'paths.pickerFailed')
            self.assertFalse(picker._active.locked())


if __name__=='__main__':unittest.main()
