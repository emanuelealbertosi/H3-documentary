# H3-documentary

**Uno studio locale per creare documentari storici visuali in italiano.** Scrivi un argomento, scegli la durata e collega il tuo server LLM: l'app ricerca le fonti, costruisce la sceneggiatura, genera la voce, anima le mappe e produce un MP4 Full HD con sottotitoli, capitoli e documenti editoriali.

Il progetto riunisce DocumentariAI Studio e il suo motore già funzionante. Il renderer, le animazioni, il TTS e i formati delle battaglie sono conservati. Non richiede una cartella DocumentariAI separata, Python già installato, FFmpeg di sistema o un editor video.

## Avvio su Windows

1. Clona questo repository oppure scarica lo ZIP ed **estrailo completamente** in una cartella scrivibile.
2. Apri **INSTALLA.bat**. Scarica gratuitamente Python, le dipendenze, FFmpeg e la voce italiana; verifica i componenti prima di terminare.
3. Apri **AVVIA.bat**. L'app si apre nel browser su `http://127.0.0.1:8775`.
4. In **Amministrazione**, inserisci indirizzo e modello del server LLM, prova la connessione e salva.

Se apri direttamente AVVIA.bat, l'installazione parte automaticamente quando manca. Non servono privilegi amministrativi. L'installazione resta nella cartella dell'app e non modifica il Python di sistema. I download già validi sono riutilizzati dopo un'interruzione. Chiudere il browser non interrompe il server o un rendering.

**Piattaforma verificata:** Windows x64 Intel/AMD, esecuzione CPU. Consigliati 16 GB di RAM e almeno 15–20 GB liberi per lavorare con video e mappe. L'ambiente di base occupa alcuni GB; ogni produzione richiede spazio aggiuntivo. GPU NVIDIA, account a pagamento e abbonamenti non sono necessari.

Internet serve per l'installazione, la ricerca e gli asset geografici/iconografici mancanti. TTS, animazioni, montaggio e verifiche sono locali. Il server LLM può trovarsi su un altro PC: è l'unico modello che devi procurare e configurare separatamente. La velocità e la qualità della ricerca/scrittura dipendono anche da quel modello.

## Collegare il modello

| Server | Indirizzo di esempio | Configurazione |
|---|---|---|
| LM Studio | `http://IP-DEL-SERVER:1234/v1` | Avvia il server e abilita l'accesso dalla rete locale. |
| Ollama | `http://IP-DEL-SERVER:11434/v1` | Usa il nome esatto del modello installato. |
| vLLM | `http://IP-DEL-SERVER:8000/v1` | Usa il modello esposto dall'endpoint. |
| API compatibile OpenAI | `https://TUO-SERVER/v1` | Chiave solo se richiesta dal server. |

`localhost` indica il PC sul quale gira H3, non l'altro computer. Il provider deve supportare `/models` e `/chat/completions`, seguire istruzioni in italiano e produrre JSON strutturato. Nessun fornitore a pagamento è preselezionato; se colleghi un servizio tariffato, valgono le sue condizioni.

Il modello riceve argomento e fonti consultate, mai l'audio di una voce da clonare. Le chiavi sono custodite dal backend con Windows DPAPI. L'app web è accessibile solo dal PC locale; questa edizione non è un servizio multiutente da esporre su Internet.

## Documentari e compatibilità

Riconoscimento automatico di `battle`, `war`, `territorial_expansion`, `migration`, `cultural_movement`, `religious_expansion`, `trade_network`, `exploration`, `political_history`, `revolution`, `economic_history`, `technology_history`, `biography`, `general_history`.

Gli elementi comprendono mappe fisiche con zoom, unità e frecce militari, territori persistenti, migrazioni, reti, itinerari, personaggi, opere, timeline e grafici. Il tipo di documentario guida la scelta delle scene. Le basi fisiche moderne e i percorsi illustrativi sono indicati nei crediti; non vengono spacciati per confini storici verificati.

Esempi da chiedere nell'app:

- «Espansione dell'Impero Romano dal 264 a.C. al 117 d.C.», 12 minuti.
- «La diffusione del Rinascimento in Europa», 10 minuti.
- «Le grandi migrazioni dei popoli germanici», 15 minuti.
- «La Via della Seta e le sue rotte commerciali».
- «Una biografia di Napoleone».

I `battle.json` precedenti continuano a funzionare. Nel repository sono inclusi i pack editoriali di Waterloo, Stalingrado, Annibale e cinque esempi generici. I video già prodotti e le cartelle private dell'installazione originaria non fanno parte della distribuzione. Per riusare un progetto personale puoi conservarlo con i suoi asset nella pipeline scelta nelle impostazioni avanzate.

Ogni nuova produzione salva il proprio workspace in `data/jobs/<id>/workspace/`. Contiene video 1920×1080, SRT, `sources.md`, `script.md`, `timeline.json`, `credits.md`, asset con provenienza e rapporto di verifica. Dall'app puoi aprire i materiali e scaricare il pacchetto del progetto. Nessun caricamento automatico su YouTube.

La ricerca conserva le pagine consultate e il modello esegue una revisione; l'esito automatico non equivale a una verifica indipendente di ogni affermazione storica. Se fonti, dati o risposta del modello sono insufficienti, la produzione si ferma con un errore visibile e conserva il lavoro.

