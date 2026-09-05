# Territori, confini e influenze

Il menu **Tipo di racconto** raggruppa le modalità esistenti in cinque famiglie: Conflitti, Territori e potere, Viaggi e scambi, Società e idee, Vite ed epoche. **Automatico** resta la scelta iniziale. I quattordici identificatori interni, i comandi CLI e le modalità dei progetti salvati rimangono compatibili.

Per conquiste, annessioni e perdite scegli **Imperi, espansioni e confini** (`territorial_expansion`); per alleanze, crisi e sfere d’influenza scegli **Geopolitica, alleanze e influenze** (`political_history`). La spiegazione sotto al menu cambia con la scelta, anche nelle impostazioni di rigenerazione.

## Cosa viene mostrato

La regia richiede territori colorati che conservano lo stato nel tempo, oltre alle eventuali frecce. Il motore distingue controllo territoriale, influenza, alleanze, aree culturali, linguistiche e religiose. Le zone contese hanno un tratteggio diagonale; le sovrapposizioni conservano entrambi i colori. La legenda chiarisce significato e precisione. Le inquadrature e l’acquisizione dell’atlante includono i vertici delle aree visibili, anche senza città di riferimento.

**Dalla 1.12.0 le nuove produzioni acquisiscono automaticamente geometrie da archivi datati.** Dopo la revisione editoriale e prima della compilazione delle mappe, il modello propone l’identità del territorio; il motore cerca nome e periodo negli archivi ammessi. Le coordinate del modello restano sempre schematiche: nessuna etichetta o bibliografia generata dal modello può certificarle.

## Archivi e uso didattico

In **Amministrazione → Confini storici e destinazione d’uso** scegli l’uso delle mappe:

