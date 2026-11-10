const controlsErrors=[],controlsWarnings=[];window.addEventListener('error',event=>(event.message.startsWith('ResizeObserver loop')?controlsWarnings:controlsErrors).push(event.message));window.addEventListener('unhandledrejection',event=>controlsErrors.push(String(event.reason)));
const fixtureFrame=(ease='smooth')=>({duration:1,x:.5,y:.5,scale:1,rotation:0,opacity:1,brightness:1,flicker:0,ease});
const fixtureProjection={uid:'fixture-animation',projectId:'oc-controls',name:'Controls preview',revision:1,enabled:true,loop:false,trigger:{kind:'work',source:'',pearlUid:'',startLineId:'',endLineId:''},images:[],tracks:[{id:'fixture-track',name:'Circle',kind:'circle',color:'#ffffff',delay:0,frames:[fixtureFrame('quadIn'),fixtureFrame('quadIn')]}]};
window.fetch=async input=>{
 const path=new URL(input,'http://fixture.invalid').pathname;let value;
 if(path.startsWith('/locales/'))value=CONTROL_CATALOGS[path.split('/').pop().replace('.json','')];
 else if(path==='/api/projections')value={projects:[{projectId:'oc-controls',name:'Preview'}],projections:[fixtureProjection],applied:{}};
 else if(path==='/api/projection-sources')value={sources:[]};
 else if(path==='/api/projection-background')value={width:1000,height:600};
 else if(path==='/api/projection-settings')value={mask:{enabled:false,x:0,y:0,width:1,height:1},revision:0};
 else if(path==='/api/projection-reference')value={assets:[],elements:[]};
 else throw Error('Unexpected isolated route '+path);
 return {ok:true,json:async()=>structuredClone(value)};
};
const controlWait=async test=>{for(let i=0;i<300;i++){if(test())return;await new Promise(resolve=>setTimeout(resolve,10));}throw Error('Control wait timed out '+controlsErrors.join('; '));};
const controlPause=()=>new Promise(resolve=>setTimeout(resolve,30));
window.runProjectionControlTests=async()=>{
 let checks=0;const check=(value,message)=>{checks++;if(!value)throw Error(message);};await controlWait(()=>document.querySelectorAll('#frameList button').length===2);
 const ease=document.getElementById('ease'),description=document.getElementById('easeDescription'),firstLanguage=MI18n.locale;
 check(ease.disabled,'First frame allows easing');check(description.hidden,'First frame shows easing description');check(ease.options.length===19,'Expected 16 native methods plus 3 existing modes');
 document.querySelectorAll('#frameList button')[1].click();check(!ease.disabled,'Second frame cannot change easing');check(!description.hidden,'Native description absent');
 for(const option of [...ease.options].slice(3)){check(/Lerp[A-Za-z]+/.test(option.text)&&!/^Lerp[A-Za-z]+$/.test(option.text),'Localized name or original method missing: '+option.text);ease.value=option.value;ease.dispatchEvent(new Event('input',{bubbles:true}));check(description.textContent.includes(MI18n.t('projection.ease.'+option.value+'.description')),'Description did not follow selected method');}
 ease.value='quadIn';ease.dispatchEvent(new Event('input',{bubbles:true}));const old=description.textContent;MI18n.setLocale(firstLanguage==='en'?'zh-CN':'en',false);await controlPause();check(description.textContent!==old,'Description did not follow language');check(ease.selectedOptions[0].text.includes('LerpQuadEaseIn'),'Language altered method name');
 MI18n.setLocale(firstLanguage,false);await controlPause();check(description.textContent===old,'Description did not restore language');ease.value='linear';ease.dispatchEvent(new Event('input',{bubbles:true}));check(!description.hidden&&description.textContent===MI18n.t('projection.ease.unchanged'),'Identical linear frames have no explanation');ease.value='quadIn';ease.dispatchEvent(new Event('input',{bubbles:true}));
 const right=document.querySelector('.inspector')||document.getElementById('trackEditor');check(right.scrollWidth<=right.clientWidth+2,'Inspector horizontally overflows');check(document.documentElement.scrollWidth<=innerWidth+2,'Page horizontally overflows');check(!controlsErrors.length,controlsErrors.join('\n'));return {checks,errors:controlsErrors,warnings:controlsWarnings};
};
window.runRoomControlTests=async()=>{
 let checks=0;const check=(value,message)=>{checks++;if(!value)throw Error(message);};const field=key=>document.querySelector('[data-wardrobe-key="'+key+'"]'),visible=e=>!!e.getClientRects().length;await controlWait(()=>field('roomPaletteMode'));
 const originals=JSON.stringify(['roomWorkColor','roomReceptionColor','roomBrightness','roomContrast','roomSaturation','roomTransition'].map(key=>project.design[key]));
 check(['roomPaletteMode','roomGravityMode','entryGravityMode'].every(key=>field(key).tagName==='SELECT'),'Three mode controls missing');
 check(visible(field('roomWorkColor')),'MI theme fields initially hidden');field('roomPaletteMode').value='room';field('roomPaletteMode').dispatchEvent(new Event('input',{bubbles:true}));
 for(const key of ['roomWorkColor','roomReceptionColor','roomBrightness','roomContrast','roomSaturation','roomTransition'])check(!visible(field(key)),'MI field still visible: '+key);
 for(const key of ['roomGravityMode','entryGravityMode','haloColor','haloOpacity','rearGlowEnabled','rearGlowColor'])check(visible(field(key)),'Independent control hidden: '+key);
 check(originals===JSON.stringify(['roomWorkColor','roomReceptionColor','roomBrightness','roomContrast','roomSaturation','roomTransition'].map(key=>project.design[key])),'Mode switch changed authored values');
 field('roomGravityMode').value='room';field('roomGravityMode').dispatchEvent(new Event('input',{bubbles:true}));field('entryGravityMode').value='room';field('entryGravityMode').dispatchEvent(new Event('input',{bubbles:true}));check(project.design.roomGravityMode==='room'&&project.design.entryGravityMode==='room','Gravity modes did not update');
 field('roomPaletteMode').value='mi';field('roomPaletteMode').dispatchEvent(new Event('input',{bubbles:true}));check(visible(field('roomWorkColor')),'MI fields not restored');check(project.design.roomGravityMode==='room'&&project.design.entryGravityMode==='room','Palette changed gravity modes');
 const host=document.getElementById('groups');check(host.scrollWidth<=host.clientWidth+2,'Settings horizontally overflow');check(document.documentElement.scrollWidth<=innerWidth+2,'Page horizontally overflows');check(!controlsErrors.length,controlsErrors.join('\n'));return {checks,errors:controlsErrors,warnings:controlsWarnings};
};
