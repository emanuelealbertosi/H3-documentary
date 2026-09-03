"""Real CPU video production with explicitly scripted research/model fixtures, no remote LLM."""
import os,sys,json,threading,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ["DOCUMENTARIAI_DATA"]=str(ROOT/"tests/output/production")
sys.path.insert(0,str(ROOT))
from app import store,runner
from app.models import ProjectRequest,Settings
from app.compiler import compile_pack
source=ROOT/"pipeline"
def digest(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
    return h.hexdigest()
protected=[source/"documentary.py",source/"engine/render.py",source/"assets/manifest.json",*sorted((source/"output").glob("*documentario_1080p.mp4"))]
before={str(p):digest(p) for p in protected}
texts=[
["Questa breve sequenza serve a controllare lo studio di produzione. La carta mostra una parte dell'Italia meridionale, con due località usate come riferimenti geografici. Il movimento della camera deve essere continuo, mentre i nomi restano legati alla posizione dei luoghi.",
"La voce viene generata su questo computer. Il modello linguistico non è coinvolto in questa prova tecnica: il testo è stato preparato in anticipo. Lo scopo è verificare che le scene, l'audio e il montaggio attraversino davvero l'intero percorso fino al video finale."],
["Una volta preparato il racconto, ogni scena riceve un intervallo di tempo. La durata viene misurata sulla voce narrante, così il cambiamento della mappa accompagna le parole. Le linee sulla carta rappresentano un percorso dimostrativo e non la ricostruzione di una battaglia.",
"La stessa procedura permette di controllare la leggibilità delle località, il comportamento dello zoom e l'orientamento della vista. Il nord rimane in alto. La piccola mappa nell'angolo aiuta a capire dove si trova l'area inquadrata rispetto al territorio circostante e alla penisola italiana."],
["Durante la produzione, lo studio salva i passaggi completati. Se un processo viene interrotto, la ripresa può usare i materiali già disponibili. I progetti hanno cartelle separate, mentre il motore legge i caratteri, la voce e le mappe senza modificare i documentari precedenti.",
"La prova controlla anche la creazione dei sottotitoli e dei capitoli. Questi elementi vengono aggiunti al file insieme alla traccia audio. I documenti del progetto conservano le informazioni necessarie per capire come il risultato è stato composto e per riprodurre il lavoro in seguito."],
["La fase conclusiva analizza il video codificato. Vengono controllati tutti i fotogrammi e l'audio, la risoluzione, la durata delle tracce e i livelli sonori. Un ulteriore controllo misura i cambiamenti di luminosità, per individuare eventuali lampi durante i movimenti della carta.",
"Questo filmato resta una dimostrazione del funzionamento tecnico. Per produrre un documentario nuovo, lo studio userà il modello configurato e fonti consultate sull'argomento scelto. Il risultato di questa prova conferma il collegamento tra l'applicazione e il motore locale, senza richiedere una scheda grafica dedicata."]
]
places=[{"id":"capua","name":"Capua","pos":[14.214,41.106]},{"id":"benevento","name":"Benevento","pos":[14.781,41.13]}]
outline={"title":"Prova tecnica dello studio","short_title":"Studio","description":"Verifica del percorso di produzione locale.","display_date":"Prova tecnica",
 "factions":["Percorso dimostrativo","Riferimenti"],"places":places,"commanders":[],"river_names":["Volturno"],
 "uncertainties":["Questo filmato è una prova tecnica, non una ricostruzione storica."],
 "scenes":[{"title":t,"date":"Test locale","focus":["capua","benevento"],"event":"Controllo tecnico del motore.","source_ids":["S1"],
 "routes":[{"side":"a","points":[[14.214,41.106],[14.45,41.12],[14.781,41.13]],"uncertain":True}],"commander_ids":[]} for t in ["Dalla richiesta al video","La carta e il tempo","Un progetto riproducibile","Il controllo finale"]]}
narration=[{"index":i,"lines":lines,"fact":"Prova tecnica con testo preparato e rendering locale","kicker":"Il funzionamento dello studio"} for i,lines in enumerate(texts)]
sources=[{"id":"S1","title":"DocumentariAI - documentazione del progetto","url":"https://example.org/test-fixture","text":"Fixture tecnica dichiarata. Non è una fonte di ricerca storica.","retrieved":store.now()}]
class ScriptedModel:
    def __init__(self,*a,**k):self.calls=0;self.batch=0
    def structured(self,system,prompt,schema,**kwargs):
        self.calls+=1
        if schema.__name__=="Outline":return outline
        if schema.__name__=="NarrationBatch":
            first=self.batch;self.batch+=3;return {"scenes":narration[first:first+3]}
        if schema.__name__=="Review":return {"acceptable":True,"issues":[],"source_ids":["S1"],"summary":"Fixture tecnica: nessuna verifica storiografica simulata come reale."}
        raise AssertionError(schema)
runner.LLM=ScriptedModel
runner.collect=lambda *a,**k:sources
store.init()
record=ROOT/"tests/output/production/job-id.txt";record.parent.mkdir(parents=True,exist_ok=True)
if record.exists():
    pid=record.read_text().strip()
else:
    p=store.create(ProjectRequest(topic="Prova tecnica del motore - fixture dichiarata",minutes=2,start=False,documentary_type="battle"));pid=p["id"];record.write_text(pid)
runner.FLAGS[pid]=threading.Event()
cfg=Settings(model="scripted-test-fixture",pipeline_path=str(source),fps=24,render_jobs=2).model_dump()
print("Real pipeline job:",pid,"word counts:",[sum(len(x.split()) for x in n["lines"]) for n in narration],flush=True)
runner.produce(pid,cfg)
p=store.project(pid);after={str(path):digest(path) for path in protected}
result={"status":p["status"],"error":p["error"],"project":p["id"],"result":p["result"],"scope":"Scripted LLM and research fixtures; real compiler, asset isolation, cartography, TTS, scene rendering, FFmpeg mixing, full MP4 decoding and brightness checks.","original_pipeline_unchanged":before==after,"hashes":after}
store.write_json(ROOT/"tests/output/production-report.json",result)
print(json.dumps(result,ensure_ascii=True,indent=2),flush=True)
assert p["status"]=="completed",p["error"]
assert before==after
