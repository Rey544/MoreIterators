"""Project-bound dialogue presets; appearance saves cannot overwrite this document."""
import copy,json,re,math,uuid
from pathlib import Path

AFFINITY_TIERS=('notSpeaking','dislikes','neutral','likes')
ITEM_CATEGORIES=('items','weapons','pearls','mixed','creatures','corpses','food')
OBSERVATION_POOLS=ITEM_CATEGORIES+tuple('repeat'+key[0].upper()+key[1:] for key in ITEM_CATEGORIES)
PEARL_POOLS=('firstPreRead','greetingCreatures','greetingCorpses','greetingFood','greeting','greetingItems','greetingWeapons','greetingPearls','greetingMixed','quickReturn','revisit','extractedPreRead','repeat','many','leaving','returning','preRead','misc')

def affinity_defaults():
    return dict(enabled=True,initial=.3,attackMode='vanilla',rockPenalty=.2,spearPenalty=.5,
        refuseBelow=-.5,pearlGiftEnabled=False,pearlGiftAmount=.1,attackRock={tier:[] for tier in AFFINITY_TIERS},
        attackSpear={tier:[] for tier in AFFINITY_TIERS},refusal=[])

def observation_defaults():return dict(enabled=True,cooldown=4.0,**{key:[] for key in OBSERVATION_POOLS})

def presentation_defaults():return dict(movement='inherit',eyes='inherit')

def validate_presentation(value):
    if not isinstance(value,dict) or set(value)-{'movement','eyes'}:raise ValueError('台词表现设置无效')
    result={**presentation_defaults(),**value}
    if result['movement'] not in ('inherit','still','small','large'):raise ValueError('台词活动幅度无效')
    if result['eyes'] not in ('inherit','natural','open','closed'):raise ValueError('台词眼睛状态无效')
    return result

def validate_action(action,child=False):
    if not isinstance(action,dict) or action.get('type') not in ('none','killPlayer','liftSpinPlayer','liftAndGiveMark','giveMark','movePlayerToExit','sequence'):
        raise ValueError('台词结束动作无效')
    kind=action['type'];allowed={'type','delay'}
    if child and kind in ('sequence','none'):raise ValueError('组合中只能加入独立动作')
    if kind=='sequence':
        if set(action)-{'type','actions'}:raise ValueError('动作组合包含未知字段')
        parts=action.get('actions')
        if not isinstance(parts,list) or not 1<=len(parts)<=16:raise ValueError('动作组合应包含 1—16 个动作')
        for part in parts:validate_action(part,True)
        return
    if kind in ('liftSpinPlayer','liftAndGiveMark','movePlayerToExit'):allowed.add('duration')
    if kind=='movePlayerToExit':allowed.add('exitNode')
    if kind=='liftSpinPlayer':allowed.update(('offsetX','offsetY','radius','endAngle'))
    if set(action)-allowed:raise ValueError('台词结束动作包含未知字段')
    action.setdefault('delay',0.0);delay=action['delay']
    if type(delay) not in (int,float) or not math.isfinite(delay) or not 0<=delay<=60:
        raise ValueError('动作延迟应为 0—60 秒')
    if kind in ('liftSpinPlayer','liftAndGiveMark','movePlayerToExit'):
        action.setdefault('duration',3.0);duration=action['duration']
        if type(duration) not in (int,float) or not math.isfinite(duration) or not .25<=duration<=15:
            raise ValueError('动作持续时间应为 0.25—15 秒')
    if kind=='movePlayerToExit':
        action.setdefault('exitNode',0)
        if type(action['exitNode']) is not int or not 0<=action['exitNode']<=127:
            raise ValueError('动作目标出口应为 0—127 的通道编号')
    if kind=='liftSpinPlayer':
        for key,lo,hi,default in (('offsetX',-1000,1000,0),('offsetY',-1000,1000,70),('radius',0,200,14),('endAngle',-1440,1440,360)):
            if key not in action:continue  # Preserve the compact legacy representation.
            value=action[key]
            if type(value) not in (int,float) or not math.isfinite(value) or not lo<=value<=hi:raise ValueError('旋转动作参数超出范围：'+key)

