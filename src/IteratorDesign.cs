namespace MoreIterators {
using System;
using System.IO;
using UnityEngine;
[Serializable] public class IteratorLayers {public bool head=true,body=true,neck=true,eyes=true,face=true,antenna=true,ears=true,robe=true,sleeves=true,hands=true,feet=true,collar=true,mechanicalArm=true,cables=true,halo=true;}
[Serializable] public class IteratorDesign {
 public CreatorVoiceDesign voice=new CreatorVoiceDesign();
 public string schema="moreiterators.oracle.v1",projectId="",name="未命名迭代器",oracleId="default",previewToken="";
 public string headColor="#a0aaa7",eyeColor="#eef0e8",clothTopColor="#687872",clothBottomColor="#bac2ba",antennaColor="#84a99d",metalColor="#334542",facePng="",antennaPng="";
 public string armJointColor="#354b43",collarColor="#29bc91",eyeshadowColor="#91232d"; public float eyeshadowOpacity=0,eyeshadowSize=.65f;
 public string clothMiddleColor="#a45a60";public float clothGrain=.16f;
 public string cableColorA="#79998b",cableColorB="#a5b8ad",headCableRed="#ff0000",headCableBlue="#0000ff";
 public float earWidth=4,earHeight=7; public string armColor="#728b80",haloPreset="original"; public float haloSpeed=1;
 public string pearlColor1="#000000",pearlColor2="#6d9983",pearlColor3="#8c9272",pearlColor4="#e0dfbf",pearlGlyphColor="#afc9b8";public float pearlGlyphOpacity=.68f;
 public int pearlCount=32; public string capeColor="#283136",capeLiningColor="#a5afb0"; public float capeLength=38,capeWidth=19;
 public int pearlGlyph1=0,pearlGlyph2=3,pearlGlyph3=6,pearlGlyph4=9;
 public Color PearlColor(int i){return C(i%4==0?pearlColor1:i%4==1?pearlColor2:i%4==2?pearlColor3:pearlColor4);}
 public int PearlGlyph(int i){return Mathf.Clamp(i%4==0?pearlGlyph1:i%4==1?pearlGlyph2:i%4==2?pearlGlyph3:pearlGlyph4,0,13);}
 public float antennaHeight=13,antennaWidth=1.1f,antennaSpread=8.2f,eyeSpacing=3.2f,eyeSize=1.35f,robeLength=29,robeHemWidth=1,sleeveWidth=4,faceScale=1,faceOffsetX=0,faceOffsetY=0;
 public string haloColor="#74b69b",haloPng=""; public float haloScale=1,haloOpacity=.5f; public int roomPalette=13;
 public string earLeftInnerPng="",earLeftPng="",earRightInnerPng="",earRightPng="",earInnerColor="#9cafaa",earOuterColor="#323e3d";public bool earTint=false,earCustom=false;
 public float roomBrightness=1,roomContrast=1,roomSaturation=1;
 public string rearGlowColor="#98b4a5";public bool rearGlowEnabled=true;public float rearGlowOpacity=.12f,rearGlowRadius=250;
 public ColorGradient armGradient=new ColorGradient(),cableThinGradient=new ColorGradient(),cableThickGradient=new ColorGradient(),headCableAGradient=new ColorGradient(),headCableBGradient=new ColorGradient();
 public RoomGradient roomGradient=new RoomGradient();
 public bool antennaUpperEnabled=true,earBodyEnabled=true;
 public bool antennaLowerEnabled=false,antennaLowerCustom=false,antennaLowerTint=false;
 public float antennaLowerWidth=2.4f,antennaLowerHeight=10,antennaLowerSpread=8.2f,antennaLowerOffsetY=0;
 public string antennaLowerColor="#334542",antennaLowerInnerColor="#9cafaa",antennaLowerOuterColor="#323e3d";
 public string antennaLowerLeftInnerPng="",antennaLowerLeftPng="",antennaLowerRightInnerPng="",antennaLowerRightPng="";
 public bool earDecorationEnabled=false,earDecorationCustom=false,earDecorationTint=false;
 public float earDecorationWidth=3,earDecorationHeight=10,earDecorationSpread=8,earDecorationOffsetY=-9;
 public string earDecorationColor="#334542",earDecorationInnerColor="#9cafaa",earDecorationOuterColor="#323e3d";
 public string earDecorationLeftInnerPng="",earDecorationLeftPng="",earDecorationRightInnerPng="",earDecorationRightPng="";

 public AudioTrackDesign musicWork=new AudioTrackDesign(),musicReception=new AudioTrackDesign(),musicReading=new AudioTrackDesign();
 public string antennaInnerMode="",antennaOuterMode="",earInnerMode="",earOuterMode="",antennaLowerInnerMode="",antennaLowerOuterMode="",earDecorationInnerMode="",earDecorationOuterMode="";
 public string antennaInnerEndColor="#9cafaa",antennaOuterEndColor="#323e3d",earInnerEndColor="#9cafaa",earOuterEndColor="#323e3d",antennaLowerInnerEndColor="#9cafaa",antennaLowerOuterEndColor="#323e3d",earDecorationInnerEndColor="#9cafaa",earDecorationOuterEndColor="#323e3d";
 public string antennaInnerDirection="vertical",antennaOuterDirection="vertical",earInnerDirection="vertical",earOuterDirection="vertical",antennaLowerInnerDirection="vertical",antennaLowerOuterDirection="vertical",earDecorationInnerDirection="vertical",earDecorationOuterDirection="vertical";
 public PearlAccessoryDesign[] pearlAccessories=new PearlAccessoryDesign[0];
 public EyeDesign[] eyes=new EyeDesign[0];
 public PuppetArmDesign[] puppetArms=new PuppetArmDesign[0];
 public bool puppetArmSymmetry=true,puppetExtraArmSymmetry=true;
 public bool puppetSleeveSyncSeparated=false,puppetExtraSleeveSymmetry=true;
 public string dialogueJson="";
 public string overseerJson="";
 public string cheekPng="",gownPng="",sleevePng="",collarPng="",antennaLeftPng="",antennaRightPng="",hemProfile="1,1,1,1,1,1,1,1,1,1,1";
 public float cheekScale=1,cheekOffsetX=0,cheekOffsetY=0,earOffsetX=0,earOffsetY=0,antennaOffsetY=0,puppetScale=1,torsoLength=1,armLength=1,legLength=1,collarWidth=1,collarHeight=3,collarNotch=0;
 public bool sleeveOwn=false;
 public string sleeveMapping="strip";public float armShadowStrength=.35f;
 public bool sleeveSymmetry=true,sleeveLeftEnabled=true,sleeveRightEnabled=true,frontSymmetry=true,straightLegs=false,legSymmetry=true;
 public string sleeveRBasePng="",sleeveRPng="",legThighBasePng="",legThighPng="",legKneeBasePng="",legKneePng="",legShinBasePng="",legShinPng="";
 public float thighLength=10,shinLength=13,legWidth=2.5f,kneeSize=3,legElasticity=.7f;
 public float legSpacing=6,legLeftOffset=0,legRightOffset=0,rightLegLength=1,rightThighLength=10,rightShinLength=13,rightLegWidth=2.5f,rightKneeSize=3,rightLegElasticity=.7f;
 public string legThighRBasePng="",legThighRPng="",legKneeRBasePng="",legKneeRPng="",legShinRBasePng="",legShinRPng="";
 public bool SeparateLeg(int side){return side==1&&!legSymmetry;}
 public float LegLength(int side){return SeparateLeg(side)?rightLegLength:legLength;}
 public float ThighLength(int side){return SeparateLeg(side)?rightThighLength:thighLength;}
 public float ShinLength(int side){return SeparateLeg(side)?rightShinLength:shinLength;}
 public float LegWidth(int side){return SeparateLeg(side)?rightLegWidth:legWidth;}
 public float KneeSize(int side){return SeparateLeg(side)?rightKneeSize:kneeSize;}
 public float LegElasticity(int side){return SeparateLeg(side)?rightLegElasticity:legElasticity;}
 public float LegShift(int side){return (side==0?-1:1)*(legSpacing-6)*.5f+(side==0?legLeftOffset:legSymmetry?-legLeftOffset:legRightOffset);}
 public int shawlCount;
 public GarmentDesign[] frontPanels=new GarmentDesign[0],shawls=new GarmentDesign[0],accessories=new GarmentDesign[0];
 public string[] renderOrder=new string[0];
 public bool legacyGownUV=false,legacySleeveUV=false,legacyCollarUV=false,legacyAntennaUV=false;
 public int necklaceCount=0;
 public NecklaceDesign[] necklaces=new NecklaceDesign[0];
 public string collarBasePng="",gownBasePng="",sleeveBasePng="",sleeveTopColor="#813c46",sleeveMiddleColor="#b68b8e",sleeveBottomColor="#e0dfd8";
 public float collarOffsetY=0,collarTopNotch=0,collarRoundness=.5f,collarTaper=1,sleeveGrain=.12f;
 public float neckLength=1;
 public string antennaLeftInnerPng="",antennaRightInnerPng="",antennaInnerColor="#9cafaa",antennaOuterColor="#323e3d";
 public bool antennaTint=true;
 public int scarfPanels=0;
 public int scarfShape=0;public float scarfTopWidth=10;
 public float scarfLength=36,scarfWidth=36,scarfGap=.18f,scarfLightness=.7f,scarfFringeLength=5,scarfGrain=.12f;
 public bool scarfFringe=false;
 public string scarfTopColor="#384845",scarfMiddleColor="#688479",scarfBottomColor="#b5c7bd",scarfBasePng="",scarfPng="";
 public string roomWorkColor="#476d67",roomReceptionColor="#bd8152",roomTemplate="fp";public float roomTransition=3;
 public float pearlClusterX=.25f,pearlClusterY=.18f,pearlCluster2X=.75f,pearlCluster2Y=.18f,pearlScatter=1;public int pearlFixedCount=8;
 public string firstDialogue="……你好。",repeatDialogue="又见面了。",unmarkedDialogue="……",pearlDialogue="……让我看看。";
 public IteratorLayers layers=new IteratorLayers();
 public string appearanceAdapter="",nativeOracle="";
 public static IteratorDesign Current=new IteratorDesign();
 sealed class CachedDesign {public IteratorDesign value;public DateTime stamp;public float poll;}
 static readonly System.Collections.Generic.Dictionary<string,CachedDesign> roomDesigns=new System.Collections.Generic.Dictionary<string,CachedDesign>();
 public static IteratorDesign ForRoom(Room r){return ForId(CreatorRuntime.Id(r==null?null:r.abstractRoom.name));}
 public static IteratorDesign ForId(string id){
  CachedDesign cache;if(!roomDesigns.TryGetValue(id,out cache)){cache=new CachedDesign{value=new IteratorDesign{oracleId=id}};roomDesigns[id]=cache;}
  if(Time.realtimeSinceStartup<cache.poll)return cache.value;cache.poll=PlaybackMode.Enabled?float.MaxValue:Time.realtimeSinceStartup+.5f;
  string path=RuntimePaths.DesignPath(id);if(!File.Exists(path))return cache.value;
  var modified=File.GetLastWriteTimeUtc(path);if(modified==cache.stamp)return cache.value;
  try{var value=new IteratorDesign();ReadFields(value,Json.Deserialize(File.ReadAllText(path)) as System.Collections.Generic.Dictionary<string,object>);if(value.oracleId==id){cache.value=value;cache.stamp=modified;}}catch(Exception e){MiDiagnostics.Report("MI_DESIGN_READ","IteratorDesign.ForId",e,id);UnityEngine.Debug.LogWarning("[More Iterators] Room design "+id+": "+e.Message);}return cache.value;
 }
 public static string SelectedId="default"; public static void Select(string id){if(SelectedId==id)return;SelectedId=id;stamp=DateTime.MinValue;nextRead=0;}
 static float nextRead;static DateTime stamp;public static int Revision;
 public static string FaceElement,AntennaElement,HaloElement; public static Rect FaceInk=new Rect(-2,-2,4,4);
 public static void Poll(Action<string> log){
  if(Time.realtimeSinceStartup<nextRead)return;nextRead=Time.realtimeSinceStartup+.12f;
  string path=RuntimePaths.DesignPath(SelectedId);if(!File.Exists(path))return;
  DateTime modified=PlaybackMode.Enabled?new DateTime(1):File.GetLastWriteTimeUtc(path);if(modified==stamp)return;
  PendingTexture face=null,antenna=null,halo=null;bool committed=false;
  try{
   var d=new IteratorDesign();ReadFields(d,Json.Deserialize(File.ReadAllText(path)) as System.Collections.Generic.Dictionary<string,object>);
   if((d.schema!="eoe.oracle.v1"&&d.schema!="moreiterators.oracle.v1")||d.oracleId!=SelectedId)throw new Exception("Unsupported oracle project");
   // Stage every atlas under a fresh name. A later failure must not unload an
   // earlier active texture or publish only part of this design revision.
   face=PrepareTexture(d.facePng,"moreiterators_face");
   antenna=PrepareTexture(d.antennaPng,"moreiterators_antenna");
   halo=PrepareTexture(d.haloPng,"moreiterators_halo",d.haloOpacity*.68f);
   string oldFace=FaceElement,oldAntenna=AntennaElement,oldHalo=HaloElement;
   FaceElement=face.element;AntennaElement=antenna.element;HaloElement=halo.element;FaceInk=face.ink;
   Current=d;stamp=modified;
   roomDesigns[SelectedId]=new CachedDesign{value=d,stamp=modified,poll=PlaybackMode.Enabled?float.MaxValue:Time.realtimeSinceStartup+.5f};
   Revision++;committed=true;
   ReleaseAtlas(oldFace);ReleaseAtlas(oldAntenna);ReleaseAtlas(oldHalo);
   if(log!=null)log("Applied oracle project "+d.projectId+" revision "+Revision+" arm="+d.layers.mechanicalArm+" cables="+d.layers.cables+" halo="+d.layers.halo);
  }catch(Exception e){
   stamp=modified;MiDiagnostics.Report("MI_DESIGN_APPLY","IteratorDesign.Poll",e,SelectedId);
   if(log!=null)log("Oracle project read failed: "+e.Message);
  }finally{
   if(!committed){DiscardTexture(face);DiscardTexture(antenna);DiscardTexture(halo);}
  }
 }
 sealed class DesignFieldException:FormatException {
  public DesignFieldException(string node,Type type,object value,Exception cause):base("Invalid project field "+node+" (expected "+type.Name+", received "+(value==null?"null":value is System.Collections.IDictionary?"object":value is System.Collections.IList?"array":value.GetType().Name)+"). "+cause.Message,cause){}
 }
 static object ReadValue(Type type,object value,string node){try{
  if(type==typeof(string)&&value==null){MiDiagnostics.Warn("MI_DESIGN_NULL_STRING","IteratorDesign.ReadValue","Null string was treated as empty.",node);return "";}
  if(type.IsArray){var list=value as System.Collections.IList;if(list==null)throw new Exception("Expected array");Type item=type.GetElementType();var result=Array.CreateInstance(item,list.Count);for(int i=0;i<list.Count;i++)result.SetValue(ReadValue(item,list[i],node+"["+i+"]"),i);return result;}
  if(type==typeof(PuppetArmDesign)){var fields=value as System.Collections.Generic.Dictionary<string,object>;var result=new PuppetArmDesign();ReadFields(result,fields,node);if(!fields.ContainsKey("handTextureTint"))result.handTextureTint=result.handOwnColor;return result;}
  if(type==typeof(CreatorVoiceDesign)||type==typeof(EyeDesign)||type==typeof(AudioTrackDesign)||type==typeof(IteratorLayers)||type==typeof(NecklaceDesign)||type==typeof(NecklacePearl)||type==typeof(GarmentDesign)||type==typeof(ColorGradient)||type==typeof(GradientStop)||type==typeof(RoomGradient)||type==typeof(CornerGlow)||type==typeof(PearlAccessoryDesign)||type==typeof(PearlAccessoryBead)||type==typeof(PearlAccessoryChild)){object result=Activator.CreateInstance(type);ReadFields(result,value as System.Collections.Generic.Dictionary<string,object>,node);return result;}
  return Convert.ChangeType(value,type,System.Globalization.CultureInfo.InvariantCulture);
 }catch(DesignFieldException){throw;}catch(Exception error){throw new DesignFieldException(node,type,value,error);}
 }
 static void ReadFields(object target,System.Collections.Generic.Dictionary<string,object> values){ReadFields(target,values,target.GetType().Name);}
 static void ReadFields(object target,System.Collections.Generic.Dictionary<string,object> values,string node){if(values==null)throw new Exception("Invalid project object");foreach(var field in target.GetType().GetFields(System.Reflection.BindingFlags.Public|System.Reflection.BindingFlags.Instance)){object value;if(values.TryGetValue(field.Name,out value))field.SetValue(target,ReadValue(field.FieldType,value,node+"."+field.Name));}}
 sealed class PendingTexture {
  public string element;public Texture2D texture;public Rect ink=new Rect(-2,-2,4,4);
 }
 static PendingTexture PrepareTexture(string png,string key,float opacity=1){
  var pending=new PendingTexture();if(String.IsNullOrEmpty(png))return pending;
  try{
   var t=new Texture2D(2,2,TextureFormat.ARGB32,false);pending.texture=t;
   t.filterMode=key=="moreiterators_halo"?FilterMode.Bilinear:FilterMode.Point;t.wrapMode=TextureWrapMode.Clamp;
   byte[] bytes=Convert.FromBase64String(png.Substring(png.IndexOf(',')+1));
   if(!ImageConversion.LoadImage(t,bytes))throw new FormatException("Invalid PNG");
   if(key=="moreiterators_halo"){
    var pixels=t.GetPixels();for(int i=0;i<pixels.Length;i++)pixels[i].a*=Mathf.Clamp01(opacity);t.SetPixels(pixels);t.Apply();
   }
   if(key=="moreiterators_face"){
    int x0=t.width,y0=t.height,x1=0,y1=0;Color[] pixels=t.GetPixels();
    for(int y=0;y<t.height;y++)for(int x=0;x<t.width;x++)if(pixels[y*t.width+x].a>.05f){x0=Math.Min(x0,x);x1=Math.Max(x1,x+1);y0=Math.Min(y0,y);y1=Math.Max(y1,y+1);}
    pending.ink=x1>x0?new Rect(x0-t.width*.5f,y0-t.height*.5f,x1-x0,y1-y0):new Rect(-2,-2,4,4);
   }
   pending.element=key+"_"+Guid.NewGuid().ToString("N");
   Futile.atlasManager.LoadAtlasFromTexture(pending.element,t,false);
   return pending;
  }catch{DiscardTexture(pending);throw;}
 }
 static void DiscardTexture(PendingTexture pending){
  if(pending==null||pending.texture==null)return;
  try{
   if(pending.element!=null&&Futile.atlasManager.DoesContainAtlas(pending.element))Futile.atlasManager.UnloadAtlas(pending.element);
   else UnityEngine.Object.Destroy(pending.texture);
  }catch(Exception e){MiDiagnostics.Report("MI_DESIGN_TEXTURE_RELEASE","IteratorDesign.DiscardTexture",e,pending.element??SelectedId);}
 }
 static void ReleaseAtlas(string element){
  if(String.IsNullOrEmpty(element))return;
  try{Futile.atlasManager.UnloadAtlas(element);}catch(Exception e){MiDiagnostics.Report("MI_DESIGN_TEXTURE_RELEASE","IteratorDesign.ReleaseAtlas",e,element);}
 }
 public static Color C(string h){Color c;return ColorUtility.TryParseHtmlString(h,out c)?c:Color.white;}
 public Color Cloth(float f){var extension=IteratorIntegrations.ForId(oracleId);return extension==null?Color.Lerp(C(clothTopColor),C(clothBottomColor),Mathf.Pow(Mathf.Clamp01(f),2)):extension.Cloth(this,f);}

}
}
