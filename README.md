# H3-documentary

**Uno studio locale per creare documentari storici visuali in italiano.** Scrivi un argomento, scegli la durata e collega il tuo server LLM: l'app ricerca le fonti, costruisce la sceneggiatura, genera la voce, anima le mappe e produce un MP4 Full HD con sottotitoli, capitoli e documenti editoriali.

Il progetto riunisce DocumentariAI Studio e il suo motore già funzionante. Il renderer, le animazioni, il TTS e i formati delle battaglie sono conservati. Non richiede una cartella DocumentariAI separata, Python già installato, FFmpeg di sistema o un editor video.

**Novità 1.13.1:** recupero più efficace quando un modello ripete dati non validi. I gruppi problematici diventano richieste mirate a una singola scena; i doppioni certi di un itinerario vengono rimossi dalla scena adiacente che non ne racconta la destinazione. Ogni correzione supera nuovamente tutti i controlli e viene registrata, conservando i checkpoint già approvati. Non vengono inventati luoghi, date o fatti per completare il film. Vedi [Ricerca e recupero](docs/RICERCA.md).

La scelta **Uso di mappe e immagini** vale anche per le foto scaricate e riutilizzate. L’uso didattico non commerciale ammette anche CC BY-NC e CC BY-NC-SA. Dopo Wikimedia Commons, la ricerca può consultare Openverse, controllando i metadati della singola opera sulla pagina originaria prima del download. Attribuzioni, provenienza e condizioni restano nei crediti. Vedi [Immagini e riquadri](docs/IMMAGINI.md).

Il recupero dei confini usa archivi datati con cache locale: Cliopatria copre molte epoche; l’opzione didattica non commerciale aggiunge CShapes. Il progetto distingue geometrie da archivio, copertura parziale e aree indicative. Vedi [Territori, confini e influenze](docs/TERRITORI.md).

## Avvio su Windows

1. Clona questo repository oppure scarica lo ZIP ed **estrailo completamente** in una cartella scrivibile.
2. Apri **INSTALLA.bat**. Scarica gratuitamente Python, le dipendenze, FFmpeg e la voce italiana; verifica i componenti prima di terminare.
3. Apri **START.bat** (oppure **AVVIA.bat**, mantenuto compatibile). L'app si apre nel browser su `http://127.0.0.1:8775`.
4. In **Amministrazione**, inserisci indirizzo e modello del server LLM, prova la connessione e salva.

Se apri direttamente AVVIA.bat, l'installazione parte automaticamente quando manca. Non servono privilegi amministrativi. L'installazione resta nella cartella dell'app e non modifica il Python di sistema. I download già validi sono riutilizzati dopo un'interruzione. Chiudere il browser non interrompe il server o un rendering.

Per **chiudere il server prima dei test**, apri **STOP.bat** nella stessa cartella. Ferma quella copia dell'app e i suoi processi di rendering, conservando progetti e materiali già salvati. Dopo puoi avviare i test oppure riaprire START.bat. Se il server è già fermo, lo stop non fa nulla. Non serve un collegamento a GitHub e lo stop non installa dipendenze.

Se usi porte diverse, `START.bat -Port 8776` avvia su quella porta e `STOP.bat -Port 8776` ferma solo quell'istanza. Senza `-Port`, STOP ferma tutte le istanze avviate da questa cartella. Ogni copia locale ha i propri comandi: vengono verificati percorso del programma e identità del processo, senza chiudere indiscriminatamente altri processi Python. Una produzione interrotta può essere ripresa dai passaggi salvati.

**Piattaforma verificata:** Windows x64 Intel/AMD, esecuzione CPU. Consigliati 16 GB di RAM e almeno 15–20 GB liberi per lavorare con video e mappe. L'ambiente di base occupa alcuni GB; ogni produzione richiede spazio aggiuntivo. GPU NVIDIA, account a pagamento e abbonamenti non sono necessari.

Internet serve per l'installazione, la ricerca e gli asset geografici/iconografici mancanti. Animazioni, montaggio e verifiche sono locali. Il server LLM e, facoltativamente, un server TTS possono trovarsi su un altro PC. La velocità e la qualità della ricerca/scrittura dipendono anche dal modello collegato.

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

