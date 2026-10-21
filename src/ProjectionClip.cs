using System;
using System.Collections.Generic;
using UnityEngine;

namespace MoreIterators {
 internal static class ProjectionClip {
  internal struct Point {public Vector2 pos,uv;public Point(Vector2 p,Vector2 u){pos=p;uv=u;}}
  // Merge the largest open connected chamber into disjoint horizontal strips.
  // Smaller disconnected voids behind the level artwork are not projection areas.
  internal static Rect[] Areas(Room room){
   int width=room.TileWidth,height=room.TileHeight;var visited=new bool[width,height];var largest=new List<IntVector>();
   // Match the editor's top-origin tie break for equally sized components.
   for(int x=0;x<width;x++)for(int y=height-1;y>=0;y--){
    if(visited[x,y]||!Open(room,x,y))continue;
    var component=new List<IntVector>();var queue=new Queue<IntVector>();queue.Enqueue(new IntVector(x,y));visited[x,y]=true;
    while(queue.Count>0){var p=queue.Dequeue();component.Add(p);for(int n=0;n<4;n++){int nx=p.x+(n==0?-1:n==1?1:0),ny=p.y+(n==2?-1:n==3?1:0);if(nx<0||ny<0||nx>=width||ny>=height||visited[nx,ny]||!Open(room,nx,ny))continue;visited[nx,ny]=true;queue.Enqueue(new IntVector(nx,ny));}}
    if(component.Count>largest.Count)largest=component;
   }
   var cells=new bool[width,height];foreach(var p in largest)cells[p.x,p.y]=true;
   var rectangles=new List<Rect>();var previous=new Dictionary<string,int>();
   for(int y=0;y<height;y++){
    var current=new Dictionary<string,int>();
    for(int x=0;x<width;x++){
     if(!cells[x,y])continue;int start=x;while(x+1<width&&cells[x+1,y])x++;
     string key=start+":"+x;int index;
     if(previous.TryGetValue(key,out index)){Rect r=rectangles[index];r.height+=20;rectangles[index]=r;}
     else{index=rectangles.Count;rectangles.Add(new Rect(start*20,y*20,(x-start+1)*20,20));}
     current[key]=index;
    }
    previous=current;
   }
   if(rectangles.Count>512)throw new InvalidOperationException("Projection chamber mask exceeds 512 strips.");
   return rectangles.ToArray();
  }
  struct IntVector {public int x,y;public IntVector(int x,int y){this.x=x;this.y=y;}}
  static bool Open(Room room,int x,int y){var tile=room.GetTile(x,y);return !tile.Solid&&tile.Terrain!=Room.Tile.TerrainType.Slope;}
  internal static Rect[] Resolve(Room room,ProjectionGroup group,ProjectionTrack track){
   Rect[] areas=group.confineToRoom?Areas(room):null;
   ProjectionMask mask=track.maskMode=="custom"?track.mask:track.maskMode=="none"?null:group.projectMask;
   if(mask==null||!mask.enabled)return areas;
   Rect custom=new Rect(mask.x*room.PixelWidth,(1-mask.y-mask.height)*room.PixelHeight,mask.width*room.PixelWidth,mask.height*room.PixelHeight);
   if(areas==null)return new[]{custom};
   var result=new List<Rect>();
   foreach(var area in areas){float x=Math.Max(area.xMin,custom.xMin),y=Math.Max(area.yMin,custom.yMin),right=Math.Min(area.xMax,custom.xMax),top=Math.Min(area.yMax,custom.yMax);if(right>x&&top>y)result.Add(new Rect(x,y,right-x,top-y));}
   return result.ToArray();
  }
  internal static TriangleMesh Create(string element,int count){
   var triangles=new TriangleMesh.Triangle[Math.Max(1,count)*6];
   for(int r=0;r<Math.Max(1,count);r++)for(int n=0;n<6;n++)triangles[r*6+n]=new TriangleMesh.Triangle(r*8,r*8+n+1,r*8+n+2);
   return new TriangleMesh(element,triangles,false);
  }
  internal static List<Point> Polygon(IList<Point> source,Rect area){
   var points=new List<Point>(source);
   for(int edge=0;edge<4&&points.Count>0;edge++){
    var next=new List<Point>();Point a=points[points.Count-1];bool insideA=Inside(a.pos,area,edge);
    foreach(Point b in points){bool insideB=Inside(b.pos,area,edge);if(insideA!=insideB){float av=edge<2?a.pos.x:a.pos.y,bv=edge<2?b.pos.x:b.pos.y,bound=edge==0?area.xMin:edge==1?area.xMax:edge==2?area.yMin:area.yMax;float t=(bound-av)/(bv-av);AddDistinct(next,new Point(Vector2.Lerp(a.pos,b.pos,t),Vector2.Lerp(a.uv,b.uv,t)));}if(insideB)AddDistinct(next,b);a=b;insideA=insideB;}
    if(next.Count>1&&Same(next[0].pos,next[next.Count-1].pos))next.RemoveAt(next.Count-1);
    points=next;
   }
   return points;
  }
  static bool Same(Vector2 a,Vector2 b){return Math.Abs(a.x-b.x)<.00001f&&Math.Abs(a.y-b.y)<.00001f;}
  static void AddDistinct(List<Point> points,Point point){if(points.Count==0||!Same(points[points.Count-1].pos,point.pos))points.Add(point);}
  static bool Inside(Vector2 p,Rect r,int edge){return edge==0?p.x>=r.xMin:edge==1?p.x<=r.xMax:edge==2?p.y>=r.yMin:p.y<=r.yMax;}
  internal static void Apply(TriangleMesh mesh,Rect[] areas,Vector2 camera){
   var element=mesh.element;Rect source=element.sourceRect;
   float left=-mesh.anchorX*element.sourceSize.x+source.x,bottom=-mesh.anchorY*element.sourceSize.y+element.sourceSize.y-source.y-source.height;
   Vector2 origin=new Vector2(mesh.x,mesh.y);float angle=-mesh.rotation*Mathf.Deg2Rad,c=Mathf.Cos(angle),s=Mathf.Sin(angle);
   var points=new List<Point>();
   for(int n=0;n<4;n++){float u=n==0||n==3?0:1,v=n<2?0:1;Vector2 p=new Vector2((left+u*source.width)*mesh.scaleX,(bottom+v*source.height)*mesh.scaleY);Vector2 uv=Vector2.Lerp(Vector2.Lerp(element.uvBottomLeft,element.uvBottomRight,u),Vector2.Lerp(element.uvTopLeft,element.uvTopRight,u),v);points.Add(new Point(origin+new Vector2(p.x*c-p.y*s,p.x*s+p.y*c),uv));}
   mesh.SetPosition(Vector2.zero);mesh.scaleX=mesh.scaleY=1;mesh.rotation=0;
   for(int r=0;r<Math.Max(1,areas.Length);r++){
    var clipped=areas.Length==0?new List<Point>():Polygon(points,new Rect(areas[r].x-camera.x,areas[r].y-camera.y,areas[r].width,areas[r].height));
    for(int n=0;n<8;n++){Point p=clipped.Count==0?new Point(Vector2.zero,element.uvBottomLeft):clipped[Math.Min(n,clipped.Count-1)];mesh.MoveVertice(r*8+n,p.pos);mesh.UVvertices[r*8+n]=p.uv;}
   }
  }
 }
}
