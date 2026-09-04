"""Visual inventory, neutral fallbacks and scene-scoped replacements."""
import hashlib
import io

import pytest
from PIL import Image
from fastapi.testclient import TestClient

from app import media, runner, server, store, visual_slots
from app.models import ProjectRequest


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    (tmp_path / "jobs").mkdir()
    for module in (store, server, runner):
        if hasattr(module,"DATA"):monkeypatch.setattr(module, "DATA", tmp_path)
        if hasattr(module,"JOBS"):monkeypatch.setattr(module, "JOBS", tmp_path / "jobs")
    store.init()


def image_bytes(color="red"):
    data=io.BytesIO();Image.new("RGB",(320,240),color).save(data,format="PNG");return data.getvalue()


def make_project():
    project=store.create(ProjectRequest(topic="Viaggio di prova",start=False));pid=project["id"]
    work=store.JOBS/pid/"workspace";packpath=work/"battles/film-test/battle.json";packpath.parent.mkdir(parents=True)
    portrait=work/"assets/portraits/film-test/eroe.jpg";portrait.parent.mkdir(parents=True);Image.new("RGB",(200,300),"navy").save(portrait)
    store.write_json(portrait.with_suffix(".metadata.json"),{"descriptionurl":"https://example.test/eroe","extmetadata":{"LicenseShortName":{"value":"Public domain"},"ObjectName":{"value":"Eroe"}}})
    artwork=work/"assets/history/film-test/opera.jpg";artwork.parent.mkdir(parents=True);Image.new("RGB",(300,200),"gold").save(artwork)
    pack={"schema_version":2,"slug":"film-test","verification_dir":"film-test_verification","persons":[{"id":"eroe","name":"Eroe","portrait":"assets/portraits/film-test/eroe.jpg"}],
          "locations":[{"id":"citta","name":"Città","pos":[12,42]}],
          "visual_assets":[{"id":"opera","title":"Opera antica","path":"assets/history/film-test/opera.jpg","source":"https://example.test","license":"Public domain"}],
          "scenes":[{"id":"01","lines":["L'Eroe raggiunge la Città."],"person_ids":["eroe"],"location_ids":["citta"],"asset_ids":[]},
                    {"id":"02","lines":["Osserviamo l'opera."],"person_ids":[],"location_ids":[],"asset_ids":["opera"]}]}
    store.write_json(packpath,pack);return pid,work,packpath


def test_inventory_includes_people_places_and_authored_artwork():
    pid,work,packpath=make_project();pack=store.read_json(packpath)
    slots=visual_slots.prepare(pack)
    assert {(x["source_type"],x["label"]) for x in slots}=={("person","Eroe"),("place","Città"),("visual_asset","Opera antica")}
    assert next(x for x in slots if x["label"]=="Città")["uses"]==[{"scene_id":"01","cue":0}]
    assert pack["auto_visual_assets"][0]["name"]=="Città"


def test_neutral_place_and_portrait_are_attached_to_spoken_cue():
    pid,work,packpath=make_project();pack=store.read_json(packpath);visual_slots.prepare(pack)
    place=next(x for x in pack["visual_slots"] if x["kind"]=="place");target=work/place["path"];target.parent.mkdir(parents=True)
    Image.new("RGB",(300,220),"gray").save(target)
    store.write_json(target.with_suffix(".metadata.json"),{"h3_placeholder":True,"descriptionurl":"local","extmetadata":{"ObjectName":{"value":"Riquadro generico per Città"},"LicenseShortName":{"value":"CC0-1.0"}}})
    visual_slots.materialize(pack,work,[])
    assert {x["visual_state"] for x in pack["user_media"]}=={"available","blank"}
    assert len(pack["scenes"][0]["image_insets"])==2
    assert all(x["slots"]==2 for x in pack["scenes"][0]["image_insets"])


