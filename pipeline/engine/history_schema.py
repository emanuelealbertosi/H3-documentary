"""Version 2 editorial document -> version 1 render/TTS contract (legacy unchanged)."""
import copy,math,re
from pathlib import PurePosixPath
from .history_profiles import PROFILES,SCENE_TYPES,MOVEMENTS,EVENT_TYPES,choose_scene
from .history_contract import normalize_document,validate_cue_records

def year_label(year):
    year=int(round(year))
    return f'{abs(year)} a.C.' if year<0 else f'{max(1,year)} d.C.'

def historical_value(year):
    if year==0:raise ValueError('Usare anni storici senza anno zero: -1 = 1 a.C., 1 = 1 d.C.')
    return year+1 if year<0 else year

def interpolate_year(a,b,q,*,calendar=False):
    v=historical_value(a)+(historical_value(b)-historical_value(a))*max(0,min(1,q))
    n=math.floor(v) if calendar else round(v)
    return n-1 if n<=0 else n

def position(p):
    if len(p)!=2 or not all(isinstance(x,(int,float)) and math.isfinite(x) for x in p) or not(-180<=p[0]<=180 and -79<=p[1]<=79):raise ValueError('Coordinate lon/lat non valide')

def fit(points):
    if not points:return [15,43,60]
    def merc(lat):return math.degrees(math.asinh(math.tan(math.radians(lat))))
    xs=[p[0] for p in points];ys=[merc(p[1]) for p in points]
    width=max(6,(max(xs)-min(xs))*1.65,(max(ys)-min(ys))*16/9*1.8)
    if width>170:raise ValueError('Suddividere la carta: teatro troppo ampio per la proiezione Mercatore.')
    return [(max(xs)+min(xs))/2,math.degrees(math.atan(math.sinh(math.radians((max(ys)+min(ys))/2)))),width]

