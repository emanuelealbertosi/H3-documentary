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
    for file in ['app/battle_outline.py','app/narration_builder.py','pipeline/engine/render.py','pipeline/engine/atlas.py','pipeline/engine/narration.py',
                 'app/documents.py','app/document_routes.py','static/documents.js','docs/DOCUMENTI.md',
                 'app/tts_api.py','app/tts_routes.py','static/tts-api.js','docs/TTS_API.md',
                 'pipeline/engine/history_schema.py','pipeline/engine/history_direction.py',
                 'pipeline/engine/history_geography.py','pipeline/tools/acquire_atlas.py',
                 'pipeline/battles/waterloo/battle.json','pipeline/documentaries/rinascimento/documentary.json',
                 'pipeline/documentaries/via-della-seta/documentary.json']:
        assert (ROOT/file).is_file(),file

def test_tts_admin_uses_a_friendly_default_profile_name():
    source=(ROOT/'static/tts-api.js').read_text(encoding='utf-8')
    assert "providers[provider]?.name||'Server TTS'" in source

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

def test_broad_cached_patch_is_not_reused_for_close_tactical_map(tmp_path):
    from app import pipeline
    source=tmp_path/'pipeline';atlas=source/'assets/geography/atlas-v2';atlas.mkdir(parents=True)
    (atlas/'atlas.json').write_text(json.dumps({'layers':[{'levels':['unused.npy']}]}))
    (source/'assets/geography/manifest.json').write_text(json.dumps({'bounds':[0,0,10,10],'patches':{'broad':[0,0,10,10]}}))
    work=tmp_path/'work';work.mkdir()
    geo={'bounds':[4,4,6,6],'patches':{'close':[4.9,4.9,5.1,5.1]},'output':'assets/geography/new'}
    assert pipeline.reuse_atlas(work,source,geo) is False

def test_history_asset_fix_is_applied_only_to_bundled_resumable_workspace(tmp_path,monkeypatch):
    from app import pipeline
    root=tmp_path/'app';source=root/'pipeline';jobs=root/'data/jobs';work=jobs/'abc/workspace'
    for base in (source/'engine',work/'engine'):base.mkdir(parents=True)
    for name in ('acquire.py','history_assets.py'):
        (source/'engine'/name).write_text('new '+name)
        (work/'engine'/name).write_text('old '+name)
    monkeypatch.setattr(pipeline,'ROOT',root);monkeypatch.setattr(pipeline,'JOBS',jobs)
    assert pipeline.prepare_history_asset_engine(work,source) is True
    assert (work/'engine/acquire.py').read_text()=='new acquire.py'
    assert list((work/'engine-compat-backups').glob('asset-*/acquire.py'))
    external=tmp_path/'external';(external/'engine').mkdir(parents=True)
    assert pipeline.prepare_history_asset_engine(work,external) is False

def test_runtime_fixes_are_applied_generically_to_bundled_jobs(tmp_path,monkeypatch):
    from app import pipeline
    root=tmp_path/'app';source=root/'pipeline';jobs=root/'data/jobs';work=jobs/'any-project/workspace'
    names=['engine/narration.py','engine/atlas.py','engine/history_visuals.py','tools/chatterbox/synthesize_documentary.py']
    for name in names:
        (source/name).parent.mkdir(parents=True,exist_ok=True);(source/name).write_text('new '+name)
        (work/name).parent.mkdir(parents=True,exist_ok=True);(work/name).write_text('old '+name)
    monkeypatch.setattr(pipeline,'ROOT',root);monkeypatch.setattr(pipeline,'JOBS',jobs)
    assert pipeline.prepare_bundled_runtime_engine(work,source) is True
    assert all((work/name).read_text()=='new '+name for name in names)
    assert list((work/'engine-compat-backups').glob('runtime-*/engine/narration.py'))
    external=tmp_path/'external';(external/'engine').mkdir(parents=True)
    assert pipeline.prepare_bundled_runtime_engine(work,external) is False

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
        # Named general-history modules have explicit, tested compatibility extensions.
        expected=baseline.get('hybrid_extensions_sha256',{}).get(name,expected)
        data=(ROOT/'pipeline/engine'/name).read_bytes().replace(b'\r\n',b'\n')
        # Strip only named additive hooks; all other original renderer/TTS bytes are checked.
        if name in {'visuals.py','render.py','export.py','atlas.py'}:
            data=re.sub(rb'(?m)^ +# BEGIN H3 IMAGE INSETS\n.*?^ +# END H3 IMAGE INSETS\n',b'',data,flags=re.S)
            data=re.sub(rb'(?m)^ +# BEGIN H3 RESEARCH PROVENANCE\n.*?^ +# END H3 RESEARCH PROVENANCE\n',b'',data,flags=re.S)
            data=re.sub(rb'(?m)^ +# BEGIN H3 BATTLE ATLAS TACTICS\n.*?^ +# END H3 BATTLE ATLAS TACTICS\n',b'',data,flags=re.S)
            data=re.sub(rb'(?m)^ +# BEGIN H3 OPENING LAYOUT\n.*?^ +# END H3 OPENING LAYOUT\n',b'',data,flags=re.S)
            data=re.sub(rb'(?m)^ +# BEGIN H3 TTS CREDIT\n.*?^ +# END H3 TTS CREDIT\n',b'',data,flags=re.S)
            data=re.sub(rb'(?m)^ +# BEGIN H3 LOCAL DOCUMENT LINKS\n.*?^ +# END H3 LOCAL DOCUMENT LINKS\n',b'',data,flags=re.S)
        assert hashlib.sha256(data).hexdigest()==expected,name
