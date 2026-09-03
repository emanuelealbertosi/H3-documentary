"""Export a committed source release. Never includes data, caches or untracked files."""
from pathlib import Path
import hashlib,json,subprocess,zipfile
ROOT=Path(__file__).resolve().parents[1]

def main():
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    version=subprocess.check_output(['git','show','HEAD:VERSION'],cwd=ROOT,text=True).strip()
    dest=ROOT/'dist';dest.mkdir(exist_ok=True)
    archive=dest/f'H3-documentary-{version}.zip'
    subprocess.run(['git','archive','--format=zip','--prefix=H3-documentary/','--output',str(archive),'HEAD'],cwd=ROOT,check=True)
    with zipfile.ZipFile(archive) as source:
        assert source.testzip() is None
        names=source.namelist()
        for forbidden in ['/data/','/.venv/','/.runtimes/','/.cache/','/tests/output/']:
            assert not any(forbidden in n for n in names),forbidden
    info={'version':version,'commit':commit,'archive':archive.name,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'bytes':archive.stat().st_size,'files':len(names)}
    archive.with_suffix('.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
    print(json.dumps(info,indent=2))

if __name__=='__main__':main()
