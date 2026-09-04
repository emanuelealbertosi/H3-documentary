"""Resumable narration authoring with a single-scene fallback for smaller models."""
import json,math
from .llm import ModelError,TruncatedResponse
from .models import NarrationBatch
from .research import evidence
from .store import read_json,write_json
from .editorial_quality import near_duplicates


def words(row):return len(' '.join(row.get('lines',[])).split())


def narration_wpm(project):
    """Use an authoring rate suited to the selected synthesizer."""
    return 112 if project.get('tts_engine') in ('api','chatterbox') else 170


def issue(batch,expected,target,prior=None):
    rows=batch.get('scenes',[]);indices=[row.get('index') for row in rows]
    if indices!=expected:return f'Restituisci esattamente gli indici {expected}, in questo ordine; ricevuti {indices}.'
    low=math.ceil(target*.82);high=math.floor(target*1.18)
    bad=[(row['index'],words(row)) for row in rows if not low<=words(row)<=high]
    if bad:return f'Conteggi parole errati {bad}. Ogni scena deve contenere {low}–{high} parole totali nelle due lines; event era solo una sintesi e il suo limite non si applica alla voce.'
    combined=list(prior or [])+rows
    duplicates=near_duplicates(combined,lambda row:' '.join(row.get('lines',[])))
    if duplicates:
        a,b,_=duplicates[0]
        return f'Le scene {combined[a].get("index",a)+1} e {combined[b].get("index",b)+1} ripetono lo stesso contenuto. Riscrivi la nuova scena con fatti e sviluppo distinti.'
    return ''


def recoverable(error):
    text=str(error)
    return isinstance(error,TruncatedResponse) or text.startswith('Il modello non riesce a produrre dati validi') or 'oggetto JSON valido' in text


def request_rows(llm,system,outline,rows,sources,target,log,attempts,prior=None):
    expected=[row['index'] for row in rows];ids={sid for row in rows for sid in row.get('source_ids',[])}
    local=evidence([source for source in sources if source['id'] in ids])
    low=math.ceil(target*.90);high=math.floor(target*1.10);line_low=max(25,math.floor(low/2));line_high=math.ceil(high/2)
    one=len(rows)==1
    base='Titolo: '+outline['title']+'\nScaletta generale: '+json.dumps([s['title'] for s in outline['scenes']],ensure_ascii=False)
    if prior:base+='\nTESTO GIÀ SCRITTO, DA NON RIPETERE:\n'+json.dumps([{'index':r['index'],'lines':r['lines']} for r in prior],ensure_ascii=False)
    base+=f'''\nScrivi SOLO {'UNA SOLA SCENA' if one else 'le scene indicate'}, con gli indici esatti {expected}.
Per ogni scena, lines contiene esattamente DUE PARAGRAFI narrati, ciascuno di circa {line_low}–{line_high} parole; totale {low}–{high} parole italiane. Conta le parole prima di rispondere.
Il campo event in ingresso è soltanto una sintesi breve: NON copiarlo come intera narrazione e NON applicare alla voce il suo limite di 35 parole.
Primo paragrafo: contesto e situazione visibile. Secondo: sviluppo, significato e collegamento cronologico. Periodi chiari, ritmo documentaristico, nessuna indicazione di regia nella voce. Numeri e anni in lettere nella narrazione. Evita ripetizioni con le altre scene. fact è un cartello sintetico; kicker è un breve sottotitolo.
SCENE:\n'''+json.dumps(rows,ensure_ascii=False)+'\nFONTI:\n'+local
    prompt=base
    last=''
    for attempt in range(attempts):
        try:batch=llm.structured(system,prompt,NarrationBatch)
        except ModelError as error:
            if not recoverable(error) or attempt==attempts-1:raise
            last=str(error);log(f'Sceneggiatura: formato non valido, nuovo tentativo {attempt+2}/{attempts}.')
        else:
            last=issue(batch,expected,target,prior)
            if not last:return batch
            if attempt==attempts-1:return None
            log(f'Sceneggiatura: lunghezza da correggere ({attempt+2}/{attempts}): {last}')
        prompt=base+'\nCORREZIONE OBBLIGATORIA: '+last+' Restituisci il JSON completo e conta di nuovo le parole.'
    return None


def build_narration(llm,system,outline,project,sources,cp,log,cancel):
    """Try efficient groups first; preserve and retry individual scenes when needed."""
    result=[];count=len(outline['scenes']);target=round(project['minutes']*project.get('narration_wpm',170)/count)
    for first in range(0,count,3):
        cancel();last=min(first+3,count);group_path=cp/f'narration-{first:03}.json'
        if group_path.exists():batch=read_json(group_path)
        else:
            rows=[{'index':i,**outline['scenes'][i]} for i in range(first,last)]
            try:batch=request_rows(llm,system,outline,rows,sources,target,log,2,prior=result)
            except ModelError as error:
                if not recoverable(error):raise
                batch=None
            if batch is None:
                log(f'Sceneggiatura: il gruppo {first+1}–{last} non rispetta il contratto; passo a una scena per volta.')
                singles=[]
                for i,row in zip(range(first,last),rows):
                    cancel();single_path=cp/f'narration-scene-{i:03}.json'
                    if single_path.exists():single=read_json(single_path)
                    else:
                        single=request_rows(llm,system,outline,[row],sources,target,log,3,prior=result+singles)
                        if single is None:raise ModelError(f'La scena {i+1} resta troppo breve o troppo lunga anche da sola. Usa un modello più aderente alle lunghezze richieste; i checkpoint precedenti sono conservati.')
                        write_json(single_path,single)
                    problem=issue(single,[i],target,result+singles)
                    if problem:raise ModelError(f'Checkpoint della scena {i+1} non valido: {problem}')
                    singles.extend(single['scenes']);log(f'Sceneggiatura: scena {i+1}/{count} controllata e salvata.')
                batch={'scenes':singles}
            problem=issue(batch,list(range(first,last)),target,result)
            if problem:raise ModelError('Sceneggiatura non valida: '+problem)
            write_json(group_path,batch)
        result.extend(batch['scenes']);log(f'Sceneggiatura: {last} / {count} scene.')
    return result
