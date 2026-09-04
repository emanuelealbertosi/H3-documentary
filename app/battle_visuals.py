"""Recover geographic and visual direction when a compact model omits battle motion."""
import copy,math,re,time,unicodedata,statistics
from pathlib import Path
import requests
from pydantic import BaseModel,Field,model_validator
from typing import Literal
from .llm import ModelError
from .store import read_json,write_json


MOVE_WORDS=re.compile(r"\b(attacc|assalt|avanz|caric|marci|ritirat|ripieg|insegu|fug|converg|arriv|attravers|invad|sfond|circond|spost|incalz|disgreg)",re.I)
RETREAT_WORDS=re.compile(r"\b(ritirat|ripieg|fug|disgreg|arretr)",re.I)
ALLY_WORDS=re.compile(r"\b(prussian|prussiani|alleat|wellington|bl[uü]cher|coalizion)",re.I)


class BattleMove(BaseModel):
    side:Literal['a','b']
    kind:Literal['attack','advance','retreat','reinforcement','march']='advance'
    label:str=Field(min_length=2,max_length=34)
    unit_kind:Literal['infantry','cavalry','artillery']='infantry'
    from_place:str|None=None
    to_place:str
    approach:Literal['north','north_east','east','south_east','south','south_west','west','north_west']|None=None
    @model_validator(mode='after')
    def endpoints(self):
        if self.from_place==self.to_place:raise ValueError('Origine e destinazione devono essere diverse.')
        if not self.from_place and not self.approach:raise ValueError('Senza from_place indica approach.')
        return self


class BattleVisualScene(BaseModel):
    index:int=Field(ge=0,le=119)
    moves:list[BattleMove]=Field(default_factory=list,max_length=4)


class BattleVisualBatch(BaseModel):
    scenes:list[BattleVisualScene]=Field(min_length=1,max_length=2)


def _normal(value):
    value=''.join(c for c in unicodedata.normalize('NFKD',str(value)).casefold() if not unicodedata.combining(c))
    return ' '.join(re.findall(r'[a-z0-9]+',value))


def _query_name(name):
    words=_normal(name).split()
    while words and words[0] in {'ferme','farm','fattoria','battle','battaglia','city','citta'}:words.pop(0)
    if words and words[0] in {'de','del','della','of'}:words.pop(0)
    return ' '.join(words)


def _distance(a,b):
    lat=math.radians((a[1]+b[1])/2)
    return math.hypot((a[0]-b[0])*111.32*math.cos(lat),(a[1]-b[1])*111.32)


