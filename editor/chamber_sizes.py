from pathlib import Path
import copy,io,json,math,os,shutil,subprocess,tempfile,uuid
from PIL import Image
from room_lingo import parse,dump,Call
import default_text,room_editor,storage


def options(spec):
    result=[dict(id='original',columns=0,rows=0,width=spec['width'],height=spec['height'],cameraCount=spec['cameraCount'])]
    for columns,rows in ((1,1),(2,1),(3,1),(1,2),(1,3),(2,2),(2,3),(3,2),(3,3)):
        if columns*70<spec['width'] or rows*40<spec['height']:continue
        result.append(dict(id=str(columns)+'x'+str(rows),columns=columns,rows=rows,width=columns*70,height=rows*40,cameraCount=columns*rows))
    return result


def resize_source(content,light,width,height):
    values=[parse(line) for line in content.decode('utf-8-sig').splitlines()[:9]]
    geo,tiles=values[0],values[1]['tlMatrix'];oldw,oldh=len(geo),len(geo[0])
    left,top,right,bottom=values[5]['extraTiles'];dw=width-(oldw-left-right);dh=height-(oldh-top-bottom)
    if dw<0 or dh<0:raise ValueError(default_text.text('chamberPresets.error.size'))
    xscore=lambda x:sum(geo[x][y][0][0]==0 for y in range(top,oldh-bottom))
    yscore=lambda y:sum(geo[x][y][0][0]==0 for x in range(left,oldw-right))
    shortcut=lambda cell:cell[0][0]==7 or bool(set(cell[0][1])&{4,5,6,7,8})
    xs=[x for x in range(left+1,oldw-right-1) if not any(shortcut(geo[column][y]) for column in (x-1,x) for y in range(oldh))]
    ys=[y for y in range(top+1,oldh-bottom-1) if not any(shortcut(geo[x][row]) for row in (y-1,y) for x in range(oldw))]
    if not xs or not ys:raise ValueError(default_text.text('chamberPresets.error.size'))
    sx=max(xs,key=lambda x:(xscore(x),x))
    sy=max(ys,key=lambda y:(yscore(y),-y))
    def nx(x):return x+dw if x>=sx else x
    def ny(y):return y+dh if y>=sy else y
    crossing=set()
    for x in range(oldw):
        for y in range(oldh):
            for z,cell in enumerate(tiles[x][y]):
                if cell['tp']!='tileBody':continue
                head=cell['data'][0];hx,hy=(int(v)-1 for v in head.args);hz=int(cell['data'][1])-1
                if (nx(x)-nx(hx),ny(y)-ny(hy))!=(x-hx,y-hy):crossing.add((hx,hy,hz))
    for x in range(oldw):
        for y in range(oldh):
            for z,cell in enumerate(tiles[x][y]):
                owner=(x,y,z)
                if cell['tp']=='tileBody':owner=(int(cell['data'][0].args[0])-1,int(cell['data'][0].args[1])-1,int(cell['data'][1])-1)
                if owner in crossing:tiles[x][y][z]={'tp':'material','data':'Standard'} if geo[x][y][z][0] else {'tp':'default','data':0}
                elif cell['tp']=='tileBody':cell['data'][0]=Call('point',[nx(owner[0])+1,ny(owner[1])+1])
    ix=lambda x:x if x<sx else sx if x<sx+dw else x-dw
    iy=lambda y:y if y<sy else sy if y<sy+dh else y-dh
    newgeo=[];newtiles=[]
    for x in range(oldw+dw):
        gc=[];tc=[]
        for y in range(oldh+dh):
            g=copy.deepcopy(geo[ix(x)][iy(y)]);t=copy.deepcopy(tiles[ix(x)][iy(y)])
            if sx<=x<sx+dw or sy<=y<sy+dh:
                for z in range(3):
                    if g[z][0]==7:raise ValueError(default_text.text('chamberPresets.error.size'))
                    g[z][1]=[flag for flag in g[z][1] if flag in (1,2)]
                    t[z]={'tp':'material','data':'Standard'} if g[z][0] else {'tp':'default','data':0}
            gc.append(g);tc.append(t)
        newgeo.append(gc);newtiles.append(tc)
    values[0]=newgeo;values[1]['tlMatrix']=newtiles
    for effect in values[2].get('effects',[]):
        matrix=effect.get('mtrx') if isinstance(effect,dict) else None
        if isinstance(matrix,list) and len(matrix)==oldw and all(len(col)==oldh for col in matrix):effect['mtrx']=[[matrix[ix(x)][iy(y)] for y in range(oldh+dh)] for x in range(oldw+dw)]
    for prop in values[8].get('props',[]):
        quad=prop[3];cx=sum(p.args[0] for p in quad)/len(quad);cy=sum(p.args[1] for p in quad)/len(quad)
        dx=dw*20 if cx>=sx*20 else 0;dy=dh*20 if cy>=sy*20 else 0
        for point in quad+prop[4].get('points',[]):point.args[0]+=dx;point.args[1]+=dy
    columns=width//70;rows=height//40
    values[5]['size']=Call('point',[oldw+dw,oldh+dh])
    values[6]['cameras']=[Call('point',[left*20+x*1400,top*20+y*800]) for y in range(rows) for x in range(columns)]
    values[6]['quads']=[[[0,0],[0,0],[0,0],[0,0]] for _ in range(columns*rows)]
    values[6]['selectedCamera']=0
    with Image.open(io.BytesIO(light)) as image:
        ax=sx*20+150;ay=sy*20+150
        expanded=Image.new(image.mode,(image.width+dw*20,image.height+dh*20),'white')
        for x0,x1,dx in ((0,ax,0),(ax,image.width,dw*20)):
            for y0,y1,dy in ((0,ay,0),(ay,image.height,dh*20)):expanded.paste(image.crop((x0,y0,x1,y1)),(x0+dx,y0+dy))
        if dw:
            strip=image.crop((ax,0,ax+1,image.height)).resize((dw*20,image.height))
            expanded.paste(strip.crop((0,0,dw*20,ay)),(ax,0));expanded.paste(strip.crop((0,ay,dw*20,image.height)),(ax,ay+dh*20))
        if dh:
            strip=expanded.crop((0,ay-1,expanded.width,ay)).resize((expanded.width,dh*20));expanded.paste(strip,(0,ay))
        output=io.BytesIO();expanded.save(output,format='PNG')
    source=('\r\n'.join(dump(v) for v in values)+'\r\n').encode('utf-8')
    return source,output.getvalue(),dict(x=(sx-left)*20,y=(oldh-bottom-sy)*20,dx=dw*20,dy=dh*20)


