import room_bindings


def inspect(name, links, content, geometry_source, connection_source):
    count = None
    issues = []
    try:
        count = room_bindings.geometry(None, content=content)['exitCount']
    except (ValueError, OSError):
        issues.append(dict(code='geometryUnavailable', room=name))
    if count is not None and count != len(links):
        issues.append(dict(code='exitCountMismatch', room=name))
    for issue in issues:
        issue.update(actualExitCount=count, connectionSlotCount=len(links),
                     geometrySource=geometry_source, connectionSource=connection_source)
    return dict(actualExitCount=count, connectionSlotCount=len(links),
                geometrySource=geometry_source, connectionSource=connection_source,
                verified=not issues, issues=issues)


def require(check):
    if not check['issues']:return
    issue = check['issues'][0]
    if issue['code'] == 'geometryUnavailable':
        raise room_bindings.RoomBindingError('workflowGeometry', room=issue['room'])
    raise room_bindings.RoomBindingError('workflowGeometryDetails', room=issue['room'],
        actual=issue['actualExitCount'], slots=issue['connectionSlotCount'],
        geometrySource=issue['geometrySource'], connectionSource=issue['connectionSource'])


def connected(rows, first, second):
    graph = {row['name']: row['connections'] for row in rows}
    pending = [first]
    found = set()
    while pending:
        name = pending.pop()
        if name == second:return True
        if name in found:continue
        found.add(name)
        pending.extend(target for target in graph.get(name, []) if target != 'DISCONNECTED')
    return False
