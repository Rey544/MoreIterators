"""Editable paint stacks. Hardware surfaces remain separate runtime materials."""
import base64
import io
import math

from PIL import Image

MAX_LAYERS = 32

def hardware(key):
    return key.startswith(('antenna', 'ear'))

def surface(layer, index, layers):
    if layer.get('surface') in ('inner', 'outer'):
        return layer['surface']
    # Old four-layer hardware was composited entirely into the inner material.
    return 'inner' if len(layers) == 4 or index == 0 else 'outer'

def select_surface(texture, outer):
    layers = texture.get('layers', [])
    wanted = 'outer' if outer else 'inner'
    return [layer for index, layer in enumerate(layers) if surface(layer, index, layers) == wanted]

def validate(texture, key):
    if not isinstance(texture, dict):
        raise ValueError('贴图格式错误')
    layers = texture.get('layers')
    if not isinstance(layers, list) or not 1 <= len(layers) <= MAX_LAYERS:
        raise ValueError('每张贴图需要 1–32 个图层')
    if 'symmetry' in texture and type(texture['symmetry']) is not bool:
        raise ValueError('贴图对称开关格式错误')
    seen = set()
    for index, layer in enumerate(layers):
        if not isinstance(layer, dict):
            raise ValueError('图层格式错误')
        for key_bool in ('visible', 'locked', 'clipToBelow'):
            if key_bool in layer and type(layer[key_bool]) is not bool:
                raise ValueError('图层显示与锁定必须为开启或关闭')
        opacity = layer.get('opacity', 1)
        if type(opacity) not in (float, int) or not math.isfinite(opacity) or not 0 <= opacity <= 1:
            raise ValueError('图层透明度超出范围')
        if not isinstance(layer.get('name', ''), str) or len(layer.get('name', '')) > 120:
            raise ValueError('图层名称最长为 120 个字')
        if not isinstance(layer.get('png', ''), str):
            raise ValueError('图层图片格式错误')
        identity = layer.get('id')
        if identity is not None:
            if not isinstance(identity, str) or not identity or len(identity) > 80 or identity in seen:
                raise ValueError('图层编号重复或格式错误')
            seen.add(identity)
        if hardware(key):
            if 'surface' in layer and layer['surface'] not in ('inner', 'outer'):
                raise ValueError('天线图层请选择前层或后层')
    return texture


def groups(layers):
    result = []
    for index, layer in enumerate(layers):
        if layer.get('clipToBelow', False) and result:
            result[-1].append(index)
        else:
            result.append([index])
    return result


def _image(layer, size):
    result = Image.new('RGBA', size)
    if layer.get('visible', True) is False or not layer.get('png'):
        return result
    result = Image.open(io.BytesIO(base64.b64decode(layer['png'].split(',', 1)[1]))).convert('RGBA')
    if result.size != tuple(size):
        raise ValueError('图层图片尺寸错误')
    result.putalpha(result.getchannel('A').point(lambda value: round(value * layer.get('opacity', 1))))
    return result


def _group(layers, size, indices, raw_base=None):
    first = indices[0]
    result = raw_base.copy() if first == 0 and raw_base is not None else _image(layers[first], size)
    alpha = result.getchannel('A')
    for index in indices[1:]:
        source = _image(layers[index], size)
        
        result = Image.composite(source, result, source.getchannel('A'))
        result.putalpha(alpha)
    return result


def compose(texture, size):
    layers = texture.get('layers', [])
    result = Image.new('RGBA', size)
    for indices in groups(layers):
        result = Image.alpha_composite(result, _group(layers, size, indices))
    return result


def split(texture, size, raw_base):
    
    layers = texture.get('layers', [])
    stacks = groups(layers)
    base = _group(layers, size, stacks[0], raw_base) if stacks else raw_base.copy()
    overlay = Image.new('RGBA', size)
    for indices in stacks[1:]:
        overlay = Image.alpha_composite(overlay, _group(layers, size, indices))
    return base, overlay


def overlay_texture(texture):
    
    layers = texture.get('layers', [])
    stacks = groups(layers)
    return {'layers': layers[len(stacks[0]):] if stacks else []}
