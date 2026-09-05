"""Reusable editorial direction and observable visual coverage, opt-in for new plans."""
import re,unicodedata

MAP_SCENES={'map_overview','animated_route','territorial_change','city_focus','network_map','battle'}


def direction_for(topic,kind,basis='history'):
    text=''.join(c for c in unicodedata.normalize('NFKD',topic.lower()) if not unicodedata.combining(c))
    journey=kind=='exploration' or bool(re.search(r'\bviaggi\w*|\bitinerar\w*|\bperiplo\b|\brientr\w*|\btraversat\w*|\bspostament\w*|\britorno.*(?:ulisse|odisseo|itaca)|\b(?:ulisse|odisse[ao]).*(?:ritorn\w*|rientr\w*|itaca)|\bodisse[ao]\b',text))
    return {'version':1,'movement_sync':1,'territory_style':2,'territory_mode':'territory' if kind=='territorial_expansion' else 'influence' if kind=='political_history' else '',
            'journey':journey,'map_led':journey or kind in {'migration','trade_network','territorial_expansion','political_history'},
            'timeline_mode':'sequence' if basis=='literary_tradition' else 'historical','auto_persons':True}


def shot_role(direction,index,count):
    if not direction.get('journey'):return 'appropriate_visual'
    if index in (0,count-1):return 'geographic_anchor'
    return 'supporting_scene' if index%3==0 else 'journey_progress'


def direction_prompt(direction):
    text='''REGIA VISIVA: il piano deve descrivere cosa cambia sullo schermo, oltre al racconto.
Ogni scena di mappa deve avere luoghi pertinenti, movimenti, reti o territori visibili: vietate mappe vuote che ereditano il luogo precedente.
animated_route richiede movements con almeno due punti distinti, oppure schematic_journey. person_ids attiva un ritratto in riquadro anche sulle mappe e sulle schede.
schematic_journey={"stops":["Tappa precedente","Tappa attuale","Tappa successiva"],"note":"Localizzazioni non accertate"} è una sequenza ANIMATA priva di coordinate, sovrapposta a una carta DI ORIENTAMENTO con focus geografici reali. Usa 2–5 tappe distinte, brevi, in ordine narrativo; non è una rotta geografica.
Non sostituire le immagini con solo testo se il soggetto ha spostamenti o persone rappresentabili. Per scene di opere usa asset con licenza e provenienza verificabili; se mancano, scegli un altro componente pertinente.
Se rappresenti una rotta geografica incerta, indica uncertain=true e una nota sulle basi della ricostruzione; non inventare localizzazioni tradizionali prive di riscontri. Una mappa può accompagnare la sequenza di tappe non localizzate senza collocarle falsamente sulla carta.
La sola presenza di ID di personaggi nel catalogo non equivale a raccontarli: collega person_ids alle scene pertinenti. Non aggiungere punti fittizi per superare un controllo.'''
    if direction.get('journey'):
        text+='''\nLa richiesta riguarda un VIAGGIO: conserva una regia prevalentemente cartografica. La prima e ultima scena mostrano partenza e arrivo con focus pertinenti; per l'apertura usa entrambi quando utili all'orientamento.
Le assegnazioni journey_progress richiedono animated_route con movements oppure schematic_journey e una carta di orientamento. Le supporting_scene possono mostrare personaggi, opere o brevi spiegazioni. Non decidere che la carta è secondaria al racconto e non trasformare il viaggio in una successione di sole slide.
Per ogni gruppo di scene conserva continuità delle tappe, evitando episodi duplicati. La narrazione deve raccontare esattamente ciò che queste scene permettono di vedere.'''
        text+='''\nOgni movements geografico usa from e to come ID del catalogo e cue=0 oppure cue=1. La scena deve nominare nel proprio event la destinazione to: non assegnare alla tappa attuale la freccia verso una tappa che verrà raccontata soltanto nella scena successiva. cue=0 accompagna il primo paragrafo narrato, di norma un arrivo; cue=1 accompagna il secondo, di norma una partenza o la prosecuzione del percorso.'''
    if direction.get('timeline_mode')=='sequence':
        text+='\nMostra la successione narrativa degli episodi, senza far scorrere anni inventati. historical_period resta una cornice; historical_range non rappresenta la durata del viaggio.'
    if direction.get('territory_mode'):
        text+='''\nREGIA TERRITORIALE: mostra aree colorate con visual_layers e territory_ids, non soltanto frecce. Usa kind=territory per controllo politico, influence per influenza senza sovranità, alliance per alleanze, contested per zone contese. Ogni area richiede label, color, sources, schematic=true, states=[{year,polygons}] e label_pos quando utile. Le coordinate prodotte dal modello sono sempre schematiche: non sono confini verificati. Non sostituire confini antichi con quelli moderni. Mantieni lo stesso ID fra scene e aggiungi stati cronologici: ogni stato contiene l’intera geometria di quella data; polygons=[] indica la perdita completa. territory_ids elenca anche i livelli precedenti da conservare visibili nella scena. Gli intervalli historical_range devono essere continui quando si mostrano trasformazioni continue. transition_years può rendere morbido un passaggio illustrativo, senza farlo passare per una data storica misurata. Se le fonti non consentono di delineare neppure un’area indicativa, usa città e relazioni e spiega la limitazione in event e uncertainties.'''
    return text