- **Anche commerciale**, predefinito nelle nuove installazioni: [Cliopatria v0.2.0](https://github.com/Seshat-Global-History-Databank/cliopatria/tree/v0.2.0), Seshat Global History Databank, CC BY 4.0. Copertura generale dal 3400 a.C. al 2024 d.C.; la presenza del periodo non garantisce la copertura di ogni territorio. La legenda dice «ricostruzione da fonte».
- **Didattico non commerciale**: aggiunge [CShapes 2.0](https://icr.ethz.ch/data/cshapes/), ETH Zurich, codifica Gleditsch–Ward, 1886–2019, CC BY-NC-SA 4.0. Nel suo periodo ha precedenza quando esiste una corrispondenza univoca. Le mappe derivate conservano attribuzione, uso non commerciale e condivisione alle stesse condizioni. Non è un archivio di fronti o occupazioni militari.

Gli archivi sono scaricati dalle fonti ufficiali al primo utilizzo (circa 44 MB e 26 MB), verificati tramite SHA-256 e indicizzati localmente. La cache comune evita download ripetuti. L’indice occupa ulteriore spazio; non richiede GPU, LLM geografici o servizi a pagamento. URL, revisioni, impronte e licenze sono fissati in `pipeline/engine/boundary_sources.json`.

Il confronto dei nomi è esatto dopo normalizzazione e un piccolo dizionario di equivalenze linguistiche; l’eventuale ID Wikidata deve concordare quando presente nell’archivio. Repubblica, Regno e Impero Romano sono identità distinte. Il motore non sceglie arbitrariamente fra record ambigui. Mantiene le variazioni datate, anche più volte nello stesso anno, senza estendere un confine oltre la validità dichiarata.

Nel progetto compare **Confini e provenienza**: aree da archivio, copertura parziale e aree indicative. Nei **Materiali** sono disponibili i GeoJSON originali selezionati e il manifest; fonti, licenze e trasformazioni sono riportate nei crediti e nella descrizione esportata. La selezione è congelata nel progetto: Riprendi la riusa, Rigenera effettua una nuova selezione con le impostazioni correnti. I film già compilati non vengono modificati.

## Limiti storici e geografici

Un dataset pubblicato è una fonte tracciabile, non una garanzia di frontiere perfette. Le ricostruzioni antiche hanno risoluzione e incertezze proprie: [metodo di Cliopatria](https://www.nature.com/articles/s41597-025-04516-9). Il programma non calcola superfici storiche dalle aree illustrative e non sostituisce dati mancanti con confini moderni.

Gli archivi di sovranità non vengono usati per inventare aree religiose, linguistiche, culturali o d’influenza. Queste rimangono livelli tematici distinti, indicativi quando non documentati geometricamente. In caso di download fallito, identità ambigua, periodo scoperto o geometria non rappresentabile, il progetto segnala il limite e conserva soltanto le aree illustrative dichiarate, oppure nessuna area.

Sono supportati Polygon/MultiPolygon con isole e anelli interni. La carta Mercatore attuale non rappresenta territori polari, attraversamenti del cambio data o insiemi troppo estesi: questi casi richiedono un piano regionale; non vengono tagliati o riparati inventando coordinate. La ricerca testuale resta necessaria per interpretare e narrare le variazioni, indipendentemente dalla geometria.

## Contratto condiviso

Le nuove produzioni usano `visual_direction.territory_style: 2`. I documenti privi di questo campo mantengono la resa precedente. Ogni elemento di `visual_layers` ammette:

- `id`, `label`, `kind`: `territory`, `influence`, `alliance`, `contested`, `cultural`, `linguistic`, `religious`;
- `color`: tre interi RGB; `schematic`, `sources`, eventuali `geometry_source` e `label_pos`;
- `states`: sequenza di `{year, polygons, color?, contested?, label?}`; ogni poligono contiene coppie longitudine/latitudine;
- `transition_years`: durata illustrativa facoltativa della dissolvenza, senza implicare una misura storica.

Per la selezione automatica un territorio può aggiungere `boundary_query: {"name":"Roman Empire", "wikidata_id":"Q2277"}`. Il nome deve identificare la corretta entità nel periodo; Wikidata è facoltativo e va omesso se incerto. Dopo l’acquisizione il motore aggiunge `geometry_source`, `geometry_status`, `polygon_holes` e, negli stati, `at`/`valid_until` (inizio incluso, fine esclusa, asse continuo senza anno zero). Sono campi del motore: quelli provenienti dal modello vengono rimossi. Le geometrie acquisite cambiano alla data della fonte, senza interpolare frontiere inesistenti. I vecchi pack che usano solo `year` mantengono il comportamento precedente.

Ogni stato contiene **tutta** la geometria attiva da quella data. Il suo ID si conserva fra scene e stati; `polygons: []` rappresenta la perdita completa. `territory_ids` nella scena seleziona le aree: una lista vuota le nasconde, mentre l’assenza del campo include tutte quelle applicabili. Le scene che devono mantenere un’area la elencano esplicitamente. Le dissolvenze sono calcolate dal tempo assoluto: anteprime fuori ordine, ripresa e rendering producono lo stesso fotogramma.

## Verifica riproducibile

`tests/test_territories.py` controlla selezione delle modalità, continuità, perdite, stile, provenienza, compilazione, camera e copertura geografica. Per una prova video con un atlante già acquisito:

```powershell
pipeline\.venv\Scripts\python.exe tests\territories_smoke.py --base-work CARTELLA_CON_ASSET --atlas assets\geography\atlas-film\atlas.json --output data\qa-territories
```

La prova produce un MP4 silenzioso di 12 secondi, 1920×1080, con aree **fittizie**, tre anteprime, fotogrammi estratti dal video e rapporto di decodifica completa. Non chiama LLM o TTS e non modifica produzioni esistenti. La cartella dell’atlante è un argomento della prova; l’app resta autonoma e acquisisce i propri asset normalmente.

Per la prova con **archivi reali**, eseguire prima nell’ambiente app, poi nell’ambiente grafico:

```powershell
.venv\Scripts\python.exe tests\boundaries_smoke.py prepare --output data\qa-boundaries
pipeline\.venv\Scripts\python.exe tests\boundaries_smoke.py render --output data\qa-boundaries --base-work CARTELLA_CON_ASSET --atlas assets\geography\atlas-film\atlas.json
```

Il caso predefinito è Germania 1918–1920, con CShapes e uso non commerciale. `--name "Roman Empire" --label "Impero Romano" --years 27 117 --usage commercial` prova Cliopatria. La query editoriale è una fixture esplicita, mentre dataset, selezione, compilazione, esportazione e rendering sono reali. La suite automatica verifica inoltre cache, ripresa, licenze, ambiguità, buchi temporali, date a.C./d.C., anelli interni e mantenimento della provenienza fino alla timeline.
