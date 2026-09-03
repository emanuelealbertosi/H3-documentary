"""Editorial exports for non-battle productions, keeping legacy exporters intact."""
from .common import ROOT,write_json

def augment_script(script,timeline):
    if timeline.get('timing_status')=='estimated':
        script=[line.replace('Durata misurata:', 'Durata STIMATA (anteprima editoriale, voce non sintetizzata):') for line in script]
    script+=['## Regia visuale','']
    for s in timeline['scenes']:
        script += [f'{s["id"]} · {s["scene_type"]} · persone: {", ".join(s.get("person_ids",[])) or "—"} · luoghi: {", ".join(s.get("location_ids",[])) or "—"}']
    return script

def asset_credits(timeline):
    result=['## Opere, documenti e altri materiali','']
    for a in timeline.get('visual_assets',[]):
        result += [f'### {a.get("title",a["id"])}',f'{a.get("creator","")}. {a.get("credit","")} Licenza: {a["license"]}. [Provenienza]({a["source"]}). Originale: `{a["path"]}`. Riproduzione ridimensionata; nessuna alterazione del contenuto.','']
    return result

def export_estimate(timeline):
    from .export import export_documents
    write_json(ROOT/'build'/timeline['slug']/'timeline-estimated.json',timeline)
    write_json(ROOT/'timeline.json',timeline)
    export_documents(timeline)
    write_json(ROOT/'documentaries'/timeline['slug']/'timeline.json',timeline)
