namespace MoreIterators
{
    using System;
    using System.Collections.Generic;
    using UnityEngine;
    // Shared by the creator and playback exports. Persistence belongs to each runtime.
    public static class CreatorControlPanel
    {
        static Overlay overlay;
        static RainWorldGame game;
        static string room;
        static int shortcutFrame=-1;
        static readonly string[] layerIds=
        {
            "head","neck","body","eyes","face","antenna","ears","robe","sleeves","hands","feet","collar","mechanicalArm","cables","halo"
        }
        ;
        static readonly string[] layerNames=
        {
            "game.panel.head","game.panel.neck","game.panel.body","game.panel.eyes","game.panel.face","game.panel.antenna","game.panel.ears","game.panel.robe","game.panel.sleeves","game.panel.hands","game.panel.feet","game.panel.collar","game.panel.arm","game.panel.cables","game.panel.halo"
        }
        ;
        public static void Tick(RainWorldGame current)
        {
            if(!CreatorRuntime.CanControl||current.pauseMenu!=null||current.manager.dialog!=null||current.manager.upcomingProcess!=null)
            {
                Close();
                return;
            }
            if(Input.GetKeyDown(KeyCode.F8)&&shortcutFrame!=Time.frameCount)
            {
                shortcutFrame=Time.frameCount;
                CreatorRuntime.Panel=!CreatorRuntime.Panel;
            }
            if(!CreatorRuntime.Panel)
            {
                Close();
                return;
            }
            if(overlay!=null&&(game!=current||room!=CreatorRuntime.CurrentRoom))
            {
                Close();
                return;
            }
            if(overlay==null)
            {
                game=current;
                room=CreatorRuntime.CurrentRoom;
                overlay=new Overlay(current.manager);
            }
            overlay.Update();
            if(!CreatorRuntime.Panel)Close();
        }
        public static void Draw(RainWorldGame current,float timeStacker)
        {
            if(overlay!=null&&game==current)overlay.GrafUpdate(timeStacker);
        }
        public static void FilterInput(Player player)
        {
            // Menu navigation uses PlayerUIInput; only suppress the character controls.
            if(overlay!=null&&CreatorRuntime.Panel&&player.room!=null&&player.room.game==game)player.input[0]=default(Player.InputPackage);
        }
        public static void Close()
        {
            CreatorRuntime.Panel=false;
            if(overlay!=null)overlay.ShutDownProcess();
            overlay=null;
            game=null;
            room=null;
        }
        static void Apply(string command)
        {
            if(command=="draw-state"){OracleSpriteDiagnostics.OpenReport(CreatorRuntime.Id(CreatorRuntime.CurrentRoom));return;}
            if(command=="affinity-"||command=="affinity+"){CreatorAffinity.Adjust(game,room,command=="affinity-"?-.1f:.1f);return;}
            if(command=="pause")CreatorRuntime.Paused=!CreatorRuntime.Paused;
            else if(command=="work"||command=="reception")
            {
                CreatorRuntime.Behavior=command;
                CreatorRuntime.Mode="silent";
                CreatorRuntime.Paused=false;
            }
            else if(command=="mode")
            {
                CreatorRuntime.Mode=CreatorRuntime.Mode=="silent"?"story":CreatorRuntime.Mode=="story"?"read":"silent";
                CreatorRuntime.Behavior="work";
                CreatorRuntime.Paused=false;
            }
            else if(command=="replay")
            {
                string id=CreatorRuntime.Id(CreatorRuntime.CurrentRoom);
                CreatorRuntime.Visits.Remove(id);
                CreatorDialogue.Reset(id);
                CreatorPearlReader.Reset(id);
                CreatorEncounter.Restart++;
                CreatorRuntime.Mode="story";
                CreatorRuntime.Behavior="work";
                CreatorRuntime.Paused=false;
            }
            else if(command=="glow")CreatorRuntime.RearGlow=!CreatorRuntime.RearGlow;
            else if(command=="lightning")CreatorRuntime.Lightning=!CreatorRuntime.Lightning;
            else if(command=="pearls")CreatorRuntime.Pearls=!CreatorRuntime.Pearls;
            else if(command=="glyphs")CreatorRuntime.Glyphs=!CreatorRuntime.Glyphs;
            else if(command=="close")
            {
                CreatorRuntime.Paused=false;
                CreatorRuntime.Panel=false;
            }
            else if(command.StartsWith("layer:"))
            {
                CreatorRuntime.ToggleLayer(command.Substring(6));
                return;
            }
            CreatorRuntime.SaveControl();
        }
        static string Label(string command)
        {
            switch(command)
            {
                case "draw-state":return UiText.Get("game.panel.draw_state");
                case "affinity-":return UiText.Get("game.panel.affinity_decrease");
                case "affinity+":return UiText.Get("game.panel.affinity_increase");
                case "pause":return CreatorRuntime.Paused?UiText.Get("game.panel.resume"):UiText.Get("game.panel.pause");
                case "work":return UiText.Get("game.panel.work");
                case "reception":return UiText.Get("game.panel.reception_motion");
                case "mode":return UiText.Format("game.menu.mode_label",UiText.Get(CreatorRuntime.Mode=="silent"?"game.menu.silent":CreatorRuntime.Mode=="story"?"game.menu.story":"game.menu.read"));
                case "replay":return UiText.Get("game.panel.replay");
                case "glow":return ToggleLabel(UiText.Get("game.panel.glow"),CreatorRuntime.RearGlow);
                case "lightning":return ToggleLabel(UiText.Get("game.panel.lightning"),CreatorRuntime.Lightning);
                case "pearls":return ToggleLabel(UiText.Get("game.panel.pearls"),CreatorRuntime.Pearls);
                case "glyphs":return ToggleLabel(UiText.Get("game.panel.glyphs"),CreatorRuntime.Glyphs);
                case "close":return UiText.Get("game.panel.close");
            }
            if(command.StartsWith("layer:"))
            {
                string name=command.Substring(6);
                int index=Array.IndexOf(layerIds,name);
                var d=IteratorDesign.ForId(CreatorRuntime.Id(CreatorRuntime.CurrentRoom));
                return ToggleLabel(index<0?name:UiText.Get(layerNames[index]),(bool)typeof(IteratorLayers).GetField(name).GetValue(d.layers));
            }
            return command;
        }
        static string ToggleLabel(string name,bool on)
        {
            return UiText.Format("game.panel.toggle",name,UiText.Get(on?"game.panel.visible":"game.panel.hidden"));
        }
        sealed class Overlay:Menu.Menu
        {
            readonly List<Menu.SimpleButton> controls=new List<Menu.SimpleButton>();
            readonly List<Menu.SimpleButton> tabs=new List<Menu.SimpleButton>();
            readonly Menu.MenuLabel status,affinity;
            readonly float left=24,width=332,top,bottom;
            int tab;
            string pending;
            string error="";
            public Overlay(ProcessManager manager):base(manager,ProcessManager.ProcessID.Game)
            {
                top=manager.rainWorld.options.ScreenSize.y-24;
                bottom=Mathf.Max(24,top-610);
                pages.Add(new Menu.Page(this,null,"Iterator controls",0));
                var page=pages[0];
                var frame=new Menu.RoundedRect(this,page,new Vector2(left,bottom),new Vector2(width,top-bottom),true);
                frame.fillAlpha=.94f;
                for(int i=0;i<frame.sprites.Length;i++)frame.sprites[i].color=Color.black;
                page.subObjects.Add(frame);
                page.subObjects.Add(new Menu.RoundedRect(this,page,new Vector2(left,bottom),new Vector2(width,top-bottom),false));
                AddLabel(UiText.Get("game.panel.title"),top-47,true);
                var d=IteratorDesign.ForId(CreatorRuntime.Id(CreatorRuntime.CurrentRoom));
                AddLabel(d.name,top-78,false);
                string[] names=
                {
                    UiText.Get("game.panel.motion"),UiText.Get("game.panel.display"),UiText.Get("game.panel.layers")
                }
                ;
                for(int i=0;i<names.Length;i++)tabs.Add(AddButton(names[i],"tab:"+i,left+16+i*102,top-128,96));
                status=AddLabel("",top-157,false);
                affinity=AddLabel("",top-182,false);
                BuildControls();
            }
            Menu.MenuLabel AddLabel(string text,float y,bool large)
            {
                var label=new Menu.MenuLabel(this,pages[0],text,new Vector2(left+16,y),new Vector2(width-32,28),large);
                pages[0].subObjects.Add(label);
                return label;
            }
            Menu.SimpleButton AddButton(string text,string signal,float x,float y,float w)
            {
                var b=new Menu.SimpleButton(this,pages[0],text,signal,new Vector2(x,y),new Vector2(w,34));
                pages[0].subObjects.Add(b);
                return b;
            }
            protected override void Init()
            {
                base.Init();
                pages[0].pos.x+=HorizontalMoveToGetCentered(manager);
                pages[0].lastPos=pages[0].pos;
                pages[0].lastSelectedObject=controls[0];
                if(!manager.menuesMouseMode)selectedObject=controls[0];
            }
            void BuildControls()
            {
                selectedObject=null;
                backObject=null;
                foreach(var b in controls)
                {
                    b.RemoveSprites();
                    pages[0].RemoveSubObject(b);
                }
                controls.Clear();
                string[] commands=tab==0?new[]
                {
                    "pause","work","reception","mode","replay","affinity-","affinity+"
                }
                :tab==1?new[]
                {
                    "glow","lightning","pearls","glyphs","draw-state"
                }
                :Array.ConvertAll(layerIds,x=>"layer:"+x);
                for(int i=0;i<commands.Length;i++)
                {
                    int column=tab==2?i%2:0,row=tab==2?i/2:i;
                    controls.Add(AddButton(Label(commands[i]),commands[i],left+16+column*154,top-215-row*46,tab==2?146:width-32));
                }
                var close=AddButton(Label("close"),"close",left+16,bottom+20,width-32);
                controls.Add(close);
                backObject=close;
                for(int i=0;i<tabs.Count;i++)tabs[i].buttonBehav.greyedOut=i==tab;
                pages[0].lastSelectedObject=controls[0];
                if(!manager.menuesMouseMode)selectedObject=controls[0];
            }
            public override void Singal(Menu.MenuObject sender,string message)
            {
                pending=message;
            }
            public override void Update()
            {
                base.Update();
                if(pending!=null)
                {
                    string command=pending;
                    pending=null;
                    if(command.StartsWith("tab:"))
                    {
                        tab=Int32.Parse(command.Substring(4));
                        BuildControls();
                    }
                    else try
                    {
                        Apply(command);
                        error="";
                    }
                    catch(Exception e)
                    {
                        error=UiText.Get("game.panel.failed");
                        MiDiagnostics.Report("MI-F8-001","F8.Command",e,command);
                    }
                    PlaySound(SoundID.MENU_Button_Standard_Button_Pressed);
                }
                foreach(var b in controls){b.menuLabel.text=Label(b.signalText);if(b.signalText.StartsWith("affinity"))b.buttonBehav.greyedOut=!CreatorAffinity.CanAdjust(game,room);}
                affinity.text=CreatorAffinity.Label(game,room);
                status.text=error.Length>0?error:CreatorRuntime.Paused?UiText.Get("game.panel.paused"):CreatorRuntime.Behavior=="reception"?UiText.Get("game.panel.reception"):UiText.Get("game.panel.active");
            }
            public override string UpdateInfoText()
            {
                return "";
            }
        }
    }
}
