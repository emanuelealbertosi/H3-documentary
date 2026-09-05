"""Shared image reuse rules. Educational use is a licence choice, not an exception."""
import html,json,re
from pathlib import Path
from urllib.parse import urlsplit

def clean(value):return html.unescape(re.sub(r'<[^>]+>','',str(value or ''))).strip()

def usage_for(pack):
    value=pack.get('asset_usage') or pack.get('metadata',{}).get('asset_usage') or pack.get('metadata',{}).get('boundary_usage') or 'commercial'
    return 'education_nc' if value=='education_nc' else 'commercial'

def _url_license(url):
    try:p=urlsplit(clean(url))
    except ValueError:return None
    if p.scheme not in {'http','https'} or p.hostname not in {'creativecommons.org','www.creativecommons.org'} or p.username or p.password:return None
    path=p.path.lower().strip('/')
    m=re.fullmatch(r'licenses/(by(?:-nc)?(?:-sa|-nd)?)/(1\.0|2\.0|2\.5|3\.0|4\.0)(?:/([a-z-]+))?(?:/legalcode)?',path)
    if m:return ('CC-'+m[1].upper()+'-'+m[2],f'https://creativecommons.org/licenses/{m[1]}/{m[2]}/'+(m[3]+'/' if m[3] and m[3]!='legalcode' else ''))
    pd=re.fullmatch(r'publicdomain/(zero|mark)/1\.0(?:/(?:legalcode|deed)(?:\.[a-z]{2,3}(?:[-_][a-z]{2,4})?)?)?',path)
    if pd:return ('CC0-1.0' if pd[1]=='zero' else 'Public-domain',f'https://creativecommons.org/publicdomain/{pd[1]}/1.0/')
    return None

def _license_text(label):
    value=clean(label).lower().replace('–','-').replace('—','-')
    for pattern,replacement in [(r'creative[\s_-]+commons','cc'),(r'attribution','by'),
            (r'non[\s_-]*commercial','nc'),(r'share[\s_-]*alike','sa'),
            (r'no[\s_-]*(?:derivatives|derivs)','nd')]:
        value=re.sub(pattern,replacement,value)
    return re.sub(r'[\s_-]+','-',value)

def _label_license(label):
    value=clean(label).lower().replace('–','-').replace('—','-')
    if re.search(r'\b(?:not|unknown|unverified|uncertain|fair use|nonfree|non-free)\b',value):return None
    if re.fullmatch(r'(?:public domain(?: mark)?|pdm)(?:[ -]1\.0)?',value):return ('Public-domain','https://creativecommons.org/publicdomain/mark/1.0/')
    if re.match(r'^cc0(?:[ -]1\.0)?(?:$|\s*[·;])',value):return ('CC0-1.0','https://creativecommons.org/publicdomain/zero/1.0/')
    value=_license_text(value)
    m=re.match(r'^(?:cc-)?by((?:-nc)?(?:-sa|-nd)?)-(1\.0|2\.0|2\.5|3\.0|4\.0)(?=$|[-,;/])',value)
    if not m:return None
    code='by'+m[1];return ('CC-'+code.upper()+'-'+m[2],f'https://creativecommons.org/licenses/{code}/{m[2]}/')

def license_policy(label,usage='commercial',license_url=''):
    by_label=_label_license(label);by_url=_url_license(license_url)
    chosen=by_label or by_url
    # Do not turn a restrictive label into a permissive licence through a bad URL.
    mismatch=bool(by_label and by_url and by_label[0]!=by_url[0])
    text=clean(label).lower()
    if by_url and not by_label and re.search(r'\bcopyright\b',text):mismatch=True
    normalized=_license_text(text)
    family=re.match(r'^(?:cc-)?(by(?:-nc)?(?:-sa|-nd)?)(?=-|$)',normalized)
    if (chosen or family) and re.search(r'\b(?:not|reserved|fair use|unknown|unverified|uncertain|nonfree|non-free)\b',text):mismatch=True
    if chosen and family and chosen[0].rsplit('-',1)[0]!='CC-'+family[1].upper():mismatch=True
    # Restrictions count even without a version or after a valid licence name.
    # A suffix cannot silently change CC BY into a different licence grant.
    obligations=set(re.findall(r'(?<![a-z0-9])(nc|nd|sa)(?![a-z0-9])',normalized))
    if chosen and any('-'+term.upper()+'-' not in chosen[0] for term in obligations):mismatch=True
    if by_url and by_label and by_url[0]==by_label[0]:chosen=by_url  # preserve ported licence URL
    ident,url=chosen or ('unknown','')
    nc='-NC-' in ident;nd='-ND-' in ident;sa='-SA-' in ident
    allowed=bool(chosen) and not mismatch and not nd and (not nc or usage=='education_nc')
    return {'allowed':allowed,'id':ident,'license_url':url,'noncommercial':nc,'sharealike':sa,'noderivatives':nd,'conflict':mismatch}

