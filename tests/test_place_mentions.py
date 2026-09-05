"""Geographic short names are accepted only when the actual catalog disambiguates them."""
import copy

import pytest

from app.movement_sync import mentions,narration_issue,plan_issue,repair_duplicate_routes


SIRENS={'id':'li_galli','name':'Isola delle Sirene (Li Galli)','pos':[14.431333,40.580833]}


def test_explicit_names_are_preserved_and_short_name_requires_catalog():
    assert mentions('Transito presso Li Galli.',SIRENS)
    assert mentions('Verso l’Isola delle Sirene.',SIRENS)
    assert not mentions('Ulisse supera le Sirene.',SIRENS)
    assert mentions('Ulisse supera le Sirene.',SIRENS,[SIRENS])


@pytest.mark.parametrize('other',[
    {'id':'sirens_other','name':'Isole delle Sirene (Altro arcipelago)'},
    {'id':'sirens_other','name':'Sirene'},
    {'id':'sirene','name':'Altra località'},
    {'id':'other','name':'Altra località','aliases':['Sirene']},
    {'id':'other','name':'Altra località','alternate_names':['Sirene']},
    {'id':'other','name':'Altra località','variants':['Sirene']},
])
def test_another_explicit_or_derived_name_blocks_ambiguous_shortcut(other):
    assert not mentions('Ulisse supera le Sirene.',SIRENS,[SIRENS,other])
    assert mentions('Transito presso Li Galli.',SIRENS,[SIRENS,other])


@pytest.mark.parametrize('label,spoken',[
    ('Porto di Forco','Forco'),('Lago dell’Averno','Averno'),
    ('Città di Firenze','Firenze'),('Arcipelago delle Galapagos','Galapagos'),
    ('Baia del Paradiso','Paradiso'),('Monte degli Ulivi','Ulivi'),
    ('Golfo dello Sperone','Sperone'),('Penisola della Maddalena','Maddalena'),
])
def test_only_explicit_geographic_prefix_and_preposition_are_removed(label,spoken):
    place={'id':'place','name':label}
    assert mentions('Arrivo a '+spoken,place,[place])


@pytest.mark.parametrize('label,spoken',[
    ('La terra delle Sirene','Sirene'),('Isola Sirene','Sirene'),
    ('Santuario delle Sirene','Sirene'),('Isola delle Sirenette','Sirene'),
    ('Isola di Eea','Eea'),('Isola del Nord','Nord'),('Isola del Sud','Sud'),
    ('Isola dell’Est','Est'),('Isola dell’Ovest','Ovest'),
    ('Baia del Nord-Ovest','Nord-Ovest'),('Golfo di Oriente','Oriente'),
])
def test_no_arbitrary_substrings_short_names_or_cardinal_directions(label,spoken):
    place={'id':'place','name':label}
    assert not mentions('Arrivo a '+spoken,place,[place])


def test_catalog_coordinates_and_names_remain_unchanged_and_ids_must_be_unique():
    catalog=[copy.deepcopy(SIRENS),{'id':'other','name':'Altro luogo','pos':[1.1,2.2]}]
    before=copy.deepcopy(catalog)
    assert mentions('Sirene',catalog[0],catalog)
    assert catalog==before
    assert not mentions('Sirene',catalog[0],[catalog[0],{**catalog[1],'id':'li_galli'}])
    assert not mentions('Sirene',catalog[0],[catalog[1]])


def test_plan_and_narration_accept_the_same_unique_short_name():
    place=copy.deepcopy(SIRENS)
    scene={'index':0,'title':'Passaggio delle Sirene','event':'Ulisse prosegue il viaggio.',
           'movements':[{'from':'ea','to':'li_galli','cue':0}]}
    assert plan_issue(scene,[place])==''
    batch={'scenes':[{'index':0,'lines':['Ulisse supera le Sirene.']}]}
    assert narration_issue(batch,[scene],[place])==''
    conflict={'id':'other','name':'Sirene'}
    assert plan_issue(scene,[place,conflict])
    assert narration_issue(batch,[scene],[place,conflict])


def test_duplicate_route_repair_uses_the_same_unambiguous_short_name():
    places=[{'id':'start','name':'Partenza'},{'id':'ea','name':'Eea'},copy.deepcopy(SIRENS)]
    route={'from':'ea','to':'li_galli','semantic':'journey','points':[[13,41],[14,40]]}
    scenes=[{'index':0,'historical_range':[-1200,-1100],'title':'Eea','event':'Partenza da Eea.',
             'focus':['ea'],'movements':[{'from':'start','to':'ea','semantic':'journey','cue':0},{**route,'cue':1}]},
            {'index':1,'historical_range':[-1200,-1100],'title':'Le Sirene','event':'Passaggio nello stretto.',
             'focus':['li_galli'],'movements':[{**route,'cue':0}]}]
    original=copy.deepcopy(scenes)
    reports=repair_duplicate_routes(scenes,places)
    assert len(reports)==1 and len(scenes[0]['movements'])==1
    assert scenes[1]==original[1]
    ambiguous=copy.deepcopy(original)
    assert repair_duplicate_routes(ambiguous,places+[{'id':'other','name':'Sirene'}])==[]
    assert ambiguous==original
