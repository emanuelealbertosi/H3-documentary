"""Editorial battle pack. The renderer has no Waterloo-specific logic."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

SOURCES=[
 {'id':'NAM','title':'National Army Museum — Battle of Waterloo','url':'https://www.nam.ac.uk/explore/battle-waterloo','use':'Contesto, eserciti multinazionali, riserve, esito. Non ripresa la generalizzazione sulla pace europea fino al 1914.'},
 {'id':'RA','title':'Royal Armouries — Waterloo 1815','url':'https://royalarmouries.org/objects-and-stories/stories/waterloo-1815','use':'Campagna, armi, protagonisti; cifre confrontate con altre fonti.'},
 {'id':'CRW','title':'Comité Royal de Waterloo — Chronologie de la bataille','url':'https://www.waterloocommittee.be/battle.php?view=chronology','use':'Sequenza degli attacchi, circa 68.000 alleati, circa 80 cannoni nella grande batteria.'},
 {'id':'FNP','title':'Fondation Napoléon — Blücher and the Prussians at Waterloo','url':'https://www.napoleon.org/en/history-of-the-two-empires/timelines/blucher-and-the-prussians-at-waterloo/','use':'Ritirata a Wavre, marcia prussiana, Zieten, inseguimento, abdicazione del 22 giugno. A Wavre rimase Thielmann: la frase della pagina che vi colloca Blücher è un evidente refuso.'},
 {'id':'WA','title':'Waterloo Association — The Battle of Waterloo','url':'https://waterlooassociation.org.uk/The%20Battle%20of%20Waterloo.pdf','use':'Terreno, capisaldi, azioni della cavalleria e crisi finale.'},
 {'id':'LAR','title':'Larousse — Bataille de Waterloo','url':'https://www.larousse.fr/encyclopedie/divers/bataille_de_Waterloo/149568','use':'Confronto sulla sequenza tattica; la Guardia attaccante è descritta senza confonderla interamente con la Vecchia Guardia.'},
 {'id':'WAL','title':'Service public de Wallonie — La bataille de Waterloo, 18 juin 1815 (16 h.)','url':'https://connaitrelawallonie.wallonie.be/histoire-et-symboles/histoire/atlas-historique/la-bataille-de-waterloo-18-juin-1815-16-h','use':'Geografia e disposizione generale, strade e direttrici degli attacchi.'},
 {'id':'FNS','title':'Fondation Napoléon — Waterloo : les sites remarquables','url':'https://www.napoleon.org/magazine/lieux/waterloo/','use':'Località, fattorie, Rossomme e Plancenoit.'},
 {'id':'MCU','title':'Marine Corps University Press — Wargaming Waterloo','url':'https://www.usmcu.edu/Portals/218/Wargaming%20Waterloo_new%20web_1.pdf','use':'Controllo della geografia, del terreno e delle interpretazioni; non trattato come fonte di coordinate tattiche esatte.'},
 {'id':'TNA','title':'The National Archives — Report of Wellington, 19 June 1815, WO 1/179','url':'https://discovery.nationalarchives.gov.uk/details/r/C3159420','use':'Riferimento archivistico primario per ulteriori controlli; catalogo consultato, testo integrale non trascritto né citato.'}
]

P={
 'hougoumont':[4.3952,50.6706], 'haye':[4.4116,50.6783], 'belle':[4.4144,50.6694],
 'papelotte':[4.4339,50.6806], 'plancenoit':[4.4298,50.6606], 'mont':[4.4076,50.6860],
 'waterloo':[4.3977,50.7154], 'wavre':[4.6119,50.7166], 'ligny':[4.5747,50.5121],
 'quatrebras':[4.4521,50.5710], 'charleroi':[4.4446,50.4108], 'bruxelles':[4.3517,50.8466],
 'genappe':[4.4513,50.6107], 'namur':[4.8674,50.4669], 'nivelles':[4.3282,50.5984],
 'frischermont':[4.4500,50.6780], 'bois':[4.4660,50.6680], 'rossomme':[4.419,50.6545]
}

COMMANDERS={
 'napoleon':{'name':'Napoleone','subtitle':'Imperatore dei francesi','side':'fr','portrait':'assets/portraits/napoleon.jpg'},
 'wellington':{'name':'Wellington','subtitle':'Comandante anglo-alleato','side':'allied','portrait':'assets/portraits/wellington.jpg'},
 'blucher':{'name':'Blücher','subtitle':'Comandante prussiano','side':'pr','portrait':'assets/portraits/blucher.jpg'},
 'ney':{'name':'Michel Ney','subtitle':'Maresciallo di Francia','side':'fr','portrait':'assets/portraits/ney.jpg'},
 'grouchy':{'name':'Grouchy','subtitle':'All’inseguimento dei prussiani','side':'fr','portrait':'assets/portraits/grouchy.jpg'},
 'derlon':{'name':'D’Erlon','subtitle':'I corpo francese','side':'fr','portrait':'assets/portraits/derlon.jpg'},
 'bulow':{'name':'Bülow','subtitle':'IV corpo prussiano','side':'pr','portrait':'assets/portraits/bulow.jpg'},
 'picton':{'name':'Thomas Picton','subtitle':'5ª divisione anglo-alleata','side':'allied','portrait':'assets/portraits/picton.jpg'},
 'uxbridge':{'name':'Uxbridge','subtitle':'Cavalleria anglo-alleata','side':'allied','portrait':'assets/portraits/uxbridge.jpg'},
 'lobau':{'name':'Lobau','subtitle':'VI corpo francese','side':'fr','portrait':'assets/portraits/lobau.jpg'},
 'zieten':{'name':'Zieten','subtitle':'I corpo prussiano','side':'pr','portrait':'assets/portraits/zieten.jpg'}
}

MAPS={
 'battle':{'center':[4.420,50.6745],'scale':[19000,24200],'seed':1815,
   'landmarks':[{'id':k,'name':n,'pos':P[k],'kind':typ} for k,n,typ in [
    ('hougoumont','HOUGOUMONT','farm'),('haye','LA HAYE SAINTE','farm'),('belle','LA BELLE ALLIANCE','farm'),
    ('papelotte','PAPELOTTE','farm'),('plancenoit','PLANCENOIT','town'),('mont','MONT-SAINT-JEAN','ridge'),
    ('bois','BOIS DE PARIS','forest'),('rossomme','ROSSOMME','town')]],
   'roads':[
    {'name':'Bruxelles — Charleroi','points':[[4.408,50.704],P['mont'],P['haye'],P['belle'],P['rossomme'],[4.425,50.638]]},
    {'name':'Chemin d’Ohain','points':[[4.375,50.679],[4.398,50.6825],[4.412,50.6817],[4.435,50.6830],[4.465,50.691]]},
    {'name':'Nivelles','points':[[4.407,50.701],[4.402,50.687],[4.390,50.676],[4.373,50.661]]},
    {'name':'Plancenoit','points':[P['belle'],[4.423,50.664],P['plancenoit'],[4.444,50.658]]}],
   'rivers':[{'name':'Lasne','points':[[4.427,50.656],[4.444,50.650],[4.463,50.661],[4.475,50.677]]}],
   'ridges':[{'pos':[4.407,50.683],'amplitude':22,'width':[.045,.004]},
             {'pos':[4.417,50.668],'amplitude':18,'width':[.04,.005]}],
   'forests':[{'pos':[4.467,50.675],'radius':[.010,.012]},{'pos':[4.395,50.668],'radius':[.0025,.002]}]},
 'campaign':{'center':[4.48,50.64],'scale':[3200,4050],'seed':1816,
   'landmarks':[{'id':k,'name':n,'pos':P[k],'kind':'town'} for k,n in [
    ('waterloo','WATERLOO'),('wavre','WAVRE'),('ligny','LIGNY'),('quatrebras','QUATRE-BRAS'),('charleroi','CHARLEROI'),
    ('bruxelles','BRUXELLES'),('genappe','GENAPPE'),('nivelles','NIVELLES'),('namur','NAMUR')]],
   'roads':[{'name':'Bruxelles — Charleroi','points':[P[k] for k in ['bruxelles','waterloo','genappe','quatrebras','charleroi']]},
            {'name':'Nivelles — Namur','points':[P[k] for k in ['nivelles','quatrebras','ligny','namur']]},
            {'name':'Vers Wavre','points':[P['ligny'],[4.659,50.56],P['wavre']]}],
   'rivers':[{'name':'Sambre','points':[[4.2,50.33],[4.3,50.385],P['charleroi'],[4.53,50.425],[4.60,50.42],[4.70,50.455],P['namur']]},
             {'name':'Dyle','points':[[4.46,50.603],[4.52,50.625],[4.566,50.673],P['wavre'],[4.64,50.79],[4.71,50.86]]}],
   'ridges':[],'forests':[{'pos':[4.435,50.775],'radius':[.085,.029]}]}
}

def unit(id,label,side,pos,kind='infantry',count=3,path=None,cue=0,until=None):
    return dict(id=id,label=label,side=side,pos=pos,kind=kind,count=count,path=path or [],cue=cue,until=until)
def arrow(side,points,cue=0,end_cue=None,kind='attack'):
    return dict(side=side,points=points,cue=cue,end_cue=end_cue,kind=kind)

def battle_units():
    return [unit('reille','REILLE · II','fr',[4.394,50.667],count=3),
     unit('derlon','D’ERLON · I','fr',[4.426,50.6710],count=4),
     unit('guard','GUARDIA','fr',[4.413,50.6577],count=2),
     unit('allied_w','ANGLO-ALLEATI','allied',[4.398,50.6846],count=4),
     unit('allied_e','ALA SINISTRA','allied',[4.427,50.6850],count=3),
     unit('hou','GUARNIGIONE','allied',[4.3947,50.6723],count=1),
     unit('lhs','LEGIONE TEDESCA','allied',[4.4102,50.6790],count=1)]

SCENES=[]
def scene(id,title,kicker,date,lines,**kwargs):
    s=dict(id=id,title=title,kicker=kicker,date=date,lines=lines,map='battle',camera_start=[4.420,50.675,1.0],camera_end=[4.418,50.675,1.05],
       units=battle_units(),arrows=[],commanders=[],facts=[],focus=[],sources=[],sfx=[],note='Posizioni, rilievi e movimenti schematici · Orari indicativi')
    s.update(kwargs); SCENES.append(s); return s

scene('01','WATERLOO','IL GIORNO CHE CHIUDE UN’EPOCA','18 GIUGNO 1815',[
 'Un terreno fradicio. Due creste basse. Una strada che conduce a Bruxelles.',
 'Il diciotto giugno milleottocentoquindici, a sud di Waterloo, Napoleone tenta di spezzare l’esercito di Wellington prima che arrivino i prussiani di Blücher.',
 'Per i francesi, ogni ora che passa rende più difficile la vittoria. Per gli alleati, resistere significa guadagnare tempo.',
 'Questa battaglia si decide anche lontano dai cannoni: sulle strade percorse da un esercito che molti francesi credono già sconfitto.'
],commanders=[{'id':'napoleon','cue':0},{'id':'wellington','cue':1},{'id':'blucher','cue':3}],facts=['18 GIUGNO 1815','Un fronte di pochi chilometri'],sources=['NAM','FNP'],mode='opening',sfx=[{'type':'cannon','cue':1}])

scene('02','DIVIDERE GLI ALLEATI','LA CAMPAGNA DEI CENTO GIORNI','MARZO — GIUGNO 1815',[
 'Tre mesi prima, Napoleone è tornato dall’Elba e ha ripreso il potere a Parigi. Le potenze europee si preparano a combatterlo di nuovo.',
 'Attendere significa affrontare forze sempre più numerose. L’imperatore sceglie quindi di colpire subito gli eserciti schierati nell’attuale Belgio, allora parte del Regno dei Paesi Bassi.',
 'A ovest si trova Wellington. A est, Blücher. Il piano francese è inserirsi fra loro, batterli separatamente e impedire che si sostengano.',
 'Il quindici giugno l’Armata del Nord attraversa la Sambre a Charleroi. La campagna entra nel vivo.'
],map='campaign',camera_start=[4.49,50.625,.86],camera_end=[4.49,50.625,.94],
 units=[unit('fr','NAPOLEONE','fr',P['charleroi'],path=[P['charleroi'],P['quatrebras']],cue=3),unit('al','WELLINGTON','allied',[4.30,50.69]),unit('pr','BLÜCHER','pr',[4.72,50.54])],
 arrows=[arrow('fr',[P['charleroi'],P['quatrebras']],3)],commanders=[{'id':'napoleon','cue':0}],facts=['15 GIUGNO','Attraversamento della Sambre'],sources=['RA','CRW'],sfx=[{'type':'march','cue':3}])

scene('03','DUE BATTAGLIE','UN SUCCESSO INCOMPLETO','16 GIUGNO 1815',[
 'Il sedici giugno si combatte su due campi distinti. A Ligny, Napoleone sconfigge i prussiani, ma non distrugge il loro esercito.',
 'A Quatre-Bras, il maresciallo Ney attacca le forze di Wellington. Il crocevia resta agli alleati, che ricevono rinforzi durante la giornata.',
 'Il progetto francese ottiene dunque soltanto una parte del risultato: i nemici sono separati, ma entrambi restano capaci di combattere.',
 'Soprattutto, i prussiani non si ritirano definitivamente verso est. Ripiegano verso Wavre, mantenendo aperta la possibilità di raggiungere Wellington.'
],map='campaign',camera_start=[4.50,50.615,.93],camera_end=[4.51,50.62,1.02],
 units=[unit('nap','NAPOLEONE','fr',[4.55,50.493],path=[[4.55,50.493],P['ligny']],cue=0),unit('ney','NEY','fr',[4.452,50.54],path=[[4.452,50.54],P['quatrebras']],cue=1),
 unit('wel','WELLINGTON','allied',[4.452,50.585]),unit('blu','BLÜCHER','pr',[4.587,50.529],path=[[4.587,50.529],[4.64,50.60],P['wavre']],cue=3)],
 arrows=[arrow('fr',[[4.55,50.493],P['ligny']],0),arrow('fr',[[4.452,50.54],P['quatrebras']],1),arrow('pr',[P['ligny'],[4.64,50.60],P['wavre']],3,kind='retreat')],
 commanders=[{'id':'ney','cue':1},{'id':'blucher','cue':3}],facts=['LIGNY + QUATRE-BRAS','Separati, ma ancora operativi'],sources=['RA','FNP'],sfx=[{'type':'cannon','cue':0}])

scene('04','LA PROMESSA','IL TEMPO DIVENTA UN’ARMA','17 GIUGNO 1815',[
 'Saputo della sconfitta prussiana, Wellington ripiega a nord, sulla posizione di Mont-Saint-Jean, a sud del villaggio di Waterloo.',
 'La notte porta pioggia intensa. Uomini, cavalli e cannoni affrontano strade sempre più difficili.',
 'Wellington accetta di combattere contando sull’aiuto di Blücher. È una scelta rischiosa: deve resistere fino all’arrivo dell’alleato.',
 'Napoleone, intanto, ha distaccato il maresciallo Grouchy all’inseguimento dei prussiani. Una parte importante dell’esercito francese è ormai lontana dal campo su cui si deciderà la campagna.'
],map='campaign',camera_start=[4.48,50.645,.96],camera_end=[4.50,50.674,1.08],
 units=[unit('wel','WELLINGTON','allied',P['quatrebras'],path=[P['quatrebras'],P['genappe'],P['waterloo']],cue=0),unit('blu','BLÜCHER','pr',P['wavre']),
 unit('nap','NAPOLEONE','fr',[4.455,50.54],path=[[4.455,50.54],P['quatrebras'],[4.424,50.651]],cue=1),unit('gro','GROUCHY','fr',[4.6,50.56],path=[[4.6,50.56],[4.67,50.62]],cue=3)],
 arrows=[arrow('allied',[P['quatrebras'],P['genappe'],P['waterloo']],0,kind='retreat'),arrow('pr',[P['wavre'],[4.53,50.69],P['waterloo']],2,kind='plan')],
 commanders=[{'id':'wellington','cue':0},{'id':'grouchy','cue':3}],facts=['OBIETTIVO ALLEATO','Resistere fino ai rinforzi'],sources=['NAM','FNP'],sfx=[{'type':'rain','cue':1}])

scene('05','LEGGERE IL TERRENO','IL CAMPO DI BATTAGLIA','18 GIUGNO · MATTINO',[
 'Guardiamo la mappa. Il nord è in alto: verso Bruxelles. Wellington occupa la cresta settentrionale, mentre i francesi si schierano a sud, oltre una valle poco profonda.',
 'Gran parte della fanteria alleata si ripara dietro il crinale. Il terreno riduce la visibilità e offre una protezione parziale dal fuoco francese.',
 'Davanti alla linea si trovano tre punti essenziali: Hougoumont a ovest, La Haye Sainte al centro e Papelotte a est.',
 'Fattorie, muri e siepi diventano ostacoli militari. Le loro guarnigioni obbligano gli attaccanti a deviare, fermarsi e spendere uomini.'
],focus=[{'place':'mont','cue':0},{'place':'hougoumont','cue':2},{'place':'haye','cue':2},{'place':'papelotte','cue':2}],facts=['NORD ↑ BRUXELLES','Una difesa in profondità'],sources=['WA','WAL','FNS'],mode='terrain')

scene('06','TRE ESERCITI','GLI UOMINI E I COMANDANTI','18 GIUGNO · MATTINO',[
 'Napoleone dispone sul campo di circa settantaduemila uomini. Di fronte, Wellington ne ha all’incirca sessantottomila.',
 'Il suo esercito è una coalizione: britannici, olandesi, belgi, hannoveriani, uomini di Brunswick e di Nassau, oltre alla Legione Tedesca del Re.',
 'I prussiani arriveranno progressivamente da est: circa cinquantamila parteciperanno alla battaglia, secondo le stime più comuni.',
 'Questi numeri sono indicativi. Il punto decisivo è quando le forze possono intervenire: al mattino Napoleone affronta Wellington; più tardi dovrà combattere su due fronti.'
],commanders=[{'id':'napoleon','cue':0},{'id':'wellington','cue':1},{'id':'blucher','cue':2}],facts=['FRANCESI ≈ 72.000','ANGLO-ALLEATI ≈ 68.000','PRUSSIANI ≈ 50.000, in arrivo'],sources=['NAM','CRW','WA'],mode='forces')

scene('07','HOUGOUMONT','IL PRIMO URTO','CIRCA 11:30',[
 'Verso le undici e trenta, l’attacco francese investe Hougoumont, davanti all’ala destra alleata.',
 'Gli uomini del secondo corpo avanzano fra il bosco e gli accessi della tenuta. Nei giardini e attorno agli edifici si combatte a distanza ravvicinata.',
 'I difensori mantengono il nucleo del complesso. Gli assalti francesi si rinnovano, ma la posizione non cede.',
 'L’azione, spesso interpretata come una diversione, assorbe uomini per tutta la giornata. Hougoumont diventa una battaglia dentro la battaglia: una minaccia che Wellington contiene senza abbandonare la cresta.'
],camera_start=[4.407,50.678,1.08],camera_end=[4.403,50.677,1.18],
 arrows=[arrow('fr',[[4.391,50.665],[4.392,50.668],P['hougoumont']],0),arrow('fr',[[4.398,50.666],[4.399,50.670],P['hougoumont']],1)],
 focus=[{'place':'hougoumont','cue':0}],facts=['ALA DESTRA ALLEATA','Hougoumont resiste'],sources=['CRW','WA'],sfx=[{'type':'musket','cue':1},{'type':'cannon','cue':2}])

scene('08','LA GRANDE BATTERIA','PREPARARE LO SFONDAMENTO','CIRCA 13:00',[
 'Mentre Hougoumont brucia, l’artiglieria francese prepara l’attacco principale. Decine di cannoni, tradizionalmente stimati attorno a ottanta nella grande batteria, concentrano il fuoco.',
 'I proiettili attraversano la valle. Il terreno bagnato limita i rimbalzi, ma il bombardamento resta micidiale.',
 'I fanti alleati cercano riparo dietro il crinale; i reparti più esposti subiscono le perdite maggiori.',
 'Napoleone vuole aprire la strada alla fanteria sul settore orientale del fronte. La potenza dei cannoni, però, non basta: qualcuno deve ancora salire la cresta e conquistarla.'
],arrows=[arrow('fr',[[4.420,50.672],[4.423,50.683]],0,kind='fire'),arrow('fr',[[4.430,50.672],[4.430,50.684]],1,kind='fire')],facts=['GRANDE BATTERIA','≈ 80 pezzi · stima tradizionale'],sources=['CRW','MCU','WA'],sfx=[{'type':'cannon','cue':0},{'type':'cannon','cue':1},{'type':'cannon','cue':3}])

s=scene('09','L’ATTACCO DI D’ERLON','LA FANTERIA ATTRAVERSA LA VALLE','CIRCA 13:30 — 14:00',[
 'Il primo corpo di d’Erlon avanza a est della strada principale, fra La Haye Sainte e Papelotte. Migliaia di fanti francesi risalgono il pendio.',
 'Sulla cresta incontrano la resistenza degli alleati. Le scariche di fucileria e i contrattacchi spezzano lo slancio in più punti.',
 'Il generale Picton viene ucciso mentre guida i suoi uomini. La linea, tuttavia, non si apre.',
 'È il momento della cavalleria pesante britannica. Le brigate di Uxbridge scendono contro le formazioni francesi già impegnate nello scontro. L’attacco di d’Erlon comincia a crollare.'
],commanders=[{'id':'derlon','cue':0},{'id':'picton','cue':2},{'id':'uxbridge','cue':3}],arrows=[arrow('fr',[[4.426,50.672],[4.426,50.681]],0,end_cue=2),arrow('allied',[[4.425,50.687],[4.425,50.680]],3)],facts=['I CORPO FRANCESE','L’assalto viene respinto'],sources=['RA','CRW','LAR'],sfx=[{'type':'march','cue':0},{'type':'musket','cue':1},{'type':'cavalry','cue':3}])
for u in s['units']:
 if u['id']=='derlon': u.update(path=[[4.426,50.671],[4.426,50.680],[4.426,50.673]],cue=0)

scene('10','OLTRE IL LIMITE','IL PREZZO DEL CONTRATTACCO','PRIMO POMERIGGIO',[
 'La carica alleata cattura uomini e insegne. Ma una parte dei cavalieri continua verso le batterie francesi, oltre il sostegno della propria fanteria.',
 'Cavalli stanchi e squadroni disordinati diventano vulnerabili. La cavalleria francese contrattacca e infligge gravi perdite.',
 'La vittoria locale ha un costo che peserà per il resto della giornata: Wellington conserva la posizione, ma consuma una risorsa preziosa.',
 'Sulla mappa, le frecce si invertono. Nella realtà, tornare indietro attraverso fumo, fango e reparti dispersi è molto più difficile che ordinare una carica.'
],arrows=[arrow('allied',[[4.426,50.683],[4.426,50.673],[4.429,50.670]],0,end_cue=1),arrow('fr',[[4.440,50.670],[4.432,50.674],[4.426,50.679]],1),arrow('allied',[[4.425,50.674],[4.418,50.686]],3,kind='retreat')],commanders=[{'id':'uxbridge','cue':0}],facts=['CAVALLERIA PESANTE','Successo tattico, perdite elevate'],sources=['CRW','WA'],sfx=[{'type':'cavalry','cue':0},{'type':'cavalry','cue':1}])

scene('11','VERSO WATERLOO','LA SECONDA BATTAGLIA SI AVVICINA','18 GIUGNO · POMERIGGIO',[
 'A est, i prussiani sono in marcia da Wavre. Il quarto corpo di Bülow apre la strada verso il fianco destro francese.',
 'Il fango e gli ingorghi rallentano le colonne. L’arrivo non è un singolo istante: i reparti entrano in azione progressivamente.',
 'Grouchy, intanto, si dirige su Wavre, dove incontra la retroguardia prussiana. Non riesce a impedire che il grosso delle forze di Blücher raggiunga Waterloo.',
 'Attribuire tutto a un solo ordine mancato sarebbe riduttivo. Contano le distanze, le informazioni incomplete e una decisione prussiana essenziale: continuare a sostenere Wellington.'
],map='campaign',camera_start=[4.51,50.687,1.02],camera_end=[4.505,50.684,1.08],units=[unit('wel','WELLINGTON','allied',P['waterloo']),unit('nap','NAPOLEONE','fr',[4.416,50.658]),
 unit('bul','BÜLOW · IV','pr',P['wavre'],path=[P['wavre'],[4.57,50.679],[4.51,50.674],[4.464,50.669]],cue=0),unit('gro','GROUCHY','fr',[4.66,50.615],path=[[4.66,50.615],[4.63,50.69]],cue=2)],
 arrows=[arrow('pr',[P['wavre'],[4.57,50.679],[4.51,50.674],[4.434,50.667]],0),arrow('fr',[[4.66,50.615],[4.63,50.69]],2)],commanders=[{'id':'bulow','cue':0},{'id':'grouchy','cue':2}],facts=['DA WAVRE A WATERLOO','La cooperazione alleata continua'],sources=['FNP','MCU'],sfx=[{'type':'march','cue':0}])

s=scene('12','LE CARICHE DI NEY','CAVALLERIA CONTRO FANTERIA','CIRCA 16:00 — 18:00',[
 'Sul fronte principale, Ney interpreta alcuni movimenti alleati come l’inizio di una ritirata. Lancia la cavalleria contro il centro destro di Wellington.',
 'I cavalieri attraversano lo spazio fra Hougoumont e La Haye Sainte e risalgono il pendio. Ma li attendono battaglioni schierati in quadrato.',
 'Le baionette proteggono ogni lato. Finché i fanti mantengono ordine e disciplina, la cavalleria fatica a trovare un’apertura.',
 'Le cariche si ripetono. Il sostegno coordinato di fanteria e artiglieria è insufficiente a trasformarle in uno sfondamento. Il campo si riempie di uomini e cavalli abbattuti, mentre le riserve francesi si consumano.'
],camera_start=[4.414,50.678,1.08],camera_end=[4.410,50.679,1.16],commanders=[{'id':'ney','cue':0}],arrows=[arrow('fr',[[4.403,50.669],[4.402,50.677],[4.400,50.683]],0),arrow('fr',[[4.408,50.670],[4.405,50.678],[4.407,50.684]],1)],facts=['QUADRATI DI FANTERIA','Disciplina contro impeto'],sources=['LAR','WA','CRW'],sfx=[{'type':'cavalry','cue':1},{'type':'musket','cue':2}],mode='squares')
for u in s['units']:
 if u['id']=='allied_w': u['kind']='square'
s['units'].append(unit('cav','CAVALLERIA · NEY','fr',[4.405,50.670],kind='cavalry',path=[[4.405,50.670],[4.404,50.680],[4.406,50.676]],cue=1))

s=scene('13','PLANCENOIT','NAPOLEONE COMBATTE SU DUE FRONTI','DALLE 16:30 CIRCA',[
 'Mentre le cariche continuano, i prussiani escono dai boschi a est. Bülow attacca in direzione di Plancenoit, sul fianco e alle spalle dei francesi.',
 'Napoleone invia il corpo di Lobau per contenerlo. La minaccia è concreta: se i prussiani avanzano ancora, possono raggiungere la strada della ritirata.',
 'La lotta entra nel villaggio. Le case e il cimitero diventano posizioni da conquistare una dopo l’altra.',
 'Per tenere Plancenoit, l’imperatore deve impiegare anche reparti della Guardia. Ogni battaglione mandato a est è un battaglione che non può usare contro Wellington.'
],camera_start=[4.429,50.671,1.02],camera_end=[4.435,50.668,1.12],commanders=[{'id':'bulow','cue':0},{'id':'lobau','cue':1}],arrows=[arrow('pr',[[4.464,50.669],[4.449,50.665],P['plancenoit']],0),arrow('fr',[[4.416,50.664],[4.436,50.667]],1)],focus=[{'place':'plancenoit','cue':2}],facts=['FIANCO DESTRO FRANCESE','La pressione delle riserve prussiane'],sources=['FNP','RA','FNS'],sfx=[{'type':'cannon','cue':0},{'type':'musket','cue':2}])
s['units'] += [unit('bul','BÜLOW · IV','pr',[4.459,50.669],count=4,path=[[4.459,50.669],[4.440,50.665]],cue=0),unit('lob','LOBAU · VI','fr',[4.419,50.665],path=[[4.419,50.665],[4.438,50.667]],cue=1)]

s=scene('14','CADE LA HAYE SAINTE','IL CENTRO ALLEATO IN CRISI','CIRCA 18:00 — 18:30',[
 'Nel tardo pomeriggio, i francesi conquistano La Haye Sainte. La guarnigione della Legione Tedesca del Re ha resistito per ore, ma le munizioni sono ormai insufficienti.',
 'La perdita della fattoria apre un varco pericoloso davanti al centro alleato. I francesi possono avvicinare i cannoni e colpire da distanza ridotta.',
 'È uno dei momenti più critici per Wellington. Deve rinforzare i punti minacciati con ciò che gli rimane.',
 'Anche Ney chiede altra fanteria per sfruttare il successo. Ma Napoleone è già impegnato contro i prussiani: ottenere una breccia e avere le forze per allargarla sono due problemi diversi.'
],camera_start=[4.415,50.677,1.09],camera_end=[4.413,50.679,1.19],focus=[{'place':'haye','cue':0,'side':'fr'}],arrows=[arrow('fr',[[4.419,50.674],P['haye']],0),arrow('fr',[P['haye'],[4.409,50.684]],1,kind='fire')],facts=['IL CAPOSALDO CADE','Il centro di Wellington vacilla'],sources=['WA','LAR','CRW'],sfx=[{'type':'musket','cue':0},{'type':'cannon','cue':1}])
for u in s['units']:
 if u['id']=='lhs': u.update(side='fr',label='FRANCESI',cue=1)

s=scene('15','IL TEMPO SI ESAURISCE','UNA VITTORIA ANCORA CONTESA','VERSO LE 19:00',[
 'Plancenoit viene contesa e riconquistata. I contrattacchi della Guardia danno ai francesi un sollievo temporaneo, senza eliminare la pressione prussiana.',
 'Più a nord, il corpo di Zieten raggiunge il settore di Papelotte e rafforza la sinistra alleata.',
 'Wellington può trasferire parte delle sue forze verso il centro. L’unione che Napoleone voleva impedire sta diventando realtà.',
 'La battaglia non è ancora finita. L’imperatore dispone di un’ultima possibilità: colpire la linea di Wellington con i battaglioni della Guardia ancora disponibili, prima che la situazione precipiti.'
],commanders=[{'id':'zieten','cue':1},{'id':'napoleon','cue':3}],arrows=[arrow('pr',[[4.457,50.687],[4.447,50.684],P['papelotte']],1),arrow('allied',[[4.429,50.686],[4.410,50.686]],2,kind='move')],facts=['LE FORZE ALLEATE SI UNISCONO','Zieten raggiunge Papelotte'],sources=['FNP','NAM'],sfx=[{'type':'march','cue':1}])
s['units'] += [unit('pr','PRUSSIANI','pr',[4.440,50.665],count=4),unit('zie','ZIETEN · I','pr',[4.454,50.685],path=[[4.454,50.685],[4.437,50.683]],cue=1)]

s=scene('16','L’ULTIMO ASSALTO','LA GUARDIA SALE LA CRESTA','CIRCA 19:30',[
 'Verso le diciannove e trenta, i battaglioni d’attacco della Guardia imperiale avanzano fra Hougoumont e La Haye Sainte.',
 'Il loro prestigio è enorme. Ma di fronte trovano reparti alleati ancora in grado di combattere e un fronte che Wellington ha rafforzato.',
 'Il fuoco colpisce le colonne. I contrattacchi alleati ne arrestano l’avanzata; alcuni reparti sono investiti anche sul fianco.',
 'La Guardia attaccante ripiega. Non tutta la Guardia è stata annientata, e altri battaglioni continueranno a coprire la ritirata. Ma vedere arretrare quelle uniformi distrugge la fiducia di molti soldati francesi.'
],camera_start=[4.412,50.676,1.06],camera_end=[4.409,50.680,1.17],arrows=[arrow('fr',[[4.414,50.669],[4.407,50.678],[4.404,50.683]],0,end_cue=2),arrow('allied',[[4.398,50.684],[4.406,50.681]],2),arrow('fr',[[4.405,50.681],[4.413,50.670]],3,kind='retreat')],facts=['LA GUARDIA RIPIEGA','La fiducia francese si spezza'],sources=['NAM','WA','MCU'],sfx=[{'type':'march','cue':0},{'type':'musket','cue':2}])
for u in s['units']:
 if u['id']=='guard': u.update(path=[[4.413,50.6577],[4.413,50.670],[4.405,50.681],[4.411,50.672]],cue=0)

s=scene('17','IL CROLLO','DALLA RITIRATA ALLA ROTTA','DALLE 20:00 CIRCA',[
 'Wellington ordina l’avanzata generale. A est, la pressione prussiana travolge infine la difesa di Plancenoit.',
 'Il fronte francese cede in più punti. I reparti si mescolano sulla strada verso Genappe, mentre alcune unità della Guardia cercano di proteggere il ripiegamento.',
 'L’inseguimento prussiano continua nella notte. Napoleone riesce a lasciare il campo, ma l’Armata del Nord ha perso la capacità di tenere insieme la battaglia.',
 'I due eserciti alleati hanno ottenuto ciò che il piano francese doveva evitare: combattere insieme, fino alla decisione.'
],arrows=[arrow('allied',[[4.401,50.685],[4.405,50.674]],0),arrow('allied',[[4.428,50.686],[4.425,50.674]],0),arrow('pr',[[4.447,50.666],P['plancenoit'],[4.419,50.660]],0),arrow('fr',[[4.415,50.673],[4.418,50.660],[4.425,50.649]],1,kind='retreat')],facts=['AVANZATA GENERALE','Ritirata francese verso Genappe'],sources=['FNP','CRW'],mode='rout',sfx=[{'type':'cannon','cue':0},{'type':'cavalry','cue':2}])
for u in s['units']:
 if u['side']=='fr': u.update(path=[u['pos'],[4.419,50.657],[4.425,50.646]],cue=1)

scene('18','DOPO I CANNONI','IL COSTO DELLA BATTAGLIA','NOTTE DEL 18 GIUGNO',[
 'Dopo il rumore resta un campo disseminato di feriti, morti e cavalli abbattuti. I soccorsi sono lenti, e la sofferenza continua ben oltre il tramonto.',
 'Le stime delle perdite variano: complessivamente si parla di decine di migliaia di uomini uccisi, feriti, catturati o dispersi.',
 'Sommare categorie diverse come se fossero tutte morti falserebbe il bilancio. Ma nessuna cautela sui numeri riduce la dimensione della catastrofe.',
 'Dietro i rettangoli della mappa ci sono vite individuali. La chiarezza di un’animazione non deve far dimenticare il disordine e il dolore di una battaglia reale.'
],units=[],arrows=[],facts=['DECINE DI MIGLIAIA DI PERDITE','Morti, feriti, prigionieri e dispersi'],sources=['NAM','CRW'],mode='aftermath')

scene('19','PERCHÉ WATERLOO','IL RISULTATO DI UNA COALIZIONE','22 GIUGNO 1815 E OLTRE',[
 'Il ventidue giugno Napoleone abdica. Il ritorno dei Cento Giorni è terminato. Seguiranno la resa agli inglesi e l’esilio a Sant’Elena.',
 'Waterloo non si spiega con una sola carica sbagliata o con l’assenza di un solo comandante. Il terreno, la resistenza dei capisaldi e il consumo delle riserve condizionano ogni scelta.',
 'Soprattutto, Wellington tiene abbastanza a lungo e Blücher mantiene l’impegno di raggiungerlo. Il piano di separarli è fallito.',
 'Su pochi chilometri di campagna si chiude il potere di Napoleone. A decidere non è soltanto la forza di un esercito, ma la capacità di due alleati di arrivare insieme al momento decisivo.'
],units=[unit('wel','WELLINGTON','allied',[4.410,50.682]),unit('blu','BLÜCHER','pr',[4.445,50.677])],commanders=[{'id':'wellington','cue':2},{'id':'blucher','cue':3}],arrows=[arrow('allied',[[4.410,50.682],[4.416,50.670]],2,kind='move'),arrow('pr',[[4.445,50.677],[4.416,50.670]],3,kind='move')],facts=['RESISTERE · COORDINARSI','Arrivare al momento decisivo'],sources=['FNP','NAM'],mode='ending')

PACK=dict(schema_version=1,slug='waterloo',title='Waterloo — Il tempo di una battaglia',language='it-IT',date='1815-06-18',target_minutes=9.5,
          short_title='WATERLOO',subtitle='Il tempo di una battaglia',display_date='18 GIUGNO 1815',min_minutes=8,max_minutes=10,
          output='output/waterloo_documentario_1080p.mp4',fps=24,width=1920,height=1080,voice='assets/voice/it_IT-paola-medium.onnx',
          pronunciation={'Waterloo':'Uaterlò','Wellington':'Uèllington','Blücher':'Blùcher','Hougoumont':'Ugomon','La Haye Sainte':'La È Sant','Papelotte':'Papelòt','Plancenoit':'Plansenuà',
           'Quatre-Bras':'Catr Brà','Ligny':'Lignì','Wavre':'Vavr','Charleroi':'Sciarleruà','Grouchy':'Gruscì','Bülow':'Bùlov','Ney':'Nè','d’Erlon':'d’Erlòn','Uxbridge':'Àcsbrig','Picton':'Pìcton','Lobau':'Lobò','Zieten':'Zìten','Genappe':'Genàp','Mont-Saint-Jean':'Mon San Giàn'},
          commanders=COMMANDERS,maps=MAPS,sources=SOURCES,scenes=SCENES,
          editorial_notes=['Orari arrotondati: divergenze fino a circa mezz’ora fra ricostruzioni.',
          'Le formazioni sono aggregati grafici: un simbolo non equivale a un battaglione né a un numero fisso di uomini.',
          'Coordinate geografiche approssimative dei luoghi, verificate rispetto alla cartografia delle fonti. Percorsi tattici interpretativi, non tracce GPS.',
          'Rilievi, campi, alberi ed edifici sono una ricostruzione illustrativa procedurale; non un modello altimetrico del 1815. Non è rappresentata la Butte du Lion, posteriore alla battaglia.',
          'Le scene tematiche del pomeriggio mostrano eventi in parte simultanei; le fasce orarie a schermo lo rendono esplicito.',
          'Nessuna citazione diretta o frase apocrifa; testo italiano originale basato sul confronto delle fonti.'])

if __name__=='__main__':
    PACK.update(voice='assets/voice/kokoro/kokoro-v1.0.onnx',voice_engine='kokoro',
       voice_styles='assets/voice/kokoro/voices-v1.0.bin',voice_speaker='if_sara',
       voice_credit='Kokoro 82M v1.0, voce italiana if_sara, eseguita localmente con kokoro-onnx 0.6.1 e Misaki/eSpeak NG. Pesi Apache-2.0; codice kokoro-onnx MIT. Nessun servizio vocale remoto.',
       description='La Battaglia di Waterloo, dalle manovre della campagna al crollo dell’esercito napoleonico: 19 scene narrate in italiano con mappe animate e ritratti storici.',
       source_method='Consultazione: 2 settembre 2026. Orari e cifre confrontati fra musei, associazioni storiche e opere di sintesi; nessuna citazione diretta. I diversi fronti del pomeriggio sono in parte simultanei.',
       territorial_note='Il campo si trovava nel Regno dei Paesi Bassi, oggi in Belgio. Nessun confine moderno è retrodatato al 1815. La frontiera francese è a sud dell’area inquadrata.',
       factions=[{'id':'fr','label':'FRANCESI','color':[102,164,227],'estimate':72000,'commander':'napoleon'},
                 {'id':'allied','label':'ANGLO-ALLEATI','color':[237,132,113],'estimate':68000,'commander':'wellington'},
                 {'id':'pr','label':'PRUSSIANI','color':[229,197,109],'estimate':50000,'commander':'blucher','note':'Intervento progressivo nel pomeriggio'}],
       assets=[{'path':'assets/voice/kokoro/kokoro-v1.0.onnx','url':'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx','license':'Apache-2.0'},
               {'path':'assets/voice/kokoro/voices-v1.0.bin','url':'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin','license':'Apache-2.0'},
               {'path':'assets/voice/kokoro/MODEL_CARD.md','url':'https://huggingface.co/hexgrad/Kokoro-82M/raw/main/README.md','license':'Model documentation'},
               {'path':'assets/voice/kokoro/LICENSE','url':'https://www.apache.org/licenses/LICENSE-2.0.txt','license':'Apache-2.0; model declaration in accompanying MODEL_CARD.md'}])
    wiki_pages={'napoleon':'Napoleon','wellington':'Arthur Wellesley, 1st Duke of Wellington','blucher':'Gebhard Leberecht von Blücher',
       'ney':'Michel Ney','grouchy':'Emmanuel de Grouchy, marquis de Grouchy','derlon':"Jean-Baptiste Drouet, comte d'Erlon",'bulow':'Friedrich Wilhelm Freiherr von Bülow',
       'picton':'Thomas Picton','uxbridge':'Henry Paget, 1st Marquess of Anglesey','lobau':'Georges Mouton','zieten':'Hans Ernst Karl, Graf von Zieten'}
    for cid,c in COMMANDERS.items():c['wikipedia_page']=wiki_pages[cid]
    MAPS['battle']['zones']=[{'side':'allied','points':[[4.386,50.682],[4.439,50.682],[4.442,50.689],[4.385,50.689]]},
                           {'side':'fr','points':[[4.387,50.667],[4.438,50.667],[4.438,50.671],[4.387,50.671]]}]
    MAPS['battle']['north_label']='↑ Bruxelles'
    MAPS['campaign'].update(north_label='1815',region_label='REGNO DEI PAESI BASSI · 1815')
    SCENES[1].update(camera_start=[4.50,50.621,.35],camera_end=[4.50,50.621,.36])
    SCENES[2].update(camera_start=[4.53,50.615,.58],camera_end=[4.52,50.620,.61])
    SCENES[3].update(camera_start=[4.51,50.653,.72],camera_end=[4.50,50.665,.75])
    SCENES[10].update(camera_start=[4.52,50.674,.90],camera_end=[4.51,50.678,.94])
    for u in SCENES[6]['units']:
        if u['id']=='reille':u.update(path=[[4.394,50.667],[4.393,50.670],[4.392,50.668]],cue=0)
    SCENES[7]['units'].append(unit('battery','GRANDE BATTERIA','fr',[4.430,50.674],kind='artillery',count=4))
    for u in SCENES[16]['units']:
        if u['id']=='allied_w':u.update(path=[u['pos'],[4.405,50.674]],cue=0)
        elif u['id']=='allied_e':u.update(path=[u['pos'],[4.425,50.674]],cue=0)
    # The captured farm must remain French in every later tactical scene.
    for s in SCENES[14:17]:
        for u in s['units']:
            if u['id']=='lhs':
                u.update(side='fr',label='FRANCESI · LA HAYE SAINTE')
                if s['id']=='17':u.update(path=[u['pos'],[4.419,50.657],[4.425,50.646]],cue=1)
    SCENES[15]['units'].append(unit('pr_east','PRUSSIANI','pr',[4.443,50.663],count=4))
    SCENES[16]['units'].append(unit('pr_east','PRUSSIANI','pr',[4.443,50.665],count=4,
        path=[[4.443,50.665],P['plancenoit'],[4.419,50.660]],cue=0))
    # Separate advance and retreat cues so a formation does not retreat during its introduction.
    for u in SCENES[8]['units']:
        if u['id']=='derlon':u.update(path=[[4.426,50.671],[4.426,50.680]],cue=0,end_cue=2,until=3)
    SCENES[8]['units'].append(unit('derlon_retreat','D’ERLON · I','fr',[4.426,50.680],count=4,
        path=[[4.426,50.680],[4.426,50.673]],cue=3))
    for u in SCENES[15]['units']:
        if u['id']=='guard':u.update(path=[[4.413,50.6577],[4.413,50.670],[4.405,50.681]],cue=0,end_cue=2,until=3)
    SCENES[15]['units'].append(unit('guard_retreat','GUARDIA','fr',[4.405,50.681],count=2,
        path=[[4.405,50.681],[4.411,50.672]],cue=3))
    PACK['framing']={'napoleon':[.20,.075,.79,.55],'derlon':[.21,.08,.77,.54],'grouchy':[.28,.07,.77,.50],
                     'lobau':[.22,.04,.73,.51],'uxbridge':[.30,.11,.72,.51],'zieten':[.08,.03,.93,.75]}
    out=ROOT/'battles/waterloo/battle.json'; out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(PACK,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Scenes:',len(SCENES),'Words:',sum(len(x.split()) for s in SCENES for x in s['lines']))
