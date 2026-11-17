"""Capture the frozen page using disposable project and game roots."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.parse
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_room_identity_workflow as fixture

SOURCE = Path(__file__).resolve().parents[1]
WORK = SOURCE.parent.parent
CANDIDATE = WORK / 'mi-041/candidate/MoreIterators'
OUT = WORK / 'mi-041/evidence/room-ux-final-comparison'
OUT.mkdir(parents=True, exist_ok=True)
fixture.ROOT = CANDIDATE
case = fixture.RoomIdentityWorkflowTests()
try:
    case.setUp()
    project = next(row for row in case.request('/api/projects') if row['name'] == 'PL workflow fixture')
    pid = project['projectId']
    binding = case.request('/api/room-binding?' + urllib.parse.urlencode({'projectId': pid}))['binding']
    requested = dict(binding, region='PL', ai='PL_AI', entry='PL_POOL')
    plan = case.request('/api/room-binding/preview', dict(projectId=pid, binding=requested))
    case.request('/api/room-binding/apply', dict(projectId=pid, binding=requested, token=plan['token']))
    document = json.loads((case.data / 'projects' / pid / 'project.json').read_text('utf-8'))
    document['name'] = 'PL'
    case.request('/api/save', document)
    run = subprocess.run([shutil.which('node') or 'C:/Program Files/node.exe', str(Path(__file__).with_name('capture_room_ux_baseline.mjs')), 'C:/Program Files/Google/Chrome/Application/chrome.exe', case.base, str(case.folder / 'baseline-profile'), str(OUT)], capture_output=True, encoding='utf-8', timeout=60)
    if run.returncode:
        raise RuntimeError(run.stderr)
    print(run.stdout)
    (OUT / 'baseline-result.json').write_text(run.stdout, 'utf-8')
finally:
    case.doCleanups()
