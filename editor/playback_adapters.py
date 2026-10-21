"""Public playback builds use only the shared renderer."""
def export_sources(destination,projects,namespace):
    if any(p.get('legacyOracle') for p in projects):
        raise ValueError('This appearance requires its original author workspace; it is not included in the public tool package.')
    return []
