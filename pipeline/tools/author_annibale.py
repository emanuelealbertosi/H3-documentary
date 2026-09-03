"""Editorially authored Hannibal pack, rendered by the shared atlas engine."""
import sys,re
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine.common import ROOT,write_json,validate_pack

P={
 'cartagine':('Cartagine',[10.323,36.852]),'roma':('Roma',[12.492,41.89]),
 'gades':('Gades',[-6.30,36.53]),'cartagena':('Nuova Cartagine',[-.986,37.60]),
 'sagunto':('Sagunto',[-.278,39.681]),'ebro':('Ebro',[.67,40.72]),
 'pirenei':('Pirenei',[2.45,42.55]),'emporion':('Emporion',[3.12,42.13]),
 'rodano':('Rodano',[4.78,44.13]),'massalia':('Massalia',[5.369,43.297]),
 'alpi':('Alpi',[7.3,45.7]),'taurini':('Taurini',[7.686,45.07]),
 'ticino':('Ticino · 218 a.C.',[8.95,45.15]),'trebbia':('Trebbia · 218 a.C.',[9.615,45.01]),
 'trasimeno':('Trasimeno · 217 a.C.',[12.12,43.21]),'canne':('Canne · 216 a.C.',[16.132,41.296]),
 'capua':('Capua',[14.252,41.083]),'aniene':('Aniene',[12.56,41.95]),
 'bernardo':('Piccolo San Bernardo',[6.883,45.682]),'moncenisio':('Moncenisio',[6.90,45.26]),
 'clapier':('Clapier',[6.93,45.17]),'monginevro':('Monginevro',[6.72,44.93]),'traversette':('Traversette',[7.07,44.709])}
