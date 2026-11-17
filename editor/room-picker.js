'use strict';
(function(global){
  let active=null;
  const text=value=>global.MI18n?.text(value)||value;
  const node=(tag,label,cls)=>{const e=document.createElement(tag);if(label!==undefined)e.textContent=text(label);if(cls)e.className=cls;return e;};
  const content=(tag,value,cls)=>{const e=node(tag,undefined,cls);global.MI18n?.content(e);e.textContent=value;return e;};
  const button=(label,action)=>{const b=node('button',label);b.type='button';b.onclick=action;return b;};
  async function request(path,params){
    const query=new URLSearchParams(Object.entries(params).filter(([,value])=>value!==undefined&&value!==null));
    const response=await fetch('/api/'+path+'?'+query,{headers:{'X-MI-Language':global.MI18n?.locale||'zh-CN'}});
    const value=await response.json();if(!response.ok)throw Error(global.MI18n?.error(value,'请求失败')||value.error||'Request failed');return value;
  }
  function layout(rooms){
    const located=rooms.filter(room=>Array.isArray(room.position)),right=located.length?Math.max(...located.map(room=>room.position[0]))+180:0;
    const missing=rooms.filter(room=>!Array.isArray(room.position)),columns=Math.max(1,Math.ceil(Math.sqrt(missing.length)));
    return rooms.map(room=>{const i=missing.indexOf(room);return {...room,x:i<0?room.position[0]:right+(i%columns)*150,y:i<0?-room.position[1]:Math.floor(i/columns)*70};});
  }
  function open(options={}){
    active?.();
    return new Promise(resolve=>{
      let closed=false,data=null,current=null,geometry=null,image=null,point=null,regionToken=0,roomToken=0,view=null,initialView=null,canvasRect=null;
      const dialog=node('dialog',undefined,'mi-room-picker'),heading=node('header'),title=node('h2',options.readOnly?'房间预览':'地图选房'),close=button('关闭',()=>finish(null));
      heading.append(title,close);
      const toolbar=node('div',undefined,'rp-toolbar'),region=node('select'),search=node('input');region.setAttribute('aria-label',text('区域'));search.type='search';search.placeholder=text('搜索房间');search.setAttribute('aria-label',text('搜索房间'));
      const regionsLabel=node('label','区域');regionsLabel.append(region);toolbar.append(regionsLabel,search);
      const body=node('div',undefined,'rp-body'),mapSide=node('section',undefined,'rp-map-side'),mapHeading=node('div',undefined,'rp-map-heading'),mapTitle=node('span','区域地图');
      const mapTools=node('div');mapTools.append(button('−',()=>zoom(1.35)),button('+',()=>zoom(1/1.35)),button('重置视图',()=>{if(initialView){view={...initialView};setView();}}));mapHeading.append(mapTitle,mapTools);
      const mapBody=node('div',undefined,'rp-map-body'),list=node('div',undefined,'rp-room-list');list.setAttribute('role','listbox');list.setAttribute('aria-label',text('房间'));
      const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.classList.add('rp-map');svg.setAttribute('aria-label',text('区域地图'));svg.setAttribute('role','group');
      mapBody.append(list,svg);mapSide.append(mapHeading,mapBody);
      const detail=node('section',undefined,'rp-detail'),roomName=content('h3',''),canvas=node('canvas');canvas.width=1000;canvas.height=680;canvas.className='rp-preview';canvas.setAttribute('aria-label',text('房间预览'));
      const previewKind=node('p','', 'rp-hint'),coordinates=content('p','', 'rp-coordinates'),connections=node('div',undefined,'rp-connections');detail.append(roomName,canvas,previewKind,coordinates,connections);body.append(mapSide,detail);
      const footer=node('footer'),status=node('p','', 'rp-status');status.setAttribute('role','status');const cancel=button('取消',()=>finish(null)),use=button('选择房间',async()=>{
        if(!current||use.disabled)return;const value={room:current.name,region:current.region,geometry,...(point?{point:{...point},pixelPoint:{x:point.x*geometry.width*20,y:point.y*geometry.height*20}}:{})};
        use.disabled=true;try{await options.onSelect?.(value);finish(value);}catch(error){status.textContent=error.message;updateUse();}
      });use.hidden=!!options.readOnly;footer.append(status,cancel,use);dialog.append(heading,toolbar,body,footer);document.body.append(dialog);
      const previous=document.activeElement;
      function finish(value){if(closed)return;closed=true;regionToken++;roomToken++;dialog.close();dialog.remove();active=null;previous?.focus();resolve(value);}
      active=()=>finish(null);dialog.addEventListener('cancel',event=>{event.preventDefault();finish(null);});
      function updateUse(){use.disabled=!current||!geometry||!!options.readOnly||options.selectable?.(current)===false;}
      function setView(){if(view)svg.setAttribute('viewBox',[view.x,view.y,view.w,view.h].join(' '));}
      function zoom(factor,event){if(!view)return;const rect=svg.getBoundingClientRect(),px=event?(event.clientX-rect.left)/rect.width:.5,py=event?(event.clientY-rect.top)/rect.height:.5;const width=Math.max(100,Math.min(initialView.w*6,view.w*factor)),ratio=width/view.w;view={x:view.x+view.w*px*(1-ratio),y:view.y+view.h*py*(1-ratio),w:width,h:view.h*ratio};setView();}
      svg.addEventListener('wheel',event=>{event.preventDefault();zoom(event.deltaY>0?1.15:1/1.15,event);},{passive:false});
      let pan=null;svg.addEventListener('pointerdown',event=>{if(event.target!==svg||event.button!==0)return;pan={x:event.clientX,y:event.clientY,view:{...view}};svg.setPointerCapture(event.pointerId);});
      svg.addEventListener('pointermove',event=>{if(!pan)return;const rect=svg.getBoundingClientRect();view={...pan.view,x:pan.view.x-(event.clientX-pan.x)*pan.view.w/rect.width,y:pan.view.y-(event.clientY-pan.y)*pan.view.h/rect.height};setView();});
      svg.addEventListener('pointerup',()=>pan=null);svg.addEventListener('pointercancel',()=>pan=null);
      function markSelection(){
        for(const el of dialog.querySelectorAll('[data-room]')){const selected=el.dataset.room===current?.name;el.classList.toggle('selected',selected);el.setAttribute(el.tagName.toLowerCase()==='button'?'aria-selected':'aria-pressed',String(selected));}
      }
      function renderMap(){
        const rooms=layout(data?.rooms||[]),lookup=new Map(rooms.map(room=>[room.name,room]));svg.replaceChildren();const ns=svg.namespaceURI;
        function element(tag,attrs){const el=document.createElementNS(ns,tag);for(const [key,value]of Object.entries(attrs))el.setAttribute(key,value);return el;}
        const seen=new Set();for(const room of rooms)for(const name of room.connections||[]){const target=lookup.get(name),key=[room.name,name].sort().join('\n');if(!target||seen.has(key))continue;seen.add(key);svg.append(element('line',{x1:room.x,y1:room.y,x2:target.x,y2:target.y,class:'rp-edge'}));}
        for(const room of rooms){const g=element('g',{transform:`translate(${room.x},${room.y})`,role:'button',tabindex:0,'aria-label':room.name,'data-room':room.name,class:'rp-node'+(!room.position?' rp-unplaced':'')});
          const label=element('text',{'text-anchor':'middle',y:4});label.textContent=room.name;const width=Math.max(64,room.name.length*7+14);g.append(element('rect',{x:-width/2,y:-13,width,height:26,rx:3}),label);g.onclick=()=>select(room);g.onkeydown=event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();select(room);}};svg.append(g);}
        const xs=rooms.map(room=>room.x),ys=rooms.map(room=>room.y);initialView={x:Math.min(0,...xs)-100,y:Math.min(0,...ys)-50,w:Math.max(200,Math.max(0,...xs)-Math.min(0,...xs)+200),h:Math.max(150,Math.max(0,...ys)-Math.min(0,...ys)+100)};view={...initialView};setView();renderList();markSelection();
      }
      function renderList(){const query=search.value.trim().toUpperCase();list.replaceChildren(...(data?.rooms||[]).filter(room=>!query||room.name.includes(query)).map(room=>{const b=button('',()=>select(room));global.MI18n?.content(b);b.textContent=room.name;b.dataset.room=room.name;b.setAttribute('role','option');return b;}));markSelection();}
      async function loadRegion(id,initial=false){
        const token=++regionToken;++roomToken;current=null;geometry=null;image=null;point=null;roomName.textContent='';connections.replaceChildren();drawPreview();updateUse();status.textContent=text('正在加载');
        try{const value=await request('room-picker-map',{region:id||'',projectId:options.projectId||'',lang:global.MI18n?.locale||'zh-CN'});if(closed||token!==regionToken)return;data=value;region.replaceChildren(...value.regions.map(item=>{const e=content('option',item.name===item.id?item.id:item.name+' ('+item.id+')');e.value=item.id;return e;}));region.value=value.region;mapTitle.textContent=text(value.layout==='map'?'区域地图':'连接示意');renderMap();status.textContent='';
          const room=value.rooms.find(item=>item.name===(initial?options.room:''))||value.rooms[0];if(room)await select(room,initial);else status.textContent=text('没有可用房间');
        }catch(error){if(!closed&&token===regionToken){status.textContent=error.message;data=null;renderMap();}}
      }
      async function select(room,initial=false){
        const token=++roomToken;current=room;geometry=null;image=null;point=initial&&options.point?{...options.point}:null;roomName.textContent=room.name;markSelection();updateUse();drawPreview();status.textContent=text('正在加载');connections.replaceChildren();
        try{const value=await request('room-picker-preview',{room:room.name,projectId:options.projectId||''});if(closed||token!==roomToken)return;geometry=value;
          if(value.image){const loaded=new Image();loaded.src=value.image;await loaded.decode();if(closed||token!==roomToken)return;image=loaded;}
          previewKind.textContent=text(image?'相机预览':'房间地形');status.textContent=!options.readOnly&&options.selectable?.(room)===false?text(options.unavailableText||'此房间不可选择'):'';
          const destinations=(room.connections||[]).filter(name=>name&&name!=='DISCONNECTED');if(destinations.length){connections.append(node('span','连接房间'));for(const name of [...new Set(destinations)]){const target=data.rooms.find(item=>item.name===name),b=button('',()=>{if(target)select(target);});global.MI18n?.content(b);b.textContent=name;b.disabled=!target;connections.append(b);}}
          drawPreview();updateUse();
        }catch(error){if(!closed&&token===roomToken){status.textContent=error.message;drawPreview();updateUse();}}
      }
      function drawPreview(){
        const ctx=canvas.getContext('2d');ctx.clearRect(0,0,canvas.width,canvas.height);ctx.fillStyle='#181818';ctx.fillRect(0,0,canvas.width,canvas.height);canvasRect=null;coordinates.textContent='';if(!geometry)return;
        const width=geometry.width,height=geometry.height,s=Math.min((canvas.width-24)/width,(canvas.height-24)/height),x=(canvas.width-width*s)/2,y=(canvas.height-height*s)/2;canvasRect={x,y,w:width*s,h:height*s};
        if(image)ctx.drawImage(image,x,y,width*s,height*s);else{ctx.fillStyle='#777';for(const [tx,ty]of geometry.solids||[])ctx.fillRect(x+tx*s,y+(height-ty-1)*s,Math.ceil(s),Math.ceil(s));}
        ctx.fillStyle='#dedede';for(const [tx,ty]of geometry.shortcuts||[])ctx.fillRect(x+tx*s,y+(height-ty-1)*s,Math.max(3,s),Math.max(3,s));
        if(point){const px=x+point.x*width*s,py=y+(1-point.y)*height*s;ctx.strokeStyle='#fff';ctx.lineWidth=2;ctx.beginPath();ctx.arc(px,py,7,0,Math.PI*2);ctx.moveTo(px-12,py);ctx.lineTo(px+12,py);ctx.moveTo(px,py-12);ctx.lineTo(px,py+12);ctx.stroke();coordinates.textContent='X '+Math.round(point.x*width*20)+'   Y '+Math.round(point.y*height*20);}
      }
      canvas.classList.toggle('rp-point-enabled',!!options.pickPoint);canvas.onclick=event=>{if(!options.pickPoint||!canvasRect)return;const r=canvas.getBoundingClientRect(),x=(event.clientX-r.left)/r.width*canvas.width,y=(event.clientY-r.top)/r.height*canvas.height,c=canvasRect;if(x<c.x||x>c.x+c.w||y<c.y||y>c.y+c.h)return;point={x:Math.max(0,Math.min(1,(x-c.x)/c.w)),y:Math.max(0,Math.min(1,1-(y-c.y)/c.h))};drawPreview();};
      region.onchange=()=>{search.value='';loadRegion(region.value);};search.oninput=renderList;dialog.showModal();const roomParts=String(options.room||'').split('_');loadRegion(options.region||(roomParts[0]==='GATE'?roomParts[1]:roomParts[0]),true);
    });
  }
  global.MIRoomPicker={open,layout};
})(typeof window!=='undefined'?window:globalThis);
