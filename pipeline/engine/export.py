"""Source notes, human-readable script, captions, YouTube description and chapters."""
from pathlib import Path
import re,html
import shutil
from .common import ROOT,stamp,read_json,write_json

def clean(s):return html.unescape(re.sub('<[^>]+>','',s)).strip()

def export_documents(timeline):
    if timeline.get('documentary_schema_version')==2:write_json(ROOT/'timeline.json',timeline)
    out=ROOT/'output'; out.mkdir(exist_ok=True)
    script=[f'# {timeline["title"]}','',f'Durata misurata: **{stamp(timeline["duration"])}**. Lingua: italiano.',
       '','Testo originale; voce sintetica locale. Il testo TTS usa un dizionario di pronuncia separato: i sottotitoli conservano la grafia storica.','']
    captions=[]; chapter=[';FFMETADATA1',f'title={timeline["title"]}','artist=DocumentariAI','language=ita']
    caption_id=0
    for s in timeline['scenes']:
        script.extend([f'## {stamp(s["start"])} — {s["title"]}',f'*Tempo storico: {s["date"]}. Fonti: {", ".join(s["sources"])}.*',''])
        script.extend(s['lines']); script.append('')
        script.extend(['Elementi visivi: '+s['kicker']+'. '+('; '.join(s['facts'])), ''])
        chapter+=['[CHAPTER]','TIMEBASE=1/1000',f'START={round(s["start"]*1000)}',f'END={round(s["end"]*1000)}',f'title={s["title"]}']
        for cue in s['cues']:
            # Phrase-sized soft subtitles, timed by word weights inside each measured TTS cue.
            words=cue['text'].split(); groups=[]; group=[]; nchars=0
            for w in words:
                if nchars+len(w)>77 and group:groups.append(group);group=[];nchars=0
                group.append(w);nchars+=len(w)+1
            if group:groups.append(group)
            weights=[sum(len(w)+1 for w in g) for g in groups]; whole=sum(weights); at=cue['start']
            for group,weight in zip(groups,weights):
                length=(cue['end']-cue['start'])*weight/whole
                midpoint=len(group)//2
                if sum(map(len,group))>44:text=' '.join(group[:midpoint])+'\n'+' '.join(group[midpoint:])
                else:text=' '.join(group)
                caption_id+=1
                captions.append(f'{caption_id}\n{stamp(s["start"]+at,True)} --> {stamp(s["start"]+at+length,True)}\n{text}\n')
                at+=length
    script+=['## Note editoriali','',*['- '+x for x in timeline['editorial_notes']]]
    if timeline.get('documentary_schema_version')==2:
        from .history_export import augment_script
        script=augment_script(script,timeline)
    (ROOT/'script.md').write_text('\n\n'.join(script),encoding='utf-8')
    srt=out/f'{timeline["slug"]}_it.srt'; srt.write_text('\n'.join(captions),encoding='utf-8')
    meta=ROOT/'build'/timeline['slug']/'chapters.ffmetadata'; meta.write_text('\n'.join(chapter)+'\n',encoding='utf-8')
    sources=['# Fonti e metodo','', 'Sintesi originale in italiano; nessuna riproduzione estesa dei testi delle fonti.','',
      timeline.get('source_method','Le ricostruzioni sono confrontate fra fonti indipendenti. Orari, posizioni e consistenze indicativi sono segnalati nel video.'),'']
    for src in timeline['sources']:
        sources.extend([f'## {src["id"]} — {src["title"]}',f'[{src["title"]}]({src["url"]})',src['use'],''])
    sources+=['## Scelte di ricostruzione','',*['- '+x for x in timeline['editorial_notes']], '',
     '## Tracciabilità','', 'Ogni scena in timeline.json contiene gli identificatori delle fonti, coordinate longitudine/latitudine dei luoghi e delle unità, percorsi, direzioni, comandanti, intervalli storici, cue audio misurati e timestamp video. La posizione del simbolo indica un settore operativo, non la geometria esatta della formazione.',
     '', timeline.get('territorial_note','Confini, schieramenti e luoghi seguono il periodo rappresentato; i percorsi sono interpretativi.'),
     '', 'La sinistra/destra degli eserciti è riferita al rispettivo orientamento. Le direzioni geografiche seguono la freccia del nord sulla mappa.']
    if timeline.get('documentary_schema_version')==2:
        sources=sources[:sources.index('## Tracciabilità')]+['## Tracciabilità','Ogni scena cita le fonti consultate. Eventi, livelli geografici e dati conservano riferimenti e note di incertezza. I timestamp video sono misurati dalla voce; negli studi preliminari sono esplicitamente stimati.',timeline.get('territorial_note','')]
    (ROOT/'sources.md').write_text('\n\n'.join(sources),encoding='utf-8')
    credits=['# Crediti e licenze','', '## Materiale originale','',
       'Sceneggiatura italiana, montaggio, cartografia illustrativa, animazioni, musica ed effetti procedurali realizzati per questo progetto. Il codice originale è rilasciato con licenza MIT; gli asset originali prodotti dal codice con CC0-1.0. I ritratti e le dipendenze mantengono le rispettive licenze.',
       '', '## Voce locale','',
       timeline.get('voice_credit','Voce sintetica locale; modello e licenza nel manifest degli asset.'),
       '', 'Kokoro: https://huggingface.co/hexgrad/Kokoro-82M. Kokoro-ONNX: https://github.com/thewh1teagle/kokoro-onnx. Attribuzioni dei dati dichiarate dalla model card: Koniwa, CC BY 3.0, https://github.com/koniwa/koniwa; SIWIS, CC BY 4.0, https://datashare.ed.ac.uk/handle/10283/2353. Le model card e licenze sono conservate negli asset. Il prototipo Piper/Paola è conservato come alternativa tecnica, ma non è la voce del video finale.',
       '', '## Ritratti storici','']
    # BEGIN H3 TTS CREDIT
    if timeline.get('voice_engine') in ('chatterbox','tts_api'):
        legacy='Kokoro: https://huggingface.co/hexgrad/Kokoro-82M. Kokoro-ONNX: https://github.com/thewh1teagle/kokoro-onnx. Attribuzioni dei dati dichiarate dalla model card: Koniwa, CC BY 3.0, https://github.com/koniwa/koniwa; SIWIS, CC BY 4.0, https://datashare.ed.ac.uk/handle/10283/2353. Le model card e licenze sono conservate negli asset. Il prototipo Piper/Paola è conservato come alternativa tecnica, ma non è la voce del video finale.'
        if timeline.get('voice_engine')=='chatterbox':
            replacement='Chatterbox Multilingual V3: https://github.com/resemble-ai/chatterbox e https://huggingface.co/ResembleAI/chatterbox. Codice e pesi MIT alle revisioni registrate nel manifest. Sintesi eseguita localmente; il campione one-shot, quando usato, resta nel progetto. Chatterbox applica il proprio watermark audio.'
        else:
            api=timeline.get('voice_api',{});replacement=f'Sintesi tramite server TTS configurato: {api.get("name",api.get("provider","API TTS"))}. Il testo narrato è stato inviato al server; l’audio è stato normalizzato localmente. Condizioni e licenza della voce dipendono dal provider scelto.'
        credits[credits.index(legacy)]=replacement
    # END H3 TTS CREDIT
    if timeline.get('video_license'):
        credits[2:2]=['## Licenza del video',timeline['video_license'],'']
    portrait_credits=[]
    for id,c in timeline['commanders'].items():
        mp=(ROOT/c['portrait']).with_suffix('.metadata.json')
        md=read_json(mp); ex=md['extmetadata']
        author=clean(ex.get('Attribution',ex.get('Artist',{})).get('value','Attribuzione nella scheda originale'))
        license_name=clean(ex.get('LicenseShortName',{}).get('value','Vedere scheda'))
        license_url=clean(ex.get('LicenseUrl',{}).get('value',''))
        title=clean(ex.get('ObjectName',{}).get('value',c['name']))
        credits.extend([f'### {c["name"]}',f'{title}. {author}. **{license_name}**. '+(f'[Licenza]({license_url}).' if license_url else ''),
          f'[Scheda e provenienza]({md["descriptionurl"]}). Riproduzione bidimensionale, ritagliata e ridimensionata nel montaggio. File sorgente integro in `{c["portrait"]}`; metadati della licenza conservati accanto al file.',''])
        if 'public domain' not in license_name.lower():
            portrait_credits.append(f'{c["name"]}: {author}; {license_name}; ritaglio/ridimensionamento. {md["descriptionurl"]}')
    if timeline.get('extra_credits'):credits+=['## Cartografia e dati geografici','',timeline['extra_credits'],'']
    credits+=['## Caratteri e strumenti','',
      'Bebas Neue, Manrope e Cormorant Garamond — SIL Open Font License 1.1. Font e testi OFL in assets/fonts; provenienza: https://github.com/google/fonts.',
      '', 'FFmpeg 7.1 tramite imageio-ffmpeg: encoding H.264/libx264 e AAC. FFmpeg/libx264 soggetti alle rispettive licenze software, senza tariffa API. NumPy, SciPy, Pillow e OpenCV: dipendenze open source elencate in requirements.txt. Nessuna musica commerciale, immagine generata con servizi a pagamento o registrazione esterna di effetti sonori.',
      '', 'Le licenze dei programmi regolano la distribuzione del software; non impongono la licenza GPL al video prodotto. Per ridistribuire l’intero ambiente Python o i binari, consultare e rispettare le licenze dei singoli pacchetti.',
      '', '## Manifest degli asset','', 'assets/manifest.json registra URL, licenza dichiarata, percorso locale e impronta SHA-256 di ogni asset scaricato.']
    if timeline.get('documentary_schema_version')==2:
        from .history_export import asset_credits
        credits+=asset_credits(timeline)
    # BEGIN H3 IMAGE INSETS
    if timeline.get('user_media'):
        from .image_insets import credits as image_credits
        credits+=image_credits(timeline)
    if timeline.get('asset_usage'):
        from .image_rights import image_license_notice
        credits+=['',*image_license_notice(timeline,root=ROOT)]
    # END H3 IMAGE INSETS
    (ROOT/'credits.md').write_text('\n\n'.join(credits),encoding='utf-8')
    description=[timeline['title'],'',timeline.get('description','Un documentario storico in italiano attraverso mappe animate e ritratti storici.'),'', 'CAPITOLI']
    description.extend(f'{stamp(s["start"])[3:]} {s["title"]}' for s in timeline['scenes'])
    description+=['',timeline.get('map_notice','Mappe, rilievi e movimenti schematici; orari ed effettivi indicativi.')+' Voce sintetica italiana generata localmente. Musica ed effetti originali procedurali. Ritratti storici da Wikimedia Commons: provenienza e licenze nei crediti.','', 'FONTI PRINCIPALI']
    # BEGIN H3 LOCAL DOCUMENT LINKS
    # A private relative file path is useful inside sources.md, but it must not
    # leak into the public YouTube description. Preserve source order while
    # counting only links that a viewer can open.
    all_sources=timeline['sources']
    timeline['sources']=[src for src in all_sources if str(src.get('url','')).startswith(('http://','https://'))]
    # END H3 LOCAL DOCUMENT LINKS
    description.extend(src['title']+' — '+src['url'] for src in timeline['sources'][:4 if timeline.get('video_license') else 8])
    # BEGIN H3 LOCAL DOCUMENT LINKS
    timeline['sources']=all_sources
    # END H3 LOCAL DOCUMENT LINKS
    if timeline.get('extra_credits'):description+=['','CARTOGRAFIA E LICENZE',timeline['extra_credits'],*portrait_credits]
    if timeline.get('video_license'):
        description+=['','LICENZA E RITRATTI',timeline['video_license'],*portrait_credits,
          'Licenze ritratti: https://creativecommons.org/licenses/by/4.0/ ; https://creativecommons.org/licenses/by-sa/3.0/de/ . Fonti complete e crediti nel progetto.']
    # BEGIN H3 IMAGE INSETS
    if timeline.get('asset_usage'):
        from .image_rights import image_license_notice
        description+=['',*image_license_notice(timeline,root=ROOT)]
    # END H3 IMAGE INSETS
    (out/'youtube_description.txt').write_text('\n'.join(description),encoding='utf-8')
    # BEGIN H3 RESEARCH PROVENANCE
    if timeline.get('research', {}).get('fallback_used'):
        from .research_provenance import export_provenance
        export_provenance(ROOT, timeline)
    # END H3 RESEARCH PROVENANCE
    archive=ROOT/('documentaries' if timeline.get('documentary_schema_version')==2 else 'battles')/timeline['slug'];archive.mkdir(exist_ok=True,parents=True)
    for name in ['script.md','sources.md','credits.md','timeline.json']:
        shutil.copy2(ROOT/name,archive/name)
    shutil.copy2(out/'youtube_description.txt',archive/'youtube_description.txt')
    shutil.copy2(out/'youtube_description.txt',out/f'{timeline["slug"]}_youtube_description.txt')
    return srt,meta
