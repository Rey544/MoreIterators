using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Web.Script.Serialization;
using Mono.Cecil;
using Mono.Cecil.Cil;
using MonoMod.RuntimeDetour;
using MoreIterators;

public static class ModManager {
 public static bool InitializationScreenFinished=true;
 public static List<Mod> ActiveMods=new List<Mod>();
 public sealed class Mod {public string id,path,TargetedPath,NewestPath;public bool enabled=true,hasTargetedVersionFolder,hasNewestFolder;}
}
public static class Json {
 public static object Deserialize(string value){return new JavaScriptSerializer().DeserializeObject(value);}
}
namespace MoreIterators {
 public static class ContentAssets {
  public static int Generation;
  public static string ResolveOwnedFile(string owner,string relative){foreach(var mod in ModManager.ActiveMods)if(mod.id==owner)return Path.Combine(mod.path,relative);return null;}
 }
 public static class MiDiagnostics {
  public static void Info(string code,string detail){}
  public static void Report(string code,string area,Exception error,string detail){throw new Exception(code+": "+detail,error);}
 }
}
public static class LegacyCatalogCacheCheck {
 static int assertions,calls;static double now;static int generation;static bool available;
 static List<Dictionary<string,object>> next;
 static string gameRoot,fixtureRoot;
 static void Assert(bool value,string message){assertions++;if(!value)throw new Exception("FAILED: "+message);}
 static List<Dictionary<string,object>> Value(string value){return new List<Dictionary<string,object>>{new Dictionary<string,object>{{"name",value}}};}
 static LegacyCatalogCache.Cache Fresh(){calls=0;now=20;generation=1;available=true;next=Value("a");return new LegacyCatalogCache.Cache(delegate{return now;},delegate{return generation;},delegate{return available;});}
 static List<Dictionary<string,object>> Original(){calls++;return next;}
 static void CacheBehavior(){
  var cache=Fresh();var first=cache.Invoke(Original);next=Value("b");now+=.249;
  Assert(ReferenceEquals(cache.Invoke(Original),first)&&calls==1,"success retains the original reference inside TTL");
  now=20.25;Assert(ReferenceEquals(cache.Invoke(Original),next)&&calls==2,"exact expiry runs original");
  generation++;next=Value("context");Assert(ReferenceEquals(cache.Invoke(Original),next)&&calls==3,"generation change invalidates immediately");
  available=false;cache.Invoke(Original);cache.Invoke(Original);Assert(calls==5,"unavailable owner bypasses caching");
  available=true;cache.Invoke(Original);cache.Invoke(Original);Assert(calls==6,"owner recovery can cache again");
  now+=.25;next=new List<Dictionary<string,object>>();Assert(ReferenceEquals(cache.Invoke(Original),next),"empty failure does not return prior success");
  cache.Invoke(Original);Assert(calls==8,"empty result retries on the next call");
  next=Value("recovered");cache.Invoke(Original);now+=.25;
  var sentinel=new IOException("sentinel");bool propagated=false;
  try{cache.Invoke(delegate{throw sentinel;});}catch(IOException error){propagated=ReferenceEquals(error,sentinel);}
  Assert(propagated,"original exception propagated unchanged");next=Value("after throw");Assert(ReferenceEquals(cache.Invoke(Original),next)&&calls==10,"exception cannot resurrect stale success");
  now-=1;cache.Invoke(Original);Assert(calls==11,"backwards clock expires prior success");
  cache.Clear();cache.Invoke(Original);Assert(calls==12,"explicit clear removes cached reference");
  cache=Fresh();cache.Invoke(delegate{calls++;generation++;return next;});cache.Invoke(Original);Assert(calls==2,"context changed during original is not cached");
  cache=Fresh();cache.Invoke(delegate{calls++;available=false;return next;});available=true;cache.Invoke(Original);Assert(calls==2,"availability changed during original is not cached");
  cache=Fresh();next=null;Assert(cache.Invoke(Original)==null&&cache.Invoke(Original)==null&&calls==2,"null preserves original return and retries");
  cache=Fresh();available=false;cache.Invoke(Original);cache.Invoke(Original);available=true;cache.Invoke(Original);cache.Invoke(Original);Assert(calls==3,"startup unavailable path remains live");
  calls=0;next=Value("unavailable original");
  cache=new LegacyCatalogCache.Cache(delegate{throw new InvalidOperationException("clock unavailable");},delegate{throw new InvalidOperationException("generation unavailable");},delegate{return false;});
  Assert(ReferenceEquals(cache.Invoke(Original),next)&&calls==1,"unavailable branch invokes original without reading generation or clock");
 }
 [MethodImpl(MethodImplOptions.NoInlining)] static List<Dictionary<string,object>> HookTarget(){return Original();}
 static void RealHook(){
  var cache=Fresh();var method=typeof(LegacyCatalogCacheCheck).GetMethod("HookTarget",BindingFlags.Static|BindingFlags.NonPublic);
  using(var hook=new Hook(method,new Func<LegacyCatalogCache.Original,List<Dictionary<string,object>>>(cache.Invoke))){var first=HookTarget();next=Value("new");Assert(ReferenceEquals(HookTarget(),first)&&calls==1,"actual Hook caches original");now+=.25;Assert(ReferenceEquals(HookTarget(),next)&&calls==2,"actual Hook expires");}
  HookTarget();HookTarget();Assert(calls==4,"disposing Hook restores original");
 }
 static Assembly Resolve(object sender,ResolveEventArgs args){
  string name=new AssemblyName(args.Name).Name+".dll";
  foreach(string directory in new[]{args.RequestingAssembly==null?AppDomain.CurrentDomain.BaseDirectory:Path.GetDirectoryName(args.RequestingAssembly.Location),AppDomain.CurrentDomain.BaseDirectory,Path.Combine(gameRoot,"RainWorld_Data/Managed"),Path.Combine(gameRoot,"BepInEx/core"),Path.Combine(gameRoot,"BepInEx/plugins")}){
   string file=Path.Combine(directory,name);if(File.Exists(file))return Assembly.LoadFrom(file);
  }
  return null;
 }
 static void PrintFingerprints(string file){
  var assembly=Assembly.LoadFrom(file);string name=assembly.GetName().Name;
  var paths=assembly.GetType(name+".RuntimePaths");string owner=(string)paths.GetField("ModId").GetRawConstantValue();
  foreach(string qualified in new[]{"IteratorCatalog.Projects","RuntimePaths.TryContentRoot","ContentAssets.ResolveOwnedFile"}){
   int dot=qualified.LastIndexOf('.');var method=assembly.GetType(name+"."+qualified.Substring(0,dot)).GetMethod(qualified.Substring(dot+1),BindingFlags.Public|BindingFlags.Static);
   Console.WriteLine(name+" "+qualified+" "+LegacyCatalogCache.Fingerprint(method,name,owner));
  }
 }
 static int fixtureNumber;
 static TypeDefinition FixtureType(ModuleDefinition module,string name){foreach(var type in module.Types)if(type.Name==name)return type;throw new Exception("Fixture type missing: "+name);}
 static Assembly Fixture(string source,string mutation,out ModManager.Mod owner){
  string suffix=(++fixtureNumber).ToString("x12"),name="IteratorContent_"+suffix,id="mi.legacy.fixture."+fixtureNumber;
  string runtimeVersion=mutation=="version030"?"0.3.0":mutation=="version040"?"0.4.0":"0.4.1";
  string root=Path.Combine(fixtureRoot,"fixture-"+fixtureNumber),plugins=Path.Combine(root,"plugins");Directory.CreateDirectory(plugins);
  using(var data=AssemblyDefinition.ReadAssembly(source)){
   string oldName=data.Name.Name;data.Name.Name=name;data.Name.Version=new Version(runtimeVersion+".0");data.MainModule.Name=name+".dll";
   foreach(var type in data.MainModule.Types){
    if(type.Namespace==oldName)type.Namespace=name;
    foreach(var field in type.Fields)if(field.Name=="ModId")field.Constant=id;
    foreach(var attribute in type.CustomAttributes)if(attribute.AttributeType.FullName=="BepInEx.BepInPlugin")attribute.ConstructorArguments[0]=new CustomAttributeArgument(data.MainModule.TypeSystem.String,mutation=="guid"?"not.the.owner":id);
    foreach(var method in type.Methods)if(method.HasBody)foreach(var instruction in method.Body.Instructions){
     if(instruction.OpCode.Code!=Code.Ldstr)continue;
     string literal=(string)instruction.Operand;
     if(literal=="mi.legacy.fixture")instruction.Operand=id;
     else if(literal=="[More Iterators content mi.legacy.fixture] Cannot load registry at ")instruction.Operand="[More Iterators content "+id+"] Cannot load registry at ";
    }
   }
   if(mutation=="projects"||mutation=="root"||mutation=="resolve"){
    string target=mutation=="projects"?"IteratorCatalog":mutation=="root"?"RuntimePaths":"ContentAssets";
    string methodName=mutation=="projects"?"Projects":mutation=="root"?"TryContentRoot":"ResolveOwnedFile";
    foreach(var method in FixtureType(data.MainModule,target).Methods)if(method.Name==methodName)method.Body.Instructions.Insert(0,Instruction.Create(OpCodes.Nop));
   }
   if(mutation=="marker")FixtureType(data.MainModule,"IteratorCatalog").Fields.Add(new FieldDefinition("ProjectsCacheVersion",Mono.Cecil.FieldAttributes.Public|Mono.Cecil.FieldAttributes.Static|Mono.Cecil.FieldAttributes.Literal|Mono.Cecil.FieldAttributes.HasDefault,data.MainModule.TypeSystem.Int32){Constant=1});
   if(mutation=="literal")foreach(var field in FixtureType(data.MainModule,"RuntimePaths").Fields)if(field.Name=="ModId")field.Attributes=Mono.Cecil.FieldAttributes.Public|Mono.Cecil.FieldAttributes.Static;
   if(mutation=="foreign"){
    string foreignName="ForeignCatalogue"+fixtureNumber;
    using(var bytes=new MemoryStream()){
     data.Write(bytes);bytes.Position=0;
     using(var foreign=AssemblyDefinition.ReadAssembly(bytes)){foreign.Name.Name=foreignName;foreign.MainModule.Name=foreignName+".dll";foreign.Write(Path.Combine(plugins,foreignName+".dll"));}
    }
    var scope=new AssemblyNameReference(foreignName,new Version(0,4,1,0));data.MainModule.AssemblyReferences.Add(scope);
    var foreignType=new TypeReference(name,"RuntimePaths",data.MainModule,scope);
    var foreignMethod=new MethodReference("TryContentRoot",data.MainModule.TypeSystem.Boolean,foreignType){HasThis=false};
    foreignMethod.Parameters.Add(new ParameterDefinition(new ByReferenceType(data.MainModule.TypeSystem.String)));
    foreach(var method in FixtureType(data.MainModule,"IteratorCatalog").Methods)if(method.Name=="Projects")foreach(var instruction in method.Body.Instructions){
     var called=instruction.Operand as MethodReference;if(called!=null&&called.Name=="TryContentRoot")instruction.Operand=foreignMethod;
    }
   }
   data.Write(Path.Combine(plugins,name+".dll"));
  }
  File.WriteAllText(Path.Combine(root,"content-manifest.json"),"{\"schema\":\"moreiterators.playback-export.v1\",\"independentMod\":true,\"runtimeVersion\":\""+runtimeVersion+"\"}");
  owner=new ModManager.Mod{id=id,path=root};ModManager.ActiveMods.Add(owner);
  return Assembly.LoadFrom(Path.Combine(plugins,name+".dll"));
 }
 static bool Identified(Assembly assembly){ModManager.Mod owner;MethodInfo method;string reason;return LegacyCatalogCache.Identify(assembly,out owner,out method,out reason);}
 static void IdentityAndLifecycle(string source){
  ModManager.ActiveMods.Clear();ModManager.Mod owner;
  var known=Fixture(source,"",out owner);Assert(Identified(known),"known legacy template accepts normalized generated name and owner");
  ModManager.Mod secondOwner;var second=Fixture(source,"",out secondOwner);Assert(Identified(second),"independent second export accepts without any user-specific ID");
  foreach(string version in new[]{"version030","version040"}){ModManager.Mod earlierOwner;var earlier=Fixture(source,version,out earlierOwner);Assert(Identified(earlier),"verified earlier runtime family "+version+" is accepted");earlierOwner.enabled=false;}
  foreach(string mutation in new[]{"projects","root","resolve","marker","guid","literal","foreign"}){
   ModManager.Mod ignored;var changed=Fixture(source,mutation,out ignored);Assert(!Identified(changed),"reject "+mutation+" mutation");ignored.enabled=false;
  }
  owner.enabled=false;Assert(!Identified(known),"disabled owner is ineligible");owner.enabled=true;
  string manifest=Path.Combine(owner.path,"content-manifest.json"),valid=File.ReadAllText(manifest);
  foreach(string invalid in new[]{valid.Replace("true","false"),valid.Replace("playback-export.v1","another-format"),valid.Replace("0.4.1","0.4.2"),valid.Replace("0.4.1","0.3.0")}){
   File.WriteAllText(manifest,invalid);Assert(!Identified(known),"reject manifest identity/version mismatch");
  }
  File.Delete(manifest);Assert(!Identified(known),"manifest required");File.WriteAllText(manifest,valid);
  Assert(!LegacyCatalogCache.RuntimeName("ThirdParty_000000000001")&&!LegacyCatalogCache.RuntimeName("IteratorContent_00000000000z")&&!LegacyCatalogCache.RuntimeName("IteratorContent_000000000001_extra"),"unrelated or malformed assembly names are not candidates");
  Assert(!LegacyCatalogCache.OwnedPlugin(Path.Combine(owner.path,"plugins-evil/runtime.dll"),owner),"plugin directory boundary prevents prefix match");
  owner.hasTargetedVersionFolder=true;owner.TargetedPath=Path.Combine(owner.path,"target");
  Assert(LegacyCatalogCache.OwnedPlugin(Path.Combine(owner.TargetedPath,"plugins/runtime.dll"),owner),"declared targeted plugin folder is eligible");
  owner.hasTargetedVersionFolder=false;Assert(!LegacyCatalogCache.OwnedPlugin(Path.Combine(owner.TargetedPath,"plugins/runtime.dll"),owner),"undeclared targeted folder is ineligible");
  LegacyCatalogCache.Refresh();Assert(LegacyCatalogCache.InstalledCount==2,"Refresh hooks two known exports only");
  LegacyCatalogCache.Refresh();Assert(LegacyCatalogCache.InstalledCount==2,"Refresh does not duplicate hooks");
  LegacyCatalogCache.RemoveDisabled(new[]{owner});Assert(LegacyCatalogCache.InstalledCount==1&&owner.enabled,"disabled-event removal works while ActiveMods is stale");
  owner.enabled=false;LegacyCatalogCache.Refresh();Assert(LegacyCatalogCache.InstalledCount==1,"disabled owner is not reattached");
  owner.enabled=true;LegacyCatalogCache.Refresh();Assert(LegacyCatalogCache.InstalledCount==2,"reenabled known owner can reattach");
  LegacyCatalogCache.Shutdown();LegacyCatalogCache.Shutdown();Assert(LegacyCatalogCache.InstalledCount==0,"Shutdown releases all hooks and is idempotent");
 }
 public static int Main(string[] args){
  try{gameRoot=args[0];AppDomain.CurrentDomain.AssemblyResolve+=Resolve;
   if(args[1]=="fingerprints"){for(int i=2;i<args.Length;i++)PrintFingerprints(args[i]);return 0;}
   fixtureRoot=args[1];CacheBehavior();RealHook();IdentityAndLifecycle(args[2]);
   Console.WriteLine("PASS "+assertions+" legacy catalogue assertions");return 0;
  }catch(Exception error){Console.Error.WriteLine(error);return 1;}
 }
}
