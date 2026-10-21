"""Fixed vanilla-room bindings. Editable data stays local; game assets stay read-only."""
import colorsys

BINDINGS = {
    'lttm-spearmaster': dict(ai='DM_AI', entry='DM_MOONCHAMBER', oracleId='lttm_spear',
                           ownerMod='moreslugcats', timeline='Spear', nativeOracle='DM', previewOnly=True)
}

def binding(pid):
    value = BINDINGS.get(pid)
    return dict(value) if value else None

def moon_project(default):
    p = default()
    p.update(projectId='lttm-spearmaster', name='LTTM · 月姐（矛大师）', roomTemplate='native-dm')
    d = p['design']
    # OracleGraphics.SkinColor and Gown.Color for IsPastMoon.
    def gown(f):
        rgb = colorsys.hls_to_rgb(.08+(.02-.08)*f*f, .4, .6+(.4-.6)*f)
        return '#'+''.join(f'{round(c*255):02x}' for c in rgb)
    d.update(headColor='#2187b0', eyeColor='#0b1720', clothTopColor=gown(0),
             clothMiddleColor=gown(.58), clothBottomColor=gown(1), clothGrain=0,
             metalColor='#76828c', armColor='#afb4ba', armJointColor='#66768b',
             antennaColor='#a2b7e1', haloColor='#a3b9e7', rearGlowColor='#8296c2',
             cableColorA='#454959', cableColorB='#bec2c8', earWidth=4, earHeight=7,
             roomWorkColor='#5d6493', roomReceptionColor='#c59573', roomPalette=26,
             pearlColor2='#617da1', pearlColor3='#a7bdcc', pearlColor4='#d4cbd8',
             pearlGlyphColor='#bbc7dc', neckLength=2)
    d['layers'].update(antenna=False, collar=False)
    return p
