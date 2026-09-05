import copy,json,sys,subprocess,math,shutil
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'pipeline'))
from engine.history_territories import area_style,scene_area_points,area_view,state_blend
from engine.history_profiles import detect_type,PROFILES
from engine.history_direction import direction_for,direction_prompt
from engine.history_schema import validate_document

POLYGON=[[0,40],[14,40],[14,50],[0,50]]

def layer():return {'id':'domain','label':'Area di prova','kind':'territory','schematic':True,'color':[218,154,70],
                    'sources':['R1'],'states':[{'year':1500,'polygons':[POLYGON]},{'year':1520,'polygons':[]}]}

def test_geopolitical_requests_and_boundary_topics_keep_the_existing_types():
    assert len(PROFILES)==14
    for topic in ['Zone di influenza in Europa','Sfere d’influenza nel Mediterraneo','Alleanze della Guerra Fredda']:
        assert detect_type(topic)=='political_history'
    for topic in ['Espansione territoriale mongola','I confini delle nazioni europee','Perdite territoriali di un impero']:
        assert detect_type(topic)=='territorial_expansion'
    assert detect_type('Battaglia di Napoleone per i confini')=='battle'
    direction=direction_for('Zone di influenza','political_history')
    assert direction['map_led'] and direction['territory_style']==2
    assert 'schematic=true' in direction_prompt(direction)

def test_camera_covers_inherited_and_changed_territory_without_future_expansion():
    domain=layer();domain['states'].append({'year':1550,'polygons':[[[70,20],[75,20],[75,25]]]})
    doc={'visual_layers':[domain]};scene={'historical_range':[1510,1525],'territory_ids':['domain']}
    points=scene_area_points(doc,scene)
    assert points==POLYGON and scene_area_points(doc,{**scene,'territory_ids':[]})==[]
    view=area_view(points)
    def merc(y):return math.degrees(math.asinh(math.tan(math.radians(y))))
    xy=[(960+(p[0]-view[0])*1920/view[2],540-(merc(p[1])-merc(view[1]))*1920/view[2]) for p in points]
    assert all(60<x<1860 and 180<y<745 for x,y in xy)
    assert scene_area_points(doc,{'historical_range':[1530,1540],'territory_ids':['domain']})==[]

def test_area_state_is_persistent_and_fades_continuously_including_total_loss():
    domain=layer();domain['transition_years']=2
    assert state_blend(domain,1490)==[]
    assert state_blend(domain,1510)==[(domain['states'][0],1)]
    before=state_blend(domain,1520.1);after=state_blend(domain,1520.2)
    assert before[0][1]>after[0][1] and before[-1][1]<after[-1][1]
    assert state_blend(domain,1523)==[(domain['states'][1],1)]


def test_compiler_and_atlas_include_territories_without_city_focus():
    from engine.history_authoring import compile_outline
    from engine.history_schema import adapt
    domain=layer()
    outline={'documentary_type':'territorial_expansion','title':'Prova dei territori','short_title':'Territori',
             'historical_period':[1500,1525],'places':[],'visual_layers':[domain],
             'scenes':[{'title':'Area iniziale','scene_type':'territorial_change','historical_range':[1500,1515],
                        'territory_ids':['domain'],'focus':[],'event':'Area di prova','source_ids':['R1']}]}
    narration=[{'index':0,'lines':['parola '*170],'fact':'Dati sintetici di prova','kicker':'Prova'}]
    doc,geo=compile_outline(outline,narration,[{'id':'R1','title':'Fixture','url':'https://example.org'}],
                            {'id':'area-test','topic':'Espansione territoriale','minutes':1},{})
    assert doc['scenes'][0]['camera_end']==area_view(POLYGON)
    west,south,east,north=geo['bounds']
    assert all(west<x<east and south<y<north for x,y in POLYGON)
    direct=copy.deepcopy(doc)
    direct['scenes'][0].pop('camera_end');direct['scenes'][0].pop('camera_start')
    assert adapt(direct)['scenes'][0]['camera_end']==area_view(POLYGON)

def test_area_semantics_distinguish_sovereignty_influence_and_dispute():
    domain=layer();state=domain['states'][0]
    influence={**domain,'kind':'influence','color':[68,184,231]}
    contested={**domain,'kind':'contested','color':[239,86,91]}
    assert area_style(domain,state)['fill']>area_style(influence,state)['fill']
    assert area_style(contested,state)['hatch']
    assert area_style({**domain,'schematic':False},state)['dashed'] is False
    assert area_style(influence,state)['dashed'] is True

def test_documented_boundary_requires_geometry_provenance_but_legacy_stays_valid():
    doc=json.loads((ROOT/'pipeline/documentaries/rinascimento/documentary.json').read_text(encoding='utf-8'))
    doc['visual_layers']=[layer()];doc['visual_layers'][0]['schematic']=False
    validate_document(doc)  # Legacy pack compatibility.
    doc['visual_direction']={'territory_style':2}
    with pytest.raises(ValueError,match='geometry_source'):validate_document(doc)
    doc['visual_layers'][0]['geometry_source']='Explicit synthetic fixture geometry; not a historical border.'
    validate_document(doc)
    doc['visual_layers'][0]['transition_years']=-1
    with pytest.raises(ValueError,match='transition_years'):validate_document(doc)

def test_grouped_mode_menu_preserves_every_api_value_including_existing_projects():
    # Exercise the actual browser module in Node, not a second copy of its catalog.
    script="""import {modeGroups,documentaryModeSelect,modeHint} from './static/documentary-modes.js';
    console.log(JSON.stringify({groups:modeGroups.length,ids:modeGroups.flatMap(g=>g[1].map(r=>r[0])),
      html:documentaryModeSelect('reg-type','political_history'),hint:modeHint('political_history')}));"""
    if not shutil.which('node'):pytest.skip('Node is only needed for the frontend developer check')
    result=subprocess.run(['node','--input-type=module','-e',script],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',check=True)
    data=json.loads(result.stdout)
    assert data['groups']==5 and len(data['ids'])==len(set(data['ids']))==14 and set(data['ids'])==set(PROFILES)
    assert 'value="political_history" selected' in data['html'] and data['html'].count('<optgroup')==5
    assert 'aria-describedby="reg-type-hint"' in data['html'] and 'Influenza' in data['hint']
