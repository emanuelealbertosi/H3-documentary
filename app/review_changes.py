"""Apply explicit human corrections to existing scenes, never re-author a film."""
import copy
import time
from pathlib import Path

from . import store


def places_for(pack):
    if pack.get('locations'):
        return pack['locations']
    value=pack.get('places',{})
    return [{'id':key,**row} for key,row in value.items()] if isinstance(value,dict) else value


def _same(a,b):
    return isinstance(a,(list,tuple)) and isinstance(b,(list,tuple)) and len(a)==len(b) and all(abs(x-y)<1e-8 for x,y in zip(a,b))


def _replace_point(point,changed,ambiguous):
    if any(_same(point,old) for old in ambiguous):return point
    matches=[new for old,new in changed.values() if _same(point,old)]
    # Two distinct named places can share coordinates. Do not guess which moved.
    return copy.deepcopy(matches[0]) if len(matches)==1 else point


def _routes(scene,changed,ambiguous):
    touched=False
    items=[*scene.get('movements',[]),*scene.get('routes',[]),*scene.get('arrows',[]),
           *scene.get('units',[]),*scene.get('network',{}).get('edges',[])]
    for item in items:
        if not isinstance(item,dict):continue
        before=copy.deepcopy(item)
        for field in ('points','path'):
            points=item.get(field)
            if not isinstance(points,list) or not points:continue
            item[field]=[_replace_point(point,changed,ambiguous) for point in points]
            for end,index in (('from',0),('to',-1)):
                if isinstance(item.get(end),str) and item[end] in changed:
                    item[field][index]=copy.deepcopy(changed[item[end]][1])
        if 'pos' in item:item['pos']=_replace_point(item['pos'],changed,ambiguous)
        touched=touched or item!=before
    for item in scene.get('network',{}).get('nodes',[]):
        if item.get('location_id') in changed and 'pos' in item:
            item['pos']=copy.deepcopy(changed[item['location_id']][1]);touched=True
    return touched


def _move_catalog(pack,changed):
    for name in ('locations','places'):
        collection=pack.get(name,[])
        rows=collection.items() if isinstance(collection,dict) else ((row.get('id'),row) for row in collection)
        for ident,row in rows:
            if ident in changed:
                row['pos']=copy.deepcopy(changed[ident][1])
                row['coordinate_origin']='user_review'
    for name in ('events','persons','entities'):
        for row in pack.get(name,[]):
            if row.get('location_id') in changed and 'pos' in row:
                row['pos']=copy.deepcopy(changed[row['location_id']][1])


def _scene_points(scene,places,pack):
    ids=scene.get('location_ids',scene.get('visible_places',[]))
    points=[places[ident]['pos'] for ident in ids if ident in places]
    for item in [*scene.get('movements',[]),*scene.get('routes',[]),*scene.get('arrows',[]),*scene.get('network',{}).get('edges',[])]:
        points.extend(item.get('points',[]))
    for node in scene.get('network',{}).get('nodes',[]):
        if node.get('location_id') in places:points.append(places[node['location_id']]['pos'])
    if pack.get('schema_version')==2:
        from pipeline.engine.history_territories import scene_area_points
        points.extend(scene_area_points(pack,scene))
    return points


