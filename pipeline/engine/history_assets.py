"""Reuse the existing Commons licence checker for arbitrary historical images."""
import copy
from .common import ROOT,read_json,write_json

def acquire_history(pack):
    from .acquire import acquire
    clone=copy.deepcopy(pack)
    for a in clone.get('visual_assets',[]):
        if (ROOT/a['path']).exists():continue
        if a.get('commons_file') or a.get('wikipedia_page'):
            clone['commanders']['asset_'+a['id']]={'name':a.get('title',a['id']),'portrait':a['path'],**{k:a[k] for k in ['commons_file','wikipedia_page'] if k in a}}
        elif a.get('url'):
            if not any(x in a.get('license','').lower() for x in ['public domain','cc0','cc by','cc-by']):raise ValueError('Licenza immagine da verificare')
            clone['assets'].append({'path':a['path'],'url':a['url'],'license':a['license'],'source':a['source']})
        else:raise ValueError('Asset mancante: '+a['path'])
    acquire(clone)
