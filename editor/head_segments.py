"""Independent rigid head pieces; existing upper antenna and ear data stay unchanged."""
import base64
import math

MATERIAL_PREFIXES = ('antenna', 'antennaLower', 'ear', 'earDecoration')
MATERIAL_MODES = ('', 'original', 'solid', 'gradient')
MATERIAL_DIRECTIONS = ('vertical', 'vertical-reverse', 'horizontal', 'horizontal-reverse')

TEXTURES = {'antennaLowerL': (24, 48), 'antennaLowerR': (24, 48),
            'earDecorationL': (24, 32), 'earDecorationR': (24, 32)}
DEFAULTS = {'antennaUpperEnabled': True, 'earBodyEnabled': True}
LIMITS = {'antennaHeight': (3, 80), 'antennaWidth': (.3, 8),
          'antennaSpread': (0, 40), 'antennaOffsetY': (-40, 80),
          'earWidth': (1, 24), 'earHeight': (2, 40),
          'earOffsetX': (-8, 40), 'earOffsetY': (-80, 80)}
for _prefix, _width, _height, _spread, _y in (
        ('antennaLower', 2.4, 10, 8.2, 0), ('earDecoration', 3, 10, 8, -9)):
    DEFAULTS.update({_prefix+'Enabled': False, _prefix+'Custom': False,
                     _prefix+'Tint': False, _prefix+'Color': '#334542',
                     _prefix+'InnerColor': '#9cafaa', _prefix+'OuterColor': '#323e3d',
                     _prefix+'Width': _width, _prefix+'Height': _height,
                     _prefix+'Spread': _spread, _prefix+'OffsetY': _y})
    LIMITS.update({_prefix+'Width': (.2, 24), _prefix+'Height': (.2, 40),
                   _prefix+'Spread': (0, 40), _prefix+'OffsetY': (-80, 40)})


def prefix(key):
    if key.startswith('antennaLower'):
        return 'antennaLower'
    if key.startswith('earDecoration'):
        return 'earDecoration'
    return 'ear' if key.startswith('ear') else 'antenna'


def defaults(design):
    for key, value in DEFAULTS.items():
        design.setdefault(key, value)
    for part in MATERIAL_PREFIXES:
        for layer in ('Inner', 'Outer'):
            design.setdefault(part+layer+'Mode', '')
            design.setdefault(part+layer+'EndColor', design.get(part+layer+'Color', '#9cafaa' if layer == 'Inner' else '#323e3d'))
            design.setdefault(part+layer+'Direction', 'vertical')


def validate(design):
    defaults(design)
    for part in MATERIAL_PREFIXES:
        for layer in ('Inner', 'Outer'):
            if design[part+layer+'Mode'] not in MATERIAL_MODES:
                raise ValueError(part+layer+'Mode is not a supported material mode')
            if design[part+layer+'Direction'] not in MATERIAL_DIRECTIONS:
                raise ValueError(part+layer+'Direction is not a supported gradient direction')
    for key, default in DEFAULTS.items():
        value = design[key]
        if isinstance(default, bool) and type(value) is not bool:
            raise ValueError(key+' must be true or false')
        if key in LIMITS:
            lo, hi = LIMITS[key]
            if type(value) not in (int, float) or not math.isfinite(value) or not lo <= value <= hi:
                raise ValueError(key+' is outside the supported range')


def recolor_layer(design, key, index, image):
    """Bake RGB through the original alpha mask; never change the author's source PNG."""
    part = prefix(key)
    layer = 'Inner' if index == 0 else 'Outer'
    mode = design.get(part+layer+'Mode') or ('solid' if design.get(part+'Tint', False) else 'original')
    if mode == 'original':
        return image
    if mode not in MATERIAL_MODES:
        raise ValueError(part+layer+'Mode is not a supported material mode')
    def rgb(value):
        return tuple(int(value[i:i+2], 16) for i in (1, 3, 5))
    start = rgb(design.get(part+layer+'Color', '#9cafaa' if index == 0 else '#323e3d'))
    end = rgb(design.get(part+layer+'EndColor', design.get(part+layer+'Color', '#9cafaa' if index == 0 else '#323e3d')))
    direction = design.get(part+layer+'Direction', 'vertical')
    if direction not in MATERIAL_DIRECTIONS:
        raise ValueError(part+layer+'Direction is not a supported gradient direction')
    result = image.convert('RGBA').copy()
    pixels = result.load()
    horizontal = direction.startswith('horizontal')
    extent = result.width if horizontal else result.height
    for y in range(result.height):
        for x in range(result.width):
            t = (x if horizontal else y) / max(1, extent-1)
            if direction.endswith('-reverse'):
                t = 1-t
            if mode == 'solid':
                t = 0
            color = tuple(int(a+(b-a)*t+.5) for a, b in zip(start, end))
            pixels[x, y] = color+(pixels[x, y][3],)
    return result


def compile_textures(project, design, antenna_layer, pngbytes):
    defaults(design)
    for key in TEXTURES:
        side = 'Left' if key.endswith('L') else 'Right'
        for index, suffix in ((0, 'InnerPng'), (1, 'Png')):
            image = antenna_layer(project, key, index)
            design[prefix(key)+side+suffix] = (
                'data:image/png;base64,'+base64.b64encode(pngbytes(image)).decode()
                if image.getchannel('A').getbbox() else '')