def _refit(pack,changed,affected,geo):
    if pack.get('presentation_mode')=='slides':return geo
    from .compiler import fit
    from pipeline.engine.history_geography import atlas_config
    places={p['id']:p for p in places_for(pack)}
    previous_old=pack.get('overview',pack.get('atlas_locator'));old_overview=copy.deepcopy(previous_old)
    overview_points=[p['pos'] for p in places.values()]
    if pack.get('schema_version')==2:
        from pipeline.engine.history_territories import scene_area_points
        for scene in pack['scenes']:overview_points.extend(scene_area_points(pack,scene))
    overview=fit(overview_points,pad=1.7,min_width=previous_old[2] if previous_old else 6)
    if 'overview' in pack:pack['overview']=overview
    if 'atlas_locator' in pack:pack['atlas_locator']=overview
    previous_new=overview
    for i,scene in enumerate(pack['scenes']):
        if not scene.get('camera_end'):
            points=_scene_points(scene,places,pack)
            scene['camera_end']=fit(points,pad=1.85,min_width=6) if points else copy.deepcopy(previous_new)
        if not scene.get('camera_start'):scene['camera_start']=copy.deepcopy(previous_old or overview)
        old_start=copy.deepcopy(scene.get('camera_start'))
        old_end=copy.deepcopy(scene.get('camera_end'))
        ids=scene.get('location_ids',scene.get('visible_places',[]))
        network_ids=[node.get('location_id') for node in scene.get('network',{}).get('nodes',[])]
        touches=scene['id'] in affected or any(ident in changed for ident in [*ids,*network_ids])
        if touches:
            points=_scene_points(scene,places,pack)
            if points:
                scene['camera_end']=fit(points,pad=1.85,min_width=old_end[2] if old_end else 6)
            affected.add(scene['id'])
            scene.pop('label_offsets',None)
        if _same(old_end,old_overview) and (i==0 or scene.get('mode') in ('opening','ending')):
            scene['camera_end']=copy.deepcopy(overview)
        if _same(old_start,previous_old):scene['camera_start']=copy.deepcopy(previous_new)
        if scene.get('camera_start')!=old_start or scene.get('camera_end')!=old_end:
            affected.add(scene['id'])
            # Preserve all authored time positions, substituting only known poses.
            for key in scene.get('camera_keys',[]):
                if _same(old_start,old_end) and _same(key.get('view'),old_end):
                    key['view']=copy.deepcopy(scene['camera_start'] if key.get('at',0)==0 else scene['camera_end'])
                elif _same(key.get('view'),old_start):key['view']=copy.deepcopy(scene['camera_start'])
                elif _same(key.get('view'),old_end):key['view']=copy.deepcopy(scene['camera_end'])
            view=scene['camera_end']
            for unit in scene.get('units',[]):
                if unit.get('id')==f'hold-{i}' and scene.get('routes'):
                    target=scene['routes'][0]['points'][-1]
                    unit['pos']=[target[0]+view[2]*.018,target[1]+view[2]*.012]
                elif unit.get('id') in (f'formation-{i}-a',f'formation-{i}-b'):
                    from .compiler import static_pos
                    unit['pos']=static_pos(view,unit['side'])
        previous_old=old_end;previous_new=scene.get('camera_end',previous_new)
    views=[overview]
    for scene in pack['scenes']:
        views.extend(scene[key] for key in ('camera_start','camera_end') if scene.get(key))
        views.extend(key['view'] for key in scene.get('camera_keys',[]) if key.get('view'))
    try:
        if pack.get('schema_version')==1:
            from .compiler import geography_for_views
            updated=geography_for_views(overview,views[1:],output=geo.get('output','assets/geography/atlas-film'))
        else:updated=atlas_config(views,output=geo.get('output','assets/geography/atlas-film'))
    except ValueError as error:
        raise ValueError('La posizione scelta richiede una mappa oltre i limiti di questo progetto. Avvicina il luogo al teatro geografico del racconto o crea un progetto separato.') from error
    return {**geo,**updated}


def _resync_text(scene,pack,warnings):
    from .movement_sync import mentions
    places=places_for(pack);by_id={p['id']:p for p in places}
    for movement in scene.get('movements',[]):
        target=by_id.get(movement.get('to'))
        if not target:continue
        matches=[i for i,line in enumerate(scene['lines']) if mentions(line,target,places)]
        if len(matches)==1:
            movement['cue']=matches[0]
            if 'end_cue' in movement:movement['end_cue']=max(matches[0],movement['end_cue'])
        elif not matches:
            warnings.append(f"Scena {scene['id']}: il testo modificato non nomina più {target['name']}; il percorso conserva il collegamento al paragrafo originale.")
    # Text-specific audio fragments must never override newly written words.
    for key in ('voice_custom_chunks','voice_phoneme_overrides','voice_chunk_assets'):
        if isinstance(pack.get(key),dict):
            for cue in range(len(scene['lines'])):pack[key].pop(f"{scene['id']}:{cue}",None)
    from .media import scene_matches
    entries=[entry for entry in pack.get('user_media',[]) if entry.get('bindings') and not str(entry.get('id','')).startswith('visual-')]
    managed={entry['id'] for entry in entries}
    insets=[item for item in scene.get('image_insets',[]) if item.get('asset_id') not in managed]
    for entry in entries:
        if entry.get('enabled',True):
            for cue in scene_matches(scene,entry):
                insets.append({'asset_id':entry['id'],'cue':cue,'slot':0,'slots':1,'title':entry.get('title',''),
                               'layout':entry.get('layout',{}),'sha256':entry.get('image_sha256','')})
    if managed:scene['image_insets']=insets


