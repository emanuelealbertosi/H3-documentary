# Presentazioni PDF

H3-documentary 1.14.0 può esportare una presentazione PDF dalle scene del progetto. Il PDF riusa mappe, percorsi, riquadri e materiali locali della stessa versione, con testo selezionabile. È un risultato separato dall’MP4: non richiede una nuova ricerca, una riscrittura della narrazione o una nuova sintesi vocale.

## Creare e scaricare una presentazione

1. Apri il progetto e raggiungi **Presentazione PDF**, sotto il riquadro del video.
2. Scegli **Compatta** oppure **Didattica**.
3. Lascia selezionato **Includi il testo narrato originale** se vuoi usarlo come spiegazione nelle pagine.
4. Premi **Crea PDF**. La stessa sezione mostra avanzamento, risultato e collegamenti per scaricare le presentazioni già pronte.

Il comando diventa disponibile quando il progetto contiene la timeline preparata con i tempi delle frasi e gli asset necessari. Può quindi essere usato anche prima di avere un MP4 completato. Durante una produzione occorre aspettarne la fine o interromperla: esportazione e modifiche del progetto non lavorano contemporaneamente sugli stessi file.

| Variante | Contenuto visuale |
|---|---|
| Compatta | Un’immagine riepilogativa per scena, con lo stato finale della scena |
| Didattica | Passaggi associati alle frasi; per i percorsi vengono mostrati partenza e sviluppo/arrivo, insieme ai riquadri collegati |

**Compatta** limita il numero di immagini, non la quantità del testo richiesto. Se includi la narrazione, il testo originale prosegue su pagine aggiuntive quando serve. La modalità didattica riporta il testo nel passaggio pertinente senza ripeterlo su ogni immagine dello stesso passaggio. Togliere la spunta esclude la narrazione dalle pagine; **fonti e crediti restano inclusi**.

Le mappe nel PDF sono immagini statiche generate dal motore esistente con un’inquadratura adatta alla scena. Mantengono luoghi e geometrie del progetto, ma una pagina non riproduce l’animazione o l’audio del film. Per mostrare il movimento continuo resta disponibile il video.

## Versioni, fonti e licenze

Ogni esportazione crea un nuovo PDF e conserva quelli precedenti. I download restano visibili anche quando un tentativo successivo fallisce. Puoi produrre, ad esempio, una versione compatta senza testo per la proiezione e una didattica con la spiegazione originale per lo studio.

L’esportazione copia nelle pagine i riferimenti del progetto e le attribuzioni dei materiali della versione corrente. Non svolge una verifica storica aggiuntiva e non corregge fatti o fonti mancanti: conserva anche le indicazioni di incertezza già presenti. Le condizioni delle immagini e delle mappe, incluse quelle non commerciali o di condivisione alle stesse condizioni, valgono anche quando i materiali sono distribuiti nel PDF.

I file si trovano nel workspace del progetto, sotto `output/presentations/`. Accanto al PDF viene scritto un manifest JSON con le opzioni, le scene e gli istanti utilizzati, il conteggio delle pagine e le impronte dei file. I fotogrammi intermedi rimangono nella sottocartella `.frames`. La timeline, la sceneggiatura e il video esistenti non vengono riscritti.

Se chiudi H3 durante un’esportazione, alla riapertura il progetto segnala l’interruzione e permette di creare nuovamente il PDF. I PDF già completati restano disponibili. Un errore di esportazione non richiede di rifare il documentario.

## Esportare da terminale

L’interfaccia prepara automaticamente percorsi e nomi univoci. Per un uso riproducibile da codice è disponibile anche il comando seguente, eseguito dalla cartella dell’app. Sostituisci `ID-PROGETTO` con l’identificativo della produzione:

```powershell
$presentationWorkspace = (Resolve-Path '.\data\jobs\ID-PROGETTO\workspace').Path
$presentationFile = Join-Path $presentationWorkspace 'output\presentations\lezione.pdf'
.\pipeline\.venv\Scripts\python.exe .\pipeline\tools\export_presentation.py --workspace $presentationWorkspace --output $presentationFile --variant teaching --narration full
```

`--variant` accetta `compact` o `teaching`; `--narration` accetta `full` o `none`. Il percorso di uscita deve essere assoluto e interno a `output/presentations` di quel progetto. Se il PDF o il suo manifest esistono già, scegli un nuovo nome: il comando conserva i risultati precedenti.

Il renderer richiede una timeline coerente e gli asset locali della produzione, compreso il carattere Manrope. Non scarica immagini o modelli mancanti. Le presentazioni molto lunghe hanno un limite di 500 immagini e 2.000 pagine totali: superarlo produce un errore esplicito, senza troncare silenziosamente il testo. Per ridurre il numero di immagini scegli la variante compatta.
