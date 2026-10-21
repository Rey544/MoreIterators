namespace MoreIterators
{
    using System;
    using System.Collections.Generic;
    using System.Runtime.CompilerServices;
    using UnityEngine;
    // A read needs an actual Player.ThrowObject occurrence, never proximity or a drop.
    public static class CreatorPearlOffers
    {
        sealed class Offer
        {
            public DataPearl pearl;
            public Player giver;
            public Oracle oracle;
            public int restart;
            public string mode,identity;
            public bool revoked;
        }
        sealed class Inbox
        {
            public readonly List<Offer> items=new List<Offer>();
        }
        static ConditionalWeakTable<Oracle,Inbox> inboxes=new ConditionalWeakTable<Oracle,Inbox>();
        static ConditionalWeakTable<DataPearl,Offer> latest=new ConditionalWeakTable<DataPearl,Offer>();
        public const float MaximumDistance=1200f;
        public static void Install(List<Action> removals)
        {
            var throwHook=new On.Player.hook_ThrowObject((orig,player,grasp,eu)=>
            {
                DataPearl pearl=null;
                Room room=null;
                Vector2 origin=default(Vector2);
                try
                {
                    if(player!=null)
                    {
                        room=player.room;
                        origin=player.mainBodyChunk.pos;
                        if(player.grasps!=null&&grasp>=0&&grasp<player.grasps.Length&&player.grasps[grasp]!=null)
                            pearl=player.grasps[grasp].grabbed as DataPearl;
                        if(pearl!=null)
                            Revoke(pearl,"new throw");
                    }
                }
                catch(Exception error)
                {
                    pearl=null;
                    MiDiagnostics.Report("MI-PEARL-OFFER-CAPTURE","CreatorPearlOffers.ThrowObject",error,"grasp="+grasp);
                }
                // Native code is outside our capture guards and always runs exactly once.
                orig(player,grasp,eu);
                if(pearl==null)
                    return;
                try
                {
                    Released(player,pearl,room,origin);
                }
                catch(Exception error)
                {
                    MiDiagnostics.Report("MI-PEARL-OFFER","CreatorPearlOffers.ThrowObject",error,MiDiagnostics.Context(room));
                }
            });
            On.Player.ThrowObject+=throwHook;
            removals.Add(delegate
            {
                On.Player.ThrowObject-=throwHook;
                Reset();
                MiDiagnostics.Info("hook.remove","CreatorPearlOffers ThrowObject");
            });
            var grabHook=new On.Player.hook_SlugcatGrab((orig,player,item,grasp)=>
            {
                orig(player,item,grasp);
                try
                {
                    var pearl=item as DataPearl;
                    if(pearl!=null&&pearl.grabbedBy.Count>0)
                        Revoke(pearl,"grabbed again");
                }
                catch(Exception error)
                {
                    MiDiagnostics.Report("MI-PEARL-OFFER-GRAB","CreatorPearlOffers.SlugcatGrab",error,"grasp="+grasp);
                }
            });
            On.Player.SlugcatGrab+=grabHook;
            removals.Add(delegate
            {
                On.Player.SlugcatGrab-=grabHook;
                MiDiagnostics.Info("hook.remove","CreatorPearlOffers SlugcatGrab");
            });
            MiDiagnostics.Info("hook.install","CreatorPearlOffers: native ThrowObject offers; SlugcatGrab invalidation");
        }
        static bool Supports(DataPearl pearl,Oracle oracle)
        {
            var custom=pearl as CreatorDataPearl;
            return custom!=null?custom.Project!=null&&custom.Project.Reader(IteratorDesign.ForRoom(oracle.room).projectId)!=null:CreatorMiscPearls.IsOrdinary(pearl);
        }
        static void Released(Player player,DataPearl pearl,Room before,Vector2 origin)
        {
            if(before==null||player.dead||player.room!=before||pearl.room!=before||pearl.slatedForDeletetion||pearl.grabbedBy.Count>0||(CreatorRuntime.Mode!="story"&&CreatorRuntime.Mode!="read")||StudioRuntime.Recording||CreatorRuntime.Paused||!IteratorCatalog.IsAI(before.abstractRoom.name)||!CreatorRuntime.UsesDialogue(before.abstractRoom.name))
                return;
            if(player.grasps!=null)
                foreach(var grasp in player.grasps)if(grasp!=null&&grasp.grabbed==pearl)return;
            Vector2 velocity=pearl.firstChunk.vel;
            if(velocity.sqrMagnitude<1f)
                return;
            Oracle selected=null;
            float best=MaximumDistance;
            foreach(var item in before.updateList)
            {
                var oracle=item as Oracle;
                if(oracle==null||oracle.room!=before||oracle.slatedForDeletetion||!(oracle.oracleBehavior is IteratorBehavior)||!Supports(pearl,oracle))
                    continue;
                Vector2 toward=oracle.firstChunk.pos-origin;
                float distance=toward.magnitude;
                // Actual released velocity includes native horizontal/upward/flip tossing rules.
                if(distance>best||distance>16&&Vector2.Dot(velocity.normalized,toward.normalized)<.25f||!before.VisualContact(origin,oracle.firstChunk.pos))
                    continue;
                selected=oracle;
                best=distance;
            }
            if(selected==null)
                return;
            var inbox=inboxes.GetOrCreateValue(selected);
            Prune(inbox);
            if(inbox.items.Count>=16)
            {
                MiDiagnostics.Warn("MI-PEARL-OFFER-LIMIT","CreatorPearlOffers.ThrowObject","Too many pending pearl offers; throw this pearl again after a read completes.",MiDiagnostics.Context(before));
                return;
            }
            var offer=new Offer
            {
                pearl=pearl,giver=player,oracle=selected,restart=CreatorEncounter.Restart,mode=CreatorRuntime.Mode,identity="oracle="+IteratorDesign.ForRoom(before).oracleId+" pearl="+pearl.abstractPhysicalObject.ID
            };
            latest.Add(pearl,offer);
            inbox.items.Add(offer);
            MiDiagnostics.Info("pearl.offer","oracle="+IteratorDesign.ForRoom(before).oracleId+" pearl="+pearl.abstractPhysicalObject.ID+" queued="+inbox.items.Count);
        }
        static string InvalidReason(Offer offer)
        {
            if(offer==null||offer.pearl==null||offer.oracle==null||offer.oracle.room==null||offer.oracle.room.abstractRoom==null)
                return "room detached";
            Offer current;
            if(!latest.TryGetValue(offer.pearl,out current)||!System.Object.ReferenceEquals(current,offer))
                return "replaced or recaught";
            if(offer.pearl.slatedForDeletetion||offer.oracle.slatedForDeletetion)
                return "object removed";
            if(offer.pearl.grabbedBy.Count>0)
                return "pearl grabbed";
            if(offer.pearl.room!=offer.oracle.room)
                return "pearl left room";
            if(!(offer.oracle.oracleBehavior is IteratorBehavior)||!IteratorCatalog.IsAI(offer.oracle.room.abstractRoom.name)||!CreatorRuntime.UsesDialogue(offer.oracle.room.abstractRoom.name)||!Supports(offer.pearl,offer.oracle))
                return "reader no longer available";
            if(offer.giver==null||offer.giver.dead||offer.giver.room!=offer.oracle.room||offer.giver.inShortcut||offer.giver.enteringShortCut.HasValue)
                return "player left or unavailable";
            if(CreatorRuntime.Paused)
                return "paused";
            if(StudioRuntime.Recording)
                return "recording";
            if(offer.restart!=CreatorEncounter.Restart||offer.mode!=CreatorRuntime.Mode)
                return "playback changed";
            return null;
        }
        static void Cancelled(Offer offer,string reason)
        {
            if(offer.revoked)
                return;
            offer.revoked=true;
            MiDiagnostics.Info("pearl.offer.cancel",offer.identity+" reason="+reason);
        }
        static void Revoke(DataPearl pearl,string reason)
        {
            Offer offer;
            if(latest.TryGetValue(pearl,out offer))
            {
                latest.Remove(pearl);
                Cancelled(offer,reason);
            }
        }
        static void Prune(Inbox inbox)
        {
            for(int i=inbox.items.Count-1;i>=0;i--)
            {
                var offer=inbox.items[i];
                string reason=InvalidReason(offer);
                if(reason==null)
                    continue;
                Offer current;
                if(offer.pearl!=null&&latest.TryGetValue(offer.pearl,out current)&&System.Object.ReferenceEquals(current,offer))
                    latest.Remove(offer.pearl);
                Cancelled(offer,reason);
                inbox.items.RemoveAt(i);
            }
        }
        public static bool Pending(Oracle oracle)
        {
            if(oracle==null)
                return false;
            var inbox=inboxes.GetOrCreateValue(oracle);
            Prune(inbox);
            return inbox.items.Count>0;
        }
        public static bool Take(Oracle oracle,out DataPearl pearl,out Player giver)
        {
            pearl=null;
            giver=null;
            if(oracle==null)
                return false;
            var inbox=inboxes.GetOrCreateValue(oracle);
            Prune(inbox);
            if(inbox.items.Count==0)
                return false;
            var offer=inbox.items[0];
            inbox.items.RemoveAt(0);
            latest.Remove(offer.pearl);
            pearl=offer.pearl;
            giver=offer.giver;
            MiDiagnostics.Info("pearl.offer.consume",offer.identity);
            return true;
        }
        public static void Clear(Oracle oracle,string reason="reset")
        {
            if(oracle==null)
                return;
            Inbox inbox;
            if(!inboxes.TryGetValue(oracle,out inbox))
                return;
            foreach(var offer in inbox.items)
            {
                Offer current;
                if(latest.TryGetValue(offer.pearl,out current)&&System.Object.ReferenceEquals(current,offer))
                {
                    latest.Remove(offer.pearl);
                    Cancelled(offer,reason);
                }
            }
            inbox.items.Clear();
        }
        public static void Reset()
        {
            inboxes=new ConditionalWeakTable<Oracle,Inbox>();
            latest=new ConditionalWeakTable<DataPearl,Offer>();
        }
    }
}
