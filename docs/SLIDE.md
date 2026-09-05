# Slide senza mappa

La composizione è indipendente dall’argomento: una biografia, un viaggio o una battaglia possono essere raccontati con slide. I progetti esistenti mantengono automaticamente **Mappe e scene automatiche**.

1. In **Nuovo documentario → Composizione del video**, scegli **Slide senza mappa**. La spunta **Fermati per la revisione** viene proposta automaticamente; puoi toglierla.
2. Quando il progetto si ferma prima della voce e del rendering, apri **Immagini e riquadri**. Ogni scena ha un elemento **Sfondo · titolo della scena**. Senza immagine lo sfondo del film rimane nero; le miniature associate ai soggetti restano visibili.
3. Premi **Collega** o **Sostituisci immagine**. Puoi trascinare un file dal PC, aprire la scelta del file oppure usare un’immagine della libreria. Ogni sfondo è indipendente.
4. Imposta **Riquadro libero** o **Tutto schermo**. Le miniature offrono anche **Miniatura con didascalia**. **Immagine intera** conserva le proporzioni; **Riempi e ritaglia** riempie l’area. Nel riquadro libero scegli larghezza e altezza e trascinalo nell’anteprima; i tasti freccia permettono piccoli spostamenti.
5. Scegli **Fissa**, **Zoom in lento**, **Zoom out lento** oppure scorrimento nelle quattro direzioni. La **Dissolvenza in entrata e uscita** è indipendente dal movimento. La barra di anteprima permette di osservare l’effetto senza produrre un nuovo video.
6. Per lo sfondo puoi disattivare **Mostra titolo e testo della scena**, lasciando la sola immagine con le eventuali miniature. Premi **Continua produzione** quando hai terminato: i tempi seguono la voce narrante.

Le modifiche si salvano automaticamente. Il collegamento semantico delle immagini resta riutilizzabile; l’inquadratura modificata su un elemento del progetto vale per quel progetto. L’anteprima nell’editor mostra il singolo elemento selezionato: controlla le anteprime della scena per la composizione completa.

Su un film concluso usa **Rivedi e aggiorna questo video** per applicare cambiamenti alle sole scene interessate nello stesso progetto, conservando la versione verificata fino al completamento. Per cambiare la composizione di un progetto esistente da mappe a slide scegli **Slide senza mappa** nelle **Impostazioni per la prossima versione** e rigenera. L’esportazione PDF riutilizza queste stesse slide e i testi già approvati.

## Comportamento tecnico

`ProjectRequest.presentation_mode` accetta `map` (predefinito) e `slides`. Il pack e la timeline conservano il campo esplicito quando necessario. `documentary_type`, TTS, misurazione delle frasi, formato dei progetti e comandi precedenti restano condivisi. Non occorrono nuove dipendenze.

`layout.slide` è un’estensione facoltativa del layout precedente: `mode`, `x`, `y`, `width`, `height`, `fit`, `effect`, `fade`, `show_text`. Dimensioni e coordinate sono frazioni del fotogramma. I vecchi layout serializzano esattamente i quattro campi precedenti. L’editor limita il riquadro alla superficie visibile.

Il renderer delle slide non carica l’atlante. Gli effetti dipendono esclusivamente dal tempo della scena o del cue, senza casualità: zoom fino al 10%, margine del 12% per lo scorrimento, dissolvenza fino a 0,75 secondi per lato. Gli effetti vengono ritagliati nella propria area. Nei PDF vengono resi a metà percorso e senza dissolvenza per mantenere le immagini leggibili.

Il controllo finale continua a decodificare tutto il file e verificare audio, risoluzione, tempi, capitoli e sottotitoli. Il nero è intenzionale soltanto per questa modalità ed è registrato nel rapporto: non viene segnalato come guasto. Le modalità cartografiche mantengono il controllo precedente sugli intervalli neri. La riproducibilità dei fotogrammi delle slide ha un rapporto separato `slide-effects.json`; non è una certificazione estetica o storica.
