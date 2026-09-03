# Analisi dell’estensione e dipendenze

## Componenti preesistenti riutilizzabili

Il percorso originale è documentary.py → common.validate_pack → acquire / narration → Visuals → render → sound / export → verify. Visuals disponeva già di due destinazioni: battaglia operativa e atlante geografico. La geometria delle mappe era già distinta dalla voce. Narration misurava cue e scene a fotogrammi interi; render concatenava MP4 e sound gestiva mix e attenuazione sotto il narratore.

Il sistema dei comandanti è un catalogo di persone con ritratti. Il contratto tecnico di scene/cue/audio è indipendente dalla storia narrata. Le frecce dell’atlante, invece, avevano un simbolo militare e la legenda “Avanzata”; il compilatore Studio richiedeva sempre due fazioni. Questi erano i punti da generalizzare.

## Scelta architetturale

Un adattatore versione 2 costruisce il contratto tecnico versione 1, conservando i campi editoriali generici. Un terzo percorso nella factory Visuals seleziona HistoryVisuals soltanto per visual_style=history. I renderer legacy non sono stati riscritti. HistoryVisuals usa RasterAtlas, proiezione, filtri e caratteri esistenti e compone territorio, flusso, rete, cronologia, scheda persona/opera, confronto e grafico.

La sintesi vocale riceve lo stesso formato lines e conserva Kokoro if_sara, cache, dizionario, chunk, keep-timing e misure. Due agganci condizionali aggiungono eventi/narrazione alla timeline nuova. Export conserva il percorso legacy e archivia i documentari generali in documentaries. Il rendering nuovo include nell’impronta di cache tutti i suoi moduli, dati globali e asset.

Studio continua a usare Outline/compile_pack per battle. HistoryOutline e il compilatore condiviso della pipeline accettano le nuove forme visuali. Ricerca, narrazione a gruppi, revisione, isolamento delle cartelle, coda, annullamento, download, TTS, rendering e verifica sono riusati. Le tabelle esistenti ricevono una colonna con valore legacy battle; le nuove richieste impostano auto. I checkpoint legacy sono riconosciuti anche dal contenuto.

## Protezioni prima delle modifiche

Copia dei sorgenti, documentazione e pack in backups/before-general-history-20260903; conservazione degli asset grandi in sede. Baseline di tre fotogrammi per ognuno dei tre film, con SHA dei pixel RGB e dei file video originali. La procedura di controllo riapre le timeline esistenti e confronta i risultati con la baseline; non usa solo una copia dei nuovi dati.

La copia dell’app precedente è nella sua cartella backups/before-general-history-20260903. I progetti e il database non sono stati sostituiti.
