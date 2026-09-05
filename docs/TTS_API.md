# Voci, ritmo e server TTS

H3-documentary può usare Kokoro e Chatterbox sul computer locale oppure un server TTS raggiungibile via HTTP. Apri **Amministrazione → Server per la voce**, crea un profilo, ascolta la prova e salvalo. Il profilo comparirà nella scelta **Voce narrante** dei nuovi documentari.

Ogni progetto conserva una copia pubblica e immutabile di provider, indirizzo, modello, voce, lingua, formato e parametri di generazione. La credenziale resta in `data/tts-api.json`, cifrata con Windows DPAPI, e non viene scritta nel workspace, nella timeline, nei log o negli ZIP. Puoi anche fornire la credenziale con `DOCUMENTARIAI_TTS_API_KEY` senza salvarla su disco.

## Ritmo e interpretazione della voce

Dalla versione 1.14.0, sotto la scelta della voce trovi il pannello richiudibile **Ritmo e interpretazione della voce**. È disponibile in Amministrazione, nel nuovo documentario e nelle impostazioni per la prossima versione di un progetto.

| Controllo | Scelta |
|---|---|
| Stile della lettura | Voce del modello, Documentario, Calmo, Coinvolgente, Solenne |
| Velocità | Dall’85% al 115%; 100% mantiene la velocità di base |
| Pausa fra le frasi | Da 0 a 0,8 secondi, in passi di 0,01 secondi |

Stile, velocità e pausa sono indipendenti: selezionare un preset non sposta gli altri controlli. I valori iniziali sono **Voce del modello, 100%, 0,18 s** e mantengono il comportamento temporale precedente. Quando personalizzi la lettura, la durata effettiva segue l’audio misurato: il film può durare più o meno dell’indicazione iniziale, senza una seconda accelerazione per farlo rientrare a forza.

Il valore salvato in Amministrazione diventa il predefinito per i nuovi progetti. Ogni progetto conserva poi la propria scelta. In **Impostazioni per la prossima versione** puoi modificarla prima di rigenerare; per un tentativo interrotto è disponibile anche **Applica soltanto la voce**, che conserva il lavoro editoriale. Un video completato rimane nella versione precedente.

### Cosa supporta ogni motore

| Voce scelta | Interpretazione espressiva | Velocità e pause |
|---|---|---|
| Kokoro | Mantiene l’espressività del modello | Regolabili localmente |
| Chatterbox Multilingual V3 | I preset regolano i parametri espressivi; influisce anche il campione vocale | Regolabili localmente |
| Higgs con indicazioni espressive disattivate | Mantiene l’espressività del modello | Regolabili localmente |
| Higgs con indicazioni espressive attivate | Invia i tag Higgs TTS 3 al server compatibile; verifica il risultato ascoltandolo | Regolabili localmente |
| Altre API TTS | Questa integrazione mantiene l’interpretazione della voce configurata | Regolabili localmente |

Se il motore non supporta il preset selezionato, l’interfaccia lo segnala e applica soltanto velocità e pause. I preset non riscrivono la sceneggiatura: il testo visibile, i sottotitoli e i riferimenti storici rimangono invariati.

### Ascoltare una prova

Apri **Ascolta prima di produrre il video**, modifica il breve testo e usa **Ascolta questa lettura**. **Confronta con la voce normale** ripete lo stesso testo e lo stesso campione con i valori iniziali, senza cambiare le impostazioni selezionate. Il player mostra l’audio restituito e segnala l’eventuale ripiego sulla voce originale. Queste prove usano il motore scelto e non avviano un documentario.

La prova del profilo in **Server per la voce → Ascolta una prova** usa il testo editabile di **Testo e impostazioni della prova**, i parametri di quel server e il ritmo selezionato nella sezione **Voce e cloning one-shot**. Permette quindi di provare un profilo prima di salvarlo. Durante una produzione o un’altra operazione TTS, H3 chiede di attendere per evitare richieste concorrenti allo stesso modello.

## Higgs Audio remoto

Il profilo **Higgs TTS remoto** segue il contratto descritto nella specifica del server Higgs Audio v3. Come indirizzo usa:

```text
http://IP-DEL-PC-CON-GPU:8095/v1
```

`localhost` indica sempre il computer su cui gira H3. Se Higgs si trova su un altro PC, inserisci il suo indirizzo LAN o VPN. Il server non deve essere esposto direttamente a Internet senza autenticazione e TLS.

H3 gestisce autonomamente il modello remoto per ogni attività vocale:

1. chiama `POST /v1/model/load` una sola volta;
2. genera tutti i segmenti del documentario in sequenza;
3. chiama `POST /v1/model/unload` in un blocco finale, anche dopo errore o interruzione;
4. lascia attivo il processo HTTP del server.

Se tutti i segmenti sono già nella cache, H3 non carica inutilmente il modello. Se lo scaricamento fallisce dopo una sintesi riuscita, la fase non viene dichiarata completata e il diario mostra l’errore. In Amministrazione sono disponibili anche i pulsanti **Controlla stato**, **Carica modello** e **Scarica modello**; usano `GET /v1/status`, `POST /v1/model/load` e `POST /v1/model/unload`.

Senza campione, H3 usa `POST /v1/audio/speech` con JSON. Con un campione one-shot usa:

```text
POST /v1/audio/voice-clone
Content-Type: multipart/form-data

input
reference_audio
reference_text
temperature
top_p
top_k
seed
max_new_tokens
response_format
```

