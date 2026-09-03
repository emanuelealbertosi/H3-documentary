# Battle pack: contratto editoriale e tecnico

## Stile atlante geografico

`visual_style: "atlas"` seleziona `engine/atlas.py`; l’assenza del campo conserva lo stile precedente. Esempio completo: `battles/annibale/battle.json`. I dati geografici si preparano con `tools/acquire_atlas.py --config ...` e `tools/prepare_atlas.py --config ...`. Il file di configurazione contiene `bounds: [ovest,sud,est,nord]`, `patches` con rettangoli nello stesso ordine, `terrain_zoom` e una cartella `output` distinta per produzione/revisione. Le fonti geografiche e le licenze vanno conservate.

- `atlas` indica il manifest dei raster georeferenziati; `atlas_locator: [lon,lat,ampiezza_lon]` definisce la minimappa.
- **Nello stile atlas**, il terzo numero di `camera_start`, `camera_end` e `camera_keys[].view` è l’ampiezza orizzontale in gradi di longitudine, non il moltiplicatore di zoom dello stile precedente. `camera_keys[].at` è una frazione della durata. Le pose successive devono coincidere ai raccordi. La scala viene interpolata in forma logaritmica.
- `places` è un dizionario di `{name,pos,size?,color?,offset?}`; `visible_places` sceglie le località della scena, `label_offsets` ne fissa lo spostamento grafico. Non si ricalcolano collisioni a ogni fotogramma: controllare e correggere il layout in anteprima.
- `routes` contiene `{points,side,cue,end_cue?,complete?,alpha?,uncertain?,marker?}`. `complete` conserva un percorso già compiuto, `uncertain` usa tratti statici. `region_labels` contiene `{text,pos,size?}`; `callouts` contiene `{text,pos,cue,offset}`. `uncertainty_areas` contiene poligoni `points`.
- `river_names` seleziona i fiumi del dataset Natural Earth; `local_rivers` permette integrazioni esplicitamente documentate. Le forme attuali non vanno spacciate per ricostruzioni idrografiche antiche.
- `tactical_diagram` aggiunge un inserto schematico con `title`, `cue`, `panel`, unità `{side,pos,end}` e percorsi `{side,points}` in coordinate normalizzate; è indipendente dalla scala della carta geografica.
- `extra_credits` e `map_notice` vengono esportati nei crediti e nella descrizione YouTube; `commanders[].portrait_note` fornisce due righe sul ritratto.

Il motore usa mappe immutabili, mipmap interpolate, sovracampionamento 2× degli elementi vettoriali e nessun passaggio a nero fra capitoli. Non aggiungere texture casuali per fotogramma o riposizionamenti automatici delle etichette durante gli zoom. Il test `tools/check_atlas_final.py <slug>` misura eventuali lampi globali nel file codificato, oltre alla verifica ordinaria.

Il battle pack è un JSON UTF-8 con `schema_version: 1`. L'esempio completo e funzionante è `battles/waterloo/battle.json`. Il motore lavora con dati, senza richiedere un file Python per ogni nuova battaglia.

## Metadati

- `slug`: nome cartella/output, ad esempio `austerlitz`.
- `title`, `short_title`, `subtitle`, `display_date`, `description`: testi del documentario.
- `language`, `date`: lingua e data ISO.
- `target_minutes`, `min_minutes`, `max_minutes`: durata richiesta e intervallo accettato. Sono configurabili anche per 15 o più minuti.
- `width: 1920`, `height: 1080`, `fps: 24`, `output: output/<slug>_documentario_1080p.mp4`.
- `sources`: oggetti `{id, title, url, use}`. `use` distingue contenuti realmente consultati da semplici riferimenti di catalogo.
- `editorial_notes`, `source_method`, `territorial_note`: incertezze, criteri di ricostruzione e contesto geografico.

## Voce e asset

La configurazione locale predefinita riutilizzabile è:

```json
{
  "voice_engine": "kokoro",
  "voice": "assets/voice/kokoro/kokoro-v1.0.onnx",
  "voice_styles": "assets/voice/kokoro/voices-v1.0.bin",
  "voice_speaker": "if_sara"
}
```

