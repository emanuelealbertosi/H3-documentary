"""Deterministic adapter: validated narrative data -> the reusable atlas engine."""
import math,copy,re
from pathlib import Path
from .models import Outline
from .store import write_json
CREDIT="Cartografia Natural Earth (pubblico dominio). Rilievo Mapzen Terrain Tiles: Europe terrain data produced using Copernicus data and information funded by the European Union - EU-DEM layers; USGS GMTED2010/SRTM; NOAA ETOPO1. https://www.naturalearthdata.com/about/terms-of-use/ ; https://registry.opendata.aws/terrain-tiles/"
def merc(y):return math.degrees(math.asinh(math.tan(math.radians(y))))
def invmerc(y):return math.degrees(math.atan(math.sinh(math.radians(y))))
def fit(points,pad=1.8,min_width=2.2):
    xs=[p[0] for p in points];ys=[merc(p[1]) for p in points]
    width=max(min_width,(max(xs)-min(xs))*pad,(max(ys)-min(ys))*16/9*pad)
    if width>160:raise ValueError("Teatro geografico troppo ampio o attraversamento della linea del cambio data: restringi il tema.")
    return [(min(xs)+max(xs))/2,invmerc((min(ys)+max(ys))/2),width]
def bounds_for_views(views):
    w=min(x-z*.56 for x,y,z in views);e=max(x+z*.56 for x,y,z in views)
    south=min(invmerc(merc(y)-z*9/16*.57) for x,y,z in views)
    north=max(invmerc(merc(y)+z*9/16*.57) for x,y,z in views)
    if not(-180<w<e<180 and -80<south<north<80):raise ValueError("L'inquadratura supera i limiti geografici supportati.")
    return [w,south,e,north]
def commander_side(commander):
    text=(commander.get('name','')+' '+commander.get('role','')).casefold()
    return 'b' if re.search(r'wellington|bl[uü]cher|prussian|prussian|coalizion|anglo|alleat',text) else 'a'
def static_pos(view,side):
    # Stable opposing offsets inside the camera; these indicate formations, not exact coordinates.
    direction=-1 if side=='a' else 1
    return [view[0]+direction*view[2]*.10,view[1]+direction*view[2]*.035]
def source_method(sources):
    local=any(s.get('origin')=='local_document' for s in sources)
    web=any(s.get('origin')!='local_document' for s in sources)
    origin=('documenti locali selezionati e pagine web consultate' if local and web else
            'documenti locali selezionati' if local else
            'pagine web consultate' if web else 'nessuna fonte esterna consultabile')
    retrieval=' I passaggi locali sono scelti con ricerca ibrida.' if local else ''
    return f'Fonti: {origin}; sceneggiatura e revisione mediante modello configurato.{retrieval} La revisione automatica non equivale a una verifica storiografica indipendente.'
