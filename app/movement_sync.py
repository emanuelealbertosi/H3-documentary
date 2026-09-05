"""Deterministic contract between itinerary movements and narrated paragraphs."""
import re
import unicodedata
from copy import deepcopy


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


def _geographic_short_name(place):
    """Drop only a named Italian geographic prefix and its preposition."""
    outside=re.sub(r'\([^)]*\)',' ',str(place.get('name',''))).strip()
    match=re.fullmatch(r'(?:isola|isole|arcipelago|citta|porto|capo|lago|monte|golfo|baia|penisola|valle) '
                       r'(?:di|del|della|delle|dei|degli|dello|dell) (.+)',_fold(outside))
    if not match:return ''
    name=match[1]
    directions={'nord','sud','est','ovest','nordest','nordovest','sudest','sudovest',
                'settentrione','meridione','oriente','occidente','settentrionale','meridionale',
                'orientale','occidentale','centro','centrale'}
    if len(name.replace(' ',''))<4 or set(name.split())<=directions:return ''
    return name


def _unique_short_name(place,places):
    if not isinstance(places,(list,tuple)) or not places:return ''
    if any(not isinstance(row,dict) or not isinstance(row.get('id'),str) or not row['id'] for row in places):return ''
    ids=[row['id'] for row in places]
    if len(set(ids))!=len(ids) or place.get('id') not in ids:return ''
    current=next(row for row in places if row['id']==place['id'])
    if _fold(current.get('name',''))!=_fold(place.get('name','')):return ''
    name=_geographic_short_name(place)
    if not name:return ''
    for other in places:
        if other['id']==place['id']:continue
        if name in _variants(other) or name==_geographic_short_name(other):return ''
    return name


def mentions(text,place,places=None):
    folded=' '+_fold(text)+' '
    variants=_variants(place)
    if places is not None:
        shortened=_unique_short_name(place,places)
        if shortened:variants.append(shortened)
    return any(' '+variant+' ' in folded for variant in variants)


def repair_duplicate_routes(scenes,places):
    """Remove only an identical journey assigned twice in the current scene batch.

    This never borrows previously validated scenes, transfers geometry or adjusts
    the recipient cue. Ambiguous or unsupported cases remain for validation.
    """
    by_id={p['id']:p for p in places if isinstance(p,dict) and isinstance(p.get('id'),str)}
    ignored={'cue','from_label','to_label'}
    reports=[]
    for scene in scenes:
        index=scene.get('index');period=scene.get('historical_range')
        if not isinstance(index,int) or isinstance(index,bool) or not isinstance(period,(list,tuple)) or len(period)!=2:
            continue
        movements=scene.get('movements',[])
        if not isinstance(movements,list):continue
        description=str(scene.get('title',''))+' '+str(scene.get('event',''))
        for movement in list(movements):
            if not isinstance(movement,dict) or movement.get('semantic')!='journey':continue
            origin,target=movement.get('from'),movement.get('to')
            if not isinstance(origin,str) or not isinstance(target,str) or origin==target or origin not in by_id or target not in by_id:
                continue
            if origin not in scene.get('focus',[]) or mentions(description,by_id[target],places):continue
            comparable={key:value for key,value in movement.items() if key not in ignored}
            recipients=[]
            for other in scenes:
                other_index=other.get('index')
                if other is scene or not isinstance(other_index,int) or isinstance(other_index,bool) or abs(other_index-index)!=1:
                    continue
                other_period=other.get('historical_range')
                if not isinstance(other_period,(list,tuple)) or tuple(other_period)!=tuple(period) or target not in other.get('focus',[]):continue
                if not mentions(str(other.get('title',''))+' '+str(other.get('event','')),by_id[target],places):continue
                if any(isinstance(candidate,dict) and {key:value for key,value in candidate.items() if key not in ignored}==comparable
                       for candidate in other.get('movements',[])):
                    recipients.append(other)
            if len(recipients)!=1 or (len(movements)<=1 and not scene.get('schematic_journey')):continue
            # Identity locates this exact occurrence without reordering other routes.
            at=next(i for i,item in enumerate(movements) if item is movement)
            removed=movements.pop(at)
            reports.append({'action':'remove_adjacent_duplicate_journey','scene_index':index,
                            'kept_scene_index':recipients[0]['index'],'from':origin,'to':target,
                            'semantic':'journey','removed':deepcopy(removed)})
    return reports


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
        if target and not mentions(description,target,places):
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
            if target and isinstance(cue,int) and 0<=cue<len(lines) and not mentions(lines[cue],target,places):
                return (f"Scena {scene['index']+1}, movimento {index}: la freccia arriva a {target['name']!r} nel "
                        f"paragrafo {cue+1}, ma quel paragrafo non nomina la destinazione. Riscrivi quel paragrafo "
                        "descrivendo esplicitamente il movimento nella stessa direzione mostrata.")
    return ''
