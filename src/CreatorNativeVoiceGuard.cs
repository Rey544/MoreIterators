using System;
using System.Collections.Generic;

namespace MoreIterators {
 // Native reactions (for example ReactToHitWeapon) bypass CreatorSpeech. Filter
 // only iterator talk samples attached to an oracle owned by this runtime.
 public static class CreatorNativeVoiceGuard {
  static readonly List<Lifetime> active=new List<Lifetime>();
  static bool IsTalk(SoundID sound){
   return sound==SoundID.SS_AI_Talk_1||sound==SoundID.SS_AI_Talk_2||sound==SoundID.SS_AI_Talk_3||sound==SoundID.SS_AI_Talk_4||sound==SoundID.SS_AI_Talk_5||
    sound==SoundID.SL_AI_Talk_1||sound==SoundID.SL_AI_Talk_2||sound==SoundID.SL_AI_Talk_3||sound==SoundID.SL_AI_Talk_4||sound==SoundID.SL_AI_Talk_5;
  }
  static bool Muted(Oracle oracle){return !CreatorVoiceControl.Enabled||IteratorBehavior.HasCommunicationMark(oracle);}
  static void Stop(Oracle oracle,ChunkSoundEmitter emitter){
   if(oracle!=null&&oracle.oracleBehavior!=null&&Object.ReferenceEquals(oracle.oracleBehavior.voice,emitter))oracle.oracleBehavior.voice=null;
   emitter.volume=0;emitter.alive=false;emitter.Destroy();
  }
  public static void Install(List<Action> remove){
   On.Room.hook_PlaySound_SoundID_BodyChunk_bool_float_float_bool hook=Play;
   On.Room.PlaySound_SoundID_BodyChunk_bool_float_float_bool+=hook;
   remove.Add(delegate {
    On.Room.PlaySound_SoundID_BodyChunk_bool_float_float_bool-=hook;
    foreach(var lifetime in active.ToArray())lifetime.End();
   });
  }
  static ChunkSoundEmitter Play(On.Room.orig_PlaySound_SoundID_BodyChunk_bool_float_float_bool orig,Room room,SoundID sound,BodyChunk chunk,bool loop,float volume,float pitch,bool randomStart){
   var oracle=chunk==null?null:chunk.owner as Oracle;
   if(oracle==null||oracle.room!=room||!IsTalk(sound)||(!CreatorOracleLifecycle.Owns(oracle)&&!(oracle.oracleBehavior is IteratorBehavior)))return orig(room,sound,chunk,loop,volume,pitch,randomStart);
   bool mute=Muted(oracle);
   // Never return null: native reactions immediately set requireActiveUpkeep.
   // A zero-volume original call cannot leak its initial sample before cleanup.
   var emitter=orig(room,sound,chunk,loop,mute?0:volume,pitch,randomStart);
   if(emitter==null)return null;
   if(mute){Stop(oracle,emitter);return emitter;}
   var guard=new Lifetime(oracle,emitter);active.Add(guard);room.AddObject(guard);return emitter;
  }
  sealed class Lifetime:UpdatableAndDeletable,INotifyWhenRoomUnloaded {
   readonly Oracle oracle;readonly ChunkSoundEmitter emitter;
   public Lifetime(Oracle oracle,ChunkSoundEmitter emitter){this.oracle=oracle;this.emitter=emitter;}
   public override void Update(bool eu){
    base.Update(eu);
    if(emitter.slatedForDeletetion){Destroy();return;}
    if(oracle.slatedForDeletetion||oracle.room!=room||Muted(oracle))End();
   }
   public void RoomUnloaded(){End();}
   public void End(){Stop(oracle,emitter);Destroy();}
   public override void Destroy(){active.Remove(this);base.Destroy();}
  }
 }
}