def validate_line_actions(line):
    if line.get('kind','text') not in ('text','action'):raise ValueError('对话条目类型无效')
    if line.get('kind')=='action' and line['text'].strip():raise ValueError('独立动作不能包含台词')
    for key in ('beforeAction','action'):
        if key in line:validate_action(line[key])


def project(root,pid):
    if not isinstance(pid,str) or not re.fullmatch('[a-z][a-z0-9-]{0,47}',pid):raise ValueError('项目编号无效')
    return json.loads((root/pid/'project.json').read_text('utf-8'))

def lines(text):return [dict(lineId=uuid.uuid4().hex,text=s.strip(),hold=2.0,gap=.6) for s in (text or '').splitlines() if s.strip()]

def pearl_defaults():
    return dict(firstPreRead=[],greetingCreatures=[],greetingCorpses=[],greetingFood=[],greetingEnabled=True,greetingDelay=3.0,greetingItems=[],greetingWeapons=[],greetingPearls=[],greetingMixed=[],quickReturn=[],revisit=[],quickReturnWindow=30.0,returnCooldown=10.0,extractStomachPearl=False,extractedPreRead=[],presentation=presentation_defaults(),preRead=[],misc=[],
        greeting=[dict(name='带来了什么',lines=lines('小家伙，你这次给我带了什么东西？'))],
        preventSameCycleRepeat=True,
        repeat=[dict(name='已经读过',lines=lines('这颗珍珠，我记得。'))],
        manyEnabled=True,manyThreshold=3,
        many=[dict(name='带来不少',lines=lines('你这一趟带来了不少珍珠。\n让我看看这一颗。'))],
        leavePolicy='resume',
        leaving=[dict(name='离开',lines=lines('……你要离开了吗？'))],
        returning=[dict(name='回来',lines=lines('那么，接着刚才的内容。'))])

def with_pearl_rules(p,d):
    existing=d.get('pearlReading',{})
    if not isinstance(existing,dict):raise ValueError('读珍珠设置必须是对象')
    if all(k in existing for k in ('repeat','many','leaving','returning','leavePolicy')):return validate(d)
    # Merge earlier per-pearl pools once, without changing their source files.
    import storage
    rules={**pearl_defaults(),**existing};found={k:[] for k in ('repeat','many','leaving','returning') if k not in existing}
    migrated=storage.DATA/'pearl-projects/legacy/pearls'
    legacy=migrated if migrated.is_dir() else storage.DATA/'pearls'
    for file in sorted(legacy.glob('*/pearl.json')):
        old=json.loads(file.read_text('utf-8'))
        for reader in old.get('readers',[]):
            if reader.get('projectId')!=p.get('projectId'):continue
            if 'leavePolicy' not in existing and reader.get('leavePolicy') in ('resume','restart','cancel'):rules['leavePolicy']=reader['leavePolicy']
            for key in found:
                for group in reader.get(key,[]):
                    if group not in found[key]:found[key].append(copy.deepcopy(group))
    for key,pool in found.items():
        if pool:rules[key]=pool[:40]
    d=copy.deepcopy(d);d['pearlReading']=rules
    return validate(d)

def profile(p):
    if p.get('dialogue'):return with_pearl_rules(p,copy.deepcopy(p['dialogue']))
    d=p.get('design',{})
    result=dict(schema='moreiterators.dialogue.v1',enabled=not bool(p.get('legacyOracle')),requireMark=True,
        first=lines(d.get('firstDialogue','……你好。')),repeat=[],
        pickupEnabled=True,pickup=[dict(name='请放回',lines=lines('那颗珍珠我还在用。\n请先把它放回来。')),dict(name='不是食物',lines=lines('……那不是食物。\n我们继续吧。'))],
        leaveEnabled=True,leaving=[dict(name='离开提醒',lines=lines('……要离开了吗？'))],
        returning=[dict(name='继续',lines=lines('你回来了。\n那么，接着刚才的话。'))],cooldown=4.0)
    import compatibility
    result=compatibility.dialogue_profile(p,result)
    return with_pearl_rules(p,result)

