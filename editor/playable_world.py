
from pathlib import Path
import re

import room_bindings

TIMELINE='White'
SECTIONS={'ROOMS','CONDITIONAL LINKS'}


def _error(message,region,line=''):
    raise ValueError(message+'：'+region+(' / '+line if line else ''))


def _prefix(line,relevant,region):
    if line.startswith('('):
        end=line.find(')')
        if end<0:_error('无法解析世界时间线条件',region,line)
        selector=line[1:end];negated=selector.startswith('X-')
        if negated:selector=selector[2:]
        names=[item.strip() for item in selector.split(',')]
        if not names or any(not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*',item) for item in names):
            _error('暂不支持此世界时间线条件',region,line)
        if (TIMELINE in names)==negated:return None
        line=line[end+1:].strip()
    if line.startswith('{'):
        end=line.find('}');tail=line[end+1:].strip() if end>=0 else ''
        if relevant or tail in SECTIONS or tail.startswith('END '):
            _error('无法离线确认房间的存档条件',region,line)
        return None
    if line.startswith('('):_error('无法解析重复的世界时间线条件',region,line)
    return line


def _name(value,region,line):
    if not isinstance(value,str) or not room_bindings.ROOM_RE.fullmatch(value):
        _error('世界房间编号无效',region,line)
    return value


def _region(stage,region):
    path=stage/'world'/region.lower()/('world_'+region.lower()+'.txt')
    text=path.read_text('utf-8-sig');section='';rows={};conditions=[];saw_rooms=False
    for raw in text.splitlines():
        line=raw.strip()
        if not line or line.startswith('//'):continue
        
        if section not in SECTIONS and line.startswith(('(','{')) and not any(token in line for token in SECTIONS):continue
        line=_prefix(line,section in SECTIONS,region)
        if line is None:continue
        if line in SECTIONS:
            if section:_error('世界文件区段未结束',region,line)
            section=line;saw_rooms|=line=='ROOMS';continue
        if line.startswith('END '):
            if section and line!='END '+section:_error('世界文件区段结束不匹配',region,line)
            section='';continue
        if not section:continue
        parts=line.split(' : ')
        if section=='ROOMS':
            if len(parts)<2:_error('无法解析房间连接',region,line)
            name=_name(parts[0],region,line)
            if name in rows:_error('当前时间线存在重复房间',region,name)
            links=[item.strip() for item in parts[1].split(',')] if parts[1] else []
            for target in links:
                if target!='DISCONNECTED':_name(target,region,line)
            tags=parts[2:]
            if any(not tag for tag in tags):_error('无法解析房间标签',region,line)
            rows[name]=dict(name=name,region=region,connections=links,tags=' : '.join(tags),hidden=False,replacement='')
        else:
            if len(parts)<2:_error('无法解析条件连接',region,line)
            conditions.append((parts,line))
    if section:_error('世界文件区段未结束',region,section)
    if not saw_rooms or not rows:_error('当前时间线没有可用房间',region)

    exclusive={};hidden=set();links=[]
    for parts,line in conditions:
        selectors=parts[0].split(',')
        if any(not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*',value) for value in selectors):
            _error('无法解析条件连接的时间线',region,line)
        active=TIMELINE in selectors;kind=parts[1]
        if kind in ('EXCLUSIVEROOM','HIDEROOM'):
            if len(parts)!=3:_error('无法解析隐藏房间条件',region,line)
            name=_name(parts[2],region,line)
            if kind=='EXCLUSIVEROOM':exclusive.setdefault(name,set()).update(selectors)
            elif active:hidden.add(name)
        elif kind=='REPLACEROOM':
            if len(parts)!=4:_error('无法解析替代房间条件',region,line)
            name=_name(parts[2],region,line);replacement=_name(parts[3],region,line)
            if active and name in rows:
                if rows[name]['replacement']:_error('同一房间有重复替代条件',region,line)
                rows[name]['replacement']=replacement
        elif active:
            if len(parts)!=4:_error('无法解析条件连接',region,line)
            name=_name(kind,region,line);target=parts[2];destination=parts[3]
            if not re.fullmatch(r'[+-]?\d+',target) and target!='DISCONNECTED':_name(target,region,line)
            if destination!='DISCONNECTED':_name(destination,region,line)
            links.append((name,target,destination))
    hidden.update(name for name,selectors in exclusive.items() if TIMELINE not in selectors)
    for name,row in rows.items():
        row['hidden']=name in hidden
        if row['hidden']:
            row['tags']=' : '.join(tag for tag in row['tags'].split(' : ') if tag not in ('SWARMROOM','SCAVOUTPOST','SCAVTRADER'))
        
        
        pending=[];connections=row['connections']
        for source,target,destination in links:
            if source!=name:continue
            if re.fullmatch(r'[+-]?\d+',target):
                index=int(target);empty=[i for i,value in enumerate(connections) if value=='DISCONNECTED']
                if 1<=index<=len(empty):pending.append((empty[index-1],destination))
            elif target in connections:connections[connections.index(target)]=destination
        for index,destination in pending:connections[index]=destination
        for destination in connections:
            if destination!='DISCONNECTED' and destination not in rows:
                _error('当前时间线连接到未加载的房间，不能确认可达',region,name+' -> '+destination)
    return list(rows.values())


def validate(stage,regions,start,required_rooms=()):
    stage=Path(stage)
    if not isinstance(regions,(list,tuple)) or not regions or any(not isinstance(region,str) or not room_bindings.REGION_RE.fullmatch(region) for region in regions) or len(set(regions))!=len(regions):
        raise ValueError('剧情地区清单无效')
    rows=[]
    for region in regions:rows.extend(_region(stage,region))
    by_name={row['name']:row for row in rows}
    if len(by_name)!=len(rows):raise ValueError('跨地区重复房间暂不能确认剧情可达性')
    if not isinstance(start,str) or start not in by_name:raise ValueError('起始房间未在 White 时间线加载')
    if start.startswith('GATE_') or 'GATE' in by_name[start]['tags'].split(' : ') or 'OFFSCREEN' in start:
        raise ValueError('起始房间不能是业力门或离屏房间')
    required=set(required_rooms)
    if not required.issubset(by_name):raise ValueError('所选演算室未在 White 时间线加载：'+', '.join(sorted(required-set(by_name))))
    reachable={start};pending=[start]
    while pending:
        for target in by_name[pending.pop()]['connections']:
            if target!='DISCONNECTED' and target not in reachable:reachable.add(target);pending.append(target)
    missing=required-reachable
    if missing:raise ValueError('起始房间无法通往所选演算室：'+', '.join(sorted(missing)))
    if len(by_name)>1 and len(reachable)==1:raise ValueError('起始房间与导出地区不连通：'+start)
    return rows