Il campo file si chiama esattamente `reference_audio`; la trascrizione viene inviata separatamente come `reference_text`. H3 accetta campioni WAV da 4 a 60 secondi e non impone un limite specifico di 30 secondi al provider Higgs. Una registrazione pulita di 10–20 secondi è spesso sufficiente. La trascrizione deve riportare esattamente ciò che viene pronunciato nel campione ed è particolarmente utile per il cloning fra lingue diverse.

Dopo `load` e `unload`, H3 interroga nuovamente `/v1/status` e considera riuscita l'operazione soltanto se `model_state` coincide. Questa è una conferma dello stato dichiarato dall'API remota. Per verificare anche la memoria GPU, il server Higgs deve esporre una misura della VRAM allocata: H3 non può osservare né svuotare direttamente la cache CUDA di un altro computer.

Puoi anche registrare il campione sul PC Higgs come voce riutilizzabile. Seleziona il campione in Amministrazione, assegna un ID composto da lettere, numeri, trattino o trattino basso e usa **Registra questa voce sul server**. H3 chiama `POST /v1/voices/upload` con `voice_id`, `reference_audio`, `reference_text` e `overwrite`. Il nome restituito viene inserito nel campo **Voce / voice ID persistente**; salva il profilo per usarlo successivamente tramite `/v1/audio/speech`.

Il timeout predefinito del profilo Higgs è 900 secondi per frase. La connessione usa un limite separato di 10 secondi. La risposta può essere WAV, MP3, FLAC o OGG e viene sempre convertita localmente in WAV PCM mono a 24 kHz.

### Indicazioni espressive Higgs 3

Nel profilo Higgs, apri **Parametri di generazione Higgs** e abilita **Indicazioni espressive Higgs 3** soltanto per un server che le supporta. La scelta è salvata nel profilo (`style_protocol=higgs_tags`); resta disattivata nei profili precedenti e non si applica agli altri provider.

H3 antepone i [tag ufficiali Higgs TTS 3](https://docs.boson.ai/models/higgs-tts/tags) alla sola richiesta di sintesi. Non devi inserirli nel racconto e non finiscono nella sceneggiatura, nei cue o nei sottotitoli. Velocità e pause vengono applicate localmente, così non sono moltiplicate anche dai tag del server.

Se la richiesta con tag viene rifiutata per formato non accettato (HTTP 400 o 422), H3 prova una sola volta la stessa frase con l’interpretazione originale, conservando velocità e pause. La prova d’ascolto e il diario della produzione segnalano questo ripiego. Errori di autenticazione, connessione o server restano distinti e non cambiano automaticamente il profilo salvato.

Una risposta HTTP riuscita conferma che il server ha restituito audio, non che abbia interpretato correttamente i tag. **Verifica con la prova d’ascolto**: server personalizzati e checkpoint diversi possono ignorarli o pronunciarli. Per tornare al comportamento precedente disattiva la spunta oppure scegli **Voce del modello**. Il supporto del server Higgs personale non viene dichiarato verificato dalle simulazioni dei test automatici.

## Altri contratti supportati

| Tipo | Richiesta | Autenticazione | Voce one-shot |
|---|---|---|---|
| OpenAI compatibile | `POST <base>/audio/speech`, JSON con `model`, `input`, `voice`, `response_format` | Bearer facoltativo | No |
| Higgs Audio remoto | endpoint lifecycle, speech e voice-clone descritti sopra | Bearer facoltativo | Sì, audio e trascrizione |
| ElevenLabs | `POST <base>/text-to-speech/{voice_id}` | header `xi-api-key` | Usa un voice ID già creato |
| Google Cloud TTS | `POST <base>/text:synthesize`, risposta `audioContent` | OAuth Bearer, JSON service account o Application Default Credentials | Usa il nome voce configurato |

Google accetta nel campo credenziale un token OAuth temporaneo o il contenuto JSON completo di un service account. Se il campo resta vuoto, H3 prova le Application Default Credentials configurate sul PC. Il token viene richiesto o aggiornato al momento della sintesi.

## Ripresa e cache

Ogni risposta viene limitata a 25 MB, decodificata con FFmpeg e normalizzata in WAV PCM mono a 24 kHz. La pipeline misura poi la durata reale e crea cue, timeline e montaggio con lo stesso codice usato dalle voci locali. Ogni frase valida viene memorizzata prima di richiedere la successiva: dopo un timeout o un’interruzione, **Riprendi** riusa l’audio già pronto.

La configurazione della lettura viene conservata come `tts_delivery` nell’app e come `voice_delivery` nel pack del motore. La selezione entra nei dati usati per il riuso dell’audio; un cambiamento di stile non viene confuso con la voce precedente. La configurazione iniziale e i vecchi pack senza questi campi restano compatibili.

Il test in Amministrazione effettua una vera richiesta breve al provider. Se scegli un campione Higgs, prova anche il cloning one-shot. I test automatici del repository usano server simulati e non consumano crediti. ElevenLabs, Google Cloud e servizi Higgs ospitati possono applicare quote o costi secondo il relativo account; il software non li abilita né li acquista. Per un flusso completamente gratuito usa Kokoro, Chatterbox locale o un server TTS self-hosted.

Fonti dei contratti generali: [Higgs TTS 3](https://docs.boson.ai/models/higgs-tts/overview), [ElevenLabs Text to Speech](https://elevenlabs.io/docs/api-reference/text-to-speech/convert), [Google Cloud Text-to-Speech REST](https://docs.cloud.google.com/text-to-speech/docs/reference/rest/v1/text/synthesize).
