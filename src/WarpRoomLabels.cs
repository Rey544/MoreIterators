using System;
using System.Collections.Generic;
using System.Reflection;
using UnityEngine;

namespace MoreIterators
{
    // Warp intentionally shortens room names. Preserve IDs only for our registered rooms.
    internal static class WarpRoomLabels
    {
        static readonly Dictionary<Type,FieldInfo> signalFields=new Dictionary<Type,FieldInfo>();

        internal static string RoomId(string typeName,string signal,Func<string,bool> registered)
        {
            if(typeName!="WarpButton"||String.IsNullOrEmpty(signal)||!signal.EndsWith("warp",StringComparison.Ordinal))return null;
            string room=signal.Substring(0,signal.Length-4);
            return room.Length>0&&registered(room)?room:null;
        }

        internal static void Install(List<Action> removeHooks)
        {
            var hook=new On.Menu.MenuLabel.hook_ctor((orig,self,menu,owner,text,pos,size,bigText,parameters)=>
            {
                string fullId=null;
                try
                {
                    if(menu is Menu.PauseMenu&&owner!=null&&owner.GetType().FullName=="WarpButton")
                    {
                        Type type=owner.GetType();FieldInfo signal;
                        if(!signalFields.TryGetValue(type,out signal))
                        {
                            signal=type.GetField("signalText",BindingFlags.Public|BindingFlags.Instance);
                            signalFields[type]=signal;
                        }
                        fullId=RoomId(type.FullName,signal==null?null:signal.GetValue(owner) as string,room=>IteratorCatalog.Find(room)!=null);
                    }
                }
                catch(Exception error){MiDiagnostics.Report("MI-WARP-LABEL","WarpRoomLabels",error,"Original label retained.");}
                orig(self,menu,owner,fullId??text,pos,size,bigText,parameters);
                if(fullId!=null&&self.label!=null&&self.label.textRect.width>size.x-4&&size.x>8)
                    self.label.scaleX=Mathf.Min((size.x-4)/self.label.textRect.width,1f);
            });
            On.Menu.MenuLabel.ctor+=hook;
            removeHooks.Add(delegate{On.Menu.MenuLabel.ctor-=hook;signalFields.Clear();});
            MiDiagnostics.Info("hook.install","On.Menu.MenuLabel.ctor: registered Warp room labels only");
        }
    }
}
