"""Lossless shape repairs. Never fabricate a place or choose a fuzzy geographic match."""
import copy,unicodedata

COLLECTIONS=('places','persons','entities','events','visual_layers','visual_assets')

def collections(value):
    if not isinstance(value,dict):return value
    data=copy.deepcopy(value)
    for key in COLLECTIONS:
        rows=data.get(key)
        if isinstance(rows,dict) and all(isinstance(v,dict) for v in rows.values()):
            data[key]=[{'id':k,**v} for k,v in rows.items()]
    return data

def normalized(value):
    return ''.join(c for c in unicodedata.normalize('NFKD',str(value)).casefold() if not unicodedata.combining(c)).strip()

def place_references(data,places):
    data=copy.deepcopy(data);ids={p['id'] for p in places};aliases={}
    for p in places:
        for name in (p['id'],p['name']):aliases.setdefault(normalized(name),set()).add(p['id'])
    for scene in data.get('scenes',[]):
        refs=scene.get('focus',[])
        if not isinstance(refs,list):continue
        scene['focus']=[next(iter(aliases[normalized(ref)])) if isinstance(ref,str) and ref not in ids and len(aliases.get(normalized(ref),set()))==1 else ref for ref in refs]
    return data
