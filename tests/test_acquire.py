from pipeline.engine import acquire as acquire_module


def test_chatterbox_does_not_require_a_kokoro_download(tmp_path, monkeypatch):
    monkeypatch.setattr(acquire_module, "ROOT", tmp_path)
    for name in (
        "BebasNeue-Regular.ttf", "bebasneue-OFL.txt",
        "Manrope[wght].ttf", "manrope-OFL.txt",
        "CormorantGaramond[wght].ttf", "cormorantgaramond-OFL.txt",
    ):
        path = tmp_path / "assets" / "fonts" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fixture")

    acquire_module.acquire({
        "assets": [],
        "voice_engine": "chatterbox",
        "voice": "chatterbox-multilingual-v3@fixture",
        "commanders": {},
    })

    assert not (tmp_path / "chatterbox-multilingual-v3@fixture").exists()


def test_optional_people_and_places_fall_back_when_public_source_is_offline(tmp_path,monkeypatch):
    monkeypatch.setattr(acquire_module,"ROOT",tmp_path)
    for name in ("BebasNeue-Regular.ttf","bebasneue-OFL.txt","Manrope[wght].ttf","manrope-OFL.txt","CormorantGaramond[wght].ttf","cormorantgaramond-OFL.txt"):
        path=tmp_path/"assets/fonts"/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b"fixture")
    class Offline:
        headers={}
        def get(self,*args,**kwargs):raise acquire_module.requests.ConnectionError("offline")
    monkeypatch.setattr(acquire_module.requests,"Session",Offline)
    acquire_module.acquire({"assets":[],"voice_engine":"chatterbox","voice":"fixture",
        "commanders":{"persona":{"name":"Persona","portrait":"assets/portraits/persona.jpg","wikipedia_page":"Persona","portrait_optional":True}},
        "auto_visual_assets":[{"id":"visual-place-luogo","kind":"place","name":"Luogo","path":"assets/user/automatic/visual-place-luogo.jpg","wikipedia_page":"Luogo"}]})
    for path in (tmp_path/"assets/portraits/persona.jpg",tmp_path/"assets/user/automatic/visual-place-luogo.jpg"):
        assert path.is_file() and acquire_module.read_json(path.with_suffix('.metadata.json'))['h3_placeholder'] is True