def scene_issues(scene,direction,role=None):
    kind=scene.get('scene_type');issues=[]
    focus=scene.get('location_ids',scene.get('focus',[]))
    moves=scene.get('movements',[]);net=scene.get('network') or {};journey=scene.get('schematic_journey')
    route=bool(moves or net.get('edges') or journey)
    geography=bool(focus or moves or net.get('nodes') or net.get('edges') or scene.get('territory_ids') or scene.get('units'))
    if kind in MAP_SCENES and not geography:issues.append('mappa vuota: manca un riferimento geografico pertinente')
    if (moves or journey) and kind not in MAP_SCENES:issues.append('movimento nascosto da una scena testuale: scegli animated_route')
    if kind=='animated_route' and not route:issues.append('animated_route senza percorso: aggiungi movements o schematic_journey con tappe motivate')
    if journey:
        stops=journey.get('stops') if isinstance(journey,dict) else None
        if not isinstance(stops,list) or not 2<=len(stops)<=5 or any(not isinstance(s,str) or not s.strip() or len(s)>60 for s in stops) or len(set(stops))!=len(stops):
            issues.append('schematic_journey.stops richiede 2–5 etichette distinte, di massimo 60 caratteri')
        if not isinstance(journey,dict) or not isinstance(journey.get('note'),str) or not journey['note'].strip() or len(journey['note'])>180:
            issues.append('schematic_journey.note deve spiegare in massimo 180 caratteri perché le tappe non sono geolocalizzate')
        if not focus:issues.append('la sequenza senza coordinate richiede focus per la carta di orientamento')
    for movement in moves:
        points=movement.get('points',[])
        if len({tuple(p) for p in points})<2:issues.append('movimento senza spostamento: servono punti geografici distinti')
    if kind=='person_intro' and not scene.get('person_ids'):issues.append('introduzione senza personaggio')
    if kind in {'artwork','document'} and not scene.get('asset_ids'):issues.append('scena di opera/documento senza immagine associata')
    if kind=='network_map' and not net.get('edges'):issues.append('rete senza collegamenti')
    if kind=='territorial_change' and not scene.get('territory_ids'):issues.append('cambiamento territoriale senza livello territoriale')
    if kind=='data_visualization' and not scene.get('chart'):issues.append('grafico senza dati')
    if role=='geographic_anchor' and (kind not in MAP_SCENES or not focus):issues.append('partenza/arrivo devono essere mostrati su una mappa con focus pertinente')
    if role=='journey_progress' and (kind!='animated_route' or not route):issues.append('questa scena deve fare avanzare il viaggio: animated_route con percorso o sequenza di tappe')
    return issues


def coverage(document):
    direction=document.get('visual_direction') or document.get('metadata',{}).get('visual_direction',{})
    scenes=document.get('scenes',[]);problems=[]
    expected_count=max(len(scenes),int(direction.get('scene_count') or len(scenes)))
    if direction.get('version')==1:
        for i,s in enumerate(scenes):
            scene_index=int(s.get('index',i))
            for message in scene_issues(s,direction,shot_role(direction,scene_index,expected_count)):
                problems.append(f"Scena {i+1} ({s.get('title','')}): {message}.")
    return {'policy_version':direction.get('version',0),'scenes':len(scenes),
            'map_scenes':sum(s.get('scene_type') in MAP_SCENES for s in scenes),
            'geographic_routes':sum(len(s.get('movements',[])) for s in scenes),
            'schematic_journeys':sum(bool(s.get('schematic_journey')) for s in scenes),
            'person_scenes':sum(bool(s.get('person_ids')) for s in scenes),
            'issues':problems,'passed':not problems}


def require_coverage(document):
    report=coverage(document)
    if report['issues']:raise ValueError('Regia visiva incompleta: '+' '.join(report['issues'][:6]))
    return report