`pronunciation` è un dizionario di sostituzioni usato solo nel TTS. `lines` e sottotitoli mantengono la grafia corretta. Non trasformare sistematicamente tutti i nomi in grafie fonetiche: confronta la resa sul campione vocale. `voice_credit` descrive il modello effettivamente scelto.

Per correggere un difetto locale della sintesi, `voice_sentence_chunks` o `voice_clause_chunks` selezionano cue nel formato `"13:1"` (scena e indice da zero) da sintetizzare in frammenti. `voice_custom_chunks` permette una segmentazione esplicita: unendo i frammenti con spazi si deve ottenere esattamente il testo originale. `voice_phoneme_overrides` contiene sostituzioni fonetiche per singolo cue, da usare soltanto dopo una verifica. Queste impostazioni entrano nella cache vocale e non alterano i sottotitoli. Con testo invariato, `voice --keep-timing` conserva la durata delle scene e adatta soltanto l’audio, rifiutando variazioni eccessive. Un controllo ASR locale è un aiuto per individuare difetti; nomi propri, numeri e silenzi possono generare errori del riconoscitore.

`voice_chunk_assets` può conservare un frammento vocale locale già verificato: per cue e indice di frammento, indica `{path,text}`. Il testo deve coincidere con quello pronunciato; l’audio deve essere PCM mono 24 kHz a 16 bit. Il contenuto del file entra nell’impronta della cache. Conservare provenienza e controllo del frammento accanto all’asset. Non usare questa possibilità per introdurre parole estranee alla sceneggiatura.

`assets` è una lista di `{path, url, license, source?}`. `documentary.py assets` scarica solo file mancanti. I checksum sono conservati in `assets/manifest.json`. Le immagini scaricate da Commons richiedono una licenza compatibile.

## Fazioni e comandanti

`factions` contiene `{id, label, color: [r,g,b], estimate, commander, note?}`. Gli identificatori sono liberi e sono usati da unità, frecce e zone. Non riusare nomi francesi/prussiani in una battaglia diversa se non pertinenti.

`commanders` è un dizionario da identificatore a `{name, subtitle, side, portrait, wikipedia_page}`. Un ritratto locale deve avere il relativo `<nome>.metadata.json` con provenienza e licenza. `framing` associa un comandante a `[left, top, right, bottom]` fra 0 e 1 per inquadrare il ritratto nel video senza modificare il file originale.

## Mappe

Ogni oggetto in `maps` contiene:

- `center: [lon, lat]` e `scale: [pixel_per_degree_longitude, pixel_per_degree_latitude]`.
- `seed`: intero per una resa procedurale riproducibile.
- `north_label`, `region_label`: annotazioni appropriate alla geografia e all'epoca.
- `landmarks`: `{id, name, pos:[lon,lat], kind}`; tipi `town`, `farm`, `ridge`, `forest`.
- `roads`, `rivers`: `{name, points:[[lon,lat],...]}`.
- `ridges`: `{pos, amplitude, width:[lon_width,lat_width]}`. Sono rilievi illustrativi, non altimetria reale certificata.
- `forests`: `{pos, radius:[lon_radius,lat_radius]}`.
- `zones`: `{side, points}` per le aree d'influenza. Possono essere sovrascritte dalla scena.

Le chiavi convenzionali `campaign` e `battle` determinano soltanto la scala grafica di campi ed edifici; coordinate, strade, località e colori sono forniti dal pack. La mappa mantiene sempre il nord in alto. L'asse verticale è compresso visivamente per l'effetto 2.5D.

## Scene e cue

Ogni scena contiene:

- `id`: numero a due cifre, univoco.
- `title`, `kicker`, `date`, `note`: titolo, spiegazione, intervallo storico e nota di ricostruzione.
- `lines`: elenco di frasi/paragrafi da sintetizzare separatamente. Nessun timestamp scritto a mano: viene misurato dall'audio.
- `map`, `camera_start`, `camera_end`: nome mappa e `[lon,lat,zoom]` per la camera.
- `units`, `arrows`, `commanders`, `facts`, `focus`, `sources`, `sfx`.
- `mode`: opzionale; `opening` e `ending` aggiungono i titoli; `aftermath` nasconde le zone d'influenza.

