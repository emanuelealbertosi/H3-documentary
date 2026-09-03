# Verifica della distribuzione

Prima installazione autonoma verificata su Windows x64, Intel i7-1165G7 e 16 GB di RAM, senza GPU NVIDIA.

- Scaricati nella nuova cartella: uv 0.12.9, Python 3.13.13 gestito, dipendenze fissate, Kokoro e voci. Python, eSpeak e FFmpeg esterni non sono stati usati.
- Installazione e controlli di coerenza dei due ambienti completati.
- 23 test superati: API, segreti, endpoint, coda, compatibilità storica, distribuzione e cache geografica.
- Interfaccia iniziale e amministrazione controllate nel browser; voce e motore risultano installati. Il modello remoto resta da configurare.
- Produzione dimostrativa realmente completata in 1920×1080 a 24 fps: 2.884 fotogrammi, circa due minuti; decodifica completa, audio, sottotitoli, capitoli e variazioni di luminosità controllati.
- I 17 moduli del motore sono stati confrontati con la pipeline funzionante prima del confezionamento. Nessuna riscrittura del renderer o del TTS; impronte originali in `engine-baseline.json`. Git può normalizzare i terminatori di riga senza modificare il codice.

Il filmato usa **ricerca e risposte LLM preparate esplicitamente per il test**, non un server LLM reale. Cartografia, download, sintesi vocale, rendering, montaggio e verifica del file sono reali. Nessuna prova viene presentata come una produzione storica verificata da un modello remoto.

La prova Chatterbox CPU è stata eseguita nell'ambiente sperimentale originario. La distribuzione conserva il modulo opzionale; l'integrazione nella selezione voce dell'app non è implementata.

Il controllo di clonazione e confezionamento viene registrato nel rapporto conclusivo della release.
