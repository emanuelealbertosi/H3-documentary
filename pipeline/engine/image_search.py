"""Conservative, anonymous Openverse fallback with source-specific rights evidence.

One exact-name search, at most three source pages, no broad keyword expansion.
The source page must identify this work and its licence; a site footer is not
evidence. Unavailable or ambiguous sources retain the normal placeholder.
"""
import hashlib
import html
from html.parser import HTMLParser
import ipaddress
import json
import re
import socket
import time
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit, unquote

import requests

from .image_rights import license_policy

API = 'https://api.openverse.org/v1/images/'
MAX_PAGE_BYTES = 2 * 1024 * 1024
MAX_RESULTS = 20
MAX_SOURCE_PAGES = 3


def public_url(value):
    """Syntactic gate, also used before exposing an image URL to the downloader."""
    if not isinstance(value, str) or len(value) > 4096:
        return False
    try:
        p = urlsplit(value)
        host = (p.hostname or '').lower().rstrip('.')
        if p.scheme not in ('https', 'http') or not host or p.username or p.password:
            return False
        if p.port not in (None, 80, 443) or any(ord(c) < 33 for c in value):
            return False
        if host == 'localhost' or host.endswith(('.localhost', '.local', '.internal')):
            return False
        try:
            return ipaddress.ip_address(host).is_global
        except ValueError:
            return '.' in host
    except ValueError:
        return False


