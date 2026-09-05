"""The opt-in recovery card displays replacements without changing other cards."""
import copy
import sys
from pathlib import Path

import pytest
from PIL import Image,ImageDraw

PIPELINE=Path(__file__).resolve().parents[1]/'pipeline'
sys.path.insert(0,str(PIPELINE))
from engine import image_insets,visuals


@pytest.fixture
def compositor(tmp_path,monkeypatch):
    monkeypatch.setattr(image_insets,'ROOT',tmp_path)
    monkeypatch.setattr(visuals,'ROOT',PIPELINE)
    visuals.font.cache_clear()
    obj=object.__new__(image_insets.InsetVisuals)
    obj.cards={};obj.items={}
    yield obj,tmp_path
    visuals.font.cache_clear()


def scene():
    return {'id':'01','scene_type':'event_focus','background_asset_id':'replacement',
            'facts':['Una carta caricata per spiegare il passaggio.'],
            'visual_recovery':{'version':1,'placeholder':True,'reason':'route_not_grounded'},
            'movements':[],'image_insets':[]}


def base_card():
    image=Image.new('RGB',(1920,1080),(13,31,42));draw=ImageDraw.Draw(image)
    draw.rectangle((0,0,1919,169),fill=(90,31,120))
    draw.rectangle((0,935,1919,1079),fill=(20,110,45))
    draw.rectangle((115,285,1450,450),fill=(249,238,211))
    return image


def associate(obj,work,size=(1600,900),**flags):
    image=Image.new('RGB',size,(244,242,232));draw=ImageDraw.Draw(image)
    edge=100;w,h=size
    for box,color in [((0,0,edge,edge),(255,0,0)),((w-edge-1,0,w-1,edge),(0,255,0)),
                      ((0,h-edge-1,edge,h-1),(0,0,255)),((w-edge-1,h-edge-1,w-1,h-1),(255,255,0))]:
        draw.rectangle(box,fill=color)
    path=work/'assets/user/replacement.png';path.parent.mkdir(parents=True);image.save(path)
    obj.items['replacement']={'id':'replacement','path':'assets/user/replacement.png','visual_state':'user',**flags}
    return path


@pytest.mark.parametrize('size',[(1600,900),(800,1200)])
def test_replacement_is_complete_bright_and_keeps_header_and_chronology(compositor,size):
    obj,work=compositor;path=associate(obj,work,size);original=path.read_bytes()
    card=base_card();before=card.tobytes();spec=scene();saved=copy.deepcopy(spec)
    result=obj.backdrop(card,spec)
    colors=dict((color,count) for count,color in result.getcolors(result.width*result.height))
    # All four corner markers survive contain scaling, at their original
    # brightness; both cover cropping and old backdrop darkening fail this.
    for color in ((255,0,0),(0,255,0),(0,0,255),(255,255,0)):
        assert colors.get(color,0)>500
    assert colors.get((244,242,232),0)>150000
    for box in ((0,0,1920,170),(0,935,1920,1080),(0,170,50,935),(1870,170,1920,935)):
        assert result.crop(box).tobytes()==card.crop(box).tobytes()
    assert card.tobytes()==before and spec==saved and path.read_bytes()==original
    assert result.tobytes()==obj.backdrop(card,spec).tobytes()


@pytest.mark.parametrize('flags',[{'visual_state':'blank'},{'placeholder':True}])
def test_known_generated_placeholder_preserves_editorial_card(compositor,flags):
    obj,work=compositor;associate(obj,work,**flags)
    card=base_card()
    assert obj.backdrop(card,scene()).tobytes()==card.tobytes()
    assert not obj.cards


def test_unknown_user_image_is_still_displayed_and_long_fact_does_not_cover_it(compositor):
    obj,work=compositor;associate(obj,work,visual_state=None)
    spec=scene();spec['facts']=['Una spiegazione approvata molto estesa. '*70]
    card=base_card();result=obj.backdrop(card,spec)
    spec['facts']=[]
    without_caption=obj.backdrop(card,spec)
    assert result.tobytes()==without_caption.tobytes()
    assert result.tobytes()!=card.tobytes()


@pytest.mark.parametrize('recovery',[None,{'version':2,'placeholder':True,'reason':'test'},
                                   {'version':1,'placeholder':False,'reason':'test'}])
def test_existing_backdrops_keep_their_previous_blended_appearance(compositor,recovery):
    obj,work=compositor;associate(obj,work)
    card=base_card();normal=scene();normal.pop('visual_recovery')
    expected=obj.backdrop(card,normal)
    candidate={**normal,'visual_recovery':recovery}
    assert obj.backdrop(card,candidate).tobytes()==expected.tobytes()
    # Existing text remains readable in the legacy blended treatment.
    assert expected.getpixel((500,350))==card.getpixel((500,350))