def test_user_replacement_changes_only_scenes_that_use_the_asset():
    pid,work,packpath=make_project();pack=store.read_json(packpath);visual_slots.prepare(pack)
    portrait_slot=next(x for x in pack["visual_slots"] if x["kind"]=="person")
    visual_slots.materialize(pack,work,[]);before=(work/pack["persons"][0]["portrait"]).read_bytes()
    uploaded=media.upload(image_bytes("green"),"nuovo-eroe.png")
    replacement=media.save(uploaded["id"],media.MediaEdit(title="Nuovo Eroe",bindings=[{"kind":"person","label":"Eroe"}],rights="test"))
    changed=visual_slots.materialize(pack,work,[replacement],replacements_only=True)
    assert changed==["01"] and (work/pack["persons"][0]["portrait"]).read_bytes()!=before
    entry=next(x for x in pack["user_media"] if x["id"]==portrait_slot["id"])
    assert entry["origin"]=="user_replacement" and entry["image_sha256"]==hashlib.sha256((work/entry["path"]).read_bytes()).hexdigest()


def test_completed_project_api_lists_all_replaceable_images_and_clone_omits_old_movie():
    pid,work,packpath=make_project();pack=store.read_json(packpath);visual_slots.prepare(pack);visual_slots.materialize(pack,work,[]);store.write_json(packpath,pack)
    store.update(pid,status="completed",stage="Documentario completato",progress=100)
    movie=work/"output/film-test_documentario_1080p.mp4";movie.parent.mkdir();movie.write_bytes(b"old movie")
    client=TestClient(server.app,headers={"X-DocumentariAI":"studio"})
    response=client.get(f"/api/projects/{pid}/visual-slots")
    assert response.status_code==200 and len(response.json()["slots"])==3
    clone=store.clone_completed(pid);visual_slots.clone_workspace(pid,clone["id"])
    assert movie.read_bytes()==b"old movie" and not (store.JOBS/clone["id"]/"workspace/output").exists()


def test_selective_worker_renders_only_changed_scene_and_reassembles(monkeypatch,tmp_path):
    pid,work,packpath=make_project();pack=store.read_json(packpath);visual_slots.prepare(pack);visual_slots.materialize(pack,work,[]);store.write_json(packpath,pack)
    timeline={**{k:v for k,v in pack.items() if k!='scenes'},"duration":6,"scenes":[
        {**pack['scenes'][0],"start":0,"end":3,"duration":3,"frames":72,"cues":[{"index":0,"start":.5,"end":2.5,"text":pack['scenes'][0]['lines'][0]}]},
        {**pack['scenes'][1],"start":3,"end":6,"duration":3,"frames":72,"cues":[{"index":0,"start":.5,"end":2.5,"text":pack['scenes'][1]['lines'][0]}]}]}
    store.write_json(work/'build/film-test/timeline.json',timeline)
    replacement=media.upload(image_bytes('green'),'sostituto.png')
    media.save(replacement['id'],media.MediaEdit(title='Eroe sostituito',bindings=[{'kind':'person','label':'Eroe'}],rights='test'))
    store.update(pid,status='running',result={'research':{'mode':'test'}});runner.FLAGS[pid]=__import__('threading').Event()
    source=tmp_path/'source';source.mkdir();(source/'.venv/Scripts').mkdir(parents=True);(source/'.venv/Scripts/python.exe').write_bytes(b'fixture')
    monkeypatch.setattr(runner,'verify_pipeline',lambda path:source)
    calls=[]
    def fake_run(project,python,folder,args,*rest,**kwargs):
        calls.append(args)
        if args[0].startswith('tools/check_'):
            store.write_json(work/'output/film-test_verification/report.json',{'video_duration':6,'bytes':123,'sha256':'a'*64})
    monkeypatch.setattr(runner,'run',fake_run)
    runner.refresh_visuals(pid,{'pipeline_path':'fixture','render_jobs':2})
    project=store.project(pid)
    assert project['status']=='completed' and project['result']['visual_update_scenes']==['01'],project['error']
    documentary=[x for x in calls if x[0]=='documentary.py']
    assert [x[1] for x in documentary]==['preview','render','finalize','verify']
    assert documentary[0][-2:]==['--scenes','01'] and documentary[1][4:6]==['--scenes','01']