def transform(pack,geo,outline,narration,draft):
    """Return edited copies. Named endpoints move; sourced territory geometry does not."""
    edited=copy.deepcopy(pack);geography=copy.deepcopy(geo)
    plan=copy.deepcopy(outline);speech=copy.deepcopy(narration)
    by_id={s['id']:s for s in edited['scenes']}
    texts={row['id']:row['lines'] for row in draft.get('scenes',[])}
    old_places={p['id']:p for p in places_for(pack)}
    all_positions=[tuple(p['pos']) for p in old_places.values()]
    ambiguous={pos for pos in all_positions if all_positions.count(pos)>1}
    changed={p['id']:(old_places[p['id']]['pos'],p['pos']) for p in draft.get('places',[])}
    affected=set(texts);map_scenes=set();warnings=[]
    for ident,lines in texts.items():
        by_id[ident]['lines']=copy.deepcopy(lines);_resync_text(by_id[ident],edited,warnings)
    for i,scene in enumerate(edited['scenes']):
        if scene['id'] in texts:
            row=next((n for n in speech if n.get('index')==i),None)
            if row is not None:row['lines']=copy.deepcopy(texts[scene['id']])
            if i<len(plan.get('scenes',[])):
                # Persist the new cue assignments without importing other compiled fields.
                for old,new in zip(plan['scenes'][i].get('movements',[]),scene.get('movements',[])):
                    for key in ('cue','end_cue'):
                        if key in new:old[key]=new[key]
    if changed:
        _move_catalog(edited,changed)
        if plan:_move_catalog(plan,changed)
        for scene in edited['scenes']:
            if _routes(scene,changed,ambiguous):map_scenes.add(scene['id'])
        if plan:
            for scene in plan.get('scenes',[]):_routes(scene,changed,ambiguous)
        geography=_refit(edited,changed,map_scenes,geography)
        affected.update(map_scenes)
    if texts:
        edited.setdefault('metadata',{})['manual_narration']=True
    report={'revision':draft['revision'],'scene_ids':sorted(affected),'text_scene_ids':sorted(texts),'map_scene_ids':sorted(map_scenes),
            'place_ids':sorted(changed),'warnings':warnings,'narration_modified':bool(texts),'geography_modified':bool(changed),
            'provenance':'Correzioni esplicite dell’utente durante la revisione; nessuna nuova verifica storica automatica.'}
    edited.setdefault('metadata',{})['editorial_review']=copy.deepcopy(report)
    # Validate through the existing adapter; this never relaxes historical geometry gates.
    from pipeline.engine.common import validate_pack
    validate_pack(edited)
    return edited,geography,plan,speech,report


def commit(pid,packpath,pack,geo,outline,narration,report):
    """Archive originals and invalidate only derived work, with rollback on write error."""
    folder=store.JOBS/pid;work=folder/'workspace';cp=folder/'checkpoints'
    paths={Path(packpath):pack,Path(packpath).with_name('geography.json'):geo}
    if (cp/'outline.json').is_file():paths[cp/'outline.json']=outline
    if (cp/'narration.json').is_file():paths[cp/'narration.json']=narration
    stale=[cp/(key+'.done.json') for key in ('voice','preview','render','finalize','verify')]
    stale+=[cp/'visual-review-preview.done.json',cp/'visual-review.approved.json']
    if report['geography_modified']:stale.append(cp/'geography.done.json')
    stale.extend([work/'timeline.json',work/'build'/pack['slug']/'timeline.json'])
    original={path:path.read_bytes() if path.is_file() else None for path in [*paths,*stale]}
    backup=cp/'editorial-review-backups'/str(time.time_ns())
    for path,data in original.items():
        if data is not None:
            target=backup/path.relative_to(folder);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    try:
        for path,value in paths.items():store.write_json(path,value)
        for path in stale:path.unlink(missing_ok=True)
        from .review_editor import mark_applied
        mark_applied(pid,report)
    except BaseException:
        for path,data in original.items():
            if data is None:path.unlink(missing_ok=True)
            else:
                # Replace rather than mutate a potentially shared inode.
                temporary=path.with_name(path.name+'.rollback');temporary.write_bytes(data);temporary.replace(path)
        raise
    store.event(pid,'Revisione applicata: '+str(len(report['text_scene_ids']))+' testi e '+str(len(report['place_ids']))+' luoghi corretti. Le fasi derivate saranno aggiornate alla ripresa.')
    for warning in report['warnings']:store.event(pid,warning,'warning')
    return report
