"""Shared UI resources for the desktop launcher and local web studios."""
import json
import locale
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent / 'locales'
_catalogs = {}
_language = None


def normalize(value):
    return 'zh-CN' if str(value or '').lower().startswith('zh') else 'en'


def set_language(value):
    global _language
    _language = normalize(value)


def language():
    return _language or normalize(os.environ.get('MORE_ITERATORS_LANGUAGE') or locale.getlocale()[0])


def catalog(code):
    if code not in _catalogs:
        try:
            with (ROOT / (code + '.json')).open(encoding='utf-8') as stream:
                _catalogs[code] = json.load(stream)
        except (OSError, ValueError) as error:
            _catalogs[code] = {}
            if sys.stderr:
                print('[MI i18n] ' + str(error), file=sys.stderr)
    return _catalogs[code]


def text(key, **params):
    value = catalog(language()).get(key, catalog('en').get(key, key))
    return value.format(**params)
