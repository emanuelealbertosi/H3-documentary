"""Conservative itinerary recovery; no route invention or edits to validated scenes."""
from copy import deepcopy

import pytest

from app.movement_sync import repair_duplicate_routes


PLACES=[{'id':'porto-alfa','name':'Porto Alfa','pos':[10,40]},
        {'id':'porto-beta','name':'Porto Beta','pos':[11,41]},
        {'id':'porto-gamma','name':'Porto Gamma','pos':[9,39]}]


def fixture():
    journey={'from':'porto-alfa','to':'porto-beta','semantic':'journey',
             'entity_id':'viaggiatore','points':[[10,40],[10.5,40.7],[11,41]],'sources':['S1'],'cue':1}
    arrival={'from':'porto-gamma','to':'porto-alfa','semantic':'journey',
             'points':[[9,39],[10,40]],'sources':['S2'],'cue':0}
    donor={'index':4,'title':'La sosta a Porto Alfa','event':'La nave riparte da Porto Alfa.',
           'historical_range':[-1200,-1100],'focus':['porto-alfa'],'movements':[arrival,deepcopy(journey)],
           'source_ids':['S1','S2'],'notes':'Testo editoriale immutato.'}
    kept=deepcopy(journey);kept.update(cue=0,from_label='Porto Alfa',to_label='Porto Beta')
    recipient={'index':5,'title':'Il passaggio a Porto Beta','event':'I viaggiatori arrivano a Porto Beta.',
               'historical_range':[-1200,-1100],'focus':['porto-beta'],'movements':[kept],
               'source_ids':['S1']}
    return [donor,recipient]


def test_identical_adjacent_route_different_cues_has_exact_audit_and_no_other_edits():
    scenes=fixture();before=deepcopy(scenes);places=deepcopy(PLACES)
    original_removed=scenes[0]['movements'][1]
    removed=deepcopy(before[0]['movements'][1]);expected=deepcopy(before)
    expected[0]['movements'].pop(1)
    report=repair_duplicate_routes(scenes,places)
    assert scenes==expected and places==PLACES
    assert report==[{'action':'remove_adjacent_duplicate_journey','scene_index':4,'kept_scene_index':5,
                    'from':'porto-alfa','to':'porto-beta','semantic':'journey','removed':removed}]
    assert scenes[1]==before[1]  # The arrival cue, sources and coordinates are untouched.
    original_removed['points'][0][0]=100
    assert report[0]['removed']['points'][0]==[10,40]
    assert repair_duplicate_routes(scenes,places)==[]  # Idempotent.


@pytest.mark.parametrize('semantic',['attack','invasion','migration','trade'])
def test_even_identical_nonjourney_movements_are_not_deduplicated(semantic):
    scenes=fixture()
    scenes[0]['movements'][1]['semantic']=scenes[1]['movements'][0]['semantic']=semantic
    before=deepcopy(scenes)
    assert repair_duplicate_routes(scenes,PLACES)==[] and scenes==before


def test_previously_validated_scene_outside_batch_is_neither_used_nor_changed():
    donor,approved=fixture();approved_before=deepcopy(approved)
    batch=[donor];before=deepcopy(batch)
    assert repair_duplicate_routes(batch,PLACES)==[]
    assert batch==before and approved==approved_before


def test_both_scenes_explicitly_tell_the_destination_are_legitimate():
    scenes=fixture();scenes[0]['event']='La nave lascia Porto Alfa verso Porto Beta.'
    before=deepcopy(scenes)
    assert repair_duplicate_routes(scenes,PLACES)==[] and scenes==before


@pytest.mark.parametrize('difference',[
    'reverse','points','sources','entity','period','donor-semantic','recipient-semantic',
    'additional-field','far-recipient','donor-focus','recipient-focus','unknown-place','same-place',
])
def test_nonidentical_or_unsupported_routes_are_never_repaired(difference):
    scenes=fixture();donor,recipient=scenes;route=recipient['movements'][0]
    if difference=='reverse':route['from'],route['to']=route['to'],route['from']
    elif difference=='points':route['points'][1]=[10.6,40.8]
    elif difference=='sources':route['sources']=['S3']
    elif difference=='entity':route['entity_id']='altro-viaggiatore'
    elif difference=='period':recipient['historical_range']=[-1190,-1100]
    elif difference=='donor-semantic':donor['movements'][1]['semantic']='migration'
    elif difference=='recipient-semantic':route['semantic']='trade'
    elif difference=='additional-field':route['label']='Un percorso distinto'
    elif difference=='far-recipient':recipient['index']=8
    elif difference=='donor-focus':donor['focus']=['porto-gamma']
    elif difference=='recipient-focus':recipient['focus']=['porto-gamma']
    elif difference=='unknown-place':
        donor['movements'][1]['from']=route['from']='porto-sconosciuto';donor['focus']=['porto-sconosciuto']
    elif difference=='same-place':
        donor['movements'][1]['from']=route['from']='porto-beta';donor['focus']=['porto-beta']
    before=deepcopy(scenes)
    assert repair_duplicate_routes(scenes,PLACES)==[] and scenes==before


def test_ambiguous_adjacent_recipients_require_author_revision():
    scenes=fixture();other=deepcopy(scenes[1]);other['index']=3;scenes.append(other)
    before=deepcopy(scenes)
    assert repair_duplicate_routes(scenes,PLACES)==[] and scenes==before


def test_last_route_is_retained_unless_a_schematic_journey_remains():
    scenes=fixture();scenes[0]['movements']=scenes[0]['movements'][1:]
    before=deepcopy(scenes)
    assert repair_duplicate_routes(scenes,PLACES)==[] and scenes==before
    scenes[0]['schematic_journey']={'stops':[{'label':'Porto Gamma'},{'label':'Porto Alfa'}]}
    schematic=deepcopy(scenes[0]['schematic_journey'])
    assert len(repair_duplicate_routes(scenes,PLACES))==1
    assert scenes[0]['movements']==[] and scenes[0]['schematic_journey']==schematic


def test_batch_order_does_not_define_adjacency_or_change_recipient_order():
    scenes=fixture();scenes.reverse();recipient_before=deepcopy(scenes[0])
    assert len(repair_duplicate_routes(scenes,PLACES))==1
    assert [scene['index'] for scene in scenes]==[5,4] and scenes[0]==recipient_before


@pytest.mark.parametrize('donor_type,recipient_type',[(list,list),(tuple,tuple),(list,tuple),(tuple,list)])
def test_equivalent_period_sequences_are_compared_without_rewriting_them(donor_type,recipient_type):
    scenes=fixture()
    scenes[0]['historical_range']=donor_type(scenes[0]['historical_range'])
    scenes[1]['historical_range']=recipient_type(scenes[1]['historical_range'])
    original_periods=[scene['historical_range'] for scene in scenes]
    assert len(repair_duplicate_routes(scenes,PLACES))==1
    assert scenes[0]['historical_range'] is original_periods[0]
    assert scenes[1]['historical_range'] is original_periods[1]
