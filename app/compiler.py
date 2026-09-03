"""Deterministic adapter: validated narrative data -> the reusable atlas engine."""
import math,copy
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
def compile_pack(outline,narration,sources,project,settings):
    o=Outline.model_validate(outline).model_dump()
    places={p["id"]:dict(name=p["name"],pos=p["pos"],size=24) for p in o["places"]}
    sid={s["id"] for s in sources};rows={n["index"]:n for n in narration}
    if set(rows)!=set(range(len(o["scenes"]))):raise ValueError("Sceneggiatura incompleta.")
    for s in o["scenes"]:
        if not set(s["source_ids"])<=sid:raise ValueError("La scena cita una fonte mai consultata.")
        if not s['source_ids'] and not settings.get('research_context',{}).get('fallback_used'):
            raise ValueError("La scena non indica fonti consultate.")
    overview=fit([p["pos"] for p in o["places"]],pad=1.6,min_width=7)
    poses=[fit([places[x]["pos"] for x in s["focus"]]+[p for r in s["routes"] for p in r["points"]],pad=1.75) for s in o["scenes"]]
    poses[0]=overview;poses[-1]=overview
    bbox=bounds_for_views([overview,*poses]);slug="film-"+project["id"]
    commanders={c["id"]:dict(name=c["name"],subtitle=c["role"],side="a",portrait="assets/portraits/"+slug+"/"+c["id"]+".jpg",wikipedia_page=c["wikipedia_page"],
                   portrait_note=[c["role"][:45],"Ritratto storico · fonte nei crediti"]) for c in o["commanders"]}
    scenes=[];prev=overview
    for i,(s,view) in enumerate(zip(o["scenes"],poses)):
        n=rows[i];used=set(s["focus"])
        routes=[{**r,"cue":0,"end_cue":1,"marker":True} for r in s["routes"]]
        scene=dict(id=f"{i+1:02}",title=s["title"],date=s["date"],kicker=n["kicker"],note=s["event"],facts=[n["fact"]],
            lines=n["lines"],map="campaign",camera_start=prev,camera_end=view,
            camera_keys=[{"at":0,"view":prev},{"at":.42,"view":view},{"at":1,"view":view}],
            sources=s["source_ids"],visible_places=list(used),routes=routes,units=[],arrows=[],
            commanders=[{"id":c,"cue":0} for c in s["commander_ids"]],sfx=[],focus=[],region_labels=[])
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
        route_legend=o["factions"][0][:30],maps={"campaign":dict(center=overview[:2],scale=[100,100],seed=41,landmarks=[],roads=[],rivers=[],ridges=[],forests=[],zones=[])},
        sources=[dict(id=s["id"],title=s["title"],url=s["url"],use="Pagina consultata il "+s["retrieved"][:10]+". Riferimenti per il racconto; evidenza testuale conservata nel progetto.") for s in sources],
        editorial_notes=o["uncertainties"]+["Itinerari e schieramenti illustrativi; geografia fisica moderna, senza confini politici non verificati."],
        source_method="Fonti recuperate dal web, sceneggiatura e revisione mediante modello configurato. La revisione automatica non equivale a una verifica storiografica indipendente.",
        territorial_note="Nord in alto. Base fisica moderna, percorsi schematici. Nessun confine attuale è presentato come storico.",
        map_notice="Mappe illustrative su base fisica moderna; percorsi e orari incerti sono segnalati.",
        extra_credits=CREDIT,assets=[],scenes=scenes)
    patches={}
    for i,view in enumerate(poses):
        if view[2]>16:continue
        b=bounds_for_views([view])
        if any(b[0]>=old[0] and b[1]>=old[1] and b[2]<=old[2] and b[3]<=old[3] for old in patches.values()):continue
        if len(patches)<6:patches["detail"+str(i+1)]=b
    geo={"bounds":bbox,"patches":patches,"terrain_zoom":8,"output":"assets/geography/atlas-film"}
    # Bound terrain work and memory on CPU-only production machines.
    if sum((b[2]-b[0])*(merc(b[3])-merc(b[1])) for b in patches.values())>450:geo["terrain_zoom"]=7
    return pack,geo
