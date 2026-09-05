"""Offline integration checks: downloaded bitmap, usage gate and published credits."""
import copy
import hashlib
import io
import json

from PIL import Image
import pytest
import requests

from pipeline.engine import acquire, history_assets, image_search


PATH = 'assets/portraits/malea.jpg'
SUBJECT = {'name': 'Cape Malea', 'kind': 'place', 'commons_file': 'Cape Malea.jpg'}


def bitmap():
    stream = io.BytesIO()
    Image.new('RGB', (640, 480), (32, 120, 180)).save(stream, format='JPEG')
    return stream.getvalue()


def metadata(code='by-nc-sa'):
    url = f'https://creativecommons.org/licenses/{code}/4.0/'
    return {'url': 'https://images.example.org/original.jpg',
            'thumburl': 'https://images.example.org/thumb.jpg',
            'descriptionurl': 'https://museum.example.org/malea',
            'extmetadata': {key: {'value': value} for key, value in {
                'LicenseShortName': 'CC ' + code.upper() + ' 4.0', 'LicenseUrl': url,
                'Artist': 'Fotografo del museo', 'ObjectName': 'Cape Malea',
                'Attribution': 'Cape Malea, Fotografo del museo, licenza originale'}.items()}}


def http_json(value):
    result = requests.Response()
    result.status_code = 200
    result._content = json.dumps(value).encode()
    return result


@pytest.fixture
def network(tmp_path, monkeypatch):
    monkeypatch.setattr(acquire, 'ROOT', tmp_path)
    calls = {'commons': [], 'bitmap': [], 'fallback': []}
    def offline(url, params=None):
        calls['commons'].append((url, params))
        raise requests.ConnectionError('Fixture: fonte non disponibile')
    def download(url, **kwargs):
        calls['bitmap'].append((url, kwargs))
        result = requests.Response(); result.status_code = 200; result._content = bitmap()
        return result
    def fallback(request, subject, usage):
        calls['fallback'].append((subject, usage))
        return None
    monkeypatch.setattr(image_search, 'bounded_request', download)
    monkeypatch.setattr(image_search, 'find_image', fallback)
    return calls, offline


def commons_response(info, calls):
    def request(url, params=None):
        calls['commons'].append((url, params))
        assert url == 'https://commons.wikimedia.org/w/api.php'
        return http_json({'query': {'pages': {'1': {'imageinfo': [copy.deepcopy(info)]}}}})
    return request


def saved(tmp_path):
    path = tmp_path / PATH
    return path, json.loads(path.with_suffix('.metadata.json').read_text(encoding='utf-8'))