def validate(d):
    if not isinstance(d,dict) or d.get('schema') not in ('eoe.dialogue.v1','moreiterators.dialogue.v1'):raise ValueError('对话预设格式错误')
    d=copy.deepcopy(d)
    d['requireMark']=True
    def section(key,defaults):
        value=d.get(key,{})
        if not isinstance(value,dict):raise ValueError('对话设置必须是对象：'+key)
        result={**defaults,**value};d[key]=result;return result
    p=section('pearlReading',pearl_defaults())
    affinity=section('affinity',affinity_defaults())
    observation=section('observation',observation_defaults())
    for k in ('enabled','requireMark','pickupEnabled','leaveEnabled'):
        if type(d.get(k)) is not bool:raise ValueError('对话开关无效：'+k)
    def number(v,lo,hi):return type(v) in (int,float) and math.isfinite(v) and lo<=v<=hi
    if not number(d.get('cooldown'),0,60):raise ValueError('打断冷却应为 0—60 秒')
    line_ids=set()
    def check_lines(arr):
        if not isinstance(arr,list) or len(arr)>200:raise ValueError('每组最多 200 句')
        for line in arr:
            if not isinstance(line,dict) or not isinstance(line.get('text'),str) or len(line['text'])>2000:raise ValueError('每句最多 2000 字')
            ensure_line_id(line,line_ids)
            validate_line_actions(line)
            if 'presentation' in line:line['presentation']=validate_presentation(line['presentation'])
            for key,lo,hi in [('hold',.1,60),('gap',0,60)]:
                if not number(line.get(key),lo,hi):raise ValueError('台词停留或间隔时间无效')
    def check_pool(pool):
        if not isinstance(pool,list) or len(pool)>40:raise ValueError('随机池最多 40 组')
        for item in pool:
            if not isinstance(item,dict) or not isinstance(item.get('name'),str) or len(item['name'])>80:raise ValueError('随机组名称无效')
            check_lines(item.get('lines'))
            if 'action' in item:validate_action(item['action'])
    d.setdefault('repeat',[])
    d.setdefault('storyMode','sequence');d.setdefault('meetings',[]);d.setdefault('loop',[])
    if d['storyMode'] not in ('sequence','firstThenLoop'):raise ValueError('后续剧情模式无效')
    if not isinstance(d['meetings'],list) or len(d['meetings'])>38:raise ValueError('最多可添加 38 次后续见面剧情')
    def check_condition(value):
        if not isinstance(value,dict) or set(value)-{'minEntries','minCycle','held'}:raise ValueError('见面条件格式无效')
        result={'minEntries':0,'minCycle':0,'held':'any',**value}
        for key in ('minEntries','minCycle'):
            if type(result[key]) is not int or not 0<=result[key]<=9999:raise ValueError('见面条件次数应为 0—9999 的整数')
        if result['held'] not in ('any',)+ITEM_CATEGORIES:raise ValueError('见面条件物品类型无效')
        return result
    for key in ('firstCondition','repeatCondition'):d[key]=check_condition(d.get(key,{}))
    meeting_ids=set()
    for meeting in d['meetings']:
        if not isinstance(meeting,dict):raise ValueError('见面剧情格式无效')
        mid=meeting.get('id')
        if not isinstance(mid,str) or not re.fullmatch('[a-f0-9]{32}',mid) or mid in meeting_ids:raise ValueError('见面剧情编号无效或重复')
        meeting_ids.add(mid)
        if not isinstance(meeting.get('name'),str) or len(meeting['name'])>80:raise ValueError('见面剧情名称最多 80 字')
        meeting['condition']=check_condition(meeting.get('condition',{}))
        check_lines(meeting.get('lines'))
        if 'action' in meeting:validate_action(meeting['action'])
    for k in ('first','repeat','loop'):
        check_lines(d.get(k))
        if k+'Action' in d:validate_action(d[k+'Action'])
    for k in ('pickup','leaving','returning'):check_pool(d.get(k))
    for k in ('greetingEnabled','preventSameCycleRepeat','manyEnabled','extractStomachPearl'):
        if type(p.get(k)) is not bool:raise ValueError('读珍珠开关无效：'+k)
    if not number(p.get('greetingDelay'),0,120):raise ValueError('进房等待应为 0—120 秒')
    for key in ('quickReturnWindow','returnCooldown'):
        if not number(p.get(key),0,3600):raise ValueError('返回时间应为 0—3600 秒')
    p['presentation']=validate_presentation(p['presentation'])
    if type(p.get('manyThreshold')) is not int or not 2<=p['manyThreshold']<=50:raise ValueError('多珍珠提示从第 2—50 颗开始')
    if p.get('leavePolicy') not in ('resume','restart','cancel'):raise ValueError('离开规则无效')
    for k in PEARL_POOLS:check_pool(p.get(k))
    if type(affinity.get('enabled')) is not bool or type(affinity.get('pearlGiftEnabled')) is not bool:raise ValueError('好感度开关无效')
    if affinity.get('attackMode') not in ('vanilla','gradual'):raise ValueError('受击好感度规则无效')
    for key,lo,hi in (('initial',-1,1),('refuseBelow',-1,1),('rockPenalty',0,2),('spearPenalty',0,2),('pearlGiftAmount',0,2)):
        if not number(affinity.get(key),lo,hi):raise ValueError('好感度数值无效：'+key)
    for key in ('attackRock','attackSpear'):
        tiers=affinity.get(key)
        if not isinstance(tiers,dict) or set(tiers)-set(AFFINITY_TIERS):raise ValueError('好感度档位无效：'+key)
        for tier in AFFINITY_TIERS:check_pool(tiers.setdefault(tier,[]))
    check_pool(affinity.get('refusal'))
    if type(observation.get('enabled')) is not bool:raise ValueError('观察物品开关无效')
    if not number(observation.get('cooldown'),0,60):raise ValueError('观察物品冷却应为 0—60 秒')
    for key in OBSERVATION_POOLS:check_pool(observation.get(key))
    return d


