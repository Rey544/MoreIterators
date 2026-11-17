import ast
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import urllib.parse

EDITOR = Path(__file__).resolve().parents[1] / 'editor'
sys.path.insert(0, str(EDITOR))
import diagnostics
import storage


class EditorLogExportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.archive = self.root / 'custom-archive'
        self.game = self.root / 'game'
        self.project = self.root / 'data/projects/retained/project.json'
        self.project.parent.mkdir(parents=True)
        self.project.write_text('{"name":"private work"}', 'utf-8')
        self.original = self.project.read_bytes()
        self.patches = [patch.object(storage, 'GAME', self.game), patch.object(storage, 'DATA', self.root/'data'),
                        patch.object(storage, 'archive_root', return_value=self.archive)]
        for item in self.patches:
            item.start()

    def tearDown(self):
        self.assertEqual(self.project.read_bytes(), self.original)
        for item in reversed(self.patches):
            item.stop()
        self.temporary.cleanup()

    def write_editor_log(self, data):
        path = self.archive / 'logs/studio-errors.log'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def test_editor_log_uses_custom_archive_without_game(self):
        original = 'operation=/api/project-package-rooms\nTraceback:\n  at 房间\nValueError: missing exits\n'.encode()
        path = self.write_editor_log(original)
        with patch.object(storage, 'GAME', Path('.')):
            result = diagnostics.snapshot('editor')
            self.assertFalse(diagnostics.snapshot()['available'])
            stream, filename, details = diagnostics.open_download('editor')
            with stream:
                self.assertEqual(stream.read(), original)
        self.assertEqual(filename, 'studio-errors.log')
        self.assertEqual(result['logPath'], str(path))
        self.assertEqual(result['tail'], original.decode())
        self.assertEqual(result['downloadName'], filename)
        self.assertEqual(details.st_size, len(original))
        self.assertFalse(self.game.exists())
        self.assertEqual(path.read_bytes(), original)

    def test_full_download_includes_entries_outside_preview_tail(self):
        original = ('FIRST IMPORTANT ERROR\n' + '历史错误\n'*30000 + 'LAST ERROR\n').encode()
        self.write_editor_log(original)
        preview = diagnostics.snapshot('editor')
        self.assertTrue(preview['truncated'])
        self.assertNotIn('FIRST IMPORTANT ERROR', preview['tail'])
        self.assertIn('LAST ERROR', preview['tail'])
        stream, filename, details = diagnostics.open_download('editor')
        with stream:
            downloaded = stream.read()
        self.assertEqual(hashlib.sha256(downloaded).digest(), hashlib.sha256(original).digest())

    def test_missing_and_empty_logs_never_create_error_files(self):
        self.assertFalse(diagnostics.snapshot('editor')['available'])
        with self.assertRaises(diagnostics.DiagnosticLogError) as missing:
            diagnostics.open_download('editor')
        self.assertEqual(missing.exception.status, 404)
        self.assertFalse(self.archive.exists())
        path = self.write_editor_log(b'')
        self.assertFalse(diagnostics.snapshot('editor')['available'])
        with self.assertRaises(diagnostics.DiagnosticLogError):
            diagnostics.open_download('editor')
        self.assertEqual(path.read_bytes(), b'')

    def test_long_single_line_log_remains_available(self):
        original = b'first error ' + b'x'*200000
        self.write_editor_log(original)
        result = diagnostics.snapshot('editor')
        self.assertTrue(result['available'])
        self.assertTrue(result['truncated'])
        self.assertEqual(len(result['tail']), diagnostics.MAX_LOG_BYTES)
        stream, name, details = diagnostics.open_download('editor')
        with stream:
            self.assertEqual(stream.read(), original)

    def test_source_cannot_address_project_or_arbitrary_file(self):
        for source in ('', '../projects/retained/project.json', str(self.project), 'startup', 'Editor'):
            with self.subTest(source=source), self.assertRaises(diagnostics.DiagnosticLogError):
                diagnostics.open_download(source)
        self.assertFalse(self.archive.exists())

    def test_snapshot_ignores_entries_appended_after_read_size(self):
        original = b'original error\n'
        path = self.write_editor_log(original)
        stream, name, details = diagnostics.open_download('editor')
        with path.open('ab') as target:
            target.write(b'later error\n')
        with stream:
            self.assertEqual(stream.read(details.st_size), original)
        self.assertIn('later error', diagnostics.snapshot('editor')['tail'])

    def test_game_download_keeps_original_fallback_file_and_full_content(self):
        path = self.game / 'BepInEx/LogOutput.txt'
        path.parent.mkdir(parents=True)
        original = b'game start\n' + b'other mod log\n'*20000
        path.write_bytes(original)
        stream, name, details = diagnostics.open_download()
        with stream:
            self.assertEqual(stream.read(), original)
        self.assertEqual(name, 'LogOutput.txt')
        self.assertEqual(details.st_size, len(original))
        self.assertFalse(self.archive.exists())

    def test_production_http_preview_download_missing_and_invalid_source(self):
        tree = ast.parse((EDITOR / 'server.py').read_text('utf-8-sig'))
        handler = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Handler')
        context = dict(BaseHTTPRequestHandler=BaseHTTPRequestHandler, default_text=SimpleNamespace(request_language=lambda fn: fn),
                       server_lifecycle=SimpleNamespace(request=lambda fn: fn), diagnostics=diagnostics,
                       urllib=__import__('urllib'), json=json, os=os, Path=Path, ROOT=EDITOR)
        exec(compile(ast.Module(body=[handler], type_ignores=[]), 'server.py', 'exec'), context)
        server = ThreadingHTTPServer(('127.0.0.1', 0), context['Handler'])
        context['PORT'] = server.server_port
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        def get(path):
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
            try:
                connection.request('GET', path)
                response = connection.getresponse()
                return response.status, dict(response.getheaders()), response.read()
            finally:
                connection.close()
        try:
            status, headers, body = get('/api/diagnostics?source=editor')
            self.assertEqual(status, 200)
            self.assertFalse(json.loads(body)['available'])
            status, headers, body = get('/api/diagnostics/download?source=editor')
            self.assertEqual(status, 404)
            self.assertEqual(json.loads(body)['code'], 'diagnostics.editorUnavailable')
            self.assertFalse(self.archive.exists())
            for query in ('source=../data/config.json', 'source=', 'source=editor&source=game'):
                status, headers, body = get('/api/diagnostics/download?' + query)
                self.assertEqual(status, 400)
                self.assertEqual(json.loads(body)['code'], 'diagnostics.invalidSource')
            original = ('FIRST\n' + '历史错误\n'*30000 + 'LAST\n').encode()
            path = self.write_editor_log(original)
            status, headers, body = get('/api/diagnostics/download?source=editor')
            self.assertEqual(status, 200)
            self.assertEqual(body, original)
            self.assertEqual(int(headers['Content-Length']), len(body))
            self.assertEqual(headers['Content-Disposition'], 'attachment; filename="studio-errors.log"')
            self.assertEqual(headers['Cache-Control'], 'no-store')
            self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')
            path.unlink()
            status, headers, body = get('/api/diagnostics/download?source=editor')
            self.assertEqual(status, 404)
            self.assertFalse(path.exists())
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
