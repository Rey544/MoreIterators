(function(scope){
 'use strict';
                                                                 
 const mask=['..+####+.....','.+#....#+....','+#..++..+....','#..+##+......','#.+#.........','#.+#.##....#.','#..+.##....#+','+#.....#..+##','.++.....#+###','........+####','.......+####+','.....#######.','......+###+..'];
 function draw(canvas,color='#C9CCCF'){
  const ctx=canvas.getContext('2d'),w=canvas.width,h=canvas.height;
  if(!ctx||!w||!h)return;
  const scale=Math.min(w,h)<13?Math.min(w,h)/13:Math.floor(Math.min(w,h)/13),ox=Math.floor((w-13*scale)/2),oy=Math.floor((h-13*scale)/2);
  ctx.save();ctx.setTransform(1,0,0,1,0,0);ctx.clearRect(0,0,w,h);ctx.globalCompositeOperation='source-over';ctx.fillStyle=/^#[\da-f]{6}$/i.test(color)?color:'#C9CCCF';ctx.imageSmoothingEnabled=false;
  for(let y=0;y<13;y++)for(let x=0;x<13;x++){const pixel=mask[y][x];if(pixel==='.')continue;ctx.globalAlpha=pixel==='+'?115/255:1;ctx.fillRect(ox+x*scale,oy+y*scale,scale,scale);}
  ctx.restore();
 }
 scope.MIBroadcastIcon={draw};
})(globalThis);
