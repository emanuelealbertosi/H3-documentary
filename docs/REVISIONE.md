# Revisione facoltativa di testi, luoghi e immagini

La pausa per la revisione permette di correggere i materiali già preparati prima
della voce e del video. Puoi usare soltanto la gestione immagini, soltanto il
testo, soltanto la mappa oppure nessuno di questi strumenti.

## Fermare la produzione nel punto giusto

Attiva **Fermati per la revisione** quando crei un progetto o nelle
**Impostazioni per la prossima versione** di un progetto esistente. L'app prepara
ricerca, sceneggiatura, geografia, immagini e anteprime provvisorie, poi si ferma.
Se un elemento visuale non è recuperabile, può già richiedere questa pausa per
mostrare una scheda da completare.

Nel progetto in revisione, apri **Rivedi il racconto e i luoghi**. Non occorre
abilitare un nuovo modello o installare un altro programma. Le produzioni già in
corso non vengono modificate durante il rendering. Per un film completato usa
**Riapri revisione**, disponibile nella pagina del progetto.

## Correggere un film completato nello stesso progetto

**Riapri revisione** rende nuovamente disponibili testi, luoghi e immagini.
Modifica soltanto ciò che ti serve, poi premi **Aggiorna questo video**.
Il pulsante salva anche i testi ancora aperti nell'editor. Non crea V2/V3,
non ripete la ricerca e non riscrive il racconto con il modello.

- Le immagini aggiornano le scene in cui compaiono.
- Il testo corretto viene risintetizzato conservando voce, riferimento e
  impostazioni del film. Le frasi ancora valide vengono riutilizzate dalla cache;
  tutti gli audio delle scene intatte vengono conservati.
- I luoghi aggiornano percorsi e inquadrature collegati. Se necessario si
  prepara nuovamente la base geografica e si aggiornano le scene che la mostrano.
- Se cambia la durata della voce o un elemento grafico comune, possono servire
  altre scene per mantenere coerenti timeline e localizzatori. Il diario lo indica.

Il montaggio finale, i sottotitoli e i controlli integrali vengono rifatti sul
video aggiornato. Il film precedente resta scaricabile durante il lavoro e viene
conservato in una copia locale prima della sostituzione verificata. Se un servizio
TTS o il rendering fallisce, il vecchio film resta disponibile e la revisione
può essere corretta e ritentata. Lo stesso vale dopo un'interruzione dell'app.
Non occorre collegare un LLM per applicare correzioni manuali.

**Annulla revisione** ripristina testo, luoghi e scelte visuali salvati prima
dell'apertura; le immagini aggiunte alla libreria restano riutilizzabili. Il film
non cambia finché non premi **Aggiorna questo video** e la verifica riesce.
Le presentazioni PDF già esportate vengono conservate: crea un altro PDF se vuoi
includere le nuove correzioni. **Prepara nuova versione** resta il comando per
cambiare struttura, argomento o fonti e ripartire dalla ricerca.

## Rivedere il testo narrato

In **Testo narrato**, scegli una scena e correggi le frasi nei campi **Passaggio**.
Quello che scrivi diventa
la narrazione usata dal TTS alla continuazione della produzione. Puoi correggere
un nome, togliere ripetizioni, spiegare meglio un passaggio o riscrivere le parole
che la voce dovrà leggere.

Ogni campo conserva il collegamento con le animazioni del proprio paragrafo. Per
questo la revisione mantiene il numero di paragrafi della scena: non introduce
nuove scene e non elimina i riferimenti delle animazioni. Per cambiare la
struttura complessiva del racconto usa invece le indicazioni editoriali di una
nuova versione.

La voce e i tempi vengono ricalcolati dal testo corretto. La durata finale può
quindi cambiare: allungare un paragrafo non richiede di comprimerne artificialmente
la lettura nella durata precedente. Se una destinazione non compare più nel
testo della sua animazione, il progetto segnala il collegamento da controllare.
Le modifiche manuali non sono riscritte dal modello né presentate come una nuova
verifica storica indipendente.

**Ripristina testo originale** recupera le parole precedenti alla revisione,
anche dopo un salvataggio. **Annulla modifiche non salvate** torna invece
all'ultima bozza salvata della scena.

## Correggere un luogo sulla mappa

In **Luoghi sulla mappa**, seleziona un luogo già presente nel progetto. Puoi
trascinarne il segnaposto, usare **Posiziona sulla mappa** e fare clic sul punto
corretto oppure aprire le coordinate avanzate e modificarne longitudine e
latitudine. La nuova posizione resta una bozza finché
non salvi; la selezione mostra anche le scene che usano quel luogo.
**Ripristina posizione originale** annulla lo spostamento rispetto ai materiali
preparati dalla pipeline; puoi poi salvare nuovamente la revisione.

La mappa di base è inclusa nell'app e funziona offline. Mostra le terre emerse
Natural Earth con coste generalizzate: serve a orientarsi, non a stabilire con
precisione archeologica dove si trovasse un sito antico. Il dettaglio
OpenStreetMap è facoltativo, richiede Internet e mostra cartografia e nomi moderni.

La correzione aggiorna la località e gli estremi dei percorsi che vi sono
collegati, quindi adatta le inquadrature interessate. I waypoint non associati
restano come erano; una localizzazione manuale non riscrive un itinerario né
deforma i confini storici provenienti dagli archivi. Se due luoghi condividono lo
stesso punto, i collegamenti ambigui non vengono reinterpretati automaticamente.

Non usare lo spostamento per trasformare un luogo in un altro: un cambiamento
del soggetto, delle fonti o delle tappe narrative appartiene alla rigenerazione.
Per correggere un punto geograficamente incerto puoi anche conservare il testo
esplicativo e sostituire la scena con una mappa o un'immagine caricata.

## Salvare e continuare

Usa **Salva la revisione** prima di lasciare l'editor. Le correzioni vengono conservate
nel singolo progetto; non alterano i dati geografici o gli asset condivisi dagli
altri film. Un conflitto tra due finestre viene segnalato prima di sovrascrivere
la bozza più recente.

**Continua produzione** salva anche le modifiche ancora presenti nell'editor e
applica le correzioni, conserva una copia dei materiali
precedenti e riprende le fasi necessarie. Se hai spostato luoghi, aggiorna la
preparazione geografica; la voce, la timeline e il rendering usano il nuovo
contenuto. Gli errori dei servizi o i limiti geografici continuano a essere
segnalati, senza inventare una posizione o cancellare le correzioni salvate.

Se non vuoi correggere testi o luoghi, lascia chiuso il pannello e continua
normalmente: il flusso automatico precedente resta disponibile.

Per sostituire o escludere un'illustrazione, usa la
[gestione immagini](IMMAGINI.md). Per regolare interpretazione, velocità e pause,
vedi [voce e server TTS](TTS_API.md). Le
[licenze della mappa di revisione](../static/licenses/review-map.md) sono incluse
nel repository e nella distribuzione.