pos=lambda k:P[k][1]
places={k:dict(name=n,pos=p) for k,(n,p) in P.items()}
places['roma']['size']=28;places['cartagine']['size']=28;places['cartagena']['size']=25
places['roma']['color']=[221,109,101]
places['cartagine']['color']=places['cartagena']['color']=[239,185,93]
def route(points,**kw):return dict({'points':[pos(x) if isinstance(x,str) else x for x in points],'side':'carthage','cue':0},**kw)
sea=route(['cartagine',[9.8,37.5],[7,37.9],[3,38.2],[0,37.4],[-2.7,36.4],[-5.1,35.98],[-5.7,36.05],'gades'],uncertain=True)
iberia=route(['gades',[-4.4,37.4],[-2.3,37.7],'cartagena'],uncertain=True)
north=route(['cartagena',[-.5,38.2],[-.3,38.8],'sagunto',[.1,40.1],'ebro',[.61,40.82],[.88,41.00],[1.14,41.17],[1.5,41.3],[2.1,41.7],'emporion',[2.84,42.49]])
gaul=route([[2.84,42.49],[2.95,42.9],[3.02,43.18],[3.3,43.45],[3.9,43.65],[4.38,43.9],[4.72,44.13]],uncertain=True)
toalps=route([[4.8,44.13],[4.9,44.55],[4.9,44.9],[5.6,45.18]],uncertain=True)
alps=route([[5.6,45.18],[6.25,45.2],[6.85,45.15],'taurini'],uncertain=True)
po=route(['taurini',[8.05,45.06],[8.55,45.06],'ticino','trebbia'],uncertain=True)
etruria=route(['trebbia',[9.85,44.55],[10.4,44.05],[10.9,43.65],[11.45,43.4],'trasimeno'],uncertain=True)
apulia=route(['trasimeno',[12.7,43.4],[13.35,43.1],[13.9,42.8],[14.55,42.2],[15.3,41.65],'canne'],uncertain=True)
torome=route(['capua',[14.05,41.4],[14.0,41.65],[13.55,41.91],[13.25,42.15],[12.85,42.14],'aniene'],uncertain=True)
def past(*routes):return [dict(r,complete=True,alpha=135,marker=False) for r in routes]
def reg(text,pos,size=34):return dict(text=text,pos=pos,size=size)
def call(text,pos,cue=0,offset=[0,-62]):return dict(text=text,pos=pos,cue=cue,offset=offset)
uncertain=[dict(points=[[5.3,44.7],[5.3,45.6],[6.6,46.0],[7.6,45.45],[7.7,44.5],[6.8,44.3]])]
overview=[reg('IBERIA',[-3.4,40.1]),reg('GALLIA',[2.0,46.5]),reg('ITALIA',[13.3,43.0]),reg('AFRICA',[8.2,33.3]),reg('MARE MEDITERRANEO',[4.5,37.8],29)]
scenespec=[
 dict(view=[7,41,43],visible=['cartagine','roma','cartagena'],regions=overview,kicker='Un esercito attraversa il Mediterraneo occidentale',fact='Dalle origini cartaginesi alla minaccia contro Roma',routes=[],mode='opening'),
 dict(view=[9.7,37.2,17],visible=['cartagine','roma'],regions=[reg('SICILIA',[14.3,37.4],30),reg('AFRICA',[8.7,34.8]),reg('SARDEGNA',[8.9,40.0],26)],kicker='Cartagine e Roma dopo la prima guerra punica',fact='La ricerca di nuove risorse porta i Barca verso l’Iberia',routes=[]),
 dict(view=[1.9,38.4,31],visible=['cartagine','cartagena','gades'],regions=[reg('IBERIA',[-3.4,40.1]),reg('MARE MEDITERRANEO',[4.2,37.7],29)],kicker='Il giovane Annibale accompagna Amilcare',fact='237 a.C. · Il trasferimento in Iberia precede l’invasione di 19 anni',routes=[sea,dict(iberia,cue=1)]),
 dict(view=[-.9,38.8,12],visible=['cartagena','sagunto'],regions=[reg('IBERIA',[-3.3,39.6])],kicker='Un comandante di circa ventisei anni',fact='221 a.C. · Annibale assume il comando in Iberia',routes=[],commander=True),
 dict(view=[.2,39.55,8],visible=['cartagena','sagunto','ebro'],regions=[],kicker='Sagunto e la crisi diplomatica',fact='219–218 a.C. · Dall’assedio alla guerra aperta',routes=[route(['cartagena','sagunto'],cue=0)]),
 dict(view=[.8,40.8,13],visible=['cartagena','sagunto','ebro','emporion','pirenei'],regions=[reg('IBERIA',[-2,40.4],34)],kicker='La spedizione parte da Nuova Cartagine',fact='218 a.C. · Guarnigioni, congedi e perdite riducono la colonna',routes=[north],offsets={'pirenei':[-90,-35],'emporion':[65,24]}),
 dict(view=[3.7,43.5,11],visible=['pirenei','emporion','rodano','massalia'],regions=[reg('GALLIA',[2,44.8])],kicker='Attraverso territori e comunità indipendenti',fact='Accordi, guide e rifornimenti rendono possibile la marcia',routes=past(north)+[gaul],offsets={'pirenei':[-45,-32],'emporion':[50,25],'rodano':[50,-27],'massalia':[65,30]}),
 dict(view=[4.55,44.05,4.8],visible=['rodano','massalia'],regions=[],kicker='Un attraversamento sotto minaccia',fact='Una forza aggira gli avversari mentre il grosso attraversa',routes=[route([[4.64,44.09],[4.66,44.42],[4.91,44.48],[4.91,44.18]],cue=1,uncertain=True),route([[4.64,44.09],[4.89,44.10]],cue=1)],offsets={'rodano':[55,-28]},callouts=[call('Guado non identificato con certezza',[4.77,44.13],0,[-150,-135])]),
 dict(view=[6.2,44.5,13],visible=['massalia','rodano','taurini','alpi'],regions=[],kicker='Scipione cambia teatro operativo',fact='Annibale prosegue verso l’interno; Roma difende il Po',routes=past(gaul)+[toalps,route(['massalia',[6.0,43.35],[7.0,43.6],[8.4,44.1]],side='rome',cue=1,uncertain=True)],offsets={'alpi':[70,-25]}),
 dict(view=[6.2,45.14,8.3],visible=['bernardo','moncenisio','traversette','taurini'],regions=[reg('ALPI',[8.45,46.1],43)],kicker='La questione del valico resta aperta',fact='Diverse ipotesi: il percorso alpino non è accertato',routes=past(toalps),areas=uncertain,offsets={'bernardo':[-155,-25],'moncenisio':[-150,5],'traversette':[-150,30],'taurini':[45,40]}),
 dict(view=[6.8,45.02,6.7],visible=['taurini'],regions=[reg('ALPI',[7.65,45.8],40)],kicker='Fame, imboscate e passaggi da ripristinare',fact='La discesa mette alla prova uomini, cavalli e animali da soma',routes=[],areas=uncertain,callouts=[call('Settore di attraversamento incerto',[6.5,45.1],0,[-180,-120])]),
 dict(view=[8.4,45.15,10.5],visible=['taurini','ticino','trebbia'],regions=[reg('PIANURA DEL PO',[9.8,45.65],32)],kicker='L’esercito raggiunge l’Italia settentrionale',fact='Polibio: circa 20.000 fanti e 6.000 cavalieri all’arrivo',routes=[alps],offsets={'ticino':[-60,-40],'trebbia':[70,28]}),
 dict(view=[9.2,45.0,6.7],visible=['taurini','ticino','trebbia'],regions=[],kicker='La cavalleria e il terreno diventano decisivi',fact='218 a.C. · Successi cartaginesi al Ticino e alla Trebbia',routes=[po],offsets={'ticino':[-80,-35],'trebbia':[75,36]},callouts=[call('Dicembre: battaglia della Trebbia',pos('trebbia'),1,[60,-150])]),
 dict(view=[11.5,43.6,8.0],visible=['trasimeno','roma'],regions=[reg('ETRURIA',[10.8,43.5],33),reg('APPENNINI',[12.35,43.8],28)],kicker='L’acqua e le alture chiudono la trappola',fact='217 a.C. · L’esercito di Flaminio viene sconfitto',routes=[etruria],callouts=[call('Lago Trasimeno',pos('trasimeno'),1,[125,-105])]),
 dict(view=[12.2,42.8,15.4],visible=['roma','trasimeno','capua','canne'],regions=[reg('ITALIA',[13.9,44.1],40)],kicker='Fabio Massimo limita le occasioni di battaglia',fact='La posta in gioco è la rete degli alleati di Roma',routes=past(etruria)),
 dict(view=[15.6,41.55,7.3],visible=['canne','capua'],regions=[reg('APULIA',[16.8,40.9],32)],kicker='Il centro arretra, i fianchi si chiudono',fact='216 a.C. · A Canne Roma subisce una catastrofe',routes=[apulia],callouts=[call('CANNE',pos('canne'),0,[-90,-105])],diagram='cannae'),
 dict(view=[13.8,41.9,13.2],visible=['roma','capua','canne'],regions=[reg('ITALIA',[15.0,43.8],38)],kicker='Una vittoria campale non garantisce una conquista',fact='Capua si schiera con Annibale; molte città restano con Roma',routes=[]),
 dict(view=[13.25,41.6,6.7],visible=['roma','capua'],regions=[reg('LAZIO',[12.6,41.55],28),reg('CAMPANIA',[14.55,40.7],26)],kicker='Annibale cerca di salvare Capua',fact='211 a.C. · Minacciare Roma per dividere gli assedianti',routes=[],callouts=[call('Assedio romano',pos('capua'),0,[40,-85])]),
 dict(view=[12.65,41.93,3.3],visible=['roma','aniene'],regions=[],kicker='La minaccia raggiunge il territorio della capitale',fact='211 a.C. · Annibale si accampa a pochi chilometri dalle mura',routes=[torome],offsets={'roma':[-110,50],'aniene':[105,-45]},callouts=[call('Roma viene difesa',pos('roma'),1,[-160,-130])]),
 dict(view=[13.1,41.75,7.0],visible=['roma','aniene','capua'],regions=[],kicker='La manovra non libera Capua',fact='Annibale si ritira; Roma non viene conquistata',routes=past(torome)+[route(['aniene',[12.9,42.1],[13.25,42.0]],cue=1,uncertain=True)],offsets={'roma':[-95,38],'aniene':[95,-33]}),
 dict(view=[7,41,43],visible=['cartagine','cartagena','roma','rodano','capua'],regions=overview,kicker='Tre fasi diverse, una lunga guerra',fact='237: Iberia · 218: invasione dell’Italia · 211: alle porte di Roma',routes=past(sea,north,gaul,toalps,alps,po,etruria,apulia,torome),mode='ending')
]

