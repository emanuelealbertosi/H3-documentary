"""Authored Stalingrad production data. The reusable renderer remains in engine/.
Narration and historical decisions are reviewed source material, not generated facts.
"""
import sys,re,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine.common import ROOT,write_json,validate_pack

def source(id,title,url,use):return dict(id=id,title=title,url=url,use=use)
SOURCES=[
 source('CMH1','Earl F. Ziemke, Stalingrad to Berlin, cap. I (U.S. Army, 1968)','https://www.ibiblio.org/hyperwar/USA/USA-EF-Defeat/USA-EF-Defeat-1.html','Testo della storia ufficiale federale statunitense, trascrizione HyperWar: contesto del 1942 e operazione Blau. Opera storica, non fonte neutrale rispetto alla storiografia del suo tempo.'),
 source('CMH3','Ziemke, Stalingrad to Berlin, cap. III: Stalingrad, the Encirclement','https://www.ibiblio.org/hyperwar/USA/USA-EF-Defeat/USA-EF-Defeat-3.html','Capitolo consultato: Don, città, ottobre-novembre, Urano e tentativo di soccorso. Carte 3 e 4 per orientamento dei settori e direttrici. Le generalizzazioni nazionali e alcune valutazioni sovietiche del 1968 non sono riprese.'),
 source('CMH4','Ziemke, Stalingrad to Berlin, cap. IV: Stalingrad, the Turning Point','https://www.ibiblio.org/hyperwar/USA/USA-EF-Defeat/USA-EF-Defeat-4.html','Testo consultato: Piccolo Saturno, logistica, fallimento del soccorso, Anello e resa. Carta 5 per il medio Don. Data di Pitomnik e cronologia di gennaio confrontate, non adottate senza riserve.'),
 source('WW2ADAPT','National WWII Museum — Stalingrad: Experimentation, Adaptation, Implementation','https://www.nationalww2museum.org/war/articles/stalingrad-experimentation-adaptation-implementation','Confronto storiografico: apprendimento sovietico, resistenza sugli accessi, errori logistici e miti di una trappola perfetta. Non si ricopiano i totali o le generalizzazioni delle memorie tedesche.'),
 source('WW2CIV','National WWII Museum — Unsung Witnesses of the Battle of Stalingrad','https://www.nationalww2museum.org/war/articles/unsung-witnesses-battle-stalingrad','Articolo consultato su evacuazione, civili fra le rovine, deportazioni e lavoro forzato. Parafrasi originale; nessuna testimonianza inventata o citazione diretta.'),
 source('DHM','Deutsches Historisches Museum — Die Schlacht um Stalingrad','https://www.dhm.de/lemo/kapitel/der-zweite-weltkrieg/kriegsverlauf/schlacht-um-stalingrad-194243','Confronto per stime della sacca, fallimento del ponte aereo e rese. La scheda sintetizza e comprime alcune date: il film distingue 19/20/23 novembre e 31 gennaio/2 febbraio. Non viene riprodotto il testo CC BY-NC-SA.'),
 source('BARCH','Bundesarchiv — Ende der Schlacht von Stalingrad','https://www.bundesarchiv.de/themen-entdecken/online-entdecken/dokumente-zur-zeitgeschichte/ende-der-schlacht-von-stalingrad/','Conferma delle rese del 31 gennaio e 2 febbraio 1943 e dei successivi 27 mesi di guerra in Europa.'),
 source('IWM','Imperial War Museums — Second World War Galleries, large print','https://www.iwm.org.uk/sites/default/files/files/2023-10/second_world_war_galleries_large_print.pdf','Testo indicizzato della sezione Stalingrad: circa 265.000 accerchiati, circa 91.000 prigionieri finali. Non è stato utilizzato materiale iconografico del PDF.'),
 source('USHMM','United States Holocaust Memorial Museum — The Soviet Union and the Eastern Front','https://encyclopedia.ushmm.org/content/en/article/the-soviet-union-and-the-eastern-front?series=7','Contesto della guerra di aggressione nazista, obiettivi economici del 1942 e significato della svolta.'),
 source('MUSEUM','Museo-riserva della battaglia di Stalingrado — Complesso di Mamayev Kurgan','https://stalingrad-battle.ru/about/about-museum-inner/2302/','Topografia commemorativa e ricostruzione della collina; confronto sulla congiunzione del 26 gennaio. Il linguaggio celebrativo non è assunto come giudizio critico.'),
 source('MAMAYEV','Mamayev Hill — Fights for Mamayev Kurgan','https://mamaev-hill.ru/en/battle','Sito non ufficiale (dichiarato nella pagina): consultato come confronto per la collina e i reparti, con conferma istituzionale del 26 gennaio. Non è il sito ufficiale del museo.'),
 source('AUP','Army University Press — Stalingrad: The Battle for the Martenovskii Shop','https://www.armyupress.army.mil/Journals/Military-Review/English-Edition-Archives/September-October-2018/Stalingrad-Martenovskii-Shop/','Contesto del combattimento industriale e della ricostruzione didattica per luoghi. Nessun filmato o immagine riprodotto.'),
]