def verify_place_coordinates(outline,checkpoint,log,session=None,pause=time.sleep):
    """Check at most twelve named places with cached, rate-limited Nominatim searches."""
    data=copy.deepcopy(outline);path=Path(checkpoint)/'battle-geocoding.json'
    if path.exists():records=read_json(path)
    else:
        used={p['id']:0 for p in data['places']}
        for scene in data['scenes']:
            for ident in scene.get('focus',[]):used[ident]=used.get(ident,0)+1
        selected=sorted(data['places'],key=lambda p:(-used.get(p['id'],0),p['id']))[:12]
        # A median is deliberately used here: one malformed model coordinate must
        # not drag the search window away from the battle theatre.
        center=[statistics.median(p['pos'][0] for p in data['places']),statistics.median(p['pos'][1] for p in data['places'])]
        max_shift_km=80.0
        own=session or requests.Session();own.headers.update({'User-Agent':'H3-documentary/1.1 (+https://github.com/emanuelealbertosi/H3-documentary)'})
        records=[]
        for number,place in enumerate(selected):
            try:
                response=own.get('https://nominatim.openstreetmap.org/search',params={'q':place['name'],'format':'jsonv2','limit':5,'accept-language':'it',
                    'viewbox':f'{center[0]-2.5},{center[1]+1.8},{center[0]+2.5},{center[1]-1.8}'},timeout=(8,18))
                response.raise_for_status();matches=[];needle=_query_name(place['name'])
                for item in response.json():
                    candidate=[float(item['lon']),float(item['lat'])]
                    if needle and needle not in _normal(item.get('display_name','')):continue
                    # Nominatim often returns a same-named village in another
                    # country. It is safer to retain the model's explicitly
                    # uncertain point than to accept a result far outside the
                    # declared local theatre.
                    if _distance(center,candidate)>300 or _distance(place['pos'],candidate)>max_shift_km:continue
                    matches.append((round(_distance(place['pos'],candidate),3),candidate,item.get('display_name','')))
                matches.sort(key=lambda row:row[0])
                chosen=matches[0] if matches else None
                records.append({'id':place['id'],'query':place['name'],'old':place['pos'],'pos':chosen[1] if chosen else None,'display_name':chosen[2] if chosen else '','provider':'OpenStreetMap Nominatim'})
            except (requests.RequestException,ValueError,KeyError,TypeError) as error:
                records.append({'id':place['id'],'query':place['name'],'old':place['pos'],'pos':None,'error':type(error).__name__,'provider':'OpenStreetMap Nominatim'})
                # A network failure is normally common to every request; retain model data.
                if isinstance(error,requests.RequestException):break
            if number<len(selected)-1:pause(1.05)
        write_json(path,records)
    # Revalidate cached responses as well. This repairs projects created by
    # earlier releases without forcing a second network request.
    changes={r['id']:r['pos'] for r in records if r.get('pos') and r.get('old') and _distance(r['old'],r['pos'])<=80.0}
    rejected=sum(1 for r in records if r.get('pos') and r['id'] not in changes)
    old={p['id']:list(p['pos']) for p in data['places']}
    for place in data['places']:
        if place['id'] not in changes:continue
        place['pos']=changes[place['id']]
        note=place.get('note','').rstrip()
        place['note']=(note+' Posizione ricontrollata con OpenStreetMap/Nominatim.').strip()
    replacements={tuple(old[k]):tuple(v) for k,v in changes.items()}
    for scene in data['scenes']:
        for route in scene.get('routes',[]):
            route['points']=[list(replacements.get(tuple(point),tuple(point))) for point in route['points']]
    if changes:log(f'Geografia: {len(changes)} coordinate di località ricontrollate con OpenStreetMap/Nominatim.')
    else:log('Geografia: servizio di verifica non disponibile; conservo le coordinate dichiarate come illustrative.')
    if rejected:log(f'Geografia: {rejected} risultati omonimi lontani scartati; mantengo le coordinate locali dichiarate.')
    return data


def _movement_required(scene):return bool(MOVE_WORDS.search(scene.get('event','')+' '+scene.get('title','')))


def _fallback(scene,outline):
    if not scene.get('focus'):return []
    text=scene.get('event','')+' '+scene.get('title','');retreat=bool(RETREAT_WORDS.search(text))
    side='b' if ALLY_WORDS.search(text) and not re.search(r'frances|napoleon',text,re.I) else 'a'
    target=scene['focus'][0];origin=scene['focus'][1] if retreat and len(scene['focus'])>1 else None
    direction='east' if re.search(r'prussian|bl[uü]cher',text,re.I) and not origin else 'south'
    kind='retreat' if retreat else 'reinforcement' if re.search(r'arriv|rinforz|converg',text,re.I) else 'attack' if re.search(r'attacc|assalt|caric|sfond',text,re.I) else 'advance'
    unit='cavalry' if re.search(r'cavall|cavalry',text,re.I) else 'artillery' if re.search(r'artiglier|cannon',text,re.I) else 'infantry'
    return [{'side':side,'kind':kind,'label':outline['factions'][0 if side=='a' else 1][:30],'unit_kind':unit,'from_place':origin,'to_place':target,'approach':None if origin else direction}]