La ricerca conserva le pagine consultate e il modello esegue una revisione; l'esito automatico non equivale a una verifica indipendente di ogni affermazione storica. Per impostazione predefinita, se le pagine consultabili non bastano, la **modalità ibrida** prosegue usando anche la conoscenza interna del modello. Il progetto, `sources.md`, la sceneggiatura, la timeline e la descrizione YouTube segnalano il livello di verifica. La conoscenza interna non viene trasformata in fonti bibliografiche; grafici quantitativi e citazioni richiedono ancora riscontri. Errori materiali, riferimenti inventati o risposte non valide continuano a fermare la produzione, conservando il lavoro.

In **Amministrazione → Produzione locale e ricerca → Se le fonti non bastano** puoi scegliere di attendere altre fonti (`strict`), ripristinando il comportamento precedente. SearXNG resta facoltativo. I progetti fermati durante la ricerca possono usare **Riprendi** dopo il riavvio dell'app aggiornata; scene già create conservano la politica editoriale salvata. [Dettagli e verifiche](docs/RICERCA.md).

Dalla versione **1.1.3** i nuovi piani storici generali vengono costruiti in passaggi salvati: concetto, catalogo dei luoghi e gruppi di due scene. Se la risposta supera lo spazio disponibile, il gruppo viene diviso in scene singole. Riferimenti geografici errati ricevono indicazioni precise per la correzione; nomi equivalenti vengono collegati solo quando identificano un luogo univoco. Il diario mostra le richieste al modello, i tentativi di correzione, le scene salvate e un messaggio d'attesa ogni 20 secondi. Il limite token configurato non viene aumentato automaticamente; un server che tronca anche una singola scena può ancora richiedere una diversa configurazione. Gli outline e i pack precedenti restano compatibili.