def lm(id,name,pos,kind='town'):return dict(id=id,name=name,pos=pos,kind=kind)
P={'stalingrad':[44.52,48.71],'kalach':[43.526,48.691],'sovetskij':[43.76,48.64],
 'serafimovich':[42.735,49.584],'kletskaya':[43.061,49.314],'kotelnikovo':[43.133,47.632],
 'pitomnik':[44.241,48.740],'gumrak':[44.355,48.794],'tatsinskaya':[41.276,48.196],
 'morozovsk':[41.826,48.354],'rostov':[39.723,47.235],'voronezh':[39.20,51.67],
 'millerovo':[40.40,48.92],'novayakalitva':[39.96,50.02],
 'mamaev':[44.537,48.742],'station':[44.513,48.711],'center':[44.516,48.707],
 'landing':[44.536,48.716],'grain':[44.498,48.686],
 'october':[44.562,48.771],'barrikady':[44.584,48.786],'tractor':[44.604,48.805]}
don=[[39.2,51.7],[39.8,50.1],[41.0,49.8],[42.05,49.58],[42.735,49.58],[43.06,49.31],[43.5,49.25],[43.93,49.10],[43.90,48.98],[43.5,48.9],[43.53,48.69],[43.40,48.47],[43.09,48.24],[42.20,47.70],[41.2,47.55],[40.4,47.55],[39.72,47.24],[39.2,47.05]]
volga=[[45.1,51.0],[44.9,50.1],[44.73,49.4],[44.66,48.94],[44.64,48.82],[44.565,48.745],[44.54,48.70],[44.49,48.60],[44.60,48.45],[45.12,48.04],[45.6,47.8],[46.8,46.6],[48.04,46.35]]
def road(name,points):return dict(name=name,points=points)
def map_spec(center,scale,seed,landmarks,**kwargs):
 return dict(center=center,scale=scale,seed=seed,north_label='NORD',region_label='URSS · 1942–1943',
  landmarks=landmarks,roads=[],rivers=[],ridges=[],forests=[],zones=[],show_river_names=True,**kwargs)
regional=map_spec([43.45,48.75],[470,580],1942,[lm(k,n,P[k]) for k,n in [('stalingrad','Stalingrado'),('kalach','Kalach'),('sovetskij','Sovetskij'),('serafimovich','Serafimovič'),('kletskaya','Kletskaja'),('kotelnikovo','Kotelnikovo'),('pitomnik','Pitomnik'),('gumrak','Gumrak')]],scale_km=25,palette=[108,115,101])
for place in regional['landmarks']:
 if place['id']=='gumrak':place['label_offset']=[65,-24]
regional['rivers']=[road('Don',don),road('Volga',volga),road('Čir',[[41.4,49.1],[42.0,48.9],[42.6,48.6],[43.1,48.35],[43.4,48.47]])]
regional['rivers'] += [road('Myškova',[[43.29,48.382],[43.64,48.32],[43.94,48.29],[44.16,48.37],[44.38,48.44]]),road('Aksaj',[[42.78,48.052],[43.33,48.02],[43.7,48.0],[44.1,48.1],[44.4,48.14]])]
regional['rivers'][-2]['label_offset']=[80,-40]
regional['roads']=[road('Asse logistico',[[41.82,48.35],[43.09,48.24],P['kalach'],P['pitomnik'],P['stalingrad']]),road('Asse di Kotelnikovo',[P['kotelnikovo'],[43.60,48.10],[44.1,48.40],P['stalingrad']])]
regional['ridges']=[dict(pos=[44.15,48.72],amplitude=15,width=[.24,.70])]
campaign=map_spec([42.2,48.3],[95,115],19420,[lm(k,n,P[k]) for k,n in [('stalingrad','Stalingrado'),('rostov','Rostov'),('voronezh','Voronež')]]+[lm('maikop','Majkop',[40.10,44.61]),lm('grozny','Groznyj',[45.7,43.3])],scale_km=100)
campaign['rivers']=[road('Don',don),road('Volga',volga)]
campaign['ridges']=[dict(pos=[43.0,43.2],amplitude=32,width=[4,.48])]
wide=map_spec([42.25,49.0],[220,300],19421,[lm(k,n,P[k]) for k,n in [('stalingrad','Stalingrado'),('kalach','Kalach'),('tatsinskaya','Tatsinskaja'),('morozovsk','Morozovsk'),('millerovo','Millerovo'),('novayakalitva','Novaja Kalitva'),('rostov','Rostov')]],scale_km=50,palette=[118,124,116])
wide['rivers']=regional['rivers'];wide['roads']=[road('Collegamenti ferroviari',[P['rostov'],P['tatsinskaya'],P['morozovsk'],P['kalach'],P['stalingrad']])]
city=map_spec([44.56,48.75],[12000,11000],19422,[lm(k,n,P[k],'ridge' if k=='mamaev' else 'town') for k,n in [('mamaev','Mamayev Kurgan'),('station','Stazione'),('landing','Approdi'),('grain','Silos del grano'),('october','Ottobre Rosso'),('barrikady','Barrikady'),('tractor','Fabbrica di trattori')]],scale_km=1)
# Schematic riverbanks before postwar reservoirs. No current dams or canal.
west=[[44.655,48.85],[44.637,48.832],[44.617,48.810],[44.594,48.790],[44.574,48.773],[44.56,48.75],[44.549,48.737],[44.54,48.723],[44.535,48.710],[44.520,48.695],[44.499,48.665],[44.489,48.646]]
east=[[x+.021,y] for x,y in west]
city['water']=[dict(points=west+east[::-1])]
city['rivers']=[road('Volga',[[x+.0105,y] for x,y in west]),road('Carica',[[44.46,48.716],[44.485,48.703],[44.506,48.697],[44.523,48.699]])]
city['districts']=[dict(points=[[44.488,48.670],[44.499,48.716],[44.516,48.753],[44.545,48.779],[44.584,48.820],[44.613,48.823],[44.591,48.790],[44.562,48.766],[44.539,48.73],[44.517,48.690]])]
city['roads']=[road('Asse urbano',[[44.485,48.665],[44.502,48.710],[44.526,48.745],[44.554,48.775],[44.59,48.813]])]
city['ridges']=[dict(pos=P['mamaev'],amplitude=27,width=[.010,.010])]
wcity=copy.deepcopy(city);wcity['palette']=[115,122,116]
maps={'campaign':campaign,'front':regional,'don':wide,'battle':city,'winter_city':wcity}

