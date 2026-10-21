namespace MoreIterators {
using System;
using System.IO;
using System.Collections.Generic;
using System.Diagnostics;
using UnityEngine;

// Core and content menus share the independent local editor bootstrap.
public static class StudioLauncher {
 internal const string LauncherFileName="studio_launcher.py";
 const string UiMessage="MoreIterators.UiMessage";
 static Exception Visible(Exception error){error.Data[UiMessage]=error.Message;return error;}
 public static ProcessStartInfo StartInfo(string editor,string python,string page,string project){
  if(page!="appearance"&&page!="dialogue"&&page!="pearls"&&page!="broadcasts")throw Visible(new ArgumentException(UiText.Get("game.studio.unknown_page")));
  if(!String.IsNullOrEmpty(project)&&!System.Text.RegularExpressions.Regex.IsMatch(project,"^[a-z][a-z0-9-]{0,47}$"))throw Visible(new ArgumentException(UiText.Get("game.studio.invalid_project")));
  string script=Path.Combine(editor,LauncherFileName);
  if(!File.Exists(script))throw Visible(new FileNotFoundException(UiText.Get("game.studio.launcher_missing")));
  if(!File.Exists(python))throw Visible(new FileNotFoundException(UiText.Get("game.studio.python_missing")));
  return new ProcessStartInfo(python,"-B \""+script+"\" --page "+page+(String.IsNullOrEmpty(project)?"":" --project "+project)){WorkingDirectory=editor,UseShellExecute=false,CreateNoWindow=true,WindowStyle=ProcessWindowStyle.Hidden};
 }
 public static void Open(Menu.MainMenu menu,string page,string project=""){
  UiText.Use(menu==null?null:menu.manager.rainWorld);
  try{
   string editor="",python="",config=Path.Combine(BepInEx.Paths.ConfigPath,"moreiterators.paths.json");
   if(File.Exists(config)){
    var settings=Json.Deserialize(File.ReadAllText(config)) as Dictionary<string,object>;
    if(settings!=null){editor=IteratorCatalog.Text(settings,"editorDirectory");python=IteratorCatalog.Text(settings,"pythonExecutable");}
   }
   if(String.IsNullOrEmpty(editor)){
    var data=Directory.GetParent(RuntimePaths.DataDirectory);
    if(data!=null&&data.Parent!=null&&File.Exists(Path.Combine(data.Parent.FullName,"editor",LauncherFileName)))editor=Path.Combine(data.Parent.FullName,"editor");
    else foreach(var mod in ModManager.ActiveMods)if(mod.id=="moreiterators.core")editor=Path.Combine(mod.path,"editor");
   }
   if(String.IsNullOrEmpty(python))throw Visible(new InvalidOperationException(UiText.Get("game.studio.python_unconfigured")));
   Process.Start(StartInfo(editor,python,page,project));
  }catch(Exception error){
    MiDiagnostics.Report("MI_STUDIO_LAUNCH","StudioLauncher.Open",error,"page="+page+"; project="+project);
    UnityEngine.Debug.LogWarning("[More Iterators] Studio launch: "+error.Message);
    string detail=error.Data[UiMessage] as string??UiText.Get("game.studio.unexpected");
    if(menu!=null)menu.manager.ShowDialog(new Menu.DialogNotify(UiText.Format("game.studio.failed",detail),new Vector2(620,240),menu.manager,delegate{}));
  }
 }
}
}
