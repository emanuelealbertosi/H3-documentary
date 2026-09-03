# Documentari storici visuali

L’estensione aggiunge un formato editoriale generale e un renderer composto sopra l’atlante geografico esistente. Il formato battle versione 1 e i tre film già prodotti rimangono validi. Non occorre convertirli.

## Un comando per una nuova storia

```powershell
./.venv/Scripts/python.exe generate.py "Espansione dell’Impero Romano dal 264 a.C. al 117 d.C." --duration 12m
./.venv/Scripts/python.exe generate.py "Diffusione del Rinascimento in Europa" --duration 10m --type cultural_movement
```

Una richiesta nuova usa Studio nella cartella accanto (`documentariAI-app`) e il modello configurato nella pagina Amministrazione. Il comando avvia Studio se necessario, crea il progetto, segue la produzione e restituisce il percorso dell’MP4 verificato. `--no-wait` restituisce subito il collegamento alla produzione. Chiavi e connessione restano nel backend: non vengono passate sulla riga di comando.

Serve una configurazione iniziale del server: LM Studio, Ollama, vLLM oppure un endpoint Chat Completions compatibile. Un modello gratuito su un altro computer evita la necessità di una GPU locale. Il sistema non include un LLM capace di ricercare un argomento dal nulla senza questa connessione. Non vengono attivate API a pagamento automaticamente. La qualità della ricerca dipende anche dal modello e dalle fonti accessibili; la revisione automatica non sostituisce una valutazione storiografica indipendente.

Per i materiali già preparati non occorre alcun LLM:

```powershell
./.venv/Scripts/python.exe generate.py --example rinascimento
./.venv/Scripts/python.exe generate.py --example via-della-seta --prepare-only
./.venv/Scripts/python.exe generate.py --pack documentaries/rinascimento/documentary.json
./.venv/Scripts/python.exe documentary.py preview --document documentaries/rinascimento/documentary.json
```

`--prepare-only` esporta ricerca documentata, script, timeline **stimata** e immagini rappresentative. Non produce una finta timeline vocale. Le scene temporizzate realmente dal TTS sono in `build/<slug>/timeline.json`. Una durata diversa richiede una nuova sceneggiatura: non viene ottenuta accelerando arbitrariamente un film esistente.

## Tipi e struttura comune

`engine/history_profiles.py` contiene quattordici strategie: battle, war, territorial_expansion, migration, cultural_movement, religious_expansion, trade_network, exploration, political_history, revolution, economic_history, technology_history, biography, general_history. Il riconoscimento lessicale seleziona una prima strategia; per il percorso generale il modello può raffinarla sulla base delle fonti, salvo un tipo imposto dall’utente.

Le strategie suggeriscono struttura narrativa, tono e componenti. La scelta della scena deriva dal contenuto: un’immagine richiede una scena di opera/documento, una persona può richiedere un’introduzione, una rete ha nodi e relazioni, dati numerici documentati hanno grafici. I campi sono estensibili; non esistono quattordici programmi separati.

L’analisi editoriale comprende periodo, geografia, protagonisti, città, entità, eventi, cronologia, cause, conseguenze, cambiamenti territoriali, spostamenti, reti, rotte, flussi, alleanze, conflitti, cambiamenti culturali e politici, quantità e incertezze. Le informazioni non disponibili vanno dichiarate, non completate con numeri inventati.

## Contratto editoriale versione 2

I nuovi pack vivono in `documentaries/<slug>/documentary.json`. Campi principali:

- `schema_version: 2`, `documentary_type`, `slug`, `title`, `target_minutes`.
- `metadata`, `historical_period: {start,end,calendar}`, `sources`.
- `locations: [{id,name,pos:[lon,lat]}]`.
- `persons: [{id,name,role,period,intro,portrait?,wikipedia_page?,events?}]`.
- `entities`, `events`, `visual_layers`, `visual_assets`, `scenes`.

Gli anni sono storici: `-264` significa 264 a.C.; `117` significa 117 d.C.; non esiste l’anno zero. I campi aggiuntivi non vengono cancellati. Un evento può avere luogo, soggetti, descrizione, importanza, visualizzazione consigliata, testo e note. I tipi comprendono battaglie, trattati, migrazioni, cambiamenti territoriali, fondazioni, crolli, scoperte, invenzioni, eventi culturali/politici/economici/religiosi, nascite, morti, incoronazioni, rivoluzioni, alleanze e cambiamenti delle rotte.

`engine/history_schema.py` valida i riferimenti e adatta il documento al contratto di rendering già esistente. Produce i campi tecnici necessari a TTS, audio e montaggio senza richiederli all’autore. La timeline conserva `documentary`, `metadata`, `historical_period`, `locations`, `persons`, `entities`, `events`, `scenes`, `visual_layers`, `narration`, `sources`. `documentary_schema_version: 2` distingue l’origine editoriale; `schema_version: 1` segnala il contratto di esecuzione compatibile. I timestamp degli eventi sono collegati ai cue e alle scene. `timing_status` distingue le stime dai tempi misurati.

## Componenti visuali

