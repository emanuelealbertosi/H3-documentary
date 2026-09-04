import array,io,math,wave
import pytest
from app import store,tts
from app.models import ProjectRequest,VoiceChoice

@pytest.fixture(autouse=True)
def isolated(tmp_path,monkeypatch):
    (tmp_path/'jobs').mkdir();monkeypatch.setattr(store,'DATA',tmp_path);monkeypatch.setattr(store,'JOBS',tmp_path/'jobs');store.init()

def sample(seconds=10,sample_rate=16000):
    data=array.array('h',(round(math.sin(i*2*math.pi*220/sample_rate)*4000) for i in range(seconds*sample_rate)))
    out=io.BytesIO()
    with wave.open(out,'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(sample_rate);f.writeframes(data.tobytes())
    return out.getvalue()

def fake_chatterbox(root):
    for path in [root/'.venv-chatterbox/Scripts/python.exe',root/'assets/tts/chatterbox-v3/manifest.json',root/'tools/chatterbox/synthesize_documentary.py']:
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text('{}')

def test_reference_is_validated_and_stored_immutably(tmp_path):
    record=tts.upload_reference(sample(),'narratore.wav')
    assert record['duration_seconds']==10 and record['name']=='narratore'
    assert tts.voice(record['id'])['sha256']==record['sha256']
    with pytest.raises(ValueError,match='WAV'):tts.upload_reference(b'not audio','bad.mp3')
    with pytest.raises(ValueError,match='4 a 60'):tts.upload_reference(sample(2),'short.wav')

def test_chatterbox_pack_uses_snapshot_and_reference_hash(tmp_path):
    pipeline=tmp_path/'pipeline';fake_chatterbox(pipeline);record=tts.upload_reference(sample(),'mia voce.wav')
    work=tmp_path/'work';work.mkdir();pack={}
    project={'tts_engine':'chatterbox','tts_reference_id':record['id']}
    tts.configure_pack(pack,project,work,pipeline)
    assert pack['voice_engine']=='chatterbox' and pack['voice_speaker'].startswith('clone-')
    copied=work/pack['voice_reference'];assert copied.read_bytes()==sample()
    assert 'MIT' in pack['voice_credit']

def test_old_projects_remain_kokoro_and_voice_change_invalidates_only_later_stages(tmp_path):
    project=store.create(ProjectRequest(topic='Battaglia di prova',start=False))
    assert project['tts_engine']=='kokoro'
    pipeline=tmp_path/'pipeline';fake_chatterbox(pipeline)
    store.save_settings(__import__('app.models',fromlist=['Settings']).Settings(pipeline_path=str(pipeline)))
    cp=store.JOBS/project['id']/'checkpoints';cp.mkdir()
    for name in ('research','outline','narration','review','geography','assets','voice','preview','render','finalize','verify'):(cp/(name+'.done.json')).write_text('{}')
    build=store.JOBS/project['id']/'workspace/build';build.mkdir(parents=True);(build/'timeline.json').write_text('{}')
    changed=tts.change_project_voice(project['id'],VoiceChoice(tts_engine='chatterbox'))
    assert changed['tts_engine']=='chatterbox' and (cp/'outline.done.json').exists() and (cp/'assets.done.json').exists()
    assert not (cp/'voice.done.json').exists() and list(cp.glob('voice.before-voice-*.json'))
    assert not build.exists() and list((store.JOBS/project['id']/'workspace').glob('build-before-voice-*'))

def test_chatterbox_requires_real_local_install(tmp_path):
    with pytest.raises(ValueError,match='INSTALLA.bat'):tts.ensure_available('chatterbox','',tmp_path/'missing')