def validate_document(doc):
    doc=normalize_document(doc)
    if doc.get('schema_version')!=2:raise ValueError('Schema storico atteso: 2')
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,79}',doc.get('slug','')):raise ValueError('Slug non valido')
    kind=doc.get('documentary_type','general_history')
    if kind not in PROFILES:raise ValueError('Tipo di documentario sconosciuto')
    sources={s['id'] for s in doc.get('sources',[])}
    from .research_provenance import uses_model_knowledge
    hybrid=uses_model_knowledge(doc)
    if (not sources and not hybrid) or len(sources)!=len(doc.get('sources',[])):raise ValueError('Fonti mancanti o duplicate')
    def refs(item,required=False):
        references=item.get('sources',[])
        if ((required or not hybrid) and not references) or not set(references)<=sources:raise ValueError('Fonte mancante o sconosciuta: '+str(item.get('id',item.get('label',''))))
    for collection in ['locations','persons','entities','events','visual_assets','visual_layers']:
        rows=doc.get(collection,[])
        if len({r['id'] for r in rows})!=len(rows):raise ValueError('ID duplicati: '+collection)
        if any(not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}',r['id']) for r in rows):raise ValueError('Identificatore non sicuro: '+collection)
    locations={r['id'] for r in doc.get('locations',[])};people={r['id'] for r in doc.get('persons',[])};events={r['id'] for r in doc.get('events',[])};assets={r['id'] for r in doc.get('visual_assets',[])}
    layers={r['id'] for r in doc.get('visual_layers',[])}
    for loc in doc.get('locations',[]):position(loc['pos'])
    for ev in doc.get('events',[]):
        refs(ev);historical_value(ev['year'])
        if ev.get('type','political_event') not in EVENT_TYPES:raise ValueError('Tipo evento sconosciuto')
        if ev.get('location_id') and ev['location_id'] not in locations:raise ValueError('Luogo evento sconosciuto')
        if ev.get('certainty','established') not in ('established','estimate','interpretation','controversial'):raise ValueError('Stato delle evidenze sconosciuto')
    for layer in doc.get('visual_layers',[]):
        refs(layer)
        if layer.get('kind') in ('territory','influence','cultural','linguistic','religious','alliance','contested'):
            from .history_territories import modern_areas
            if modern_areas(doc):
                if not isinstance(layer.get('label'),str) or not layer['label'].strip():raise ValueError('Area senza nome leggibile')
                if not isinstance(layer.get('schematic',True),bool):raise ValueError('schematic deve essere un booleano')
                if layer.get('schematic') is False and not layer.get('geometry_source'):raise ValueError('Un confine documentato richiede geometry_source con provenienza dei dati geografici; coordinate illustrative: schematic=true')
                duration=layer.get('transition_years',0)
                if isinstance(duration,bool) or not isinstance(duration,(int,float)) or not math.isfinite(duration) or duration<0:raise ValueError('transition_years deve essere un numero finito non negativo')
                if layer.get('label_pos') is not None:position(layer['label_pos'])
                years=[state.get('at',historical_value(state['year'])) for state in layer.get('states',[])]
                if len(set(years))!=len(years):raise ValueError('Stati territoriali duplicati nello stesso anno')
                for row in [layer,*layer.get('states',[])]:
                    if 'color' in row and (not isinstance(row['color'],(list,tuple)) or len(row['color'])!=3 or any(isinstance(x,bool) or not isinstance(x,int) or not 0<=x<=255 for x in row['color'])):raise ValueError('Colore territoriale RGB non valido')
            for state in layer.get('states',[]):
                historical_value(state['year'])
                if 'at' in state:
                    at=state['at'];base=historical_value(state['year']);until=state.get('valid_until')
                    if isinstance(at,bool) or not isinstance(at,(int,float)) or not math.isfinite(at) or not base<=at<base+1:raise ValueError('Data geografica at incoerente con year')
                    if not isinstance(until,(int,float)) or not math.isfinite(until) or until<=at:raise ValueError('Intervallo geografico valid_until non valido')
                holes=state.get('polygon_holes',[])
                if holes and len(holes)!=len(state.get('polygons',[])):raise ValueError('Anelli interni dei territori non coerenti')
                for group in holes:
                    for ring in group:
                        if len(ring)<4 or ring[0]!=ring[-1]:raise ValueError('Anello interno non chiuso')
                        for p in ring:position(p)
                for polygon in state.get('polygons',[]):
                    if len(polygon)<3:raise ValueError('Poligono incompleto')
                    for p in polygon:position(p)
    scenes=doc.get('scenes',[])
    if not scenes or len({s['id'] for s in scenes})!=len(scenes):raise ValueError('Scene mancanti o duplicate')
    for s in scenes:
        if not re.fullmatch(r'\d{2,3}',s['id']):raise ValueError('ID scena numerico a 2/3 cifre richiesto dal motore audio')
        refs(s)
        if s.get('scene_type') and s['scene_type'] not in SCENE_TYPES:raise ValueError('Tipo scena sconosciuto')
        if not s.get('lines') or any(not str(l).strip() for l in s['lines']):raise ValueError('Narrazione mancante')
        validate_cue_records(s)
        for key,valid in [('location_ids',locations),('person_ids',people),('event_ids',events),('asset_ids',assets),('territory_ids',layers)]:
            if not set(s.get(key,[]))<=valid:raise ValueError('Riferimenti sconosciuti: '+key)
        for y in s.get('historical_range',[s.get('year',1)]):historical_value(y)
        for m in s.get('movements',[]):
            refs(m)
            if m.get('semantic',PROFILES[kind].movement) not in MOVEMENTS:raise ValueError('Semantica movimento sconosciuta')
            if len(m.get('points',[]))<2:raise ValueError('Movimento senza percorso')
            for p in m['points']:position(p)
        for node in s.get('network',{}).get('nodes',[]):
            if node['location_id'] not in locations:raise ValueError('Nodo senza luogo')
        for edge in s.get('network',{}).get('edges',[]):
            refs(edge)
            if edge.get('from') not in locations or edge.get('to') not in locations:raise ValueError('Collegamento senza nodo')
            if edge.get('semantic','connection') not in MOVEMENTS:raise ValueError('Semantica della rete sconosciuta')
            for p in edge.get('points',[]):position(p)
        if s.get('chart'):
            refs(s['chart'],required=True)
            if s['chart']['kind'] not in ('bar','line','comparison'):raise ValueError('Grafico sconosciuto')
            for row in s['chart']['values']:
                if row.get('value') is None or not math.isfinite(row['value']):raise ValueError('Non inventare quantità mancanti')
        if s.get('quote') and not s['quote'].get('source'):raise ValueError('Citazione senza provenienza')
        if hybrid and s.get('quote'):refs(s,required=True)
        for item in s.get('movements',[])+s.get('network',{}).get('edges',[]):
            if not 0<=item.get('cue',0)<len(s['lines']):raise ValueError('Cue fuori intervallo')
    from .history_direction import require_coverage
    require_coverage(doc)
    for a in doc.get('visual_assets',[]):
        if not a.get('source') or not a.get('license'):raise ValueError('Materiale privo di provenienza o licenza')
    for path in [a['path'] for a in doc.get('visual_assets',[]) if a.get('path')]+[p['portrait'] for p in doc.get('persons',[]) if p.get('portrait')]:
        normalized=path.replace('\\','/');parts=PurePosixPath(normalized).parts
        if not normalized.startswith('assets/') or '..' in parts or ':' in normalized:raise ValueError('Gli asset devono essere percorsi relativi dentro assets/')
    return doc

