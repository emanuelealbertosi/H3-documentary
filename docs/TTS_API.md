# Server TTS esterni

H3-documentary può usare Kokoro e Chatterbox sul computer locale oppure un server TTS raggiungibile via HTTP. Apri **Amministrazione → Server per la voce**, crea un profilo, ascolta la prova e salvalo. Il profilo comparirà nella scelta **Voce narrante** dei nuovi documentari.

Ogni progetto conserva una copia pubblica e immutabile di provider, indirizzo, modello, voce, lingua e formato. La credenziale resta in `data/tts-api.json`, cifrata con Windows DPAPI, e non viene scritta nel workspace, nella timeline, nei log o negli ZIP. Puoi anche fornire la credenziale con `DOCUMENTARIAI_TTS_API_KEY` senza salvarla su disco.

## Contratti supportati

| Tipo | Richiesta | Autenticazione | Voce one-shot |
|---|---|---|---|
| OpenAI compatibile | `POST <base>/audio/speech`, JSON con `model`, `input`, `voice`, `response_format` | Bearer facoltativo | No |
| Higgs TTS | stesso endpoint; con riferimento usa multipart e `ref_audio` | Bearer facoltativo | Sì |
| ElevenLabs | `POST <base>/text-to-speech/{voice_id}` | header `xi-api-key` | Usa un voice ID già creato |
| Google Cloud TTS | `POST <base>/text:synthesize`, risposta `audioContent` | OAuth Bearer, JSON service account o Application Default Credentials | Usa il nome voce configurato |

Per Higgs self-hosted scegli **Higgs TTS**, inserisci l'indirizzo OpenAI compatibile del server e il nome del modello esposto. Un WAV caricato nella sezione voce viene inviato come `ref_audio` soltanto se è selezionato per quel progetto. Il testo di ogni frase viene sempre inviato al TTS scelto.

Google accetta nel campo credenziale un token OAuth temporaneo o il contenuto JSON completo di un service account. Se il campo resta vuoto, H3 prova le Application Default Credentials configurate sul PC. Il token viene richiesto o aggiornato al momento della sintesi.

## Ripresa e formato audio

Ogni risposta viene limitata a 25 MB, decodificata con FFmpeg e normalizzata in WAV PCM mono a 24 kHz. La pipeline misura poi la durata reale e crea cue, timeline e montaggio con lo stesso codice usato dalle voci locali. Ogni frase valida viene memorizzata prima di richiedere la successiva: dopo un timeout o un'interruzione, **Riprendi** riusa l'audio già pronto.

Il test in Amministrazione effettua una vera richiesta breve al provider. I test automatici del repository usano server simulati e non consumano crediti. ElevenLabs, Google Cloud e servizi Higgs ospitati possono applicare quote o costi secondo il relativo account; il software non li abilita né li acquista. Per un flusso completamente gratuito usa Kokoro, Chatterbox locale o un server TTS self-hosted.

Fonti dei contratti: [Higgs TTS 3](https://docs.boson.ai/models/higgs-tts/overview), [ElevenLabs Text to Speech](https://elevenlabs.io/docs/api-reference/text-to-speech/convert), [Google Cloud Text-to-Speech REST](https://docs.cloud.google.com/text-to-speech/docs/reference/rest/v1/text/synthesize).
