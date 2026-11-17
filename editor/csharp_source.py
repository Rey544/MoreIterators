from dataclasses import dataclass
import json
import re


class SourceError(ValueError):
    pass


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    start: int
    end: int


def tokens(source):
    result = []
    index = 0
    while index < len(source):
        start = index
        char = source[index]
        if char.isspace() or char == '\ufeff':
            index += 1
            continue
        if source.startswith('//', index):
            end = source.find('\n', index + 2)
            index = len(source) if end < 0 else end + 1
            continue
        if source.startswith('/*', index):
            end = source.find('*/', index + 2)
            if end < 0:
                raise SourceError('Unclosed C# comment at offset '+str(index))
            index = end + 2
            continue
        if source.startswith(('$"', '$@"', '@$"', '"""'), index):
            raise SourceError('Unsupported C# string syntax at offset '+str(index))
        verbatim = source.startswith('@"', index)
        if char in ('"', "'") or verbatim:
            quote = '"' if verbatim else char
            index += 2 if verbatim else 1
            while index < len(source):
                if source[index] == quote:
                    if verbatim and source.startswith('""', index):
                        index += 2
                        continue
                    index += 1
                    break
                if not verbatim and source[index] == '\\':
                    index += 2
                elif not verbatim and source[index] in '\r\n':
                    raise SourceError('Newline in C# literal at offset '+str(start))
                else:
                    index += 1
            else:
                raise SourceError('Unclosed C# literal at offset '+str(start))
            if index > len(source):
                raise SourceError('Unclosed C# literal at offset '+str(start))
            kind = 'string' if quote == '"' else 'character'
        elif char == '#':
            end = source.find('\n', index)
            index = len(source) if end < 0 else end
            kind = 'directive'
        elif char.isalpha() or char == '_' or char == '@':
            index += 1
            while index < len(source) and (source[index].isalnum() or source[index] == '_'):
                index += 1
            kind = 'identifier'
        else:
            index += 1
            kind = 'symbol'
        result.append(Token(kind, source[start:index], start, index))
    return result


def _unique(matches, label):
    if len(matches) != 1:
        raise SourceError(label+': expected one match, found '+str(len(matches)))
    return matches[0]


def _matching(items, start):
    pairs = {'(': ')', '[': ']', '{': '}'}
    stack = []
    for index in range(start, len(items)):
        token = items[index]
        if token.kind != 'symbol':
            continue
        if token.value in pairs:
            stack.append(pairs[token.value])
        elif token.value in pairs.values():
            if not stack or token.value != stack.pop():
                raise SourceError('Mismatched C# delimiter at offset '+str(token.start))
            if not stack:
                return index
    raise SourceError('Unclosed C# delimiter at offset '+str(items[start].start))


def _edits(source, edits):
    last = len(source)
    for start, end, replacement in sorted(edits, reverse=True):
        if not 0 <= start <= end <= last:
            raise SourceError('Overlapping C# source replacements')
        source = source[:start]+replacement+source[end:]
        last = start
    return source


def extract_class(source, name):
    items = tokens(source)
    candidates = [index for index in range(len(items)-1)
                  if items[index].value == 'class' and items[index+1].kind == 'identifier' and items[index+1].value == name]
    index = _unique(candidates, 'C# class '+name)
    start = index
    modifiers = {'public', 'internal', 'private', 'protected', 'static', 'sealed', 'abstract', 'partial'}
    while start and items[start-1].kind == 'identifier' and items[start-1].value in modifiers:
        start -= 1
    body = index + 2
    while body < len(items) and items[body].value != '{':
        if items[body].value in (';', '}'):
            raise SourceError('Missing C# class body: '+name)
        body += 1
    if body == len(items):
        raise SourceError('Missing C# class body: '+name)
    end = _matching(items, body)
    return source[items[start].start:items[end].end]


def replace_identifier(source, name, replacement, required=False):
    found = [token for token in tokens(source) if token.kind == 'identifier' and token.value == name]
    if required or found:
        token = _unique(found, 'C# placeholder '+name)
        return _edits(source, [(token.start, token.end, replacement)])
    return source


