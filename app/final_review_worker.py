"""Rebuild explicit final corrections in an unpublished, independent workspace."""
import copy
import hashlib
import json
import shutil
from pathlib import Path

from . import store,visual_slots
from .pipeline import run,verify_pipeline,Cancelled


def digest(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda:source.read(1024*1024),b''):value.update(block)
    return value.hexdigest()


def render_plan(previous,current,changed,geography_changed=False):
    """Track actual visual dependencies, including programme-wide progress bars."""
    old={s['id']:s for s in previous['scenes']};new={s['id']:s for s in current['scenes']}
    if list(old)!=list(new):raise ValueError('La revisione finale mantiene numero e ordine delle scene.')
    affected=set(changed);reasons=[]
    sequence=current.get('visual_style')=='history' and (
        current.get('visual_direction') or current.get('metadata',{}).get('visual_direction',{})).get('timeline_mode')=='sequence'
    timing_changed=any(any(old[sid].get(key)!=new[sid].get(key) for key in ('start','end','duration','frames')) for sid in old)
    if timing_changed and not sequence:
        affected.update(old)
        reasons.append('La durata è cambiata: aggiorno anche la timeline di avanzamento visibile nelle altre scene.')
    for sid,scene in new.items():
        ignored={'start','end','audio'}
        if {k:v for k,v in scene.items() if k not in ignored}!={k:v for k,v in old[sid].items() if k not in ignored}:
            affected.add(sid)
    if geography_changed:
        nonmap={'timeline','person_intro','event_focus','comparison','data_visualization','quote','artwork','document','transition','summary'}
        direction=current.get('visual_direction') or current.get('metadata',{}).get('visual_direction',{})
        for sid,scene in new.items():
            if current.get('visual_style')!='history' or scene.get('scene_type') not in nonmap or (
                direction.get('map_led') and scene.get('scene_type') in {'event_focus','summary'}):affected.add(sid)
        reasons.append('La base geografica è cambiata: aggiorno le scene che mostrano la mappa.')
    # These shared fields affect frame content outside the edited scene itself.
    for key in ('maps','short_title','historical_period','visual_direction','factions','boundary_report','atlas_locator'):
        if previous.get(key)!=current.get(key):
            affected.update(old);reasons.append('Un elemento grafico comune è cambiato: '+key+'.')
    if not affected<=set(old):raise ValueError('La revisione cita una scena non presente nel film.')
    return {'scene_ids':[sid for sid in old if sid in affected],
            'reused_scene_ids':[sid for sid in old if sid not in affected],
            'timing_changed':timing_changed,'reasons':reasons}


def preserve_external_manifest(path,previous):
    current=store.read_json(path) if path.is_file() else {}
    merged={**previous,**current,'items':{**previous.get('items',{}),**current.get('items',{})}}
    store.write_json(path,merged)


def install_revision_voice_tools(work):
    """Upgrade candidate voice support without replacing a legacy renderer."""
    from .paths import ROOT
    for name in ('engine/revision_narration.py','engine/narration.py','engine/voice_delivery.py','tools/revise_narration.py'):
        dest=work/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/'pipeline'/name,dest)


def _geography_covered(work,geography,original):
    """Reuse the original atlas when every new view still fits its existing raster."""
    atlas=work/original.get('output','assets/geography/atlas-film')/'atlas.json'
    if not atlas.is_file():return False
    # The preserved acquisition config describes the atlas used by this film.
    # Requiring detailed coverage as well avoids blurry enlarged base rasters.
    def contains(old,new):
        return len(old)==len(new)==4 and old[0]<=new[0] and old[1]<=new[1] and old[2]>=new[2] and old[3]>=new[3]
    if not contains(original.get('bounds',[]),geography.get('bounds',[])):return False
    def spec(value,default):
        return (value.get('bounds',[]),value.get('zoom',default)) if isinstance(value,dict) else (value,default)
    available=[spec(v,original.get('terrain_zoom',8)) for v in original.get('patches',{}).values()]
    requested=[spec(v,geography.get('terrain_zoom',8)) for v in geography.get('patches',{}).values()]
    if any(not any(contains(o,n) and oz>=nz for o,oz in available) for n,nz in requested):return False
    layers=store.read_json(atlas).get('layers',[])
    return bool(layers) and all(layer.get('levels') and all((work/p).is_file() for p in layer['levels']) for layer in layers)