def _public_host(url):
    if not public_url(url):
        raise ValueError('Non-public image source URL')
    p = urlsplit(url)
    addresses = socket.getaddrinfo(p.hostname, p.port or (443 if p.scheme == 'https' else 80), type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError('Image source resolves to a non-public address')


def bounded_request(url, params=None, *, max_bytes=MAX_PAGE_BYTES):
    """Public GET, no credentials/retries, capped bytes/time and checked redirects."""
    if not isinstance(max_bytes, int) or not 1 <= max_bytes <= 20 * 1024 * 1024:
        raise ValueError('Invalid image response size limit')
    deadline = time.monotonic() + 35
    with requests.Session() as session:
        session.trust_env = False
        session.headers['User-Agent'] = 'H3-documentary/1.13 (licensed historical images)'
        for redirect in range(3):
            _public_host(url)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise requests.Timeout('Image source time limit exceeded')
            with session.get(url, params=params, timeout=(min(8, remaining), min(20, remaining)), stream=True, allow_redirects=False) as response:
                if response.is_redirect:
                    if redirect == 2:
                        raise requests.TooManyRedirects('Image source redirect limit exceeded')
                    url = urljoin(url, response.headers.get('Location', ''))
                    params = None
                    continue
                response.raise_for_status()
                length = response.headers.get('Content-Length')
                if length and int(length) > max_bytes:
                    raise ValueError('Image source response exceeds size limit')
                body = bytearray()
                for chunk in response.iter_content(65536):
                    body.extend(chunk)
                    if len(body) > max_bytes:
                        raise ValueError('Image source response exceeds size limit')
                    if time.monotonic() > deadline:
                        raise requests.Timeout('Image source time limit exceeded')
                response._content = bytes(body)
                response._content_consumed = True
                return response
    raise requests.TooManyRedirects('Image source redirect limit exceeded')


def _text(value):
    return html.unescape(re.sub(r'<[^>]*>', ' ', value)) if isinstance(value, str) else ''


def _normal(value):
    text = unicodedata.normalize('NFKD', _text(value)).casefold()
    return ' '.join(re.sub(r'[^\w]+', ' ', ''.join(c for c in text if not unicodedata.combining(c))).replace('_', ' ').split())


def _named(title, name, kind):
    title, name = _normal(title), _normal(name)
    if not name or len(name) < 3:
        return False
    # A single-word person (e.g. Napoleon) must not select Napoleon III.
    if kind == 'person' and len(name.split()) == 1:
        return title == name
    return (' ' + name + ' ') in (' ' + title + ' ')


class _RightsPage(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.head = False
        self.json_script = None
        self.structured = []
        self.meta = {}
        self.licenses = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'head':
            self.head = True
        if tag == 'script' and attrs.get('type', '').lower() == 'application/ld+json':
            self.json_script = []
        if self.head and tag == 'meta':
            self.meta[attrs.get('property', attrs.get('name', '')).lower()] = attrs.get('content', '')
        if self.head and tag == 'link' and 'license' in attrs.get('rel', '').lower().split():
            self.licenses.append(attrs.get('href', ''))

    def handle_data(self, data):
        if self.json_script is not None:
            self.json_script.append(data)

    def handle_endtag(self, tag):
        if tag == 'head':
            self.head = False
        if tag == 'script' and self.json_script is not None:
            try:
                self.structured.append(json.loads(''.join(self.json_script)))
            except (ValueError, RecursionError):
                pass
            self.json_script = None


def _objects(value, depth=0):
    if depth > 12:
        return
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _objects(child, depth + 1)
    elif isinstance(value, list):
        for child in value[:100]:
            yield from _objects(child, depth + 1)


def _evidence(response, row, policy, usage):
    if len(response.content) > MAX_PAGE_BYTES:
        return None
    page = _RightsPage()
    page.feed(response.text)
    found = []
    for tree in page.structured:
        for item in _objects(tree):
            types = item.get('@type', [])
            types = [types] if isinstance(types, str) else types
            if not isinstance(types, list) or not set(types).intersection({'ImageObject', 'Photograph', 'https://schema.org/ImageObject', 'http://schema.org/ImageObject'}):
                continue
            # Bind a work-specific license to the returned bitmap and its title.
            image_url = item.get('contentUrl', item.get('url'))
            if image_url != row['url'] or _normal(item.get('name', '')) != _normal(row['title']):
                continue
            link = item.get('license')
            if isinstance(link, dict):
                link = link.get('@id', link.get('url'))
            if isinstance(link, str):
                found.append((link, 'jsonld_imageobject'))
    # Head-only rel=license is accepted only when OpenGraph identifies this
    # exact bitmap and title. A footer's general CC license is never consulted.
    if page.meta.get('og:image') == row['url'] and _normal(page.meta.get('og:title')) == _normal(row['title']):
        found.extend((urljoin(row['foreign_landing_url'], link), 'head_rel_license') for link in page.licenses)
    matching = []
    for link, method in found:
        original = license_policy('', usage=usage, license_url=link)
        if not original['allowed'] or original['id'] != policy['id'] or original['license_url'] != policy['license_url']:
            return None
        matching.append((link, method))
    if not matching:
        return None
    link, method = matching[0]
    return {'url': response.url or row['foreign_landing_url'], 'method': method,
            'license': policy['id'], 'license_url': link,
            'checked_at': datetime.now(timezone.utc).isoformat(),
            'page_sha256': hashlib.sha256(response.content).hexdigest()}


def find_image(request, subject, usage='commercial'):
    """Return Commons-like imageinfo, or None; injected request must be bounded."""
    if not isinstance(subject, dict) or subject.get('kind', 'person') not in ('person', 'place', 'topic'):
        return None
    kind = subject.get('kind', 'person')
    name = subject.get('wikipedia_page') or subject.get('name', '')
    if not isinstance(name, str) or len(name) > 160:
        return None
    if name.startswith(('https://', 'http://')):
        p = urlsplit(name)
        if not (p.hostname or '').endswith('.wikipedia.org') or not p.path.startswith('/wiki/'):
            return None
        name = unquote(p.path[6:])
    name = _normal(name)
    if len(name) < 3:
        return None
    licenses = 'cc0,pdm,by,by-sa' + (',by-nc,by-nc-sa' if usage == 'education_nc' else '')
    try:
        response = request(API, {'q': '"' + name + '"', 'license': licenses, 'page_size': MAX_RESULTS, 'mature': 'false'})
        response.raise_for_status()
        if len(response.content) > MAX_PAGE_BYTES:
            return None
        rows = response.json().get('results', [])
        if not isinstance(rows, list):
            return None
    except (requests.RequestException, OSError, ValueError, TypeError, AttributeError):
        return None
    candidates = []
    for row in rows[:MAX_RESULTS]:
        if not isinstance(row, dict) or not _named(row.get('title'), name, kind):
            continue
        if row.get('mature') or row.get('removed_from_source') or row.get('watermarked'):
            continue
        if not public_url(row.get('url')) or not public_url(row.get('foreign_landing_url')):
            continue
        code = row.get('license', '')
        if code not in ('cc0', 'pdm', 'by', 'by-sa', 'by-nc', 'by-nc-sa'):
            continue
        version = str(row.get('license_version') or '')
        label = ('Public domain' if code == 'pdm' else 'CC0 ' + version if code == 'cc0' else 'CC ' + code.upper() + ' ' + version).strip()
        policy = license_policy(label, usage=usage, license_url=row.get('license_url', ''))
        if not policy['allowed'] or not row.get('creator') or not row.get('id'):
            continue
        candidates.append((row, policy, label))
    # Prefer less restrictive alternatives when both depict the same subject.
    candidates.sort(key=lambda x: (x[1]['noncommercial'], x[1]['sharealike']))
    for row, policy, label in candidates[:MAX_SOURCE_PAGES]:
        try:
            original = request(row['foreign_landing_url'])
            original.raise_for_status()
            evidence = _evidence(original, row, policy, usage)
            if not evidence:
                continue
        except (requests.RequestException, OSError, ValueError, TypeError, AttributeError, RecursionError):
            continue
        return {'url': row['url'], 'descriptionurl': row['foreign_landing_url'],
                'h3_image_source': 'openverse', 'h3_openverse_id': row['id'],
                'h3_openverse_provider': row.get('source', row.get('provider', '')),
                'h3_openverse_license': {k: row.get(k) for k in ('license', 'license_version', 'license_url', 'attribution', 'creator', 'creator_url', 'last_synced_with_source')},
                'h3_license_evidence': evidence, 'h3_subject_kind': kind, 'h3_placeholder': False,
                'extmetadata': {key: {'value': value} for key, value in {
                    'LicenseShortName': label, 'LicenseUrl': policy['license_url'],
                    'Artist': _text(row['creator']), 'ObjectName': _text(row['title']),
                    'Attribution': _text(row.get('attribution', ''))}.items()}}
    return None
