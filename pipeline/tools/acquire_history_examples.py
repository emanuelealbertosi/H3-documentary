"""Public-domain museum assets for the editorial acceptance examples."""
import sys,hashlib,requests
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine.common import ROOT,write_json,read_json

def main():
    out=ROOT/'assets/history';out.mkdir(parents=True,exist_ok=True);manifest=[]
    session=requests.Session();session.headers['User-Agent']='DocumentariAI educational history film'
    for ident,oid in [('goldsmith',459052),('adam-eve',336222),('erasmus',459080),('melencolia',336228)]:
        url=f'https://collectionapi.metmuseum.org/public/collection/v1/objects/{oid}'
        mdpath=out/(ident+'.met.json')
        if mdpath.exists():md=read_json(mdpath)
        else:
            response=session.get(url,timeout=90);response.raise_for_status();md=response.json();write_json(mdpath,md)
        if not md.get('isPublicDomain') or not md.get('primaryImage'):raise ValueError('Museum has not marked this image public domain')
        path=out/(ident+'.jpg')
        if not path.exists():
            response=session.get(md['primaryImage'],timeout=120);response.raise_for_status();path.write_bytes(response.content)
        record={'id':ident,'path':path.relative_to(ROOT).as_posix(),'title':md['title'],'creator':md['artistDisplayName'],'date':md['objectDate'],'license':'Public domain / CC0 (Met Open Access)','source':md['objectURL'],'url':md['primaryImage'],'credit':'The Metropolitan Museum of Art · '+md['creditLine'],'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        # A portrait can be consumed by the existing licensed-portrait exporter.
        write_json(path.with_suffix('.metadata.json'),{'descriptionurl':md['objectURL'],'url':md['primaryImage'],'extmetadata':{'Artist':{'value':md['artistDisplayName']},'LicenseShortName':{'value':'Public domain'},'LicenseUrl':{'value':'https://creativecommons.org/publicdomain/zero/1.0/'},'ObjectName':{'value':md['title']}}})
        manifest.append(record);print(ident,md['title'],flush=True)
    write_json(out/'manifest.json',manifest)

if __name__=='__main__':main()