SOURCES=[
 dict(id='POL3',title='Polibio, Storie III (traduzione W. R. Paton, 1922; testo antico)',url='https://penelope.uchicago.edu/Thayer/E/Roman/Texts/Polybius/3*.html',use='Fonte antica consultata per cause della guerra, Iberia, Rodano, Alpi, forze superstiti, Ticino, Trebbia, Trasimeno e Canne. Traduzione storica in pubblico dominio. Le sue stime non sono conteggi moderni.'),
 dict(id='POL9',title='Polibio, Storie IX, 3–9: la marcia su Roma',url='https://penelope.uchicago.edu/Thayer/E/Roman/Texts/Polybius/9*.html',use='Fonte antica primaria: obiettivo di soccorrere Capua, avvicinamento all’Aniene, difesa di Roma, allontanamento. Consultato il testo della traduzione storica in pubblico dominio.'),
 dict(id='LIV26',title='Tito Livio, Storia di Roma XXVI, 7–12',url='https://www.perseus.tufts.edu/hopper/text?doc=26&fromdoc=Perseus%3Atext%3A1999.02.0158',use='Fonte antica primaria, consultata in traduzione: percorso del 211, Fulvio Flacco, Aniene, mancata conquista. Confrontata con Polibio; non fuse le divergenze in una cronaca fittiziamente precisa.'),
 dict(id='LIVIUS',title='Jona Lendering, Hannibal Barca, Livius.org',url='https://www.livius.org/articles/person/hannibal-3-barca/',use='Sintesi moderna di confronto per la cronologia di Amilcare, Asdrubale, Annibale e la permanenza italiana. Non adottata la tesi teleologica di una inevitabile unificazione mediterranea.'),
 dict(id='ALPS',title='Livius.org, Hannibal in the Alps',url='https://www.livius.org/articles/person/hannibal-3-barca/hannibal-in-the-alps/',use='Confronto fra descrizioni antiche e varie ipotesi di valico. Il suo giudizio sui valichi non è presentato come consenso. La carta evidenzia l’incertezza.'),
 dict(id='NE',title='Natural Earth II: physical raster and rivers, public domain',url='https://www.naturalearthdata.com/downloads/10m-raster-data/10m-natural-earth-2/',use='Base geografica ad alta risoluzione con rilievo e copertura ideale del suolo. Coordinate fisiche moderne, senza confini politici, strade moderne o pretesa di ricostruire esattamente coste e vegetazione antiche.'),
 dict(id='DEM',title='Mapzen Terrain Tiles — AWS Open Data',url='https://registry.opendata.aws/terrain-tiles/',use='Quote moderne per l’ombreggiatura di Alpi e Italia. Dati gratuiti elaborati localmente, non filmati o immagini satellitari della campagna antica.')]

