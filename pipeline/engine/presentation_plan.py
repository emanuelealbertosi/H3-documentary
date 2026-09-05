"""Pure, bounded page planning from the approved timeline. No authoring or synthesis."""
import copy,json,math
from pathlib import Path


def date_label(value):
    text=str(value)
    if text.lstrip('-').isdigit() and int(text)!=0:
        from .history_schema import year_label
        return year_label(int(text))
    return text


def load_timeline(workspace):
    root=Path(workspace).resolve()
    candidates=[root/'timeline.json']
    candidates.extend(sorted((root/'build').glob('*/timeline.json')))
    for path in candidates:
        if not path.is_file():continue
        if not path.resolve().is_relative_to(root):raise ValueError('Timeline esterna al progetto.')
        value=json.loads(path.read_text(encoding='utf-8'))
        if isinstance(value,dict) and value.get('scenes') and all(s.get('cues') for s in value['scenes']):
            return value,path
    raise ValueError('Timeline non disponibile: completa la preparazione delle scene e della voce prima di esportare il PDF.')


def validate_timeline(data):
    scenes=data.get('scenes',[])
    if not scenes:raise ValueError('Il progetto non contiene scene.')
    seen=set()
    for scene in scenes:
        sid=scene.get('id')
        if not sid or sid in seen:raise ValueError('Identificativi delle scene mancanti o duplicati.')
        seen.add(sid)
        duration=scene.get('duration',0)
        if not isinstance(duration,(int,float)) or not math.isfinite(duration) or duration<=0:raise ValueError('Durata della scena non valida.')
        cues=scene.get('cues',[])
        if not cues:raise ValueError('Cue narrativi mancanti nella scena '+str(sid))
        for cue in cues:
            a,b=cue.get('start'),cue.get('end')
            if not all(isinstance(v,(int,float)) and math.isfinite(v) for v in (a,b)) or not 0<=a<b<=duration+.001:
                raise ValueError('Tempi dei cue incoerenti nella scena '+str(sid))
            if not isinstance(cue.get('text'),str):raise ValueError('Testo narrativo mancante nella scena '+str(sid))


def plan_pages(timeline,variant='compact',narration='full',max_visual_pages=500):
    if variant not in ('compact','teaching') or narration not in ('full','none'):raise ValueError('Opzioni della presentazione non valide.')
    validate_timeline(timeline)
    pages=[]
    for scene in timeline['scenes']:
        cues=scene['cues']
        selected=[len(cues)-1] if variant=='compact' else list(range(len(cues)))
        for cue_index in selected:
            cue=cues[cue_index]
            routes=[m for key in ('movements','routes','arrows') for m in scene.get(key,[]) if m.get('cue',0)==cue_index and len(m.get('points',[]))>=2]
            linked=[i for i in scene.get('image_insets',[]) if i.get('cue',0)==cue_index]
            inset_ids=[i['asset_id'] for i in linked] or [None]
            if variant=='compact':inset_ids=inset_ids[-1:]
            phases=['start','end'] if variant=='teaching' and routes else ['end']
            for phase in phases:
                for inset_id in inset_ids if phase=='end' else [inset_ids[0]]:
                    text=''
                    if narration=='full' and phase=='end' and inset_id==inset_ids[0]:
                        text='\n\n'.join(c['text'] for c in cues) if variant=='compact' else cue['text']
                    at=scene['duration'] if variant=='compact' else cue['start']+min(.01,(cue['end']-cue['start'])/4) if phase=='start' else cue['end']-.000001
                    pages.append({'scene_id':scene['id'],'cue_index':cue_index,'phase':phase,'time':at,
                        'inset_asset_id':inset_id,'title':scene['title'],'text':text,
                        'source_ids':copy.deepcopy(scene.get('sources',scene.get('source_ids',[]))),
                        'historical_date':date_label(scene.get('date','')),'variant':variant})
                    if len(pages)>max_visual_pages:
                        raise ValueError(f'La presentazione supera {max_visual_pages} immagini: usa la versione compatta. Nessun testo è stato troncato.')
    return pages
