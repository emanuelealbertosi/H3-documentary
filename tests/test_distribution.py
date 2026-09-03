"""Packaging gates; no production output or remote model is fabricated."""
from pathlib import Path
import json,hashlib,re
import httpx,pytest
from scripts import launch

ROOT=Path(__file__).resolve().parents[1]

def test_bundled_default_and_relocatable_settings(tmp_path,monkeypatch):
    from app import store
    from app.models import Settings
    from app.paths import DEFAULT_PIPELINE
    assert Path(DEFAULT_PIPELINE)==ROOT/'pipeline'
    monkeypatch.setattr(store,'DATA',tmp_path)
    saved=store.save_settings(Settings(pipeline_path=DEFAULT_PIPELINE))
    assert saved['pipeline_path']==DEFAULT_PIPELINE
    assert json.loads((tmp_path/'settings.json').read_text())['pipeline_path']==''

def test_local_instance_collision_is_rejected():
    def request(req):return httpx.Response(200,json={'service':'h3-documentary','instance':str(ROOT.parent/'another-copy')})
    with httpx.Client(transport=httpx.MockTransport(request)) as client:
        with pytest.raises(RuntimeError,match='occupata'):launch.health(client,'http://127.0.0.1:8775')

def test_assets_have_source_license_and_checksum():
    records=json.loads((ROOT/'scripts/assets-lock.json').read_text())
    paths={r['path'] for r in records}
    assert {'assets/voice/kokoro/kokoro-v1.0.onnx','assets/voice/kokoro/voices-v1.0.bin'}<=paths
    for r in records:
        assert len(r['sha256'])==64 and r['url'].startswith('https://') and r['license']
        if r['path'].startswith('assets/fonts/'):
            assert hashlib.sha256((ROOT/'pipeline'/r['path']).read_bytes()).hexdigest()==r['sha256']

def test_bat_uses_own_directory_and_inbox_powershell():
    assert sorted(p.name for p in ROOT.glob('*.bat'))==['AVVIA.bat','INSTALLA.bat','START.bat','STOP.bat']
    for p in ROOT.glob('*.bat'):
        data=p.read_text()
        assert '%~dp0' in data and '%SystemRoot%' in data and '-NoProfile' in data

def test_examples_and_runtime_modules_are_bundled():
    for file in ['pipeline/engine/render.py','pipeline/engine/atlas.py','pipeline/engine/narration.py',
                 'pipeline/engine/history_schema.py','pipeline/tools/acquire_atlas.py',
                 'pipeline/battles/waterloo/battle.json','pipeline/documentaries/rinascimento/documentary.json',
                 'pipeline/documentaries/via-della-seta/documentary.json']:
        assert (ROOT/file).is_file(),file

def test_geo_cache_never_modifies_external_pipeline(tmp_path,monkeypatch):
    from app import pipeline
    monkeypatch.setattr(pipeline,'ROOT',tmp_path)
    work=tmp_path/'work';raw=work/'assets/geography';raw.mkdir(parents=True)
    (raw/'land.geojson').write_text('immutable input')
    external=tmp_path/'external';external.mkdir()
    pipeline.cache_geographic_inputs(work,external)
    assert not (external/'assets').exists()
    bundled=tmp_path/'pipeline';bundled.mkdir()
    pipeline.cache_geographic_inputs(work,bundled)
    assert (bundled/'assets/geography/land.geojson').read_text()=='immutable input'
    (raw/'rivers.geojson.part').write_text('unfinished')
    pipeline.cache_geographic_inputs(work,bundled)
    assert not (bundled/'assets/geography/rivers.geojson.part').exists()

def test_example_portraits_are_downloadable_without_original_assets():
    for pattern in ['battles/*/battle.json','documentaries/*/documentary.json']:
        for path in (ROOT/'pipeline').glob(pattern):
            doc=json.loads(path.read_text(encoding='utf-8'))
            people=doc.get('commanders',doc.get('persons',[]))
            if isinstance(people,dict):people=people.values()
            for person in people:
                if person.get('portrait'):
                    metadata=(ROOT/'pipeline'/person['portrait']).with_suffix('.metadata.json')
                    assert metadata.exists() or person.get('commons_file') or person.get('wikipedia_page'),person['name']

def test_preserved_engine_baseline():
    baseline=json.loads((ROOT/'docs/engine-baseline.json').read_text())
    for name,expected in baseline['normalized_sha256'].items():
        data=(ROOT/'pipeline/engine'/name).read_bytes().replace(b'\r\n',b'\n')
        # Only the three explicit additive extension hooks may differ from 1.0.0.
        if name in {'visuals.py','render.py','export.py'}:
            data=re.sub(rb'(?m)^ +# BEGIN H3 IMAGE INSETS\n.*?^ +# END H3 IMAGE INSETS\n',b'',data,flags=re.S)
        assert hashlib.sha256(data).hexdigest()==expected,name
