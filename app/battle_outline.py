"""Checkpointed battle authoring; output remains the original Outline contract."""
import copy,json
from pydantic import BaseModel,Field
from .models import Outline,OutlineScene
from .outline_normalization import battle_references
from .llm import TruncatedResponse,ModelError
from .research import evidence
from .research_policy import validate_references
from .store import read_json,write_json


class BattleCatalog(Outline):
    scenes:list[OutlineScene]=Field(default_factory=list,max_length=0,description='Lascia vuoto: le scene saranno richieste separatamente.')


class BattleScene(OutlineScene):
    index:int=Field(ge=0,le=119)


class BattleSceneBatch(BaseModel):
    scenes:list[BattleScene]=Field(min_length=1,max_length=2)


def build_battle_outline(llm,system,project,sources,research,cp,log,cancel):
    count=round(project['minutes']*2)
    context=f"Battaglia: {project['topic']}. Durata {project['minutes']} minuti. Indicazioni: {project['notes']}. Scrivi tutti i titoli e testi in ITALIANO."
    ev=evidence([{**s,'text':s.get('text','')[:4500]} for s in sources])
    catalog_path=cp/'battle-catalog.json';progress_path=cp/'battle-progress.json'
    def refs(value):validate_references(value,sources,research);return value
    if catalog_path.exists():
        catalog=BattleCatalog.model_validate(read_json(catalog_path)).model_dump();log('Ripresa: catalogo della battaglia già salvato.')
    else:
        log('Battaglia: preparo luoghi, comandanti e fazioni prima delle scene.')
        prompt=context+'''\nProduci SOLO il catalogo, con scenes=[]. Due fazioni principali. Identifica i luoghi e i comandanti necessari per raccontare contesto, terreno, attacchi e ritirate; evita duplicati. ID brevi, stabili, da citare esattamente nelle scene successive.
Coordinate [LONGITUDINE,LATITUDINE], controlla ordine ed emisferi rispetto all'area della battaglia. Non scambiare le due coordinate. Non inventare localizzazioni precise prive di riscontri. wikipedia_page è il titolo esatto inglese della voce, mentre name/role e gli altri testi sono italiani. Ritratti massimo cinque protagonisti. Fonti consultate:\n'''+ev
        catalog=llm.structured(system,prompt,BattleCatalog,validator=refs)
        write_json(catalog_path,catalog)
    scenes=read_json(progress_path) if progress_path.exists() else []
    if [s.get('index') for s in scenes]!=list(range(len(scenes))) or len(scenes)>count:raise ValueError('Salvataggio delle scene incoerente: crea una nuova revisione.')
    def validate(batch,first,last):
        rows=batch['scenes']
        if sorted(s['index'] for s in rows)!=list(range(first,last)):raise ValueError(f'Restituisci esattamente le scene con index {list(range(first,last))}.')
        candidate=battle_references({**catalog,'scenes':rows})
        # Same reference checks as the final Outline, without fabricating padding scenes.
        for s in candidate['scenes']:
            for field,key in [('focus','places'),('commander_ids','commanders')]:
                allowed={r['id'] for r in catalog[key]};missing=set(s.get(field,[]))-allowed
                if missing:raise ValueError(f"Scena {s['index']+1} ({s['title']}), {field}: {sorted(missing)} non sono riferimenti validi. Usa soltanto {sorted(allowed)}. Temi, attacchi e nomi di eserciti appartengono a event, non a focus.")
        refs(candidate)
        return {'scenes':sorted(candidate['scenes'],key=lambda s:s['index'])}
    def request(first,last):
        cancel();log(f'Battaglia: preparo le scene {first+1}–{last} di {count}.')
        assignments=[{'index':i,'position':f'{i+1}/{count}'} for i in range(first,last)]
        prompt=context+f'''\nScrivi SOLO gli indici assegnati, circa trenta secondi per scena, in ordine cronologico nell'intero film di {count} scene. event è un breve riassunto, non ancora la voce.
focus DEVE essere una lista di ID geografici presenti nel catalogo seguente: mai temi come 'attacco', 'sconfitta', 'ritorno di Napoleone'. commander_ids DEVE usare ID del catalogo. Conserva questi riferimenti senza riscrivere il catalogo.
Mostra movimenti delle forze quando pertinenti con routes=[{{side:"a" o "b",points:[[lon,lat],...],uncertain:true}}]; non limitare una battaglia a carte immobili. Traiettorie illustrative coerenti con le località e il terreno, non coordinate tattiche spacciate per certe. Apertura e conclusione hanno focus d'insieme. Eventi simultanei restano simultanei. Non ripetere le scene precedenti. source_ids usa solo fonti consultate; [] se non ci sono riscontri e la modalità è ibrida.
CATALOGO FISSO:\n'''+json.dumps(catalog,ensure_ascii=False)+'\nSCENE PRECEDENTI:\n'+json.dumps([{'index':s['index'],'title':s['title'],'event':s['event']} for s in scenes],ensure_ascii=False)+'\nASSEGNAZIONI ESATTE:\n'+json.dumps(assignments)+'\nFONTI:\n'+ev
        try:batch=llm.structured(system,prompt,BattleSceneBatch,validator=lambda b:validate(b,first,last),split_on_truncation=last-first>1)
        except TruncatedResponse:
            if last-first==1:raise ModelError('Risposta troncata anche per una singola scena della battaglia; catalogo e scene completate sono salvati.')
            log('Gruppo troncato: richiedo una scena della battaglia alla volta.')
            for i in range(first,last):request(i,i+1)
            return
        batch=validate(batch,first,last);scenes.extend(batch['scenes']);write_json(progress_path,scenes)
        log(f'Battaglia: {len(scenes)}/{count} scene controllate e salvate.')
    while len(scenes)<count:request(len(scenes),min(len(scenes)+2,count))
    result=Outline.model_validate({**copy.deepcopy(catalog),'scenes':scenes}).model_dump();refs(result)
    return result
