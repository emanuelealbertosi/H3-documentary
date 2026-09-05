"""Defer unusable optional visuals without inventing geography or changing prose.

Only complete, schema-validated model responses reach this recovery. The caller
must run all historical, source and rendering validations again before saving.
"""
import copy,math


def _snapshot(value):
    if isinstance(value,dict):return {key:_snapshot(item) for key,item in value.items()}
    if isinstance(value,(list,tuple)):return [_snapshot(item) for item in value]
    if isinstance(value,float) and not math.isfinite(value):return {'invalid_numeric_value':repr(value)}
    return value


def strip_model_recovery(batch):
    """Recovery marks are application records, never claims made by the model."""
    batch.pop('visual_warnings',None)
    for scene in batch.get('scenes',[]):scene.pop('visual_recovery',None)
    return batch


def normalize_inline_visuals(batch):
    """Lift complete declarations from scenes without guessing their references."""
    from .outline_normalization import collections
    for key in ('visual_layers','visual_assets'):
        destination=batch.setdefault(key,[])
        for scene in batch.get('scenes',[]):
            declared=scene.get(key)
            if not isinstance(declared,(dict,list)) or not declared:continue
            rows=collections({key:declared})[key]
            if not isinstance(rows,list) or any(not isinstance(row,dict) or not row.get('id') for row in rows):continue
            # Ambiguous duplicate definitions remain errors for the normal merge.
            for row in rows:
                existing=next((item for item in destination if item.get('id')==row['id']),None)
                if existing is not None and existing!=row:raise ValueError(key+': ID già usato con contenuti diversi: '+row['id'])
                if existing is None:destination.append(copy.deepcopy(row))
            scene.pop(key,None)
    return batch


def _movement_problem(movement,scene,places):
    from engine.history_profiles import MOVEMENTS
    from .movement_sync import plan_issue
    ids={place['id'] for place in places}
    for field in ('from','to'):
        if movement.get(field) is not None and not isinstance(movement[field],str):return 'Il riferimento geografico del percorso non è un ID valido: '+field+'.'
        if movement.get(field) and movement[field] not in ids:return 'Il percorso cita un luogo non presente nel catalogo: '+str(movement[field])+'.'
    if movement.get('semantic') is not None and (not isinstance(movement['semantic'],str) or movement['semantic'] not in MOVEMENTS):return 'Il tipo di movimento non è supportato dal motore grafico.'
    points=movement.get('points',[])
    if not isinstance(points,(list,tuple)) or len(points)<2:return 'Il movimento non contiene un percorso utilizzabile.'
    for point in points:
        if (not isinstance(point,(list,tuple)) or len(point)!=2
                or any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in point)
                or not -180<=point[0]<=180 or not -79<=point[1]<=79):return 'Il percorso contiene coordinate non valide; non sono state corrette o inventate.'
    if len({tuple(point) for point in points})<2:return 'Il movimento parte e arriva nello stesso punto: non mostra uno spostamento.'
    return plan_issue({**scene,'movements':[movement]},places)


def recover_visuals(batch,places,known,direction,count):
    """Return an audit of omitted visuals; mutate only the caller's copied batch.

    Unknown scene locations, people/events, dates, quotations, quantitative data,
    source claims and catalog objects still pass through the strict validators.
    """
    from engine.history_direction import MAP_SCENES,scene_issues,shot_role
    from engine.history_profiles import SCENE_TYPES
    warnings=[]
    for scene in batch.get('scenes',[]):
        omitted=[];original_type=scene.get('scene_type');index=scene['index']
        def omit(element,data,reason):
            # JSON-native snapshots remain identical across checkpoint/resume;
            # tuples normalized by Pydantic do not change coordinate values.
            omitted.append({'element':element,'reason':reason,'data':_snapshot(data)})
        movements=[]
        for number,movement in enumerate(scene.get('movements',[])):
            problem=_movement_problem(movement,scene,places)
            if problem:omit(f'movements[{number}]',movement,problem)
            else:movements.append(movement)
        scene['movements']=movements
        if scene.get('network') is not None and not isinstance(scene['network'],dict):
            omit('network',scene.pop('network'),'La rete non ha una struttura visuale utilizzabile.')
        # These are optional picture/area links, not the historical objects.
        for field in ('asset_ids','territory_ids'):
            missing=[value for value in scene.get(field,[]) if value not in known[field]]
            if missing:
                omit(field,missing,'Riferimenti visuali non disponibili: '+', '.join(missing)+'.')
                scene[field]=[value for value in scene.get(field,[]) if value in known[field]]
        visual_payload=bool(movements or (scene.get('network') or {}).get('edges') or scene.get('schematic_journey')
                            or scene.get('person_ids') or scene.get('asset_ids') or scene.get('territory_ids')
                            or scene.get('chart') or scene.get('quote') or scene.get('comparison'))
        issues=scene_issues(scene,direction,shot_role(direction,index,count))
        if original_type not in SCENE_TYPES:issues.append('Tipo di scena non riconosciuto: '+str(original_type)+'.')
        # Only replace an empty/unsupported display. Keep every remaining valid
        # movement and visual component; never hide them in a text-only scene.
        placeholder=not visual_payload and bool(omitted or issues)
        if placeholder:
            if issues:omit('scene_type',original_type,'; '.join(issues))
            scene['scene_type']='event_focus'
        elif movements and original_type not in MAP_SCENES:
            omit('scene_type',original_type,'Il tipo di scena nascondeva i movimenti validi; sono conservati su una mappa.')
            scene['scene_type']='animated_route'
        elif issues and visual_payload:
            # An omitted route must not strand a valid portrait or artwork in
            # an animated_route scene that can no longer draw any route.
            preferred=('animated_route' if movements or scene.get('schematic_journey') else
                       'network_map' if (scene.get('network') or {}).get('edges') else
                       'territorial_change' if scene.get('territory_ids') else
                       'person_intro' if scene.get('person_ids') else
                       'document' if scene.get('asset_ids') and original_type=='document' else
                       'artwork' if scene.get('asset_ids') else
                       'data_visualization' if scene.get('chart') else
                       'comparison' if scene.get('comparison') else 'quote')
            if preferred!=original_type:
                omit('scene_type',original_type,'Il tipo di scena è stato adattato agli elementi visuali validi rimasti.')
                scene['scene_type']=preferred
        if not omitted:continue
        reason=' '.join(dict.fromkeys(item['reason'] for item in omitted))
        scene['visual_recovery']={'version':1,'reason':reason,'omitted_items':omitted,
                                  'original_scene_type':original_type,'placeholder':placeholder}
        warnings.append({'scene_index':index,'scene_id':f'{index+1:02}','scene_title':scene['title'],
                         'element':', '.join(item['element'] for item in omitted),'reason':reason,
                         'omitted_items':copy.deepcopy(omitted),'placeholder':placeholder})
    return warnings
