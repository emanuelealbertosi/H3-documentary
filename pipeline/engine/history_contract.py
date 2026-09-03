"""Bridge editorial place IDs to the legacy cue-effect contract without losing geography."""
import copy


def normalize_document(document):
    if document.get('schema_version')!=2:return document
    result=copy.deepcopy(document)
    known={p['id'] for p in result.get('locations',[])}
    for scene in result.get('scenes',[]):
        value=scene.get('focus',[])
        if not isinstance(value,list):raise ValueError(f"Scena {scene.get('id')}: focus deve essere un elenco di luoghi oppure di effetti grafici.")
        if value and all(isinstance(item,str) for item in value):
            if not set(value)<=known:raise ValueError(f"Scena {scene.get('id')}: focus cita luoghi non presenti nel catalogo: {sorted(set(value)-known)}.")
            if 'location_ids' in scene and not set(value)<=set(scene['location_ids']):
                raise ValueError(f"Scena {scene.get('id')}: focus e location_ids indicano luoghi diversi; correggi i riferimenti.")
            scene.setdefault('location_ids',list(value))
            scene['focus']=[]  # Legacy focus is exclusively a list of cue effect records.
        elif any(not isinstance(item,dict) for item in value):
            raise ValueError(f"Scena {scene.get('id')}: non mescolare luoghi ed effetti grafici in focus.")
    return result


def validate_cue_records(scene):
    """Catch malformed legacy effects during authoring, before CLI validation/rendering."""
    for key in ('units','arrows','sfx','focus','commanders','routes'):
        rows=scene.get(key,[])
        if not isinstance(rows,list) or any(not isinstance(row,dict) for row in rows):
            raise ValueError(f"Scena {scene.get('id')}: {key} deve contenere oggetti grafici, non stringhe. Per persone usa person_ids; per luoghi usa location_ids.")
        for row in rows:
            cue=row.get('cue',0)
            if not isinstance(cue,int) or isinstance(cue,bool) or not 0<=cue<len(scene['lines']):
                raise ValueError(f"Scena {scene.get('id')}: cue non valido in {key}: {cue!r}.")
