"""Translate only text being created, with a language scoped to one request."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from urllib.parse import parse_qs, urlsplit
import localization

_language = ContextVar('mi_default_text_language', default=None)


def text(key):
    language = _language.get() or localization.language()
    return localization.catalog(language).get(key, localization.catalog('en').get(key, key))


@contextmanager
def use_language(value):
    token = _language.set(localization.normalize(value))
    try:
        yield
    finally:
        _language.reset(token)


def request_language(handler):
    @wraps(handler)
    def call(self, *args, **kwargs):
        headers = getattr(self, 'headers', {})
        value = headers.get('X-MI-Language')
        if not value:
            value = parse_qs(urlsplit(getattr(self, 'path', '')).query).get('lang', [''])[0]
        if not value:
            referer = urlsplit(headers.get('Referer', ''))
            if referer.netloc == headers.get('Host'):
                value = parse_qs(referer.query).get('lang', [''])[0]
        with use_language(value or localization.language()):
            return handler(self, *args, **kwargs)
    return call
