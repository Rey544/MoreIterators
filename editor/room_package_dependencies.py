import math
import re


def region_filename(region, filename):
    if not isinstance(filename, str):return False
    return filename in ('properties.txt', 'displayname.txt', 'map_' + region.lower() + '.txt') or bool(
        re.fullmatch(re.escape(region.lower()) + r'_settingstemplate_[a-z0-9-]+\.txt', filename))


def template_files(region, properties):
    match = re.search(r'(?m)^Room Setting Templates:[ \t]*([^\r\n]*)', properties)
    if not match:
        return []
    names = [name.strip().lower() for name in match[1].split(',')]
    if not names or any(not re.fullmatch(r'[a-z0-9-]+', name) for name in names) or len(names) != len(set(names)):
        raise ValueError('房间模板列表无效：' + region)
    return [region.lower() + '_settingstemplate_' + name + '.txt' for name in names]


def parent_template(region, text, properties):
    files = template_files(region, properties)
    direct = re.search(r'(?m)^Template:[ \t]*([^\r\n]*)', text)
    if direct:
        name = direct[1].strip()
        if name.upper() == 'NONE':
            return None
        match = re.fullmatch(r'[A-Za-z0-9]+_settingstemplate_([A-Za-z0-9-]+)', name, re.I)
        if not match:
            raise ValueError('房间模板名称无效：' + name)
        if match[1].lower() == 'first':return files[0] if files else None
        filename = region.lower() + '_settingstemplate_' + match[1].lower() + '.txt'
        return filename if filename in files else None
    return files[0] if files else None


def sky_enabled(text, inherited=''):
    for effect in ('AboveCloudsView', 'PinkSky'):
        pattern = r'(?:^|,\s*)' + effect + r'-(-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)-'
        direct = []
        for line in re.findall(r'(?m)^Effects:[ \t]*([^\r\n]*)', text):
            direct.extend(re.findall(pattern, line))
        source = text if direct else inherited
        for line in re.findall(r'(?m)^Effects:[ \t]*([^\r\n]*)', source):
            for raw in re.findall(pattern, line):
                try:
                    value = float(raw)
                except ValueError as error:
                    raise ValueError('天空远景参数无效') from error
                if not math.isfinite(value):
                    raise ValueError('天空远景参数无效')
                if value > 0:
                    return True
    return False


def map_positions(text, names):
    result = {}
    for line in text.splitlines():
        name, separator, value = line.partition(':')
        name = name.strip().upper()
        if not separator or name not in names:
            continue
        if name in result:
            raise ValueError('房间地图坐标重复：' + name)
        try:
            values = value.strip().split('><')
            x, y = float(values[0]), float(values[1])
            if not math.isfinite(x) or not math.isfinite(y):
                raise ValueError()
            if len(values) >= 5:
                int(values[4])
        except (ValueError, IndexError) as error:
            raise ValueError('房间地图坐标无效：' + name) from error
        result[name] = (x, y)
    return result


def validate_room(region, name, settings, region_files, label):
    properties = region_files.get('properties.txt', '')
    active = False
    for filename, text in settings.items():
        if '_settings' not in filename:
            continue
        try:
            template = parent_template(region, text, properties)
            if template and template not in region_files:
                raise ValueError('缺少房间模板：' + template)
            if not sky_enabled(text, region_files.get(template, '') if template else ''):
                continue
            active = True
            map_name = 'map_' + region.lower() + '.txt'
            map_positions(region_files.get(map_name, ''), {name})
        except ValueError as error:
            raise ValueError('房间 ' + name + '（' + filename + '，' + label(filename) + '）：' + str(error)) from error
    return active


def require_sky_rooms(region, name, available_rooms, label):
    if region != 'OE' and not name.startswith('OE_'):return
    missing = sorted({'GATE_SB_OE', 'OE_RUIN02'} - set(available_rooms))
    if missing:raise ValueError('房间 ' + name + '（' + label + '）的天空远景缺少参照房间：' + '、'.join(missing))


def background(value, name, size):
    required = {'schema', 'room', 'sourceRegion', 'size', 'mapPosition'}
    if not isinstance(value, dict) or not required.issubset(value) or set(value) - required - {'mapFingerprint'}:
        raise ValueError('房间背景坐标格式无效：' + name)
    if value['schema'] != 'moreiterators.background-coordinates.v1' or value['room'] != name:
        raise ValueError('房间背景坐标编号不符：' + name)
    if not isinstance(value['sourceRegion'], str) or not re.fullmatch(r'[A-Z][A-Z0-9]{1,7}', value['sourceRegion']):
        raise ValueError('房间背景来源区域无效：' + name)
    if value['size'] != list(size) or any(type(number) is not int for number in value['size']):
        raise ValueError('房间背景坐标与房间尺寸不符：' + name)
    position = value['mapPosition']
    if not isinstance(position, list) or len(position) != 2 or any(type(number) not in (int, float) or not math.isfinite(number) or abs(number) > 10000000 for number in position):
        raise ValueError('房间背景坐标无效：' + name)
    if 'mapFingerprint' in value and (not isinstance(value['mapFingerprint'], str) or not re.fullmatch(r'[a-f0-9]{64}', value['mapFingerprint'])):
        raise ValueError('房间背景坐标校验无效：' + name)
    return value
