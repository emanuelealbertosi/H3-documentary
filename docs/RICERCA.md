# Ricerca ibrida e provenienza

La modalità predefinita `hybrid` cerca prima sul web. Se non acquisisce almeno tre pagine da due domini diversi, di cui almeno uno esterno a Wikipedia, prosegue con le pagine disponibili e la conoscenza del modello configurato. Zero pagine è ammesso. Questo criterio misura disponibilità e varietà delle fonti, non la verità dei fatti.

`strict`, selezionabile in Amministrazione, conserva il blocco precedente. Non cambia la connessione al modello, non richiede SearXNG e non installa servizi aggiuntivi. Le configurazioni precedenti senza `research_mode` usano il nuovo valore predefinito.

La produzione registra `checkpoints/research.json`, il resoconto delle acquisizioni e le pagine realmente scaricate. Gli ID bibliografici possono riferire soltanto queste pagine, anche nei dati annidati del piano visivo e nella revisione. In assenza di riscontri gli elenchi restano vuoti. La conoscenza interna non viene aggiunta all'elenco delle fonti.

La revisione ibrida cerca errori, contraddizioni e dettagli dubbi anche con la conoscenza del modello, senza bocciare il solo fatto che manchino pagine. Rimane una revisione automatica, non una verifica indipendente. Il testo viene corretto una volta; problemi materiali irrisolti continuano a bloccare la produzione. I prompt richiedono di omettere cifre precise non supportate; il validatore rifiuta grafici senza riferimenti. Questi controlli non garantiscono che ogni affermazione con un riferimento sia vera.

L'app mostra un avviso persistente. `sources.md` distingue le pagine consultate dalle scene senza riscontri; `timeline.json` conserva `research` e `evidence_status`. Anche la sceneggiatura e la descrizione YouTube dichiarano la verifica incompleta. TTS, rendering e tracce audio restano invariati; non vengono aggiunti avvisi alla voce narrante.

Per riprendere un progetto fermato con «Fonti consultabili insufficienti», riavvia l'app aggiornata e premi **Riprendi**. Se non aveva ancora scene, il motore isolato viene aggiornato da quello incluso, conservando una copia del precedente. Progetti con scene esistenti conservano la propria politica salvata: una nuova revisione permette di cambiarla. Una pipeline esterna precedente deve essere aggiornata oppure sostituita nelle impostazioni con quella inclusa; l'app non modifica la cartella esterna.

Le prove automatiche simulano indisponibilità delle fonti, fonti parziali e revisione del modello. Verificano entrambe le modalità, ripresa, riferimenti e documenti esportati. Non rappresentano una valutazione storiografica di un LLM reale.
