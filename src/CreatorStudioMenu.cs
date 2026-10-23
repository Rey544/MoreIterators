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
 static int category,listOffset,pearlOffset,broadcastOffset,reader,pearlStage,textOffset,broadcastPage;
 static string selectedProject="",selectedPearl="",selectedBroadcast="",catalog="";
 static CreatorMenuScrollBar listScroll,textScroll;
 static readonly List<Menu.MenuLabel> textLabels=new List<Menu.MenuLabel>();
 static List<string> textLines=new List<string>();
 static float textTop,textBottom;
 static float nextPoll,left,right,top,listWidth,width,height;
 const string Prefix="MI_STUDIO_";
 const float CollectionStep=50,CollectionSize=42;
 const float FooterY=42,FooterHeight=32,FooterGap=12,ContentBottom=90;
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
  if(IsOpen&&menu==m){category=tab;textOffset=broadcastPage=0;Render();return;}
  Close();menu=m;category=tab;textOffset=broadcastPage=0;originalPage=m.pages[0];originalScene=m.scene;originalBack=m.backObject;originalSelection=m.selectedObject;
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
  foreach(var item in controls){item.RemoveSprites();if(page!=null)page.RemoveSubObject(item);}controls.Clear();navigation.Clear();collectionButtons.Clear();textLabels.Clear();listScroll=textScroll=null;
  foreach(var icon in icons)icon.RemoveFromContainer();icons.Clear();
 }
 static Menu.SimpleButton Button(string label,string signal,float x,float y,float w,float h=32){
  var b=new CreatorMenuButton(menu,page,label,Prefix+signal,new Vector2(x,y),new Vector2(w,h));Fit(b.menuLabel.label,w-24);controls.Add(b);navigation.Add(b);page.subObjects.Add(b);return b;
 }
 static Menu.MenuLabel Label(string text,float x,float y,float w,bool big=false){
  var label=new Menu.MenuLabel(menu,page,text??"",new Vector2(x-w/2,y),new Vector2(w,28),big);label.label.alignment=FLabelAlignment.Left;Fit(label.label,w);controls.Add(label);page.subObjects.Add(label);return label;
 }
 static void Fit(FLabel label,float width){float measured=label.textRect.width;if(measured>width&&measured>0)label.scale=width/measured;}
 static float Measure(string value){return new FLabel(RWCustom.Custom.GetFont(),value).textRect.width;}
 static float CompactWidth(string value,float maximum){return Mathf.Min(maximum,Math.Max(60,Measure(value)+24));}
 static Menu.SimpleButton CompactButton(string label,string signal,float x,float y,float maximum,float h=32){return Button(label,signal,x,y,CompactWidth(label,maximum),h);}
 // CollectionsMenu uses native 42px square buttons on a 50px grid. Keep the
 // atlas sprite at its original size; the native button draws focus/selection.
 static Menu.SimpleButton CollectionButton(string signal,string sprite,Color color,int local){
  int columns=CollectionColumns();float gridWidth=(columns-1)*CollectionStep+CollectionSize;float x=left+(listWidth-gridWidth)*.5f+(local%columns)*CollectionStep,y=top-(local/columns)*CollectionStep;
  var b=Button("",signal,x,y,CollectionSize,CollectionSize);collectionButtons.Add(b);
  var icon=new FSprite(sprite){x=x+CollectionSize*.5f,y=y+CollectionSize*.5f,color=color};icons.Add(icon);page.Container.AddChild(icon);return b;
 }
 static int CollectionRows(){return Math.Max(1,(int)((top-ContentBottom)/CollectionStep)+1);}
 static int CollectionColumns(){return Math.Max(1,(int)((listWidth+8)/CollectionStep));}
 static int CollectionCount(){return CollectionRows()*CollectionColumns();}
 static int CollectionOffset(int offset,int total){return Mathf.Clamp(offset,0,Math.Max(0,(total+CollectionColumns()-1)/CollectionColumns()-CollectionRows()));}
 static CreatorMenuScrollBar ScrollBar(string key,float x,float bottom,float upper,int total,int count,int offset,Action<int> changed){
  if(total<=count)return null;var bar=new CreatorMenuScrollBar(menu,page,key,new Vector2(x,bottom),upper-bottom,total,count,offset,changed);controls.Add(bar);page.subObjects.Add(bar);return bar;
 }
 static void CollectionScroll(int total,int offset){listScroll=ScrollBar("LIST",left+listWidth+6,top-(CollectionRows()-1)*CollectionStep,top+CollectionSize,(total+CollectionColumns()-1)/CollectionColumns(),CollectionRows(),offset,SetListOffset);}
 static Menu.SimpleButton CenterButton(string label,string signal,float y,float maximum,float h=32){float span=width-left-right,w=CompactWidth(label,Math.Min(maximum,span));return Button(label,signal,right+(span-w)*.5f,y,w,h);}
 static void FooterActions(string editorLabel,bool preview=false,bool enabled=true){
  float span=width-left-right;
  if(!preview){CenterButton(editorLabel,"WEB",FooterY,span,FooterHeight);return;}
  string enterLabel=T("enter");float maximum=(span-FooterGap)*.5f;
  float actionWidth=Math.Max(CompactWidth(editorLabel,maximum),CompactWidth(enterLabel,maximum));
  float x=right+(span-actionWidth*2-FooterGap)*.5f;
  Button(editorLabel,"WEB",x,FooterY,actionWidth,FooterHeight);
  Button(enterLabel,"ENTER",x+actionWidth+FooterGap,FooterY,actionWidth,FooterHeight).buttonBehav.greyedOut=!enabled;
 }
 static void FooterNavigation(){
  var back=FindButton("CLOSE");var web=FindButton("WEB");var enter=EnabledButton("ENTER");
  back.nextSelectable[2]=web;web.nextSelectable[0]=back;
  if(enter!=null){web.nextSelectable[2]=enter;enter.nextSelectable[0]=web;enter.nextSelectable[2]=enter;}
 }
 static Menu.SimpleButton FindButton(string signal){return navigation.Find(b=>b.signalText==Prefix+signal);}
 static Menu.SimpleButton EnabledButton(string signal){var b=FindButton(signal);return b!=null&&!b.buttonBehav.greyedOut?b:null;}
 static void CollectionNavigation(){
  if(collectionButtons.Count==0)return;
  int columns=CollectionColumns();var selected=collectionButtons.Find(b=>b.toggled)??collectionButtons[0];
  Menu.MenuObject detail=FindButton("READER")??FindButton("TEXT_UP")??FindButton("WEB");
  if(detail is Menu.SimpleButton&&((Menu.SimpleButton)detail).buttonBehav.greyedOut)detail=EnabledButton("TEXT_DOWN")??FindButton("WEB");
  var tab=FindButton("TAB_"+category);var back=FindButton("CLOSE");
  for(int i=0;i<collectionButtons.Count;i++){
   var b=collectionButtons[i];int row=i/columns,col=i%columns;
   b.nextSelectable[0]=col==0?b:collectionButtons[i-1];
   b.nextSelectable[1]=row==0?tab:collectionButtons[i-columns];
   b.nextSelectable[2]=col+1<columns&&i+1<collectionButtons.Count?collectionButtons[i+1]:(Menu.MenuObject)listScroll??detail;
   b.nextSelectable[3]=i+columns<collectionButtons.Count?collectionButtons[i+columns]:(Menu.MenuObject)listScroll??back;
  }
  tab.nextSelectable[3]=selected;
  foreach(var signal in new[]{"READER","TEXT_UP","TEXT_DOWN","WEB"}){var b=FindButton(signal);if(b!=null)b.nextSelectable[0]=selected;}
  var rb=FindButton("READER");var sb=FindButton("STAGE");
  if(rb!=null&&sb!=null){rb.nextSelectable[2]=sb;sb.nextSelectable[0]=rb;if(sb.pos.y<rb.pos.y){rb.nextSelectable[3]=sb;sb.nextSelectable[1]=rb;}}
  if(listScroll!=null){listScroll.nextSelectable[0]=selected;listScroll.nextSelectable[2]=detail;}
  if(textScroll!=null){textScroll.nextSelectable[0]=detail;textScroll.nextSelectable[2]=FindButton("WEB");if(rb!=null)rb.nextSelectable[3]=textScroll;if(sb!=null)sb.nextSelectable[3]=textScroll;}
  var previous=FindButton("TEXT_UP");var next=FindButton("TEXT_DOWN");var web=FindButton("WEB");
  if(previous!=null&&next!=null){
   previous.nextSelectable[2]=next.buttonBehav.greyedOut?(Menu.MenuObject)textScroll??web:next;
   next.nextSelectable[0]=previous.buttonBehav.greyedOut?selected:previous;
   previous.nextSelectable[1]=next.nextSelectable[1]=(Menu.MenuObject)textScroll??tab;
   previous.nextSelectable[3]=next.nextSelectable[3]=web;
   web.nextSelectable[1]=EnabledButton("TEXT_DOWN")??EnabledButton("TEXT_UP")??(Menu.MenuObject)textScroll??selected;
  }
 }
 internal static string ProjectDetail(Dictionary<string,object> project,List<Dictionary<string,object>> all){
  string name=IteratorCatalog.Text(project,"name"),id=IteratorCatalog.Text(project,"projectId");
  if(all.FindAll(p=>IteratorCatalog.Text(p,"name")==name).Count<2)return "";
  DateTime created;
  if(id.StartsWith("oc-")&&id.Length==15&&DateTime.TryParseExact("20"+id.Substring(3),"yyyyMMddHHmmss",CultureInfo.InvariantCulture,DateTimeStyles.None,out created))return created.ToString("yyyy-MM-dd HH:mm:ss",CultureInfo.InvariantCulture);
  return IteratorCatalog.Text(project,"entry");
 }
 static string Clip(string value,int count){value=value??"";return value.Length>count?value.Substring(0,count-1)+"…":value;}
 static int Rows(){return Math.Max(1,(int)((top-ContentBottom)/48)+1);}
 static List<Dictionary<string,object>> Projects(){return CreatorRuntime.MenuProjects();}
 static Dictionary<string,object> SelectedProject(){var all=Projects();var item=all.Find(p=>IteratorCatalog.Text(p,"projectId")==selectedProject);if(item==null&&all.Count>0){item=all[0];selectedProject=IteratorCatalog.Text(item,"projectId");}return item;}
 static string Room(Dictionary<string,object> p){return p==null?"":IteratorCatalog.Text(p,entrySpawn?"entry":"ai");}
 static void Render(){
  if(!IsOpen)return;UiText.Use(menu.manager.rainWorld);var previous=menu.selectedObject as Menu.SimpleButton;var oldScroll=menu.selectedObject as CreatorMenuScrollBar;string focus=previous==null?"":previous.signalText;string scrollFocus=oldScroll==null?"":oldScroll.key;Clear();
  width=menu.manager.rainWorld.options.ScreenSize.x;height=menu.manager.rainWorld.options.ScreenSize.y;
  float available=Mathf.Min(1160,width-100);left=(width-available)*.5f;listWidth=category==0?Mathf.Clamp(available*.30f,220,340):Mathf.Min(250,available*.30f);right=left+listWidth+44;top=height-170;
  Label(T("title"),left,height-65,available,true);
  string[] names={T("chambers"),T("broadcasts"),T("pearls")};float tabWidth=Mathf.Min(220,(available-24)/3);
  for(int i=0;i<3;i++){var tab=Button(names[i],"TAB_"+i,left+i*(tabWidth+12),height-118,tabWidth);tab.toggled=i==category;}
  var back=Button(UiText.Get("game.menu.back"),"CLOSE",left,FooterY,110,FooterHeight);menu.backObject=back;
  if(category==0)Chambers();else if(category==1)Broadcasts();else Pearls();
  if(category!=0)CollectionNavigation();else ProjectNavigation();FooterNavigation();
  // Native geometric navigation keeps columns and tab rows in screen order.
  var restored=navigation.Find(b=>b.signalText==focus&&!b.buttonBehav.greyedOut);
  if(restored==null&&(focus==Prefix+"TEXT_UP"||focus==Prefix+"TEXT_DOWN"))restored=EnabledButton(focus==Prefix+"TEXT_UP"?"TEXT_DOWN":"TEXT_UP");
  if(restored==null&&(focus==Prefix+"UP"||focus==Prefix+"DOWN"||focus.StartsWith(Prefix+"PEARL_")||focus.StartsWith(Prefix+"BROADCAST_")))restored=collectionButtons.Find(b=>b.toggled)??(collectionButtons.Count>0?collectionButtons[0]:null);
  menu.selectedObject=(scrollFocus=="LIST"?(Menu.MenuObject)listScroll:scrollFocus=="TEXT"?textScroll:null)??restored??(navigation.Count>0?navigation[category]:back);page.lastSelectedObject=menu.selectedObject;
  page.mouseCursor.BumToFront();
 }
 static void ProjectButtons(){
  var all=Projects();int rows=Rows();listOffset=Mathf.Clamp(listOffset,0,Math.Max(0,all.Count-rows));
  for(int i=listOffset;i<Math.Min(all.Count,listOffset+rows);i++){var p=all[i];string detail=ProjectDetail(p,all);string label=Clip(IteratorCatalog.Text(p,"name"),26)+(detail.Length==0?"":"\n"+detail);var b=Button(label,"PROJECT_"+IteratorCatalog.Text(p,"projectId"),left,top-(i-listOffset)*48,listWidth,40);b.toggled=IteratorCatalog.Text(p,"projectId")==selectedProject;collectionButtons.Add(b);}
 }
 static void ProjectNavigation(){
  if(listScroll==null||collectionButtons.Count==0)return;var chosen=collectionButtons.Find(b=>b.toggled)??collectionButtons[0];
  listScroll.nextSelectable[0]=chosen;listScroll.nextSelectable[2]=FindButton("SLUGCAT")??FindButton("WEB");
  foreach(var b in collectionButtons)b.nextSelectable[2]=listScroll;
  collectionButtons[collectionButtons.Count-1].nextSelectable[3]=listScroll;
 }
 static void CollectionButtons(){
  int count=CollectionCount(),columns=CollectionColumns();
  if(category==1){var all=CreatorBroadcastCatalog.All();broadcastOffset=CollectionOffset(broadcastOffset,all.Count);int start=broadcastOffset*columns;for(int i=start;i<Math.Min(all.Count,start+count);i++){var b=CollectionButton("BROADCAST_"+i,"Symbol_Satellite",Color.white,i-start);b.toggled=all[i].uid==selectedBroadcast;}}
  else{var all=CreatorPearlCatalog.All();pearlOffset=CollectionOffset(pearlOffset,all.Count);int start=pearlOffset*columns;for(int i=start;i<Math.Min(all.Count,start+count);i++){var appearance=all[i].appearance??new PearlAppearance();var b=CollectionButton("PEARL_"+i,"Symbol_Pearl",Color.Lerp(IteratorDesign.C(appearance.baseColor),IteratorDesign.C(appearance.highlightColor),.35f),i-start);b.toggled=all[i].uid==selectedPearl;}}
 }
 static void SetListOffset(int offset){
  if(category==0)listOffset=offset;else if(category==1)broadcastOffset=offset;else pearlOffset=offset;
  var focused=menu.selectedObject as Menu.SimpleButton;string signal=focused==null?"":focused.signalText;int focusIndex=collectionButtons.IndexOf(focused);
  foreach(var b in collectionButtons){b.RemoveSprites();page.RemoveSubObject(b);controls.Remove(b);navigation.Remove(b);}collectionButtons.Clear();
  foreach(var icon in icons)icon.RemoveFromContainer();icons.Clear();
  if(category==0){ProjectButtons();ProjectNavigation();}else{CollectionButtons();CollectionNavigation();}FooterNavigation();
  if(focusIndex>=0&&collectionButtons.Count>0){menu.selectedObject=collectionButtons.Find(b=>b.signalText==signal)??collectionButtons[Math.Min(focusIndex,collectionButtons.Count-1)];page.lastSelectedObject=menu.selectedObject;}
 }
 static void Chambers(){
  var all=Projects();var chosen=SelectedProject();int rows=Rows();ProjectButtons();
  listScroll=ScrollBar("LIST",left+listWidth+6,top-(rows-1)*48,top+40,all.Count,rows,listOffset,SetListOffset);float span=Mathf.Min(400,width-left-right);
  if(chosen==null){FooterActions(UiText.Get("game.menu.studio"));return;}
  Label(IteratorCatalog.Text(chosen,"name"),right,top,span,true);
  if(!IteratorCatalog.OwnerEnabled(IteratorCatalog.Text(chosen,"ownerMod"))){
   Label(T("local_not_enabled"),right,top-48,span);
   Label(T("enable_local_in_remix"),right,top-80,span);
   FooterActions(UiText.Get("game.menu.studio"),true,false);return;
  }
  float step=Mathf.Clamp((top-182)/6,32,44),y=top-step;
  string[] options={CreatorSlugcatSelection.Label(menu,Room(chosen)),UiText.Format("game.studio_menu.spawn",entrySpawn?T("waiting"):T("chamber")),UiText.Format("game.menu.mark",UiText.Get(CreatorRuntime.Mark?"game.menu.yes":"game.menu.no")),UiText.Format("game.studio_menu.keep_progress",CreatorRuntime.Reset?T("off"):T("on")),UiText.Format("game.menu.mode",UiText.Get(CreatorRuntime.Mode=="silent"?"game.menu.silent":CreatorRuntime.Mode=="story"?"game.menu.story":"game.menu.read"))};
  string[] signals={"SLUGCAT","SPAWN","MARK","KEEP","MODE"};float optionWidth=110;
  foreach(string option in options)optionWidth=Math.Max(optionWidth,CompactWidth(option,span));
  for(int i=0;i<options.Length;i++)Button(options[i],signals[i],right+(width-left-right-optionWidth)*.5f,y-step*i,optionWidth);
  Label(T("waiting")+" · "+IteratorCatalog.Text(chosen,"entry"),right,y-step*4-36,span);
  Label(T("chamber")+" · "+IteratorCatalog.Text(chosen,"ai"),right,y-step*4-60,span);
  FooterActions(UiText.Get("game.menu.studio"),true);
 }
 static void Broadcasts(){
  var all=CreatorBroadcastCatalog.All();broadcastOffset=CollectionOffset(broadcastOffset,all.Count);
  var selected=all.Find(p=>p.uid==selectedBroadcast);if(selected==null&&all.Count>0){selected=all[0];selectedBroadcast=selected.uid;}
  CollectionButtons();CollectionScroll(all.Count,broadcastOffset);FooterActions(UiText.Get("game.gallery.broadcast.studio"));
  if(selected==null)return;
  Label(selected.name,right,top,width-left-right,true);Label(selected.region+" / "+selected.room,right,top-36,width-left-right);
  int pages=selected.pages==null?0:selected.pages.Length;broadcastPage=Mathf.Clamp(broadcastPage,0,Math.Max(0,pages-1));
  Text(CreatorBroadcastGallery.TextLines(selected,broadcastPage),top-82);
  float span=width-left-right,maximum=(span-12)*.5f;string prev=UiText.Get("game.gallery.previous_text"),next=UiText.Get("game.gallery.next_text");float pw=CompactWidth(prev,maximum),nw=CompactWidth(next,maximum),x=right+(span-pw-nw-12)*.5f;
  Button(prev,"TEXT_UP",x,84,pw).buttonBehav.greyedOut=broadcastPage==0;Button(next,"TEXT_DOWN",x+pw+12,84,nw).buttonBehav.greyedOut=broadcastPage>=pages-1;
 }
 static void Pearls(){
  var all=CreatorPearlCatalog.All();pearlOffset=CollectionOffset(pearlOffset,all.Count);
  var selected=all.Find(p=>p.uid==selectedPearl);if(selected==null&&all.Count>0){selected=all[0];selectedPearl=selected.uid;reader=0;}
  CollectionButtons();CollectionScroll(all.Count,pearlOffset);FooterActions(UiText.Get("game.gallery.pearl.studio"));
  if(selected==null)return;
  Label(selected.name,right,top,width-left-right,true);
  var readers=selected.readers??new PearlReaderProfile[0];if(readers.Length==0)return;
  reader=Mathf.Clamp(reader,0,readers.Length-1);var selectedReader=readers[reader];if(selectedReader==null)return;
  float span=width-left-right,controlsY=top-46;
  string readerText=UiText.Format("game.gallery.pearl.reader",selectedReader.name);float readerWidth=CompactWidth(readerText,span);
  string[] stages={"read","repeat","leaving","returning","many"};string stage=UiText.Get("game.gallery.pearl.stage."+stages[pearlStage]);float stageWidth=CompactWidth(stage,span);
  bool sameRow=readerWidth+stageWidth+12<=span;float readerX=right+(span-(sameRow?readerWidth+stageWidth+12:readerWidth))*.5f;
  Button(readerText,"READER",readerX,controlsY,readerWidth);
  float stageX=sameRow?readerX+readerWidth+12:right+(span-stageWidth)*.5f;if(!sameRow)controlsY-=42;
  Button(stage,"STAGE",stageX,controlsY,stageWidth);
  var shared=CreatorDialogueProfile.For(IteratorDesign.ForId(selectedReader.oracleId)).pearlReading;var lines=new List<string>();
  if(pearlStage==0)Lines(lines,selectedReader.read);else{var groups=pearlStage==1?shared.repeat:pearlStage==2?selectedReader.leaving:pearlStage==3?selectedReader.returning:shared.many;if(groups!=null)foreach(var group in groups){if(group==null)continue;Wrap(lines,group.name);Lines(lines,group.lines);lines.Add("");}}
  Text(lines,controlsY-50);
 }
 static void Lines(List<string> result,CreatorDialogueLine[] lines){if(lines!=null)foreach(var line in lines)if(line!=null)Wrap(result,line.text);}
 static void Wrap(List<string> result,string text){if(text==null)return;foreach(var part in text.Replace("<LINE>","\n").Split('\n')){if(part.Length==0){result.Add("");continue;}int start=0;while(start<part.Length){int count=1;float max=Math.Max(40,width-left-right-24);while(start+count<part.Length&&Measure(part.Substring(start,count+1))<=max)count++;result.Add(part.Substring(start,count));start+=count;}}}
 static void Text(List<string> source,float y){
  textLines=new List<string>();foreach(string line in source)Wrap(textLines,line);float bottom=category==1?130:ContentBottom;int count=Math.Max(1,(int)((y-bottom)/27)+1);float span=width-left-right-24;
  textOffset=Mathf.Clamp(textOffset,0,Math.Max(0,textLines.Count-count));textTop=y+28;textBottom=y-(count-1)*27;
  for(int i=0;i<count;i++)textLabels.Add(Label("",right,y-i*27,span));
  textScroll=ScrollBar("TEXT",right+span+8,textBottom,textTop,textLines.Count,count,textOffset,SetTextOffset);SetTextOffset(textOffset);
 }
 static void SetTextOffset(int offset){textOffset=offset;for(int i=0;i<textLabels.Count;i++)textLabels[i].text=textOffset+i<textLines.Count?textLines[textOffset+i]:"";}
 static void Scroll(int delta){if(listScroll!=null)listScroll.Move(delta);}
 public static void Update(Menu.MainMenu m){
  if(!IsOpen||m!=menu||!m.Active||m.manager.dialog!=null)return;
  if(listScroll!=null)listScroll.Poll();if(textScroll!=null)textScroll.Poll();
  if(m.mouseScrollWheelMovement!=0){
   int delta=m.mouseScrollWheelMovement;
   if(m.mousePosition.x>=left&&m.mousePosition.x<=left+listWidth+22&&m.mousePosition.y>88&&m.mousePosition.y<top+(category==0?40:CollectionSize))Scroll(delta);
   else if(textScroll!=null&&m.mousePosition.x>=right&&m.mousePosition.x<=width-left&&m.mousePosition.y>=textBottom&&m.mousePosition.y<=textTop)textScroll.Move(delta*3);
  }
  if(Input.GetKeyDown(KeyCode.Escape)){Close();return;}
  if(Time.realtimeSinceStartup<nextPoll)return;nextPoll=Time.realtimeSinceStartup+.5f;string current=CreatorRuntime.Catalog();if(current!=catalog){catalog=current;Render();}
 }
 public static bool Signal(Menu.MainMenu m,string signal){
  if(signal=="TEST_MENU"){if(IsOpen)Close();else Open(m,0);return true;}
  if(signal=="TEST_PEARLS"||signal=="TEST_BROADCASTS"){Open(m,signal=="TEST_PEARLS"?2:1);return true;}
  if(String.IsNullOrEmpty(signal)||!signal.StartsWith(Prefix)||!IsOpen||m!=menu)return false;string action=signal.Substring(Prefix.Length);
  if(action=="CLOSE"){Close();return true;}
  if(action.StartsWith("TAB_")){int.TryParse(action.Substring(4),out category);category=Mathf.Clamp(category,0,2);textOffset=broadcastPage=0;}
  else if(action.StartsWith("PROJECT_")){selectedProject=action.Substring(8);}
  else if(action.StartsWith("PEARL_")){int i;var all=CreatorPearlCatalog.All();if(int.TryParse(action.Substring(6),out i)&&i>=0&&i<all.Count){selectedPearl=all[i].uid;reader=pearlStage=textOffset=broadcastPage=0;}}
  else if(action.StartsWith("BROADCAST_")){int i;var all=CreatorBroadcastCatalog.All();if(int.TryParse(action.Substring(10),out i)&&i>=0&&i<all.Count){selectedBroadcast=all[i].uid;textOffset=broadcastPage=0;}}
  else if(action=="UP"||action=="DOWN"){Scroll(action=="UP"?-1:1);return true;}
  else if(action=="SLUGCAT")CreatorSlugcatSelection.Next(m.manager.rainWorld);
  else if(action=="SPAWN")entrySpawn=!entrySpawn;
  else if(action=="MARK")CreatorRuntime.Mark=!CreatorRuntime.Mark;
  else if(action=="KEEP")CreatorRuntime.Reset=!CreatorRuntime.Reset;
  else if(action=="MODE")CreatorRuntime.Mode=CreatorRuntime.Mode=="silent"?"story":CreatorRuntime.Mode=="story"?"read":"silent";
  else if(action=="READER"){var p=CreatorPearlCatalog.All().Find(v=>v.uid==selectedPearl);if(p!=null&&p.readers!=null&&p.readers.Length>0)reader=(reader+1)%p.readers.Length;textOffset=broadcastPage=0;}
  else if(action=="STAGE"){pearlStage=(pearlStage+1)%5;textOffset=broadcastPage=0;}
  else if(action=="TEXT_UP"){broadcastPage=Math.Max(0,broadcastPage-1);textOffset=0;}
  else if(action=="TEXT_DOWN"){broadcastPage++;textOffset=0;}
  else if(action=="WEB"){StudioLauncher.Open(m,category==0?"appearance":category==1?"broadcasts":"pearls",category==0?selectedProject:"");return true;}
  else if(action=="ENTER"){var p=SelectedProject();if(p!=null&&IteratorCatalog.OwnerEnabled(IteratorCatalog.Text(p,"ownerMod"))){string room=Room(p);CreatorRuntime.Prepare(room,CreatorRuntime.Mode,CreatorRuntime.Mark,CreatorRuntime.Reset);MoreIteratorsPlugin.Instance.LaunchPreview(m,room);}return true;}
  Render();return true;
 }
}
}
#endif
