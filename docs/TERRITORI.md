# Territori, confini e influenze

Il menu **Tipo di racconto** raggruppa le modalità esistenti in cinque famiglie: Conflitti, Territori e potere, Viaggi e scambi, Società e idee, Vite ed epoche. **Automatico** resta la scelta iniziale. I quattordici identificatori interni, i comandi CLI e le modalità dei progetti salvati rimangono compatibili.

Per conquiste, annessioni e perdite scegli **Imperi, espansioni e confini** (`territorial_expansion`); per alleanze, crisi e sfere d’influenza scegli **Geopolitica, alleanze e influenze** (`political_history`). La spiegazione sotto al menu cambia con la scelta, anche nelle impostazioni di rigenerazione.

## Cosa viene mostrato

La regia richiede territori colorati che conservano lo stato nel tempo, oltre alle eventuali frecce. Il motore distingue controllo territoriale, influenza, alleanze, aree culturali, linguistiche e religiose. Le zone contese hanno un tratteggio diagonale; le sovrapposizioni conservano entrambi i colori. La legenda chiarisce significato e precisione. Le inquadrature e l’acquisizione dell’atlante includono i vertici delle aree visibili, anche senza città di riferimento.

**Le coordinate generate dal modello sono schematiche.** La pipeline le marca sempre come tali; non acquisisce automaticamente confini storici verificati. Per contorni documentati, un pack preparato con dati geografici controllati può specificare `schematic: false` e deve indicare `geometry_source`, oltre alle fonti editoriali. Non basta un riferimento bibliografico generico per rendere precise le coordinate. I confini moderni non sostituiscono quelli di un’epoca precedente. Quando l’evidenza non permette neppure una delimitazione indicativa, il piano deve usare città e relazioni e dichiarare il limite. Nessun dato di superficie viene calcolato dai poligoni illustrativi.

## Contratto condiviso

Le nuove produzioni usano `visual_direction.territory_style: 2`. I documenti privi di questo campo mantengono la resa precedente. Ogni elemento di `visual_layers` ammette:

- `id`, `label`, `kind`: `territory`, `influence`, `alliance`, `contested`, `cultural`, `linguistic`, `religious`;
- `color`: tre interi RGB; `schematic`, `sources`, eventuali `geometry_source` e `label_pos`;
- `states`: sequenza di `{year, polygons, color?, contested?, label?}`; ogni poligono contiene coppie longitudine/latitudine;
- `transition_years`: durata illustrativa facoltativa della dissolvenza, senza implicare una misura storica.

Ogni stato contiene **tutta** la geometria attiva da quella data. Il suo ID si conserva fra scene e stati; `polygons: []` rappresenta la perdita completa. `territory_ids` nella scena seleziona le aree: una lista vuota le nasconde, mentre l’assenza del campo include tutte quelle applicabili. Le scene che devono mantenere un’area la elencano esplicitamente. Le dissolvenze sono calcolate dal tempo assoluto: anteprime fuori ordine, ripresa e rendering producono lo stesso fotogramma.

## Verifica riproducibile

`tests/test_territories.py` controlla selezione delle modalità, continuità, perdite, stile, provenienza, compilazione, camera e copertura geografica. Per una prova video con un atlante già acquisito:

```powershell
pipeline\.venv\Scripts\python.exe tests\territories_smoke.py --base-work CARTELLA_CON_ASSET --atlas assets\geography\atlas-film\atlas.json --output data\qa-territories
```

La prova produce un MP4 silenzioso di 12 secondi, 1920×1080, con aree **fittizie**, tre anteprime, fotogrammi estratti dal video e rapporto di decodifica completa. Non chiama LLM o TTS e non modifica produzioni esistenti. La cartella dell’atlante è un argomento della prova; l’app resta autonoma e acquisisce i propri asset normalmente.