def resize_settings(content,shift,cameras,columns=None):
    lines=[]
    for line in content.decode('utf-8-sig').splitlines():
        if line.startswith('PlacedObjects: '):
            objects=[]
            for raw in line[len('PlacedObjects: '):].split(', '):
                if not raw:continue
                parts=raw.split('><')
                if len(parts)>=4:
                    x,y=float(parts[1]),float(parts[2]);parts[1]=format(x+(shift['dx'] if x>=shift['x'] else 0),'.8g');parts[2]=format(y+(shift['dy'] if y>shift['y'] else 0),'.8g')
                objects.append('><'.join(parts))
            line='PlacedObjects: '+', '.join(objects)+', '
        elif line.startswith('FadePalette: '):
            parts=line.split(': ',1)[1].split(', ');columns=columns or cameras
            fades=[parts[min(len(parts)-1,1+round((i%columns)*max(0,len(parts)-2)/max(1,columns-1)))] for i in range(cameras)]
            line='FadePalette: '+', '.join([parts[0]]+fades)
        elif line.startswith('AmbientSounds: '):
            sounds=[]
            for raw in line[len('AmbientSounds: '):].split(', '):
                if not raw:continue
                parts=raw.split('><')
                if parts[0]=='SPOT' and len(parts)>=8:
                    x,y=float(parts[6]),float(parts[7]);parts[6]=format(x+(shift['dx'] if x>=shift['x'] else 0),'.8g');parts[7]=format(y+(shift['dy'] if y>shift['y'] else 0),'.8g')
                sounds.append('><'.join(parts))
            line='AmbientSounds: '+', '.join(sounds)+', '
        elif line.startswith('Triggers: '):
            triggers=[]
            for raw in line[len('Triggers: '):].split(', '):
                if not raw:continue
                fields=raw.split('<tA>')
                for index,field in enumerate(fields):
                    parts=field.split('<tB>')
                    if parts[0]=='pos' and len(parts)==3:
                        x,y=float(parts[1]),float(parts[2]);parts[1]=format(x+(shift['dx'] if x>=shift['x'] else 0),'.8g');parts[2]=format(y+(shift['dy'] if y>shift['y'] else 0),'.8g');fields[index]='<tB>'.join(parts)
                triggers.append('<tA>'.join(fields))
            line='Triggers: '+', '.join(triggers)+', '
        lines.append(line)
    return ('\n'.join(lines)+'\n').encode('utf-8')


