"""Narrow, reversible repair of already compiled general packs on resume."""
import functools,importlib.util,shutil,time
from pathlib import Path
from .paths import ROOT
from .store import read_json,write_json


@functools.lru_cache(maxsize=1)
def bundled_contract():
    # Use the shipped pure adapter even when a workspace retains an older isolated engine.
    spec=importlib.util.spec_from_file_location('h3_history_contract',ROOT/'pipeline/engine/history_contract.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


@functools.lru_cache(maxsize=1)
def bundled_geography():
    spec=importlib.util.spec_from_file_location('h3_history_geography',ROOT/'pipeline/engine/history_geography.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def repair_pack(path,workspace,log=lambda _:None):
    path=Path(path).resolve()
    if not path.is_relative_to(Path(workspace).resolve()):raise ValueError('Riparazione consentita soltanto nel workspace del progetto.')
    pack=read_json(path)
    if pack.get('schema_version')!=2:return False
    from .source_coordinates import ground_coordinates
    grounded,coordinate_changes=ground_coordinates(pack,workspace)
    normalized=bundled_contract().normalize_document(grounded)
    if normalized==pack:return False
    stamp=str(time.time_ns())
    # Keep the historical backup name used by existing projects and tests.
    backup=path.with_name(path.stem+'.before-focus-fix-'+stamp+path.suffix)
    shutil.copy2(path,backup)
    write_json(path,normalized)
    if coordinate_changes and pack.get('presentation_mode')!='slides':
        geopath=path.with_name('geography.json')
        views=[normalized.get('overview')]+[scene.get('camera_end') for scene in normalized.get('scenes',[])]
        views=[view for view in views if isinstance(view,list) and len(view)==3]
        write_json(geopath,bundled_geography().atlas_config(views))
        checkpoint=Path(workspace).parent/'checkpoints'
        for name in ('geography','preview','render','finalize','verify'):
            marker=checkpoint/(name+'.done.json')
            if marker.exists():marker.rename(checkpoint/(name+'.before-coordinate-fix-'+stamp+'.json'))
        labels=', '.join(change['name'] for change in coordinate_changes)
        log('Geografia documentale corretta per '+labels+'. Mappe e anteprime saranno rigenerate; voce e testo restano invariati.')
    else:
        log('Compatibilità delle mappe corretta: riferimenti ai luoghi conservati. Testo, fonti e mappe già preparate vengono riutilizzati; copia precedente salvata.')
    return True
