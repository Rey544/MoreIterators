"""Apply the shipped appearance only when creating a new project."""
import copy
import json
from pathlib import Path
import paint_layers


def create(base):
    template=json.loads((Path(__file__).resolve().parents[1]/'templates/default-project.json').read_text('utf-8-sig'))
    result=copy.deepcopy(base)
    result['design'].update(copy.deepcopy(template['design']))
    result['textures']=copy.deepcopy(template.get('textures',{}))
    # Only new projects receive four layers. Resolve old material assignments
    # before extending a two-layer hardware stack: legacy four-layer stacks
    # otherwise mean that every layer belongs to the back material.
    for key,texture in result['textures'].items():
        layers=texture.get('layers',[])
        if paint_layers.hardware(key):
            surfaces=[paint_layers.surface(layer,index,layers) for index,layer in enumerate(layers)]
            for layer,surface in zip(layers,surfaces):layer['surface']=surface
        while len(layers)<4:
            layer=dict(name='纹理 '+str(len(layers)),png='',visible=True,locked=False,opacity=1)
            if paint_layers.hardware(key):layer['surface']='outer'
            layers.append(layer)
    return result
