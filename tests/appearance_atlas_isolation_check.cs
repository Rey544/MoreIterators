using System;
using System.Collections.Generic;

namespace UnityEngine {
 public class Object {public bool destroyed;public static void Destroy(Object value){value.destroyed=true;}}
 public enum TextureFormat {ARGB32}
 public enum FilterMode {Point}
 public enum TextureWrapMode {Clamp}
 public class Texture2D:Object {
  public byte[] data;public FilterMode filterMode;public TextureWrapMode wrapMode;
  public Texture2D(int width,int height,TextureFormat format,bool mipmaps){}
 }
 public static class ImageConversion {
  public static bool LoadImage(Texture2D texture,byte[] data){texture.data=data;return data.Length>0&&data[0]!=0;}
 }
}
public class FSprite {public float scaleX,scaleY;}
public class RoomCamera {public class SpriteLeaser {public FSprite[] sprites;}}
public class FAtlasElement {public string name;public UnityEngine.Texture2D texture;}
public class FAtlasManager {
 readonly Dictionary<string,FAtlasElement> atlases=new Dictionary<string,FAtlasElement>();
 public bool failNextLookup;public int Count {get{return atlases.Count;}}
 public bool DoesContainAtlas(string name){return atlases.ContainsKey(name);}
 public FAtlasElement LoadAtlasFromTexture(string name,UnityEngine.Texture2D texture,bool fromAsset){
   
  if(DoesContainAtlas(name))return atlases[name];
  var element=new FAtlasElement{name=name,texture=texture};atlases.Add(name,element);return element;
 }
 public FAtlasElement GetElementWithName(string name){if(failNextLookup){failNextLookup=false;throw new InvalidOperationException("Registration lookup failed");}return atlases[name];}
 public void UnloadAtlas(string name){var element=atlases[name];atlases.Remove(name);UnityEngine.Object.Destroy(element.texture);}
}
public static class Futile {public static FAtlasManager atlasManager=new FAtlasManager();}
public static class UiText {public static string Get(string value){return value;}}
public static class MiDiagnostics {
 public static int reports;
 public static bool Require(bool condition,params string[] unused){return condition;}
 public static void Report(string code,string method,Exception error,string detail){reports++;}
}
public static class Check {
 static void Require(bool condition,string message){if(!condition)throw new Exception(message);}
 static string Png(byte value){return "data:image/png;base64,"+Convert.ToBase64String(new byte[]{value,7,8,9});}
 static void Owns(FAtlasElement element,byte value){Require(!element.texture.destroyed,"another runtime destroyed this texture");Require(element.texture.data[0]==value,"author texture was replaced");Require(Object.ReferenceEquals(element,Futile.atlasManager.GetElementWithName(element.name)),"atlas no longer registered");}
 static int Main(){try{
  const string slot="same-oracle-gown";
  var core=MoreIterators.CreatorAppearance.Texture(Png(1),slot);
  var first=__FIRST__.CreatorAppearance.Texture(Png(2),slot);
  var second=__SECOND__.CreatorAppearance.Texture(Png(3),slot);
  Require(core.name!=first.name&&first.name!=second.name&&core.name!=second.name,"runtime atlas names collided");
  Owns(core,1);Owns(first,2);Owns(second,3);Require(Futile.atlasManager.Count==3,"three runtimes must own three atlases");
  Require(Object.ReferenceEquals(first,__FIRST__.CreatorAppearance.Texture(Png(2),slot)),"unchanged texture should reuse its own cache");
  var previous=core;core=MoreIterators.CreatorAppearance.Texture(Png(4),slot);
  Require(previous.texture.destroyed&&!Futile.atlasManager.DoesContainAtlas(previous.name),"replaced core atlas was not released");
  Owns(core,4);Owns(first,2);Owns(second,3);
  previous=first;first=__FIRST__.CreatorAppearance.Texture(Png(5),slot);
  Require(previous.texture.destroyed,"replaced export atlas was not released");
  Owns(core,4);Owns(first,5);Owns(second,3);
  Require(Object.ReferenceEquals(second,__SECOND__.CreatorAppearance.Texture(Png(0),slot)),"failed decode lost previous texture");
  int reports=MiDiagnostics.reports;
  Require(Object.ReferenceEquals(second,__SECOND__.CreatorAppearance.Texture(Png(0),slot)),"repeated failed decode lost previous texture");
  Require(MiDiagnostics.reports==reports,"unchanged invalid image retried every draw");
  Owns(core,4);Owns(first,5);Owns(second,3);Require(Futile.atlasManager.Count==3,"failed decode altered registered atlases");
  Futile.atlasManager.failNextLookup=true;
  Require(Object.ReferenceEquals(first,__FIRST__.CreatorAppearance.Texture(Png(6),slot)),"failed registration lost previous texture");
  Owns(core,4);Owns(first,5);Owns(second,3);Require(Futile.atlasManager.Count==3,"rollback altered another runtime's atlas");
  var other=MoreIterators.CreatorAppearance.Texture(Png(7),"other-oracle-gown");Owns(other,7);Owns(core,4);
  Console.WriteLine("PASS: core and two exported runtimes retain original bytes, caches, replacement ownership and rollback isolation");return 0;
 }catch(Exception error){Console.Error.WriteLine(error.Message);return 1;}}
}
