const diagnosticsCalls=[],diagnosticsDownloads=[],diagnosticsErrors=[];
const fullEditorLog='EARLY EDITOR ERROR\n'+'context\n'.repeat(22000)+'LAST EDITOR ERROR\n';
const fullGameLog='EARLY GAME ERROR\n'+'context\n'.repeat(22000)+'LAST GAME ERROR\n';
let editorState='ok',downloadState='ok',holdPreview=null,holdDownload=null;
window.addEventListener('error',event=>diagnosticsErrors.push(event.message));
window.addEventListener('unhandledrejection',event=>diagnosticsErrors.push(String(event.reason)));
const previewFor=source=>({available:source!=='editor'||editorState!=='missing',logPath:'<local>/保存/'+source+'.log',modified:'2026-11-13T00:00:00Z',tail:source==='editor'&&['missing','no-preview'].includes(editorState)?'':'PREVIEW '+source+'\n保存',errors:[],truncated:true,downloadName:source==='editor'?'studio-errors.log':'LogOutput.txt'});
const jsonResponse=(value,status=200)=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});
window.fetch=async input=>{
 const url=new URL(input,'http://localhost');
 if(url.pathname.startsWith('/locales/'))return jsonResponse(CATALOGS[url.pathname.split('/').pop().replace('.json','')]);
 const source=url.searchParams.get('source');diagnosticsCalls.push({path:url.pathname,source});
 if(url.pathname==='/api/diagnostics'){
  if(holdPreview&&source==='editor'){const wait=holdPreview;holdPreview=null;await wait.promise;}
  if(source==='editor'&&editorState==='error')return jsonResponse({code:'diagnostics.readFailed'},500);
  return jsonResponse(previewFor(source));
 }
 if(url.pathname==='/api/diagnostics/download'){
  if(holdDownload){const wait=holdDownload;holdDownload=null;await wait.promise;}
  if(downloadState==='error')return jsonResponse({code:'diagnostics.readFailed'},500);
  if(downloadState==='missing')return jsonResponse({code:'diagnostics.editorUnavailable'},404);
  return new Response(downloadState==='empty'?'':source==='editor'?fullEditorLog:fullGameLog,{status:200,headers:{'Content-Type':'text/plain'}});
 }
 throw Error('Unexpected fixture request: '+input);
};
const exportedBlobs=new Map(),originalObjectURL=URL.createObjectURL.bind(URL);
URL.createObjectURL=blob=>{const url=originalObjectURL(blob);exportedBlobs.set(url,blob);return url;};
HTMLAnchorElement.prototype.click=function(){diagnosticsDownloads.push({name:this.download,data:exportedBlobs.get(this.href)});};
const deferred=()=>{let resolve;const promise=new Promise(done=>resolve=done);return {promise,resolve};};
