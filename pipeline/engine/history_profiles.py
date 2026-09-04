"""Editorial strategies: shared visual vocabulary, different narrative priorities."""
from dataclasses import dataclass
import re,unicodedata

@dataclass(frozen=True)
class Profile:
    label: str
    scenes: tuple[str,...]
    movement: str
    narration: str
    structure: tuple[str,...]

PROFILES={
 'battle':Profile('Battaglia',('map_overview','battle','person_intro','summary'),'attack','Ritmo dinamico; terreno, decisioni ed eventi simultanei.',('contesto','schieramenti','scontro','conseguenze')),
 'war':Profile('Guerra',('map_overview','territorial_change','battle','timeline','comparison'),'campaign','Alterna strategia, società e costi umani.',('cause','fronti','svolte','pace','conseguenze')),
 'territorial_expansion':Profile('Espansione territoriale',('map_overview','territorial_change','timeline','event_focus','summary'),'expansion','Distingui conquiste, amministrazione e controllo effettivo.',('situazione iniziale','espansioni','consolidamento','perdite','eredità')),
 'migration':Profile('Migrazioni',('map_overview','animated_route','timeline','comparison','summary'),'migration','Persone e gruppi mutevoli; evita di equiparare movimento e invasione.',('origini','cause','percorsi','incontri','insediamenti','conseguenze')),
 'cultural_movement':Profile('Movimento culturale',('city_focus','artwork','person_intro','network_map','document','summary'),'cultural_diffusion','Spiegazione attraverso città, opere, committenti e scambi reciproci.',('contesto','centri','protagonisti','opere','circolazione','eredità')),
 'religious_expansion':Profile('Diffusione religiosa',('map_overview','territorial_change','network_map','person_intro','timeline'),'religious_diffusion','Distingui potere politico, conversioni e pluralità delle comunità.',('origini','comunità','diffusione','istituzioni','diversità','eredità')),
 'trade_network':Profile('Reti commerciali',('network_map','animated_route','artwork','city_focus','comparison','summary'),'trade','Reti, intermediari, merci e conoscenze; niente strada unica immutabile.',('nodi','rotte','merci','scambi','trasformazioni','eredità')),
 'exploration':Profile('Esplorazioni',('map_overview','animated_route','person_intro','document','timeline'),'exploration','Incontri e conseguenze; percorsi incerti dichiarati.',('motivazioni','partenza','tappe','incontri','conseguenze')),
 'political_history':Profile('Storia politica',('timeline','territorial_change','network_map','person_intro','document'),'influence','Alleanze, istituzioni, scelte e popolazioni coinvolte.',('contesto','attori','crisi','trattati','trasformazioni')),
 'revolution':Profile('Rivoluzione',('timeline','city_focus','person_intro','document','comparison'),'influence','Cause molteplici, mobilitazione, svolte e risultati.',('cause','attori','rottura','conflitti','nuovo ordine','eredità')),
 'economic_history':Profile('Storia economica',('data_visualization','network_map','comparison','city_focus','timeline'),'trade','Nessi causa-effetto; quantità soltanto se documentate e comparabili.',('condizioni','meccanismi','cambiamenti','distribuzione','conseguenze')),
 'technology_history':Profile('Storia della tecnologia',('document','person_intro','network_map','data_visualization','timeline'),'technology_diffusion','Distingui invenzione, perfezionamento, adozione ed effetti sociali.',('problema','precedenti','invenzioni','adozione','conseguenze')),
 'biography':Profile('Biografia',('person_intro','timeline','animated_route','document','event_focus','summary'),'journey','Struttura personale; mappe soltanto per spostamenti significativi.',('nascita','formazione','spostamenti','alleati e avversari','ascesa','risultati','caduta','morte','eredità')),
 'general_history':Profile('Storia generale',('map_overview','timeline','event_focus','comparison','summary'),'connection','Contesto, fonti, spiegazione e conseguenze senza determinismo.',('contesto','cause','eventi','conseguenze','eredità')),
}
SCENE_TYPES={'map_overview','territorial_change','animated_route','timeline','person_intro','event_focus','comparison','battle','city_focus','network_map','data_visualization','quote','artwork','document','transition','summary'}
MOVEMENTS={'attack','retreat','campaign','expansion','migration','trade','sea_trade','journey','exploration','cultural_diffusion','religious_diffusion','technology_diffusion','influence','connection','population_transfer','invasion'}
EVENT_TYPES={'battle','treaty','migration','territorial_change','foundation','collapse','discovery','invention','cultural_event','political_event','economic_event','religious_event','birth','death','coronation','revolution','alliance','trade_route_change'}

def normalized(s):return ''.join(c for c in unicodedata.normalize('NFKD',s.lower()) if not unicodedata.combining(c))

def detect_type(topic):
    """Fast routing hint. Source-grounded LLM analysis can refine an uncertain result."""
    t=normalized(topic)
    rules=[('biography',r'biografi|vita di|napoleone|leonardo da vinci'),('territorial_expansion',r'espansion.*(?:impero|roman|territor)|conquiste.*roman'),('religious_expansion',r'islam|cristianesimo|buddh|religio'),('migration',r'migraz|germanic|barbarich'),('cultural_movement',r'rinasciment|illuminism|romanticism|culturale'),('trade_network',r'via della seta|rotte commercial|commerci.*rete'),('exploration',r'esplora|circumnavig|scopert.*america'),('economic_history',r'industrial|economi|produzione|capitalism'),('technology_history',r'tecnolog|invenz|telegrafo|stampa'),('political_history',r'guerra fredda|geopolit|alleanze'),('battle',r'battaglia|waterloo|stalingrado|austerlitz|gettysburg'),('revolution',r'rivoluzion'),('war',r'guerra')]
    # Explicit battle requests outrank the name of a biographical subject.
    if 'battaglia' in t:return 'battle'
    for kind,pattern in rules:
        if re.search(pattern,t):return kind
    if re.search(r'\bviaggi\w*|\bitinerar\w*|\bperiplo\b|\bodisse[ao]\b|ritorno.*(?:ulisse|itaca)',t):return 'exploration'
    return 'general_history'

def choose_scene(scene,kind,index=0):
    if scene.get('scene_type') in SCENE_TYPES:return scene['scene_type']
    if scene.get('chart'):return 'data_visualization'
    if scene.get('asset_ids'):return 'artwork'
    if scene.get('person_ids'):return 'person_intro'
    if scene.get('territory_ids'):return 'territorial_change'
    if scene.get('network'):return 'network_map'
    if scene.get('movements'):return 'animated_route'
    if scene.get('comparison'):return 'comparison'
    if scene.get('event_ids'):return 'timeline'
    return 'map_overview' if scene.get('location_ids') else ('summary' if index else 'event_focus')