Le scene disponibili sono map_overview, territorial_change, animated_route, timeline, person_intro, event_focus, comparison, battle, city_focus, network_map, data_visualization, quote, artwork, document, transition, summary.

Le mappe riusano Natural Earth, rilievi, fiumi, zoom e filtri dell’atlante esistente. Luoghi ed etichette rimangono in coordinate geografiche con nord in alto. `region_labels` può identificare mari e regioni. `local_rivers` integra corsi d’acqua documentati. Le strade e i corridoi sono linee geografiche con una semantica dichiarata.

I livelli territoriali hanno `id`, `kind`, `label`, `sources`, `schematic`, `color`, `states`. Ogni stato contiene `year`, `polygons` ed eventualmente colore e `contested`. Lo stato resta visibile fino al successivo: poligoni vuoti rimuovono l’area, colori successivi rappresentano cambiamenti di controllo. `transition_years` permette dissolvenze tra stati. I tipi di area includono territory, influence, cultural, linguistic, religious, alliance, contested. Un livello schematico ha contorni tratteggiati. Le aree religiose non devono essere ricavate automaticamente dalle conquiste politiche.

I movimenti contengono punti, cue, fonti e `semantic`: migration, population_transfer, trade, sea_trade, cultural_diffusion, religious_diffusion, technology_diffusion, journey, exploration, connection, influence, attack, invasion, campaign, retreat, expansion. I movimenti civili usano punti di flusso; le punte militari compaiono solo con una semantica militare esplicita. Spessore e numero dei punti non indicano una popolazione.

Una rete usa nodi riferiti alle città e archi `{from,to,semantic,sources,points?,uncertain?}`. Gli archi possono cambiare tra scene. Una biografia alterna ritratti, cronologia, documenti e spostamenti personali. Le scene di opere mostrano immagini originali integre con un lieve movimento della camera, autore, data e attribuzione. Un ritratto non disponibile ha una scheda tipografica dichiarata, non un volto inventato.

I grafici supportano barre, linee e confronti numerici. `chart` contiene tipo, titolo, unità, valori `{label,value,x?}`, fonti e note. Le linee usano `x` quando la distanza temporale conta. Valori mancanti o non finiti sono rifiutati. Confronti qualitativi usano invece colonne di testo, senza inventare una scala quantitativa.

## Fonti e materiali

Ogni scena, evento, area e movimento cita fonti presenti nel documento. `certainty` degli eventi distingue established, estimate, interpretation e controversial. Le stime e le controversie vanno spiegate anche nella narrazione e nei cartelli quando rilevanti. Il test romano usa regioni schematiche selezionate, **non** confini imperiali esatti né superfici in km².

`visual_assets` gestisce dipinti, incisioni, fotografie, manoscritti, monumenti, reperti, bandiere, stemmi, ritratti, icone e illustrazioni originali tramite un unico catalogo. Ogni elemento conserva percorso, titolo, autore, data, provenienza, licenza e attribuzione. Il downloader riusa il controllo di licenza Commons e ammette URL pubblici documentati. Gli esempi culturali usano Met Open Access; metadati e SHA sono in `assets/history/manifest.json`. Le pagine conservabili direttamente sono in `assets/research/history`; `research.json` segnala quelle consultate via browser ma non scaricabili direttamente.

## Verifiche e limiti pratici

La copia precedente è in `backups/before-general-history-20260903`. `tools/compatibility_baseline.py --check` confronta nove fotogrammi e i tre video originali. `tests/test_history.py` esercita i nuovi contratti e componenti. Studio conserva i suoi test precedenti e aggiunge quelli del compilatore e della migrazione del database.

Le prove editoriali sono Roma, Rinascimento, migrazioni germaniche, Vie della Seta, Napoleone; Waterloo resta il controllo della pipeline precedente. Le anteprime sono in `build/<slug>/layout`. Il Rinascimento è una produzione completa di circa sette minuti. Le altre sono studi narrativi brevi, con timeline dichiaratamente stimate; non sono sei film completi.

`generate.py` ricostruisce gli atlanti mancanti quando è disponibile il relativo `geography.json`, usando gli strumenti geografici preesistenti. Dopo la voce controlla e corregge le inquadrature dei luoghi focali; dopo l’MP4 esegue anche il controllo dei lampi. I comandi granulari `documentary.py` restano disponibili con il loro comportamento precedente.

Il controllo MP4 decodifica tutti i fotogrammi e l’audio, misura sincronizzazione e loudness, controlla capitoli e sottotitoli ed estrae immagini dal file codificato. `tools/check_history_final.py` cerca lampi **dentro** le scene e registra separatamente i tagli intenzionali fra mappe e opere. Non certifica ogni forma di aliasing locale. Il controllo ASR è un ausilio: numeri e nomi stranieri possono ridurre la corrispondenza senza indicare errori equivalenti nel parlato.

L’atlante Mercatore limita le viste alle latitudini supportate e rifiuta teatri troppo ampi o a cavallo della linea del cambio data: questi richiedono una divisione editoriale. L’estensione non crea confini storici esatti a partire dal solo nome di un impero. Se mancano dati sufficienti usa regioni dichiaratamente schematiche o un’altra forma visiva.
