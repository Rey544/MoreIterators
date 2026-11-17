import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT=Path(__file__).resolve().parents[1]


class RainedErrorTranslations(unittest.TestCase):
    def test_rained_sync_errors_translate_in_english_and_preserve_room_and_path(self):
        chrome=shutil.which('chrome') or 'C:/Program Files/Google/Chrome/Application/chrome.exe'
        node=shutil.which('node')
        if not Path(chrome).is_file() or not node:self.skipTest('Chrome and Node are required')
        catalogs={language:json.loads((ROOT/'editor/locales'/(language+'.json')).read_text('utf-8')) for language in ('zh-CN','en')}
        script='const CATALOGS='+json.dumps(catalogs)+';\n'
        script+='window.fetch=async input=>new Response(JSON.stringify(CATALOGS[String(input).split("/").pop().replace(".json","")]),{status:200});\n'
        script+=(ROOT/'editor/i18n.js').read_text('utf-8')
        script+='''
(async()=>{
 try{
  await MI18n.ready;MI18n.setLocale('en',false);
  const cases=[
   ['房间地形或出口数据无效：PL_AI','Invalid room geometry or exit data: PL_AI'],
   ['Rained 渲染结果未更新，房间未同步：PL_AI','Rained did not update the rendered output. The room was not synced: PL_AI'],
   ['房间同步输出路径越界','Room sync output path is outside its allowed directory.'],
   ['房间同步回滚未完成：world/pl-rooms/PL_AI_1.png: permission denied','Room sync rollback could not finish: world/pl-rooms/PL_AI_1.png: permission denied'],
   ['Rained 启动失败，未跳过自动加载脚本：scripts/init.lua\\nSystem.NullReferenceException','Rained could not start. Automatic scripts were not skipped: scripts/init.lua\\nSystem.NullReferenceException']
  ];
  for(const [source,expected] of cases){
   const translated=MI18n.error({error:source});
   if(translated!==expected||/[\\u3400-\\u9fff]/.test(translated))throw Error('Untranslated room sync error: '+translated);
  }
  const authored='世界/我的房间.png';
  if(!MI18n.error({error:'房间同步回滚未完成：'+authored}).endsWith(authored))throw Error('Authored path changed');
  document.getElementById('result').textContent=JSON.stringify({ok:true,checks:cases.length+1});
 }catch(error){document.getElementById('result').textContent=JSON.stringify({ok:false,error:String(error.stack||error)});}
})();'''
        document='<!doctype html><html><head><meta charset="utf-8"></head><body><header></header><pre id="result">PENDING</pre><script>'+script+'</script></body></html>'
        with tempfile.TemporaryDirectory(prefix='mi-rained-errors-') as temporary:
            root=Path(temporary);page=root/'test.html';page.write_text(document,'utf-8')
            result=subprocess.run([node,str(ROOT/'tests/await_browser_result.mjs'),chrome,str(page),str(root/'profile')],capture_output=True,encoding='utf-8',timeout=60)
            self.assertEqual(result.returncode,0,result.stderr[-4000:])
            report=json.loads(result.stdout);self.assertTrue(report['ok'],report);self.assertEqual(report['checks'],6)


if __name__=='__main__':unittest.main()
