import ast
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / 'editor'


def sample(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return sample(node.left) + sample(node.right)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id == 'str' and node.args and isinstance(node.args[0], ast.Name) and node.args[0].id == 'error':
            return '天空远景参数无效'
        if node.func.id in ('_dependency_origin', 'label'):
            return '本地模组/world/test/TEST_A_settings.txt'
    return 'TEST_SAMPLE'


class ExportErrors(unittest.TestCase):
    def test_backend_error_catalog_coverage(self):
        zh = json.loads((ROOT / 'locales/zh-CN.json').read_text('utf-8'))
        en = json.loads((ROOT / 'locales/en.json').read_text('utf-8'))
        patterns = []
        for key, value in zh.items():
            expression = re.escape(value)
            expression = re.sub(r'\\\{[A-Za-z][A-Za-z0-9_]*\\\}', lambda match: r'[\s\S]*?', expression)
            patterns.append((re.compile('^' + expression + '$'), key))
        missing = []
        for filename in ('project_bundles.py', 'room_package_dependencies.py', 'project_packages.py'):
            tree = ast.parse((ROOT / filename).read_text('utf-8-sig'))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Raise) or not isinstance(node.exc, ast.Call) or not node.exc.args:
                    continue
                message = sample(node.exc.args[0])
                if not re.search(r'[\u3400-\u9fff]', message):
                    continue
                keys = [key for pattern, key in patterns if pattern.fullmatch(message)]
                if not keys or not any(en.get(key) and not re.search(r'[\u3400-\u9fff]', en[key]) for key in keys):
                    missing.append(f'{filename}:{node.lineno}: {message}')
        self.assertEqual(missing, [])


if __name__ == '__main__':
    unittest.main()
