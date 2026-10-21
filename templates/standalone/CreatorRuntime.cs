namespace MoreIterators
{
    using System;
    using System.IO;
    using System.Collections.Generic;
    using UnityEngine;
    public static class CreatorRuntime
    {
        public static bool IsRoom(string room)
        {
            return IteratorCatalog.OwnsRoom(room);
        }
        public static bool IsAI(string room)
        {
            return IteratorCatalog.IsAI(room)&&!IteratorIntegrations.Native(Id(room));
        }
        public static bool UsesDialogue(string room)
        {
            return IteratorCatalog.IsAI(room);
        }
        public static string Id(string room)
        {
            return IteratorCatalog.Id(room);
        }
        public static string Root
        {
            get
            {
                return RuntimePaths.DataDirectory;
            }
        }
        public static string Selected="",Mode="story",Behavior="work",CurrentRoom="";
        public static bool Paused,Panel,Mark=true,Reset=true,RearGlow=true,Lightning=true,Pearls=true,Glyphs=true;
        public static void GrantMark(){Mark=true;StudioRuntime.Pose.hasMark=true;}
        public static bool CanControl
        {
            get
            {
                return IteratorCatalog.IsAI(CurrentRoom);
            }
        }
        public static float PalettePreview=-1;
        public static readonly Dictionary<string,int> Visits=new Dictionary<string,int>();
        static bool open,firstStory=true;
        static int selection;
        static readonly List<Menu.SimpleButton> buttons=new List<Menu.SimpleButton>();
        public static List<Dictionary<string,object>> Projects()
        {
            return IteratorCatalog.Projects();
        }
        public static void Menu(Menu.MainMenu m)
        {
            buttons.Clear();
            open=false;
            m.pages[0].subObjects.Add(new CreatorMenuButton(m,m.pages[0],UiText.Get("game.menu.chamber"),"PLAY_MENU",new Vector2(m.manager.rainWorld.options.ScreenSize.x-230,30),new Vector2(200,40)));
        }
        public static void MenuUpdate(Menu.MainMenu m)
        {
        }
        static void Add(Menu.MainMenu m,string text,string signal,int row)
        {
            var b=new CreatorMenuButton(m,m.pages[0],text,signal,new Vector2(m.manager.rainWorld.options.ScreenSize.x-380,480-row*46),new Vector2(350,38));
            buttons.Add(b);
            m.pages[0].subObjects.Add(b);
        }
        static void Refresh(Menu.MainMenu m)
        {
            foreach(var b in buttons)
            {
                b.RemoveSprites();
                m.pages[0].RemoveSubObject(b);
            }
            buttons.Clear();
            if(!open)return;
            var ps=Projects();
            int row=0;
            if(ps.Count>0)
            {
                selection%=ps.Count;
                Add(m,IteratorCatalog.Text(ps[selection],"name"),"PLAY_PROJECT",row++);
            }
            Add(m,CreatorSlugcatSelection.Label(m,ps.Count>0?IteratorCatalog.Text(ps[selection],"ai"):""),"PLAY_SLUGCAT",row++);
            Add(m,firstStory?UiText.Get("game.menu.first"):UiText.Get("game.menu.skip"),"PLAY_FIRST",row++);
            Add(m,Mark?UiText.Get("game.menu.mark_yes"):UiText.Get("game.menu.mark_no"),"PLAY_MARK",row++);
            if(ps.Count>0)
            {
                Add(m,UiText.Get("game.menu.enter"),"PLAY_ENTER",row++);
                Add(m,UiText.Get("game.menu.waiting"),"PLAY_ENTRY",row++);
            }
            Add(m,UiText.Get("game.menu.collapse"),"PLAY_MENU",row);
        }
        public static bool Signal(Menu.MainMenu m,string s)
        {
            if(!s.StartsWith("PLAY_"))return false;
            if(s=="PLAY_MENU")open=!open;
            if(s=="PLAY_PROJECT")selection++;
            if(s=="PLAY_SLUGCAT")CreatorSlugcatSelection.Next(m.manager.rainWorld);
            if(s=="PLAY_FIRST")firstStory=!firstStory;
            if(s=="PLAY_MARK")Mark=!Mark;
            if(s=="PLAY_ENTER"||s=="PLAY_ENTRY")
            {
                var ps=Projects();
                if(ps.Count>0)
                {
                    var p=ps[selection%ps.Count];
                    string room=s=="PLAY_ENTRY"?(string)p["entry"]:(string)p["ai"];
                    Prepare(room,firstStory?"story":"read",Mark,true);
                    MoreIteratorsPlugin.Instance.LaunchPreview(m,Selected);
                }
                return true;
            }
            Refresh(m);
            return true;
        }
        public static void Prepare(string entry,string mode,bool mark,bool reset)
        {
            Selected=entry;
            Mode=mode;
            Mark=mark;
            Reset=reset;
            Behavior="work";
            Paused=Panel=false;
            Visits.Remove(Id(entry));
            CreatorDialogue.Reset(Id(entry));
            CreatorPearlReader.Reset(Id(entry));
            StudioRuntime.Pose=new StudioPose
            {
                hasMark=mark
            }
            ;
        }
        public static void Tick(RainWorldGame g)
        {
            CurrentRoom=g.cameras.Length>0&&g.cameras[0].room!=null?g.cameras[0].room.abstractRoom.name:"";
            if(CanControl)
            {
            }
            else Panel=false;
        }
        public static void SaveControl()
        {
        }
        public static void SyncPose()
        {
        }
        public static void ToggleLayer(string name)
        {
            var design=IteratorDesign.ForId(Id(CurrentRoom));
            var field=typeof(IteratorLayers).GetField(name);
            if(field==null||field.FieldType!=typeof(bool))return;
            field.SetValue(design.layers,!(bool)field.GetValue(design.layers));
        }
        public static void Palette(Texture2D t,RoomCamera cam,int palette)
        {
            var room=MoreIteratorsPlugin.PaletteRoom(cam);
            if(room==null||!IsAI(room.abstractRoom.name))return;
            var d=IteratorDesign.ForRoom(room);
            Color theme=IteratorDesign.C(palette==25?d.roomReceptionColor:d.roomWorkColor);
            for(int y=0;y<t.height;y++)for(int x=0;x<Mathf.Min(30,t.width);x++)
            {
                if(y%8>5)continue;
                Color c=t.GetPixel(x,y);
                float v=c.grayscale;
                t.SetPixel(x,y,Color.Lerp(new Color(v,v,v,c.a),theme*v*1.6f,.55f));
            }
            t.Apply(false);
        }
    }
    __ENCOUNTER__
}