def run_revision(pid,cfg,revision_id):
    from . import final_review,runner,tts
    from .review_changes import transform
    from pipeline.engine.revision_narration import prepare_revision_pack,merge_timeline
    cancel=lambda:runner.check(pid)
    def log(message):store.event(pid,str(message))
    def stage(message,progress):
        cancel();store.update(pid,status='running',stage=message,progress=progress)
        final_review.set_state(pid,status='running',message=message)
    try:
        stage('Preparazione della revisione finale',3)
        candidate=final_review.prepare_candidate(pid,revision_id);work=candidate/'workspace';cp=candidate/'checkpoints'
        request=final_review.request_snapshot(pid,revision_id)
        source=verify_pipeline(cfg['pipeline_path']);python=source/'.venv/Scripts/python.exe'
        original_work=store.JOBS/pid/'workspace'
        relative_pack=visual_slots.project_pack(pid).relative_to(original_work)
        packpath=work/relative_pack;pack=store.read_json(packpath)
        timeline_path=work/'build'/pack['slug']/'timeline.json';previous=store.read_json(timeline_path)
        if previous.get('timing_status')=='estimated':raise ValueError('La revisione finale richiede la timeline misurata del video concluso.')
        geo_path=packpath.with_name('geography.json');geo=store.read_json(geo_path) if geo_path.is_file() else {}
        original_geography=copy.deepcopy(geo)
        outline=store.read_json(cp/'outline.json') if (cp/'outline.json').is_file() else {}
        narration=store.read_json(cp/'narration.json') if (cp/'narration.json').is_file() else []
        draft=request.get('editorial')
        report={'scene_ids':[],'text_scene_ids':[],'place_ids':[],'warnings':[],'geography_modified':False}
        if draft:pack,geo,outline,narration,report=transform(pack,geo,outline,narration,draft)
        # Preserve the completed film's voice and settings, not today's Admin profile.
        from pipeline.engine.revision_narration import VOICE_IDENTITY
        frozen=prepare_revision_pack(pack,previous)
        for key in VOICE_IDENTITY:
            if key in frozen:pack[key]=copy.deepcopy(frozen[key])
            else:pack.pop(key,None)
        visual_slots.apply_options(pack,request.get('visual_options',{}),request.get('layout_options',{}))
        changed=set(visual_slots.materialize(pack,work,request.get('media_records',[]),
                    replacements_only=True,media_root=candidate.parent/'media'))|set(report['scene_ids'])
        if not changed:raise ValueError('Non risultano modifiche da applicare al video.')
        # Keep the authored schema (including history v2) in the published pack.
        # The runtime adapter is only for measured timeline and synthesis work.
        store.write_json(packpath,pack);store.write_json(geo_path,geo)
        pack=prepare_revision_pack(pack,previous)
        for name,value in (('outline',outline),('narration',narration)):
            if (cp/(name+'.json')).is_file():store.write_json(cp/(name+'.json'),value)
        command=lambda name,*args:run(pid,python,work,['documentary.py',name,'--battle',str(relative_pack),*args],cancel,log)
        # Older films lack explicit delivery and subset synthesis support. Update
        # only the isolated voice helpers; retain the renderer and its old clips.
        install_revision_voice_tools(work)
        stage('Applicazione delle correzioni',12)
        command('validate')
        geography_rebuilt=False
        if report['geography_modified']:
            if _geography_covered(work,geo,original_geography):log('Le posizioni corrette sono coperte dalla mappa esistente: riuso i raster.')
            else:
                stage('Aggiornamento delle mappe interessate',18)
                for tool in ('tools/acquire_atlas.py','tools/prepare_atlas.py'):
                    run(pid,python,work,[tool,'--config',str(geo_path.relative_to(work))],cancel,log,max_hours=3)
                geography_rebuilt=True
        text_ids=report['text_scene_ids'];audio_hashes={s['id']:digest(work/s['audio']) for s in previous['scenes'] if s['id'] not in text_ids}
        if text_ids:
            stage('Aggiornamento del parlato modificato',30)
            subset=copy.deepcopy(pack);subset['scenes']=[s for s in pack['scenes'] if s['id'] in text_ids]
            manifest=work/'build'/pack['slug']/'voice'/'external-voice-cache.json'
            old_manifest=store.read_json(manifest) if manifest.is_file() else {}
            engine=pack.get('voice_engine')
            if engine=='tts_api':
                from .tts_api import synthesize_pack
                project={**store.project(pid),'tts_config':pack.get('voice_api'),
                         'tts_profile_id':pack.get('voice_api',{}).get('id')}
                # Public config is immutable; only the saved secret is resolved at call time.
                synthesize_pack(subset,project,work,cancel,log)
            elif engine=='chatterbox':
                _,tts_python,model,worker=tts.chatterbox_paths(source)
                subset_path=packpath.with_name('revision-voice.json');store.write_json(subset_path,subset)
                run(pid,tts_python,work,[str(worker),'--workspace',str(work),'--pack',str(subset_path.relative_to(work)),
                    '--model',str(model),'--threads',str(cfg.get('chatterbox_threads',4))],cancel,log,max_hours=12)
            if engine in ('tts_api','chatterbox'):preserve_external_manifest(manifest,old_manifest)
            run(pid,python,work,['tools/revise_narration.py','--battle',str(relative_pack),'--scenes',','.join(text_ids)],cancel,log)
            current=store.read_json(timeline_path)
        else:
            current=merge_timeline(previous,pack,{})
            store.write_json(timeline_path,current);store.write_json(work/'timeline.json',current)
            log('Testo invariato: tutti gli audio originali vengono riutilizzati.')
        if any(digest(work/next(s for s in current['scenes'] if s['id']==sid)['audio'])!=value for sid,value in audio_hashes.items()):
            raise ValueError('Un audio non modificato è cambiato durante la revisione: pubblicazione annullata.')
        selection=render_plan(previous,current,changed,geography_rebuilt)
        scenes=work/'build'/pack['slug']/'scenes'
        # A missing reusable clip is a real dependency, not a reason to restart research.
        for sid in list(selection['reused_scene_ids']):
            clip=scenes/(sid+'.mp4');marker=scenes/(sid+'.render.json')
            if not clip.is_file() or not marker.is_file() or store.read_json(marker).get('frames')!=next(s for s in current['scenes'] if s['id']==sid)['frames']:
                selection['scene_ids'].append(sid);selection['reused_scene_ids'].remove(sid)
        untouched={sid:digest(scenes/(sid+'.mp4')) for sid in selection['reused_scene_ids']}
        final_review.set_state(pid,changed_scene_ids=selection['scene_ids'],reused_scene_ids=selection['reused_scene_ids'])
        for message in [*report['warnings'],*selection['reasons']]:log(message)
        log(f"Revisione: {len(selection['scene_ids'])} scene da renderizzare, {len(untouched)} clip conservate; {len(text_ids)} scene con testo corretto.")
        scene_arg=','.join(selection['scene_ids'])
        stage('Anteprime delle scene modificate',55);command('preview','--scenes',scene_arg)
        # Explicitly invalidate selected clips only; shared render fingerprints are broader.
        for sid in selection['scene_ids']:(scenes/(sid+'.render.json')).unlink(missing_ok=True)
        stage('Rendering delle parti modificate',65);command('render','--scenes',scene_arg,'--jobs',str(cfg['render_jobs']))
        if any(digest(scenes/(sid+'.mp4'))!=value for sid,value in untouched.items()):
            raise ValueError('Una clip da conservare è cambiata: pubblicazione annullata.')
        stage('Rimontaggio del video aggiornato',86);command('finalize')
        stage('Verifica integrale del video aggiornato',94);command('verify')
        checker='tools/check_history_final.py' if pack.get('documentary_schema_version')==2 or pack.get('visual_style')=='history' else 'tools/check_atlas_final.py'
        run(pid,python,work,[checker,pack['slug']],cancel,log)
        verification_path=work/'output'/pack['verification_dir']/'report.json'
        verification=store.read_json(verification_path)
        if verification.get('status')!='passed':raise ValueError('Il nuovo video non ha superato la verifica.')
        verification['file']=str(original_work/pack['output'])
        store.write_json(verification_path,verification)
        audit={**report,**selection,'revision_id':revision_id,'verified':True,'audio_preserved':sorted(audio_hashes),
               'clip_sha256_preserved':untouched,'completed':store.now()}
        store.write_json(cp/'final-revision-report.json',audit)
        if draft:
            store.write_json(cp/'editorial-review-applied'/('final-'+revision_id+'.json'),{'draft':draft,'report':audit})
            (cp/'editorial-review.json').unlink(missing_ok=True)
        result={**request.get('original_result',{}),'duration':verification['video_duration'],'bytes':verification['bytes'],
                'sha256':verification['sha256'],'final_revision':audit}
        cancel();final_review.publish(pid,candidate,{'verified':True,'revision_id':revision_id,
                    'changed_scene_ids':selection['scene_ids'],'reused_scene_ids':selection['reused_scene_ids'],'result':result})
        log('Video aggiornato nello stesso progetto. Copia precedente conservata; nessuna nuova versione creata.')
    except Cancelled:
        final_review.finish_failure(pid,revision_id,'Revisione interrotta. Il video precedente è ancora disponibile.',cancelled=True)
    except Exception as error:
        message=str(error)
        if cfg.get('api_key'):message=message.replace(cfg['api_key'],'[chiave rimossa]')
        final_review.finish_failure(pid,revision_id,message[:2500])