def manual_allowed(record,usage='commercial'):
    """User-owned uploads need no invented licence; explicit restrictions still apply."""
    label=record.get('rights') or record.get('license') or ''
    decision=license_policy(label,usage,record.get('license_url',''))
    if decision['id']!='unknown' or decision['conflict']:return decision['allowed']
    compact=re.sub(r'[\s_-]+','',clean(label).lower())
    if any(x in compact for x in ('noderivatives','ccbynd','ccbyncnd','senzamodifiche')):return False
    if any(x in compact for x in ('noncommercial','ccbync','solodidattic')):return usage=='education_nc'
    return True

def metadata_policy(info,usage='commercial'):
    unknown=lambda:license_policy('',usage)
    if not isinstance(info,dict):return unknown()
    fields=info.get('extmetadata',{})
    if not isinstance(fields,dict):return unknown()
    for key in ('LicenseShortName','LicenseUrl'):
        field=fields.get(key,{})
        if not isinstance(field,dict) or not isinstance(field.get('value',''),str):return unknown()
    def value(key):return fields.get(key,{}).get('value','')
    decision=license_policy(value('LicenseShortName'),usage,value('LicenseUrl'))
    if info.get('h3_user_replacement'):
        decision['allowed']=manual_allowed({'rights':value('LicenseShortName'),'license_url':value('LicenseUrl')},usage)
    return decision

def image_license_credits(timeline,root=None):
    """Collect used image obligations without overriding other media/map licences."""
    rows=[];seen=set()
    assets=timeline.get('user_media',[])+[a for a in timeline.get('visual_assets',[]) if a.get('id') not in timeline.get('disabled_visual_asset_ids',[])]
    if root is not None:
        root=Path(root).resolve()
        for person in timeline.get('commanders',{}).values():
            if not isinstance(person,dict) or not isinstance(person.get('portrait'),str) or not person['portrait']:continue
            path=(root/person['portrait']).resolve().with_suffix('.metadata.json')
            if not path.is_relative_to(root):continue
            try:info=json.loads(path.read_text(encoding='utf-8'))
            except (OSError,ValueError):continue
            if metadata_policy(info,usage_for(timeline))['id']=='unknown':continue
            if not isinstance(info.get('descriptionurl',''),str):continue
            fields=info['extmetadata']
            def value(key):
                field=fields.get(key,{})
                text=field.get('value','') if isinstance(field,dict) else ''
                return clean(text) if isinstance(text,str) else ''
            assets.append({'title':value('ObjectName') or person.get('name','Ritratto'),
                'source':info.get('descriptionurl',''),'credit':value('Attribution') or value('Artist'),
                'license':value('LicenseShortName'),'license_url':value('LicenseUrl')})
    for asset in assets:
        label=asset.get('rights') or asset.get('license','');policy=license_policy(label,usage_for(timeline),asset.get('license_url',''))
        if policy['id']=='unknown':continue
        source=asset.get('source','');key=(source,policy['id'])
        if key in seen:continue
        seen.add(key);rows.append({'title':asset.get('title',asset.get('id','Immagine')),'source':source,'credit':asset.get('credit') or asset.get('creator',''),**policy})
    return rows

def image_license_notice(timeline,root=None):
    rows=image_license_credits(timeline,root)
    if not rows:return []
    lines=['IMMAGINI: ATTRIBUZIONI E LICENZE']
    for row in rows:
        if row['id'] in ('Public-domain','CC0-1.0'):continue
        conditions=[]
        if row['noncommercial']:conditions.append('uso non commerciale')
        if row['sharealike']:conditions.append('adattamenti dell’immagine da condividere alle stesse condizioni')
        lines.append(f"{row['title']} — {row['credit']}. {row['source']} · {row['id']}: {row['license_url']}"+(' · '+', '.join(conditions) if conditions else '')+'. Ridimensionamento, eventuale ritaglio e composizione nel video.')
    return lines if len(lines)>1 else []
