"""Acquire editorial artwork through the same usage/licence gate as portraits."""
import copy
from .common import ROOT,read_json,write_json

def acquire_history(pack):
    from .acquire import acquire
    clone=copy.deepcopy(pack)
    for a in clone.get('visual_assets',[]):
        if a.get('commons_file') or a.get('wikipedia_page'):
            clone['commanders']['asset_'+a['id']]={'name':a.get('title',a['id']),'kind':'topic','portrait':a['path'],'portrait_optional':True,**{k:a[k] for k in ['commons_file','wikipedia_page'] if k in a}}
        elif a.get('url'):
            clone.setdefault('assets',[]).append({**a,'h3_image':True})
        elif (ROOT/a['path']).exists():
            # Legacy locally prepared images carry their rights in the pack.
            metadata=(ROOT/a['path']).with_suffix('.metadata.json')
            if not metadata.exists():
                write_json(metadata,{'descriptionurl':a.get('source',''),'h3_image_source':'editorial',
                  'extmetadata':{'LicenseShortName':{'value':a.get('license','')},'LicenseUrl':{'value':a.get('license_url','')},
                    'Artist':{'value':a.get('creator','')},'ObjectName':{'value':a.get('title',a['id'])}}})
            clone['commanders']['asset_'+a['id']]={'name':a.get('title',a['id']),'kind':'topic','portrait':a['path'],'portrait_optional':True}
        else:raise ValueError('Asset mancante: '+a['path'])
    for person in clone.get('commanders',{}).values():person['portrait_optional']=True
    acquire(clone)

def sync_image_metadata(raw,root=ROOT):
    """Actual downloaded licence wins over the model's proposed artwork credit."""
    from .image_rights import clean
    changed=False
    for asset in raw.get('visual_assets',[]):
        path=root/asset['path'];meta=path.with_suffix('.metadata.json')
        if not path.is_file() or not meta.is_file():continue
        info=read_json(meta);ex=info.get('extmetadata',{})
        updates={'license':clean(ex.get('LicenseShortName',{}).get('value','')),
                 'license_url':clean(ex.get('LicenseUrl',{}).get('value','')),
                 'source':info.get('descriptionurl',asset.get('source','')),
                 'creator':clean(ex.get('Artist',{}).get('value','')),
                 'credit':clean(ex.get('Attribution',{}).get('value','')),
                 'image_source':info.get('h3_image_source','cache'),
                 'placeholder':bool(info.get('h3_placeholder'))}
        if info.get('h3_placeholder') or asset.get('placeholder'):
            updates['title']=clean(ex.get('ObjectName',{}).get('value',asset.get('title','')))
        if any(asset.get(k)!=v for k,v in updates.items()):asset.update(updates);changed=True
    return changed
