'use strict';
const MIActionEditor=(()=>{
  // Keep each stored action value, visible label and editable fields together.
  const definitions={
    none:{label:'无动作',fields:[]},
    killPlayer:{label:'处死玩家',fields:['delay']},
    liftSpinPlayer:{label:'举起玩家旋转',fields:['delay','duration','offsetX','offsetY','radius','endAngle']},
    liftAndGiveMark:{label:'举起玩家并赋予印记',fields:['delay','duration']},
    giveMark:{label:'赋予印记',fields:['delay']},
    movePlayerToExit:{label:'送入指定通道井',fields:['delay','duration','exitNode']},
    sequence:{label:'动作组合',fields:[]}
  };
  const types=Object.keys(definitions),labels=Object.fromEntries(Object.entries(definitions).map(([type,definition])=>[type,definition.label]));
  const bounded=(value,low,high,fallback)=>Number.isFinite(Number(value))?Math.max(low,Math.min(high,Number(value))):fallback;
  function normalize(value,child=false){
    const type=types.includes(value?.type)?value.type:'none';
    if(type==='sequence'){
      if(child)return {type:'none',delay:0};
      const actions=(Array.isArray(value.actions)?value.actions:[]).slice(0,16).map(item=>normalize(item,true)).filter(item=>item.type!=='none');
      return actions.length?{type,actions}:{type:'none',delay:0};
    }
    const result={type,delay:bounded(value?.delay,0,60,0)};
    if(definitions[type].fields.includes('duration'))result.duration=bounded(value?.duration,.25,15,3);
    if(definitions[type].fields.includes('exitNode'))result.exitNode=Math.floor(bounded(value?.exitNode,0,127,0));
    if(type==='liftSpinPlayer')for(const [key,min,max,fallback] of [['offsetX',-1000,1000,0],['offsetY',-1000,1000,70],['radius',0,200,14],['endAngle',-1440,1440,360]])if(value?.[key]!==undefined)result[key]=bounded(value[key],min,max,fallback);
    return result;
  }
  function sequence(...values){return values.flatMap(value=>{const action=normalize(value);return action.type==='sequence'?action.actions:action.type==='none'?[]:[action];});}
  const runnable=line=>!!line&&((line.text||'').trim().length>0||sequence(line.beforeAction,line.action).length>0);
  const preset=()=>({type:'sequence',actions:[{type:'liftSpinPlayer',delay:0,duration:3,offsetX:0,offsetY:70,radius:14,endAngle:360},{type:'giveMark',delay:0}]});
  const seconds=action=>(action.delay||0)+(action.type==='killPlayer'?1:action.type==='giveMark'?0:action.duration??3);
  const presets=(()=>{
    const fallback={open:'预设',action:'动作预设',presentation:'表现预设',choose:'选择预设',apply:'使用',name:'名称',save:'保存当前设置',close:'关闭',overwrite:'覆盖“{name}”？',saved:'已保存 {name}',busy:'正在载入…',builtinAction:'举起玩家旋转并开智',builtinPresentation:'闭眼静止'};
    const t=(key,params={})=>typeof MI18n!=='undefined'?MI18n.t('action.presets.'+key,params):Object.entries(params).reduce((s,[k,v])=>s.replace('{'+k+'}',v),fallback[key]||key);
    async function request(method,data,kind){
      if(typeof MI18n!=='undefined')await MI18n.ready;
      const response=await fetch('/api/action-presets'+(method==='GET'?'?kind='+encodeURIComponent(kind):''),method==='GET'?{}:{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}),result=await response.json();
      if(!response.ok)throw Error(typeof MI18n!=='undefined'?MI18n.error(result,response.statusText):result.error||response.statusText);
      return result;
    }
    async function open({kind='action',value,onApply}){
      const current=kind==='action'?normalize(value):presentation.normalize(value),dialog=document.createElement('dialog');dialog.className='mi-preset-library';dialog.style.cssText='width:min(560px,90vw);max-height:80vh;overflow:auto;padding:24px';
      const title=document.createElement('h2'),select=document.createElement('select'),preview=document.createElement('p'),status=document.createElement('p'),apply=document.createElement('button'),name=document.createElement('input'),save=document.createElement('button'),close=document.createElement('button');
      const chooseLabel=document.createElement('label'),nameLabel=document.createElement('label'),chooseText=document.createElement('span'),nameText=document.createElement('span'),actions=document.createElement('div'),saveRow=document.createElement('div');
      chooseLabel.style.cssText=nameLabel.style.cssText='display:grid;gap:8px;margin:16px 0';actions.style.cssText=saveRow.style.cssText='display:flex;gap:12px;justify-content:flex-end;margin-top:16px';
      name.maxLength=80;name.autocomplete='off';for(const button of [apply,save,close])button.type='button';
      chooseLabel.append(chooseText,select);nameLabel.append(nameText,name);actions.append(apply,close);saveRow.append(save);dialog.append(title,chooseLabel,preview,actions,nameLabel,saveRow,status);document.body.append(dialog);
      let entries=[],busy=false,selected='';
      const describe=item=>item.kind==='presentation'?presentation.describe(item.value):sequence(item.value).map(v=>typeof MI18n!=='undefined'?MI18n.text(labels[v.type]):labels[v.type]).join(' → ');
      function render(){
        const before=select.value||selected;title.textContent=t(kind);chooseText.textContent=t('choose');nameText.textContent=t('name');save.textContent=t('save');close.textContent=t('close');apply.textContent=t('apply');select.setAttribute('aria-label',t('choose'));name.setAttribute('aria-label',t('name'));
        select.replaceChildren();for(const item of entries){const option=document.createElement('option');option.value=item.id;option.textContent=item.builtin?t(item.kind==='action'?'builtinAction':'builtinPresentation'):item.name;if(!item.builtin&&typeof MI18n!=='undefined')MI18n.content(option);select.append(option);}
        select.value=entries.some(v=>v.id===before)?before:entries[0]?.id||'';selected=select.value;preview.textContent=entries.find(v=>v.id===selected)?describe(entries.find(v=>v.id===selected)):'';apply.disabled=busy||!selected;save.disabled=busy;select.disabled=busy;
      }
      async function run(operation){if(busy)return;busy=true;status.textContent='';render();try{await operation();}catch(error){status.textContent=error.message;status.style.color='#ffb4a7';}finally{busy=false;render();}}
      select.onchange=()=>{selected=select.value;render();};close.onclick=()=>dialog.close();
      apply.onclick=()=>{const item=entries.find(v=>v.id===select.value);if(!item||busy)return;onApply(structuredClone(item.value));dialog.close();};
      save.onclick=()=>run(async()=>{
        const title=name.value.trim();const latest=await request('GET',undefined,kind),existing=latest.find(v=>v.name.toLocaleLowerCase()===title.toLocaleLowerCase());
        if(existing&&!existing.builtin&&!confirm(t('overwrite',{name:existing.name})))return;
        const result=await request('POST',{kind,name:title,value:current,...(existing&&!existing.builtin?{overwriteId:existing.id}:{})},kind);entries=result.presets;select.value='';selected=result.preset.id;status.style.color='';status.textContent=t('saved',{name:result.preset.name});
      });
      const language=()=>render();if(typeof window!=='undefined')window.addEventListener('mi-language-change',language);dialog.addEventListener('close',()=>{if(typeof window!=='undefined')window.removeEventListener('mi-language-change',language);dialog.remove();},{once:true});
      render();dialog.showModal();await run(async()=>{entries=await request('GET',undefined,kind);});return dialog;
    }
    return {open};
  })();
  function geometry(value,onChange){
    let state={offsetX:0,offsetY:70,radius:14,endAngle:360,...value},drag=null;
    const box=document.createElement('details');box.className='mi-motion-geometry';
    const summary=document.createElement('summary');summary.textContent='拖动终点与半径';box.append(summary);
    const plane=document.createElement('div');plane.className='mi-motion-plane';plane.setAttribute('aria-label','旋转路径');box.append(plane);
    const make=(tag,cls,text)=>{const node=document.createElement(tag);node.className=cls;if(text)node.textContent=text;plane.append(node);return node;};
    const ring=make('div','mi-motion-ring'),origin=make('span','mi-motion-origin','起点');
    const center=make('button','mi-motion-handle mi-motion-center','终点'),radius=make('button','mi-motion-handle mi-motion-radius','半径'),angle=make('button','mi-motion-handle mi-motion-angle','角度');
    center.title='旋转中心的终点，相对玩家起始位置';angle.title='玩家在轨道上的结束角度';
    const scale=()=>Math.min(1,130/(Math.abs(state.offsetX)+state.radius+35),140/(Math.abs(state.offsetY)+state.radius+35));
    function point(node,x,y){node.style.left=(x/320*100)+'%';node.style.top=(y/240*100)+'%';}
    function draw(){const s=drag?.scale??scale(),x=160+state.offsetX*s,y=170-state.offsetY*s,r=state.radius*s,a=state.endAngle*Math.PI/180;point(origin,160,170);point(center,x,y);point(radius,x+r,y);point(angle,x+Math.cos(a)*r,y-Math.sin(a)*r);point(ring,x-r,y-r);ring.style.width=(Math.max(1,2*r)/320*100)+'%';ring.style.height=(Math.max(1,2*r)/240*100)+'%';}
    for(const [node,kind] of [[center,'center'],[radius,'radius'],[angle,'angle']]){
      node.type='button';node.setAttribute('aria-label',kind==='center'?'拖动旋转终点':kind==='radius'?'拖动旋转半径':'拖动结束角度');
      node.onpointerdown=e=>{if(e.button!==0)return;e.preventDefault();drag={kind,pointer:e.pointerId,scale:scale()};node.setPointerCapture(e.pointerId);};
      node.onpointermove=e=>{if(!drag||drag.pointer!==e.pointerId)return;e.preventDefault();const rect=plane.getBoundingClientRect(),x=(e.clientX-rect.left)*320/rect.width,y=(e.clientY-rect.top)*240/rect.height,s=drag.scale,cx=160+state.offsetX*s,cy=170-state.offsetY*s;
        if(kind==='center'){state.offsetX=Math.round(bounded((x-160)/s,-1000,1000,0));state.offsetY=Math.round(bounded((170-y)/s,-1000,1000,70));}
        else if(kind==='radius')state.radius=Math.round(bounded(Math.hypot(x-cx,y-cy)/s,0,200,14));
        else {const raw=Math.atan2(cy-y,x-cx)*180/Math.PI;state.endAngle=Math.round(bounded(raw+360*Math.round((state.endAngle-raw)/360),-1440,1440,360));}
        draw();onChange({...state});};
      const end=e=>{if(!drag||drag.pointer!==e.pointerId)return;drag=null;if(node.hasPointerCapture(e.pointerId))node.releasePointerCapture(e.pointerId);draw();};node.onpointerup=node.onpointercancel=node.onlostpointercapture=end;
    }
    box.update=value=>{state={...state,...value};draw();};draw();return box;
  }
  function create(value,onChange,{label='句末动作',child=false}={}){
    let action=normalize(value);
    const host=document.createElement('div');host.className='mi-action-fields';
    const field=(title,input)=>{const row=document.createElement('label');row.className='inline-field';const span=document.createElement('span');span.textContent=title;row.append(span,input);host.append(row);return row;};
    const type=document.createElement('select');type.setAttribute('aria-label',label);
    for(const [key,definition] of Object.entries(definitions)){if(child&&['sequence','none'].includes(key))continue;const option=document.createElement('option');option.value=key;option.textContent=definition.label;type.append(option);}
    field(label,type);
    const numbers={};
    const defaults={delay:0,duration:3,exitNode:0,offsetX:0,offsetY:70,radius:14,endAngle:360};
    let motion=null;
    for(const [key,title,min,max,step] of [['delay','动作延迟（秒）',0,60,.1],['duration','动作时长（秒）',.25,15,.25],['exitNode','通道井 ID',0,127,1],['offsetX','终点水平偏移（px）',-1000,1000,1],['offsetY','终点垂直偏移（px）',-1000,1000,1],['radius','旋转半径（px）',0,200,1],['endAngle','结束角度（度）',-1440,1440,1]]){
      const input=document.createElement('input');input.type='number';input.min=min;input.max=max;input.step=step;input.setAttribute('aria-label',title);
      const row=field(title,input);numbers[key]={input,row};
      input.oninput=()=>{const next=Number(input.value);if(input.value===''||!Number.isFinite(next)||next<min||next>max||key==='exitNode'&&!Number.isInteger(next))return;action={...action,[key]:next};motion?.update(action);onChange(normalize(action));};
      input.onchange=()=>{const next=Number(input.value);if(input.value===''||!Number.isFinite(next)||next<min||next>max||key==='exitNode'&&!Number.isInteger(next)){input.value=action[key]??defaults[key];return;}action={...action,[key]:next};motion?.update(action);onChange(normalize(action));};
    }
    const extra=document.createElement('div');extra.className='mi-action-extra';host.append(extra);
    if(!child){const apply=document.createElement('button');apply.type='button';apply.className='mi-action-preset';apply.textContent='预设';apply.onclick=()=>presets.open({kind:'action',value:action,onApply:next=>{action=normalize(next);render();onChange(structuredClone(action));}});host.append(apply);}
    function render(){
      type.value=action.type;for(const [key,item] of Object.entries(numbers)){item.input.value=action[key]??defaults[key];item.row.hidden=!definitions[action.type].fields.includes(key);}
      extra.replaceChildren();motion=null;
      if(action.type==='liftSpinPlayer'){motion=geometry(action,next=>{action=normalize(next);for(const key of ['offsetX','offsetY','radius','endAngle'])numbers[key].input.value=action[key]??defaults[key];onChange(action);});extra.append(motion);}
      if(action.type==='sequence'){
        action.actions.forEach((part,index)=>{const row=document.createElement('div');row.className='mi-sequence-row';const bar=document.createElement('div');bar.className='mi-sequence-order';const title=document.createElement('span');title.textContent=String(index+1);bar.append(title);
          for(const [text,delta] of [['↑',-1],['↓',1],['删除',0]]){const button=document.createElement('button');button.type='button';button.textContent=text;button.setAttribute('aria-label',(delta?'移动动作':'删除动作')+' '+(index+1));button.disabled=delta!==0&&(index+delta<0||index+delta>=action.actions.length);button.onclick=()=>{if(delta){const [item]=action.actions.splice(index,1);action.actions.splice(index+delta,0,item);}else action.actions.splice(index,1);action=normalize(action);render();onChange(action);};bar.append(button);}
          row.append(bar,create(part,next=>{action.actions[index]=next;onChange(normalize(action));},{label:'动作',child:true}));extra.append(row);});
        const add=document.createElement('button');add.type='button';add.textContent='＋ 添加动作';add.disabled=action.actions.length>=16;add.onclick=()=>{action.actions.push({type:'liftSpinPlayer',delay:0,duration:3});render();onChange(action);};extra.append(add);
      }
    }
    type.onchange=()=>{action=type.value==='sequence'?{type:'sequence',actions:action.type==='none'?[{type:'liftSpinPlayer',delay:0,duration:3}]:sequence(action)}:normalize({...action,type:type.value});render();onChange(action);};
    render();return host;
  }
  const presentation=(()=>{
    const labels={movement:{inherit:'沿用',still:'静止',small:'小幅活动',large:'大幅活动'},eyes:{inherit:'沿用',natural:'自然眨眼',open:'睁眼',closed:'闭眼'}};
    const normalize=value=>Object.fromEntries(Object.entries(labels).map(([key,options])=>[key,Object.hasOwn(options,value?.[key])?value[key]:'inherit']));
    function resolve(...layers){const result=normalize();for(const layer of layers){const value=normalize(layer);for(const key of Object.keys(labels))if(value[key]!=='inherit')result[key]=value[key];}return result;}
    function describe(value){const state=normalize(value),text=raw=>typeof MI18n!=='undefined'?MI18n.text(raw):raw;return text('活动')+'：'+text(labels.movement[state.movement])+' · '+text('眼睛')+'：'+text(labels.eyes[state.eyes]);}
    function create(value,onChange,{label='表现',mode=false}={}){
      let state=normalize(value),custom=Object.values(state).some(value=>value!=='inherit');
      const host=document.createElement('details');host.className='mi-presentation';
      const summary=document.createElement('summary');summary.textContent=label;host.append(summary);
      const fields=document.createElement('div');fields.className='mi-presentation-fields';host.append(fields);
      let modeSelect=null;
      const selects={};
      const field=(title,select)=>{const row=document.createElement('label'),caption=document.createElement('span');caption.textContent=title;select.setAttribute('aria-label',title);row.append(caption,select);fields.append(row);};
      const choice=(key,title)=>{const option=document.createElement('option');option.value=key;option.textContent=title;return option;};
      if(mode){modeSelect=document.createElement('select');modeSelect.append(choice('inherit','沿用'),choice('custom','自定义'));field('读取表现',modeSelect);modeSelect.onchange=()=>{custom=modeSelect.value==='custom';if(!custom){state=normalize();onChange(state);}render();};}
      for(const [key,title] of [['movement','活动'],['eyes','眼睛']]){const select=document.createElement('select');select.dataset.presentation=key;select.append(...Object.entries(labels[key]).map(([value,title])=>choice(value,title)));field(title,select);selects[key]=select;select.onchange=()=>{state={...state,[key]:select.value};onChange({...state});};}
      const presetButton=document.createElement('button');presetButton.type='button';presetButton.textContent='预设';presetButton.className='mi-presentation-preset';presetButton.onclick=()=>presets.open({kind:'presentation',value:state,onApply:value=>{state=normalize(value);custom=true;render();onChange({...state});}});fields.append(presetButton);
      function render(){if(modeSelect)modeSelect.value=custom?'custom':'inherit';for(const [key,select] of Object.entries(selects)){select.value=state[key];select.disabled=mode&&!custom;}}
      render();return host;
    }
    return {labels,normalize,resolve,describe,create};
  })();
  return {types,labels,normalize,sequence,runnable,preset,seconds,geometry,create,presentation,presets};
})();
if(typeof module!=='undefined')module.exports=MIActionEditor;
if(typeof window!=='undefined')window.MIActionEditor=MIActionEditor;
