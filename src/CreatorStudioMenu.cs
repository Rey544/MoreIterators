#if !PLAYBACK
namespace MoreIterators {
using System;
using System.Collections.Generic;
using System.Reflection;
using System.Globalization;
using UnityEngine;

// A separate native page keeps the main menu's original controls, callbacks,
// focus and scene intact. Content preview still uses the existing launch path.
internal static class CreatorStudioMenu {
 static Menu.MainMenu menu;
 static Menu.Page originalPage,page;
 static Menu.MenuScene originalScene;
 static Menu.MenuObject originalBack,originalSelection;
 static readonly List<KeyValuePair<FNode,bool>> hidden=new List<KeyValuePair<FNode,bool>>();
 static readonly List<Menu.MenuObject> controls=new List<Menu.MenuObject>();
 static readonly List<FSprite> icons=new List<FSprite>();
 static readonly List<Menu.SimpleButton> navigation=new List<Menu.SimpleButton>();
 static readonly List<Menu.SimpleButton> collectionButtons=new List<Menu.SimpleButton>();
 static bool oldInfoVisible,entrySpawn=true;
 static int category,listOffset,pearlOffset,broadcastOffset,reader,pearlStage,textPage;
 static string selectedProject="",selectedPearl="",selectedBroadcast="",catalog="";
 static float nextPoll,left,right,top,listWidth,width,height;
 const string Prefix="MI_STUDIO_";
 const float CollectionStep=50,CollectionSize=42;
 internal static bool IsOpen { get { return menu!=null&&page!=null; } }
 static string T(string key){return UiText.Get("game.studio_menu."+key);}
 internal static int InsertBeforeRemix(IList<Menu.SimpleButton> list){
  for(int i=0;i<list.Count;i++)if(list[i].signalText=="REMIX")return list.Count-i;
  return 0;
 }
 public static void InstallHooks(List<Action> cleanup){
  var hook=new On.Menu.Menu.hook_ShutDownProcess((orig,m)=>{if(m==menu)Close();orig(m);});
  On.Menu.Menu.ShutDownProcess+=hook;
  cleanup.Add(delegate{Close();On.Menu.Menu.ShutDownProcess-=hook;});
 }
 public static void Install(Menu.MainMenu m){
  Close();
  var field=typeof(Menu.MainMenu).GetField("mainMenuButtons",BindingFlags.Instance|BindingFlags.NonPublic);
  var list=field==null?null:field.GetValue(m) as List<Menu.SimpleButton>;
  if(list==null){list=new List<Menu.SimpleButton>();foreach(var item in m.pages[0].subObjects){var b=item as Menu.SimpleButton;if(b!=null)list.Add(b);}}
  Menu.SimpleButton remix=list.Find(b=>b.signalText=="REMIX");
  Vector2 size=remix==null?new Vector2(110,30):remix.size;
  var button=new Menu.SimpleButton(m,m.pages[0],T("title"),"TEST_MENU",Vector2.zero,size);
  m.AddMainMenuButton(button,delegate{Open(m,0);},InsertBeforeRemix(list));
 }
 public static void Open(Menu.MainMenu m,int tab){
  if(IsOpen&&menu==m){category=tab;textPage=0;Render();return;}
  Close();menu=m;category=tab;originalPage=m.pages[0];originalScene=m.scene;originalBack=m.backObject;originalSelection=m.selectedObject;
  for(int i=0;i<m.container.GetChildCount();i++){var node=m.container.GetChildAt(i);hidden.Add(new KeyValuePair<FNode,bool>(node,node.isVisible));node.isVisible=false;}
  if(m.infoLabel!=null){oldInfoVisible=m.infoLabel.isVisible;m.infoLabel.isVisible=false;}
  page=new Menu.Page(m,null,"More Iterators",0);page.pos=page.lastPos=Vector2.zero;
  page.Container=new FContainer();m.container.AddChild(page.Container);m.pages[0]=page;m.currentPage=0;
  // MouseCursor owns a shared stage container. Never let its base cleanup
  // remove the original cursor container while replacing a Page.
  page.mouseCursor.Container=new FContainer();page.mouseCursor.RemoveSprites();page.RemoveSubObject(page.mouseCursor);
  originalPage.RemoveSubObject(originalPage.mouseCursor);page.mouseCursor=originalPage.mouseCursor;
  page.mouseCursor.owner=page;page.subObjects.Add(page.mouseCursor);
  var scene=new Menu.InteractiveMenuScene(m,page,ModManager.MMF?m.manager.rainWorld.options.subBackground:Menu.MenuScene.SceneID.Landscape_SU);
  page.subObjects.Add(scene);scene.HorizontalDisplace(-Menu.Menu.HorizontalMoveToGetCentered(m.manager));m.scene=scene;
  var dim=new FSprite("pixel"){color=Color.black,alpha=.85f,anchorX=0,anchorY=0,scaleX=m.manager.rainWorld.options.ScreenSize.x,scaleY=m.manager.rainWorld.options.ScreenSize.y};page.Container.AddChild(dim);
  catalog=CreatorRuntime.Catalog();nextPoll=Time.realtimeSinceStartup+.5f;Render();
 }
 public static void Close(){
  if(menu==null)return;
  Clear();if(page!=null){page.RemoveSubObject(page.mouseCursor);page.mouseCursor.owner=originalPage;originalPage.subObjects.Add(page.mouseCursor);page.RemoveSprites();}
  if(originalPage!=null){menu.pages[0]=originalPage;menu.currentPage=0;}
  menu.scene=originalScene;menu.backObject=originalBack;menu.selectedObject=originalSelection;
  foreach(var pair in hidden)pair.Key.isVisible=pair.Value;hidden.Clear();
  if(menu.infoLabel!=null)menu.infoLabel.isVisible=oldInfoVisible;
  menu=null;page=originalPage=null;originalScene=null;originalBack=originalSelection=null;
 }
 static void Clear(){
  foreach(var item in controls){item.RemoveSprites();if(page!=null)page.RemoveSubObject(item);}controls.Clear();navigation.Clear();collectionButtons.Clear();
  foreach(var icon in icons)icon.RemoveFromContainer();icons.Clear();
 }
 static Menu.SimpleButton Button(string label,string signal,float x,float y,float w,float h=32){
  var b=new CreatorMenuButton(menu,page,label,Prefix+signal,new Vector2(x,y),new Vector2(w,h));Fit(b.menuLabel.label,w-24);controls.Add(b);navigation.Add(b);page.subObjects.Add(b);return b;
 }
 static void Label(string text,float x,float y,float w,bool big=false){
  var label=new Menu.MenuLabel(menu,page,text??"",new Vector2(x-w/2,y),new Vector2(w,28),big);label.label.alignment=FLabelAlignment.Left;Fit(label.label,w);controls.Add(label);page.subObjects.Add(label);
 }
 static void Fit(FLabel label,float width){float measured=label.textRect.width;if(measured>width&&measured>0)label.scale=width/measured;}
 static float Measure(string value){return new FLabel(RWCustom.Custom.GetFont(),value).textRect.width;}
 static float CompactWidth(string value,float maximum){return Mathf.Min(maximum,Math.Max(60,Measure(value)+24));}
 static Menu.SimpleButton CompactButton(string label,string signal,float x,float y,float maximum,float h=32){return Button(label,signal,x,y,CompactWidth(label,maximum),h);}
 // CollectionsMenu uses native 42px square buttons on a 50px grid. Keep the
 // atlas sprite at its original size; the native button draws focus/selection.
 static Menu.SimpleButton CollectionButton(string signal,string sprite,Color color,int local){
  int rows=CollectionRows();float x=left+(local/rows)*CollectionStep,y=top-(local%rows)*CollectionStep;
  var b=Button("",signal,x,y,CollectionSize,CollectionSize);collectionButtons.Add(b);
  var icon=new FSprite(sprite){x=x+CollectionSize*.5f,y=y+CollectionSize*.5f,color=color};icons.Add(icon);page.Container.AddChild(icon);return b;
 }
 static int CollectionRows(){return Math.Max(1,(int)((top-138)/CollectionStep)+1);}
 static int CollectionColumns(){return Math.Max(1,(int)((listWidth+8)/CollectionStep));}
 static int CollectionCount(){return CollectionRows()*CollectionColumns();}
 static int CollectionOffset(int offset,int total){int count=CollectionCount();return Mathf.Clamp(offset/count,0,Math.Max(0,(total-1)/count))*count;}
 static void CollectionPages(int total,int offset){
  int count=CollectionCount();if(total<=count)return;
  Button("‹","UP",left,88,42).buttonBehav.greyedOut=offset==0;
  Button("›","DOWN",left+listWidth-42,88,42).buttonBehav.greyedOut=offset+count>=total;
  Label((offset/count+1)+" / "+((total+count-1)/count),left+54,90,listWidth-108);
 }
 static Menu.SimpleButton FindButton(string signal){return navigation.Find(b=>b.signalText==Prefix+signal);}
 static Menu.SimpleButton EnabledButton(string signal){var b=FindButton(signal);return b!=null&&!b.buttonBehav.greyedOut?b:null;}
 static void CollectionNavigation(){
  if(collectionButtons.Count==0)return;
  int rows=CollectionRows();var selected=collectionButtons.Find(b=>b.toggled)??collectionButtons[0];
  var detail=FindButton("READER")??FindButton("TEXT_UP")??FindButton("WEB");
  if(detail.buttonBehav.greyedOut)detail=FindButton("TEXT_DOWN")??FindButton("WEB");
  var tab=FindButton("TAB_"+category);var back=FindButton("CLOSE");
  for(int i=0;i<collectionButtons.Count;i++){
   var b=collectionButtons[i];int row=i%rows,col=i/rows;
   b.nextSelectable[0]=col==0?b:collectionButtons[i-rows];
   b.nextSelectable[1]=row==0?tab:collectionButtons[i-1];
   b.nextSelectable[2]=(col+1)*rows<collectionButtons.Count?collectionButtons[Math.Min(i+rows,collectionButtons.Count-1)]:detail;
   b.nextSelectable[3]=row+1<rows&&i+1<collectionButtons.Count?collectionButtons[i+1]:(EnabledButton("DOWN")??back);
  }
  tab.nextSelectable[3]=selected;
  foreach(var signal in new[]{"READER","TEXT_UP","WEB"}){var b=FindButton(signal);if(b!=null)b.nextSelectable[0]=selected;}
  var readerButton=FindButton("READER");var stageButton=FindButton("STAGE");
  if(readerButton!=null&&stageButton!=null){readerButton.nextSelectable[2]=stageButton;stageButton.nextSelectable[0]=readerButton;if(stageButton.pos.y<readerButton.pos.y){readerButton.nextSelectable[3]=stageButton;stageButton.nextSelectable[1]=readerButton;}}
  foreach(var signal in new[]{"UP","DOWN"}){var b=FindButton(signal);if(b!=null)b.nextSelectable[1]=selected;}
 }
 internal static string ProjectDetail(Dictionary<string,object> project,List<Dictionary<string,object>> all){
  string name=IteratorCatalog.Text(project,"name"),id=IteratorCatalog.Text(project,"projectId");
  if(all.FindAll(p=>IteratorCatalog.Text(p,"name")==name).Count<2)return "";
  DateTime created;
  if(id.StartsWith("oc-")&&id.Length==15&&DateTime.TryParseExact("20"+id.Substring(3),"yyyyMMddHHmmss",CultureInfo.InvariantCulture,DateTimeStyles.None,out created))return created.ToString("yyyy-MM-dd HH:mm:ss",CultureInfo.InvariantCulture);
  return IteratorCatalog.Text(project,"entry");
 }
 static string Clip(string value,int count){value=value??"";return value.Length>count?value.Substring(0,count-1)+"…":value;}
 static int Rows(){return Math.Max(3,(int)((top-126)/(category==0?48:40)));}
 static List<Dictionary<string,object>> Projects(){return CreatorRuntime.MenuProjects();}
 static Dictionary<string,object> SelectedProject(){var all=Projects();var item=all.Find(p=>IteratorCatalog.Text(p,"projectId")==selectedProject);if(item==null&&all.Count>0){item=all[0];selectedProject=IteratorCatalog.Text(item,"projectId");}return item;}
 static string Room(Dictionary<string,object> p){return p==null?"":IteratorCatalog.Text(p,entrySpawn?"entry":"ai");}
 static void Render(){
  if(!IsOpen)return;UiText.Use(menu.manager.rainWorld);var previous=menu.selectedObject as Menu.SimpleButton;string focus=previous==null?"":previous.signalText;Clear();
  width=menu.manager.rainWorld.options.ScreenSize.x;height=menu.manager.rainWorld.options.ScreenSize.y;
  float available=Mathf.Min(1160,width-100);left=(width-available)*.5f;listWidth=category==0?Mathf.Clamp(available*.30f,220,340):Mathf.Min(250,available*.30f);right=left+listWidth+44;top=height-170;
  Label(T("title"),left,height-65,available,true);
  string[] names={T("chambers"),T("broadcasts"),T("pearls")};float tabWidth=Mathf.Min(220,(available-24)/3);
  for(int i=0;i<3;i++){var tab=Button(names[i],"TAB_"+i,left+i*(tabWidth+12),height-118,tabWidth);tab.toggled=i==category;}
  var back=Button(UiText.Get("game.menu.back"),"CLOSE",left,42,110,30);menu.backObject=back;
  if(category==0)Chambers();else if(category==1)Broadcasts();else Pearls();
  if(category!=0)CollectionNavigation();
  // Native geometric navigation keeps columns and tab rows in screen order.
  var restored=navigation.Find(b=>b.signalText==focus&&!b.buttonBehav.greyedOut);
  if(restored==null&&(focus==Prefix+"TEXT_UP"||focus==Prefix+"TEXT_DOWN"))restored=EnabledButton(focus==Prefix+"TEXT_UP"?"TEXT_DOWN":"TEXT_UP");
  if(restored==null&&(focus==Prefix+"UP"||focus==Prefix+"DOWN"||focus.StartsWith(Prefix+"PEARL_")||focus.StartsWith(Prefix+"BROADCAST_")))restored=collectionButtons.Find(b=>b.toggled)??(collectionButtons.Count>0?collectionButtons[0]:null);
  menu.selectedObject=restored??(navigation.Count>0?navigation[category]:back);page.lastSelectedObject=menu.selectedObject;
  page.mouseCursor.BumToFront();
 }
 static void ScrollControls(int total,int offset,int count){
  if(total<=count)return;
  Button("↑","UP",left,88,(listWidth-12)/2).buttonBehav.greyedOut=offset==0;
  Button("↓","DOWN",left+(listWidth+12)/2,88,(listWidth-12)/2).buttonBehav.greyedOut=offset>=total-count;
 }
 static void Chambers(){
  var all=Projects();var chosen=SelectedProject();int rows=Rows();listOffset=Mathf.Clamp(listOffset,0,Math.Max(0,all.Count-rows));
  for(int i=listOffset;i<Math.Min(all.Count,listOffset+rows);i++){var p=all[i];string detail=ProjectDetail(p,all);string label=Clip(IteratorCatalog.Text(p,"name"),26)+(detail.Length==0?"":"\n"+detail);var b=Button(label,"PROJECT_"+IteratorCatalog.Text(p,"projectId"),left,top-(i-listOffset)*48,listWidth,40);b.toggled=IteratorCatalog.Text(p,"projectId")==selectedProject;}
  ScrollControls(all.Count,listOffset,rows);float span=Mathf.Min(400,width-left-right);
  if(chosen==null){CompactButton(UiText.Get("game.menu.studio"),"WEB",right,42,span,30);return;}
  Label(IteratorCatalog.Text(chosen,"name"),right,top,span,true);
  if(!IteratorCatalog.OwnerEnabled(IteratorCatalog.Text(chosen,"ownerMod"))){
   Label(T("local_not_enabled"),right,top-48,span);
   Label(T("enable_local_in_remix"),right,top-80,span);
   CompactButton(T("enter"),"ENTER",right,84,span,40).buttonBehav.greyedOut=true;
   CompactButton(UiText.Get("game.menu.studio"),"WEB",right,42,span,30);return;
  }
  float step=Mathf.Clamp((top-182)/6,32,44),y=top-step;
  string[] options={CreatorSlugcatSelection.Label(menu,Room(chosen)),UiText.Format("game.studio_menu.spawn",entrySpawn?T("waiting"):T("chamber")),UiText.Format("game.menu.mark",UiText.Get(CreatorRuntime.Mark?"game.menu.yes":"game.menu.no")),UiText.Format("game.studio_menu.keep_progress",CreatorRuntime.Reset?T("off"):T("on")),UiText.Format("game.menu.mode",UiText.Get(CreatorRuntime.Mode=="silent"?"game.menu.silent":CreatorRuntime.Mode=="story"?"game.menu.story":"game.menu.read"))};
  string[] signals={"SLUGCAT","SPAWN","MARK","KEEP","MODE"};float optionWidth=110;
  foreach(string option in options)optionWidth=Math.Max(optionWidth,CompactWidth(option,span));
  for(int i=0;i<options.Length;i++)Button(options[i],signals[i],right,y-step*i,optionWidth);
  Label(T("waiting")+" · "+IteratorCatalog.Text(chosen,"entry"),right,y-step*4-36,span);
  Label(T("chamber")+" · "+IteratorCatalog.Text(chosen,"ai"),right,y-step*4-60,span);
  CompactButton(T("enter"),"ENTER",right,84,span,40);CompactButton(UiText.Get("game.menu.studio"),"WEB",right,42,span,30);
 }
 static void Broadcasts(){
  var all=CreatorBroadcastCatalog.All();int count=CollectionCount();broadcastOffset=CollectionOffset(broadcastOffset,all.Count);
  var selected=all.Find(p=>p.uid==selectedBroadcast);if(selected==null&&all.Count>0){selected=all[0];selectedBroadcast=selected.uid;}
  for(int i=broadcastOffset;i<Math.Min(all.Count,broadcastOffset+count);i++){var b=CollectionButton("BROADCAST_"+i,"Symbol_Satellite",Color.white,i-broadcastOffset);b.toggled=all[i].uid==selectedBroadcast;}
  CollectionPages(all.Count,broadcastOffset);CompactButton(UiText.Get("game.gallery.broadcast.studio"),"WEB",right,42,width-left-right,30);
  if(selected==null)return;
  Label(selected.name,right,top,width-left-right,true);Label(selected.region+" / "+selected.room,right,top-36,width-left-right);
  Text(CreatorBroadcastGallery.TextLines(selected),top-82);
 }
 static void Pearls(){
  var all=CreatorPearlCatalog.All();int count=CollectionCount();pearlOffset=CollectionOffset(pearlOffset,all.Count);
  var selected=all.Find(p=>p.uid==selectedPearl);if(selected==null&&all.Count>0){selected=all[0];selectedPearl=selected.uid;reader=0;}
  for(int i=pearlOffset;i<Math.Min(all.Count,pearlOffset+count);i++){var appearance=all[i].appearance??new PearlAppearance();var b=CollectionButton("PEARL_"+i,"Symbol_Pearl",Color.Lerp(IteratorDesign.C(appearance.baseColor),IteratorDesign.C(appearance.highlightColor),.35f),i-pearlOffset);b.toggled=all[i].uid==selectedPearl;}
  CollectionPages(all.Count,pearlOffset);CompactButton(UiText.Get("game.gallery.pearl.studio"),"WEB",right,42,width-left-right,30);
  if(selected==null)return;
  Label(selected.name,right,top,width-left-right,true);
  var readers=selected.readers??new PearlReaderProfile[0];if(readers.Length==0)return;
  reader=Mathf.Clamp(reader,0,readers.Length-1);var selectedReader=readers[reader];if(selectedReader==null)return;
  float span=width-left-right,controlsY=top-46;
  var readerButton=CompactButton(UiText.Format("game.gallery.pearl.reader",selectedReader.name),"READER",right,controlsY,span);
  string[] stages={"read","repeat","leaving","returning","many"};string stage=UiText.Get("game.gallery.pearl.stage."+stages[pearlStage]);float stageWidth=CompactWidth(stage,span);
  float stageX=right+readerButton.size.x+12;if(stageX+stageWidth>right+span){stageX=right;controlsY-=42;}
  Button(stage,"STAGE",stageX,controlsY,stageWidth);
  var shared=CreatorDialogueProfile.For(IteratorDesign.ForId(selectedReader.oracleId)).pearlReading;var lines=new List<string>();
  if(pearlStage==0)Lines(lines,selectedReader.read);else{var groups=pearlStage==1?shared.repeat:pearlStage==2?selectedReader.leaving:pearlStage==3?selectedReader.returning:shared.many;if(groups!=null)foreach(var group in groups){if(group==null)continue;Wrap(lines,group.name);Lines(lines,group.lines);lines.Add("");}}
  Text(lines,controlsY-50);
 }
 static void Lines(List<string> result,CreatorDialogueLine[] lines){if(lines!=null)foreach(var line in lines)if(line!=null)Wrap(result,line.text);}
 static void Wrap(List<string> result,string text){if(text==null)return;foreach(var part in text.Replace("<LINE>","\n").Split('\n')){if(part.Length==0){result.Add("");continue;}int start=0;while(start<part.Length){int count=1;float max=Math.Max(100,width-left-right);while(start+count<part.Length&&Measure(part.Substring(start,count+1))<=max)count++;result.Add(part.Substring(start,count));start+=count;}}}
 static void Text(List<string> source,float y){
  var lines=new List<string>();foreach(string line in source)Wrap(lines,line);int count=Math.Max(1,(int)((y-146)/27));float span=width-left-right;
  textPage=Mathf.Clamp(textPage,0,Math.Max(0,(lines.Count-1)/count));for(int i=0;i<count&&textPage*count+i<lines.Count;i++)Label(lines[textPage*count+i],right,y-i*27,span);
  if(lines.Count>count){
   float maximum=(span-80)/2;var previous=CompactButton(UiText.Get("game.gallery.previous_text"),"TEXT_UP",right,90,maximum);previous.buttonBehav.greyedOut=textPage==0;
   var next=CompactButton(UiText.Get("game.gallery.next_text"),"TEXT_DOWN",right+previous.size.x+12,90,maximum);next.buttonBehav.greyedOut=(textPage+1)*count>=lines.Count;
   Label((textPage+1)+" / "+((lines.Count+count-1)/count),next.pos.x+next.size.x+12,90,56);
  }
 }
 static void Scroll(int delta){if(category==0)listOffset=Math.Max(0,listOffset+delta);else if(category==1)broadcastOffset=Math.Max(0,broadcastOffset+delta*CollectionCount());else pearlOffset=Math.Max(0,pearlOffset+delta*CollectionCount());Render();}
 public static void Update(Menu.MainMenu m){
  if(!IsOpen||m!=menu||!m.Active||m.manager.dialog!=null)return;
  if(m.mouseScrollWheelMovement!=0&&m.mousePosition.x>=left&&m.mousePosition.x<=left+listWidth&&m.mousePosition.y>88&&m.mousePosition.y<top+(category==0?40:CollectionSize))Scroll(m.mouseScrollWheelMovement>0?1:-1);
  if(Input.GetKeyDown(KeyCode.Escape)){Close();return;}
  if(Time.realtimeSinceStartup<nextPoll)return;nextPoll=Time.realtimeSinceStartup+.5f;string current=CreatorRuntime.Catalog();if(current!=catalog){catalog=current;Render();}
 }
 public static bool Signal(Menu.MainMenu m,string signal){
  if(signal=="TEST_MENU"){if(IsOpen)Close();else Open(m,0);return true;}
  if(signal=="TEST_PEARLS"||signal=="TEST_BROADCASTS"){Open(m,signal=="TEST_PEARLS"?2:1);return true;}
  if(String.IsNullOrEmpty(signal)||!signal.StartsWith(Prefix)||!IsOpen||m!=menu)return false;string action=signal.Substring(Prefix.Length);
  if(action=="CLOSE"){Close();return true;}
  if(action.StartsWith("TAB_")){int.TryParse(action.Substring(4),out category);category=Mathf.Clamp(category,0,2);textPage=0;}
  else if(action.StartsWith("PROJECT_")){selectedProject=action.Substring(8);}
  else if(action.StartsWith("PEARL_")){int i;var all=CreatorPearlCatalog.All();if(int.TryParse(action.Substring(6),out i)&&i>=0&&i<all.Count){selectedPearl=all[i].uid;reader=pearlStage=textPage=0;}}
  else if(action.StartsWith("BROADCAST_")){int i;var all=CreatorBroadcastCatalog.All();if(int.TryParse(action.Substring(10),out i)&&i>=0&&i<all.Count){selectedBroadcast=all[i].uid;textPage=0;}}
  else if(action=="UP"||action=="DOWN"){Scroll(action=="UP"?-1:1);return true;}
  else if(action=="SLUGCAT")CreatorSlugcatSelection.Next(m.manager.rainWorld);
  else if(action=="SPAWN")entrySpawn=!entrySpawn;
  else if(action=="MARK")CreatorRuntime.Mark=!CreatorRuntime.Mark;
  else if(action=="KEEP")CreatorRuntime.Reset=!CreatorRuntime.Reset;
  else if(action=="MODE")CreatorRuntime.Mode=CreatorRuntime.Mode=="silent"?"story":CreatorRuntime.Mode=="story"?"read":"silent";
  else if(action=="READER"){var p=CreatorPearlCatalog.All().Find(v=>v.uid==selectedPearl);if(p!=null&&p.readers!=null&&p.readers.Length>0)reader=(reader+1)%p.readers.Length;textPage=0;}
  else if(action=="STAGE"){pearlStage=(pearlStage+1)%5;textPage=0;}
  else if(action=="TEXT_UP")textPage=Math.Max(0,textPage-1);
  else if(action=="TEXT_DOWN")textPage++;
  else if(action=="WEB"){StudioLauncher.Open(m,category==0?"appearance":category==1?"broadcasts":"pearls",category==0?selectedProject:"");return true;}
  else if(action=="ENTER"){var p=SelectedProject();if(p!=null&&IteratorCatalog.OwnerEnabled(IteratorCatalog.Text(p,"ownerMod"))){string room=Room(p);CreatorRuntime.Prepare(room,CreatorRuntime.Mode,CreatorRuntime.Mark,CreatorRuntime.Reset);MoreIteratorsPlugin.Instance.LaunchPreview(m,room);}return true;}
  Render();return true;
 }
}
}
#endif