def render(assets,spec,size_id):
    size=next((row for row in options(spec) if row['id']==size_id),None)
    if size is None:raise ValueError(default_text.text('chamberPresets.error.size'))
    if size_id=='original':return assets,spec
    exe=room_editor.rained_root();data=room_editor.rained_data_root(exe)
    staging=(storage.DATA/'.staging').resolve();staging.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='chamber-',dir=staging) as temporary:
        root=Path(temporary);resources=root/'data';resources.mkdir()
        for name in ('Graphics','Materials','Effects','Props'):
            target=data/name
            if not target.is_dir():continue
            link=resources/name
            if os.name=='nt':
                command="New-Item -ItemType Junction -Path '"+str(link).replace("'","''")+"' -Target '"+str(target).replace("'","''")+"' | Out-Null"
                result=subprocess.run(['powershell','-NoProfile','-Command',command],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
                if result.returncode:raise ValueError(default_text.text('chamberPresets.error.render'))
            else:link.symlink_to(target,target_is_directory=True)
        for file in data.iterdir():
            if file.is_file():shutil.copy2(file,resources/file.name)
        (resources/'Levels').mkdir()
        source,light,shift=resize_source(assets['source']['.txt'],assets['source']['.png'],size['width'],size['height'])
        name='MI_CHAMBER_'+uuid.uuid4().hex;file=root/(name+'.txt');file.write_bytes(source);file.with_suffix('.png').write_bytes(light)
        try:
            result=subprocess.run([str(exe),'--no-splash-screen','--no-autoloads','--app-data',str(root/'profile'),'--data',str(resources),'--render','--threads','1',str(file)],cwd=exe.parent,capture_output=True,timeout=600,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        except subprocess.TimeoutExpired:raise ValueError(default_text.text('chamberPresets.error.render')) from None
        if result.returncode:raise ValueError(default_text.text('chamberPresets.error.render')) from RuntimeError((result.stdout+result.stderr).decode('utf-8',errors='replace')[-6000:])
        rendered=resources/'Levels'/name;geometry=rendered.with_suffix('.txt').read_bytes()
        lines=geometry.decode('utf-8-sig').splitlines()
        if lines[1].split('|')[0]!=str(size['width'])+'*'+str(size['height']) or len([v for v in lines[3].split('|') if v])!=size['cameraCount']:raise ValueError(default_text.text('chamberPresets.error.render'))
        output={'source':{'.txt':source,'.png':light},'rendered':{'.txt':geometry}}
        for i in range(1,size['cameraCount']+1):output['rendered']['_'+str(i)+'.png']=rendered.with_name(name+'_'+str(i)+'.png').read_bytes()
        for suffix,content in assets['rendered'].items():
            if suffix.startswith('_settings'):output['rendered'][suffix]=resize_settings(content,shift,size['cameraCount'],size['columns'])
        return output,dict(spec,**{key:size[key] for key in ('width','height','cameraCount')})