commanders={}
for id,name,sub,side,page in [
 ('hitler','Adolf Hitler','Dittatore della Germania nazista','axis','Adolf Hitler'),
 ('stalin','Iosif Stalin','Capo dell’Unione Sovietica','soviet','Joseph Stalin'),
 ('paulus','Friedrich Paulus','Comandante della Sesta armata','axis','Friedrich Paulus'),
 ('hoth','Hermann Hoth','Quarta armata corazzata','axis','Hermann Hoth'),
 ('eremenko','Andrej Eremenko','Comandante del settore; poi fronte di Stalingrado','soviet','Andrey Yeryomenko'),
 ('chuikov','Vasilij Čujkov','Comandante della Sessantaduesima armata','soviet','Vasily Chuikov'),
 ('rodimtsev','Aleksandr Rodimcev','Tredicesima divisione della Guardia','soviet','Aleksandr Rodimtsev'),
 ('zhukov','Georgij Žukov','Comando supremo sovietico','soviet','Georgy Zhukov'),
 ('vasilevsky','Aleksandr Vasilevskij','Capo di stato maggiore generale','soviet','Aleksandr Vasilevsky'),
 ('vatutin','Nikolaj Vatutin','Fronte Sudoccidentale','soviet','Nikolai Vatutin'),
 ('rokossovsky','Konstantin Rokossovskij','Fronte del Don','soviet','Konstantin Rokossovsky'),
 ('manstein','Erich von Manstein','Gruppo d’armate Don','axis','Erich von Manstein')]:
 commanders[id]=dict(name=name,subtitle=sub,side=side,portrait=f'assets/portraits/stalingrado/{id}.jpg',wikipedia_page=page)

commanders['rodimtsev']['commons_file']='Photo of Aleksandr Rodimtsev from mil.ru.jpg'
commanders['rodimtsev']['portrait']='assets/portraits/stalingrado/rodimtsev-portrait.jpg'
for cid in ['chuikov','eremenko','rodimtsev','rokossovsky','vasilevsky','vatutin','zhukov']:
 commanders[cid]['image_credit']='Foto: Mil.ru · CC BY 4.0'
for cid in ['hitler','manstein']:
 commanders[cid]['image_credit']='Foto: Bundesarchiv · CC BY-SA 3.0 DE'

def unit(label,side,pos,kind='infantry',count=2,path=None,cue=0,end_cue=None,until=None):
 u=dict(id=re.sub(r'\W+','_',label),label=label,side=side,pos=pos,kind=kind,count=count,path=path or [],cue=cue)
 if end_cue is not None:u['end_cue']=end_cue
 if until is not None:u['until']=until
 return u
def arrow(side,points,cue=0,end_cue=None,kind='attack'):
 a=dict(side=side,points=points,cue=cue,kind=kind)
 if end_cue is not None:a['end_cue']=end_cue
 return a
def focus(place,cue=0,side='soviet'):return dict(place=place,cue=cue,side=side)
def cmd(id,cue=0):return dict(id=id,cue=cue)
def fx(type,cue=0):return dict(type=type,cue=cue)

