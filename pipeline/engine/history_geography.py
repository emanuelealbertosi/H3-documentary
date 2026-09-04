"""Bounded detailed atlas requests, reusing the established terrain preparation tools."""
import math


def merc(y):return math.degrees(math.asinh(math.tan(math.radians(y))))
def inv(y):return math.degrees(math.atan(math.sinh(math.radians(y))))


def bounds(views):
    return [min(x-w*.57 for x,y,w in views),min(inv(merc(y)-w*.33) for x,y,w in views),
            max(x+w*.57 for x,y,w in views),max(inv(merc(y)+w*.33) for x,y,w in views)]


def atlas_config(views,output='assets/geography/atlas-film'):
    box=bounds(views)
    if not(-180<box[0]<box[2]<180 and -79<box[1]<box[3]<79):raise ValueError('Suddividere il teatro geografico in viste più contenute')
    patches={}
    for view in views:
        if view[2]>16:continue
        b=bounds([view])
        if any(old[0]<=b[0] and old[1]<=b[1] and old[2]>=b[2] and old[3]>=b[3] for old in patches.values()):continue
        if len(patches)<6:patches['detail'+str(len(patches)+1)]=b
    area=sum((b[2]-b[0])*(merc(b[3])-merc(b[1])) for b in patches.values())
    return {'bounds':box,'patches':patches,'terrain_zoom':7 if area>450 else 8,'output':output}
