# Prova locale di Chatterbox

Ambiente opzionale e separato in `.venv-chatterbox`, Python 3.11.16 e PyTorch 2.6.0 CPU. Usa Chatterbox Multilingual V3 dal repository ufficiale, con revisioni fissate di codice, watermark e pesi. Non modifica il TTS Kokoro/Piper della pipeline né le impostazioni di Studio.

I nuovi campioni e le misure vengono salvati in `pipeline/output/chatterbox-test`. I risultati della prova originaria non sono distribuiti nello ZIP sorgente. La voce inclusa nel modello permette di provare italiano e inglese senza fornire una registrazione personale. Non costituisce una prova della clonazione della voce dell’utente.

È stato provato anche un riferimento sintetico italiano, estratto dalla voce Kokoro if_sara già prodotta dal progetto. Questa registrazione di prova non viene inclusa nella distribuzione; puoi usare un tuo campione locale. Il campione finale usa frasi separate e margine di volume prima della conversione PCM; viene conservato anche il master float.

## Utilizzo da PowerShell

Dalla cartella `pipeline/` di H3-documentary, dopo INSTALLA.bat -Chatterbox:

```powershell
# Installazione o ripristino; richiede rete soltanto per i download.
./tools/chatterbox/setup.ps1

# Prova italiana offline.
./tools/chatterbox/prova.ps1

# Clonazione da un file di riferimento disponibile localmente.
./tools/chatterbox/prova.ps1 -Reference 'C:\percorso\voce.wav'

# Testo proprio e lingua.
./tools/chatterbox/prova.ps1 -Reference 'C:\percorso\voce.wav' -TextFile 'C:\percorso\testo.txt' -Language it

# Confronto italiano / inglese e misure.
./.venv-chatterbox/Scripts/python.exe -X utf8 tools/chatterbox/probe.py --languages it en

# Riferimento sintetico della prova, con generazione per frase.
./.venv-chatterbox/Scripts/python.exe -X utf8 tools/chatterbox/probe.py --languages it --reference output/chatterbox-test/reference_sara_synthetic.wav --name sara_sentences --sentences

# Controllo ASR indipendente, opzionale: richiede requirements-qa.txt e il modello Whisper locale, non inclusi nell’installazione standard.
./.venv/Scripts/python.exe -X utf8 tools/chatterbox/check_samples.py
```

Per il campione di riferimento usare circa 10–20 secondi di parlato pulito, con una sola voce e senza musica. La sintesi utilizza il file sul computer; non lo invia a servizi esterni. La modalità di prova abilita il funzionamento offline delle librerie Hugging Face. Resta attivo il watermark audio previsto da Chatterbox.

## Misure e limiti

`benchmark_*.json` registra durata dell’audio, secondi di generazione, rapporto tempo di calcolo/durata, memoria del processo, versioni, parametri essenziali e SHA dei WAV. Il caricamento del modello è misurato a parte. Il tempo di generazione comprende anche conversione in forma d’onda e watermark; le prime chiamate possono includere inizializzazioni aggiuntive. La memoria indicata riguarda il processo, non il consumo totale del computer.

`speech-check.json` registra decodifica, lingua riconosciuta e trascrizione indipendente. Il confronto ASR non valuta la naturalezza né certifica la somiglianza della voce. L’ascolto dei campioni resta il confronto utile per scegliere un narratore.

Il test non aggiunge ancora un selettore TTS all’app, non sostituisce le voci dei documentari esistenti e non produce MP4 multitraccia. Serve a valutare concretamente questo motore e il suo costo sul PC prima dell’integrazione.

## Provenienza

- [Chatterbox ufficiale](https://github.com/resemble-ai/chatterbox), codice MIT, revisione `5de7a54aa4e5e2baadb0182dde554908b48b85c2`.
- [Pesi ufficiali ResembleAI](https://huggingface.co/ResembleAI/chatterbox), model card con licenza MIT, revisione `5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18`.
- [Watermark Perth](https://github.com/resemble-ai/Perth), revisione `ff1c8ac55a976971245cdd53c18d6131ca00d993`.
- Il tokenizer carica anche il segmentatore spacy-pkuseg: archivio pubblico, versione e checksum sono conservati dal downloader.

`assets/tts/chatterbox-v3/manifest.json` contiene URL e SHA dei file acquisiti; `requirements-lock.txt` conserva le dipendenze effettivamente installate. Le dipendenze mantengono le rispettive licenze. Non sono state usate API a pagamento.