scenes=[]
for part in (ROOT/'battles/stalingrado/narration.md').read_text(encoding='utf-8').split('## ')[1:]:
 header,body=part.strip().split('\n',1);paras=body.strip().split('\n\n');id,title,date,kicker=[x.strip() for x in header.split('|')]
 scenes.append(dict(id=id,title=title.upper(),date=date,kicker=kicker,lines=paras,map='front',
 camera_start=[43.5,48.90,.70],camera_end=[43.55,48.90,.72],units=[],arrows=[],commanders=[],facts=[],focus=[],sfx=[],sources=['CMH3'],
 note='Posizioni, rilievi e movimenti schematici · Date per fasi operative'))

def edit(n,**kwargs):scenes[n-1].update(kwargs)
def cityscene(n,cam=[44.56,48.75,.43],winter=False,visible=None,**kw):
 edit(n,map='winter_city' if winter else 'battle',camera_start=cam,camera_end=[cam[0]+.001,cam[1]+.001,cam[2]*1.06],**kw)
 if visible is not None:scenes[n-1]['visible_places']=visible
def frontline(points,side='soviet',**kw):return dict(points=points,side=side,**kw)
def cityunits(north=False):
 return [unit('Sesta armata','axis',[44.526,48.772 if north else 48.737],count=3),unit('62ª armata','soviet',[44.568 if north else 44.530,48.774 if north else 48.718],count=2)]
def pocket():return [unit('Sesta armata e aggregati','axis',[44.13,48.74],count=4),unit('Fronte del Don','soviet',[43.74,49.01],count=3),unit('Fronte di Stalingrado','soviet',[44.06,48.42],count=3)]
ring=[[43.75,48.87],[44.04,48.98],[44.42,48.96],[44.60,48.84],[44.54,48.69],[44.36,48.52],[43.98,48.51],[43.72,48.64],[43.75,48.87]]

