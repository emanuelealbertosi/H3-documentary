# DocumentariAI

Generatore locale di documentari storici in italiano: ricerca documentata → progetto editoriale → voce neurale → scene visuali → musica ed effetti procedurali → MP4 verificato.

## Estensione: storie visuali di ogni tipo

Il generatore supporta anche espansioni territoriali, migrazioni, movimenti culturali e religiosi, reti commerciali, esplorazioni, storia politica/economica/tecnologica, rivoluzioni e biografie. I battle pack e i comandi precedenti rimangono compatibili. Il nuovo formato editoriale è in `documentaries/`; voce, atlante, rendering e montaggio sono condivisi.

```powershell
./.venv/Scripts/python.exe generate.py "Diffusione del Rinascimento in Europa" --duration 10m
./.venv/Scripts/python.exe generate.py "Espansione dell’Impero Romano dal 264 a.C. al 117 d.C." --duration 12m
./.venv/Scripts/python.exe generate.py --example rinascimento
```

Le richieste nuove usano il modello collegato in **DocumentariAI Studio**, nella cartella separata `documentariAI-app`. Configuralo una volta in Amministrazione: LM Studio, Ollama, vLLM o API compatibile. Il comando avvia l’app se necessario e segue l’intera produzione. `--type cultural_movement` forza il linguaggio; normalmente viene scelto automaticamente. I pack già scritti si riproducono senza LLM.

Il documentario completo di verifica è `output/rinascimento_documentario_1080p.mp4`, circa sette minuti. Le altre prove editoriali comprendono Roma, migrazioni germaniche, Via della Seta e Napoleone; script, fonti, timeline e anteprime sono conservati. Per visualizzarle: `generate.py --example via-della-seta --prepare-only`.

Il [rapporto di consegna](output/history_acceptance/report.md) raccoglie i sei casi, i risultati dei test, le anteprime, il film e i limiti della verifica del modello esterno.

È disponibile anche una [prova locale di Chatterbox Multilingual](tools/chatterbox/README.md), installata in un ambiente separato: campioni italiano/inglese, riferimento vocale opzionale e misure della CPU. È un banco di prova; il TTS dei documentari resta quello configurato nei pack.

La guida completa è [docs/GENERAL_HISTORY.md](docs/GENERAL_HISTORY.md); analisi e dipendenze sono in [docs/EXTENSION_ANALYSIS.md](docs/EXTENSION_ANALYSIS.md). Il vecchio flusso descritto sotto continua a funzionare.

## Nuova grafica geografica: Annibale

La produzione `battles/annibale/battle.json` usa il nuovo stile `atlas`: Europa e Mediterraneo a pieno schermo, base Natural Earth, coste e laghi vettoriali, rilievi Mapzen, zoom continui, minimappa di orientamento ed etichette stabili. Il film distingue le origini cartaginesi, la partenza dall’Iberia nel 218 a.C. e la minaccia alle porte di Roma nel 211 a.C.

Il video è `output/annibale_documentario_1080p.mp4`, circa 11 minuti, 1920×1080 a 30 fps. Resta disponibile il precedente stile con mappe operative. I file finali Waterloo e Stalingrado sono conservati.

Per riprodurre la cartografia su un ambiente già installato:

```powershell
./.venv/Scripts/python.exe tools/acquire_atlas.py --config battles/annibale/geography.json
./.venv/Scripts/python.exe tools/prepare_atlas.py --config battles/annibale/geography.json
./.venv/Scripts/python.exe documentary.py build --battle battles/annibale/battle.json --jobs 3
./.venv/Scripts/python.exe tools/check_atlas_final.py annibale
```

I primi due passaggi servono soltanto se gli asset geografici mancano. Le nuove regioni si definiscono con limiti geografici e aree di dettaglio in un file di configurazione, senza duplicare il renderer. Usare una cartella cartografica diversa per nuove revisioni, evitando di modificare raster mentre un rendering li legge. La pipeline rimane locale e gratuita dopo i download.

Il primo documentario è **Waterloo — Il tempo di una battaglia**, circa **9 minuti e 31 secondi**, 1920 × 1080, 24 fps. Il risultato è `output/waterloo_documentario_1080p.mp4`.

## Nuovi documentari con una richiesta

Apri questa cartella nell'assistente e chiedi, per esempio:

> Crea un documentario di 10 minuti sulla Battaglia di Austerlitz.

oppure:

> Crea un documentario di 15 minuti sulla Battaglia di Gettysburg.

`AGENTS.md` spiega all'assistente come svolgere autonomamente ricerca, scrittura, preparazione delle mappe, acquisizione dei ritratti, rendering e verifica riutilizzando il motore esistente. Non occorre montare scene o compilare dati a mano.

Nel flusso originale descritto in questa sezione, ricerca e sceneggiatura sono realizzate dall'assistente nella conversazione e `documentary.py` trasforma il battle pack documentato in video. Il nuovo `generate.py` può invece affidare ricerca e scrittura al modello configurato in Studio, riutilizzando lo stesso motore di produzione. Un modello esterno non è necessario per riprodurre i pack già preparati.

## File consegnati

| File | Contenuto |
|---|---|
| `output/waterloo_documentario_1080p.mp4` | Video completo H.264, AAC stereo, pronto per YouTube |
| `output/waterloo_it.srt` | Sottotitoli italiani, anche incorporati nel video come traccia opzionale |
| `output/youtube_description.txt` | Descrizione e timestamp dei capitoli |
| `output/verification/report.md` | Risultato della verifica sul file finale |
| `sources.md` | Fonti, divergenze e metodo storico |
| `script.md` | Testo narrato e timestamp reali |
| `timeline.json` | Scene, cue audio, unità, percorsi, coordinate e inquadrature |
| `credits.md` | Provenienza e licenze |

