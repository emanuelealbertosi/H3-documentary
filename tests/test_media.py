"""Real image validation, local API boundaries, cue association and snapshot isolation."""
import io, json, copy, hashlib
from pathlib import Path
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from app import media,store,server
from app.models import ProjectRequest

@pytest.fixture(autouse=True)
def isolated(tmp_path,monkeypatch):
    (tmp_path/'jobs').mkdir()
    for module in (store,server):
        monkeypatch.setattr(module,'DATA',tmp_path)
        monkeypatch.setattr(module,'JOBS',tmp_path/'jobs')
    store.init()

@pytest.fixture
def client():return TestClient(server.app,headers={'X-DocumentariAI':'studio'})

def picture(color='red',fmt='PNG'):
    b=io.BytesIO();Image.new('RGB',(320,240),color).save(b,format=fmt);return b.getvalue()

def bound(label='Annibale',kind='person'):
    m=media.upload(picture(),'ritratto.png')
    return media.save(m['id'],media.MediaEdit(title='Annibale Barca',bindings=[{'kind':kind,'label':label,'aliases':['generale cartaginese']}],credit='Autore prova',rights='Immagine di test'))

def test_upload_validate_original_and_safe_filename(client):
    raw=picture()
    r=client.post('/api/media?filename=../../ritratto.png',content=raw)
    assert r.status_code==201,r.text
    m=r.json();assert m['filename']=='ritratto.png' and m['sha256']==hashlib.sha256(raw).hexdigest()
    assert (media.folder(m['id'])/m['original']).read_bytes()==raw
    assert client.get('/api/media/'+m['id']+'/image').headers['content-type']=='image/png'
    assert client.get('/api/media/'+m['id']+'/record.json').status_code==404
    assert client.get('/api/media/not-an-id/image').status_code==404
    assert client.post('/api/media',content=b'<svg onload="bad()"/>').status_code==400
    assert client.post('/api/media',content=picture(fmt='GIF')).status_code==400

def test_upload_requires_local_ui_and_size_cap(client,monkeypatch):
    assert TestClient(server.app).post('/api/media',content=picture()).status_code==403
    assert client.post('/api/media',content=picture(),headers={'Origin':'https://evil.example'}).status_code==403
    monkeypatch.setattr(media,'MAX_BYTES',32)
    assert client.post('/api/media',content=b'a'*33).status_code==413

def test_metadata_and_geometry_validation(client):
    m=bound();payload=media.MediaEdit(title='Nuovo titolo').model_dump()
    payload['layout']['width']=.95
    assert client.put('/api/media/'+m['id'],json=payload).status_code==422
    payload['layout']['width']=.2;payload['path']='../../settings.json'
    assert client.put('/api/media/'+m['id'],json=payload).status_code==422

def test_matching_uses_words_aliases_and_explicit_scene_titles():
    m=bound('Roma','place')
    assert media.scene_matches({'lines':['La città di Roma.','Il mondo romano.','Il generale cartaginese arriva.']},m)==[0,2]
    m['bindings']=[{'kind':'scene','label':'Le Alpi'}]
    assert media.scene_matches({'title':'Le Alpi','lines':['Un valico innevato.']},m)==[0]
    assert media.mention('NICCOLÒ, a Firenze.','Niccolo')

def test_archive_restore_preserves_files(client):
    m=bound();v=media.MediaEdit.model_validate({k:m[k] for k in media.MediaEdit.model_fields})
    v.enabled=False
    assert client.put('/api/media/'+m['id'],json=v.model_dump()).json()['enabled'] is False
    assert (media.folder(m['id'])/'image.png').exists()
    v.enabled=True
    assert client.put('/api/media/'+m['id'],json=v.model_dump()).json()['enabled'] is True

def test_delete_removes_only_the_library_copy(client):
    m=bound();target=media.folder(m['id'])
    response=client.delete('/api/media/'+m['id'])
    assert response.status_code==200 and response.json()=={'deleted':True,'id':m['id']}
    assert not target.exists() and client.delete('/api/media/'+m['id']).status_code==404

def test_snapshot_no_mutation_or_unmatched_assets(tmp_path):
    m=bound();unused=media.upload(picture('blue'),'altro.png')
    p=store.create(ProjectRequest(topic='La storia di Annibale',start=False))
    records=media.freeze(p['id'],True)
    media.save(m['id'],media.MediaEdit(title='Modificato dopo avvio'))
    assert media.freeze(p['id'],True)==records
    work=store.JOBS/p['id']/'workspace';work.mkdir()
    pack={'video_license':'CC0','scenes':[{'id':'01','lines':['Annibale attraversa le Alpi.','Un panorama.']} ]}
    assert media.attach(pack,records,work)==1
    assert pack['user_media'][0]['title']=='Annibale Barca'
    assert not(work/'assets/user'/unused['id']).exists()
    assert 'video_license' not in pack
    assert (work/pack['user_media'][0]['original_path']).read_bytes()==picture()
    files=server.output_files(p['id'])
    assert any(x['name']=='original.png' for x in files)
    src=media.folder(m['id'])/'image.png';src.write_bytes(picture('blue'))
    assert (work/pack['user_media'][0]['path']).read_bytes()!=src.read_bytes()

def test_unassociated_or_disabled_assets_leave_legacy_pack_identical(tmp_path):
    m=bound();pack={'scenes':[{'lines':['La rivoluzione industriale.']} ]};old=copy.deepcopy(pack)
    assert media.attach(pack,[m],tmp_path)==0 and pack==old
    pack['scenes'][0]['lines']=['Annibale'];old=copy.deepcopy(pack);m['enabled']=False
    assert media.attach(pack,[m],tmp_path)==0 and pack==old

def test_multiple_images_have_ordered_slots(tmp_path):
    a,b=bound(),bound()
    pack={'scenes':[{'lines':['Annibale.']} ]}
    assert media.attach(pack,[a,b],tmp_path)==2
    assert [(x['cue'],x['slot'],x['slots']) for x in pack['scenes'][0]['image_insets']]==[(0,0,2),(0,1,2)]

def test_project_opt_out_and_frozen_settings(client):
    p=client.post('/api/projects',json={'topic':'Storia di Roma','start':False}).json()
    assert p['use_media']==1
    assert client.put('/api/projects/'+p['id']+'/media',json={'enabled':False}).status_code==200
    assert media.freeze(p['id'],False)==[]
    assert client.put('/api/projects/'+p['id']+'/media',json={'enabled':True}).status_code==409
    assert client.get('/projects/'+p['id']+'/media').status_code==200

def test_draft_targets_are_extracted_from_outline():
    p=store.create(ProjectRequest(topic='Annibale in Italia',start=False))
    store.write_json(store.JOBS/p['id']/'checkpoints/outline.json',{'places':[{'id':'roma','name':'Roma'}],'commanders':[{'name':'Annibale'}],'scenes':[{'title':'Le Alpi'}]})
    assert {'kind':'place','label':'Roma'} in media.targets(p['id'])
    assert {'kind':'person','label':'Annibale'} in media.targets(p['id'])
    assert {'kind':'scene','label':'Le Alpi'} in media.targets(p['id'])
