# Documenti e fonti locali

La biblioteca privata permette di fondare un documentario su materiali scelti dall'utente senza chiedere al server LLM di leggere interi libri. Tutti i file vengono estratti, suddivisi e indicizzati sul PC che esegue H3-documentary.

## Uso dall'interfaccia

1. Apri **Documenti e fonti** dalla barra laterale.
2. Trascina uno o più file PDF, DOCX, TXT o Markdown, oppure apri **Incolla direttamente un testo**.
3. Indica titolo, autore, anno e provenienza. Questi dati vengono riportati nella citazione; non sostituiscono la verifica editoriale.
4. Nella schermata **Nuovo documentario** lascia attivo **Usa i miei documenti come fonti** e spunta i materiali pertinenti.
5. Se il progetto è ancora in bozza, la pagina **Documenti e fonti** del progetto permette di cambiare la selezione. Quando la produzione parte, la selezione viene congelata.

La copia congelata si trova in `data/jobs/<id>/workspace/assets/documents/`. In questo modo una modifica successiva alla biblioteca non cambia una produzione già iniziata. Il pacchetto esportabile del progetto comprende le fonti selezionate; il repository, la release pubblica e gli altri progetti non le contengono.

## Come viene recuperato il testo

H3 divide il testo in passaggi sovrapposti e calcola vettori con `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` attraverso FastEmbed e ONNX Runtime. Il modello è multilingue, gira su CPU e viene scaricato una volta da `INSTALLA.bat` nella cartella privata `data/models/rag/`. L'installatore usa la conversione ONNX quantizzata di Qdrant a una revisione fissata e registra le impronte dei file scaricati.

Per ogni produzione la ricerca combina BM25 lessicale e similarità semantica. Mantiene un massimo di quattro passaggi per documento e dodici fonti locali complessive, quindi il server LLM riceve una selezione controllata invece del contenuto integrale. Se ONNX o il modello semantico non sono disponibili, l'indicizzazione passa allo stato **Testo pronto · ricerca lessicale** e la produzione può proseguire.

I documenti locali possono essere combinati con link e ricerca web. `sources.md` distingue gli originali locali dalle pagine consultate, conserva autore, anno, nome del file e impronta SHA-256 e indica se la ricerca ha usato anche la conoscenza interna del modello.

## Formati e limiti

- PDF con testo selezionabile, fino a 2.000 pagine.
- DOCX moderno, inclusi paragrafi e tabelle.
- TXT UTF-8 e Markdown.
- Testo incollato, da 80 caratteri.
- Massimo 50 MB e 2,5 milioni di caratteri estratti per documento.
- Massimo 24 documenti selezionati per progetto.

Un PDF quasi privo di testo viene conservato con lo stato **PDF scansionato · OCR necessario** e non viene usato come evidenza finché non viene sostituito da una versione con OCR. I vecchi file `.doc` non vengono interpretati: salvali come DOCX per evitare conversioni opache o dipendenze esterne.

## Confini di fiducia

Il testo importato è una fonte non fidata. Le istruzioni del sistema e dei prompt ordinano al modello di ignorare comandi contenuti nelle pagine; i file non vengono eseguiti, le macro Word non vengono caricate e azioni, allegati o script PDF non vengono avviati. L'estrazione non rende comunque una fonte storicamente attendibile: autore, edizione, completezza e attendibilità restano informazioni da verificare.