edit(1,mode='opening',units=pocket(),arrows=[arrow('soviet',[[42.73,49.58],[43.0,49.12],[43.526,48.69]],1),arrow('soviet',[[44.30,48.22],[43.95,48.43],[43.76,48.64]],1)],facts=['La città e la steppa','Due scale della stessa battaglia'],sources=['CMH3','BARCH'])
edit(2,map='campaign',camera_start=[42.3,47.3,.83],camera_end=[42.7,47.2,.88],units=[unit('Asse','axis',[39.3,49.0],count=4)],arrows=[arrow('axis',[[39.3,49.0],[40.5,47.1],[43.0,44.3]],1,3)],focus=[focus('stalingrad',3,'axis')],facts=['Petrolio del Caucaso','Industrie e traffico sul Volga'],sources=['CMH1','USHMM'])
edit(3,map='campaign',camera_start=[42.1,47.2,.82],camera_end=[42.3,47.4,.85],units=[unit('Gruppo A','axis',[40.8,44.7],count=3),unit('Gruppo B','axis',[42.2,49.0],count=3)],arrows=[arrow('axis',[[39.72,47.23],[40.1,45.0],[44.7,43.6]],1),arrow('axis',[[40.0,49.0],[42.3,48.8],P['stalingrad']],1)],commanders=[cmd('hitler',0),cmd('stalin',3)],facts=['Due obiettivi simultanei','Comunicazioni sempre più lunghe'],sources=['CMH1','CMH3','WW2ADAPT'])
edit(4,camera_start=[43.5,48.95,.9],camera_end=[43.7,48.92,.95],units=[unit('Sesta armata','axis',[42.1,48.9],count=3,path=[[42.1,48.9],[43.3,48.83]],cue=1,end_cue=3),unit('62ª e 64ª armata','soviet',[43.65,48.70],count=3)],arrows=[arrow('axis',[[42.2,48.90],[43.3,48.8]],1)],focus=[focus('kalach',3)],facts=['Dal 17 luglio: gli accessi','Il Don prima della città'],sources=['CMH3','WW2ADAPT'],sfx=[fx('march',1)])
cityscene(5,[44.57,48.788,.48],units=[unit('16ª Panzer','axis',[44.52,48.83],kind='armor',count=2,path=[[44.52,48.83],[44.625,48.822]],cue=0,end_cue=1)],arrows=[arrow('axis',[[44.50,48.83],[44.625,48.822]],0),arrow('axis',[[44.46,48.76],[44.52,48.73]],1,kind='fire')],facts=['23 agosto: fiume e bombardamenti','La città resta contesa'],sfx=[fx('cannon',1)],sources=['CMH3','WW2ADAPT','WW2CIV'])
cityscene(6,focus=[focus('tractor',1),focus('mamaev',2)],facts=['Riva occidentale: la città','Riva orientale: retrovie e artiglieria'],sources=['CMH3','MUSEUM'])
edit(7,camera_start=[44.02,48.78,1.05],camera_end=[44.10,48.76,1.10],units=[unit('Paulus · Sesta armata','axis',[43.5,48.9],count=3,path=[[43.5,48.9],[44.18,48.80]],end_cue=2),unit('Hoth · Quarta corazzata','axis',[43.8,48.38],kind='armor',path=[[43.8,48.38],[44.20,48.63]],end_cue=2),unit('Difese sovietiche','soviet',[44.53,48.72],count=3)],commanders=[cmd('paulus',0),cmd('hoth',1),cmd('eremenko',2)],facts=['Convergenza da ovest e sud','Forze in continua trasformazione'])
cityscene(8,[44.544,48.744,.60],units=cityunits(),commanders=[cmd('chuikov')],focus=[focus('landing',1)],facts=['62ª armata','Conservare gli approdi'],sources=['CMH3','WW2ADAPT'])
cityscene(9,[44.528,48.728,.88],visible=['station','mamaev','landing'],units=[unit('Assalto tedesco','axis',[44.488,48.73],path=[[44.488,48.73],[44.515,48.719]],end_cue=1),unit('13ª Guardia','soviet',[44.578,48.713],path=[[44.578,48.713],[44.54,48.716],[44.526,48.733]],cue=1,end_cue=3)],arrows=[arrow('axis',[[44.486,48.731],[44.515,48.719]],0,1),arrow('soviet',[[44.58,48.713],[44.54,48.716],[44.526,48.733]],1)],commanders=[cmd('rodimtsev',2)],focus=[focus('mamaev',3)],facts=['Rinforzi attraverso il Volga','14–15 settembre'],sources=['CMH3','MAMAYEV'],sfx=[fx('musket',0)])
cityscene(10,[44.532,48.73,1.02],visible=['station','mamaev','landing'],units=[unit('Gruppi tedeschi','axis',[44.51,48.737],count=2),unit('Gruppi sovietici','soviet',[44.541,48.736],count=2)],arrows=[arrow('axis',[[44.511,48.736],[44.524,48.729]],2),arrow('soviet',[[44.542,48.731],[44.527,48.734]],1)],facts=['Obiettivi ravvicinati','Edifici, incroci e collegamenti'],sources=['CMH3','AUP'],sfx=[fx('musket',2)])
cityscene(11,[44.544,48.708,.66],mode='aftermath',visible=['station','landing','grain'],arrows=[arrow('soviet',[[44.522,48.712],[44.573,48.717]],1,kind='move')],facts=['Evacuazione e sopravvivenza','Civili fra i due fronti'],sources=['WW2CIV'])
cityscene(12,[44.578,48.79,.74],visible=['tractor','barrikady','october'],units=[unit('Assalto tedesco','axis',[44.555,48.810],kind='armor',count=3,path=[[44.555,48.81],[44.60,48.805]],end_cue=1),unit('Capisaldi sovietici','soviet',[44.582,48.784],count=2)],arrows=[arrow('axis',[[44.552,48.810],[44.614,48.808]],0),arrow('axis',[[44.54,48.78],[44.582,48.785]],2)],focus=[focus('tractor',1,'axis'),focus('barrikady',2)],facts=['Il settore industriale','Difese sovietiche frammentate'],sources=['CMH3','AUP'],sfx=[fx('cannon')])
cityscene(13,[44.56,48.75,.55],visible=['landing','mamaev','october'],units=[unit('Artiglieria sovietica','soviet',[44.613,48.733],kind='artillery',count=3)],arrows=[arrow('soviet',[[44.600,48.718],[44.542,48.719]],0,kind='move'),arrow('soviet',[[44.542,48.713],[44.600,48.711]],1,kind='move'),arrow('soviet',[[44.611,48.735],[44.522,48.75]],2,kind='fire')],facts=['Rinforzi e munizioni','Il ghiaccio mobile ostacola le barche'],sources=['CMH3','WW2CIV'],sfx=[fx('cannon',2)])
cityscene(14,[44.574,48.783,.76],winter=True,visible=['october','barrikady','tractor'],units=cityunits(True),arrows=[arrow('axis',[[44.549,48.786],[44.591,48.789]],1)],frontlines=[frontline([[44.565,48.758],[44.574,48.774],[44.59,48.789],[44.618,48.810]])],facts=['Ultimi assalti tedeschi','Contemporaneamente: prepara Urano'],sources=['CMH3'],sfx=[fx('musket',1)])
edit(15,map='don',camera_start=[42.55,49.1,.67],camera_end=[42.7,49.08,.69],units=[unit('8ª armata italiana','axis',[40.9,49.65],count=3),unit('3ª armata romena','axis',[42.70,49.34],count=3),unit('6ª armata tedesca','axis',[44.25,48.79],count=3),unit('Forze romene a sud','axis',[44.25,48.22],count=2)],facts=['Fianchi estesi','Riserve e difese anticarro insufficienti'],sources=['CMH3'])
edit(16,commanders=[cmd('zhukov'),cmd('vasilevsky',1)],arrows=[arrow('soviet',[[42.74,49.58],[42.95,49.16],[43.53,48.69]],2,kind='plan'),arrow('soviet',[[44.31,48.22],[43.99,48.40],[43.76,48.64]],2,kind='plan')],facts=['Urano: attaccare i fianchi','Tratteggio: piano di manovra'],sources=['CMH3','WW2ADAPT'])
edit(17,commanders=[cmd('vatutin',0)],units=[unit('Sudoccidentale · Vatutin','soviet',[42.48,49.56],count=3),unit('Don · Rokossovskij','soviet',[43.87,49.31],count=3),unit('Stalingrado · Eremenko','soviet',[44.31,48.23],count=3)],facts=['Oltre 1 milione di uomini','Nel complesso dell’area offensiva'],sources=['CMH3','WW2ADAPT'])
edit(18,units=[unit('5ª corazzata','soviet',[42.735,49.58],kind='armor',count=3,path=[[42.735,49.58],[42.99,49.16],[43.30,48.91]],cue=1,end_cue=3),unit('21ª armata','soviet',[43.06,49.31],count=2,path=[[43.06,49.31],[43.34,49.09]],cue=1,end_cue=3),unit('3ª armata romena','axis',[42.88,49.36],count=2,until=2)],arrows=[arrow('soviet',[[42.735,49.58],[42.99,49.16],[43.3,48.91]],1),arrow('soviet',[[43.06,49.31],[43.34,49.09]],1)],focus=[focus('serafimovich'),focus('kletskaya',1)],facts=['19 novembre: settore nord','Le formazioni mobili attraversano i varchi'],sfx=[fx('cannon')])
edit(19,camera_start=[43.9,48.58,.90],camera_end=[43.95,48.64,.94],units=[unit('51ª e 57ª armata','soviet',[44.34,48.19],count=3,path=[[44.34,48.19],[44.07,48.38],[43.90,48.54]],end_cue=3),unit('Forze romene','axis',[44.20,48.30],count=2,until=1),unit('Branca settentrionale','soviet',[43.44,48.91],kind='armor',path=[[43.44,48.91],[43.57,48.78]],cue=2,end_cue=3)],arrows=[arrow('soviet',[[44.34,48.19],[44.07,48.38],[43.90,48.54]],1),arrow('soviet',[[43.44,48.91],[43.57,48.78]],2)],facts=['20 novembre: settore sud','Entrambe le branche sono in movimento'],sfx=[fx('cannon')])
edit(20,camera_start=[44.0,48.78,.97],camera_end=[44.02,48.78,1.02],units=pocket(),arrows=[arrow('soviet',[[43.2,49.0],[43.526,48.69],[43.76,48.64]],0,1),arrow('soviet',[[44.3,48.22],[44.0,48.41],[43.76,48.64]],0,1)],frontlines=[frontline(ring,cue=1)],focus=[focus('sovetskij')],facts=['Circa 250.000–300.000 accerchiati','Stime dipendenti dalle categorie'],sources=['CMH3','DHM','IWM'])
edit(21,camera_start=[44.1,48.76,1.05],camera_end=[44.14,48.77,1.10],units=pocket(),frontlines=[frontline(ring)],commanders=[cmd('paulus'),cmd('manstein',2)],facts=['Resistere in attesa del soccorso','Le scorte si consumano'],sources=['CMH3'])
edit(22,camera_start=[43.98,48.76,1.0],camera_end=[44.05,48.77,1.04],units=[unit('Trasporti Luftwaffe','axis',[43.0,48.48],kind='air',count=2,path=[[43.0,48.48],[43.8,48.65],P['pitomnik']],end_cue=2),unit('Sacca','axis',[44.21,48.62],count=3)],frontlines=[frontline(ring)],focus=[focus('pitomnik',0,'axis'),focus('gumrak',0,'axis')],arrows=[arrow('axis',[[43.0,48.48],[43.8,48.65],P['pitomnik']],0,kind='move')],facts=['Servono centinaia di tonnellate al giorno','Consegne insufficienti e irregolari'],sources=['CMH3','CMH4','DHM'])
edit(23,camera_start=[43.9,48.24,.75],camera_end=[43.95,48.24,.78],units=[unit('Soccorso · Hoth','axis',P['kotelnikovo'],kind='armor',count=3,path=[P['kotelnikovo'],[43.59,48.07],[43.94,48.29]],end_cue=2),unit('Sesta armata','axis',[44.20,48.71],count=3),unit('Riserve sovietiche','soviet',[44.31,48.27],count=3,cue=3)],arrows=[arrow('axis',[P['kotelnikovo'],[43.59,48.07],[43.94,48.29]],0)],commanders=[cmd('hoth')],focus=[focus('kotelnikovo',0,'axis')],facts=['12 dicembre: inizia il soccorso','Circa 50 km dalla sacca'],sources=['CMH3','DHM'],sfx=[fx('cannon',1)])
edit(24,map='don',camera_start=[42.0,49.02,.71],camera_end=[42.05,48.91,.75],units=[unit('8ª armata italiana','axis',[40.3,49.68],count=3,until=2),unit('Avanzata sovietica','soviet',[40.4,50.05],kind='armor',count=3,path=[[40.4,50.05],[40.6,49.4],[41.276,48.196]],cue=1,end_cue=3)],arrows=[arrow('soviet',[[40.4,50.05],[40.6,49.4],[41.276,48.196]],1)],focus=[focus('tatsinskaya',2)],facts=['Piccolo Saturno: 16 dicembre','24 dicembre: incursione a Tatsinskaja'],sources=['CMH4'],sfx=[fx('cannon',1)])
edit(25,camera_start=[43.9,48.24,.75],camera_end=[44.0,48.25,.78],units=[unit('Hoth ripiega','axis',[43.94,48.29],kind='armor',count=2,path=[[43.94,48.29],[43.59,48.07],P['kotelnikovo']],cue=1,end_cue=3),unit('2ª armata Guardia','soviet',[44.12,48.36],count=3,path=[[44.12,48.36],[43.82,48.14]],cue=1,end_cue=3),unit('Sacca','axis',[44.20,48.71],count=3)],arrows=[arrow('axis',[[43.94,48.29],[43.59,48.07],P['kotelnikovo']],1,kind='retreat'),arrow('soviet',[[44.12,48.36],[43.82,48.14]],1)],facts=['Il soccorso viene respinto','Fame e isolamento precedono il collasso'],sources=['CMH4'],sfx=[fx('march',1)])
edit(26,camera_start=[44.16,48.77,1.17],camera_end=[44.21,48.78,1.24],units=[unit('Fronte del Don','soviet',[43.65,48.90],count=3,path=[[43.65,48.90],[44.13,48.79]],cue=1,end_cue=3),unit('Sesta armata','axis',[44.28,48.72],count=3)],frontlines=[frontline(ring)],arrows=[arrow('soviet',[[43.70,48.91],[44.14,48.80]],1),arrow('soviet',[[44.12,48.47],[44.29,48.66]],1)],commanders=[cmd('rokossovsky')],facts=['10 gennaio: operazione Anello','L’attacco restringe la sacca'],sources=['CMH4'],sfx=[fx('cannon',1)])
edit(27,camera_start=[44.28,48.77,1.55],camera_end=[44.39,48.76,1.7],units=[unit('Ripiegamento tedesco','axis',P['pitomnik'],count=2,path=[P['pitomnik'],[44.39,48.74],P['stalingrad']],cue=0,end_cue=2),unit('21ª armata','soviet',[44.27,48.83],count=2,path=[[44.27,48.83],P['mamaev']],cue=2,end_cue=3)],arrows=[arrow('axis',[P['pitomnik'],[44.39,48.74],P['stalingrad']],0,2,kind='retreat'),arrow('soviet',[[44.27,48.83],P['mamaev']],2)],focus=[focus('pitomnik',0),focus('gumrak',0)],facts=['Perduti gli aeroporti principali','26 gennaio: congiunzione sovietica'],sources=['CMH4','MUSEUM'])
cityscene(28,[44.559,48.754,.45],winter=True,visible=['station','mamaev','october','barrikady','tractor'],units=[unit('Settore sud · resa','axis',[44.516,48.711],count=1,cue=1,until=2),unit('Settore nord · resa','axis',[44.567,48.78],count=1,cue=2)],commanders=[cmd('paulus',0)],focus=[focus('station',1),focus('barrikady',2)],facts=['31 gennaio: settore meridionale','2 febbraio: settore settentrionale'],sources=['BARCH','DHM','IWM'])
cityscene(29,[44.548,48.745,.45],winter=True,mode='aftermath',units=[],facts=['Morti ≠ perdite complessive','Circa 91.000 prigionieri nella fase finale'],sources=['DHM','WW2CIV','IWM'])
edit(30,map='campaign',camera_start=[42.3,47.4,.88],camera_end=[42.2,47.6,.78],mode='ending',arrows=[arrow('axis',[[43.4,44.1],[41.2,45.5],P['rostov']],0,kind='retreat')],facts=['Una svolta strategica','La guerra continua fino al 1945'],sources=['CMH4','WW2ADAPT','BARCH'])