## Immagini personali insieme alle mappe

Apri **Immagini e riquadri** per caricare JPG, PNG e WebP tramite drag and drop, collegarli a persone, luoghi, argomenti, eventi, organizzazioni o scene, e posizionare il riquadro nell’anteprima. Le immagini appaiono durante le frasi che citano il nome associato o le sue varianti. Originali e crediti vengono conservati; i progetti già avviati mantengono la propria copia. [Guida e verifiche](docs/IMMAGINI.md).

## Voce e Chatterbox

La voce predefinita è **Kokoro `if_sara`**, italiana, gratuita e locale; i suoi pesi vengono scaricati automaticamente. L'eSpeak usato per la pronuncia e FFmpeg arrivano con le librerie: non vanno installati a mano.

Il pacchetto include anche **l'esperimento opzionale Chatterbox Multilingual**, con ambiente separato e supporto al campione vocale:

```powershell
.\INSTALLA.bat -Chatterbox
powershell -NoProfile -ExecutionPolicy Bypass -File .\pipeline\tools\chatterbox\prova.ps1
```

Scarica circa 3 GB di pesi oltre alle librerie. Per usare una registrazione propria, aggiungi `-Reference "C:\percorso\voce.wav"` al secondo comando. Sul PC CPU usato per le prove, circa 13 secondi di italiano hanno richiesto 94 secondi e quasi 7 GB di memoria del processo. È una prova opzionale da terminale: **Chatterbox non è ancora selezionabile come voce dei documentari nell'interfaccia**. La sua installazione non sostituisce Kokoro.

Questa versione produce documentari in italiano con una traccia audio e sottotitoli italiani. Server TTS esterni, doppiaggio multilingua e tracce audio multiple restano estensioni da integrare; non sono presentati come funzioni già pronte.

## Riga di comando

Dopo l'installazione, senza attivare ambienti:

```powershell
.\.venv\Scripts\python.exe generate.py "Espansione dell'Impero Romano dal 264 a.C. al 117 d.C." --duration 12m
.\.venv\Scripts\python.exe generate.py "Diffusione del Rinascimento" --duration 10m --type cultural_movement
```

Questi comandi usano l'app e il modello configurato. Per riprodurre un pack già scritto senza LLM:

```powershell
.\.venv\Scripts\python.exe generate.py --example rinascimento --prepare-only
.\.venv\Scripts\python.exe generate.py --example rinascimento
cd pipeline
.\.venv\Scripts\python.exe documentary.py validate --battle battles/waterloo/battle.json
```

Gli atlanti e gli asset mancanti degli esempi vengono scaricati quando necessari. Per una porta diversa usa `AVVIA.bat -Port 8776`; nel terminale CLI imposta anche `$env:H3_STUDIO_URL='http://127.0.0.1:8776'`.

## Organizzazione

```text
INSTALLA.bat / AVVIA.bat   installazione e apertura
app/                     interfaccia HTTP, ricerca, LLM, coda, compilazione
static/                  interfaccia e font locali
pipeline/engine/          motore condiviso, TTS, timeline, renderer, verifiche
pipeline/battles/         pack storici compatibili
pipeline/documentaries/  documenti storici generici ed esempi
scripts/                 installatore, download verificati, diagnostica, ZIP
tests/                   test dell'app, distribuzione e produzione dimostrativa
data/                    configurazione e produzioni private, escluse da Git
.runtimes/ e .venv/       runtime automatici, esclusi da Git
```

Schemi e architettura: [formato battle](pipeline/docs/BATTLE_PACK.md), [storia generale](pipeline/docs/GENERAL_HISTORY.md), [integrazione nell'app](docs/HISTORY.md). Per GitHub: [pubblicazione e rilascio](docs/GITHUB.md). Per i controlli eseguiti: [verifica della distribuzione](docs/VERIFICA.md).

## Aggiornare, spostare, riprendere

Dopo un aggiornamento del codice riapri INSTALLA.bat e poi AVVIA.bat. Se sposti tutta la cartella, riapri INSTALLA.bat per ricostruire i riferimenti dei runtime. Non spostare l'app durante una produzione. Impostazioni cifrate e progetti non sono inclusi nello ZIP sorgente; fai un backup separato di `data/` per i tuoi lavori.

Se l'app non si avvia, consulta `data/install.log` e `data/server.stderr.log`. Una seconda copia sulla stessa porta viene riconosciuta e non scambiata per quella corrente. La reinstallazione conserva progetti e configurazione.

## Sviluppo e licenze

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -X utf8 tests/production_smoke.py
```

Il secondo comando realizza un filmato di prova con ricerca e LLM simulati esplicitamente, cartografia scaricata e produzione audio/video reali. Non certifica la qualità di un modello remoto. I test automatici GitHub eseguono la suite leggera, senza scaricare modelli vocali o renderizzare documentari.

Codice del progetto: MIT, conservando gli avvisi originali. Dipendenze, pesi e asset mantengono le proprie licenze: [THIRD_PARTY.md](THIRD_PARTY.md). Il runtime Python viene ottenuto tramite [uv](https://docs.astral.sh/uv/guides/install-python/); release uv e file vocali sono fissati e verificati tramite checksum.
