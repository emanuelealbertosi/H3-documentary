"""Download a pinned, public Chatterbox snapshot; never uploads audio."""
import hashlib,json,time,shutil,zipfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import requests

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'assets/tts/chatterbox-v3'
REPO='ResembleAI/chatterbox'
REV='5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18'
FILES=['ve.pt','s3gen.pt','t3_mtl23ls_v3.safetensors','conds.pt','grapheme_mtl_merged_expanded_v1.json','Cangjie5_TC.json','README.md']

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()

def fetch(item):
    name=item['path'];dest=OUT/name;temp=dest.with_suffix(dest.suffix+'.part')
    expected=item.get('lfs',{}).get('oid');size=item['size']
    url=f'https://huggingface.co/{REPO}/resolve/{REV}/{name}'
    if dest.exists() and dest.stat().st_size==size and (not expected or digest(dest)==expected):
        return dict(path=dest.relative_to(ROOT).as_posix(),source=url,bytes=size,sha256=digest(dest))
    for attempt in range(4):
        try:
            offset=temp.stat().st_size if temp.exists() else 0
            if offset!=size:
                with requests.get(url,headers={'Range':f'bytes={offset}-'} if offset else {},stream=True,timeout=(30,120)) as r:
                    r.raise_for_status()
                    if r.status_code!=206:offset=0
                    elif not r.headers.get('Content-Range','').startswith(f'bytes {offset}-'):raise ValueError('Unexpected partial response')
                    n=offset;last=int(n*10/max(size,1))
                    with temp.open('ab' if offset else 'wb') as f:
                        for data in r.iter_content(1024*1024):
                            f.write(data);n+=len(data);now=int(n*10/max(size,1))
                            if now>last:print(f'{name}: {min(100,now*10)}%',flush=True);last=now
            if temp.stat().st_size!=size:raise ValueError(f'Incomplete download: {name}')
            sha=digest(temp)
            if expected and sha!=expected:raise ValueError(f'Checksum mismatch: {name}')
            temp.replace(dest)
            return dict(path=dest.relative_to(ROOT).as_posix(),source=url,bytes=size,sha256=sha)
        except requests.RequestException:
            if attempt==3:raise
            time.sleep(2*(attempt+1))

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    r=requests.get(f'https://huggingface.co/api/models/{REPO}/tree/{REV}',timeout=30);r.raise_for_status()
    entries={x['path']:x for x in r.json()};assert all(x in entries for x in FILES)
    with ThreadPoolExecutor(2) as pool:records=list(pool.map(fetch,[entries[x] for x in FILES]))
    # The upstream tokenizer uses the checkpoint directory as its HF cache.
    cached=OUT/'models--ResembleAI--chatterbox'
    snapshot=cached/'snapshots'/REV;snapshot.mkdir(parents=True,exist_ok=True)
    shutil.copy2(OUT/'Cangjie5_TC.json',snapshot/'Cangjie5_TC.json')
    (cached/'refs').mkdir(exist_ok=True);(cached/'refs/main').write_text(REV,encoding='utf-8')
    # Upstream initializes the Chinese segmenter even for Italian; cache it once.
    pkuseg=OUT/'pkuseg';pkuseg.mkdir(exist_ok=True)
    archive=pkuseg/'spacy_ontonotes.zip'
    url='https://github.com/explosion/spacy-pkuseg/releases/download/v0.0.26/spacy_ontonotes.zip'
    expected='b216e7f92de7ae285aeab8feba2faa8ea8216e5995ff6fb3d391cc8356db1bfe'
    if not archive.exists():
        with requests.get(url,stream=True,timeout=(30,120)) as r:
            r.raise_for_status()
            temp=archive.with_suffix('.zip.part')
            with temp.open('wb') as f:
                for b in r.iter_content(1024*1024):f.write(b)
        if digest(temp)!=expected:raise ValueError('Segmenter checksum mismatch')
        temp.replace(archive)
    assert digest(archive)==expected
    target=(pkuseg/'spacy_ontonotes').resolve()
    if not target.is_dir():
        with zipfile.ZipFile(archive) as z:
            for entry in z.infolist():
                if not (target/entry.filename).resolve().is_relative_to(target):raise ValueError('Unsafe archive member')
            z.extractall(target)
    records.append(dict(path=archive.relative_to(ROOT).as_posix(),source=url,sha256=expected,bytes=archive.stat().st_size))
    (OUT/'manifest.json').write_text(json.dumps(dict(repository=REPO,revision=REV,files=records),indent=2),encoding='utf-8')
    print('Model ready:',OUT,flush=True)

if __name__=='__main__':main()