pack=dict(schema_version=1,slug='stalingrado',title='Stalingrado — La città e la trappola',short_title='STALINGRADO',subtitle='La città e la trappola',display_date='1942 — 1943',date='1942-07-17',language='it',target_minutes=15,max_voice_tempo=1.28,min_minutes=14.7,max_minutes=15.4,width=1920,height=1080,fps=24,output='output/stalingrado_documentario_1080p.mp4',verification_dir='stalingrado_verification',
 video_license='Video: Creative Commons BY-SA 4.0 — https://creativecommons.org/licenses/by-sa/4.0/ . Ritratti soggetti alle attribuzioni e licenze specificate.',
 description='Dall’avanzata verso il Volga alla resa: Stalingrado raccontata in italiano con mappe animate della città, del Don e del fronte meridionale. Urano, il ponte aereo, Tempesta invernale e operazione Anello.',
 voice_engine='kokoro',voice='assets/voice/kokoro/kokoro-v1.0.onnx',voice_styles='assets/voice/kokoro/voices-v1.0.bin',voice_speaker='if_sara',voice_credit='Kokoro 82M, voce italiana if_sara; pesi Apache-2.0, sintesi locale con Kokoro-ONNX (MIT) e fonemizzazione eSpeak tramite Misaki. Nessuna API vocale a pagamento.',
 pronunciation={'Čujkov':'Ciùikov','Žukov':'Giùkov','Vasilevskij':'Vassilièvski','Rokossovskij':'Rokossòvski','Serafimovič':'Serafimòvic','Kletskaja':'Clètscaia','Myškova':'Mìscova','Tatsinskaja':'Tatsìnskaia','Mamayev Kurgan':'Mamàiev Curgàn','Rodimcev':'Rodìmtsev','Hoth':'Hot','Kalach':'Calàc','Gumrak':'Gumràc','Pitomnik':'Pitòmnic','Eremenko':'Eriomènco','Manstein':'Mànstain','Paulus':'Pàulus'},
 factions=[dict(id='axis',label='Germania e alleati dell’Asse',color=[112,179,220],estimate='Variabile per fase',commander='Paulus / Hoth / Manstein'),dict(id='soviet',label='Armata Rossa',color=[235,128,110],estimate='Oltre un milione nell’area di Urano',commander='Čujkov / Eremenko / Vatutin / Rokossovskij')],
 commanders=commanders,framing={'hoth':[0,0,1,.80],'hitler':[.08,0,.96,.83]},maps=maps,sources=SOURCES,scenes=scenes,
 source_method='Ricerca e confronto effettuati il 2 settembre 2026. Base operativa: storia ufficiale U.S. Army di Earl F. Ziemke, opera federale in pubblico dominio, capitoli I, III e IV; confronto con musei e archivi tedeschi, britannici, statunitensi e il museo di Stalingrado. Testo originale italiano, senza citazioni dirette. Le fonti commemorative e la storiografia del 1968 sono valutate criticamente.',
 territorial_note='Geografia nel contesto 1942–1943. Non sono disegnati confini politici moderni, il canale Volga-Don o i bacini di Volgograd e Cimljansk creati nel dopoguerra. I corsi fluviali e gli assi stradali sono generalizzati dalle carte storiche; gli edifici e i rilievi sono illustrativi, non una planimetria edilizia o un DEM storico. Posizioni operative approssimate in longitudine/latitudine WGS84.',
 editorial_notes=[
 'Periodo: il 17 luglio è l’inizio convenzionale della campagna sugli accessi; il 23 agosto identifica l’arrivo tedesco al Volga e il grande bombardamento; non sono date intercambiabili.',
 'Urano: attacco settentrionale 19 novembre, meridionale 20 novembre, congiunzione 23 novembre presso Sovetskij/Kalach. Le sintesi DHM/IWM comprimono la sequenza: il film la distingue.',
 'Accerchiati: intervallo circa 250.000–300.000, con differenze fra effettivi alimentati, combattenti, feriti, romeni e ausiliari. Il valore IWM di circa 265.000 è compatibile con questo ordine di grandezza.',
 'Nessun totale esatto delle vittime del bombardamento del 23 agosto. Le perdite dell’intera campagna non vengono equiparate ai morti nella città.',
 'La storia CMH contiene una data di Pitomnik differente dalla cronologia comunemente accolta (16 gennaio); il testo usa prudentemente metà gennaio. Gumrak viene collocato poco dopo, senza precisione al giorno non necessaria.',
 'Le date sintetiche DHM relative al completo ripiegamento urbano e alla divisione della sacca non sono adottate: si usa il 26 gennaio per la congiunzione, confrontato con il museo di Mamayev Kurgan.',
 'La resa del settore sud il 31 gennaio non conclude immediatamente quella del settore nord, avvenuta il 2 febbraio. Circa 91.000 prigionieri si riferiscono alla fase finale, non al totale iniziale della sacca.',
 'Il fallimento del soccorso non è attribuito al solo inverno. Ordini di Hitler, responsabilità dei comandi, logistica e azione sovietica sono rappresentati insieme. Non si afferma che una fuga precoce avrebbe sicuramente avuto successo.',
 'Piccolo Saturno (dicembre) e ritirata del corpo alpino (gennaio) sono distinti; italiani e ungheresi non vengono falsamente collocati in massa nei combattimenti urbani.',
 'Linee e zone indicano settori schematizzati, non confini occupati con precisione in ogni ora. Simboli aggregati: il numero di icone non equivale al numero di soldati. Frecce tratteggiate distinguono piani, fuoco e ritirate.',
 'I ritratti possono essere di date diverse dal 1942; sono identificativi dei comandanti, non fotografie del giorno narrato. Nessun filmato d’archivio è simulato.',
 ])
for s in pack['scenes']:
 if s['map']=='front' and int(s['id']) not in [22,27]:
  s['visible_places']=[p['id'] for p in regional['landmarks'] if p['id'] not in ['pitomnik','gumrak']]
validate_pack(pack)
write_json(ROOT/'battles/stalingrado/battle.json',pack)
print('Scenes:',len(scenes),'Words:',sum(len(x.split()) for s in scenes for x in s['lines']))
