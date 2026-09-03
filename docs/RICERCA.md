# Ricerca ibrida e provenienza

La modalità predefinita `hybrid` cerca prima sul web. Se non acquisisce almeno tre pagine da due domini diversi, di cui almeno uno esterno a Wikipedia, prosegue con le pagine disponibili e la conoscenza del modello configurato. Zero pagine è ammesso. Questo criterio misura disponibilità e varietà delle fonti, non la verità dei fatti.

`strict`, selezionabile in Amministrazione, conserva il blocco precedente. Non cambia la connessione al modello, non richiede SearXNG e non installa servizi aggiuntivi. Le configurazioni precedenti senza `research_mode` usano il nuovo valore predefinito.

La produzione registra `checkpoints/research.json`, il resoconto delle acquisizioni e le pagine realmente scaricate. Gli ID bibliografici possono riferire soltanto queste pagine, anche nei dati annidati del piano visivo e nella revisione. In assenza di riscontri gli elenchi restano vuoti. La conoscenza interna non viene aggiunta all'elenco delle fonti.

La revisione ibrida cerca errori, contraddizioni e dettagli dubbi anche con la conoscenza del modello, senza bocciare il solo fatto che manchino pagine. Rimane una revisione automatica, non una verifica indipendente. Il testo viene corretto una volta; problemi materiali irrisolti continuano a bloccare la produzione. I prompt richiedono di omettere cifre precise non supportate; il validatore rifiuta grafici senza riferimenti. Questi controlli non garantiscono che ogni affermazione con un riferimento sia vera.

L'app mostra un avviso persistente. `sources.md` distingue le pagine consultate dalle scene senza riscontri; `timeline.json` conserva `research` e `evidence_status`. Anche la sceneggiatura e la descrizione YouTube dichiarano la verifica incompleta. TTS, rendering e tracce audio restano invariati; non vengono aggiunti avvisi alla voce narrante.

Per riprendere un progetto fermato con «Fonti consultabili insufficienti», riavvia l'app aggiornata e premi **Riprendi**. Se non aveva ancora scene, il motore isolato viene aggiornato da quello incluso, conservando una copia del precedente. Progetti con scene esistenti conservano la propria politica salvata: una nuova revisione permette di cambiarla. Una pipeline esterna precedente deve essere aggiornata oppure sostituita nelle impostazioni con quella inclusa; l'app non modifica la cartella esterna.

Le prove automatiche simulano indisponibilità delle fonti, fonti parziali e revisione del modello. Verificano entrambe le modalità, ripresa, riferimenti e documenti esportati. Non rappresentano una valutazione storiografica di un LLM reale.

## Risposte errate o troncate (1.1.3)

La fase generale «Struttura e geografia» produce prima un breve concetto, poi un catalogo di luoghi/protagonisti e infine gruppi di due scene. Ogni gruppo completato e validato viene salvato. La ripresa conserva i passaggi riusciti, anche dopo aver cambiato modello.

Se un gruppo viene troncato, l'app lo divide in richieste singole. Una singola richiesta troncata viene riprovata in forma compatta per un massimo di tre tentativi. Non vengono accettati frammenti JSON né aumentati automaticamente il budget token o il limite di richieste. Errori HTTP, autenticazione e timeout non sono trattati come errori JSON da correggere. Le risposte troncate, il motivo di terminazione, l'uso token restituito dal server e il tempo trascorso sono conservati nell'audit privato.

Le raccolte indicizzate per ID vengono convertite in elenchi senza perdere i dati. I luoghi conservano `uncertain` e `note`. Un nome viene convertito in ID soltanto se coincide, senza ambiguità, con un nome o ID del catalogo (maiuscole e accenti normalizzati). L'app non associa un tema a una città, non inventa coordinate e non usa somiglianze vaghe. Gli errori indicano scena, riferimento sbagliato e ID ammessi. Le scene non geografiche possono avere `focus=[]`.

Il contratto visivo del motore viene controllato prima di salvare ogni gruppo, così riferimenti a persone, eventi o livelli inesistenti e geometrie malformate possono essere corretti prima di scrivere la narrazione. Il diario registra richieste, risposte, correzioni e gruppi salvati. Durante l'attesa compare un messaggio ogni 20 secondi: indica una richiesta aperta, non certifica che il server stia generando token.

Per temi letterari o mitologici il piano può dichiarare `narrative_basis=literary_tradition`; questa cornice accompagna la scrittura e le note editoriali. Non converte il mito in storia accertata né garantisce l'accuratezza geografica del modello.

I vecchi piani salvati vengono riutilizzati. Il percorso battle precedente rimane operativo; beneficia della diagnostica LLM aggiornata, mentre la costruzione a gruppi riguarda i nuovi piani generali. La prova opzionale `tests/outline_local_smoke.py` può usare un modello già installato su localhost: non legge chiavi o impostazioni private e non chiama endpoint remoti a pagamento.

## Passaggio dal piano al motore (1.1.4)

L'errore `'str' object has no attribute 'get'` in `validate_pack`, durante **Ritratti e materiali**, derivava da due significati diversi di `focus`: nel piano generale elencava ID di luoghi, mentre il vecchio motore attende effetti grafici con un cue. Il compilatore lasciava passare gli ID senza separarli. È un difetto dell'adattamento dell'app; non richiede di aumentare i token o cambiare modello.

La conversione conserva gli ID in `location_ids` e rimuove soltanto la loro duplicazione nel campo degli effetti. I focus già espressi come oggetti vengono conservati. Riferimenti sconosciuti o ambigui vengono segnalati, senza inventare coordinate. Tutte le scene generali vengono controllate al confine con il contratto del motore prima di preparare mappe e asset. Il formato battle e il renderer restano invariati.

Al primo **Riprendi**, il pack generale interessato viene riparato nello stesso workspace, con una copia `battle.before-focus-fix-<numero>.json`. Questa riparazione non sostituisce il motore isolato già presente e funziona anche con la versione precedente. Checkpoint editoriali e cartografia già completata vengono riutilizzati; non occorrono nuove chiamate al modello per ripetere queste fasi. Ritratti e successive fasi ancora da eseguire proseguono normalmente, con i rispettivi controlli.

Aggiorna il codice a server fermo, conservando `data/` e gli ambienti installati; riavvia e usa **Riprendi** sullo stesso progetto. La prova opzionale `tests/focus_resume_smoke.py --base-work <workspace> --previews` riproduce il problema su una copia isolata, controlla entrambi i motori e genera anteprime usando i raster salvati in sola lettura. Non modifica il workspace indicato, non chiama il modello e non produce un nuovo filmato completo.
