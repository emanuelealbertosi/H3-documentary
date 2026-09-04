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
