import json

from PIL import Image


def test_optional_historical_portrait_has_honest_procedural_fallback(tmp_path,monkeypatch):
    from pipeline.engine import acquire
    monkeypatch.setattr(acquire,'ROOT',tmp_path)
    target=tmp_path/'assets/portraits/story/ulisse.jpg';manifests=[]
    acquire._placeholder_portrait(target,'Ulisse',manifests)
    assert Image.open(target).size==(960,1200)
    metadata=json.loads(target.with_suffix('.metadata.json').read_text(encoding='utf-8'))
    assert metadata['extmetadata']['LicenseShortName']['value']=='CC0-1.0'
    assert 'non è un ritratto storico' in metadata['extmetadata']['ObjectName']['value']
    assert manifests[0]['path']=='assets/portraits/story/ulisse.jpg'
