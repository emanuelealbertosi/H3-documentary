"""Resolve editorial territory identities against dated external geometry, then freeze it."""
import copy,hashlib,json,re,sqlite3
from pathlib import Path
from .store import read_json,write_json
from .paths import DATA

def signature(outline,usage):
    raw=json.dumps({'outline':outline,'usage':usage,'version':1},sort_keys=True,ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()

def resolve(outline,work,usage='commercial',log=print,cancel=lambda:None,provider=None):
    from engine.boundary_data import BoundaryStore,SOURCES,axis,unaxis,geometry_rings
    from engine.history_territories import area_view
    result=copy.deepcopy(outline);work=Path(work)
    report={'version':1,'usage':usage,'layers':[],'sources':[]}
    provider=provider or BoundaryStore(DATA/'cache/boundaries',log,cancel)
    added_sources={};used_features={};unavailable=set()
    for layer in result.get('visual_layers',[]):
        if layer.get('kind') not in {'territory','influence','alliance','contested','cultural','religious','linguistic'}:continue
        cancel();row={'id':layer['id'],'label':layer.get('label',layer['id']),'status':'schematic','datasets':[],'notes':[]}
        layer['schematic']=True;layer.pop('geometry_source',None)
        for editorial_state in layer.get('states',[]):
            for reserved in ('at','valid_until','geometry_source','geometry_status','schematic'):editorial_state.pop(reserved,None)
        report['layers'].append(row)
        # Sovereignty datasets cannot supply the extent of a belief, alliance or influence.
        if layer.get('kind')!='territory':
            row['notes'].append('Area tematica: non sostituita con confini di sovranità.');continue
        query=layer.get('boundary_query') or {'name':layer.get('label','')}
        if not isinstance(query,dict) or not isinstance(query.get('name'),str) or not 1<=len(query['name'].strip())<=140 or (query.get('wikidata_id') and not re.fullmatch(r'Q[1-9]\d{0,12}',str(query['wikidata_id']))):
            row['notes'].append('Identità geografica mancante o non valida.');continue
        scenes=[s for s in result.get('scenes',[]) if layer['id'] in s.get('territory_ids',[])]
        if not scenes:row['notes'].append('Area non selezionata nelle scene.');continue
        start=min(axis(y) for s in scenes for y in s['historical_range'])
        end=max(axis(y) for s in scenes for y in s['historical_range'])
        horizon=end+1  # Last displayed integer year, not an extrapolated dataset date.
        candidates=[]
        order=(['cshapes'] if usage=='education_nc' and end>=1886 and start<2020 else [])+['cliopatria']
        for name in order:
            if name in unavailable:continue
            try:
                matches=provider.candidates(name,query,start,end)
                for match in matches:
                    try:
                        match['polygons'],match['polygon_holes']=geometry_rings(match['feature']['geometry'])
                        area_view([p for poly in match['polygons'] for p in poly])
                    except (ValueError,KeyError,TypeError):
                        row['notes'].append(SOURCES[name]['title']+': geometria non utilizzabile in questa proiezione.');continue
                    candidates.append(match)
            except (OSError,ValueError,RuntimeError,sqlite3.Error) as error:
                # Cancellation is propagated, even when represented by a RuntimeError.
                cancel();unavailable.add(name);row['notes'].append(SOURCES[name]['title']+': archivio non disponibile. '+str(error)[:180])
            except __import__('requests').RequestException:
                unavailable.add(name);row['notes'].append(SOURCES[name]['title']+': servizio di download non disponibile.')
        original=copy.deepcopy(layer.get('states',[]))
        cuts=sorted({start,horizon,*[max(start,s['start']) for s in candidates],*[min(horizon,s['end']) for s in candidates],
                     *[axis(s['year']) for s in original if start<=axis(s['year'])<=horizon]})
        states=[];matched=False;fallback=False;seen=set()
        for left,right in zip(cuts,cuts[1:]):
            if left>=horizon or right<=start or left>=right:continue
            active=[s for s in candidates if s['start']<=left<s['end']]
            chosen=None
            for name in order:
                possible=[s for s in active if s['provider']==name]
                if len(possible)>1:
                    row['notes'].append(SOURCES[name]['title']+': più geometrie compatibili; nessuna scelta arbitraria.');break
                if len(possible)==1:chosen=possible[0];break
            if chosen:
                name=chosen['provider'];spec=SOURCES[name];sid='GEO_'+name
                if name not in row['datasets']:row['datasets'].append(name)
                key=(name,chosen['key']);used_features[key]=chosen['feature'];seen.add(key)
                added_sources[sid]={'id':sid,'title':spec['title'],'url':spec['page'],'origin':'boundary_dataset',
                    'citation':spec['credit'],'license':spec['license'],'license_url':spec['license_url'],'sha256':spec['sha256']}
                state={'year':unaxis(left),'at':left,'valid_until':min(right,chosen['end']),'polygons':chosen['polygons'],
                       'polygon_holes':chosen['polygon_holes'],'schematic':False,'geometry_status':spec['quality'],
                       'geometry_source':{'provider':name,'feature_id':chosen['key'],'name':chosen['name'],'period':chosen['period'],
                         'url':spec['page'],'sha256':spec['sha256'],'license':spec['license'],'source_id':sid}}
                matched=True
            else:
                earlier=[s for s in original if axis(s['year'])<=left]
                last=max(earlier,key=lambda s:axis(s['year'])) if earlier else {}
                state={'year':unaxis(left),'at':left,'valid_until':right,'polygons':copy.deepcopy(last.get('polygons',[])),
                       'schematic':True,'geometry_status':'schematic' if last.get('polygons') else 'unavailable'}
                if last.get('color'):state['color']=last['color']
                if left<=end:fallback=True
            states.append(state)
        row['notes']=list(dict.fromkeys(row['notes']))
        if not matched:
            row['notes'].append('Nessun confine utilizzabile per questa identità ed epoca; conservo solo le aree illustrative dichiarate.')
            log('Confini: '+row['label']+' — nessuna geometria documentata utilizzabile.');continue
        row['status']='partial' if fallback else 'sourced';row['features']=len(seen)
        row['notes'].extend(SOURCES[name]['note'] for name in row['datasets'])
        if fallback:row['notes'].append('Copertura temporale parziale: negli intervalli mancanti rimangono aree schematiche o nessuna area.')
        # Include all source changes, not only the years invented/proposed by the model.
        layer.update(states=states,schematic=fallback,geometry_source={'datasets':row['datasets']},transition_years=0)
        layer.pop('label_pos',None)
        layer['sources']=list(dict.fromkeys(layer.get('sources',[])+['GEO_'+n for n in row['datasets']]))
        log('Confini: '+row['label']+' — '+str(len(seen))+' geometrie da archivio, '+('copertura parziale.' if fallback else 'date compatibili.'))
    report['sources']=list(added_sources.values())
    report['sourced']=sum(r['status']=='sourced' for r in report['layers']);report['partial']=sum(r['status']=='partial' for r in report['layers'])
    report['schematic']=sum(r['status']=='schematic' for r in report['layers'])
    result['boundary_report']=report
    result.setdefault('uncertainties',[]).extend(r['label']+': '+n for r in report['layers'] for n in r['notes'])
    for name in {key[0] for key in used_features}:
        features=[f for (n,_),f in used_features.items() if n==name]
        write_json(work/'assets/boundaries'/(name+'.geojson'),{'type':'FeatureCollection','features':features})
    if report['layers']:write_json(work/'assets/boundaries/manifest.json',report)
    return result,report['sources'],report

def prepare(outline,sources,work,checkpoints,usage,log,cancel):
    """Frozen checkpoint before compilation; large geometry never goes back to the LLM."""
    if not outline.get('visual_layers'):return outline,sources
    path=Path(checkpoints)/'boundary-outline.json';fingerprint=signature(outline,usage)
    if path.is_file():
        saved=read_json(path)
        if saved.get('signature')==fingerprint:
            log('Confini: riuso la selezione geografica già salvata.');return saved['outline'],sources+saved['sources']
    result,added,report=resolve(outline,work,usage,log,cancel)
    write_json(Path(checkpoints)/'boundary-report.json',report)
    write_json(path,{'signature':fingerprint,'outline':result,'sources':added})
    return result,sources+added