def adapt(doc):
    if doc.get('schema_version')!=2:return doc
    doc=normalize_document(doc)
    validate_document(doc);d=copy.deepcopy(doc);kind=d.get('documentary_type','general_history');d['documentary_type']=kind
    period=d.get('historical_period')
    if isinstance(period,(list,tuple)) and len(period)==2:
        d['historical_period']={'start':period[0],'end':period[1]}
    d['documentary_schema_version']=2;d['schema_version']=1;d['visual_style']='history'
    d['documentary']={'type':kind,'title':d['title'],'slug':d['slug']};d.setdefault('metadata',{})
    for k,v in dict(language='it',width=1920,height=1080,fps=24,target_minutes=5,short_title=d['title'][:35],subtitle=PROFILES[kind].label,display_date='',description=d['title'],editorial_notes=[],pronunciation={},assets=[],extra_credits='Natural Earth: pubblico dominio. Cartografia fisica moderna. Rilievo Mapzen / Copernicus: attribuzioni in assets/geography/terrain-attribution.md.',voice_engine='kokoro',voice='assets/voice/kokoro/kokoro-v1.0.onnx',voice_styles='assets/voice/kokoro/voices-v1.0.bin',voice_speaker='if_sara',voice_credit='Kokoro 82M / if_sara, sintesi italiana locale. Pesi Apache-2.0.').items():d.setdefault(k,v)
    d.setdefault('min_minutes',d['target_minutes']*.88);d.setdefault('max_minutes',d['target_minutes']*1.12)
    d.setdefault('output',f'output/{d["slug"]}_documentario_1080p.mp4');d.setdefault('verification_dir',d['slug']+'_verification')
    d.setdefault('atlas','assets/geography/atlas-v2/atlas.json')
    d['places']={p['id']:{**p,'size':p.get('size',23)} for p in d.get('locations',[])}
    d['commanders']={p['id']:{**p,'subtitle':p.get('role',''),'side':'neutral','portrait_note':[p.get('role',''),p.get('period','')]} for p in d.get('persons',[]) if p.get('portrait')}
    d['factions']=[{**e,'label':e.get('name',e['id']),'color':e.get('color',[239,185,93]),'estimate':e.get('estimate',''),'commander':''} for e in d.get('entities',[])]
    d['maps']={'campaign':dict(center=[15,43],scale=[100,100],seed=41,landmarks=[],roads=[],rivers=[],ridges=[],forests=[],zones=[])}
    slides=d.get('presentation_mode')=='slides'
    if slides:d['extra_credits']=doc.get('extra_credits','Slide senza mappa. Provenienza delle immagini nelle rispettive attribuzioni.')
    overview=d['overview'] if d.get('overview') else [12,43,45] if slides else fit([p['pos'] for p in d.get('locations',[])]);d['atlas_locator']=overview
    previous=overview
    for i,s in enumerate(d['scenes']):
        s['scene_type']=choose_scene(s,kind,i)
        if 'historical_range' not in s:s['historical_range']=[s.get('year',1)]*2
        s.setdefault('date',year_label(s['historical_range'][0]));s.setdefault('kicker',PROFILES[kind].label)
        s.setdefault('facts',[s.get('note',s['title'])]);s.setdefault('note','');s['map']='campaign'
        from .history_territories import modern_areas,scene_area_points,area_view
        area_points=scene_area_points(d,s) if modern_areas(d) else []
        points=[d['places'][p]['pos'] for p in s.get('location_ids',[])]+area_points
        view=previous if slides else s['camera_end'] if s.get('camera_end') else area_view(points) if area_points else fit(points)
        s.setdefault('camera_start',previous);s.setdefault('camera_end',view)
        s.setdefault('camera_keys',[{'at':0,'view':s['camera_start']},{'at':.30,'view':view},{'at':1,'view':view}]);previous=view
        s.setdefault('visible_places',s.get('location_ids',[]));s.setdefault('label_offsets',{})
        for key in ['units','arrows','sfx','focus','commanders','routes']:s.setdefault(key,[])
        for m in s.get('movements',[]):m.setdefault('semantic',PROFILES[kind].movement)
    d.setdefault('voice_sentence_chunks',[f'{s["id"]}:{i}' for s in d['scenes'] for i in range(len(s['lines']))])
    return d