Un'unità è `{id,label,side,pos,kind,count,path,cue,until}`. `count` è il numero di simboli aggregati, **non** un numero di soldati. Tipi grafici: `infantry`, `cavalry`, `artillery`, `square`. `path` è una sequenza geografica; l'animazione comincia al cue indicato, cioè all'indice (da zero) della frase associata. `until` può nascondere un'unità da un certo cue.

Una freccia è `{side,points,cue,end_cue,kind}`. Tipi: `attack`, `retreat`, `plan`, `move`, `fire`. Il percorso esprime la direzione; il motore disegna la crescita, la punta e l'animazione. Le ritirate e il fuoco sono tratteggiati.

Un ritratto viene introdotto da `{id,cue}` in `commanders`. Un punto geografico viene evidenziato da `{place,cue,side?}` in `focus`. Gli effetti sono `{type,cue}`: `cannon`, `musket`, `march`, `cavalry`, `rain`, `transition`.

## Output della sintesi

Il generatore aggiunge `start`, `end`, `duration`, `frames`, `audio` e `cues` a ogni scena. Ogni cue conserva testo originale, testo pronunciato e intervallo misurato. La durata è arrotondata a fotogrammi interi. L'audio è convertito a 48 kHz e le scene si concatenano senza deriva progressiva.

La finalizzazione richiede tutte le scene complete, aggiunge musica, effetti, capitoli, sottotitoli e loudness normalizzata. La verifica controlla l'MP4 prodotto, non solo i file intermedi. Conservare fonti, script, timeline e crediti anche in `battles/<slug>/`.

## Mappe urbane e operazioni moderne

Stalingrado (`battles/stalingrado/battle.json`) dimostra l'uso dello stesso motore per una campagna del Novecento, su più scale.

- Mappe: `water: [{points}]` disegna superfici fluviali; `districts: [{points}]` genera quartieri con edifici in rilievo; `palette: [r,g,b]` imposta il terreno; `scale_km` sceglie la scala metrica. `show_river_names` abilita i nomi dei fiumi su qualsiasi mappa.
- Località e fiumi: `label_offset: [dx,dy]` sposta soltanto l'etichetta, lasciando il punto geografico corretto. `visible_places` nella scena seleziona i nomi pertinenti.
- Unità: `armor` usa l'ovale dei mezzi corazzati, `air` il simbolo dei trasporti aerei. `count` rimane un numero di simboli aggregati.
- Scene: `frontlines: [{side,points,cue,until?}]` permette linee di fronte o anelli di accerchiamento. Restano ricostruzioni schematiche.
- Ritratti: `commons_file` seleziona un file preciso quando Wikipedia non offre un ritratto; `image_credit` mostra un'attribuzione breve. Il documento dei crediti conserva attribuzione richiesta, scheda originale e link alla licenza.
- Output: `verification_dir: "<slug>_verification"` mantiene separato il rapporto; `output/<slug>_youtube_description.txt` conserva descrizione e crediti di ogni produzione. I documenti alla radice rappresentano l'ultima produzione; le copie in `battles/<slug>/` preservano le precedenti.
- `video_license`, se presente, dichiara la licenza scelta per il montaggio e aggiunge le attribuzioni dei ritratti alla descrizione YouTube. Controllare il limite di 5.000 caratteri.
- `max_voice_tempo` permette un limite di adattamento specifico del testo; il default resta 1,22. Stalingrado usa un fattore effettivo di circa 1,254 per 2.588 parole e 15 minuti. Verificare la comprensibilità dopo l'adattamento.

Per controllare le inquadrature mentre la voce è ancora in generazione, `tools/preview_pack.py battles/<slug>/battle.json` produce un'anteprima con tempi stimati in `build/<slug>/layout`, senza modificare la timeline misurata. Le anteprime ufficiali e il rendering usano sempre i tempi della voce.
