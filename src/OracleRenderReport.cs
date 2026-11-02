using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Security;
using System.Text;
using UnityEngine;

namespace MoreIterators
{
    // Captured only when requested from F8; no polling, server, or project writes.
    public static class OracleRenderReport
    {
        public static void Open(string oracleId)
        {
            var graphics=StudioRuntime.Graphics;
            var leaser=StudioRuntime.Sprites;
            if(graphics==null||graphics.oracle==null||graphics.oracle.room==null||leaser==null||leaser.sprites==null)
                throw new InvalidOperationException(UiText.Get("No current iterator render snapshot is available."));
            if(CreatorRuntime.Id(graphics.oracle.room.abstractRoom.name)!=oracleId)
                throw new InvalidOperationException(UiText.Get("The render snapshot belongs to a different iterator. Re-enter its chamber before opening the report."));
            var design=IteratorDesign.ForRoom(graphics.oracle.room);
            string directory=Path.Combine(BepInEx.Paths.BepInExRootPath,"MoreIterators/diagnostics");
            Directory.CreateDirectory(directory);
            string path=Path.Combine(directory,"iterator-render-state.html");
            File.WriteAllText(path,Build(graphics,leaser,design,DateTime.Now),new UTF8Encoding(false));
            MiDiagnostics.Info("OracleRenderReport","project="+design.projectId+" file="+path);
            Application.OpenURL(new Uri(Path.GetFullPath(path)).AbsoluteUri);
        }

        internal static string Build(OracleGraphics graphics,RoomCamera.SpriteLeaser leaser,IteratorDesign design,DateTime time)
        {
            var html=new StringBuilder("<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>");
            html.Append(E(UiText.Get("Iterator render state"))).Append("</title><style>body{margin:28px;background:#181818;color:#eee;font:15px system-ui,sans-serif}h1{font-size:24px}dl{display:grid;grid-template-columns:max-content 1fr;gap:8px 22px}dt{color:#aaa}dd{margin:0;overflow-wrap:anywhere}.table{overflow:auto;border:1px solid #666}table{width:100%;border-collapse:collapse;font-size:13px}th,td{padding:8px;text-align:left;border-bottom:1px solid #444;white-space:nowrap}th{background:#242424}.hidden{color:#aaa}code{font-family:monospace}</style></head><body><h1>").Append(E(UiText.Get("Iterator render state"))).Append("</h1><dl>");
            Field(html,"Captured",time.ToString("yyyy-MM-dd HH:mm:ss zzz",CultureInfo.InvariantCulture));
            Field(html,"Project",design.projectId);Field(html,"Iterator ID",design.oracleId);
            Field(html,"Room",graphics.oracle.room==null?"-":graphics.oracle.room.abstractRoom.name);
            Field(html,"Culled",OnOff(graphics.culled));Field(html,"Body setting",OnOff(design.layers==null||design.layers.body));
            html.Append("</dl><div class='table'><table><thead><tr>");
            foreach(string column in new[]{"Sprite index","Part","Element","Visible","Opacity","Scale","Position","Render depth","Container","Mesh bounds"})
                html.Append("<th>").Append(E(UiText.Get(column))).Append("</th>");
            html.Append("</tr></thead><tbody>");
            var containers=new Dictionary<FContainer,int>();
            for(int i=0;i<leaser.sprites.Length;i++)
            {
                var sprite=leaser.sprites[i];
                html.Append(sprite==null||!sprite.isVisible?"<tr class='hidden'>":"<tr>");
                Cell(html,i.ToString(CultureInfo.InvariantCulture));Cell(html,Part(graphics,i));
                Cell(html,sprite==null||sprite.element==null?"-":sprite.element.name);
                Cell(html,OnOff(sprite!=null&&sprite.isVisible));
                Cell(html,sprite==null?"-":N(sprite.alpha));
                Cell(html,sprite==null?"-":N(sprite.scaleX)+", "+N(sprite.scaleY));
                Cell(html,sprite==null?"-":N(sprite.x)+", "+N(sprite.y));
                Cell(html,sprite==null?"-":sprite.depth.ToString(CultureInfo.InvariantCulture));
                string container="-";
                if(sprite!=null&&sprite.container!=null){int id;if(!containers.TryGetValue(sprite.container,out id)){id=containers.Count+1;containers.Add(sprite.container,id);}container=sprite.container.GetType().Name+" #"+id;}
                Cell(html,container);Cell(html,MeshBounds(sprite as TriangleMesh));html.Append("</tr>");
            }
            return html.Append("</tbody></table></div></body></html>").ToString();
        }

        static string Part(OracleGraphics g,int index)
        {
            if(index>=g.firstBodyChunkSprite&&index<g.firstBodyChunkSprite+g.oracle.bodyChunks.Length)return UiText.Get("Torso")+" "+(index-g.firstBodyChunkSprite+1);
            if(index==g.neckSprite)return UiText.Get("Neck");
            if(index==g.HeadSprite||index==g.ChinSprite)return UiText.Get("Head");
            if(index==g.robeSprite)return UiText.Get("Gown");
            for(int side=0;side<2;side++){
                if(index==g.EyeSprite(side))return UiText.Get("Eyes")+" "+(side+1);
                if(index==g.HandSprite(side,0))return UiText.Get("Hands")+" "+(side+1);
                if(index==g.HandSprite(side,1))return UiText.Get("Sleeves")+" "+(side+1);
                for(int k=0;k<2;k++)if(index==g.FootSprite(side,k))return UiText.Get("Feet")+" "+(side+1);
            }
            return "-";
        }
        static string MeshBounds(TriangleMesh mesh)
        {
            if(mesh==null||mesh.vertices==null||mesh.vertices.Length==0)return "-";
            float minX=Single.PositiveInfinity,minY=minX,maxX=Single.NegativeInfinity,maxY=maxX;
            foreach(var point in mesh.vertices){minX=Math.Min(minX,point.x);minY=Math.Min(minY,point.y);maxX=Math.Max(maxX,point.x);maxY=Math.Max(maxY,point.y);}
            return mesh.vertices.Length+" ("+N(minX)+", "+N(minY)+" → "+N(maxX)+", "+N(maxY)+")";
        }
        static string E(string text){return SecurityElement.Escape(text??"")??"";}
        static string N(float value){return value.ToString("0.###",CultureInfo.InvariantCulture);}
        static string OnOff(bool value){return UiText.Get(value?"Enabled":"Not enabled");}
        static void Cell(StringBuilder html,string text){html.Append("<td>").Append(E(text)).Append("</td>");}
        static void Field(StringBuilder html,string original,string value){html.Append("<dt>").Append(E(UiText.Get(original))).Append("</dt><dd>").Append(E(value)).Append("</dd>");}
    }
}
