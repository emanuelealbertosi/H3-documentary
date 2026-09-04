import copy,json,sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1];CORE=ROOT/'pipeline';sys.path.insert(0,str(CORE))
from engine.history_direction import direction_for,shot_role,scene_issues,coverage,require_coverage
from engine.history_geography import atlas_config


def journey_scene(index,kind=None):
    role=shot_role({'journey':True},index,10)
    scene={'id':f'{index+1:02}','title':f'Tappa {index+1}','scene_type':kind or ('map_overview' if role=='geographic_anchor' else 'event_focus'),
           'focus':['troia'],'location_ids':['troia'],'person_ids':['odisseo'],'movements':[]}
    if role=='journey_progress':scene.update(scene_type='animated_route',schematic_journey={'stops':['Troia','Tempesta','Itaca'],'note':'Sequenza letteraria; tappe non localizzate sulla carta.'})
    return scene


def test_visual_direction_detects_journey_and_rejects_empty_maps_and_hidden_routes():
    direction=direction_for('Viaggio di Ulisse da Troia a Itaca','general_history','literary_tradition')
    assert direction=={'version':1,'journey':True,'map_led':True,'timeline_mode':'sequence','auto_persons':True}
    empty={'scene_type':'map_overview','focus':[],'movements':[]}
    assert any('mappa vuota' in x for x in scene_issues(empty,direction))
    hidden={**empty,'scene_type':'event_focus','movements':[{'points':[[1,2],[2,3]]}]}
    assert any('nascosto' in x for x in scene_issues(hidden,direction))


def test_journey_shot_roles_require_progress_and_full_plan_reports_counts():
    direction=direction_for('Il ritorno di Odisseo','general_history','literary_tradition')
    scenes=[journey_scene(i) for i in range(10)];doc={'visual_direction':direction,'scenes':scenes}
    report=require_coverage(doc)
    assert report['passed'] and report['map_scenes']==8 and report['schematic_journeys']==6 and report['person_scenes']==10
    scenes[1].pop('schematic_journey')
    with pytest.raises(ValueError,match='deve fare avanzare il viaggio'):require_coverage(doc)


def test_schematic_journey_requires_context_distinct_stops_and_explanation():
    direction=direction_for('Viaggio di Odisseo','exploration','literary_tradition')
    scene=journey_scene(1);scene['schematic_journey']={'stops':['Ciclope','Ciclope'],'note':''};scene['focus']=scene['location_ids']=[]
    text=' '.join(scene_issues(scene,direction,'journey_progress'))
    assert all(x in text for x in ['2–5 etichette distinte','note deve spiegare','carta di orientamento'])


def test_atlas_config_adds_bounded_detail_patches_for_close_views():
    geo=atlas_config([[23,39,32],[26.24,39.96,6],[20.67,38.4,6]])
    assert geo['bounds'][0]<20.67<geo['bounds'][2]
    assert len(geo['patches'])==2 and geo['terrain_zoom']==8