## Riprodurre Waterloo

L'ambiente e gli asset sono già presenti. In PowerShell, dalla cartella del progetto:

```powershell
./render.ps1
```

Su un altro computer Windows con Python 3.13:

```powershell
./setup.ps1
./render.ps1
```

Per un battle pack diverso:

```powershell
./render.ps1 -Battle battles/austerlitz/battle.json
```

I download servono soltanto per l'installazione e gli asset mancanti. Una volta presenti, voce, mappe, audio e montaggio funzionano senza rete. Non servono credenziali, editor video o servizi a pagamento. I due processi di rendering sono configurabili con `-Jobs 1` per computer con poca memoria.

## Comandi separati e ripresa del lavoro

```powershell
./.venv/Scripts/python.exe documentary.py validate
./.venv/Scripts/python.exe documentary.py assets
./.venv/Scripts/python.exe documentary.py voice
./.venv/Scripts/python.exe documentary.py preview
./.venv/Scripts/python.exe documentary.py render --jobs 2
./.venv/Scripts/python.exe documentary.py finalize
./.venv/Scripts/python.exe documentary.py verify
```

Tutti accettano `--battle percorso/battle.json`. `render --scenes 07,08` lavora solo su quelle scene. `render --scenes 02 --seconds 8` crea un campione breve; la finalizzazione rifiuta i campioni incompleti. Le scene già completate con gli stessi dati e lo stesso codice sono riutilizzate. Il tempo di calcolo dipende dalla CPU: il rendering può essere più lento della durata del video.

Per un confronto automatico fra voce e testo, facoltativo:

```powershell
./.venv/Scripts/python.exe -m pip install -r requirements-qa.txt
./.venv/Scripts/python.exe tools/check_speech.py
```

Il riconoscimento è locale con Whisper. Il punteggio è un'indicazione di controllo, non una certificazione fonetica: nomi stranieri, numeri e silenzi possono produrre errori del riconoscitore. I risultati sono conservati, non corretti artificialmente per alzare il punteggio.

## Architettura

| Modulo | Responsabilità |
|---|---|
| `engine/acquire.py` | Download di asset gratuiti, licenze, manifest SHA-256 |
| `engine/common.py` | Validazione, percorsi, utilità FFmpeg |
| `engine/narration.py` | Kokoro/Piper locali, pronunce, durata misurata, cue e sincronizzazione |
| `engine/cartography.py` | Proiezione geografica, campi, rilievi illustrativi, strade, fiumi e villaggi |
| `engine/visuals.py` | Camera, frecce, unità, ritratti, didascalie, cronologia e transizioni |
| `engine/sound.py` | Musica originale, vento, pioggia, marcia, cavalleria e artiglieria procedurali, attenuazione sotto la voce |
| `engine/render.py` | Rendering per scena, ripresa, encoding, loudness a due passaggi e MP4 finale |
| `engine/export.py` | Sceneggiatura, fonti, crediti, SRT, capitoli e descrizione |
| `engine/verify.py` | Decodifica completa, formati, conteggio frame, sincronizzazione, loudness e immagini del video finale |
| `battles/<slug>/battle.json` | Tutti i contenuti specifici della battaglia |

Lo schema e le convenzioni dei battle pack sono spiegati in `docs/BATTLE_PACK.md`. Nessun modello 3D o motore di gioco è necessario: l'effetto 2.5D deriva da rilievi ombreggiati, terreno illustrato, edifici con volume e movimento della camera. Gli schieramenti sono simbolici; non sono simulazioni militari al livello del singolo soldato.

## Fonti e riproducibilità

Ogni fonte ha un identificatore richiamato dalle scene. Le coordinate sono longitudine/latitudine; unità e percorsi sono una ricostruzione interpretativa. Le mappe non pretendono di rappresentare un rilievo topografico misurato nell’epoca rappresentata. Gli orari sono indicativi e i numeri non equivalgono a una forza esatta presente in ogni istante.

I ritratti originali sono in `assets/portraits/` con i metadati di Commons. I caratteri e le licenze OFL sono inclusi. Il modello vocale finale è Kokoro 82M, voce italiana `if_sara`, con pesi Apache-2.0. Piper/Paola resta disponibile come alternativa. Tutti i suoni del film sono generati dal codice e non usano registrazioni protette.

Il codice originale è MIT; gli asset originali procedurali sono CC0. Per i materiali di terzi fare riferimento a `credits.md`, alle licenze e al manifest. Non viene effettuato alcun caricamento su YouTube.


## Produzione Stalingrado

`output/stalingrado_documentario_1080p.mp4`: documentario italiano di circa 15 minuti, 30 scene, mappe urbane e operative, ritratti storici con licenze compatibili, musica ed effetti originali. Il pacchetto completo è in `battles/stalingrado/`; i controlli finali sono in `output/stalingrado_verification/`.

Sono disponibili anche `output/stalingrado_it.srt`, `output/stalingrado_copertina.jpg` e `output/stalingrado_youtube_description.txt`. La descrizione include i capitoli e le attribuzioni da conservare con il video. Il montaggio di Stalingrado è distribuito in CC BY-SA 4.0; i ritratti mantengono le rispettive licenze, documentate nei crediti. Il film Waterloo rimane conservato nel suo file originale.

Per riprodurlo: `./render.ps1 -Battle battles/stalingrado/battle.json`. La grafica riutilizza il motore, esteso con quartieri urbani, superfici fluviali, carri armati, aerei, linee di fronte e rapporti separati per produzione. Non servono altre API o abbonamenti.
