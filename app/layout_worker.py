"""Choose fixed label offsets across camera samples before any frame is rendered."""
import sys,json,math
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from engine.common import ROOT,read_json,write_json
from engine.visuals import font
from engine.atlas import camera,screen,partial,progress

def area(a,b):
    return max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
def arrange(timeline):
    candidates=[(0,-30),(0,34),(-55,-45),(55,-45),(-90,35),(90,35),(0,-85),(0,85),
      (-150,-45),(150,-45),(-150,55),(150,55),(-65,-120),(65,-120),(-220,0),(220,0)]
    unit_candidates=[(0,-32),(0,34),(-75,-30),(75,-30),(-95,32),(95,32),(0,-78),(0,78),
      (-145,-36),(145,-36),(-145,42),(145,42),(-210,-70),(210,-70),(-210,70),(210,70),(0,-120),(0,120)]
    reserved=[(0,0,1920,168),(0,862,1920,1080),(1555,685,1890,885)]
    icon_spread={2:[(-22,0),(22,0)],3:[(-27,0),(0,22),(27,0)],4:[(-28,-13),(28,-13),(-28,13),(28,13)]}
    changes=[]
    for s in timeline["scenes"]:
        if s.get('mode')=='ending':
            # The overview already has place names and a final narrative card.
            # Repeated army names make that closing frame harder to read.
            for unit in s.get('units',[]):unit['show_label']=False
        # Paths often converge only in the final seconds. Fixed offsets chosen
        # without those frames looked good in the middle but collided at the
        # end; sample the settled action as well, keeping labels flicker-free.
        samples=[.12,.25,.42,.7,.86,.96]
        cams=[camera(s,s["duration"]*t) for t in samples]
        chosen=[list(reserved) for _ in cams];offsets={}
        # Counter positions are known before labels are placed. Reserve them so
        # a place name can never be drawn through a formation symbol.
        groups={}
        for unit in s.get('units',[]):
            anchor=(unit.get('path') or [unit.get('pos')])[-1]
            key=tuple(round(float(v),5) for v in anchor)
            groups.setdefault(key,[]).append(unit)
        for units in groups.values():
            if len(units)>1:
                pattern=icon_spread.get(min(4,len(units)),icon_spread[4])
                for i,unit in enumerate(units):unit['screen_offset']=list(pattern[i%len(pattern)])
        unit_positions={}
        for unit in s.get('units',[]):
            positions=[]
            for cam,tq in zip(cams,samples):
                at=s['duration']*tq
                pos=partial(unit['path'],progress(s,unit,at))[-1] if unit.get('path') else unit['pos']
                x,y=screen(pos,cam);sx,sy=unit.get('screen_offset',[0,0]);positions.append((x+sx,y+sy))
            unit_positions[unit['id']]=positions
            for i,(x,y) in enumerate(positions):
                if -50<x<1970 and -50<y<1130:chosen[i].append((x-42,y-12,x+42,y+12))
        for pid in s.get("visible_places",[]):
            place=timeline["places"][pid];ft=font(place.get("size",24));w=ft.getlength(place["name"])+16;h=36
            positions=[screen(place["pos"],c) for c in cams]
            best=None
            for dx,dy in candidates:
                score=.12*math.hypot(dx,dy);boxes=[]
                for i,(x,y) in enumerate(positions):
                    b=(x+dx-w/2,y+dy-h/2,x+dx+w/2,y+dy+h/2);boxes.append(b)
                    if not(-50<x<1970 and -50<y<1130):continue
                    score+=sum(area(b,a)*5 for a in chosen[i])
                    score+=max(0,-b[0])*h+max(0,b[2]-1920)*h+max(0,-b[1])*w+max(0,b[3]-1080)*w
                if best is None or score<best[0]:best=(score,[dx,dy],boxes)
            offsets[pid]=best[1]
            for i,b in enumerate(best[2]):chosen[i].append(b)
        for unit in s.get('units',[]):
            if not unit.get('show_label',True) or not unit.get('label'):continue
            ft=font(16);label=unit.get('label','');w=ft.getlength(label)+18;h=28
            positions=unit_positions[unit['id']]
            best=None
            for dx,dy in unit_candidates:
                score=.10*math.hypot(dx,dy);boxes=[]
                for i,(x,y) in enumerate(positions):
                    b=(x+dx-w/2,y+dy-h/2,x+dx+w/2,y+dy+h/2);boxes.append(b)
                    if -50<x<1970 and -50<y<1130:
                        score+=sum(area(b,a)*5 for a in chosen[i])
                        score+=max(0,-b[0])*h+max(0,b[2]-1920)*h+max(0,-b[1])*w+max(0,b[3]-1080)*w
                if best is None or score<best[0]:best=(score,[dx,dy],boxes)
            unit['label_offset']=best[1]
            for i,b in enumerate(best[2]):chosen[i].append(b)
        s["label_offsets"]=offsets
        changes.append({"scene":s["id"],"offsets":offsets,"units":[{"id":u['id'],"label_offset":u.get('label_offset',[0,-32]),"screen_offset":u.get('screen_offset',[0,0]),"show_label":u.get('show_label',True)} for u in s.get('units',[])]})
    return changes
if __name__=="__main__":
    packpath=Path(sys.argv[1]);p=read_json(packpath);path=ROOT/"build"/p["slug"]/"timeline.json";t=read_json(path)
    changes=arrange(t)
    for s in p["scenes"]:
        change=next(x for x in changes if x["scene"]==s["id"]);s["label_offsets"]=change["offsets"]
        by_id={u['id']:u for u in change['units']}
        for unit in s.get('units',[]):
            if unit['id'] in by_id:unit.update({k:by_id[unit['id']][k] for k in ('label_offset','screen_offset','show_label')})
    write_json(packpath,p);write_json(path,t);write_json(ROOT/"timeline.json",t)
    write_json(ROOT/"build"/p["slug"]/"label-layout.json",{"method":"Fixed offsets selected across six camera poses, including the settled action; no frame-by-frame label movement.","scenes":changes})
    print("Static label layout prepared for",len(changes),"scenes.",flush=True)
