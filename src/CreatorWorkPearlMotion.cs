using System.Collections.Generic;
using UnityEngine;

namespace MoreIterators {
 // Every uncarried work pearl has a destination, even while it is not one of
 // the few currently orbiting the puppet. Targets never change author data.
 public static class CreatorWorkPearlMotion {
  public static int MovingCount(IteratorDesign d,int count){return Mathf.Max(0,count-Mathf.Clamp(d.pearlFixedCount,0,count));}
  public static Vector2 RestPosition(IteratorDesign d,int index,int count,CreatorWorkPearlBounds bounds){
   int moving=MovingCount(d,count);bool fixedPearl=index>=moving;int slot=fixedPearl?index-moving:index;
   float x=slot%2==0?d.pearlClusterX:d.pearlCluster2X,y=slot%2==0?d.pearlClusterY:d.pearlCluster2Y;
   float dx=fixedPearl?slot*31%61-30:slot*73%101-50,dy=fixedPearl?slot*47%73-36:slot*41%61-30;
   return bounds.Position(x,y)+new Vector2(dx*d.pearlScatter,dy*d.pearlScatter);
  }
  public static Vector2 WorkingPosition(IteratorDesign d,int index,int count,int tick,Vector2 puppet,CreatorWorkPearlBounds bounds,out bool look){
   int moving=MovingCount(d,count);look=false;
   if(index<moving){
    int phase=(tick/360)%3,offset=(tick/1080)%moving,order=(index-offset+moving)%moving;
    if(order<(phase==1?5:6)){
     look=phase==2&&order==0;
     if(look)return puppet+new Vector2(-20,-7);
     float angle=tick*.018f+order*Mathf.PI/3;
     return puppet+new Vector2(Mathf.Cos(angle)*(50+order*3),Mathf.Sin(angle)*39-6);
    }
   }
   return RestPosition(d,index,count,bounds);
  }
 }

 // Geometry is scanned once per encounter. Invalid targets are resolved once
 // per tile, so an orbit brushing a wall does not scan the room every frame.
 public sealed class CreatorWorkPearlBounds {
  const float Clearance=8f; // DataPearl radius 5 plus breathing room.
  readonly Room room;
  readonly List<Vector2> clearCenters=new List<Vector2>();
  readonly HashSet<int> chamber=new HashSet<int>();
  readonly Dictionary<int,Vector2> nearest=new Dictionary<int,Vector2>();
  readonly int columns;
  public readonly Vector2 minimum,maximum;
  public CreatorWorkPearlBounds(Room room):this(room,new Vector2(room.PixelWidth*.5f,room.PixelHeight*.5f)){}
  public CreatorWorkPearlBounds(Room room,Vector2 anchor){
   this.room=room;columns=Mathf.Max(1,(int)(room.PixelWidth/20));
   int rows=Mathf.Max(1,(int)(room.PixelHeight/20));var candidates=new HashSet<int>();int start=-1;float closest=float.MaxValue;
   for(int x=0;x<columns;x++)for(int y=0;y<rows;y++){
    var p=new Vector2(x*20+10,y*20+10);
    // The thin mouths of shortcut pipes are not the chamber's usable edges.
    // Remove one-tile-wide necks before flooding so they cannot connect artwork
    // voids to the puppet's interior or stretch its normalized height range.
    if(!TerrainClear(p)||(!Open(p+new Vector2(-20,0))&&!Open(p+new Vector2(20,0)))
      ||(!Open(p+new Vector2(0,-20))&&!Open(p+new Vector2(0,20))))continue;
    int key=y*columns+x;candidates.Add(key);float distance=(p-anchor).sqrMagnitude;
    if(distance<closest){closest=distance;start=key;}
   }
   if(start<0){minimum=maximum=anchor;return;}
   int minX=columns,minY=rows,maxX=0,maxY=0;var queue=new Queue<int>();queue.Enqueue(start);chamber.Add(start);
   while(queue.Count>0){
    int cell=queue.Dequeue(),x=cell%columns,y=cell/columns;
    clearCenters.Add(new Vector2(x*20+10,y*20+10));
    minX=Mathf.Min(minX,x);minY=Mathf.Min(minY,y);maxX=Mathf.Max(maxX,x);maxY=Mathf.Max(maxY,y);
    for(int n=0;n<4;n++){
     int nx=x+(n==0?-1:n==1?1:0),ny=y+(n==2?-1:n==3?1:0),key=ny*columns+nx;
     if(nx<0||ny<0||nx>=columns||ny>=rows||!candidates.Contains(key)||chamber.Contains(key))continue;
     chamber.Add(key);queue.Enqueue(key);
    }
   }
   minimum=new Vector2(minX*20+Clearance,minY*20+Clearance);
   maximum=new Vector2((maxX+1)*20-Clearance,(maxY+1)*20-Clearance);
  }
  public Vector2 Position(float x,float y){return new Vector2(Mathf.Lerp(minimum.x,maximum.x,Mathf.Clamp01(x)),Mathf.Lerp(minimum.y,maximum.y,Mathf.Clamp01(y)));}
  bool Open(Vector2 p){var tile=room.GetTile(p);return !tile.Solid&&tile.Terrain!=Room.Tile.TerrainType.Slope&&tile.Terrain!=Room.Tile.TerrainType.Floor&&tile.Terrain!=Room.Tile.TerrainType.ShortcutEntrance;}
  bool TerrainClear(Vector2 p){
   if(p.x<Clearance||p.y<Clearance||p.x>room.PixelWidth-Clearance||p.y>room.PixelHeight-Clearance)return false;
   return Open(p)&&Open(p+new Vector2(-Clearance,-Clearance))&&Open(p+new Vector2(Clearance,-Clearance))
    &&Open(p+new Vector2(-Clearance,Clearance))&&Open(p+new Vector2(Clearance,Clearance));
  }
  public bool Clear(Vector2 p){return chamber.Contains((int)(p.y/20)*columns+(int)(p.x/20))&&TerrainClear(p);}
  public bool TryResolve(Vector2 requested,out Vector2 target){
   target=new Vector2(Mathf.Clamp(requested.x,minimum.x,maximum.x),Mathf.Clamp(requested.y,minimum.y,maximum.y));
   if(Clear(target))return true;
   int x=Mathf.Clamp((int)(target.x/20),0,columns-1),y=Mathf.Clamp((int)(target.y/20),0,Mathf.Max(0,(int)(room.PixelHeight/20)-1)),key=y*columns+x;
   Vector2 cached;if(nearest.TryGetValue(key,out cached)&&Clear(cached)){target=cached;return true;}
   var center=new Vector2(x*20+10,y*20+10);float best=float.MaxValue;bool found=false;
   foreach(var candidate in clearCenters){
    float distance=(candidate-center).sqrMagnitude;if(distance>=best||!Clear(candidate))continue;
    best=distance;target=candidate;found=true;
   }
   if(found)nearest[key]=target;
   return found;
  }
 }
}
