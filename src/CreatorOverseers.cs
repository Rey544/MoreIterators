using System;
using System.Collections.Generic;
using System.Runtime.CompilerServices;
using OverseerHolograms;
using RWCustom;
using UnityEngine;

namespace MoreIterators {
 public static class CreatorOverseers {
  sealed class Settings {public string json;public CreatorOverseerConfig value;}
  sealed class Owned {
   public string id;public Room room;public AbstractCreature creature;public CreatorOverseerConfig config;
   public readonly CreatorOverseerSchedule schedule=new CreatorOverseerSchedule();
   public readonly Dictionary<RoomCamera,FLabel> labels=new Dictionary<RoomCamera,FLabel>();
   public string action;
  }
  static RainWorldGame game;
  static readonly Dictionary<string,Settings> settings=new Dictionary<string,Settings>();
  static readonly Dictionary<string,Owned> instances=new Dictionary<string,Owned>();
  static ConditionalWeakTable<AbstractCreature,Owned> owners=new ConditionalWeakTable<AbstractCreature,Owned>();
  static readonly Dictionary<string,float> retry=new Dictionary<string,float>();
  static Owned Owner(AbstractCreature creature){Owned value;return creature!=null&&owners.TryGetValue(creature,out value)?value:null;}
  public static bool RoomAllowed(OverseerAbstractAI ai,int room,out bool allowed){var owner=ai==null?null:Owner(ai.parent);allowed=owner!=null&&owner.room!=null&&owner.room.abstractRoom!=null&&owner.room.abstractRoom.index==room;return owner!=null;}
  public static void Install(List<Action> removals){
   var roomHook=new On.Room.hook_Update((orig,room)=>{orig(room);try{Tick(room);}catch(Exception e){MiDiagnostics.Report("MI-OVERSEER-ROOM","CreatorOverseers.Tick",e,room.abstractRoom.name);}});
   On.Room.Update+=roomHook;removals.Add(delegate{On.Room.Update-=roomHook;});
   var abstractHook=new On.OverseerAbstractAI.hook_AbstractBehavior((orig,ai,time)=>{
    var own=Owner(ai.parent);if(own==null){orig(ai,time);return;}
    // The owned observer stays local and never becomes worldAI.playerGuide or touches GuideState.
    ai.SetDestinationNoPathing(ai.parent.pos,false);ai.targetCreature=PlayerIn(own.room);
   });
   On.OverseerAbstractAI.AbstractBehavior+=abstractHook;removals.Add(delegate{On.OverseerAbstractAI.AbstractBehavior-=abstractHook;});
   var aiHook=new On.OverseerAI.hook_Update((orig,ai)=>{var own=Owner(ai.creature);if(own!=null&&ai.overseer!=null)ai.overseer.conversationDelay=2;orig(ai);if(own==null)return;try{Animate(own,ai);}catch(Exception e){own.schedule.Reset();StopHologram(own);MiDiagnostics.Report("MI-OVERSEER-ANIMATION","CreatorOverseers.Animate",e,own.id);}});
   On.OverseerAI.Update+=aiHook;removals.Add(delegate{On.OverseerAI.Update-=aiHook;});
   var colorHook=new On.OverseerGraphics.hook_ColorOfSegment((orig,graphics,f,t)=>{Color native=orig(graphics,f,t);var creature=graphics.owner as Overseer;var own=creature==null?null:Owner(creature.abstractCreature);return own==null?native:CreatorOverseerConfig.Gradient(own.config.bodyColors,1f-f,native.a);});
   On.OverseerGraphics.ColorOfSegment+=colorHook;removals.Add(delegate{On.OverseerGraphics.ColorOfSegment-=colorHook;});
   var drawHook=new On.OverseerGraphics.hook_DrawSprites((orig,graphics,leaser,camera,t,pos)=>{orig(graphics,leaser,camera,t,pos);var creature=graphics.owner as Overseer;var own=creature==null?null:Owner(creature.abstractCreature);if(own==null)return;try{Paint(own,graphics,leaser,camera,pos);}catch(Exception e){MiDiagnostics.Report("MI-OVERSEER-DRAW","CreatorOverseers.Paint",e,own.id);}});
   On.OverseerGraphics.DrawSprites+=drawHook;removals.Add(delegate{On.OverseerGraphics.DrawSprites-=drawHook;});
   var hologramHook=new On.Overseer.hook_TryAddHologram((orig,overseer,message,player,importance)=>{if(Owner(overseer.abstractCreature)==null)orig(overseer,message,player,importance);});
   On.Overseer.TryAddHologram+=hologramHook;removals.Add(delegate{On.Overseer.TryAddHologram-=hologramHook;});
  }
  static CreatorOverseerConfig Config(string id){
   var design=IteratorDesign.ForId(id);string json=design==null?"":design.overseerJson;Settings cache;
   if(settings.TryGetValue(id,out cache)&&cache.json==json)return cache.value;
   cache=new Settings{json=json,value=new CreatorOverseerConfig()};settings[id]=cache;
   try{cache.value=CreatorOverseerConfig.Parse(json);}catch(Exception e){MiDiagnostics.Report("MI-OVERSEER-CONFIG","CreatorOverseers.Config",e,id);}
   return cache.value;
  }
  static AbstractCreature PlayerIn(Room room){
   if(room==null||room.game==null)return null;
   foreach(var player in room.game.Players){var realized=player.realizedCreature as Player;if(realized!=null&&!realized.dead&&realized.room==room)return player;}return null;
  }
  // Missing room lists retain the old owned-room defaults; explicit lists opt into other rooms.
  public static bool CanOwn(string room){return IteratorCatalog.IsAI(room)||IteratorCatalog.OwnsEntry(room);}
  static bool ProfileRoom(string host,CreatorOverseerConfig profile,string room){return profile.rooms==null?CanOwn(room)&&IteratorCatalog.Id(room)==host:Array.IndexOf(profile.rooms,room)>=0;}
  public static void Tick(Room room){
   if(room==null||room.game==null||room.abstractRoom==null)return;
   if(game!=room.game){Shutdown();game=room.game;}
   var active=new HashSet<string>();
   foreach(var project in IteratorCatalog.Projects()){
    string host=IteratorCatalog.Text(project,"oracleId");if(String.IsNullOrEmpty(host))continue;
    var config=Config(host);active.Add(host);TickProfile(room,host,host,config);
    if(config.guests!=null)foreach(var guest in config.guests){if(guest==null)continue;string key=host+":"+guest.id;active.Add(key);TickProfile(room,host,key,guest);}
   }
   foreach(var key in new List<string>(instances.Keys))if(!active.Contains(key)){Remove(instances[key]);instances.Remove(key);retry.Remove(key);}
  }
  static void TickProfile(Room room,string host,string id,CreatorOverseerConfig config){
   string name=room.abstractRoom.name;bool allowed=ProfileRoom(host,config,name);Owned old;
   if(instances.TryGetValue(id,out old)){
    bool detached=old.room==null||old.room.abstractRoom==null||old.room.abstractRoom.realizedRoom!=old.room||old.creature.realizedCreature==null||old.creature.realizedCreature.room!=old.room;
    if(!config.enabled||detached||!ProfileRoom(host,config,old.room.abstractRoom.name)){Remove(old);instances.Remove(id);old=null;}
    if(old!=null){
     if(old.config!=config){old.config=config;old.schedule.Reset();StopHologram(old);}
     if(old.creature.realizedCreature.dead||old.creature.realizedCreature.slatedForDeletetion){Remove(old);instances.Remove(id);retry[id]=Time.realtimeSinceStartup+30f;return;}
     if(!allowed||old.room==room||PlayerIn(old.room)!=null||PlayerIn(room)==null)return;
     Remove(old);instances.Remove(id);
    }
   }
   if(!allowed||!config.enabled||PlayerIn(room)==null||!room.readyForAI)return;
   float after;if(retry.TryGetValue(id,out after)&&Time.realtimeSinceStartup<after)return;
   // Each profile has one temporary native overseer; binding an owner never spawns an oracle.
   var creature=new AbstractCreature(room.world,StaticWorld.GetCreatureTemplate(CreatureTemplate.Type.Overseer),null,new WorldCoordinate(room.abstractRoom.index,room.TileWidth/2,room.TileHeight/2,-1),room.game.GetNewID());
   var own=new Owned{id=id,room=room,creature=creature,config=config};owners.Add(creature,own);instances[id]=own;
   try{
    creature.ignoreCycle=true;creature.saveCreature=false;room.abstractRoom.AddEntity(creature);creature.RealizeInRoom();
    var overseer=creature.realizedCreature as Overseer;if(overseer==null)throw new InvalidOperationException("Native overseer realization failed");
    overseer.conversationDelay=2;Position(overseer,PlayerIn(room));MiDiagnostics.Info("overseer.spawn",id+"; room="+name+"; owner="+config.ownerAbbreviation);
   }catch{Remove(own);instances.Remove(id);retry[id]=Time.realtimeSinceStartup+8f;throw;}
  }
  static void Position(Overseer overseer,AbstractCreature player){
   var room=overseer.room;var target=player==null?room.MiddleOfTile(room.TileWidth/2,room.TileHeight/2):player.realizedCreature.mainBodyChunk.pos;
   float best=float.MaxValue;IntVector2 hover=overseer.hoverTile,root=overseer.rootTile;
   for(int x=1;x<room.TileWidth-1;x++)for(int y=1;y<room.TileHeight-1;y++){
    var tile=new IntVector2(x,y);if(room.GetTile(tile).Solid)continue;float distance=Vector2.Distance(room.MiddleOfTile(tile),target);
    if(distance<180f||distance>650f)continue;
    foreach(var direction in Custom.fourDirections){var wall=tile+direction;if(!room.GetTile(wall).Solid)continue;float score=Mathf.Abs(distance-280f)+Mathf.Abs(room.MiddleOfTile(tile).y-target.y-80f)*.3f;if(score<best){best=score;hover=tile;root=wall;}}
   }
   overseer.HardSetTile(hover,root);
  }
  static void Animate(Owned own,OverseerAI ai){
   var overseer=ai.overseer;var player=PlayerIn(own.room);
   bool eligible=own.config.enabled&&overseer!=null&&!overseer.dead&&overseer.room==own.room&&player!=null;
   bool idle=overseer!=null&&(overseer.mode==Overseer.Mode.Watching||overseer.mode==Overseer.Mode.Projecting);
   string action=own.schedule.Tick(own.config,eligible&&idle,delegate{return UnityEngine.Random.value;});
   ai.bringUpLens=action=="lens"?1f:0f;
   if(action==own.action)return;StopHologram(own);own.action=action;
   if(action==null||action=="lens")return;
   // These native visual classes are safe without the global guide communication module.
   // A strict six-second lifetime also ends Angry before its native leave-world side effect.
   OverseerHologram hologram;
   if(action=="Angry")hologram=new AngryHologram(overseer,OverseerHologram.Message.Angry,player.realizedCreature,1f);
   else {
    var images=new OverseerImage(overseer,OverseerHologram.Message.GateScene,player.realizedCreature,1f);
    images.images.Add(OverseerImage.ImageID.Slugcat_1);images.images.Add(OverseerImage.ImageID.Slugcat_2);images.images.Add(OverseerImage.ImageID.Slugcat_3);images.timeOnEachImage=60;
    hologram=images;
   }
   overseer.hologram=hologram;own.room.AddObject(hologram);
  }
  static void StopHologram(Owned own){
   var overseer=own.creature.realizedCreature as Overseer;if(overseer!=null&&overseer.hologram!=null){overseer.hologram.stillRelevant=false;overseer.hologram.Destroy();overseer.hologram=null;}
   own.action=null;foreach(var label in own.labels.Values)label.RemoveFromContainer();own.labels.Clear();
  }
  static void Paint(Owned own,OverseerGraphics graphics,RoomCamera.SpriteLeaser leaser,RoomCamera camera,Vector2 camPos){
   if(camera.room!=own.room||own.creature.realizedCreature==null||own.creature.realizedCreature.slatedForDeletetion){FLabel stale;if(own.labels.TryGetValue(camera,out stale)){stale.RemoveFromContainer();own.labels.Remove(camera);}return;}
   var config=own.config;var sprites=leaser.sprites;Color head=CreatorOverseerConfig.Gradient(config.bodyColors,1f,1f);
   Tint(sprites[graphics.GlowSprite],head);Tint(sprites[graphics.InnerGlowSprite],head);Tint(sprites[graphics.WhiteSprite],config.eyeWhite);Tint(sprites[graphics.PupilSprite],config.eyePupil);
   for(int i=graphics.FirstMyceliumSprite;i<graphics.WhiteSprite;i++){
    var mesh=sprites[i] as TriangleMesh;if(mesh==null||mesh.verticeColors==null)continue;
    for(int v=0;v<mesh.verticeColors.Length;v++)mesh.verticeColors[v]=CreatorOverseerConfig.Gradient(config.tipColors,v/(float)Math.Max(1,mesh.verticeColors.Length-1),mesh.verticeColors[v].a);
   }
   var observer=own.creature.realizedCreature as Overseer;
   bool show=ModManager.InitializationScreenFinished&&config.ownerAbbreviation!=""&&observer!=null&&observer.hologram!=null&&observer.hologram.fade>.1f;
   FLabel label;
   if(!show){if(own.labels.TryGetValue(camera,out label)){label.RemoveFromContainer();own.labels.Remove(camera);}return;}
   if(!own.labels.TryGetValue(camera,out label)){label=new FLabel(Custom.GetFont(),config.ownerAbbreviation);camera.ReturnFContainer("Foreground").AddChild(label);own.labels[camera]=label;}
   label.text=config.ownerAbbreviation;label.x=observer.hologram.pos.x-camPos.x;label.y=observer.hologram.pos.y-camPos.y+75f;label.color=head;label.alpha=observer.hologram.fade;
  }
  static void Tint(FSprite sprite,Color color){color.a=sprite.color.a;sprite.color=color;}
  static void Remove(Owned own){
   StopHologram(own);owners.Remove(own.creature);
   var realized=own.creature.realizedCreature;if(realized!=null)realized.Destroy();
   var room=own.room==null?own.creature.Room:own.room.abstractRoom;if(room!=null)room.RemoveEntity(own.creature);
  }
  public static void Shutdown(){foreach(var own in instances.Values)Remove(own);instances.Clear();settings.Clear();retry.Clear();owners=new ConditionalWeakTable<AbstractCreature,Owned>();game=null;}
 }
}