def main():
    text=(ROOT/'battles/annibale/narration.md').read_text(encoding='utf-8')
    chunks=re.split(r'^## (\d\d) — (.+)$',text,flags=re.M);scenes=[]
    dates=['237–211 a.C.','Dopo il 241 a.C.','237–221 a.C.','221 a.C.','219–218 a.C.','Primavera–estate 218 a.C.','Estate 218 a.C.','218 a.C. · Rodano','218 a.C. · Gallia','Autunno 218 a.C.','Autunno 218 a.C.','Autunno 218 a.C.','218 a.C. · Italia','217 a.C.','217 a.C.','216 a.C.','216–212 a.C.','211 a.C.','211 a.C.','211 a.C.','237–211 a.C.']
    previous=[15,52,116]
    for i,cfg in enumerate(scenespec):
        sid,title,body=chunks[1+i*3:4+i*3];lines=[x.strip() for x in body.strip().split('\n') if x.strip()]
        sources=['POL3','LIVIUS'] if i<17 else ['POL9','LIV26']
        if i in (9,10):sources.append('ALPS')
        scenes.append(dict(id=sid,title=title,date=dates[i],lines=lines,map='atlas',camera_start=previous,camera_end=cfg['view'],
          camera_keys=[dict(at=0,view=previous),dict(at=.34,view=cfg['view']),dict(at=1,view=cfg['view'])],
          kicker=cfg['kicker'],facts=[cfg['fact']],note='Percorsi schematici; le fasi e le incertezze sono indicate.',
          caption_note='Passaggio alpino non accertato' if i in (9,10) else 'Fonte delle cifre: Polibio · consistenze indicative' if i==11 else 'Itinerario schematico · non una traccia di marcia esatta',
          visible_places=cfg['visible'],label_offsets=cfg.get('offsets',{}),region_labels=cfg['regions'],routes=cfg['routes'],
          uncertainty_areas=cfg.get('areas',[]),callouts=cfg.get('callouts',[]),mode=cfg.get('mode','map'),
          commanders=[dict(id='hannibal',cue=0)] if cfg.get('commander') else [],sources=sources,
          arrows=[],units=[],focus=[],sfx=[dict(type='march',cue=0)] if i in (5,6,11,18) else []))
        if cfg.get('diagram'):
            scenes[-1]['tactical_diagram']=dict(title='CANNE · IL DOPPIO ACCERCHIAMENTO',cue=1,
              units=[dict(side='rome',pos=[x,.17],end=[x,.46]) for x in [.35,.45,.55,.65]]+
                [dict(side='rome',pos=[x,.27],end=[x,.57]) for x in [.35,.45,.55,.65]]+
                [dict(side='carthage',pos=[x,.54],end=[x,.72]) for x in [.36,.46,.56,.66]]+
                [dict(side='carthage',pos=[.2,y],end=[.25,y-.08]) for y in [.46,.61,.76]]+
                [dict(side='carthage',pos=[.8,y],end=[.75,y-.08]) for y in [.46,.61,.76]],
              routes=[dict(side='carthage',points=[[.13,.57],[.10,.28],[.23,.12],[.45,.12],[.5,.30]]),dict(side='carthage',points=[[.87,.57],[.90,.28],[.77,.12],[.55,.12],[.5,.30]])])
        if i in (18,19):scenes[-1]['local_rivers']=[dict(name='Aniene',points=[[13.11,41.925],[13.075,41.951],[13.033,41.985],[12.985,42.012],[12.938,42.026],[12.896,42.017],[12.847,41.998],[12.802,41.959],[12.780,41.960],[12.746,41.955],[12.719,41.961],[12.682,41.958],[12.657,41.939],[12.620,41.934],[12.595,41.945],[12.56,41.950],[12.534,41.942],[12.510,41.940]])]
        previous=cfg['view']
    pack=dict(schema_version=1,slug='annibale',title='Annibale — Da Cartagine alle porte di Roma',short_title='ANNIBALE',subtitle='Da Cartagine alle porte di Roma',
      display_date='237–211 a.C.',language='it',date='-0211',description='Un viaggio sulle mappe del Mediterraneo: dalle origini cartaginesi di Annibale alla spedizione del 218 a.C., attraverso i Pirenei e le Alpi, e fino alla minaccia contro Roma nel 211 a.C. Roma non fu conquistata.',
      target_minutes=11,min_minutes=10.5,max_minutes=11.6,max_voice_tempo=1.24,width=1920,height=1080,fps=30,
      output='output/annibale_documentario_1080p.mp4',verification_dir='annibale_verification',visual_style='atlas',atlas='assets/geography/atlas-v2/atlas.json',
      voice_engine='kokoro',voice='assets/voice/kokoro/kokoro-v1.0.onnx',voice_styles='assets/voice/kokoro/voices-v1.0.bin',voice_speaker='if_sara',
      voice_credit='Kokoro 82M, voce italiana if_sara, sintesi locale gratuita. Pesi Apache-2.0; nessun audio inviato a servizi esterni.',
      voice_sentence_chunks=['13:1','17:0','21:0'],
      voice_clause_chunks=['21:0','21:1'],
      voice_phoneme_overrides={'21:0':{'restitʊˈiʃe':'restituˈiʃʃe'}},
      voice_chunk_assets={'21:0':{'2':{'path':'assets/voice/annibale/final-phrase.wav','text':"la carta restituisce l'ampiezza di un'impresa eccezionale."}}},
      voice_custom_chunks={
       '21:0':["Torniamo alla vista d'insieme.","Cartagine, l'Iberia, il Rodano, le Alpi e l'Italia:","la carta restituisce l'ampiezza di un'impresa eccezionale.","Il trasferimento giovanile in Spagna,","l'invasione del duecentodiciotto e la marcia su Roma del duecentoundici","sono però fasi diverse."],
       '21:1':["Annibale riuscì a portare la guerra","dove i Romani non volevano combatterla","e inflisse sconfitte memorabili.","Non riuscì a trasformarle nella resa di Roma.","Il suo percorso ci lascia questa distinzione:","superare montagne, fiumi ed eserciti","può aprire una strada.","Vincere una guerra richiede anche","spezzare la capacità del nemico di proseguirla."]},
      pronunciation={'a.C.':'avanti Cristo','Annibale':'Ànnibale','Amilcare':'Amìlcare','Iberia':'Ibèria','Barca':'Bàrca','Numidi':'Nùmidi'},
      factions=[dict(id='carthage',label='Annibale e Cartagine',color=list(GOLD),estimate='Consistenze variabili per fase',commander='Annibale'),dict(id='rome',label='Roma',color=[221,109,101],estimate='Consistenze variabili per fase',commander='Consoli e magistrati romani')],
      commanders={'hannibal':dict(name='Annibale',subtitle='Comandante cartaginese',side='carthage',portrait='assets/portraits/annibale/hannibal.jpg',wikipedia_page='Hannibal',portrait_note=['Attribuzione tradizionale','Busto di Capua · volto non certo'])},
      atlas_locator=[7,40,43],route_legend='Annibale',
      framing={},assets=[],places=places,maps={'atlas':dict(center=[7,41],scale=[60,60],seed=218,north_label='NORD',landmarks=[],rivers=[],roads=[],ridges=[],forests=[],zones=[])},
      scenes=scenes,sources=SOURCES,source_method='Confronto fra Polibio e Livio, con sintesi moderna Livius. Racconto originale, senza dialoghi inventati o testimonianze fittizie. La divergenza fra le fonti resta esplicita.',
      editorial_notes=[
       'La spedizione del 218 a.C. parte da Nuova Cartagine in Iberia, non direttamente da Cartagine in Africa. Il trasferimento giovanile del 237 è distinto in voce e grafica.',
       'Annibale raggiunge il territorio prossimo a Roma nel 211 a.C., non subito dopo le Alpi né immediatamente dopo Canne. Non conquista Roma.',
       'Il valico alpino e molti tratti dell’itinerario sono discussi. L’area alpina e i segmenti tratteggiati sono esplicitamente schematici. Il riepilogo non certifica una scelta di valico.',
       'Nella scena del Rodano, le frecce illustrano la manovra di aggiramento in un settore indicativo, senza identificare un guado preciso.',
       'Le cifre di 20.000 fanti, 6.000 cavalieri e 37 elefanti sono dati tramandati da Polibio per momenti diversi. I congedi e i distaccamenti non vanno conteggiati come morti.',
       'Il busto di Capua è tradizionalmente attribuito ad Annibale: il volto non è identificato con sicurezza. La didascalia non lo presenta come ritratto certo.',
       'Geografia fisica moderna usata come riferimento visivo, senza confini o strade moderni. Non si ricostruiscono precisamente coste, laghi e vegetazione del III secolo a.C.',
       'Il rilievo deriva da quote moderne Natural Earth e Mapzen, con ombreggiatura e colori rielaborati. Gli zoom non introducono geometrie casuali o etichette ricalcolate per collisione.'
      ],territorial_note='Nessun confine nazionale moderno. Le etichette Iberia, Gallia, Italia e Africa indicano regioni di orientamento, non territori politici con confini certi.',
      map_notice='Base fisica moderna senza confini politici; itinerari schematici, passaggio alpino incerto. Quote e colori rielaborati per la visualizzazione.',
      extra_credits='Cartografia: Natural Earth II e Natural Earth rivers, pubblico dominio, https://www.naturalearthdata.com/about/terms-of-use/. Rilievo: Mapzen Terrain Tiles, https://registry.opendata.aws/terrain-tiles/. Europe terrain data produced using Copernicus data and information funded by the European Union - EU-DEM layers. Global GMTED2010 and SRTM terrain data courtesy of the U.S. Geological Survey. Global ETOPO1 terrain data: DOC/NOAA/NESDIS/NCEI. Quote elaborate con ombreggiatura, ritaglio e ricampionamento. Licenze e manifest in assets/geography/terrain-attribution.md e assets/geography/manifest.json.')
    validate_pack(pack);write_json(ROOT/'battles/annibale/battle.json',pack)
    print('Authored',len(scenes),'scenes;',sum(len(x.split()) for s in scenes for x in s['lines']),'words')

GOLD=(239,185,93)
if __name__=='__main__':main()
