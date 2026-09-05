import copy,json,hashlib,sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'pipeline'))
from engine.boundary_data import BoundaryStore,SOURCES,feature_record,geometry_rings,day_axis,axis
from engine.history_territories import state_blend,area_style
from app.boundaries import resolve,prepare

RING=[[1,40],[8,40],[8,48],[1,48],[1,40]]
HOLE=[[3,42],[4,42],[4,43],[3,43],[3,42]]
def feature(name='France',start=1800,end=1900):
    return {'type':'Feature','properties':{'Name':name,'FromYear':start,'ToYear':end,'Type':'POLITY','Wikipedia':name,'Wikidata':'Q142'},
            'geometry':{'type':'Polygon','coordinates':[RING,HOLE]}}
def candidate(provider='cliopatria',start=1800,end=1901,key='0'):
    return {'provider':provider,'start':start,'end':end,'key':key,'name':'France','period':'test period','feature':feature()}
def outline(start=1850,end=1860,kind='territory'):
    return {'visual_layers':[{'id':'fr','label':'Francia','kind':kind,'color':[200,120,70],'sources':[],
               'boundary_query':{'name':'France'},'states':[{'year':start,'polygons':[RING]}]}],
            'scenes':[{'title':'Francia','historical_range':[start,end],'territory_ids':['fr']}],'uncertainties':[]}
class Provider:
    def __init__(self,rows):self.rows=rows;self.calls=[]
    def candidates(self,name,*args):self.calls.append(name);return copy.deepcopy([r for r in self.rows if r['provider']==name])

def test_actual_index_exact_identity_period_cache_and_holes(tmp_path,monkeypatch):
    raw=json.dumps({'type':'FeatureCollection','features':[feature(),feature('France',1910,1920)]}).encode()
    sha=hashlib.sha256(raw).hexdigest();spec={**SOURCES['cliopatria'],'sha256':sha};spec.pop('member')
    monkeypatch.setitem(SOURCES,'cliopatria',spec)
    (tmp_path/('cliopatria-'+sha[:12]+'.geojson')).write_bytes(raw)
    store=BoundaryStore(tmp_path,log=lambda *_:None)
    rows=store.candidates('cliopatria',{'name':'Francia','wikidata_id':'Q142'},1850,1860)
    assert len(rows)==1 and geometry_rings(rows[0]['feature']['geometry'])==([RING],[[HOLE]])
    assert not store.candidates('cliopatria',{'name':'France','wikidata_id':'Q38'},1850,1860)
    assert not store.candidates('cliopatria',{'name':'France'},1905,1906)
    assert not store.candidates('cliopatria',{'name':'Fra'},1850,1860)
    monkeypatch.setattr(store,'archive',lambda *_:pytest.fail('Cache should avoid download and reindex'))
    assert len(store.candidates('cliopatria',{'name':'France'},1800,1800))==1

def test_education_uses_nc_but_commercial_does_not_even_fetch_it(tmp_path):
    for usage,want in [('education_nc','cshapes'),('commercial','cliopatria')]:
        provider=Provider([candidate('cshapes',1886,1920),candidate('cliopatria',1800,1920)])
        doc,sources,report=resolve(outline(1900,1910),tmp_path/usage,usage,lambda *_:None,provider=provider)
        assert doc['visual_layers'][0]['states'][0]['geometry_source']['provider']==want
        assert report['sourced']==1 and sources[0]['id']=='GEO_'+want
        if usage=='commercial':assert 'cshapes' not in provider.calls
        assert (tmp_path/usage/'assets/boundaries'/f'{want}.geojson').is_file()

def test_gaps_do_not_inherit_sourced_shape_and_no_future_geometry(tmp_path):
    provider=Provider([candidate(start=1800,end=1855)])
    doc,_,report=resolve(outline(1850,1860),tmp_path,log=lambda *_:None,provider=provider)
    layer=doc['visual_layers'][0]
    assert report['partial']==1
    assert not state_blend(layer,1854)[-1][0]['schematic']
    assert state_blend(layer,1855)[-1][0]['schematic']
    assert not state_blend(layer,1861)
    assert 'ricostruzione' in area_style(layer,state_blend(layer,1854)[-1][0])['boundary']

def test_same_year_changes_use_documented_calendar_days():
    f={'properties':{'cntry_name':'France','gwsyear':1919,'gwsmonth':1,'gwsday':1,'gweyear':1919,'gwemonth':6,'gweday':27}}
    row=feature_record('cshapes',f,1)
    assert row['end']==day_axis(1919,6,28)
    layer={'states':[{'year':1919,'at':1919.,'valid_until':row['end'],'polygons':[RING]},
                     {'year':1919,'at':row['end'],'valid_until':1920.,'polygons':[HOLE]}]}
    assert state_blend(layer,1919.2)[-1][0]['polygons']==[RING]
    assert state_blend(layer,1919.8)[-1][0]['polygons']==[HOLE]
    assert state_blend(layer,1920)==[]
    ancient=feature_record('cliopatria',feature('Roman Republic',-10,-1),0)
    assert ancient['start']==-9 and ancient['end']==1  # no historical year zero

