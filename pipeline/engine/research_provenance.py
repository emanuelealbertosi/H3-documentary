"""Explicit provenance for hybrid productions; external source IDs stay real."""
import copy


def uses_model_knowledge(document):
    research=document.get('research',{})
    return research.get('mode')=='hybrid' and research.get('fallback_used') is True


def apply_context(document, context):
    if not context:
        return document
    document['research']=copy.deepcopy(context)
    if not uses_model_knowledge(document):
        return document
    notice=context['notice']
    document['source_method']=notice+' Fonti elencate: soltanto pagine effettivamente consultate. La conoscenza del modello non è una fonte bibliografica.'
    document.setdefault('editorial_notes',[]).append(notice)
    document.setdefault('metadata',{})['authoring']='Modello configurato; conoscenza interna e pagine disponibili, revisione automatica non indipendente.'
    def annotate(value):
        if isinstance(value,dict):
            if 'sources' in value or 'source_ids' in value:
                refs=value.get('sources',value.get('source_ids',[]))
                value['evidence_status']='external_references_not_independently_verified' if refs else 'model_knowledge_unverified'
            for key,item in list(value.items()):
                if key not in ('sources','source_ids','research'):annotate(item)
        elif isinstance(value,list):
            for item in value:annotate(item)
    for key in ('scenes','events','persons','entities','visual_layers'):
        annotate(document.get(key,[]))
    # A bibliography link does not license statistics invented from memory.
    for scene in document.get('scenes',[]):
        if scene.get('chart') and not scene['chart'].get('sources'):
            raise ValueError('Un grafico quantitativo richiede fonti consultate, anche in modalità ibrida.')
        if scene.get('quote') and not scene.get('sources'):
            raise ValueError('Una citazione testuale richiede fonti consultate, anche in modalità ibrida.')
    return document


def export_provenance(root, timeline):
    """Called before legacy exporter archives documents; inert for old packs."""
    if not uses_model_knowledge(timeline):
        return
    research=timeline['research']
    rows=['# Fonti e metodo', '', '## Verifica delle informazioni', research['notice'],
          'Le conoscenze interne del modello non costituiscono una fonte consultabile. La revisione automatica controlla la coerenza, ma non certifica la verità storica.',
          '', '## Pagine effettivamente consultate', '']
    if not timeline['sources']:
        rows.append('Nessuna pagina esterna consultabile acquisita per questa produzione.')
    for source in timeline['sources']:
        rows.extend([f'### {source["id"]} — {source["title"]}', f'[{source["title"]}]({source["url"]})',source['use'],''])
    rows.extend(['## Provenienza per scena', 'La presenza di riferimenti indica pagine pertinenti, non una verifica indipendente di ogni frase.'])
    for scene in timeline['scenes']:
        refs=', '.join(scene.get('sources',[]))
        state=('Riferimenti esterni: '+refs+'; possibile integrazione dalla conoscenza del modello, da verificare.') if refs else 'Conoscenza interna del modello: contenuti non verificati con fonti esterne.'
        rows.append(f'- {scene["id"]} — {scene["title"]}: {state}')
    rows.extend(['', '## Note editoriali', *['- '+note for note in timeline.get('editorial_notes',[])]])
    (root/'sources.md').write_text('\n\n'.join(rows)+'\n',encoding='utf-8')
    path=root/'script.md'
    script=path.read_text(encoding='utf-8').replace('Fonti: .*','Fonti: nessuna pagina consultata; conoscenza del modello non verificata.*')
    script+='\n\n## Livello di verifica\n\n'+research['notice']+'\n'
    path.write_text(script,encoding='utf-8')
    path=root/'output/youtube_description.txt'
    description=path.read_text(encoding='utf-8')
    path.write_text(description+'\n\nVERIFICA DELLE INFORMAZIONI\n'+research['notice']+'\n',encoding='utf-8')
