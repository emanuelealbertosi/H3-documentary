"""Download public geographic sources into a reusable local cache."""
from pathlib import Path
import sys,re,zipfile,hashlib,requests,json,math,time,argparse
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine.common import ROOT,write_json
OUT=ROOT/'assets/geography';OUT.mkdir(parents=True,exist_ok=True)

def download(url,path):
    if path.exists():return path
    path.parent.mkdir(parents=True,exist_ok=True)
    for attempt in range(4):
        try:
            with requests.get(url,stream=True,timeout=(20,120),headers={'User-Agent':'DocumentariAI educational documentary'}) as r:
                r.raise_for_status()
                temp=path.with_suffix(path.suffix+'.part')
                with temp.open('wb') as f:
                    for chunk in r.iter_content(1024*1024):f.write(chunk)
                temp.replace(path)
            return path
        except requests.RequestException:
            if attempt==3:raise
            time.sleep(1+attempt)

def tilexy(lon,lat,z):
    n=2**z
    return int((lon+180)/360*n),int((1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*n)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--config',default='battles/annibale/geography.json');args=parser.parse_args()
    config=json.loads((ROOT/args.config).read_text(encoding='utf-8'))
    page='https://www.naturalearthdata.com/downloads/10m-raster-data/10m-natural-earth-2/'
    html=requests.get(page,timeout=45).text
    links=re.findall(r'href=[\"\x27]([^\"\x27]+\.zip)',html)
    url=next((u for u in links if 'NE2_HR_LC_SR_W.zip' in u),'https://naciscdn.org/naturalearth/10m/raster/NE2_HR_LC_SR_W.zip')
    archive=download(url,OUT/'NE2_HR_LC_SR_W.zip')
    print('Natural Earth downloaded',archive.stat().st_size,flush=True)
    folder=OUT/'naturalearth';folder.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        for member in z.infolist():
            target=(folder/member.filename).resolve()
            if not target.is_relative_to(folder.resolve()):raise ValueError('Unsafe archive path')
            if not target.exists():z.extract(member,folder)
    download('https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_rivers_lake_centerlines.geojson',OUT/'rivers.geojson')
    download('https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_land.geojson',OUT/'land.geojson')
    download('https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_lakes.geojson',OUT/'lakes.geojson')
    download('https://raw.githubusercontent.com/tilezen/joerd/master/docs/attribution.md',OUT/'terrain-attribution.md')
    # Detailed terrain only around the close-up theatre; Europe overview uses Natural Earth.
    patches=config['patches'];terrain_zoom=config.get('terrain_zoom',9)
    jobs=set()
    for name,(west,south,east,north) in patches.items():
        z=terrain_zoom;x0,y0=tilexy(west,north,z);x1,y1=tilexy(east,south,z)
        for x in range(x0,x1+1):
            for y in range(y0,y1+1):jobs.add((z,x,y))
    def tile(job):
        z,x,y=job;return download(f'https://elevation-tiles-prod.s3.amazonaws.com/terrarium/{z}/{x}/{y}.png',OUT/f'terrain/{z}/{x}/{y}.png')
    with ThreadPoolExecutor(max_workers=6) as pool:
        for i,p in enumerate(pool.map(tile,sorted(jobs))):
            if i%30==0:print('Terrain tiles',i+1,'/',len(jobs),flush=True)
    records=[]
    for p in [archive,OUT/'rivers.geojson',OUT/'land.geojson',OUT/'lakes.geojson',OUT/'terrain-attribution.md']:
        h=hashlib.sha256()
        with p.open('rb') as f:
            for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
        records.append({'path':str(p.relative_to(ROOT)),'sha256':h.hexdigest()})
    write_json(OUT/'manifest.json',{'naturalearth_url':url,'naturalearth_license':'Public domain','terrain_url':'https://registry.opendata.aws/terrain-tiles/','terrain_attribution':'terrain-attribution.md','patches':patches,'terrain_zoom':terrain_zoom,'tile_count':len(jobs),'files':records,'bounds':config['bounds'],'output':config['output']})
    print('Geography acquisition complete',flush=True)

if __name__=='__main__':main()