La versione **1.1.4** corregge il blocco `'str' object has no attribute 'get'` all'inizio di **Ritratti e materiali**. I luoghi del piano vengono ora convertiti correttamente per il motore. Se il progetto è già fermo per questo errore, chiudi la tua copia con STOP.bat, aggiorna il codice, riaprila e premi **Riprendi**: il file viene riparato con una copia di sicurezza, conservando ricerca, testo, revisione e mappe già completati. Non serve creare una nuova revisione. I file privati in `data/` vanno conservati durante l'aggiornamento. [Dettagli](docs/RICERCA.md#passaggio-dal-piano-al-motore-114).

La versione **1.1.5** aggiunge una regia visuale verificabile. Viaggi e itinerari diventano documentari prevalentemente cartografici, con partenza e arrivo, movimenti geografici quando documentabili e sequenze animate esplicitamente non geografiche per tappe leggendarie o non localizzabili. Mappe vuote, rotte nascoste dentro slide, componenti privi dei propri dati e personaggi mai visualizzati vengono rifiutati prima della voce. I ritratti collegati compaiono anche in riquadro sulle scene pertinenti; la cartografia generale richiede automaticamente aree di terreno dettagliate per gli zoom. Le narrazioni letterarie mostrano l'ordine delle tappe senza interpolare anni fittizi.

Anche le battaglie vengono ora progettate in passaggi salvati: prima luoghi, fazioni e comandanti, poi gruppi di due scene. Il modello vede gli ID ammessi a ogni richiesta; nomi equivalenti vengono normalizzati solo se univoci e gli errori indicano scena, campo, valore errato e ID validi. Lo stesso protocollo Chat Completions supporta LM Studio, Ollama e vLLM locali oppure endpoint remoti compatibili, senza codice specifico per un modello. Per applicare la nuova regia a un documentario già completato o a un vecchio piano povero occorre **Nuova revisione**, perché l'app non inventa retroattivamente tappe e coordinate.

La versione **1.1.6** conserva più connessioni al modello. Ogni coppia provider/indirizzo ricorda l'ultimo modello e i propri parametri; le chiavi rimangono cifrate separatamente con il profilo Windows. In Amministrazione puoi scegliere una voce da **Connessioni salvate** oppure cambiare scheda provider: l'app ripristina indirizzo, modello e stato della chiave senza mostrarne il contenuto al browser. Inserendo un secondo endpoint non si cancella più la chiave del primo; cambiando soltanto modello, la chiave del server viene conservata.

La versione **1.2.0** aggiunge il controllo del reasoning per ogni connessione: comportamento del server, forzato attivo a livello medio oppure forzato disattivato. Il controllo è sempre visibile nella pagina Admin, accanto alla configurazione del modello. Il client invia `reasoning_effort` tramite Chat Completions, supportato dalle versioni correnti di LM Studio, Ollama e vLLM; per server compatibili che non lo accettano si lascia il valore predefinito. Con LM Studio, **Modalità JSON** usa il relativo JSON Schema invece del vecchio `json_object`, non accettato dalle versioni recenti. Se un modello locale inserisce correttamente i dati dentro il contenitore `properties` dello schema, il client recupera i valori senza scambiare lo schema per la risposta. La sceneggiatura indica la lunghezza di ciascun paragrafo, riporta i conteggi errati e, se un gruppo non obbedisce, passa automaticamente a una scena per volta con checkpoint separati.

La versione **1.2.1** irrobustisce le mappe delle battaglie. La verifica geografica scarta località omonime trovate lontano dal teatro dichiarato, compresi risultati già memorizzati da versioni precedenti. Le viste regionali e tattiche ricevono livelli di rilievo distinti, scelti in base allo zoom finale, con curve di livello già impresse nel raster per mantenere stabili pan e zoom. Il layout considera insieme luoghi, simboli e nomi delle unità; i reparti che convergono sullo stesso punto vengono separati in modo deterministico. Il controllo visivo del modello continua a fermare difetti gravi riferiti a una scena precisa, mentre osservazioni vaghe su contrasto o stile restano avvisi e non bloccano indefinitamente la produzione.

La versione **1.3.0** aggiunge una biblioteca privata di documenti con RAG locale. Puoi incollare testo oppure trascinare PDF, DOCX, TXT e Markdown, descriverne autore e provenienza e scegliere le fonti per ciascun progetto. Un piccolo modello multilingue su CPU seleziona i passaggi pertinenti; una ricerca lessicale mantiene il flusso utilizzabile anche se l'indice semantico non è disponibile. Gli originali scelti vengono congelati nella produzione, citati in `sources.md` e non sono inclusi nel repository o negli ZIP di rilascio.

La versione **1.9.0** aggiunge la spunta facoltativa **Fermati per la revisione visuale**. La produzione completa ricerca, sceneggiatura, mappe e acquisizione delle immagini, crea anteprime con tempi provvisori e si ferma prima del TTS e del rendering. La pagina del progetto distingue riferimenti obbligatori e suggeriti: gli obbligatori partono attivi e ricevono un placeholder quando manca l’immagine, mentre i suggeriti partono esclusi. Ogni elemento dispone di **Escludi**, **Ripristina** o **Attiva suggerimento**. Puoi trascinare sostituzioni o sfondi e premere **Continua produzione**: il lavoro riparte dalla voce senza rifare le fasi editoriali e geografiche. Lasciando disattivata la spunta, il flusso automatico precedente resta invariato.

La versione **1.9.1** rende diagnostici i rifiuti HTTP dei server LLM e conserva nel progetto il messaggio sicuro restituito dal provider. Se LM Studio risponde che nessun modello è caricato, H3 usa la sua API nativa per caricare il modello configurato e riprende automaticamente. Nell’Admin puoi indicare anche il contesto da usare al caricamento; `0` conserva il valore predefinito di LM Studio. I recuperi compatibili per reasoning, JSON strutturato e limiti di contesto non cambiano le impostazioni salvate. I controlli dei piani parziali conoscono il numero finale delle scene e non scambiano più l’ultima scena già salvata per la conclusione del film; i nomi dei ruoli visuali copiati dai modelli piccoli vengono tradotti deterministicamente nei componenti grafici supportati. Durante la revisione, le miniature delle immagini automatiche e personalizzate compaiono sia nel progetto sia accanto ai riferimenti della gestione drag and drop. La colonna dei riferimenti parte da una larghezza leggibile e può essere allargata trascinando il separatore; la preferenza viene ricordata dal browser.

La versione **1.9.2** separa la selezione di un asset dalle associazioni: cliccando una miniatura del progetto si apre quell’immagine nell’editor, mentre i pulsanti **Collega** e **Scollega** modificano esplicitamente la spunta. L’elenco di un progetto non mescola più soggetti provenienti dai collegamenti globali di altri lavori. Gli asset automatici espongono anteprima, provenienza, sostituzione, esclusione e inquadratura; le immagini caricate possono essere archiviate oppure eliminate definitivamente dalla libreria, senza cancellare le copie già conservate nei progetti.

La versione **1.9.3** apre **Collega** in una finestra dedicata: puoi trascinare un file dal PC, scegliere tramite Esplora file oppure riutilizzare una miniatura della libreria. Dopo il collegamento, la scheda del soggetto mostra subito l’immagine scelta e consente di cambiarla o scollegarla. Cliccando una miniatura nella pagina del progetto, la gestione visuale apre e porta automaticamente in vista lo stesso elemento invece di ripartire dall’inizio dell’elenco.

La versione **1.9.4** rimuove la spunta generale **Inserisci le mie immagini associate**. I collegamenti espliciti sono già la scelta dell’utente e vengono usati automaticamente; **Collega**, **Scollega**, **Attiva** ed **Escludi** restano gli unici controlli necessari. Il campo interno precedente viene conservato per la compatibilità con i progetti esistenti.

La versione **1.10.0** aggiunge a ogni progetto il pannello richiudibile **Impostazioni per la prossima versione**. Prima di rigenerare puoi cambiare argomento, durata, linguaggio visuale, indicazioni editoriali, link, revisione visuale, documenti, TTS e campione vocale. Un progetto completato genera V2/V3 conservando il video precedente; un tentativo interrotto o fallito archivia il tentativo e riparte con le nuove scelte. Modello LLM, reasoning e rendering continuano a usare il profilo globale scelto in Amministrazione.

La versione **1.10.1** rende persistenti fra progetti le associazioni della libreria visuale. Un ritratto o un luogo già collegato viene riconosciuto tramite nome e varianti esplicite, copiato nel nuovo workspace prima dell’acquisizione degli asset e quindi non viene cercato o scaricato di nuovo. Ogni film conserva comunque la propria copia immutabile; scollegare, archiviare o sostituire una voce della libreria influenza soltanto le produzioni future.

La versione **1.10.2** sincronizza gli itinerari con la voce prima del rendering. Per ogni movimento il piano deve nominare la destinazione nella stessa scena; il paragrafo associato deve descrivere esplicitamente la medesima direzione. Gli arrivi vengono animati con il primo paragrafo, mentre partenze e prosecuzioni usano normalmente il secondo. Una risposta incoerente viene corretta dal modello oppure rifiutata prima di produrre voce e video. Il controllo riguarda il contratto generale di viaggi, esplorazioni e altri flussi geografici, senza modificare i vecchi film già conclusi.

La versione **1.8.0** crea un inventario di tutte le immagini del film: persone e luoghi citati, ritratti, opere, documenti e immagini caricate. Cerca automaticamente immagini con licenza compatibile; se una ricerca è assente, ambigua o non utilizzabile mostra una scheda neutra chiaramente segnalata. Ogni elemento può essere sostituito con drag and drop. Su un film concluso l’app crea V2, V3 e successive, renderizza soltanto le scene interessate, rimonta e verifica il video conservando la versione precedente. Restano inclusi i miglioramenti 1.7.1 per fonti caricate, coordinate, Higgs, ritmo vocale e tempo totale di elaborazione.

La versione **1.6.2** rimuove il limite specifico di 30 secondi che H3 applicava ai riferimenti Higgs. La prova, il cloning one-shot e la registrazione di una voce accettano tutti i campioni previsti dalla libreria locale, attualmente WAV da 4 a 60 secondi.

La versione **1.6.1** conserva il profilo TTS selezionato quando salvi o riapri l'Amministrazione: l'indirizzo remoto non viene più sostituito visivamente con `localhost:8000`. Le richieste naturali che parlano di rientri, traversate e spostamenti attivano la regia di viaggio. In questi racconti le scene di evento conservano una carta di orientamento e la sequenza delle tappe occupa una fascia compatta, lasciando leggibile la geografia.

La versione **1.6.0** rinnova la regia cartografica senza cambiare i pack: il rilievo fisico riceve un color grading più naturale, fiumi e località hanno contrasto e profondità, territori e reti sono più leggibili e i percorsi diventano nastri illustrati con terminali diversi per viaggio, commercio marittimo, migrazione, diffusione e azione militare. I simboli delle unità sono badge grafici e i ritratti cambiano lato quando coprirebbero un luogo focale. Tutti gli elementi restano deterministici per evitare tremolii. La stessa versione collega esplicitamente ogni segmento prodotto da Chatterbox o da un server TTS alla frase della timeline, impedendo che venga interpretato come Piper; la ripresa riusa la cache già generata. La prova Higgs in Amministrazione assegna inoltre un nome descrittivo automatico se il campo è vuoto.

La versione **1.5.0** integra il contratto completo del server Higgs Audio remoto. H3 carica esplicitamente il modello prima dell’intera attività vocale e lo scarica in ogni percorso di uscita, lasciando acceso il server HTTP. Il cloning one-shot usa `reference_audio` e `reference_text`; Amministrazione mostra stato e lifecycle, permette di registrare una voce persistente e conserva i parametri Higgs nel profilo. I campioni includono ora la trascrizione esatta. La stessa versione rende facoltative le immagini dei personaggi nei documentari generali: prova Wikipedia in inglese e italiano, quindi crea un riquadro procedurale dichiarato quando manca un’immagine licenziata, senza fermare la produzione.

La versione **1.4.1** normalizza automaticamente gli identificatori tecnici prodotti dai modelli locali: accenti, spazi e lettere come la `ı` turca vengono convertiti in ID ASCII stabili, mentre i nomi storici mostrati restano invariati. Collisioni e riferimenti realmente inesistenti continuano a essere rifiutati. Un progetto fermato durante il catalogo geografico può essere ripreso senza rifare ricerca, documenti o piano narrativo.

La versione 1.3.0 comprende anche i miglioramenti Chatterbox e cartografici preparati nella 1.2.2: la preparazione degli asset non cerca più una voce Kokoro quando il progetto usa il motore separato, la sintesi indica segmenti completati e avanzamento, e il controllo visivo esamina sia lo sviluppo sia la conclusione di ogni scena. L'apertura non sovrappone il ritratto al titolo, la scena finale elimina le etichette militari ripetitive e per prove rapide è disponibile la durata di **3 minuti**.

Per le battaglie, un passaggio visuale dedicato richiede al modello soltanto direzione e significato dei movimenti, usando ID di località verificati. Il programma trasforma questi dati in frecce, percorsi e simboli di unità senza chiedere coordinate tattiche inventate. Se il modello omette un movimento evidente viene applicato un fallback conservativo. Le località più usate possono essere ricontrollate tramite OpenStreetMap Nominatim: massimo dodici richieste sequenziali, intervallo superiore a un secondo, User-Agent identificativo e cache permanente nel progetto. Se il servizio non è disponibile, la produzione prosegue dichiarando illustrative le coordinate del modello.

## Documenti e fonti locali

Apri **Documenti e fonti** per trascinare PDF, DOCX, TXT o Markdown, oppure per incollare direttamente un testo. Puoi aggiungere titolo, autore, anno ed edizione o archivio di provenienza. Nella schermata iniziale scegli quali documenti usare; dentro un progetto ancora da avviare puoi modificare la selezione.

All'avvio della produzione gli originali e l'indice vengono copiati nel workspace del progetto. La ricerca ibrida combina corrispondenze lessicali con il modello gratuito `paraphrase-multilingual-MiniLM-L12-v2`, eseguito da FastEmbed sulla CPU. Al modello narrativo arrivano soltanto i passaggi più pertinenti, con indicazione della pagina quando il PDF la offre. Il contenuto dei documenti viene trattato come evidenza e non come istruzioni per il programma.

I PDF composti soltanto da scansioni sono conservati e segnalati come **OCR necessario**; questa versione non inventa testo e non esegue OCR in modo implicito. Il formato Word moderno DOCX è supportato, comprese le tabelle. Per i vecchi `.doc` occorre salvarli in DOCX. Limiti: 50 MB per file, 2,5 milioni di caratteri indicizzabili e 24 documenti per progetto. [Guida completa](docs/DOCUMENTI.md).

## Immagini personali insieme alle mappe

Apri **Immagini e riquadri** per caricare JPG, PNG e WebP tramite drag and drop, collegarli a persone, luoghi, argomenti, eventi, organizzazioni o scene, e posizionare il riquadro nell’anteprima. Le immagini appaiono durante le frasi che citano il nome associato o le sue varianti. Originali e crediti vengono conservati; i progetti già avviati mantengono la propria copia. [Guida e verifiche](docs/IMMAGINI.md).

## Voce e Chatterbox

Studio permette di scegliere per ogni progetto fra **Kokoro `if_sara`** e **Chatterbox Multilingual V3**. Kokoro è la scelta veloce e resta assegnata ai progetti creati dalle versioni precedenti. Chatterbox viene usato realmente per la narrazione e supporta il cloning one-shot: in Amministrazione si carica un WAV PCM con 10–20 secondi di parlato pulito, poi lo si sceglie nel nuovo documentario. Campione e sintesi restano sul computer; il documento conserva il credito e il watermark previsto dal modello.

`INSTALLA.bat` prepara anche l’ambiente separato di Chatterbox e scarica circa 3 GB di pesi. Chi vuole una sola installazione leggera può usare `INSTALLA.bat -SenzaChatterbox`; Studio segnalerà chiaramente che quel motore non è disponibile, senza ripiegare in silenzio su Kokoro. Sul PC CPU della prova, circa 13 secondi di italiano hanno richiesto 94 secondi e quasi 7 GB di memoria del processo. La pipeline carica il modello una volta e mantiene una cache per ogni frase, quindi un documentario può essere ripreso senza rigenerare l’audio già pronto.

La prova da terminale resta disponibile:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\pipeline\tools\chatterbox\prova.ps1 -Reference "C:\percorso\voce.wav"
```

Puoi anche salvare più **server TTS esterni** come fai con i server LLM. Sono inclusi adapter per endpoint OpenAI compatibili, Higgs Audio remoto, ElevenLabs e Google Cloud TTS. Con Higgs, H3 gestisce load e unload del modello per l’intera attività, invia campione e trascrizione nel cloning one-shot e può registrare voci persistenti sul server. Le risposte vengono convertite in WAV locale e passano nella stessa timeline misurata, con cache e ripresa automatica. Credenziali e token sono cifrati con Windows DPAPI e non entrano nei progetti. [Configurazione e privacy](docs/TTS_API.md).

Questa versione produce documentari in italiano con una traccia audio e sottotitoli italiani. Doppiaggio multilingua e tracce audio multiple restano estensioni successive.

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
app/                     interfaccia HTTP, documenti/RAG, ricerca, LLM, coda, compilazione
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
.\.venv\Scripts\python.exe -m pip install -r requirements-test.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -X utf8 tests/production_smoke.py
```

La suite usa Python 3.13 e Node.js 24, anche su un checkout pulito: `requirements-test.txt` aggiunge le librerie del motore necessarie ai test audio, senza dipendere dal runtime privato `pipeline/.venv`. I test usano l’interprete che esegue pytest. I controlli GitHub partono sui branch e sulle pull request; i tag di rilascio non duplicano l’esecuzione dello stesso commit.

L’ultimo comando realizza un filmato di prova con ricerca e LLM simulati esplicitamente, cartografia scaricata e produzione audio/video reali. Richiede l’installazione completa dell’app e non certifica la qualità di un modello remoto. I test automatici GitHub eseguono la suite leggera, senza scaricare modelli vocali o renderizzare documentari.

Codice del progetto: MIT, conservando gli avvisi originali. Dipendenze, pesi e asset mantengono le proprie licenze: [THIRD_PARTY.md](THIRD_PARTY.md). Il runtime Python viene ottenuto tramite [uv](https://docs.astral.sh/uv/guides/install-python/); release uv e file vocali sono fissati e verificati tramite checksum.
