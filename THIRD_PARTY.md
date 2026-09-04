# Provenienza e licenze

La licenza MIT del progetto copre il codice originale dell'app e della pipeline. Non riassegna la licenza dei componenti scaricati.

| Componente | Provenienza | Licenza / note |
|---|---|---|
| DocumentariAI / Studio | Motore e app originali inclusi; avvisi conservati | MIT |
| uv 0.12.9 | https://github.com/astral-sh/uv/releases/tag/0.12.9 | MIT / Apache-2.0; ZIP ufficiale con SHA-256 fissato nell'installatore |
| CPython 3.13.13 | https://github.com/astral-sh/python-build-standalone | Python Software Foundation e licenze delle librerie incluse |
| Kokoro 82M, file ONNX e voci v1.0 | https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0 ; https://huggingface.co/hexgrad/Kokoro-82M | Pesi Apache-2.0; modello e licenza salvati in `pipeline/assets/voice/kokoro/` |
| kokoro-onnx | https://github.com/thewh1teagle/kokoro-onnx | MIT |
| Misaki | https://github.com/hexgrad/misaki | Apache-2.0 |
| eSpeak NG / phonemizer | https://github.com/espeak-ng/espeak-ng ; https://github.com/bootphon/phonemizer | GPL; libreria e dati forniti dal pacchetto `espeakng-loader` |
| Piper | https://github.com/OHF-Voice/piper1-gpl | GPL-3.0; backend locale alternativo conservato per compatibilità |
| FFmpeg | https://ffmpeg.org/legal.html ; https://github.com/imageio/imageio-ffmpeg | Il wrapper è BSD-2-Clause. Il binario incluso nella wheel ha la propria configurazione/licenza; consultare `ffmpeg -L` e i sorgenti del distributore prima di redistribuire i binari. |
| Natural Earth | https://www.naturalearthdata.com/about/terms-of-use/ | Pubblico dominio; base fisica moderna |
| Mapzen Terrarium / terrain tiles | https://registry.opendata.aws/terrain-tiles/ ; https://github.com/tilezen/joerd/blob/master/docs/attribution.md | Attribuzioni variabili per area, conservate con i dati scaricati |
| Manrope, Cormorant Garamond, Bebas Neue | https://github.com/google/fonts | SIL Open Font License 1.1; testi integrali nelle cartelle dei font |
| Wikimedia Commons | https://commons.wikimedia.org/ | Licenza dell'opera specifica, verificata e registrata nel manifest della produzione |
| Opere del Metropolitan Museum | https://www.metmuseum.org/policies/image-resources | Immagini Open Access degli esempi, metadati e fonti nei rispettivi pack |
| Chatterbox Multilingual, opzionale | https://github.com/resemble-ai/chatterbox ; https://huggingface.co/ResembleAI/chatterbox | MIT; commit e revisione pesi fissati negli script; watermark Perth mantenuto |
| PyTorch / torchaudio, opzionali | https://pytorch.org/ | Licenze delle distribuzioni CPU scaricate |
| FastEmbed | https://github.com/qdrant/fastembed | Apache-2.0; inferenza ONNX locale su CPU per l'indice dei documenti |
| paraphrase-multilingual-MiniLM-L12-v2, conversione ONNX Qdrant | https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 ; https://huggingface.co/qdrant/paraphrase-multilingual-MiniLM-L12-v2-onnx-Q | Apache-2.0; revisione ONNX fissata nell'app e scaricata nella cartella privata `data/models/rag/` |
| pypdf | https://github.com/py-pdf/pypdf | BSD-3-Clause; estrazione locale del testo PDF |
| python-docx | https://github.com/python-openxml/python-docx | MIT; estrazione locale di paragrafi e tabelle DOCX |
| google-auth | https://github.com/googleapis/google-auth-library-python | Apache-2.0; autenticazione OAuth facoltativa per Google Cloud TTS |

Le versioni Python sono elencate nei due `requirements-lock.txt`; ogni ambiente conserva i metadati e le licenze dei pacchetti installati. Nessun eseguibile, modello pesante o cache privata viene incluso nel repository Git o nello ZIP sorgente: sono ottenuti dall'installatore dai distributori originali.

`scripts/assets-lock.json` conserva provenienza, licenza e SHA-256 dei font e dei pesi vocali predefiniti. Ogni produzione aggiunge i propri asset e crediti. I dati originali delle produzioni non devono essere considerati liberamente riutilizzabili solo perché si trovano accanto al codice MIT.
