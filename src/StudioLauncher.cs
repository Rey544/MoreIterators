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
 public static string ResolvePython(string editor,string configured){
  if(!String.IsNullOrEmpty(configured)&&File.Exists(configured))return configured;
  if(!String.IsNullOrEmpty(editor)){
   string runtime=Path.GetFullPath(Path.Combine(editor,"..","runtime","python313"));
   foreach(string file in new[]{"pythonw.exe","python.exe"}){
    string executable=Path.Combine(runtime,file);
    if(File.Exists(executable))return executable;
   }
  }
  throw Visible(new FileNotFoundException(UiText.Get("The bundled Python runtime could not be found. Check that the mod download is complete.")));
 }
 public static ProcessStartInfo StartInfo(string editor,string python,string page,string project){
  if(page!="appearance"&&page!="dialogue"&&page!="pearls"&&page!="broadcasts")throw Visible(new ArgumentException(UiText.Get("Unknown editor page.")));
  if(!String.IsNullOrEmpty(project)&&!System.Text.RegularExpressions.Regex.IsMatch(project,"^[a-z][a-z0-9-]{0,47}$"))throw Visible(new ArgumentException(UiText.Get("Invalid project ID.")));
  string script=Path.Combine(editor,LauncherFileName);
  if(!File.Exists(script))throw Visible(new FileNotFoundException(UiText.Get("The web editor launcher could not be found. Check editorDirectory in your local moreiterators.paths.json.")));
  python=ResolvePython(editor,python);
  var start=new ProcessStartInfo(python,"-B \""+script+"\" --page "+page+(String.IsNullOrEmpty(project)?"":" --project "+project)){WorkingDirectory=editor,UseShellExecute=false,CreateNoWindow=true,WindowStyle=ProcessWindowStyle.Hidden};
  if(Environment.OSVersion.Platform==PlatformID.Win32NT){
   using(var game=Process.GetCurrentProcess())start.Arguments+=" --game-pid "+game.Id.ToString(System.Globalization.CultureInfo.InvariantCulture)+" --game-start "+game.StartTime.ToUniversalTime().ToFileTimeUtc().ToString(System.Globalization.CultureInfo.InvariantCulture);
  }
  // The game and browser must read one library even when the configured editor
  // points at a development checkout or has moved since its last registration.
  // This core-only launcher is deliberately excluded from standalone exports.
  var data=Directory.GetParent(Path.GetFullPath(RuntimePaths.DataDirectory));
  if(data==null)throw new InvalidOperationException("The editor runtime directory must have a parent data directory.");
  start.EnvironmentVariables["MORE_ITERATORS_DATA"]=data.FullName;
  return start;
 }
 public static void Open(Menu.MainMenu menu,string page,string project=""){
  UiText.Use(menu==null?null:menu.manager.rainWorld);
  try{
   string editor="",python="",config=Path.Combine(BepInEx.Paths.ConfigPath,"moreiterators.paths.json");
   if(File.Exists(config)){
    var settings=Json.Deserialize(File.ReadAllText(config)) as Dictionary<string,object>;
    if(settings!=null){editor=IteratorCatalog.Text(settings,"editorDirectory");python=IteratorCatalog.Text(settings,"pythonExecutable");}
   }
   if(String.IsNullOrEmpty(editor)||!File.Exists(Path.Combine(editor,LauncherFileName))){
    var data=Directory.GetParent(RuntimePaths.DataDirectory);
    if(data!=null&&data.Parent!=null&&File.Exists(Path.Combine(data.Parent.FullName,"editor",LauncherFileName)))editor=Path.Combine(data.Parent.FullName,"editor");
    else foreach(var mod in ModManager.ActiveMods)if(mod.id=="moreiterators.core")editor=Path.Combine(mod.path,"editor");
   }
   using(var child=Process.Start(StartInfo(editor,python,page,project))){
    if(child==null)throw new InvalidOperationException("The editor launcher did not start.");
    using(var game=Process.GetCurrentProcess())MiDiagnostics.Info("editor.launch","launcherPid="+child.Id+"; gamePid="+game.Id);
   }
  }catch(Exception error){
    MiDiagnostics.Report("MI_STUDIO_LAUNCH","StudioLauncher.Open",error,"page="+page+"; project="+project);
    UnityEngine.Debug.LogWarning("[More Iterators] Studio launch: "+error.Message);
    string detail=error.Data[UiMessage] as string??UiText.Get("The launcher failed. See MI_STUDIO_LAUNCH in the log for details.");
    if(menu!=null)menu.manager.ShowDialog(new Menu.DialogNotify(UiText.Format("Could not open the web editor: {0}",detail),new Vector2(620,240),menu.manager,delegate{}));
  }
 }
}
}
