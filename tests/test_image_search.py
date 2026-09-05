import json

import pytest
import requests

from pipeline.engine.image_search import API, MAX_PAGE_BYTES, bounded_request, find_image, public_url


def response(value, url, *, status=200):
    r = requests.Response()
    r.status_code = status
    r.url = url
    r.encoding = 'utf-8'
    r._content = (json.dumps(value) if isinstance(value, dict) else value).encode()
    return r


def candidate(**changes):
    row = dict(id='example-id', title='Cape Malea', license='by-nc', license_version='4.0',
               license_url='https://creativecommons.org/licenses/by-nc/4.0/',
               creator='Museum photographer', attribution='Cape Malea, Museum photographer, CC BY-NC 4.0',
               url='https://images.example.org/malea.jpg', foreign_landing_url='https://museum.example.org/collection/malea', source='museum')
    row.update(changes)
    return row


def page(row, **changes):
    obj = {'@context': 'https://schema.org', '@type': 'ImageObject', 'name': row['title'],
           'contentUrl': row['url'], 'license': row['license_url']}
    obj.update(changes)
    return '<html><head><script type="application/ld+json">' + json.dumps(obj) + '</script></head></html>'


def fake_request(rows, pages, calls):
    def request(url, params=None):
        calls.append((url, params))
        if url == API:
            return response({'results': rows}, url)
        value = pages[url]
        if isinstance(value, Exception):
            raise value
        return response(value, url)
    return request


def test_noncommercial_source_evidence_and_attribution_are_preserved():
    row = candidate(); calls = []
    result = find_image(fake_request([row], {row['foreign_landing_url']: page(row)}, calls), {'name': 'Capo Malea', 'wikipedia_page': 'Cape Malea', 'kind': 'place'}, 'education_nc')
    assert len(calls) == 2 and calls[0][1]['q'] == '"cape malea"'
    assert 'by-nc' in calls[0][1]['license']
    assert result['descriptionurl'] == row['foreign_landing_url']
    assert result['extmetadata']['Attribution']['value'] == row['attribution']
    assert result['h3_license_evidence']['method'] == 'jsonld_imageobject'
    assert result['h3_license_evidence']['license'] == 'CC-BY-NC-4.0'
    assert result['h3_openverse_license']['license_url'] == row['license_url']
    assert result['url'] == row['url'] and 'thumburl' not in result


def test_commercial_filter_rejects_nc_even_if_api_ignores_search_filter():
    row = candidate(); calls = []
    assert find_image(fake_request([row], {}, calls), {'name': 'Cape Malea', 'kind': 'place'}) is None
    assert len(calls) == 1 and 'by-nc' not in calls[0][1]['license']


@pytest.mark.parametrize('change', [
    {'license': 'by-nd'}, {'license': 'by-nc-nd'}, {'license': 'unknown'},
    {'title': 'Cape Matapan'}, {'creator': ''}, {'url': 'file:///C:/secret'},
    {'url': 'http://127.0.0.1/picture'}, {'foreign_landing_url': 'http://localhost/image'},
    {'mature': True}, {'removed_from_source': True}, {'watermarked': True},
])
def test_unfit_candidates_never_reach_source_page(change):
    calls = []
    assert find_image(fake_request([candidate(**change)], {}, calls), {'name': 'Cape Malea', 'kind': 'place'}, 'education_nc') is None
    assert len(calls) == 1


@pytest.mark.parametrize('original', ['mismatch', 'footer', 'other_work', 'unavailable'])
def test_license_is_bound_to_original_work_not_catalog_or_site_footer(original):
    row = candidate(); calls = []
    value = {'mismatch': page(row, license='https://creativecommons.org/licenses/by-nc-nd/4.0/'),
             'footer': '<html><footer><a rel="license" href="' + row['license_url'] + '">CC</a></footer></html>',
             'other_work': page(row, contentUrl='https://images.example.org/other.jpg'),
             'unavailable': requests.HTTPError('403')}[original]
    assert find_image(fake_request([row], {row['foreign_landing_url']: value}, calls), {'name': 'Cape Malea', 'kind': 'place'}, 'education_nc') is None


def test_search_and_verification_are_bounded_and_do_not_expand_names():
    rows = [candidate(id=str(i), foreign_landing_url=f'https://museum.example.org/{i}') for i in range(30)]
    calls = []
    assert find_image(fake_request(rows, {row['foreign_landing_url']: 'No license' for row in rows}, calls), {'name': 'Cape Malea', 'kind': 'place'}, 'education_nc') is None
    assert len(calls) == 4


def test_single_name_person_does_not_select_different_person():
    calls = []
    assert find_image(fake_request([candidate(title='Napoleon III')], {}, calls), {'name': 'Napoleon', 'kind': 'person'}, 'education_nc') is None
    assert len(calls) == 1


def test_source_head_license_requires_matching_image_and_title():
    row = candidate(license='by', license_url='https://creativecommons.org/licenses/by/4.0/'); calls = []
    original = f'<html><head><meta property="og:title" content="{row["title"]}"><meta property="og:image" content="{row["url"]}"><link rel="license" href="{row["license_url"]}"></head></html>'
    result = find_image(fake_request([row], {row['foreign_landing_url']: original}, calls), {'name': 'Cape Malea', 'kind': 'place'})
    assert result['h3_license_evidence']['method'] == 'head_rel_license'


def test_http_failures_malformed_data_and_oversize_pages_remain_optional():
    for result in [response('no json', API), response({}, API, status=429), response('x' * (MAX_PAGE_BYTES + 1), API)]:
        assert find_image(lambda *args: result, {'name': 'Cape Malea', 'kind': 'place'}) is None
    def fail(*args):
        raise requests.Timeout()
    assert find_image(fail, {'name': 'Cape Malea', 'kind': 'place'}) is None


def test_public_url_and_dns_guard_reject_private_networks(monkeypatch):
    from pipeline.engine import image_search
    for url in ['ftp://example.org/x', 'http://localhost/x', 'https://192.168.1.2/x', 'http://[::1]/x', 'https://user:pass@example.org/x', 'https://example.org:8775/x']:
        assert not public_url(url)
    monkeypatch.setattr(image_search.socket, 'getaddrinfo', lambda *a, **kw: [(None, None, None, None, ('10.1.1.1', 443))])
    with pytest.raises(ValueError, match='non-public'):
        bounded_request('https://images.example.org/x')


def test_bounded_downloader_limits_bytes_and_redirects(monkeypatch):
    from pipeline.engine import image_search
    monkeypatch.setattr(image_search, '_public_host', lambda url: None)
    class StreamingResponse:
        is_redirect = False
        headers = {}
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def raise_for_status(self): pass
        def iter_content(self, size): yield b'x' * 12
    class Session:
        headers = {}
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def get(self, *args, **kwargs):
            assert kwargs['stream'] and not kwargs['allow_redirects']
            assert kwargs['timeout'][1] <= 20
            return StreamingResponse()
    monkeypatch.setattr(image_search.requests, 'Session', Session)
    with pytest.raises(ValueError, match='size limit'):
        bounded_request('https://example.org/image', max_bytes=10)
    StreamingResponse.is_redirect = True
    StreamingResponse.headers = {'Location': 'https://example.org/image'}
    with pytest.raises(requests.TooManyRedirects):
        bounded_request('https://example.org/image')
