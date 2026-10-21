using System;
using System.Reflection;
using System.Text.RegularExpressions;
using Mono.Cecil;
using Mono.Cecil.Cil;
using MonoMod.Cil;
using MonoMod.Utils;

namespace MoreIterators {
 // Public, versioned protocol shared by independently compiled content runtimes.
 // A sibling may reuse only this exact static signature at the native mark store.
 public static class CreatorMarkGuard {
  public static bool HasMarkV1(RainWorldGame game){
   return game!=null&&game.IsStorySession&&game.GetStorySession!=null&&game.GetStorySession.saveState!=null&&game.GetStorySession.saveState.deathPersistentSaveData!=null&&game.GetStorySession.saveState.deathPersistentSaveData.theMark;
  }

  static bool KnownGuard(Instruction instruction){
   if(instruction.OpCode!=OpCodes.Call)return false;
   var method=instruction.Operand as MethodReference;
   if(method==null||method.HasThis||method.HasGenericParameters||method.Name!="HasMarkV1"||method.ReturnType.FullName!="System.Boolean"||method.Parameters.Count!=1||method.Parameters[0].ParameterType.FullName!=typeof(RainWorldGame).FullName||method.DeclaringType.Name!="CreatorMarkGuard")return false;
   string space=method.DeclaringType.Namespace;
   if(space!="MoreIterators"&&!Regex.IsMatch(space,"^IteratorContent_[a-f0-9]{12}$"))return false;
   try{
    var resolved=method.ResolveReflection() as MethodInfo;
    return resolved!=null&&resolved.IsPublic&&resolved.IsStatic&&!resolved.IsGenericMethod&&resolved.ReturnType==typeof(bool)&&resolved.GetParameters().Length==1&&resolved.GetParameters()[0].ParameterType==typeof(RainWorldGame);
   }catch{return false;}
  }

  public static bool TryApply(ILContext il,out bool reused){
   reused=false;var cursor=new ILCursor(il);
   if(cursor.TryGotoNext(MoveType.Before,
       i=>i.MatchCallvirt<RainWorldGame>("get_GetStorySession"),
       i=>i.MatchLdfld<StoryGameSession>("saveState"),
       i=>i.MatchLdfld<SaveState>("deathPersistentSaveData"),
       i=>i.MatchLdfld<DeathPersistentSaveData>("theMark"),
       i=>i.MatchStfld<SSOracleBehavior>("playerEnteredWithMark"))){
    cursor.RemoveRange(4);
    cursor.Emit(OpCodes.Call,typeof(CreatorMarkGuard).GetMethod("HasMarkV1",BindingFlags.Public|BindingFlags.Static));
    return true;
   }
   // MonoMod rebuilds from the original body after every install/removal. If an
   // earlier remaining runtime inserted this protocol, retain its call; otherwise
   // the first remaining runtime installs its own guard from the native pattern.
   cursor=new ILCursor(il);
   if(cursor.TryGotoNext(MoveType.Before,KnownGuard,i=>i.MatchStfld<SSOracleBehavior>("playerEnteredWithMark"))){reused=true;return true;}
   return false;
  }
 }
}
