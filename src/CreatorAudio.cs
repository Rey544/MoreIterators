namespace MoreIterators {
using System;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using System.Text.RegularExpressions;
using Music;
using UnityEngine;
using UnityEngine.Networking;

// Custom tracks are opt-in. The native trigger/song lifecycle is never replaced.
public static class CreatorAudio {
 static readonly List<CreatorAudioChannel> channels=new List<CreatorAudioChannel>();
 static bool installed;
 public static void Install(){if(installed)return;installed=true;On.Music.MusicPlayer.Update+=MusicUpdate;}
 internal static void Register(CreatorAudioChannel channel){Install();if(!channels.Contains(channel))channels.Add(channel);}
 internal static void Remove(CreatorAudioChannel channel){channels.Remove(channel);}
 public static bool ValidAsset(string asset){return asset!=null&&Regex.IsMatch(asset,"^[0-9a-f]{64}$");}
 internal static string Resolve(string asset){
  if(!ValidAsset(asset))throw new InvalidDataException("Invalid custom audio asset ID.");
  string path=AssetManager.ResolveFilePath(Path.Combine("mi_audio",asset+".mp3"));
  if(!File.Exists(path))throw new FileNotFoundException("The referenced MP3 is missing from the enabled content package.",asset+".mp3");
  var info=new FileInfo(path);if(info.Length<12||info.Length>10*1024*1024)throw new InvalidDataException("Custom MP3 exceeds the permitted size.");
  using(var hash=SHA256.Create())using(var stream=File.OpenRead(path))if(BitConverter.ToString(hash.ComputeHash(stream)).Replace("-","").ToLowerInvariant()!=asset)throw new InvalidDataException("Custom MP3 hash does not match its asset ID.");
  return path;
 }
 static void MusicUpdate(On.Music.MusicPlayer.orig_Update orig,MusicPlayer player){
  orig(player);
  try{
   CreatorAudioChannel winner=null;var snapshot=channels.ToArray();
   foreach(var channel in snapshot){if(!channel.Live(player)){if(channel.Player==player)channel.Stop();continue;}channel.Poll();if(channel.CanPlay&&(winner==null||channel.Priority>winner.Priority))winner=channel;}
   foreach(var channel in snapshot)if(channel.Player==player)channel.Apply(channel==winner);
   if(winner==null)return;
   // Native tracks restore their own volume on the next Update when no override
   // is active; do not stop, replace, or change their saved state.
   if(player.song!=null)foreach(var track in player.song.subTracks)if(track.source!=null)track.source.volume=0;
   if(player.proceduralMusic!=null)foreach(var track in player.proceduralMusic.subTracks)if(track.source!=null)track.source.volume=0;
  }catch(Exception error){MiDiagnostics.Report("MI-AUDIO-UPDATE","CreatorAudio.MusicUpdate",error,"custom music playback");}
 }
}

public sealed class CreatorAudioChannel {
 public readonly int Priority;
 public MusicPlayer Player{get;private set;}
 Room room;AudioTrackDesign track;AudioSource source;AudioClip clip;UnityWebRequest request;string asset="";float seen;bool failed,ended;
 public CreatorAudioChannel(int priority=10){Priority=priority;}
 public bool CanPlay{get{return !failed&&track!=null&&(track.mode=="silent"||clip!=null&&!ended);}}
 public void Update(Room current,AudioTrackDesign desired,bool active){
  if(!active||desired==null||desired.mode=="native"||current==null||current.game==null||current.game.manager==null||current.game.manager.musicPlayer==null||!current.game.manager.rainWorld.setup.playMusic){Stop();return;}
  var player=current.game.manager.musicPlayer;
  string next=desired.mode=="silent"?"silent":desired.asset;
  if(room!=current||Player!=player||asset!=next){Stop();room=current;Player=player;asset=next;track=desired;failed=false;ended=false;CreatorAudio.Register(this);if(desired.mode=="custom")BeginLoad();else if(desired.mode!="silent")Fail(new InvalidDataException("Unknown music mode."));}
  track=desired;seen=Time.realtimeSinceStartup;
 }
 void BeginLoad(){
  try{
   string path=CreatorAudio.Resolve(asset);request=UnityWebRequestMultimedia.GetAudioClip(new Uri(path).AbsoluteUri,AudioType.MPEG);
   request.timeout=20;var handler=request.downloadHandler as DownloadHandlerAudioClip;if(handler!=null)handler.streamAudio=true;request.SendWebRequest();
  }catch(Exception error){Fail(error);}
 }
 internal bool Live(MusicPlayer player){
  if(Player!=player||room==null||room.game==null||player.manager.currentMainLoop!=room.game||Time.realtimeSinceStartup-seen>1.5f)return false;
  foreach(var camera in room.game.cameras)if(camera!=null&&camera.room==room)return true;return false;
 }
 internal void Poll(){
  if(request==null||!request.isDone)return;
  try{
   if(request.result!=UnityWebRequest.Result.Success)throw new IOException(request.error??"MP3 decoding failed.");
   clip=DownloadHandlerAudioClip.GetContent(request);if(clip==null||clip.length<=0||clip.length>601)throw new InvalidDataException("The MP3 could not be decoded or exceeds ten minutes.");
   source=Player.gameObj.AddComponent<AudioSource>();source.clip=clip;source.loop=track.loop;source.spatialBlend=0;source.volume=0;source.Play();
   MiDiagnostics.Info("audio.loaded","asset="+asset+" seconds="+clip.length);
  }catch(Exception error){Fail(error);}finally{if(request!=null){request.Dispose();request=null;}}
 }
 internal void Apply(bool selected){
  if(source==null)return;source.loop=track.loop;
  if(!source.loop&&!source.isPlaying){ended=true;source.volume=0;return;}
  float volume=0;
  if(selected&&Player.manager.rainWorld.OptionsReady)volume=Mathf.Clamp01(Mathf.Pow(Mathf.Clamp01(track.volume)*Player.manager.rainWorld.options.musicVolume,Player.manager.soundLoader.volumeExponent));
  source.volume=Mathf.MoveTowards(source.volume,volume,.045f);
 }
 void Fail(Exception error){failed=true;MiDiagnostics.Report("MI-AUDIO-ASSET","CreatorAudioChannel.Load",error,"asset="+asset);if(source!=null){source.Stop();UnityEngine.Object.Destroy(source);source=null;}if(clip!=null){UnityEngine.Object.Destroy(clip);clip=null;}}
 public void Stop(){
  CreatorAudio.Remove(this);if(request!=null){request.Abort();request.Dispose();request=null;}if(source!=null){source.Stop();UnityEngine.Object.Destroy(source);source=null;}if(clip!=null){UnityEngine.Object.Destroy(clip);clip=null;}room=null;Player=null;track=null;asset="";failed=false;ended=false;
 }
}

public static class CreatorMusicSettings {
 public static AudioTrackDesign Select(IteratorDesign design,bool working,bool reading){return reading?design.musicReading:working?design.musicWork:design.musicReception;}
}
}
