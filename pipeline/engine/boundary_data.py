"""Pinned geographic datasets, exact identity/date selection, no model-generated geometry."""
import calendar,datetime,hashlib,json,math,re,sqlite3,time,unicodedata,zipfile
from pathlib import Path
from contextlib import closing

SOURCES=json.loads(Path(__file__).with_name('boundary_sources.json').read_text(encoding='utf-8'))
MAX_DOWNLOAD=220_000_000
ALIASES={'impero romano':'roman empire','repubblica romana':'roman republic','regno romano':'roman kingdom',
         'francia':'france','germania':'germany','germany prussia':'germany','italia':'italy','spagna':'spain',
         'portogallo':'portugal','unione sovietica':'soviet union','urss':'soviet union','russia':'russia',
         'regno unito':'united kingdom','giappone':'japan','cina':'china','austria ungheria':'austria-hungary',
         'impero ottomano':'ottoman empire','ottoman empire turkey':'ottoman empire'}

def normalized(value):
    text=''.join(c for c in unicodedata.normalize('NFKD',str(value).casefold()) if not unicodedata.combining(c))
    text=re.sub(r'[^\w]+',' ',text).strip()
    return ALIASES.get(text,text).replace('-',' ')

def axis(year):return year+1 if year<0 else year
def unaxis(value):return math.floor(value)-1 if value<1 else math.floor(value)
def day_axis(y,m=1,d=1):
    date=datetime.date(y,m,d);return y+(date-datetime.date(y,1,1)).days/(366 if calendar.isleap(y) else 365)

def feature_record(provider,feature,index):
    p=feature['properties']
    if provider=='cliopatria':
        if p.get('Type')!='POLITY':return None
        start,end=int(p['FromYear']),int(p['ToYear'])
        if start==0 or end==0:return None
        return dict(key=str(index),name=p['Name'],wiki=p.get('Wikipedia') or '',qid=p.get('Wikidata') or '',
                    start=axis(start),end=axis(end)+1,period=f'{start} / {end} (anni inclusivi)')
    if provider=='cshapes':
        start=datetime.date(int(p['gwsyear']),int(p['gwsmonth']),int(p['gwsday']))
        end=datetime.date(int(p['gweyear']),int(p['gwemonth']),int(p['gweday']))+datetime.timedelta(days=1)
        return dict(key=str(index),name=p['cntry_name'],wiki='',qid='',start=day_axis(start.year,start.month,start.day),
                    end=day_axis(end.year,end.month,end.day),period=f'{start.isoformat()} / {end.isoformat()} (fine esclusa)')
    raise ValueError('Provider geografico sconosciuto')

def geometry_rings(geometry):
    kind=geometry.get('type');coordinates=geometry.get('coordinates',[])
    if kind=='Polygon':coordinates=[coordinates]
    elif kind!='MultiPolygon':raise ValueError('Geometria territoriale non poligonale')
    polygons=[];holes=[];count=0
    for rings in coordinates:
        if not rings:raise ValueError('Poligono vuoto')
        for ring in rings:
            count+=len(ring)
            if len(ring)<4 or ring[0]!=ring[-1]:raise ValueError('Anello non chiuso')
            for p in ring:
                if len(p)!=2 or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in p) or not(-180<=p[0]<=180 and -79<=p[1]<=79):
                    raise ValueError('Geometria fuori dalla proiezione supportata')
            if any(abs(a[0]-b[0])>180 for a,b in zip(ring,ring[1:])):raise ValueError('Geometria attraversa il meridiano di cambio data')
        polygons.append(rings[0]);holes.append(rings[1:])
    if not polygons or count>150_000:raise ValueError('Geometria assente o troppo complessa')
    return polygons,holes

