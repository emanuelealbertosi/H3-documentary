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


def repair_pack(path,workspace,log=lambda _:None):
    path=Path(path).resolve()
    if not path.is_relative_to(Path(workspace).resolve()):raise ValueError('Riparazione consentita soltanto nel workspace del progetto.')
    pack=read_json(path)
    if pack.get('schema_version')!=2:return False
    normalized=bundled_contract().normalize_document(pack)
    if normalized==pack:return False
    backup=path.with_name(path.stem+'.before-focus-fix-'+str(time.time_ns())+path.suffix)
    shutil.copy2(path,backup)
    write_json(path,normalized)
    log('Compatibilità delle mappe corretta: riferimenti ai luoghi conservati. Testo, fonti e mappe già preparate vengono riutilizzati; copia precedente salvata.')
    return True
