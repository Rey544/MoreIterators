using System;
using System.Collections.Generic;
namespace UnityEngine
{
    public static class Time { public static float deltaTime=.1f; }
    public static class Mathf { public static float Min(float a,float b){return Math.Min(a,b);}public static float Clamp(float v,float a,float b){return Math.Max(a,Math.Min(b,v));} }
    public enum KeyCode { Space }
    public static class Input { public static bool Space;public static bool GetKey(KeyCode key){return Space;} }
    public struct Vector2 { public float x,y;public Vector2(float a,float b){x=a;y=b;} }
}
public class GameState { public object pauseMenu;public bool pauseUpdate; }
public class Options
{
    public class ControlSetup
    {
        public bool Pressed;
        public int Calls,Action=-1;
        public bool GetButton(int action){Calls++;Action=action;return Pressed;}
    }
    public static ControlSetup Primary=new ControlSetup();
    public static ControlSetup Secondary=new ControlSetup();
    public static ControlSetup[] Current={Primary,Secondary};
    public ControlSetup[] controls=Current;
    public UnityEngine.Vector2 ScreenSize=new UnityEngine.Vector2(1366,768);
}
public class RainWorld { public Options options=new Options(); }
public class FLabel { public string text;public bool isVisible;public void SetPosition(float x,float y){} }
public class FSprite { public bool isVisible;public void SetPosition(float x,float y){} }
namespace HUD { public class HUD { public RainWorld rainWorld=new RainWorld(); }public static class DialogBox {public static int GetDelay(){return 0;}} }
namespace MoreIterators
{
    using UnityEngine;
    public class BroadcastLine {public float speed=1,hold=2.5f;}
    public class DrawBase {public virtual void Draw(float t){} }
    public class CreatorBroadcastDisplay:DrawBase
    {
        class Row {public BroadcastLine style=new BroadcastLine();public string text=new string('x',100);public int[] chars;public float height=30;}
        readonly List<List<Row>> pages=new List<List<Row>>();
        int pageIndex,lineIndex,shown;
        float elapsed,hold;
        bool completed,disposed,slatedForDeletion;
        GameState Game;
        HUD.HUD hud=new HUD.HUD();
        FLabel[] label={new FLabel()};
        FSprite[] sprites={new FSprite()};
        public int Shown {get{return shown;}}
        public CreatorBroadcastDisplay(){var row=new Row{chars=new int[100]};for(int i=0;i<100;i++)row.chars[i]=i;pages.Add(new List<Row>{row});}
        void BuildPage(){}
        __DRAW__
    }
}
public static class MediaDisplayInputCheck
{
    public static int Main()
    {
        try
        {
            var normal=new MoreIterators.CreatorBroadcastDisplay();normal.Draw(0);
            Options.Primary.Pressed=true;var mapped=new MoreIterators.CreatorBroadcastDisplay();mapped.Draw(0);
            if(mapped.Shown<=normal.Shown*3)throw new Exception("mapped gameplay action must accelerate text");
            if(Options.Primary.Action!=0||Options.Primary.Calls!=2||Options.Secondary.Calls!=0)throw new Exception("same mapped player/action as native ChatLogDisplay");
            Options.Primary.Pressed=false;UnityEngine.Input.Space=true;var space=new MoreIterators.CreatorBroadcastDisplay();space.Draw(0);
            if(space.Shown!=normal.Shown)throw new Exception("unmapped Space must not bypass control mapping");
            foreach(var controls in new[]{null,new Options.ControlSetup[0],new Options.ControlSetup[]{null}})
            {
                Options.Current=controls;var absent=new MoreIterators.CreatorBroadcastDisplay();absent.Draw(0);
                if(absent.Shown!=normal.Shown)throw new Exception("missing controls must keep normal text speed");
            }
            Console.WriteLine("media input checks passed: 6");return 0;
        }
        catch(Exception error){Console.Error.WriteLine(error);return 1;}
    }
}
