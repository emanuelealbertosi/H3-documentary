"""Summarize the measured CPU experiment without claiming a quality ranking."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'output/chatterbox-test'

def main():
    checks={r['file']:r for r in json.loads((OUT/'speech-check.json').read_text(encoding='utf-8'))}
    labels={'builtin':'Voce inclusa','sara_reference':'Riferimento Sara, testo intero','sara_sentences':'Riferimento Sara, frasi separate'}
    rows=[];data=[]
    for p in sorted(OUT.glob('benchmark_*.json')):
        b=json.loads(p.read_text(encoding='utf-8'));name=p.stem.removeprefix('benchmark_')
        for s in b['samples']:
            check=checks.get(s['file'],{})
            assert check.get('decode_passed'),s['file']
            if check.get('sha256'):assert check['sha256']==s['sha256']
            title=labels.get(name,name)+' · '+s['language']
            similarity=check.get('word_sequence_similarity',0)
            rows.append(f"| {title} | {s['duration_seconds']:.2f} s | {s['generation_seconds']:.1f} s | {s['real_time_factor']:.2f} | {similarity:.1%} |")
            data.append(dict(name=name,**s,asr=check,load_seconds=b['model_load_seconds'],parameters=b['generation_parameters']))
    report=dict(hardware='Intel i7-1165G7, 4 core / 8 thread, circa 16 GB RAM, Intel Iris Xe',device='CPU',threads=4,
        status='auditions_generated_and_checked',pipeline_voice_changed=False,personal_voice_tested=False,
        synthetic_reference_tested=True,quality_note='ASR is not a perceptual quality or voice-similarity score.',samples=data)
    (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# Chatterbox Multilingual V3 — prova sul PC','',report['hardware']+'. Esecuzione CPU, 4 thread, ambiente Python separato.','',
        '| Campione | Audio | Generazione | Tempo/audio | Corrispondenza ASR |','|---|---:|---:|---:|---:|',*rows,'',
        'I tempi escludono il caricamento del modello e comprendono sintesi, conversione in forma d’onda e watermark. Le prime chiamate possono includere inizializzazioni aggiuntive. I valori sono misure di campioni brevi, non un benchmark di un intero documentario.','',
        'Tutti i campioni sono stati decodificati e riconosciuti come italiano/inglese dal modello Whisper locale. La corrispondenza confronta parole riconosciute e testo atteso: non misura naturalezza o identità vocale. Alcune pronunce italiane richiedono ascolto e revisione.','',
        'Il riferimento è un estratto sintetico Kokoro if_sara già prodotto dal progetto, con testo diverso dal campione di prova. Provenienza e SHA sono in reference_sara_source.json. È stato provato il percorso di clonazione da audio, senza una registrazione personale dell’utente.','',
        'La prima prova continua con riferimento Sara ha prodotto 72 campioni oltre il fondo scala prima del salvataggio PCM. È conservata come risultato intermedio. La prova finale a frasi separate salva anche un master float e applica il guadagno necessario prima della conversione PCM, lasciando margine ai picchi e mantenendo il watermark.','',
        '## Ascolto','',
        '- [Italiano: riferimento Sara, frasi separate](chatterbox_it_sara_sentences.wav)',
        '- [Italiano: voce inclusa](chatterbox_it_builtin.wav)',
        '- [Inglese: voce inclusa](chatterbox_en_builtin.wav)',
        '- [Riferimento sintetico originale](reference_sara_synthetic.wav)','',
        '## Valutazione pratica','',
        'Il modello funziona su questo computer senza GPU dedicata. Nei campioni la generazione richiede diversi secondi di calcolo per ogni secondo di audio: la CPU è utilizzabile per prove e produzioni non urgenti. Per documentari lunghi e molte lingue è preferibile il server con GPU. Non è stata misurata la velocità sull’altro PC.','',
        'L’esperimento è separato: non sostituisce Kokoro/Piper nei pack e non aggiunge ancora il selettore TTS nell’app o l’esportazione multitraccia. Installazione, ripetizione della prova e campione vocale proprio sono descritti in [tools/chatterbox/README.md](../../tools/chatterbox/README.md). Nessun servizio TTS esterno e nessuna API a pagamento sono stati utilizzati.','']
    (OUT/'report.md').write_text('\n'.join(lines),encoding='utf-8')
    print(OUT/'report.md')

if __name__=='__main__':main()
