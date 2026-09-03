"""Choose fixed label offsets across camera samples before any frame is rendered."""
import sys,json,math
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from engine.common import ROOT,read_json,write_json
from engine.visuals import font
from engine.atlas import camera,screen

def area(a,b):
    return max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
def arrange(timeline):
    candidates=[(0,-30),(0,34),(-55,-45),(55,-45),(-90,35),(90,35),(0,-85),(0,85),
      (-150,-45),(150,-45),(-150,55),(150,55),(-65,-120),(65,-120),(-220,0),(220,0)]
    reserved=[(0,0,1920,168),(0,862,1920,1080),(1555,685,1890,885)]
    changes=[]
    for s in timeline["scenes"]:
        cams=[camera(s,s["duration"]*t) for t in [.12,.25,.42,.7]]
        chosen=[[] for _ in cams];offsets={}
        for pid in s.get("visible_places",[]):
            place=timeline["places"][pid];ft=font(place.get("size",24));w=ft.getlength(place["name"])+16;h=36
            positions=[screen(place["pos"],c) for c in cams]
            best=None
            for dx,dy in candidates:
                score=.12*math.hypot(dx,dy);boxes=[]
                for i,(x,y) in enumerate(positions):
                    b=(x+dx-w/2,y+dy-h/2,x+dx+w/2,y+dy+h/2);boxes.append(b)
                    if not(-50<x<1970 and -50<y<1130):continue
                    score+=sum(area(b,a)*5 for a in chosen[i])+sum(area(b,a)*2 for a in reserved)
                    score+=max(0,-b[0])*h+max(0,b[2]-1920)*h+max(0,-b[1])*w+max(0,b[3]-1080)*w
                if best is None or score<best[0]:best=(score,[dx,dy],boxes)
            offsets[pid]=best[1]
            for i,b in enumerate(best[2]):chosen[i].append(b)
        s["label_offsets"]=offsets
        changes.append({"scene":s["id"],"offsets":offsets})
    return changes
if __name__=="__main__":
    packpath=Path(sys.argv[1]);p=read_json(packpath);path=ROOT/"build"/p["slug"]/"timeline.json";t=read_json(path)
    changes=arrange(t)
    for s in p["scenes"]:
        s["label_offsets"]=next(x["offsets"] for x in changes if x["scene"]==s["id"])
    write_json(packpath,p);write_json(path,t);write_json(ROOT/"timeline.json",t)
    write_json(ROOT/"build"/p["slug"]/"label-layout.json",{"method":"Fixed offsets selected across four camera poses; no frame-by-frame label movement.","scenes":changes})
    print("Static label layout prepared for",len(changes),"scenes.",flush=True)