def compile_pack(outline,narration,sources,project,settings):
    o=Outline.model_validate(outline).model_dump()
    places={p["id"]:dict(name=p["name"],pos=p["pos"],size=24) for p in o["places"]}
    sid={s["id"] for s in sources};rows={n["index"]:n for n in narration}
    if set(rows)!=set(range(len(o["scenes"]))):raise ValueError("Sceneggiatura incompleta.")
    for s in o["scenes"]:
        if not set(s["source_ids"])<=sid:raise ValueError("La scena cita una fonte mai consultata.")
        if not s['source_ids'] and not settings.get('research_context',{}).get('fallback_used'):
            raise ValueError("La scena non indica fonti consultate.")
    overview=fit([p["pos"] for p in o["places"]],pad=1.6,min_width=.45)
    poses=[fit([places[x]["pos"] for x in s["focus"]]+[p for r in s["routes"] for p in r["points"]],pad=1.75,min_width=.075) for s in o["scenes"]]
    poses[0]=overview;poses[-1]=overview
    bbox=bounds_for_views([overview,*poses]);slug="film-"+project["id"]
    commanders={c["id"]:dict(name=c["name"],subtitle=c["role"],side=commander_side(c),portrait="assets/portraits/"+slug+"/"+c["id"]+".jpg",wikipedia_page=c["wikipedia_page"],
                   portrait_note=[c["role"][:45],"Ritratto storico · fonte nei crediti"]) for c in o["commanders"]}
    scenes=[];prev=overview
    for i,(s,view) in enumerate(zip(o["scenes"],poses)):
        n=rows[i];used=set(s["focus"])
        routes=[{**r,"cue":0,"end_cue":1,"marker":False} for r in s["routes"]]
        arrows=[dict(side=r['side'],points=r['points'],cue=0,end_cue=1,kind=r.get('kind','advance')) for r in routes]
        units=[]
        for j,r in enumerate(routes):
            units.append(dict(id=f'move-{i}-{j}',label=r.get('label') or o['factions'][0 if r['side']=='a' else 1][:30],side=r['side'],
                pos=r['points'][0],kind=r.get('unit_kind','infantry'),count=2,path=r['points'],cue=0,until=None))
        if routes:
            defending='b' if routes[0]['side']=='a' else 'a';target=routes[0]['points'][-1]
            units.append(dict(id=f'hold-{i}',label=o['factions'][0 if defending=='a' else 1][:30],side=defending,
                pos=[target[0]+view[2]*.018,target[1]+view[2]*.012],kind='infantry',count=2,path=[],cue=0,until=None))
        else:
            for side in ('a','b'):
                units.append(dict(id=f'formation-{i}-{side}',label=o['factions'][0 if side=='a' else 1][:30],side=side,
                    pos=static_pos(view,side),kind='infantry',count=2,path=[],cue=0,until=None))
        scene=dict(id=f"{i+1:02}",title=s["title"],date=s["date"],kicker=n["kicker"],note=s["event"],facts=[n["fact"]],
            lines=n["lines"],map="campaign",camera_start=prev,camera_end=view,
            camera_keys=[{"at":0,"view":prev},{"at":.42,"view":view},{"at":1,"view":view}],
            sources=s["source_ids"],visible_places=list(used),routes=routes,units=units,arrows=arrows,
            commanders=[{"id":c,"cue":0} for c in s["commander_ids"]],sfx=[],focus=[],region_labels=[])
        scene['caption_note']='Movimenti e schieramenti schematici · coordinate geografiche ricontrollate quando disponibili'
        if i==0:scene["mode"]="opening"
        if i==len(poses)-1:scene["mode"]="ending"
        # Authored fixed label offsets avoid per-frame collision placement.
        scene["label_offsets"]={name:[0,30+(j%2)*12] for j,name in enumerate(s["focus"])}
        scenes.append(scene);prev=view
    words=sum(len(line.split()) for n in narration for line in n["lines"])
    if not project["minutes"]*145<=words<=project["minutes"]*195:
        raise ValueError(f"Sceneggiatura di {words} parole: fuori dall'intervallo per {project['minutes']} minuti.")
    pack=dict(schema_version=1,slug=slug,title=o["title"],short_title=o["short_title"],
        subtitle=o["title"][:50],description=o["description"],display_date=o["display_date"],
        language="it",target_minutes=project["minutes"],min_minutes=project["minutes"]*.88,max_minutes=project["minutes"]*1.12,
        width=1920,height=1080,fps=settings["fps"],visual_style="atlas",atlas="assets/geography/atlas-film/atlas.json",atlas_locator=overview,
        output="output/"+slug+"_documentario_1080p.mp4",verification_dir=slug+"_verification",
        voice_engine="kokoro",voice="assets/voice/kokoro/kokoro-v1.0.onnx",voice_styles="assets/voice/kokoro/voices-v1.0.bin",
        voice_speaker="if_sara",voice_credit="Kokoro 82M, voce italiana if_sara. Sintesi locale; pesi Apache-2.0.",
        pronunciation={},voice_sentence_chunks=[f"{i+1:02}:{j}" for i in range(len(scenes)) for j in range(2)],
        max_voice_tempo=1.22,places=places,river_names=o["river_names"],commanders=commanders,
        factions=[dict(id="a",label=o["factions"][0],color=[239,185,93],estimate="Consistenze indicate nel racconto",commander=""),dict(id="b",label=o["factions"][1],color=[221,109,101],estimate="Consistenze indicate nel racconto",commander="")],
        route_legend="Movimenti militari · schematici",maps={"campaign":dict(center=overview[:2],scale=[100,100],seed=41,landmarks=[],roads=[],rivers=[],ridges=[],forests=[],zones=[])},
        sources=[dict(id=s["id"],title=s["title"],url=s["url"],use=("Documento locale: "+s.get("citation","provenienza indicata dall’utente")+". Passaggi recuperati dall’indice locale; originale conservato nel progetto." if s.get("origin")=="local_document" else "Pagina consultata il "+s["retrieved"][:10]+". Riferimenti per il racconto; evidenza testuale conservata nel progetto.")) for s in sources],
        editorial_notes=o["uncertainties"]+["Itinerari e schieramenti illustrativi; geografia fisica moderna, senza confini politici non verificati."],
        source_method=source_method(sources),
        territorial_note="Nord in alto. Base fisica moderna, percorsi schematici. Nessun confine attuale è presentato come storico.",
        map_notice="Mappe illustrative su base fisica moderna; percorsi e orari incerti sono segnalati.",
        extra_credits=CREDIT+(" OpenStreetMap contributors (ODbL); geocodifica Nominatim. https://www.openstreetmap.org/copyright/" if any('Nominatim' in p.get('note','') for p in o['places']) else ''),assets=[],scenes=scenes)
    # Each camera scale gets enough terrain pixels for the final 1080p frame.
    # A single low zoom for the whole campaign made tactical close-ups look like
    # enlarged thumbnails. Per-patch zooms preserve both bounded downloads and
    # crisp local relief.
    candidates=[]
    for i,view in enumerate(poses):
        if view[2]>16:continue
        b=bounds_for_views([view])
        zoom=max(8,min(15,math.ceil(math.log2(360*(1920/view[2]*.75)/256))))
        candidates.append((zoom,-(b[2]-b[0])*(b[3]-b[1]),i,b))
    selected=[]
    for zoom,negative_area,i,b in sorted(candidates):
        if any(ez>=zoom and eb[0]<=b[0] and eb[1]<=b[1] and eb[2]>=b[2] and eb[3]>=b[3] for ez,_,_,eb in selected):continue
        selected.append((zoom,negative_area,i,b))
    if len(selected)>6:
        context=min(selected,key=lambda row:(row[0],row[1]))
        details=sorted((row for row in selected if row is not context),key=lambda row:(-row[0],-row[1]))[:5]
        selected=[context,*details]
    # Lower-resolution context layers are composited first; close tactical
    # layers are last and therefore retain their detail.
    selected=sorted(selected,key=lambda row:(row[0],row[1]))
    patches={f"detail{i+1}":{"bounds":b,"zoom":zoom} for zoom,_,i,b in selected}
    geo={"bounds":bbox,"patches":patches,"terrain_zoom":8,"output":"assets/geography/atlas-film"}
    return pack,geo
