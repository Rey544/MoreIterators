
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'editor'))
from csharp_source import SourceError, _matching, extract_class, replace_code, replace_namespace, tokens


def _location(source, pattern):
    items = tokens(source)
    expected = [(item.kind, item.value) for item in tokens(pattern)]
    if not expected:
        raise SourceError('Empty C# source marker')
    found = [index for index in range(len(items) - len(expected) + 1)
             if [(item.kind, item.value) for item in items[index:index + len(expected)]] == expected]
    if len(found) != 1:
        raise SourceError('C# source marker ' + pattern + ': expected one match, found ' + str(len(found)))
    return items, found[0], len(expected)


def code_index(source, pattern):
    items, index, _ = _location(source, pattern)
    return items[index].start


def before_code(source, pattern):
    return source[:code_index(source, pattern)]


def between_code(source, first, following):
    start = code_index(source, first)
    end = code_index(source, following)
    if end <= start:
        raise SourceError('C# source markers are out of order')
    return source[start:end]


def extract_block(source, marker, body_only=False):
    items, start, length = _location(source, marker)
    opening = start + length - 1
    while opening < len(items) and items[opening].value != '{':
        if items[opening].value in (';', '}'):
            raise SourceError('Missing C# block for ' + marker)
        opening += 1
    if opening == len(items):
        raise SourceError('Missing C# block for ' + marker)
    end = _matching(items, opening)
    return source[items[opening if body_only else start].start:items[end].end]


def extract_statements(source, marker, count=1):
    if count < 1:
        raise SourceError('Expected a positive C# statement count')
    items, start, _ = _location(source, marker)
    index = start
    while index < len(items):
        if items[index].value in ('(', '[', '{'):
            index = _matching(items, index)
        elif items[index].value == ';':
            count -= 1
            if not count:
                return source[items[start].start:items[index].end]
        elif items[index].value == '}':
            break
        index += 1
    raise SourceError('Missing C# statement terminator for ' + marker)

def with_dialogue_line(root,fixture):
    source=(root/'src/CreatorDialogue.cs').read_text('utf-8-sig')
    production=extract_block(source,'[Serializable] public sealed class CreatorDialogueLine')
    stub=extract_class(fixture,'CreatorDialogueLine')
    actual=[(item.kind,item.value) for item in tokens(stub)]
    expected=([ (item.kind,item.value) for item in tokens('public '+modifier+'class CreatorDialogueLine {public string text;}') ] for modifier in ('','sealed '))
    if actual not in expected:raise AssertionError('Expected exactly one dialogue-line host stub')
    return replace_code(fixture,stub,production,'dialogue-line host stub')