def assert_placeholder(tmp_path, manifests):
    path, info = saved(tmp_path)
    assert Image.open(path).size == (960, 1200)
    assert info['h3_placeholder'] is True
    assert info['extmetadata']['LicenseShortName']['value'] == 'CC0-1.0'
    assert len(manifests) == 1 and manifests[0]['path'] == PATH
    assert manifests[0]['sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert not path.with_suffix('.jpg.part').exists()


def test_commons_nc_is_rejected_before_bitmap_download_in_commercial_mode(tmp_path, network):
    calls, _ = network; manifests = []
    acquire._acquire_image(SUBJECT, PATH, None, True, 'commercial', manifests, commons_response(metadata(), calls))
    assert len(calls['commons']) == 1 and calls['bitmap'] == []
    assert calls['fallback'][0][1] == 'commercial'
    assert_placeholder(tmp_path, manifests)


def test_education_download_saves_original_rights_credit_and_digest(tmp_path, network):
    calls, _ = network; manifests = []; info = metadata()
    acquire._acquire_image(SUBJECT, PATH, None, True, 'education_nc', manifests, commons_response(info, calls))
    path, result = saved(tmp_path)
    assert path.read_bytes() == bitmap() and Image.open(path).size == (640, 480)
    assert result['h3_placeholder'] is False and result['h3_asset_usage'] == 'education_nc'
    assert result['descriptionurl'] == info['descriptionurl']
    assert result['extmetadata'] == info['extmetadata']
    assert calls['bitmap'] == [(info['thumburl'], {'max_bytes': 20 * 1024 * 1024})]
    assert calls['fallback'] == []
    assert manifests[0]['noncommercial'] and manifests[0]['sharealike']
    assert manifests[0]['license_url'] == info['extmetadata']['LicenseUrl']['value']
    assert manifests[0]['credit'] == info['extmetadata']['Attribution']['value']
    assert manifests[0]['sha256'] == hashlib.sha256(bitmap()).hexdigest()


@pytest.mark.parametrize('usage', ['commercial', 'education_nc'])
@pytest.mark.parametrize('code', ['by-nd', 'by-nc-nd'])
def test_nd_is_never_downloaded_even_for_education(tmp_path, network, usage, code):
    calls, _ = network; manifests = []
    acquire._acquire_image(SUBJECT, PATH, None, True, usage, manifests, commons_response(metadata(code), calls))
    assert calls['bitmap'] == []
    assert_placeholder(tmp_path, manifests)


def test_commons_failure_uses_source_confirmed_openverse_and_exports_evidence(tmp_path, monkeypatch, network):
    calls, offline = network; manifests = []; info = metadata('by-nc')
    info.pop('thumburl')
    info.update(h3_image_source='openverse', h3_openverse_id='fixture-openverse-id',
                h3_license_evidence={'url': info['descriptionurl'], 'method': 'jsonld_imageobject',
                                     'license': 'CC-BY-NC-4.0', 'page_sha256': 'f' * 64})
    def fallback(request, subject, usage):
        assert request is image_search.bounded_request and usage == 'education_nc'
        calls['fallback'].append((subject, usage))
        return copy.deepcopy(info)
    monkeypatch.setattr(image_search, 'find_image', fallback)
    acquire._acquire_image(SUBJECT, PATH, None, True, 'education_nc', manifests, offline)
    path, result = saved(tmp_path)
    assert len(calls['commons']) == 1 and len(calls['fallback']) == 1
    assert path.read_bytes() == bitmap() and result['h3_openverse_id'] == 'fixture-openverse-id'
    assert manifests[0]['license_evidence'] == info['h3_license_evidence']
    assert manifests[0]['image_source'] == 'openverse'
    assert manifests[0]['source'] == info['descriptionurl']
    assert manifests[0]['url'] == info['url'] and manifests[0]['noncommercial']


def test_cached_noncommercial_image_is_rechecked_and_replaced_for_commercial_project(tmp_path, network):
    calls, offline = network; manifests = []
    acquire._acquire_image(SUBJECT, PATH, metadata(), True, 'education_nc', manifests, offline)
    assert len(calls['bitmap']) == 1
    acquire._acquire_image(SUBJECT, PATH, None, True, 'commercial', manifests, offline)
    assert len(calls['bitmap']) == 1, 'The previous NC file must not be downloaded again or reused.'
    assert_placeholder(tmp_path, manifests)
    assert 'CC BY-NC' not in manifests[0]['license']


def test_valid_cached_image_reuses_bytes_and_rights_without_network(tmp_path, monkeypatch, network):
    _, offline = network; manifests = []
    acquire._acquire_image(SUBJECT, PATH, metadata(), True, 'education_nc', manifests, offline)
    original, original_meta = saved(tmp_path)
    original_bytes = original.read_bytes()
    def forbidden(*args, **kwargs):
        pytest.fail('A valid compatible cache must not access the network.')
    monkeypatch.setattr(image_search, 'bounded_request', forbidden)
    monkeypatch.setattr(image_search, 'find_image', forbidden)
    rebuilt = []
    acquire._acquire_image(SUBJECT, PATH, None, True, 'education_nc', rebuilt, forbidden)
    path, result = saved(tmp_path)
    assert path.read_bytes() == original_bytes and result == original_meta
    assert rebuilt == manifests


@pytest.mark.parametrize('cached', ['{"extmetadata":', '[null]', 'null'])
def test_broken_cached_metadata_recovers_with_a_valid_download(tmp_path, network, cached):
    calls, offline = network; manifests = []
    path = tmp_path / PATH; path.parent.mkdir(parents=True)
    path.write_bytes(b'old data'); path.with_suffix('.metadata.json').write_text(cached, encoding='utf-8')
    acquire._acquire_image(SUBJECT, PATH, metadata('by'), True, 'commercial', manifests, offline)
    assert path.read_bytes() == bitmap() and len(calls['bitmap']) == 1
    assert saved(tmp_path)[1]['h3_placeholder'] is False


@pytest.mark.parametrize('failure', ['html', 'size_limit', 'timeout'])
def test_invalid_bitmap_or_bounded_download_failure_retains_optional_fallback(tmp_path, monkeypatch, network, failure):
    calls, offline = network; manifests = []
    def bad_download(url, **kwargs):
        calls['bitmap'].append((url, kwargs))
        if failure == 'size_limit':
            raise ValueError('Image source response exceeds size limit')
        if failure == 'timeout':
            raise requests.Timeout('Fixture timeout')
        result = requests.Response(); result.status_code = 200; result._content = b'<html>Not an image</html>'
        return result
    monkeypatch.setattr(image_search, 'bounded_request', bad_download)
    acquire._acquire_image(SUBJECT, PATH, metadata('by'), True, 'commercial', manifests, offline)
    assert len(calls['bitmap']) == 1 and len(calls['fallback']) == 1
    assert_placeholder(tmp_path, manifests)


def test_unavailable_required_portrait_raises_a_clear_error(tmp_path, network):
    _, offline = network
    with pytest.raises(ValueError, match='licenza compatibile'):
        acquire._acquire_image(SUBJECT, PATH, None, False, 'commercial', [], offline)
    assert not (tmp_path / PATH).exists()


def test_artwork_metadata_replaces_proposed_license_and_clears_stale_placeholder(tmp_path, network):
    _, offline = network; manifests = []; info = metadata()
    acquire._acquire_image(SUBJECT, PATH, info, True, 'education_nc', manifests, offline)
    raw = {'visual_assets': [{'id': 'malea', 'path': PATH, 'title': 'Cape Malea', 'source': 'https://wrong.example.org',
                              'license': 'Public domain', 'creator': 'Autore inventato', 'placeholder': True}]}
    assert history_assets.sync_image_metadata(raw, root=tmp_path)
    asset = raw['visual_assets'][0]
    assert asset['license'] == 'CC BY-NC-SA 4.0'
    assert asset['source'] == info['descriptionurl'] and asset['creator'] == 'Fotografo del museo'
    assert asset['credit'] == info['extmetadata']['Attribution']['value']
    assert asset.get('placeholder') is False
    assert not history_assets.sync_image_metadata(raw, root=tmp_path), 'Sync must stabilize after correction.'


def test_placeholder_metadata_never_keeps_the_proposed_artwork_attribution(tmp_path, network):
    _, offline = network
    acquire._acquire_image(SUBJECT, PATH, None, True, 'commercial', [], offline)
    raw = {'visual_assets': [{'id': 'malea', 'path': PATH, 'title': 'Dipinto non trovato',
                              'license': 'CC BY-NC 4.0', 'creator': 'Autore inventato', 'credit': 'Attribuzione inventata'}]}
    assert history_assets.sync_image_metadata(raw, root=tmp_path)
    asset = raw['visual_assets'][0]
    assert asset['placeholder'] is True and asset['license'] == 'CC0-1.0'
    assert 'Riquadro generico' in asset['title']
    assert 'inventat' not in (asset['creator'] + asset['credit'])


def test_document_exports_keep_actual_nc_sharealike_conditions(tmp_path, monkeypatch, network):
    from pipeline.engine import export
    _, offline = network; info = metadata()
    acquire._acquire_image(SUBJECT, PATH, info, True, 'education_nc', [], offline)
    timeline = {'slug': 'licenze-fixture', 'title': 'Fixture didattica', 'duration': 3,
                'documentary_schema_version': 2, 'asset_usage': 'education_nc',
                'scenes': [], 'sources': [], 'editorial_notes': [], 'commanders': {},
                'visual_assets': [{'id': 'malea', 'path': PATH, 'title': 'Cape Malea', 'license': 'Public domain', 'source': ''}]}
    history_assets.sync_image_metadata(timeline, root=tmp_path)
    (tmp_path / 'build' / timeline['slug']).mkdir(parents=True)
    monkeypatch.setattr(export, 'ROOT', tmp_path)
    export.export_documents(timeline)
    for path in [tmp_path / 'credits.md', tmp_path / 'output/youtube_description.txt']:
        content = path.read_text(encoding='utf-8')
        assert 'CC-BY-NC-SA-4.0' in content
        assert 'uso non commerciale' in content and 'stesse condizioni' in content
        assert info['descriptionurl'] in content and 'Fotografo del museo' in content
        assert info['extmetadata']['LicenseUrl']['value'] in content
    assert (tmp_path / 'documentaries/licenze-fixture/credits.md').read_text(encoding='utf-8') == (tmp_path / 'credits.md').read_text(encoding='utf-8')
