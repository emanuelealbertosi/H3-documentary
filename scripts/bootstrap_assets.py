"""Install checksum-pinned shared voice files; safe to repeat after a failed download."""
import hashlib,json,time
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[1]

def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def install():
    records=json.loads((ROOT/'scripts/assets-lock.json').read_text(encoding='utf-8'))
    for item in records:
        target=(ROOT/'pipeline'/item['path']).resolve()
        if not target.is_relative_to(ROOT/'pipeline/assets'):raise ValueError('Percorso asset non valido')
        if target.exists() and digest(target)==item['sha256']:continue
        target.parent.mkdir(parents=True,exist_ok=True)
        partial=target.with_name(target.name+'.part')
        print('Scarico e verifico:',target.name,flush=True)
        for attempt in range(4):
            try:
                with requests.get(item['url'],stream=True,timeout=(30,120)) as response:
                    response.raise_for_status()
                    with partial.open('wb') as stream:
                        for chunk in response.iter_content(1024*1024):stream.write(chunk)
                if digest(partial)!=item['sha256']:raise ValueError('Checksum non valido: '+target.name)
                partial.replace(target);break
            except (requests.RequestException,ValueError):
                if attempt==3:raise
                time.sleep(attempt+1)
    (ROOT/'pipeline/assets/manifest.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Voce italiana e caratteri verificati.',flush=True)

if __name__=='__main__':install()