def enrich_timeline(timeline,estimated=False):
    if timeline.get('documentary_schema_version')!=2:return timeline
    timeline['timing_status']='estimated' if estimated else 'measured_tts'
    by_id={s['id']:s for s in timeline['scenes']}
    for event in timeline.get('events',[]):
        sid=event.get('scene_id')
        if sid not in by_id:sid=next((s['id'] for s in timeline['scenes'] if event['id'] in s.get('event_ids',[])),None)
        if sid is None:
            sid=next((s['id'] for s in timeline['scenes'] if min(s['historical_range'])<=event['year']<=max(s['historical_range'])),None)
        if sid:
            s=by_id[sid];cue=s['cues'][min(event.get('cue',0),len(s['cues'])-1)]
            event['timestamp_video']=round(s['start']+cue['start'],6)
            event['scene_id']=sid
        event.setdefault('data_storica',year_label(event['year']))
    timeline['narration']=[{'scene_id':s['id'],'start':s['start'],'end':s['end'],'cues':s['cues']} for s in timeline['scenes']]
    return timeline

def estimate_timeline(pack):
    d=copy.deepcopy(adapt(pack));cursor=0
    for s in d['scenes']:
        offset=.65;s['cues']=[]
        for i,line in enumerate(s['lines']):
            duration=len(line.split())/(170/60)
            s['cues'].append(dict(index=i,start=offset,end=offset+duration,text=line,spoken=line));offset+=duration+.18
        duration=math.ceil((offset+.85)*d['fps'])/d['fps']
        s.update(start=cursor,end=cursor+duration,duration=duration,frames=round(duration*d['fps']));cursor+=duration
    d['duration']=cursor;return enrich_timeline(d,estimated=True)
