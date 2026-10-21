namespace MoreIterators {
using UnityEngine;

// Effects belong to this utterance, never to the oracle's other sounds. Native
// AudioSources are pooled: disable immediately BEFORE Destroy (deferred by Unity).
internal sealed class CreatorVoiceEffects {
 AudioSource source,positioned;AudioEchoFilter echo;AudioLowPassFilter low;AudioDistortionFilter distortion;
 public void Seek(ChunkSoundEmitter emitter,float offset){var sound=emitter.currentSoundObject;var audio=sound==null?null:sound.audioSource;if(audio!=null&&audio!=positioned&&audio.clip!=null){audio.time=System.Math.Min(offset,System.Math.Max(0,audio.clip.length-.08f));positioned=audio;}}
 public bool NearEnd(ChunkSoundEmitter emitter){var sound=emitter.currentSoundObject;var audio=sound==null?null:sound.audioSource;return audio!=null&&audio.clip!=null&&audio.time+.06f*emitter.pitch>=audio.clip.length;}
 public void Update(ChunkSoundEmitter emitter,CreatorVoiceDesign value){
  var sound=emitter.currentSoundObject;var next=sound==null?null:sound.audioSource;
  if(next!=source){var seek=positioned;Clear();source=next;positioned=seek;}if(source==null)return;
  if(value.muffle>0&&low==null)low=source.gameObject.AddComponent<AudioLowPassFilter>();
  if(value.electric>0&&distortion==null)distortion=source.gameObject.AddComponent<AudioDistortionFilter>();
  if(value.echo>0&&echo==null)echo=source.gameObject.AddComponent<AudioEchoFilter>();
  if(echo!=null){echo.enabled=value.echo>0;echo.delay=180;echo.decayRatio=.25f+.3f*value.echo;echo.wetMix=.45f*value.echo;echo.dryMix=1;}
  if(low!=null){low.enabled=value.muffle>0;low.cutoffFrequency=18000f*(float)System.Math.Pow(650f/18000f,value.muffle);low.lowpassResonanceQ=1;}
  if(distortion!=null){distortion.enabled=value.electric>0;distortion.distortionLevel=.8f*value.electric;}
 }
 public void Clear(){
  if(echo!=null){echo.enabled=false;Object.Destroy(echo);}if(low!=null){low.enabled=false;Object.Destroy(low);}if(distortion!=null){distortion.enabled=false;Object.Destroy(distortion);}
  echo=null;low=null;distortion=null;source=null;positioned=null;
 }
}
}
