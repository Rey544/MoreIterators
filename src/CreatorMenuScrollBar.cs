#if !PLAYBACK
namespace MoreIterators {
using System;
using UnityEngine;

// A narrow native-menu selectable. Scrolling changes only its viewport content;
// this object survives each movement, so dragging and controller focus remain stable.
internal sealed class CreatorMenuScrollBar : Menu.RectangularMenuObject, Menu.SelectableMenuObject, Menu.ButtonMenuObject {
 readonly FSprite rail,thumb;
 readonly Menu.ButtonBehavior button;
 readonly Action<int> changed;
 internal readonly string key;
 internal int Offset { get; private set; }
 internal int Maximum { get; private set; }
 internal int Visible { get; private set; }
 internal bool Dragging { get; private set; }
 float dragOffset;
 int heldDirection,heldFrames;
 internal float ThumbHeight { get { return Math.Min(size.y,Math.Max(24,size.y*Visible/(Visible+Maximum))); } }
 internal float ThumbBottom { get { return pos.y+(size.y-ThumbHeight)*(1f-(Maximum==0?0:(float)Offset/Maximum)); } }
 public bool IsMouseOverMe { get { return menu.mousePosition.x>=pos.x&&menu.mousePosition.x<=pos.x+size.x&&menu.mousePosition.y>=pos.y&&menu.mousePosition.y<=pos.y+size.y; } }
 public bool CurrentlySelectableMouse { get { return Maximum>0; } }
 public bool CurrentlySelectableNonMouse { get { return Maximum>0; } }
 public Menu.ButtonBehavior GetButtonBehavior { get { return button; } }
 public void Clicked(){}
 internal CreatorMenuScrollBar(Menu.Menu menu,Menu.MenuObject owner,string key,Vector2 pos,float height,int total,int visible,int offset,Action<int> changed):base(menu,owner,pos,new Vector2(16,height)) {
  this.key=key;this.changed=changed;button=new Menu.ButtonBehavior(this);Visible=Math.Max(1,visible);Maximum=Math.Max(0,total-Visible);Offset=Mathf.Clamp(offset,0,Maximum);
  rail=new FSprite("pixel"){color=Color.white,anchorY=0,scaleX=1};thumb=new FSprite("pixel"){color=Color.white,anchorY=0,scaleX=3};Container.AddChild(rail);Container.AddChild(thumb);
  page.selectables.Add(this);nextSelectable[1]=nextSelectable[3]=this;
 }
 internal void SetOffset(int value){value=Mathf.Clamp(value,0,Maximum);if(value==Offset)return;Offset=value;changed(value);}
 internal void Move(int delta){SetOffset(Offset+delta);}
 // Called after the native menu update, outside its subobject traversal.
 internal void Poll(){
  if(menu.manager.menuesMouseMode){
   heldDirection=heldFrames=0;
   if(!menu.mouseDown)Dragging=false;
   else if(!Dragging&&!menu.lastMouseDown&&IsMouseOverMe){
    Dragging=true;float bottom=ThumbBottom;dragOffset=menu.mousePosition.y>=bottom&&menu.mousePosition.y<=bottom+ThumbHeight?menu.mousePosition.y-bottom:ThumbHeight*.5f;
   }
   if(Dragging){menu.selectedObject=this;page.lastSelectedObject=this;float travel=size.y-ThumbHeight;float value=travel<=0?0:1f-(menu.mousePosition.y-dragOffset-pos.y)/travel;SetOffset((int)Math.Round(value*Maximum));}
  }else{
   Dragging=false;int direction=Selected?-menu.input.y:0;
   if(direction==0){heldDirection=heldFrames=0;return;}
   if(direction!=heldDirection){heldDirection=direction;heldFrames=0;Move(direction);}else if(++heldFrames>=12&&(heldFrames-12)%4==0)Move(direction);
  }
 }
 public override void GrafUpdate(float timeStacker){base.GrafUpdate(timeStacker);rail.x=thumb.x=pos.x+size.x*.5f;rail.y=pos.y;rail.scaleY=size.y;rail.alpha=.32f;thumb.y=ThumbBottom;thumb.scaleY=ThumbHeight;thumb.alpha=Selected||Dragging||IsMouseOverMe?1f:.65f;}
 public override void RemoveSprites(){rail.RemoveFromContainer();thumb.RemoveFromContainer();base.RemoveSprites();}
}
}
#endif
