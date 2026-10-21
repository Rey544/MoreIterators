namespace MoreIterators {
using System;
using System.Runtime.CompilerServices;

[Serializable] public sealed class CreatorVoiceDesign {
 public bool enabled=false,unmarkedOnly=false,repeat=true,reverse=true,split=true;
 public string bank="pebbles";
 public float speed=1,pitch=1,volume=.35f,echo=0,muffle=0,electric=0,chaos=0;
 public int shortWeight=50,mediumWeight=35,longWeight=15;
 public static CreatorVoiceDesign Safe(CreatorVoiceDesign source){
  if(source==null)return new CreatorVoiceDesign();
  return new CreatorVoiceDesign{enabled=source.enabled,unmarkedOnly=source.unmarkedOnly,bank=source.bank=="moon"?"moon":"pebbles",
   speed=Number(source.speed,.25f,3f,1),pitch=Number(source.pitch,.2f,3f,1),volume=Number(source.volume,0,1,.35f),
   echo=Number(source.echo,0,1,0),muffle=Number(source.muffle,0,1,0),electric=Number(source.electric,0,1,0),chaos=Number(source.chaos,0,1,0),repeat=source.repeat,reverse=source.reverse,split=source.split,
   shortWeight=Math.Max(0,Math.Min(100,source.shortWeight)),mediumWeight=Math.Max(0,Math.Min(100,source.mediumWeight)),longWeight=Math.Max(0,Math.Min(100,source.longWeight))};
 }
 static float Number(float value,float min,float max,float fallback){return Single.IsNaN(value)||Single.IsInfinity(value)?fallback:Math.Max(min,Math.Min(max,value));}
}

// Uses native SoundIDs through the game's microphone/volume path. No extracted
// voice recordings are redistributed and the global game RNG is not consumed.
public sealed class CreatorVoice {
 sealed class Slot {public CreatorVoice owner;}
 // Encounter updates can stop ticking speech during an action or editor pause.
 // Native OracleBehavior keeps its voice emitter alive independently, so the
 // sound needs its own bounded room lifetime rather than relying on that upkeep.
 sealed class Guard:UpdatableAndDeletable,INotifyWhenRoomUnloaded {
  readonly CreatorVoice owner;
  public Guard(CreatorVoice owner){this.owner=owner;}
  public override void Update(bool eu){base.Update(eu);owner.CheckLifetime();}
  public void RoomUnloaded(){owner.Stop();}
 }
 static readonly ConditionalWeakTable<Oracle,Slot> slots=new ConditionalWeakTable<Oracle,Slot>();
 readonly Oracle oracle;
 CreatorVoiceDesign source,settings;ChunkSoundEmitter emitter;
 Room speakingRoom;Guard guard;int lastTick;
 readonly CreatorVoiceEffects effects=new CreatorVoiceEffects();CreatorVoiceSequence sequence;CreatorVoiceNote note;
 int elapsed,index;bool unmarked,active;
 public CreatorVoice(Oracle oracle):this(oracle,Environment.TickCount){}
 internal CreatorVoice(Oracle oracle,int seed){this.oracle=oracle;}
 public void Begin(CreatorDialogueLine line,bool withoutMark){
  Stop();if(line==null||String.IsNullOrWhiteSpace(line.text)||oracle==null||oracle.slatedForDeletetion||oracle.room==null||oracle.room.game==null)return;
  unmarked=withoutMark;settings=null;Refresh();if(!Enabled)return;
  var slot=slots.GetValue(oracle,delegate(Oracle key){return new Slot();});
  if(slot.owner!=null&&slot.owner!=this)slot.owner.Stop();slot.owner=this;
  // Do not keep babbling throughout a long post-line hold. At most twelve
  // seconds of utterance; every path still stops at the actual line boundary.
  sequence=CreatorVoiceSequence.Make(line.text,settings);if(sequence.notes.Count==0)return;
  active=true;elapsed=-1;index=0;note=null;speakingRoom=oracle.room;lastTick=speakingRoom.game.clock;
  guard=new Guard(this);speakingRoom.AddObject(guard);
 }
 void Refresh(){
  var design=IteratorDesign.ForRoom(oracle.room);var next=design==null?null:design.voice;
  if(settings==null||!Object.ReferenceEquals(next,source)){source=next;settings=CreatorVoiceDesign.Safe(next);}
 }
 bool Enabled{get{return settings!=null&&settings.enabled&&(!settings.unmarkedOnly||unmarked)&&settings.volume>0;}}
 bool Available(){
  if(oracle==null||oracle.slatedForDeletetion||oracle.room==null||oracle.room!=speakingRoom||oracle.room.game==null){Stop();return false;}
  Refresh();if(!Enabled||!Visible()){Stop();return false;}return true;
 }
 void CheckLifetime(){
  if(!active||!Available())return;
  if(CreatorRuntime.Paused){Pause();lastTick=speakingRoom.game.clock;return;}
  if(speakingRoom.game.clock-lastTick>2)Stop();
 }
 public void Tick(bool showing,bool paused){
  if(!active)return;
  if(!showing){Stop();return;}if(!Available())return;
  lastTick=speakingRoom.game.clock;
  if(paused){Pause();return;}
  if(++elapsed>=sequence.ticks){Stop();return;}
  if(note!=null&&elapsed>=note.start+note.ticks){StopEmitter();note=null;}
  if(note!=null){
   if(emitter!=null){
    try{effects.Seek(emitter,note.offset);}catch(Exception error){Stop();MiDiagnostics.Report("MI-VOICE-PLAY","CreatorVoice.Seek",error,"bank="+settings.bank);return;}
    // Release filters before a naturally ending source returns to the game's pool.
    if(emitter.slatedForDeletetion||effects.NearEnd(emitter)){StopEmitter();return;}
    emitter.alive=true;emitter.pitch=note.pitch;
    float fade=Math.Min(1f,Math.Min((elapsed-note.start)/2f,(note.start+note.ticks-elapsed)/2f));
    emitter.volume=settings.volume*Math.Max(0,fade);
    try{effects.Update(emitter,settings);}catch(Exception error){Stop();MiDiagnostics.Report("MI-VOICE-PLAY","CreatorVoice.Effects",error,"bank="+settings.bank);}
   }
   return;
  }
  if(index>=sequence.notes.Count||elapsed<sequence.notes[index].start)return;
  note=sequence.notes[index++];
  try{
   emitter=oracle.room.PlaySound(Sample(settings.bank,note.sample),oracle.firstChunk,false,0,note.pitch);
   if(emitter!=null){emitter.requireActiveUpkeep=true;emitter.alive=true;effects.Seek(emitter,note.offset);if(oracle.oracleBehavior!=null)oracle.oracleBehavior.voice=emitter;}
  }catch(Exception error){Stop();MiDiagnostics.Report("MI-VOICE-PLAY","CreatorVoice.Tick",error,"bank="+settings.bank);}
 }
 void Pause(){StopEmitter();if(note!=null){elapsed=note.start-1;index=Math.Max(0,index-1);note=null;}}
 bool Visible(){var cameras=oracle.room.game.cameras;if(cameras==null)return false;foreach(var camera in cameras)if(camera!=null&&camera.room==oracle.room)return true;return false;}
 public void Stop(){
  StopEmitter();active=false;sequence=null;note=null;index=elapsed=0;
  if(guard!=null){guard.Destroy();guard=null;}speakingRoom=null;
  Slot slot;if(oracle!=null&&slots.TryGetValue(oracle,out slot)&&slot.owner==this)slot.owner=null;
 }
 void StopEmitter(){
  effects.Clear();if(emitter==null)return;
  if(oracle!=null&&oracle.oracleBehavior!=null&&Object.ReferenceEquals(oracle.oracleBehavior.voice,emitter))oracle.oracleBehavior.voice=null;
  emitter.volume=0;emitter.alive=false;emitter.Destroy();emitter=null;
 }
 internal static int NextSample(Random random,int previous){int pick=random.Next(previous<0?5:4);return previous>=0&&pick>=previous?pick+1:pick;}
 internal static int VoiceTicks(CreatorVoiceDesign settings,Random random){
  int sum=settings.shortWeight+settings.mediumWeight+settings.longWeight;
  int choice=sum>0?random.Next(sum):0;
  int low,high;
  if(sum==0||choice<settings.shortWeight){low=5;high=10;}
  else if(choice<settings.shortWeight+settings.mediumWeight){low=11;high=21;}
  else {low=22;high=39;}
  return Math.Max(3,(int)Math.Round(random.Next(low,high)/settings.speed));
 }
 internal static int GapTicks(CreatorVoiceDesign settings,Random random){return Math.Max(1,(int)Math.Round(random.Next(3,9)/settings.speed));}
 static SoundID Sample(string bank,int index){
  if(bank=="moon"){switch(index){case 0:return SoundID.SL_AI_Talk_1;case 1:return SoundID.SL_AI_Talk_2;case 2:return SoundID.SL_AI_Talk_3;case 3:return SoundID.SL_AI_Talk_4;default:return SoundID.SL_AI_Talk_5;}}
  switch(index){case 0:return SoundID.SS_AI_Talk_1;case 1:return SoundID.SS_AI_Talk_2;case 2:return SoundID.SS_AI_Talk_3;case 3:return SoundID.SS_AI_Talk_4;default:return SoundID.SS_AI_Talk_5;}
 }
}
}
