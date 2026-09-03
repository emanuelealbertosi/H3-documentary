# Verifica della distribuzione

Prima installazione autonoma verificata su Windows x64, Intel i7-1165G7 e 16 GB di RAM, senza GPU NVIDIA.

- Scaricati nella nuova cartella: uv 0.12.9, Python 3.13.13 gestito, dipendenze fissate, Kokoro e voci. Python, eSpeak e FFmpeg esterni non sono stati usati.
- Installazione e controlli di coerenza dei due ambienti completati.
- 25 test superati nella copia clonata: API, segreti, endpoint, coda, compatibilità storica, distribuzione, cache geografica e riferimenti delle immagini.
- Interfaccia iniziale e amministrazione controllate nel browser; voce e motore risultano installati. Il modello remoto resta da configurare.
- Produzione dimostrativa realmente completata in 1920×1080 a 24 fps: 2.884 fotogrammi, circa due minuti; decodifica completa, audio, sottotitoli, capitoli e variazioni di luminosità controllati.
- I 17 moduli del motore sono stati confrontati con la pipeline funzionante prima del confezionamento. Nessuna riscrittura del renderer o del TTS; impronte originali in `engine-baseline.json`. Git può normalizzare i terminatori di riga senza modificare il codice.

Il filmato usa **ricerca e risposte LLM preparate esplicitamente per il test**, non un server LLM reale. Cartografia, download, sintesi vocale, rendering, montaggio e verifica del file sono reali. Nessuna prova viene presentata come una produzione storica verificata da un modello remoto.

La prova Chatterbox CPU è stata eseguita nell'ambiente sperimentale originario. La distribuzione conserva il modulo opzionale; l'integrazione nella selezione voce dell'app non è implementata.

La clonazione da Git è stata eseguita in una cartella separata con spazi nel percorso, senza hard link al repository sorgente. AVVIA.bat ha installato autonomamente tutti i componenti con un PATH privo di Python e Git, usando il proprio runtime gestito. Avvio su porta alternativa e secondo avvio della stessa istanza superati. È una prova isolata sullo stesso PC, non un test su ogni possibile installazione di Windows.

Il video dimostrativo dura 120,1667 secondi, contiene quattro capitoli, sottotitoli italiani e audio AAC stereo a 48 kHz. Loudness misurata: −16,01 LUFS; picco reale −3,79 dBTP. Differenza delle durate audio/video inferiore a un millisecondo. SHA-256: `8623150b105bc1f90b7b377a884830ba88ba4501fc6c089277e43429311a9836`.

Lo ZIP è prodotto dal commit corrente, riaperto e controllato per integrità. Runtime, modelli, cartelle private, database, cache e video di prova sono esclusi. I due BAT nello ZIP mantengono i terminatori Windows. Lo SHA-256 dell'archivio e il commit sorgente sono nel JSON affiancato allo ZIP.

Il repository remoto non è stato creato e nessun push è stato eseguito. La configurazione della CI è inclusa; l'esecuzione su GitHub avverrà dopo il push.