class BoundaryStore:
    """One local archive/index per pinned provider, reused across all projects."""
    def __init__(self,root,log=print,cancel=lambda:None):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True);self.log=log;self.cancel=cancel;self.ready={}

    def archive(self,provider):
        spec=SOURCES[provider];suffix='.zip' if spec.get('member') else '.geojson'
        path=self.root/(provider+'-'+spec['sha256'][:12]+suffix)
        if path.is_file():
            with path.open('rb') as f:
                if hashlib.file_digest(f,'sha256').hexdigest()==spec['sha256']:return path
        import requests
        self.cancel();self.log('Confini: scarico '+spec['title']+' (una volta, poi riuso locale).')
        # URLs come exclusively from the packaged catalog, never from model data.
        with requests.Session() as session:
            session.trust_env=False
            with session.get(spec['url'],headers={'User-Agent':'H3-documentary/1.12 (https://github.com/emanuelealbertosi/H3-documentary)'},
                             timeout=(12,35),stream=True,allow_redirects=False) as response:
                response.raise_for_status()
                if response.status_code!=200:raise ValueError('Download geografico non diretto')
                part=path.with_suffix(path.suffix+'.part');size=0;digest=hashlib.sha256();started=time.monotonic()
                try:
                    with part.open('wb') as out:
                        for chunk in response.iter_content(131072):
                            self.cancel();size+=len(chunk)
                            if size>MAX_DOWNLOAD or time.monotonic()-started>180:raise ValueError('Download geografico oltre il limite')
                            out.write(chunk);digest.update(chunk)
                    if digest.hexdigest()!=spec['sha256']:raise ValueError('Il dataset è cambiato: impronta diversa dalla versione verificata')
                    part.replace(path)
                finally:part.unlink(missing_ok=True)
        return path

    def index(self,provider):
        spec=SOURCES[provider];path=self.root/(provider+'-'+spec['sha256'][:12]+'-v1.sqlite')
        if self.ready.get(provider)==path:return path
        if path.is_file():
            try:
                with closing(sqlite3.connect(path)) as c:
                    if c.execute('SELECT sha FROM metadata').fetchone()[0]==spec['sha256'] and c.execute('PRAGMA quick_check').fetchone()[0]=='ok':
                        self.ready[provider]=path;return path
            except (sqlite3.Error,TypeError):pass
        archive=self.archive(provider);self.log('Confini: indicizzo nomi, periodi e geometrie di '+spec['title']+'.')
        if spec.get('member'):
            with zipfile.ZipFile(archive) as z:
                info=z.getinfo(spec['member'])
                if info.file_size>MAX_DOWNLOAD:raise ValueError('Archivio geografico espanso troppo grande')
                with z.open(info) as f:data=json.load(f)
        else:
            with archive.open(encoding='utf-8-sig') as f:data=json.load(f)
        if data.get('type')!='FeatureCollection' or not isinstance(data.get('features'),list):raise ValueError('Dataset geografico non valido')
        part=path.with_suffix('.part');part.unlink(missing_ok=True)
        try:
            with closing(sqlite3.connect(part)) as c,c:
                c.executescript('CREATE TABLE metadata(sha TEXT); CREATE TABLE features(key TEXT,name TEXT,normalized TEXT,wiki TEXT,qid TEXT,start REAL,end REAL,period TEXT,feature TEXT); CREATE INDEX names ON features(normalized); CREATE INDEX identities ON features(qid);')
                c.execute('INSERT INTO metadata VALUES(?)',(spec['sha256'],))
                for i,f in enumerate(data['features']):
                    if i%100==0:self.cancel()
                    row=feature_record(provider,f,i)
                    if not row or row['start']>=row['end']:continue
                    c.execute('INSERT INTO features VALUES(?,?,?,?,?,?,?,?,?)',(row['key'],row['name'],normalized(row['name']),normalized(row['wiki']),row['qid'],row['start'],row['end'],row['period'],json.dumps(f,separators=(',',':'))))
            part.replace(path)
        finally:part.unlink(missing_ok=True)
        self.ready[provider]=path;return path

    def candidates(self,provider,query,start,end):
        path=self.index(provider);name=normalized(query['name']);qid=query.get('wikidata_id','')
        with closing(sqlite3.connect(path)) as c:
            c.row_factory=sqlite3.Row
            rows=c.execute('SELECT * FROM features WHERE (normalized=? OR wiki=?) AND start<=? AND end>?',(name,name,end,start)).fetchall()
        # A supplied identity must agree when this provider includes identity data.
        if qid and provider=='cliopatria':rows=[r for r in rows if r['qid']==qid]
        return [dict(r,feature=json.loads(r['feature']),provider=provider) for r in rows]
