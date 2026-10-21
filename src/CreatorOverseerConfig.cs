using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text.RegularExpressions;
using UnityEngine;

namespace MoreIterators {
 // No native guide save data is involved in these project-owned cosmetic settings.
 public sealed class CreatorOverseerConfig {
  public bool enabled;
  public string id="",name="",ownerProjectId;public string[] rooms;public CreatorOverseerConfig[] guests=new CreatorOverseerConfig[0];
  public string ownerAbbreviation="";
  public Color[] bodyColors={Hex("#72E6C4")},tipColors={Hex("#B4FFF2")};
  public Color eyeWhite=Color.white,eyePupil=Color.black;
  public float lens=.35f,GateScene=.2f,Angry;
  static readonly HashSet<string> fields=new HashSet<string>{"enabled","ownerAbbreviation","bodyColors","tipColors","eyeWhite","eyePupil","probabilities","rooms","ownerProjectId","guests"};
  public static CreatorOverseerConfig Parse(string json){
   var result=new CreatorOverseerConfig();if(String.IsNullOrEmpty(json))return result;
   var data=Json.Deserialize(json) as Dictionary<string,object>;if(data==null)throw new ArgumentException("overseer must be an object");
   return Read(data,false);
  }
  static CreatorOverseerConfig Read(Dictionary<string,object> data,bool guest){
   var result=new CreatorOverseerConfig();
   foreach(var key in data.Keys)if(!(fields.Contains(key)&&(!guest||key!="guests"))&&!(guest&&(key=="id"||key=="name")))throw new ArgumentException("Unknown overseer field: "+key);
   object raw;
   if(guest){
    if(!data.TryGetValue("id",out raw)||!(raw is string)||!Regex.IsMatch((string)raw,"^[a-f0-9]{32}$"))throw new ArgumentException("Invalid overseer profile ID");result.id=(string)raw;
    if(!data.TryGetValue("name",out raw))throw new ArgumentException("Missing overseer profile name");
    result.name=DisplayText(raw,"profile name",60,false);result.rooms=new string[0];result.ownerProjectId="";
   }
   if(data.TryGetValue("ownerProjectId",out raw)){if(!(raw is string)||((string)raw)!=""&&!Regex.IsMatch((string)raw,"^[a-z][a-z0-9-]{0,47}$"))throw new ArgumentException("Invalid overseer owner project");result.ownerProjectId=(string)raw;}
   if(data.TryGetValue("rooms",out raw)){
    var list=raw as List<object>;if(list==null||list.Count>64)throw new ArgumentException("Invalid overseer room list");var names=new List<string>();
    foreach(var item in list){var room=item as string;if(room==null||!Regex.IsMatch(room,"^[A-Z0-9_]{1,80}$")||names.Contains(room))throw new ArgumentException("Invalid or duplicate overseer room");names.Add(room);}result.rooms=names.ToArray();
   }
   if(data.TryGetValue("guests",out raw)){
    var list=raw as List<object>;if(list==null||list.Count>16)throw new ArgumentException("Too many overseer profiles");var profiles=new List<CreatorOverseerConfig>();var ids=new HashSet<string>();
    foreach(var item in list){var child=item as Dictionary<string,object>;if(child==null)throw new ArgumentException("Invalid overseer profile");var profile=Read(child,true);if(!ids.Add(profile.id))throw new ArgumentException("Duplicate overseer profile ID");profiles.Add(profile);}result.guests=profiles.ToArray();
   }
   if(data.TryGetValue("enabled",out raw)){if(!(raw is bool))throw new ArgumentException("overseer.enabled must be boolean");result.enabled=(bool)raw;}
   if(data.TryGetValue("ownerAbbreviation",out raw))result.ownerAbbreviation=DisplayText(raw,"owner abbreviation",12,true);
   if(data.TryGetValue("bodyColors",out raw))result.bodyColors=Colors(raw,"bodyColors");
   if(data.TryGetValue("tipColors",out raw))result.tipColors=Colors(raw,"tipColors");
   if(data.TryGetValue("eyeWhite",out raw))result.eyeWhite=Hex(raw as string);
   if(data.TryGetValue("eyePupil",out raw))result.eyePupil=Hex(raw as string);
   if(data.TryGetValue("probabilities",out raw)){
    var probabilities=raw as Dictionary<string,object>;if(probabilities==null)throw new ArgumentException("overseer.probabilities must be an object");
    foreach(var pair in probabilities){float value=Probability(pair.Value,pair.Key);switch(pair.Key){case "lens":result.lens=value;break;case "GateScene":result.GateScene=value;break;case "Angry":result.Angry=value;break;default:throw new ArgumentException("Unsupported overseer native action: "+pair.Key);}}
   }
   return result;
  }
  static string DisplayText(object raw,string field,int limit,bool allowEmpty){
   var text=raw as string;if(text==null)throw new ArgumentException("Overseer "+field+" must be text");
   // Validate before trimming: whitespace must not hide controls or invalid Unicode.
   for(int i=0;i<text.Length;i++){
    char c=text[i];if(Char.IsControl(c)||c=='<'||c=='>')throw new ArgumentException("Invalid overseer "+field);
    if(Char.IsHighSurrogate(c)){if(i+1>=text.Length||!Char.IsLowSurrogate(text[++i]))throw new ArgumentException("Invalid overseer "+field+" Unicode");}
    else if(Char.IsLowSurrogate(c))throw new ArgumentException("Invalid overseer "+field+" Unicode");
   }
   text=text.Trim();int count=0;foreach(char c in text)if(!Char.IsLowSurrogate(c))count++;
   if(count>limit||!allowEmpty&&count==0)throw new ArgumentException("Overseer "+field+" must contain "+(allowEmpty?"0":"1")+" to "+limit+" characters");
   return text;
  }
  static float Probability(object value,string name){
   if(!(value is double)&&!(value is long)&&!(value is int)&&!(value is float))throw new ArgumentException("overseer probability must be numeric: "+name);
   double d=Convert.ToDouble(value,CultureInfo.InvariantCulture);if(Double.IsNaN(d)||Double.IsInfinity(d)||d<0||d>1)throw new ArgumentException("overseer probability must be between 0 and 1: "+name);return (float)d;
  }
  static Color[] Colors(object raw,string name){var list=raw as List<object>;if(list==null||list.Count<1||list.Count>2)throw new ArgumentException("overseer."+name+" needs one or two colors");var result=new Color[list.Count];for(int i=0;i<list.Count;i++)result[i]=Hex(list[i] as string);return result;}
  static Color Hex(string text){int rgb;if(text==null||text.Length!=7||text[0]!='#'||!Int32.TryParse(text.Substring(1),NumberStyles.AllowHexSpecifier,CultureInfo.InvariantCulture,out rgb))throw new ArgumentException("Overseer colors must use #RRGGBB");return new Color(((rgb>>16)&255)/255f,((rgb>>8)&255)/255f,(rgb&255)/255f,1f);}
  public static Color Gradient(Color[] colors,float t,float alpha){var c=colors.Length==1?colors[0]:Color.Lerp(colors[0],colors[1],Mathf.Clamp01(t));c.a=alpha;return c;}
 }
 // Tick only while an idle, alive player and an owned observer share a room.
 // Each 8-second opportunity rolls every channel independently, then chooses a passing one.
 public sealed class CreatorOverseerSchedule {
  public const int Interval=320,Duration=240;
  int wait=Interval,remaining;public string Active{get;private set;}
  public void Reset(){wait=Interval;remaining=0;Active=null;}
  static bool Passes(float probability,float sample){return probability>=1f||(probability>0f&&sample<probability);}
  public string Tick(CreatorOverseerConfig config,bool eligible,Func<float> random){
   if(!config.enabled||!eligible){Reset();return null;}
   if(remaining>0){if(--remaining==0){Active=null;wait=Interval;}return Active;}
   if(--wait>0)return null;wait=Interval;
   var choices=new List<string>();if(Passes(config.lens,random()))choices.Add("lens");if(Passes(config.GateScene,random()))choices.Add("GateScene");if(Passes(config.Angry,random()))choices.Add("Angry");
   if(choices.Count==0)return null;int index=Math.Min(choices.Count-1,(int)(random()*choices.Count));Active=choices[index];remaining=Duration;return Active;
  }
 }
}
