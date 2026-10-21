using System;
using System.Globalization;
using System.Runtime.CompilerServices;
using System.Text;
using UnityEngine;

namespace MoreIterators
{
    // Read-only snapshots. Coordinates never form the change key: ordinary motion
    // must not produce per-frame logs or recurring diagnostic dialogs.
    public static class OracleSpriteDiagnostics
    {
        public static void OpenReport(string oracleId) { OracleRenderReport.Open(oracleId); }
        [Flags]
        enum Problem { None=0, MissingSprite=1, NonFinite=2, MissingContainer=4, Hidden=8, Transparent=16, ZeroScale=32 }
        sealed class State
        {
            public State() { }
            public string projectId,oracleId;
            public Problem body0, body1;
            public bool sampled,reportedFailure;
            public DateTime nextWrite;
            public FSprite[] sprites;
        }
        static readonly ConditionalWeakTable<OracleGraphics,State> states=new ConditionalWeakTable<OracleGraphics,State>();

        public static void Observe(OracleGraphics graphics, RoomCamera.SpriteLeaser leaser, int extraStart, IteratorDesign design)
        {
            try { ObserveAt(graphics,leaser,extraStart,design,DateTime.UtcNow); }
            catch(Exception error) {
                // Diagnostic observation cannot interrupt the character renderer.
                if(graphics==null)return;
                State state=states.GetOrCreateValue(graphics);
                if(state.reportedFailure)return;state.reportedFailure=true;
                MiDiagnostics.Info("OracleSpriteDiagnostics","observation-failed project="+Clean(design==null?null:design.projectId)+
                    " oracle="+Clean(design==null?null:design.oracleId)+" error="+error);
            }
        }

        internal static void ObserveAt(OracleGraphics graphics, RoomCamera.SpriteLeaser leaser, int extraStart, IteratorDesign design, DateTime now)
        {
            if(graphics==null||leaser==null||design==null)return;
            FSprite a=At(leaser,graphics.firstBodyChunkSprite),b=At(leaser,graphics.firstBodyChunkSprite+1);
            Problem first=Classify(a),second=Classify(b);
            State state=states.GetOrCreateValue(graphics);
            bool changedProject=state.projectId!=design.projectId||state.oracleId!=design.oracleId;
            bool fresh=!state.sampled||changedProject||state.sprites!=leaser.sprites;
            if(!fresh&&(first==state.body0&&second==state.body1||now<state.nextWrite))return;
            state.nextWrite=now.AddSeconds(2);
            state.projectId=design.projectId;state.oracleId=design.oracleId;state.sprites=leaser.sprites;state.body0=first;state.body1=second;state.sampled=true;
            string identity="project="+Clean(design.projectId)+" oracle="+Clean(design.oracleId);
            string room=MiDiagnostics.Context(graphics.oracle==null?null:graphics.oracle.room);
            string status="body0="+first+" body1="+second+" culled="+graphics.culled;
            var sample=new StringBuilder(identity+" "+room+" "+status+" robeEnabled="+(design.layers==null?"<missing>":design.layers.robe.ToString()));
            Describe(sample,"body0",a);Describe(sample,"body1",b);
            int front=CreatorWardrobe.Start(extraStart);
            Bounds(sample,"frontL",leaser,front,1);Bounds(sample,"frontR",leaser,front+6,1);
            Bounds(sample,"back",leaser,extraStart+40,26);
            MiDiagnostics.Info("OracleSpriteDiagnostics",sample.ToString());
        }

        static FSprite At(RoomCamera.SpriteLeaser leaser,int index)
        { return leaser.sprites!=null&&index>=0&&index<leaser.sprites.Length?leaser.sprites[index]:null; }
        static bool Finite(float value) { return !Single.IsNaN(value)&&!Single.IsInfinity(value); }
        static Problem Classify(FSprite sprite)
        {
            if(sprite==null)return Problem.MissingSprite;
            Problem result=Problem.None;
            if(!Finite(sprite.x)||!Finite(sprite.y)||!Finite(sprite.scaleX)||!Finite(sprite.scaleY)||!Finite(sprite.rotation)||!Finite(sprite.alpha))result|=Problem.NonFinite;
            if(sprite.container==null)result|=Problem.MissingContainer;
            if(!sprite.isVisible)result|=Problem.Hidden;
            if(sprite.alpha<=.0001f)result|=Problem.Transparent;
            if(Math.Abs(sprite.scaleX)<=.0001f||Math.Abs(sprite.scaleY)<=.0001f)result|=Problem.ZeroScale;
            return result;
        }
        static string Number(float value) { return value.ToString("0.####",CultureInfo.InvariantCulture); }
        static string Clean(string value) { return (value??"<none>").Replace('\r',' ').Replace('\n',' '); }
        static void Describe(StringBuilder output,string name,FSprite sprite)
        {
            output.Append("; ").Append(name).Append("{");
            if(sprite==null){output.Append("missing}");return;}
            output.Append("visible=").Append(sprite.isVisible).Append(" alpha=").Append(Number(sprite.alpha))
                .Append(" scale=").Append(Number(sprite.scaleX)).Append(',').Append(Number(sprite.scaleY))
                .Append(" xy=").Append(Number(sprite.x)).Append(',').Append(Number(sprite.y))
                .Append(" rotation=").Append(Number(sprite.rotation)).Append(" element=").Append(sprite.element==null?"<none>":Clean(sprite.element.name))
                .Append(" container=").Append(sprite.container==null?"<none>":sprite.container.GetType().Name+"#"+RuntimeHelpers.GetHashCode(sprite.container).ToString("x"))
                .Append(" depth=").Append(sprite.depth).Append('}');
        }
        static void Bounds(StringBuilder output,string name,RoomCamera.SpriteLeaser leaser,int start,int count)
        {
            int visible=0,points=0,invalid=0;float minX=Single.PositiveInfinity,minY=minX,maxX=Single.NegativeInfinity,maxY=maxX;
            for(int i=0;i<count;i++){
                var sprite=At(leaser,start+i);if(sprite==null||!sprite.isVisible)continue;visible++;
                var mesh=sprite as TriangleMesh;if(mesh==null||mesh.vertices==null)continue;
                foreach(Vector2 p in mesh.vertices){if(!Finite(p.x)||!Finite(p.y)){invalid++;continue;}points++;minX=Math.Min(minX,p.x);minY=Math.Min(minY,p.y);maxX=Math.Max(maxX,p.x);maxY=Math.Max(maxY,p.y);}
            }
            output.Append("; ").Append(name).Append("{visible=").Append(visible).Append(" bounds=");
            if(points==0)output.Append("<none>");else output.Append(Number(minX)).Append(',').Append(Number(minY)).Append("..").Append(Number(maxX)).Append(',').Append(Number(maxY));
            output.Append(" invalidVertices=").Append(invalid).Append('}');
        }
    }
}
