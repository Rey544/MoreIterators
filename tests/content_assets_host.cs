using System;
using System.IO;
using System.Collections.Generic;

namespace RWCustom {
 public static class Custom {public static string RootFolderDirectory(){return AssetManager.Root;}}
}

 
 
public static class AssetManager {
 public static string Root;
 public static string GetConsoleFilesSubfolder(){return "";}
 static IEnumerable<string> Roots(){
  if(!String.IsNullOrEmpty(Root))yield return Path.Combine(Root,"mergedmods");
  if(ModManager.ActiveMods!=null)for(int i=ModManager.ActiveMods.Count-1;i>=0;i--){
   var mod=ModManager.ActiveMods[i];
   if(mod.hasTargetedVersionFolder)yield return mod.TargetedPath;
   if(mod.hasNewestFolder)yield return mod.NewestPath;
   yield return mod.path;
  }
  if(!String.IsNullOrEmpty(Root))yield return Root;
 }
 public static string[] ListDirectory(string path,bool directories=false,bool includeAll=false,bool moddedOnly=false){
  var files=new List<string>();var names=new HashSet<string>();
  foreach(string root in Roots()){
   if(moddedOnly&&root==Root)continue;
   string directory=Path.Combine(root,path.ToLowerInvariant());if(!Directory.Exists(directory))continue;
   foreach(string file in directories?Directory.GetDirectories(directory):Directory.GetFiles(directory)){
    if(includeAll||names.Add(Path.GetFileName(file)))files.Add(file.ToLowerInvariant());
   }
  }
  return files.ToArray();
 }
 public static string ResolveFilePath(string path,bool skipMergedMods=false,bool skipConsoleFiles=false){
  foreach(string root in Roots()){
   if(skipMergedMods&&root==Path.Combine(Root,"mergedmods"))continue;
   string file=Path.Combine(root,path.ToLowerInvariant());if(File.Exists(file))return file;
  }
  return Path.Combine(Root,path.ToLowerInvariant());
 }
 public static List<string> ResolveAllFilePaths(string path){
  var files=new List<string>();
  string merged=Path.Combine(Root,"mergedmods",path.ToLowerInvariant());if(File.Exists(merged))files.Add(merged);
  if(ModManager.ActiveMods!=null)foreach(var mod in ModManager.ActiveMods){
   if(mod.hasTargetedVersionFolder){string file=Path.Combine(mod.TargetedPath,path.ToLowerInvariant());if(File.Exists(file))files.Add(file);}
   if(mod.hasNewestFolder){string file=Path.Combine(mod.NewestPath,path.ToLowerInvariant());if(File.Exists(file))files.Add(file);}
   string normal=Path.Combine(mod.path,path.ToLowerInvariant());if(File.Exists(normal))files.Add(normal);
  }
  string original=Path.Combine(Root,path.ToLowerInvariant());if(File.Exists(original))files.Add(original);
  return files;
 }
}
