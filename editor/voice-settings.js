"use strict";
const VoiceSettings=(()=>{
 const blank=()=>({enabled:false,bank:'pebbles',unmarkedOnly:false,speed:1,pitch:1,volume:.35,shortWeight:50,mediumWeight:35,longWeight:15,echo:0,muffle:0,electric:0,chaos:0,repeat:true,reverse:true,split:true,templateId:'pebbles',templates:[]});
 const timbreKeys=Object.keys(blank()).filter(k=>!['enabled','unmarkedOnly','templateId','templates'].includes(k));
 let generation=0,refreshTimer=null;const t=s=>MI18n.text(s);
 function stopPreview(){generation++;clearTimeout(refreshTimer);if(typeof VoiceAudio!=='undefined')VoiceAudio.stop();}
 function init(p){stopPreview();p.design.voice={...blank(),...p.design.voice};}
 function timbre(voice){return Object.fromEntries(timbreKeys.map(k=>[k,voice[k]]));}
 function preset(voice,id){if(id==='pebbles'||id==='moon')return {...timbre(blank()),bank:id};return voice.templates.find(p=>p.id===id)?.settings;}
 function apply(voice,id){const selected=preset(voice,id);if(!selected)throw Error(t('选择的声音模板不存在'));Object.assign(voice,selected,{templateId:id});}
 function save(voice,name,create){
  name=String(name||'').trim();if(!name||name.length>60||/[\x00-\x1f]/.test(name))throw Error(t('声音模板名称需要 1–60 个字符'));
  let item=create?null:voice.templates.find(p=>p.id===voice.templateId);
  if(!create&&!item)throw Error(t('原版模板请另存为新模板'));
  if(!item){if(voice.templates.length>=32)throw Error(t('最多保存 32 个声音模板'));item={id:'voice-'+globalThis.crypto.randomUUID(),name,settings:{}};voice.templates.push(item);}
  item.name=name;item.settings=timbre(voice);voice.templateId=item.id;return item;
 }
 function remove(voice){const index=voice.templates.findIndex(p=>p.id===voice.templateId);if(index<0)throw Error(t('原版模板不能删除'));voice.templates.splice(index,1);apply(voice,voice.bank);}
 function dialogueLines(data){
  const found=[],seen=new Set();function scan(value,path,depth){if(depth>16||found.length>=500)return;if(Array.isArray(value)){value.forEach((v,i)=>scan(v,path.concat(String(i+1)),depth+1));return;}if(!value||typeof value!=='object')return;
   if(typeof value.text==='string'&&value.text.trim()&&value.kind!=='action'){const id=value.lineId||path.join('/');if(!seen.has(id)){seen.add(id);found.push({id,text:value.text,label:value.text.trim().slice(0,60)});}return;}
   for(const [key,item]of Object.entries(value))scan(item,path.concat(key),depth+1);
  }scan(data,[],0);return found;
 }
 function settings(parent,d,options={}){
  stopPreview();const session=generation,voice=d.voice??=blank();voice.templates??=[];
  const current=()=>session===generation&&(!options.getProject||options.getProject()?.design===d);
  const part=garmentSection(parent,'迭代器语音');part.dataset.sectionId='iteratorVoice';
  const commit=()=>{stopPreview();options.changed?.();options.rebuild?.();};
  garmentField(part,voice,'enabled','在游戏中启用','checkbox');
  const choices={pebbles:'五块卵石',moon:'仰望皓月',...Object.fromEntries(voice.templates.map(p=>[p.id,p.name]))};
  const select=garmentField(part,voice,'templateId','声音模板','select',choices,null,null,()=>{apply(voice,voice.templateId);options.rebuild?.();});
  if(select)for(const option of select.options||[])if(option.value.startsWith('voice-'))MI18n.content?.(option);
  const naming={name:voice.templates.find(p=>p.id===voice.templateId)?.name||''};const nameLabel=document.createElement('label');nameLabel.className='field voice-name-field';const nameTitle=document.createElement('span');nameTitle.textContent=t('模板名称');const nameInput=document.createElement('input');nameInput.type='text';nameInput.maxLength=60;nameInput.value=naming.name;nameInput.setAttribute('aria-label',t('模板名称'));nameInput.oninput=()=>naming.name=nameInput.value;nameLabel.append(nameTitle,nameInput);part.append(nameLabel);
  const actions=document.createElement('div');actions.className='voice-actions';part.append(actions);
  garmentButton(actions,'另存新模板',()=>{save(voice,naming.name,true);commit();});
  const saveButton=garmentButton(actions,'保存模板',()=>{save(voice,naming.name,false);commit();});saveButton.disabled=!voice.templateId.startsWith('voice-');
  const deleteButton=garmentButton(actions,'删除模板',()=>{remove(voice);commit();});deleteButton.disabled=saveButton.disabled;
  const body=garmentSection(part,'声线参数');body.open=true;
  const live=()=>{if(typeof VoiceAudio!=='undefined'&&VoiceAudio.active){clearTimeout(refreshTimer);refreshTimer=setTimeout(()=>{if(current())play();},140);}};
  garmentField(body,voice,'bank','原始声音','select',{pebbles:'五块卵石',moon:'仰望皓月'},null,null,live);
  for(const [key,label,min,max,step]of [['speed','语速',.25,3,.05],['pitch','音高',.2,3,.05],['volume','语音音量',0,2,.01],['echo','回声',0,1,.01],['muffle','朦胧程度',0,1,.01],['electric','电流感',0,1,.01],['chaos','混乱程度',0,1,.01]])garmentField(body,voice,key,label,'range',min,max,step,live);
  for(const [key,label]of [['repeat','重复片段'],['reverse','颠倒顺序'],['split','拆分音节']])garmentField(body,voice,key,label,'checkbox',null,null,null,live);
  const weights=garmentSection(body,'音节比例');for(const [key,label]of [['shortWeight','短音节权重'],['mediumWeight','中音节权重'],['longWeight','长音节权重']])garmentField(weights,voice,key,label,'range',0,100,1,live);
  const preview=garmentSection(part,'语音试听');preview.open=true;
  const source=document.createElement('select');source.setAttribute('aria-label',t('剧情台词'));preview.append(source);
  const text=document.createElement('textarea');text.rows=3;text.maxLength=600;text.setAttribute('aria-label',t('试听台词'));text.placeholder=t('选择剧情台词，或输入一句试听');preview.append(text);MI18n.content?.(text);
  const status=document.createElement('p');status.className='hint';status.setAttribute('role','status');preview.append(status);
  const buttons=document.createElement('div');buttons.className='voice-actions';preview.append(buttons);
  async function play(){if(!current())return;if(typeof VoiceAudio==='undefined'||typeof VoiceSequence==='undefined')throw Error(t('声音预览组件未加载，请刷新网页'));
   try{if(voice.shortWeight+voice.mediumWeight+voice.longWeight<=0)throw Error(t('至少保留一种音节'));await VoiceAudio.play(text.value,{...voice},(state,error)=>{if(!current())return;status.textContent=state==='loading'?t('正在读取原版声音…'):state==='playing'?t('正在试听'):state==='error'?t(error?.message||'声音预览失败'):'';});}catch(error){if(current()){VoiceAudio.stop();status.textContent=t(error.message);}}
  }
  garmentButton(buttons,'播放试听',play);garmentButton(buttons,'停止试听',()=>{clearTimeout(refreshTimer);if(typeof VoiceAudio!=='undefined')VoiceAudio.stop();});
  async function loadLines(){const project=options.getProject?.();let data=project?.dialogue;try{if(project?.projectId){const response=await fetch('/api/dialogue?id='+encodeURIComponent(project.projectId));if(!response.ok)throw Error(t('无法读取剧情台词'));data=(await response.json()).dialogue;}if(!current())return;
    const lines=dialogueLines(data);source.replaceChildren();const empty=document.createElement('option');empty.value='';empty.textContent=t('选择剧情台词');source.append(empty);
    for(let i=0;i<lines.length;i++){const item=document.createElement('option');item.value=String(i);item.textContent=(i+1)+'. '+lines[i].label;MI18n.content?.(item);source.append(item);}
    source.onchange=()=>{if(source.value!==''){text.value=lines[+source.value].text.slice(0,600);live();}};
    if(!text.value&&lines.length){source.value='0';text.value=lines[0].text.slice(0,600);}
   }catch(error){if(current())status.textContent=t(error.message);}}
  garmentButton(buttons,'刷新剧情台词',loadLines);loadLines();text.oninput=live;
 }
 return {blank,init,settings,stopPreview,timbre,preset,apply,save,remove,dialogueLines};
})();