def replace_namespace(source, name, replacement):
    items = tokens(source)
    found = []
    for index in range(len(items)-2):
        if items[index].kind == 'identifier' and items[index].value == 'namespace' and items[index+1].kind == 'identifier' and items[index+1].value == name:
            if items[index+2].value != '{':
                raise SourceError('Unsupported namespace declaration: '+name)
            found.append(items[index+1])
    token = _unique(found, 'C# namespace '+name)
    return _edits(source, [(token.start, token.end, replacement)])


def replace_code(source, pattern, replacement, label):
    items = tokens(source)
    expected = [(item.kind, item.value) for item in tokens(pattern)]
    if not expected:
        raise SourceError('Empty C# token pattern: '+label)
    found = []
    for index in range(len(items)-len(expected)+1):
        if index and items[index-1].value in ('.', ':'):
            continue
        if [(item.kind, item.value) for item in items[index:index+len(expected)]] == expected:
            found.append((items[index].start, items[index+len(expected)-1].end, replacement))
    return _edits(source, [_unique(found, label)])


def _string_value(token):
    if token.kind != 'string':
        raise SourceError('Expected C# string literal')
    if token.value.startswith('@"'):
        return token.value[2:-1].replace('""', '"')
    value = token.value[1:-1]
    escapes = {'0':'\0', 'a':'\a', 'b':'\b', 'f':'\f', 'n':'\n', 'r':'\r', 't':'\t', 'v':'\v', '\\':'\\', '"':'"', "'":"'"}
    def decode(match):
        escape = match.group(1)
        if escape in escapes:
            return escapes[escape]
        if escape[0] in 'xuU':
            return chr(int(escape[1:], 16))
        raise SourceError('Unsupported C# string escape: '+escape)
    return re.sub(r'\\(u[0-9a-fA-F]{4}|U[0-9a-fA-F]{8}|x[0-9a-fA-F]{1,4}|.)', decode, value)


def replace_plugin_identity(source, identifier, name, version):
    items = tokens(source)
    found = [index for index in range(len(items)-2)
             if [item.value for item in items[index:index+3]] == ['[', 'BepInPlugin', '(']]
    index = _unique(found, 'Playback plugin attribute')
    end = _matching(items, index+2)
    if end+1 >= len(items) or items[end+1].value != ']':
        raise SourceError('Unexpected playback plugin attribute boundary')
    arguments = items[index+3:end]
    if len(arguments) != 7 or arguments[1].value != ',' or arguments[3].value != ',' or [item.value for item in arguments[4:]] != ['BuildVersion', '.', 'Plugin']:
        raise SourceError('Unexpected playback plugin arguments')
    if _string_value(arguments[0]) != 'moreiterators.core' or arguments[2].kind != 'string':
        raise SourceError('Unexpected playback plugin identity')
    replacement = json.dumps(identifier)+', '+json.dumps(name,ensure_ascii=False)+', '+json.dumps(version)
    return _edits(source, [(arguments[0].start, arguments[-1].end, replacement)])


def replace_string_resources(source, replacements=(), prefixes=(), placeholder=None):
    edits = []
    placeholders = 0
    for token in tokens(source):
        if token.kind != 'string':
            continue
        begin = 2 if token.value.startswith('@"') else 1
        content = token.value[begin:-1]
        if placeholder is not None and placeholder[0] in content:
            placeholders += content.count(placeholder[0])
            content = content.replace(*placeholder)
        for old, new in prefixes:
            if content.startswith(old):
                content = new+content[len(old):]
                break
        for old, new in replacements:
            content = content.replace(old, new)
        if content != token.value[begin:-1]:
            edits.append((token.start+begin, token.end-1, content))
    if placeholder is not None and placeholders != 1:
        raise SourceError('C# string placeholder '+placeholder[0]+': expected one match, found '+str(placeholders))
    return _edits(source, edits)
