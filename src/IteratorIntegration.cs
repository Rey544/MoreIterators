using System;
using System.Collections.Generic;
using UnityEngine;

namespace MoreIterators {
 public interface IOraclePersonalSpace {
  bool Avoiding {get;}
  void Sense();
  void Move();
  void Hands(OracleGraphics graphics);
 }

 public static class IteratorSprites {
  // Reserved after the common 110 slots and necklace slots; integrations own these overlays.
  public const int IntegrationSlots=12;
 }

 public abstract class IteratorIntegration {
  public abstract string ModId {get;}
  public virtual bool Native(string id){return false;}
  public virtual void Reset(){}
  public virtual void Menu(Menu.MainMenu menu){}
  public virtual bool Signal(Menu.MainMenu menu,Menu.MenuObject sender,string signal){return false;}
  public virtual bool Launch(Menu.MainMenu menu,string room){return false;}
  public virtual int BasePalette(RoomCamera camera,int palette){return palette;}
  public virtual void Palette(Texture2D palette,RoomCamera camera,int index){}
  public virtual Color Cloth(IteratorDesign design,float f){return Color.Lerp(IteratorDesign.C(design.clothTopColor),IteratorDesign.C(design.clothBottomColor),Mathf.Pow(Mathf.Clamp01(f),2));}
  public virtual IOraclePersonalSpace PersonalSpace(IteratorBehavior behavior){return null;}
  public virtual void BeforeRoom(Room room){}
  public virtual void CreateEncounter(Oracle oracle){}
  public virtual void Update(OracleGraphics graphics){}
  public virtual void Sprites(OracleGraphics graphics,RoomCamera.SpriteLeaser sprites,RoomCamera camera,int first){}
  public virtual void Draw(OracleGraphics graphics,RoomCamera.SpriteLeaser sprites,int first,IteratorDesign design,Vector2 chest,Vector2 head,Vector2 up,Vector2 right,Vector2 camera,float timeStacker){}
 }

 public static class IteratorIntegrations {
  static readonly List<IteratorIntegration> items=new List<IteratorIntegration>();
  public static void Register(IteratorIntegration extension){if(FindMod(extension.ModId)!=null)throw new InvalidOperationException("Duplicate iterator integration: "+extension.ModId);items.Add(extension);}
  public static IteratorIntegration FindMod(string mod){return items.Find(x=>x.ModId==mod);}
  public static IteratorIntegration ForId(string id){return items.Find(x=>x.Native(id));}
  public static bool Native(string id){return ForId(id)!=null;}
  public static IteratorIntegration ForRoom(string room){var item=IteratorCatalog.Find(room);return item==null?null:FindMod(IteratorCatalog.Text(item,"ownerMod"));}
  public static void Reset(){foreach(var item in items)item.Reset();}
  public static void Menu(Menu.MainMenu menu){foreach(var item in items)item.Menu(menu);}
  public static bool Signal(Menu.MainMenu menu,Menu.MenuObject sender,string signal){foreach(var item in items)if(item.Signal(menu,sender,signal))return true;return false;}
  public static bool Launch(Menu.MainMenu menu,string room){var item=ForRoom(room);return item!=null&&item.Launch(menu,room);}
  public static IOraclePersonalSpace PersonalSpace(IteratorBehavior b){var item=ForRoom(b.oracle.room.abstractRoom.name);return item==null?null:item.PersonalSpace(b);}
  public static void BeforeRoom(Room room){var item=ForRoom(room.abstractRoom.name);if(item!=null)item.BeforeRoom(room);}
  public static void CreateEncounter(Oracle oracle){var item=ForRoom(oracle.room.abstractRoom.name);if(item!=null)item.CreateEncounter(oracle);}
  public static void Update(OracleGraphics g){var item=ForRoom(g.oracle.room.abstractRoom.name);if(item!=null)item.Update(g);}
  public static void Sprites(OracleGraphics g,RoomCamera.SpriteLeaser s,RoomCamera c,int n){var item=ForRoom(g.oracle.room.abstractRoom.name);if(item!=null)item.Sprites(g,s,c,n);}
  public static void Draw(OracleGraphics g,RoomCamera.SpriteLeaser s,int n,IteratorDesign d,Vector2 chest,Vector2 head,Vector2 up,Vector2 right,Vector2 camera,float t){var item=ForRoom(g.oracle.room.abstractRoom.name);if(item!=null)item.Draw(g,s,n,d,chest,head,up,right,camera,t);}
 }
}
