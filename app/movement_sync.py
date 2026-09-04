"""Deterministic contract between itinerary movements and narrated paragraphs."""
import re
import unicodedata


def _fold(value):
    text=unicodedata.normalize('NFKD',str(value).casefold())
    text=''.join(c for c in text if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+',' ',text).strip()


def _variants(place):
    """Names explicitly present in the catalog, without fuzzy historical guesses."""
    name=str(place.get('name','')).strip();values=[name,place.get('id','')]
    outside=re.sub(r'\([^)]*\)',' ',name).strip()
    if outside:values.append(outside)
    for group in re.findall(r'\(([^)]*)\)',name):values.extend(re.split(r'[/;,]',group))
    for key in ('aliases','alternate_names','variants'):
        value=place.get(key,[])
        values.extend(value if isinstance(value,list) else [value])
    result=[]
    for value in values:
        folded=_fold(value)
        if len(folded)>=3 and folded not in result:result.append(folded)
    return result


def mentions(text,place):
    folded=' '+_fold(text)+' '
    return any(' '+variant+' ' in folded for variant in _variants(place))


def prepare_scene(scene,places):
    """Put arrivals in paragraph one and departures/progress in paragraph two."""
    by_id={p['id']:p for p in places};focus=set(scene.get('focus',scene.get('location_ids',[])));changes=0
    for movement in scene.get('movements',[]):
        cue=movement.get('cue');origin=movement.get('from');target=movement.get('to')
        if not isinstance(cue,int) or isinstance(cue,bool) or cue not in (0,1):
            if target in focus and origin not in focus:cue=0
            elif origin in focus:cue=1
            else:cue=0
            movement['cue']=cue;changes+=1
        # These labels are only used by validation/prompting; coordinates remain authoritative.
        if origin in by_id:movement.setdefault('from_label',by_id[origin]['name'])
        if target in by_id:movement.setdefault('to_label',by_id[target]['name'])
    return changes


def prepare_outline(outline):
    places=outline.get('places',outline.get('locations',[]));changes=0
    for scene in outline.get('scenes',[]):changes+=prepare_scene(scene,places)
    return changes


def plan_issue(scene,places):
    """Reject a route whose destination is absent from the scene it is assigned to."""
    by_id={p['id']:p for p in places};description=scene.get('title','')+' '+scene.get('event','')
    for index,movement in enumerate(scene.get('movements',[]),1):
        target=by_id.get(movement.get('to'))
        if target and not mentions(description,target):
            return (f"movements[{index}] termina a {target['name']!r}, ma titolo/event della scena non nominano "
                    "questa destinazione. La stessa scena deve raccontare esplicitamente la partenza o l’arrivo; "
                    "altrimenti sposta o rimuovi il movimento.")
    return ''


def narration_issue(batch,planned,places):
    """Ensure the arrow destination is spoken while that arrow is drawn."""
    by_index={row.get('index'):row for row in batch.get('scenes',[])};by_id={p['id']:p for p in places}
    for scene in planned:
        spoken=by_index.get(scene.get('index'))
        if not spoken:continue
        lines=spoken.get('lines',[])
        for index,movement in enumerate(scene.get('movements',[]),1):
            target=by_id.get(movement.get('to'));cue=movement.get('cue',0)
            if target and isinstance(cue,int) and 0<=cue<len(lines) and not mentions(lines[cue],target):
                return (f"Scena {scene['index']+1}, movimento {index}: la freccia arriva a {target['name']!r} nel "
                        f"paragrafo {cue+1}, ma quel paragrafo non nomina la destinazione. Riscrivi quel paragrafo "
                        "descrivendo esplicitamente il movimento nella stessa direzione mostrata.")
    return ''
