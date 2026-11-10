import json,re
from dataclasses import dataclass

@dataclass
class Call:
    name:str
    args:list

def parse(text):
    tokens=re.findall(r'"(?:[^"\\]|\\.)*"|\#[A-Za-z_][A-Za-z_0-9]*|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|[A-Za-z_][A-Za-z_0-9]*|[\[\](),:]',text)
    index=0
    def value():
        nonlocal index
        token=tokens[index];index+=1
        if token=='[':
            if tokens[index]==']':index+=1;return []
            mapping=tokens[index].startswith('#') and tokens[index+1]==':'
            result={} if mapping else []
            while True:
                if mapping:
                    key=tokens[index][1:];index+=2;result[key]=value()
                else:result.append(value())
                ending=tokens[index];index+=1
                if ending==']':return result
                if ending!=',':raise ValueError((ending,index))
        if token.startswith('"'):return json.loads(token)
        if token[0].isdigit() or token[0]=='-':return float(token) if '.' in token or 'e' in token.lower() else int(token)
        if index<len(tokens) and tokens[index]=='(':
            index+=1;args=[]
            while tokens[index]!=')':
                args.append(value())
                if tokens[index]==',':index+=1
            index+=1;return Call(token,args)
        raise ValueError((token,index))
    result=value()
    if index!=len(tokens):raise ValueError(('trailing',tokens[index:index+5]))
    return result

def dump(value):
    if isinstance(value,dict):return '['+', '.join('#'+key+': '+dump(item) for key,item in value.items())+']'
    if isinstance(value,list):return '['+', '.join(dump(item) for item in value)+']'
    if isinstance(value,Call):return value.name+'('+', '.join(dump(item) for item in value.args)+')'
    return json.dumps(value,ensure_ascii=False)
