"""Deterministically ground named map points in the user's frozen documents."""
import copy,math,re,unicodedata
from pathlib import Path
from .store import read_json

COORDINATE=re.compile(r'(?<![\d.])([-+]?\d{1,3}(?:[.,]\d{3,}))\s*(?:[,;]|\|)\s*([-+]?\d{1,3}(?:[.,]\d{3,}))(?![\d.])')
GENERIC={'baia','capo','citta','fiume','isola','isole','lago','mare','monte','monti','porto','regione','sito','valle',
         'del','della','delle','dei','degli','di','in','la','le','il','lo','gli'}


def _normal(value):
    value=unicodedata.normalize('NFKD',str(value)).encode('ascii','ignore').decode().casefold()
    return re.sub(r'[^a-z0-9]+',' ',value).strip()


def _distance(a,b):
    lat=math.radians((a[1]+b[1])/2)
    return math.hypot((a[0]-b[0])*111.32*math.cos(lat),(a[1]-b[1])*111.32)


def _documents(workspace):
    root=Path(workspace)/'assets/documents'
    if not root.is_dir():return []
    values=[]
    for folder in sorted(root.iterdir()):
        if not folder.is_dir():continue
        record=folder/'record.json';chunks=folder/'chunks.json'
        if not record.is_file() or not chunks.is_file():continue
        item=read_json(record);original=folder/item.get('original','')
        text=''
        if original.suffix.casefold() in ('.md','.txt','.csv','.tsv','.json','.html','.htm'):
            try:text=original.read_text(encoding='utf-8',errors='replace')
            except OSError:text=''
        if not text:
            text='\n'.join(str(row.get('text','')) for row in read_json(chunks))
        if text.strip():values.append((item.get('title') or item.get('filename') or folder.name,text))
    return values


def _aliases(place):
    full=_normal(place.get('name',''));tokens=[x for x in full.split() if len(x)>=4 and x not in GENERIC]
    ident=[x for x in _normal(place.get('id','')).split() if len(x)>=4 and x not in GENERIC]
    values=[full,*tokens,*ident]
    return list(dict.fromkeys(x for x in values if len(x)>=4))


def _orientation(text):
    value=_normal(text)
    if re.search(r'latitudine(?:\s+decimale)?.{0,100}longitudine',value,re.S):return 'latlon'
    if re.search(r'longitudine(?:\s+decimale)?.{0,100}latitudine',value,re.S):return 'lonlat'
    return ''


def _position(match,order,current):
    first=float(match.group(1).replace(',','.'));second=float(match.group(2).replace(',','.'))
    candidates=[]
    if -179<=first<=179 and -78<=second<=78:candidates.append([first,second])
    if -179<=second<=179 and -78<=first<=78:candidates.append([second,first])
    if not candidates:return None
    if order=='latlon' and -78<=first<=78 and -179<=second<=179:return [second,first]
    if order=='lonlat' and -179<=first<=179 and -78<=second<=78:return [first,second]
    return min(candidates,key=lambda point:_distance(current,point))


def _candidate(place,documents):
    aliases=_aliases(place);current=list(place['pos']);rows=[]
    for title,text in documents:
        order=_orientation(text)
        for line in text.splitlines():
            normalized=_normal(line)
            hits=[(normalized.find(alias),alias) for alias in aliases if alias in normalized]
            if not hits:continue
            at,alias=max(hits,key=lambda item:len(item[1]))
            exact=aliases[0] in normalized
            matches=list(COORDINATE.finditer(line))
            for number,match in enumerate(matches):
                point=_position(match,order,current)
                if point is None:continue
                score=55+min(35,len(alias)*2)+(25 if exact else 0)+(18 if 'punto cartografico' in normalized else 0)
                score-=min(28,abs(match.start()-at)/18)+number*7
                rows.append({'pos':point,'score':score,'source':title})
    if not rows:return None
    clusters=[]
    for row in sorted(rows,key=lambda item:item['score'],reverse=True):
        cluster=next((item for item in clusters if _distance(item['pos'],row['pos'])<=25),None)
        if cluster:
            cluster['rows'].append(row)
            if row['score']>cluster['best']['score']:cluster['best']=row;cluster['pos']=row['pos']
        else:clusters.append({'pos':row['pos'],'best':row,'rows':[row]})
    for cluster in clusters:cluster['rank']=cluster['best']['score']+min(5,len(cluster['rows']))*9
    clusters.sort(key=lambda item:item['rank'],reverse=True);best=clusters[0]
    if len(clusters)>1 and best['rank']-clusters[1]['rank']<10 and _distance(best['pos'],clusters[1]['pos'])>80:return None
    return {'pos':[round(x,6) for x in best['pos']],'source':best['best']['source'],'matches':len(best['rows'])}


def _fit(points):
    if not points:return [15,43,60]
    def merc(lat):return math.degrees(math.asinh(math.tan(math.radians(lat))))
    xs=[p[0] for p in points];ys=[merc(p[1]) for p in points]
    width=max(6,(max(xs)-min(xs))*1.65,(max(ys)-min(ys))*16/9*1.8)
    return [(max(xs)+min(xs))/2,math.degrees(math.atan(math.sinh(math.radians((max(ys)+min(ys))/2)))),width]


def _refresh_views(document):
    locations=document.get('locations',document.get('places',[]))
    if not isinstance(locations,list) or not locations:return
    positions={item['id']:item['pos'] for item in locations}
    overview=_fit(list(positions.values()));document['overview']=overview;previous=overview
    for scene in document.get('scenes',[]):
        ids=scene.get('location_ids',scene.get('focus',[]))
        points=[positions[ident] for ident in ids if ident in positions]
        points += [point for movement in scene.get('movements',[]) for point in movement.get('points',[])]
        view=_fit(points) if points else previous
        scene['camera_start']=previous;scene['camera_end']=view
        scene['camera_keys']=[{'at':0,'view':previous},{'at':.30,'view':view},{'at':1,'view':view}]
        previous=view


def ground_coordinates(document,workspace):
    """Return a copy plus high-confidence coordinate changes found in full local documents."""
    result=copy.deepcopy(document);documents=_documents(workspace)
    locations=result.get('locations',result.get('places',[]))
    if not documents or not isinstance(locations,list):return result,[]
    changes=[];replacements={}
    for place in locations:
        candidate=_candidate(place,documents)
        if not candidate or _distance(place['pos'],candidate['pos'])<1:continue
        old=list(place['pos']);place['pos']=candidate['pos'];replacements[tuple(old)]=tuple(candidate['pos'])
        note=str(place.get('note','')).rstrip()
        place['note']=(note+f" Coordinate ricontrollate nel documento locale «{candidate['source']}».").strip()
        changes.append({'id':place['id'],'name':place['name'],'old':old,**candidate})
    if not changes:return result,[]
    for scene in result.get('scenes',[]):
        for movement in scene.get('movements',[]):
            movement['points']=[list(replacements.get(tuple(point),tuple(point))) for point in movement.get('points',[])]
        for edge in scene.get('network',{}).get('edges',[]):
            edge['points']=[list(replacements.get(tuple(point),tuple(point))) for point in edge.get('points',[])]
    _refresh_views(result)
    return result,changes
