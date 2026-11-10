import json,os,shutil,socket,subprocess,sys,tempfile,time,unittest,urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=Path(os.environ.get('MI_CHAMBER_EVIDENCE',str(ROOT.parent/'evidence/room-workflow-20261109')))


class ChamberWorkflowBrowserTests(unittest.TestCase):
    def test_real_editor_cancel_switch_replace_and_create(self):
        chrome=shutil.which('chrome') or 'C:/Program Files/Google/Chrome/Application/chrome.exe'
        with tempfile.TemporaryDirectory(prefix='mi-chamber-browser-') as temporary:
            folder=Path(temporary);data=folder/'data';game=folder/'game';data.mkdir();game.mkdir()
            (game/'RainWorld.exe').write_bytes(b'fixture')
            with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            (data/'config.json').write_text(json.dumps({'studioPort':port,'gameRoot':str(game)}),'utf-8')
            env={**os.environ,'MORE_ITERATORS_DATA':str(data),'RAIN_WORLD_ROOT':str(game),'PYTHONDONTWRITEBYTECODE':'1'}
            boot="import sys;sys.path.insert(0,sys.argv[1]);import server,chamber_presets;chamber_presets.create({'presetId':'mi-chamber-pebbles','name':'Fixture A'},server);chamber_presets.create({'presetId':'mi-chamber-moon','name':'Fixture B'},server);server.server_lifecycle.EditorServer(('127.0.0.1',server.PORT),server.Handler).run()"
            with (folder/'server.log').open('w',encoding='utf-8') as log:
                process=subprocess.Popen([sys.executable,'-X','utf8','-B','-c',boot,str(ROOT/'editor')],env=env,stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                try:
                    base='http://127.0.0.1:'+str(port)
                    for _ in range(400):
                        try:
                            with urllib.request.urlopen(base+'/api/health',timeout=.5):break
                        except OSError:
                            if process.poll() is not None:self.fail((folder/'server.log').read_text('utf-8'))
                            time.sleep(.05)
                    EVIDENCE.mkdir(parents=True,exist_ok=True)
                    result=subprocess.run([shutil.which('node') or 'C:/Program Files/node.exe',str(Path(__file__).with_name('chamber_workflow_browser.mjs')),chrome,base,str(folder/'profile'),str(EVIDENCE)],capture_output=True,encoding='utf-8',timeout=150)
                    self.assertEqual(result.returncode,0,result.stderr[-7000:])
                    report=json.loads(result.stdout);self.assertTrue(report['ok'],report)
                    (EVIDENCE/'browser-workflow.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
                    print(json.dumps(report,ensure_ascii=False))
                finally:
                    process.terminate();process.wait(timeout=10)


if __name__=='__main__':unittest.main()
