"""Authoring and review policy; model memory is never a fabricated source."""

HYBRID_INSTRUCTIONS = """MODALITÀ IBRIDA: le pagine consultabili sono insufficienti.
Puoi usare la tua conoscenza interna per il contesto storico e i fatti di cui sei ragionevolmente sicuro.
Non presentarla come verificata: segnala dubbi e interpretazioni, ometti dettagli incerti.
source_ids e sources contengono SOLO ID di pagine realmente fornite e pertinenti; usa [] quando non ci sono riscontri.
Non inventare bibliografie, URL, citazioni testuali, consistenze o statistiche.
Evita cifre precise senza evidenza testuale: preferisci descrizioni qualitative.
Non generare grafici quantitativi senza fonti. Non inventare confini esatti, immagini, provenienze o licenze.
Indica uncertain=true per percorsi e aree ricostruiti. Inserisci le limitazioni in uncertainties.
Le fonti recuperate rimangono evidenza da valutare; non usare la memoria per ignorare loro contraddizioni senza segnalarle.
La mancanza di fonti esterne, da sola, non impedisce di proseguire. La memoria del modello non è una verifica indipendente."""


def author_system(base, research):
    if not research.get("fallback_used"):
        return base
    return base.replace("Ogni evento deve riferirsi alle fonti effettivamente consultate.",
                        "Ogni riferimento deve indicare una fonte effettivamente consultata; gli eventi senza riscontri restano non verificati.") + "\n" + HYBRID_INSTRUCTIONS


def validate_references(outline, sources, research):
    ids={s["id"] for s in sources}
    def visit(value):
        if isinstance(value,dict):
            for key,item in value.items():
                if key in ("source_ids","sources"):
                    if not isinstance(item,list) or any(not isinstance(s,str) or s not in ids for s in item):
                        raise ValueError("Il modello cita fonti inesistenti; non posso proseguire.")
                else:visit(item)
        elif isinstance(value,list):
            for item in value:visit(item)
    visit(outline)
    if not research.get("fallback_used") and any(not s.get("source_ids") for s in outline["scenes"]):
        raise ValueError("Una scena non indica fonti consultate. Aggiungi riferimenti pertinenti.")


def review_instruction(research):
    if research.get("fallback_used"):
        return ("Revisiona cronologia, luoghi, protagonisti e coerenza usando le pagine disponibili e, per il resto, "
                "la tua conoscenza interna. La mancanza di fonti da sola NON rende acceptable=false. "
                "Controlla anche che ogni movimento del piano sia descritto nella stessa scena e nella medesima direzione. "
                "Rifiuta errori materiali riconoscibili, contraddizioni, fonti o citazioni inventate e numeri precisi non supportati. "
                "Per incertezze non risolvibili richiedi di qualificare oppure omettere l'affermazione. "
                "Non affermare di avere verificato fatti privi di evidenza esterna. source_ids solo da pagine fornite, oppure []. ")
    return ("Verifica questa sceneggiatura confrontandola SOLO con le fonti. Controlla cronologia, luoghi, protagonisti, "
            "e che ogni movimento del piano sia descritto nella stessa scena e nella medesima direzione. "
            "numeri e interpretazioni. acceptable=false soltanto per errori storici materiali, supporto insufficiente "
            "o contraddizioni; non per differenze stilistiche. Riporta problemi concreti e source_ids verificabili. ")


def annotate_review(review, sources, research):
    ids={s['id'] for s in sources}
    if not set(review.get('source_ids',[]))<=ids:
        raise ValueError("La revisione cita fonti mai consultate.")
    return {**review, "verification_basis":research["status"], "independent_historical_verification":False}