def _route(move,positions,scene,index):
    end=list(positions[move['to_place']])
    if move.get('from_place'):start=list(positions[move['from_place']])
    else:
        dirs={'north':(0,1),'north_east':(1,1),'east':(1,0),'south_east':(1,-1),'south':(0,-1),'south_west':(-1,-1),'west':(-1,0),'north_west':(-1,1)}
        dx,dy=dirs[move['approach']]
        local=[positions[x] for x in scene.get('focus',[]) if x in positions]
        extent=max([abs(a[0]-b[0]) for a in local for b in local]+[.018])
        lon_step=max(.014,min(.07,extent*.65))*(1+index*.16);lat_step=lon_step*.62
        start=[end[0]+dx*lon_step,end[1]+dy*lat_step]
    return {'side':move['side'],'points':[start,end],'uncertain':True,'kind':move['kind'],'label':move['label'],'unit_kind':move['unit_kind']}


def enrich_battle_outline(llm,system,outline,checkpoint,log,cancel):
    """Add a small semantic movement plan and convert it to geographic routes."""
    cp=Path(checkpoint);data=verify_place_coordinates(outline,cp,log)
    final=cp/'battle-visuals.json';progress=cp/'battle-visual-progress.json'
    selected=[i for i,s in enumerate(data['scenes']) if _movement_required(s) or s.get('routes')]
    if final.exists():plans=read_json(final)
    else:
        plans=read_json(progress) if progress.exists() else []
        if [row.get('index') for row in plans]!=selected[:len(plans)]:plans=[]
        positions={p['id']:p['pos'] for p in data['places']};place_rows=[{'id':p['id'],'name':p['name'],'pos':p['pos']} for p in data['places']]
        while len(plans)<len(selected):
            cancel();batch_indices=selected[len(plans):len(plans)+2]
            rows=[{'index':i,'title':data['scenes'][i]['title'],'event':data['scenes'][i]['event'],'focus':data['scenes'][i]['focus']} for i in batch_indices]
            prompt='''Progetta SOLO i movimenti visivi delle scene assegnate per una mappa storica animata. Usa esclusivamente gli ID di luogo del catalogo. Ogni attacco, avanzata, ritirata o arrivo deve avere 1–3 moves; [] è ammesso solo se la scena non descrive movimento. side a è la prima fazione, side b la seconda. from_place è un luogo di partenza noto; se manca, usa approach per indicare da quale bordo entra la forza. Non inventare coordinate: saranno calcolate dal programma. kind descrive il significato della freccia, label è il nome breve della forza, unit_kind il simbolo. Mantieni gli indici esatti.\nFAZIONI:\n'''+str(data['factions'])+'\nLUOGHI:\n'+str(place_rows)+'\nSCENE:\n'+str(rows)
            def validate(value):
                result=sorted(value['scenes'],key=lambda x:x['index'])
                if [x['index'] for x in result]!=batch_indices:raise ValueError(f'Restituisci esattamente gli indici {batch_indices}.')
                for row in result:
                    scene=data['scenes'][row['index']]
                    if _movement_required(scene) and not row['moves']:raise ValueError(f"La scena {row['index']} descrive un movimento: aggiungi almeno una freccia semantica.")
                    for move in row['moves']:
                        if move['to_place'] not in positions or move.get('from_place') and move['from_place'] not in positions:raise ValueError('Usa soltanto ID del catalogo luoghi.')
                return result
            try:
                result=llm.structured(system,prompt,BattleVisualBatch,validator=validate)
            except ModelError:
                result=[{'index':i,'moves':_fallback(data['scenes'][i],data)} for i in batch_indices]
                log(f'Movimenti: il modello non ha completato le scene {batch_indices}; applico frecce illustrative conservative.')
            plans.extend(result);write_json(progress,plans);log(f'Movimenti visuali: {len(plans)} / {len(selected)} scene.')
        write_json(final,plans)
    by_index={row['index']:row['moves'] for row in plans};positions={p['id']:p['pos'] for p in data['places']}
    for i,scene in enumerate(data['scenes']):
        if i in by_index:scene['routes']=[_route(move,positions,scene,j) for j,move in enumerate(by_index[i])]
    write_json(cp/'outline.json',data)
    return data
