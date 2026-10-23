using System;
using System.IO;
using System.Collections.Generic;

namespace MoreIterators {
 // A listener preference, separate from authored projects and preview commands.
 // Content exports use their own RuntimePaths directory and the same F8 control.
 public static class CreatorVoiceControl {
  static string loadedFile;
  static bool enabled=true;
  static string FilePath {get{return Path.Combine(RuntimePaths.DataDirectory,"voice-control.json");}}
  public static bool Enabled {get{Load();return enabled;}}
  static void Load(){
   string file=FilePath;if(file==loadedFile)return;loadedFile=file;enabled=true;
   try{if(File.Exists(file)){var data=Json.Deserialize(File.ReadAllText(file)) as Dictionary<string,object>;object value;if(data!=null&&data.TryGetValue("enabled",out value)&&value is bool)enabled=(bool)value;}}
   catch(Exception error){MiDiagnostics.Report("MI-VOICE-CONTROL","CreatorVoiceControl.Load",error,file);}
  }
  public static void Toggle(){
   bool next=!Enabled;string file=FilePath;
   // Preserve future preference fields and do not replace malformed files.
   var data=File.Exists(file)?Json.Deserialize(File.ReadAllText(file)) as Dictionary<string,object>:new Dictionary<string,object>();
   if(data==null)throw new InvalidDataException("Voice preferences must be a JSON object.");
   data["enabled"]=next;Directory.CreateDirectory(Path.GetDirectoryName(file));
   string temporary=file+"."+Guid.NewGuid().ToString("N")+".tmp";
   try{File.WriteAllText(temporary,Json.Serialize(data));if(File.Exists(file))File.Replace(temporary,file,null);else File.Move(temporary,file);}
   finally{if(File.Exists(temporary))File.Delete(temporary);}
   enabled=next;
  }
 }
}