def ensure_line_id(line,seen):
    """Assign once to legacy/new lines; reject collisions instead of rebinding."""
    value=line.get('lineId')
    if value is None or value=='':value=line['lineId']=uuid.uuid4().hex
    if not isinstance(value,str) or not re.fullmatch(r'[a-f0-9]{32}|[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}',value):
        raise ValueError('台词内部 ID 无效；请重新打开台词编辑器')
    if value in seen:raise ValueError('台词内部 ID 重复；复制台词时必须生成新 ID')
    seen.add(value)

def persisted_profile(pid,roomnames=None):
    """Persist legacy IDs before exposing anchors to any projection editor."""
    import storage,pearls
    p=copy.deepcopy(storage.load_project(storage.valid_id(pid)));d=profile(p)
    if p.get('dialogue')!=d:
        p['dialogue']=d;p['dialogueRevision']=p.get('dialogueRevision',0)+1
        pearls.atomic(storage.project_file(pid),p)
    if roomnames:
        oid=roomnames(p)[2];runtime=storage.design_path(pid,oid)
        if runtime.is_file():
            compiled=json.loads(runtime.read_text('utf-8'));old=json.loads(compiled.get('dialogueJson','{}'))
            before=copy.deepcopy(old);sync_line_ids(old,d)
            if old!=before:
                compiled['dialogueJson']=json.dumps(old,ensure_ascii=False)
                pearls.atomic(runtime,compiled);storage.sync_design(pid,oid)
    return p


def sync_line_ids(runtime,authored):
    """ID migration cannot publish draft text or change applied timings."""
    if isinstance(runtime,dict) and isinstance(authored,dict):
        if 'text' in runtime:
            if not runtime.get('lineId') and runtime.get('text')==authored.get('text') and authored.get('lineId'):runtime['lineId']=authored['lineId']
        else:
            for key in runtime:
                if key in authored:sync_line_ids(runtime[key],authored[key])
    elif isinstance(runtime,list) and isinstance(authored,list) and len(runtime)==len(authored):
        for a,b in zip(runtime,authored):sync_line_ids(a,b)
