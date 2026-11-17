using System;

public struct Color
{
    public float r,g,b,a;
    public Color(float red,float green,float blue,float alpha){r=red;g=green;b=blue;a=alpha;}
    public float grayscale{get{return r*.299f+g*.587f+b*.114f;}}
    public static Color operator *(Color c,float factor){return new Color(c.r*factor,c.g*factor,c.b*factor,c.a*factor);}
    public static Color Lerp(Color left,Color right,float amount)
    {
        amount=Math.Max(0,Math.Min(1,amount));
        return new Color(left.r+(right.r-left.r)*amount,left.g+(right.g-left.g)*amount,
            left.b+(right.b-left.b)*amount,left.a+(right.a-left.a)*amount);
    }
}
public sealed class Texture2D
{
    public readonly int width,height;
    public int applyCalls;
    readonly Color[] values;
    public Texture2D(int w,int h){width=w;height=h;values=new Color[w*h];}
    public Color GetPixel(int x,int y){return values[y*width+x];}
    public void SetPixel(int x,int y,Color color){values[y*width+x]=color;}
    public void Apply(bool mipmaps){applyCalls++;}
}
public static class Mathf{public static int Min(int left,int right){return Math.Min(left,right);}}
public sealed class AbstractRoom{public string name="AI";}
public sealed class Room{public readonly AbstractRoom abstractRoom=new AbstractRoom();}
public sealed class RoomCamera{public Room room=new Room();}
public static class MoreIteratorsPlugin{public static Room PaletteRoom(RoomCamera camera){return camera.room;}}
public sealed class IteratorDesign
{
    public string roomReceptionColor="reception",roomWorkColor="work";
    public static IteratorDesign ForRoom(Room room){return new IteratorDesign();}
    public static Color C(string value)
    {
        return value=="reception"?new Color(92/255f,176/255f,1,1):new Color(168/255f,1,254/255f,1);
    }
}
public static class CreatorRoomSettings
{
    public static bool useRoom;
    public static bool RoomPalette(IteratorDesign design){return useRoom;}
}
public static class PaletteCheck
{
    sealed class Sprite{public Color color;public float alpha;}
    static bool IsAI(string name){return name=="AI";}
    __PALETTE_METHOD__

    static void Require(bool condition,string message){if(!condition)throw new Exception(message);}
    static bool Same(Color left,Color right)
    {
        return left.r==right.r&&left.g==right.g&&left.b==right.b&&left.a==right.a;
    }
    static Texture2D Fixture(int width,int height)
    {
        var result=new Texture2D(width,height);
        float[] alphas={0,.3f,1};
        for(int y=0;y<height;y++)for(int x=0;x<width;x++)
            result.SetPixel(x,y,new Color((x%7)/6f,(y%5)/4f,((x+y)%11)/10f,alphas[(x+y)%3]));
        return result;
    }
    static void AlphaOrRgb(bool alpha)
    {
        foreach(int palette in new[]{25,26})foreach(int width in new[]{12,32,37})
        {
            var original=Fixture(width,16);
            var changed=Fixture(width,16);
            Palette(changed,new RoomCamera(),palette);
            Require(changed.applyCalls==1,"Palette was not applied exactly once");
            Color theme=IteratorDesign.C(palette==25?"reception":"work");
            for(int y=0;y<changed.height;y++)for(int x=0;x<Math.Min(30,width);x++)
            {
                if(y%8>5)continue;
                Color before=original.GetPixel(x,y),after=changed.GetPixel(x,y);
                if(alpha)Require(before.a==after.a,"Palette alpha changed at "+x+","+y+" in "+palette);
                else
                {
                    float gray=before.grayscale;
                    Color expected=Color.Lerp(new Color(gray,gray,gray,before.a),theme*gray*1.6f,.55f);
                    Require(after.r==expected.r&&after.g==expected.g&&after.b==expected.b,"RGB changed");
                }
            }
        }
    }
    static void Scope()
    {
        var original=Fixture(37,16);
        var changed=Fixture(37,16);
        Palette(changed,new RoomCamera(),26);
        for(int y=0;y<16;y++)for(int x=0;x<37;x++)
            if(x>=30||y%8>5)Require(Same(original.GetPixel(x,y),changed.GetPixel(x,y)),"Control pixel changed");
        for(int bypass=0;bypass<3;bypass++)
        {
            var camera=new RoomCamera();
            CreatorRoomSettings.useRoom=bypass==0;
            if(bypass==1)camera.room.abstractRoom.name="SU_A01";
            if(bypass==2)camera.room=null;
            changed=Fixture(37,16);
            Palette(changed,camera,26);
            Require(changed.applyCalls==0,"Bypassed room applied a palette");
            for(int y=0;y<16;y++)for(int x=0;x<37;x++)
                Require(Same(original.GetPixel(x,y),changed.GetPixel(x,y)),"Bypassed room pixel changed");
        }
        CreatorRoomSettings.useRoom=false;
    }
    static void ShaderSample()
    {
        var texture=new Texture2D(32,16);
        for(int y=0;y<16;y++)for(int x=0;x<32;x++)texture.SetPixel(x,y,new Color(0,0,0,1));
        Palette(texture,new RoomCamera(),26);
        foreach(float shadow in new[]{0,.5f,1})
        {
            Color setColor=Color.Lerp(texture.GetPixel(5,3),texture.GetPixel(5,0),shadow);
            Require(setColor.a==1,"LevelColor sample became translucent: "+setColor.a);
        }
    }
    static void Neck()
    {
        foreach(float alpha in new[]{0,.3f,1})
        {
            var head=new Sprite{color=new Color(.2f,.7f,.9f,alpha),alpha=1};
            var neck=new Sprite();
            __NECK_COLOR__
            Require(neck.color.a*neck.alpha==head.color.a,"Neck alpha changed");
            Require(neck.color.r==head.color.r*.88f&&neck.color.g==head.color.g*.88f&&neck.color.b==head.color.b*.88f,"Neck RGB changed");
        }
    }
    public static int Main(string[] args)
    {
        try
        {
            if(args[0]=="alpha")AlphaOrRgb(true);
            else if(args[0]=="rgb")AlphaOrRgb(false);
            else if(args[0]=="scope")Scope();
            else if(args[0]=="shader")ShaderSample();
            else if(args[0]=="neck")Neck();
            else throw new Exception("Unknown check");
            Console.WriteLine("PASS: "+args[0]);
            return 0;
        }
        catch(Exception error){Console.Error.WriteLine(error.Message);return 1;}
    }
}
