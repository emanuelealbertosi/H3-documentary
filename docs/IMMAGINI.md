# Immagini e riquadri

Disponibili dalla versione 1.1.0. Dalla versione 1.8.0 la libreria gestisce anche l’inventario completo delle immagini effettivamente usate in ciascun film.

## Inventario automatico e sostituzione parziale

Quando la struttura del racconto è pronta, l’app crea uno slot per ogni persona e luogo realmente citato e per ogni ritratto, opera, documento o immagine associata usata dalle scene. Per persone e luoghi tenta una ricerca su Wikipedia e Wikimedia Commons, verifica che la licenza sia pubblico dominio, CC0 o Creative Commons compatibile e conserva URL, metadati e impronta del file. Una ricerca non disponibile, ambigua o con licenza inadatta produce una **scheda neutra**: non viene mai presentata come ritratto o fotografia autentica.

La pagina del progetto mostra tutti gli slot con quattro stati: **Trovata automaticamente**, **Scheda neutra**, **Da completare** e **Personalizzata**. Ogni stato è sostituibile. Apri **Gestisci e sostituisci**, trascina una nuova immagine sul soggetto e premi **Aggiorna solo le scene interessate**. Un progetto completato genera automaticamente V2, V3 o la versione successiva; il vecchio film resta intatto. Il motore riusa ricerca, sceneggiatura, TTS, timeline, mappe e clip non coinvolte, renderizza soltanto le scene che contengono l’immagine cambiata, quindi esegue nuovamente montaggio e verifica tecnica.

Per un luogo la fotografia compare soltanto quando il suo nome è pronunciato. Un personaggio può comparire anche nella scena che lo introduce esplicitamente. Le sostituzioni dei ritratti e delle opere aggiornano anche le scene dedicate a quell’asset, non soltanto il riquadro sovrapposto.

## Uso nell’app

1. Apri **Immagini e riquadri**. Trascina uno o più JPG, PNG o WebP, oppure scegli **Aggiungi immagini**. Sono accettate immagini fisse fino a 20 MB e 32 megapixel.
2. Seleziona un’immagine. Crea un collegamento scegliendo **Persona, Luogo, Argomento, Evento, Popolo / organizzazione o Scena** e scrivendo il nome.
3. Trascina l’immagine sul collegamento. Puoi trascinare la scheda nella libreria oppure la miniatura “Immagine selezionata” vicina ai soggetti. In alternativa fai clic sul collegamento dopo aver selezionato l’immagine.
4. Sposta il riquadro nell’anteprima e scegli dimensione, angolo e immagine intera o ritaglio. I tasti freccia spostano il riquadro di piccoli passi. Modifiche e associazioni si salvano automaticamente; **Salva riquadro** permette di riprovare un salvataggio.
5. Inserisci titolo, varianti del nome, provenienza, autore e diritti. Per esempio, collega “Annibale” e aggiungi “Annibale Barca” o “generale cartaginese” fra le varianti.
6. Crea un documentario lasciando selezionato **Inserisci le mie immagini associate**. Puoi disattivarlo per una produzione. Nei progetti ancora da avviare, il collegamento **Immagini e riquadri** permette di scegliere se usare la libreria.

Le immagini possono avere più collegamenti e uno stesso soggetto può avere più immagini. Queste si alternano durante la frase pertinente. **Archivia** è reversibile e mantiene gli originali; **Ripristina** rende nuovamente utilizzabile l’immagine.

## Quando appaiono

L’associazione usa nomi e varianti effettivamente presenti nelle frasi narrate, ignorando maiuscole, punteggiatura e accenti. Non deduce sinonimi: “Roma” non corrisponde a “romano” e un’immagine di Roma non appare soltanto perché il tema generale riguarda l’Impero Romano. Aggiungi le varianti pertinenti. Un collegamento di tipo **Scena** può corrispondere al titolo o all’identificatore della scena; in questo caso l’immagine appare durante la sua prima frase.

Il TTS misura le frasi e il riquadro usa quegli intervalli. La comparsa ha una breve dissolvenza; fuori dalla frase il compositore restituisce il fotogramma originale. Se una frase contiene molte immagini, il suo tempo disponibile viene suddiviso: usa poche immagini per ciascun soggetto per mantenerle leggibili.

Il motore applica lo stesso riquadro a battaglie, atlanti, mappe storiche e scene senza mappa. Non altera zoom, percorsi, narrazione o sottotitoli. L’anteprima nell’editor mostra la posizione su una carta dimostrativa, **non** una simulazione del futuro racconto. Le anteprime prodotte dopo il TTS mostrano invece le scene reali. Il riquadro ha un formato fisso con immagine 4:3 e didascalia; posizione e larghezza sono configurabili entro l’area centrale sicura. Può coprire elementi di una scena: scegli un angolo adatto e controlla le anteprime.

