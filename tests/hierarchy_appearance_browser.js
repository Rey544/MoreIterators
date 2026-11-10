(async()=>{
 let checks=0;const check=(value,message)=>{checks++;if(!value)throw Error(message);},section=id=>document.querySelector('[data-section-id="'+id+'"]'),field=(host,key)=>host.querySelector('[data-wardrobe-key="'+key+'"]'),hidden=node=>!!node.closest('[hidden],[inert]'),openAll=()=>document.querySelectorAll('#settings details').forEach(node=>node.open=true);
 try{
  await MI18n.ready;await MI18n.setLocale('zh-CN',false);
  const design={layers:{sleeves:true,hands:true,mechanicalArm:false,cables:false},scarfPanels:0,sleeveMapping:'front',sleeveSymmetry:true,puppetSleeveSyncSeparated:true};
  for(const [,definitions]of sections)for(const [key,label,min]of definitions)if(!Object.hasOwn(design,key))design[key]=min==='color'?'#aabbcc':min==='bool'?true:typeof min==='number'?min:0;
  project={projectId:'hierarchy-fixture',name:'Hierarchy fixture',design,textures:{},editor:{externalRoomTools:true,target:'forehead',layer:1}};
  PuppetArms.init(project);VoiceSettings.init(project);gradientDefaults(design);for(const key of Object.keys(gradientChannels))design[key].enabled=true;
  design.roomGradient.enabled=true;design.roomGradient.ramp.enabled=false;
  const initial=JSON.stringify(project);buildSettings();openAll();
  MIUndo.register({key:()=>project.projectId,capture:()=>structuredClone(project),restore:snapshot=>{project=structuredClone(snapshot);buildSettings();},onError:error=>{throw error;}});MIUndo.reset();
  check(JSON.stringify(project)===initial&&!dirtyCount,'Hierarchy rendering rewrote project data');
  const roomStop=field(section('roomGradient').querySelector('[data-section-id="gradientStop0"]'),'color'),rampSwitch=section('roomGradient').querySelector(':scope > .setting-dependents > .field input[type=checkbox]');check(hidden(roomStop)&&!rampSwitch.checked,'Disabled room ramp hides its saved colors incorrectly');rampSwitch.click();MIUndo.flush();check(project.design.roomGradient.ramp.enabled&&!hidden(roomStop),'Explicit room ramp switch failed');check(await MIUndo.undo()&&!project.design.roomGradient.ramp.enabled,'Undo failed to restore disabled room ramp');
  check(section('iteratorVoice').parentElement===$('groups'),'Iterator voice still belongs to room settings');
  check(section('sleeves').closest('[data-section-id="clothes"]'),'Sleeves cannot be found in clothing');
  check(!section('puppetArms').querySelector('[data-wardrobe-key="sleeveEnabled"]'),'Sleeve values duplicated under body');
  check(section('puppetSleeve1').closest('[data-section-id="sleeves"]')&&section('puppetArm1').closest('[data-section-id="body"]'),'Sleeve or arm is assigned to wrong object');
  check(field(section('roomPalette'),'roomWorkColor')&&section('roomPalette').querySelector('.room-gradient-preview'),'Room palette and gradient are separated');
  check(field(section('waiting'),'entryGravityMode')&&!field(section('chamber'),'entryGravityMode'),'Waiting gravity remains inside chamber');
  const mechanical=section('mechanicalArm'),cables=section('cables');check([...mechanical.querySelectorAll('.setting-dependents details')].length>0,'Mechanical gradient missing');check([...cables.querySelectorAll('.setting-dependents details')].length>=4,'Cable gradients missing');
  check(hidden(field(mechanical.querySelector('.setting-dependents details'),'enabled'))&&hidden(field(cables.querySelector('.setting-dependents details'),'enabled')),'Disabled hardware leaves gradient controls active');
  field(mechanical,'mechanicalArm').click();MIUndo.flush();check(!hidden(field(mechanical.querySelector('.setting-dependents details'),'enabled')),'Enabling mechanical support fails to reveal gradient');check(await MIUndo.undo(),'Mechanical toggle undo failed');
  openAll();MIUndo.reset();section('chamber').open=false;section('waiting').open=true;section('puppetSleeve1').open=true;
  const oldOwn=project.design.puppetArms[1].widthScale,oldArm=project.design.puppetArms[0].lengthScale,rightWidth=field(section('puppetSleeve1'),'widthScale');rightWidth.value='1.37';rightWidth.dispatchEvent(new Event('input',{bubbles:true}));MIUndo.flush();
  check(project.design.puppetArms[0].widthScale===1.37&&project.design.puppetArms[1].widthScale===oldOwn,'Mirrored sleeve no longer edits original bound arm data');
  check(project.design.puppetArms[0].lengthScale===oldArm,'Sleeve edit changed arm geometry');check(+field(section('puppetSleeve0'),'widthScale').value===1.37,'Mirrored sibling sleeve UI failed to refresh');
  check(await MIUndo.undo(),'Sleeve edit undo failed');check(project.design.puppetArms[0].widthScale===1,'Undo failed to restore sleeve width');check(!section('chamber').open&&section('waiting').open&&section('puppetSleeve1').open,'Undo lost expanded object context');
  check(await MIUndo.redo()&&project.design.puppetArms[0].widthScale===1.37,'Sleeve edit redo failed');
  await MI18n.setLocale('en',false);buildSettings();await new Promise(resolve=>setTimeout(resolve,40));check(section('puppetArms').querySelector('summary').textContent==='Arms and hands','New arm label untranslated');check(section('roomPalette').querySelector('summary').textContent==='Room colors','New room palette label untranslated');
  document.querySelectorAll('#settings details').forEach(node=>node.open=false);section('chamber').open=true;section('roomPalette').open=true;section('clothes').open=true;section('sleeves').open=true;
  $('result').textContent=JSON.stringify({ok:true,checks});
 }catch(error){$('result').textContent=JSON.stringify({ok:false,checks,error:error.stack});}
})();
