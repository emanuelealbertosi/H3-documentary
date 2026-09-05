"""Lossless shape repairs. Never fabricate a place or choose a fuzzy geographic match."""
import copy,hashlib,re,unicodedata

COLLECTIONS=('places','persons','commanders','entities','events','visual_layers','visual_assets')
SPECIAL_ID_CHARS=str.maketrans({'ı':'i','ł':'l','đ':'d','ð':'d','þ':'th','æ':'ae','œ':'oe','ß':'ss'})

def technical_id(value):
    """Turn a model-written label into a stable machine ID; visible names stay intact."""
    original=str(value).strip();folded=unicodedata.normalize('NFKD',original.casefold()).translate(SPECIAL_ID_CHARS)
    ascii_value=''.join(c for c in folded if not unicodedata.combining(c)).encode('ascii','ignore').decode()
    result=re.sub(r'[^a-z0-9_-]+','-',ascii_value).strip('-_')[:50]
    return result or 'id-'+hashlib.sha256(original.encode()).hexdigest()[:12]

def collections(value):
    if not isinstance(value,dict):return value
    data=copy.deepcopy(value)
    for key in COLLECTIONS:
        rows=data.get(key)
        if isinstance(rows,dict) and all(isinstance(v,dict) for v in rows.values()):
            data[key]=[{'id':k,**v} for k,v in rows.items()]
            rows=data[key]
        if isinstance(rows,list):
            for row in rows:
                if isinstance(row,dict) and isinstance(row.get('id'),str):row['id']=technical_id(row['id'])
    for scene in data.get('scenes',[]) if isinstance(data.get('scenes',[]),list) else []:
        rows=scene.get('movements') if isinstance(scene,dict) else None
        if isinstance(rows,dict) and all(isinstance(v,dict) for v in rows.values()):scene['movements']=list(rows.values())
    return data

def normalized(value):
    text=unicodedata.normalize('NFKD',str(value)).casefold().translate(SPECIAL_ID_CHARS)
    return ''.join(c for c in text if not unicodedata.combining(c)).strip()

def named_references(data,places,field):
    data=copy.deepcopy(data);ids={p['id'] for p in places};aliases={}
    for p in places:
        for name in (p['id'],p['name']):aliases.setdefault(normalized(name),set()).add(p['id'])
    for scene in data.get('scenes',[]):
        refs=scene.get(field,[])
        if not isinstance(refs,list):continue
        scene[field]=[next(iter(aliases[normalized(ref)])) if isinstance(ref,str) and ref not in ids and len(aliases.get(normalized(ref),set()))==1 else ref for ref in refs]
    return data


def place_references(data,places):return named_references(data,places,'focus')


def battle_references(data):
    data=collections(data)
    if not isinstance(data,dict):return data
    for key,field in [('places','focus'),('commanders','commander_ids')]:
        rows=data.get(key,[])
        if isinstance(rows,list) and all(isinstance(r,dict) and 'id' in r and 'name' in r for r in rows):
            data=named_references(data,rows,field)
    return data


def movement_endpoints(data,places):
    """Convert exact catalog endpoints into coordinates; never geocode or guess."""
    data=copy.deepcopy(data);positions={p['id']:p['pos'] for p in places}
    for scene in data.get('scenes',[]):
        for movement in scene.get('movements',[]):
            if (not movement.get('points') and isinstance(movement.get('from'),str) and isinstance(movement.get('to'),str)
                    and movement['from'] in positions and movement['to'] in positions):
                movement['points']=[positions[movement['from']],positions[movement['to']]]
    return data