Nelle scene senza mappa il contenuto centrale viene adattato allo spazio libero accanto ai riquadri, mantenendo titoli e cronologia alle dimensioni originali. Questa disposizione rimane stabile per l’intera scena. Per conservare spazio leggibile, usa preferibilmente lo stesso lato per tutte le immagini della scena.

## Conservazione e privacy

- Gli originali rimangono in `data/media/<id>/`; anteprima normalizzata e miniatura hanno file separati. L’originale non viene ritagliato né ricodificato.
- All’avvio si fissa la selezione della libreria in `checkpoints/media-selection.json`. La produzione copia soltanto gli asset realmente abbinati in `workspace/assets/user/`, con manifest, attribuzione e SHA-256. Le modifiche successive alla libreria non cambiano i progetti già avviati.
- Timeline e crediti includono le immagini utilizzate; lo ZIP dei materiali contiene anche i relativi originali. Lo ZIP di distribuzione dell’app esclude sempre `data/`, immagini personali e progetti di test.
- Le immagini personali non vengono inviate al server LLM. Per produzioni che ne contengono, il controllo visivo remoto delle anteprime viene saltato anche se configurato; verifiche tecniche e anteprime locali restano attive.
- Non viene attribuita una licenza presunta ai file caricati. Una licenza generale del pack non viene automaticamente estesa ai nuovi materiali.

Le associazioni sono un sistema di composizione locale. Questa estensione non aggiunge ancora un editor del testo narrato né una modalità slideshow a tutto schermo.

## Estensione tecnica e compatibilità

`app/media.py` gestisce validazione, associazione e copia degli asset; `app/media_routes.py` espone API locali protette. `static/media.js` e `static/media.css` implementano l’editor.

`pipeline/engine/image_insets.py` aggiunge un compositore sopra il renderer esistente. Tre agganci delimitati in `visuals.py`, `render.py`, `export.py` collegano rispettivamente compositing, invalidazione della cache e crediti. Il test della baseline 1.0.0 verifica che, rimuovendo esclusivamente questi agganci, i file originali coincidano con le impronte già registrate. I progetti migrati hanno `use_media=0`; i nuovi progetti possono attivarlo. Senza corrispondenze il pack resta identico.

I pack mantengono tutte le chiavi esistenti e aggiungono solo `user_media` alla radice e `image_insets` nelle scene. Ogni riquadro identifica asset, cue della narrazione, ordine di alternanza, titolo, posizione normalizzata, dimensione e impronta dell’immagine. I file devono trovarsi sotto `assets/user/`; percorsi esterni e impronte alterate vengono rifiutati. Per motori esterni configurati nell’app serve anche questa estensione; il motore incluso la contiene già.

## Verifica della versione 1.1.0

35 test automatici passati: upload reale di immagini, formati e limiti, accesso locale, associazioni per nomi e varianti, alternanza, archiviazione, snapshot, esportazione e migrazione; inclusi i precedenti test dell’app e della baseline del motore.

Provati nel browser: creazione dei collegamenti, associazione tramite clic e drag and drop, trascinamento del riquadro, salvataggio, titolo e attribuzione. Il layout è adattivo anche nel pannello stretto dell’app.

Prodotto un MP4 reale di **30,75 secondi**, 1920×1080 a 24 fps, con Kokoro italiano, ritratto di Annibale e due grafiche originali dimostrative. Decodificati tutti i **738 fotogrammi** e l’audio; sincronizzazione esatta, loudness **−16,00 LUFS**, nessun intervallo nero anomalo. Controllo luminosità superato: massimo salto medio **1,517/255**. SHA-256: `b0043d33a55a4e884e52f4b62edcfcec4d4b72785208f39a07fb49bb0c669435`.

Confronti dei fotogrammi: pixel identici alla mappa originale fuori dal riquadro, pixel identici a parità di timestamp, assenza del riquadro prima della frase. Controllate anche anteprime storiche con mappa e scena riepilogativa senza mappa. La prova usa testo preparato e non un LLM reale né una nuova ricerca storica.

Per ripetere il test dopo l’installazione: esegui `tests/media_smoke.py` con il Python dell’app, passando `--base-work` a un workspace già prodotto con atlante compatibile. `--portrait` è facoltativo; senza, viene creata una grafica di prova. Tutti i risultati sono isolati in `tests/output/media-smoke/`.