def test_displayed_calendar_year_does_not_anticipate_a_sourced_boundary():
    from engine.history_schema import interpolate_year
    assert interpolate_year(1918,1920,.75,calendar=True)==1919
    assert interpolate_year(1918,1920,1,calendar=True)==1920
    assert interpolate_year(-1,1,.75,calendar=True)==-1
    assert interpolate_year(-1,1,1,calendar=True)==1
    assert interpolate_year(1918,1920,.75)==1920  # Existing editorial timelines unchanged.

def test_influence_and_ambiguous_matches_never_become_a_national_border(tmp_path):
    provider=Provider([candidate(),candidate(key='1')])
    doc,sources,report=resolve(outline(),tmp_path,log=lambda *_:None,provider=provider)
    assert not sources and report['schematic']==1 and doc['visual_layers'][0]['schematic']
    provider.calls.clear()
    _,sources,_=resolve(outline(kind='influence'),tmp_path,log=lambda *_:None,provider=provider)
    assert not sources and not provider.calls

def test_model_cannot_certify_its_own_geometry(tmp_path):
    obj=outline();layer=obj['visual_layers'][0]
    layer.update(schematic=False,geometry_source={'url':'https://example.org/lie'})
    layer['states'][0].update(schematic=False,geometry_status='dataset',geometry_source={'fake':True})
    doc,_,_=resolve(obj,tmp_path,log=lambda *_:None,provider=Provider([]))
    assert doc['visual_layers'][0]['schematic']
    assert 'geometry_source' not in doc['visual_layers'][0]['states'][0]

def test_checkpoint_resume_does_not_query_provider_again(tmp_path,monkeypatch):
    import app.boundaries as module
    original=module.resolve;calls=[]
    def resolver(*args,**kwargs):calls.append(1);return original(*args,**kwargs,provider=Provider([candidate()]))
    monkeypatch.setattr(module,'resolve',resolver)
    first=prepare(outline(),[],tmp_path/'work',tmp_path/'cp','commercial',lambda *_:None,lambda:None)
    assert prepare(outline(),[],tmp_path/'work',tmp_path/'cp','commercial',lambda *_:None,lambda:None)==first
    assert len(calls)==1

def test_invalid_geometry_is_not_repaired_with_invented_points():
    with pytest.raises(ValueError):geometry_rings({'type':'Polygon','coordinates':[RING[:-1]]})
    with pytest.raises(ValueError):geometry_rings({'type':'Polygon','coordinates':[[[179,1],[-179,1],[-179,3],[179,1]]]})

def test_credits_and_settings_preserve_educational_conditions():
    from app.models import Settings
    from engine.boundary_credits import attach_credits
    assert Settings(boundary_usage='education_nc').boundary_usage=='education_nc'
    with pytest.raises(ValueError):Settings(boundary_usage='anything')
    s=SOURCES['cshapes'];doc={};report={'usage':'education_nc','layers':[],
        'sources':[{'citation':s['credit'],'url':s['page'],'license':s['license'],'license_url':s['license_url'],'sha256':s['sha256']}]}
    attach_credits(doc,report)
    assert 'CC BY-NC-SA' in doc['video_license'] and 'Natural Earth' in doc['extra_credits']

def test_compilation_preserves_dated_geometry_and_adapts_period_for_renderer(tmp_path):
    from engine.history_authoring import compile_outline
    from engine.history_schema import estimate_timeline
    original=outline(1900,1910)
    original.update(documentary_type='territorial_expansion',title='Confini di prova',short_title='Confini',historical_period=[1900,1910],places=[])
    original['scenes'][0].update(scene_type='territorial_change',focus=[],event='Prova',source_ids=['GEO_cshapes'])
    resolved,sources,report=resolve(original,tmp_path,'education_nc',lambda *_:None,provider=Provider([candidate('cshapes',1886,1920)]))
    narration=[dict(index=0,lines=['parola '*170],fact='Prova',kicker='Prova')]
    doc,geo=compile_outline(resolved,narration,sources,dict(id='fixture',topic='Confini territoriali',minutes=1),{})
    timeline=estimate_timeline(doc)
    assert timeline['historical_period']=={'start':1900,'end':1910}
    assert timeline['visual_layers'][0]['states'][0]['polygon_holes']==[[HOLE]]
    assert timeline['sources'][0]['license']=='CC-BY-NC-SA-4.0'
    assert timeline['boundary_report']==report
