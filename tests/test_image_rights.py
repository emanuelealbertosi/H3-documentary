import pytest
from pipeline.engine.image_rights import license_policy,metadata_policy,manual_allowed,usage_for

@pytest.mark.parametrize('label',['Public domain','CC0-1.0','CC BY 4.0','CC-BY-SA-3.0','Creative Commons Attribution-ShareAlike 4.0 International','Attribution-ShareAlike 4.0'])
def test_commercial_compatible_licenses(label):
    assert license_policy(label)['allowed']

@pytest.mark.parametrize('label',['CC BY-NC 4.0','CC-BY-NC-SA-3.0','Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International'])
def test_noncommercial_is_a_real_gate_not_a_substring(label):
    assert not license_policy(label)['allowed']
    assert license_policy(label,'education_nc')['allowed']

@pytest.mark.parametrize('label',['CC BY-ND 4.0','CC BY-NC-ND 3.0','Unknown','Not public domain','fair use','All rights reserved'])
def test_education_does_not_permit_every_image(label):
    assert not license_policy(label,'education_nc')['allowed']

def test_conflicting_metadata_does_not_downgrade_nc_to_by():
    assert not license_policy('CC BY-NC 4.0',license_url='https://creativecommons.org/licenses/by/4.0/')['allowed']
    assert not license_policy('All rights reserved','education_nc','https://creativecommons.org/licenses/by/4.0/')['allowed']
    assert license_policy('CC BY-SA 3.0',license_url='https://creativecommons.org/licenses/by-sa/3.0/de/')['license_url'].endswith('/de/')

def test_manual_upload_is_explicit_but_known_restrictions_apply():
    assert manual_allowed({'rights':'Fotografia mia'})
    assert manual_allowed({'rights':''})
    assert not manual_allowed({'rights':'CC BY-NC 4.0'})
    assert manual_allowed({'rights':'CC BY-NC 4.0'},'education_nc')
    assert not manual_allowed({'rights':'CC BY-ND 4.0'},'education_nc')
    assert not manual_allowed({'rights':'CC-BY-NC'})

def test_frozen_usage_and_metadata_are_independent_from_admin_changes():
    assert usage_for({})=='commercial'
    assert usage_for({'asset_usage':'education_nc'})=='education_nc'
    assert usage_for({'asset_usage':'commercial','metadata':{'boundary_usage':'education_nc'}})=='commercial'
    info={'extmetadata':{'LicenseShortName':{'value':'CC BY-NC-SA 4.0'}}}
    assert metadata_policy(info,'education_nc')['allowed'] and not metadata_policy(info)['allowed']


@pytest.mark.parametrize('label,url',[
    ('CC BY-SA','https://creativecommons.org/licenses/by/4.0/'),
    ('CC BY-NC-SA','https://creativecommons.org/licenses/by-nc/4.0/'),
    ('Attribution Share Alike','https://creativecommons.org/licenses/by/4.0/'),
    ('CC BY-ND','https://creativecommons.org/licenses/by/4.0/'),
])
def test_versionless_restrictions_are_not_dropped_by_a_conflicting_url(label,url):
    result=license_policy(label,'education_nc',url)
    assert not result['allowed'] and result['conflict']


def test_matching_url_supplies_version_without_losing_sharealike():
    result=license_policy('CC BY-NC-SA','education_nc','https://creativecommons.org/licenses/by-nc-sa/4.0/')
    assert result['allowed'] and result['noncommercial'] and result['sharealike']
    assert not license_policy('CC BY-SA')['allowed']


@pytest.mark.parametrize('label',[
    'CC BY 4.0; non-commercial use only','CC BY 4.0 - no-derivatives',
    'CC BY 4.0; NC','CC BY 4.0; share-alike','CC0-1.0; no derivatives',
    'CC BY-SA 4.0; not for commercial use',
])
def test_restrictive_suffixes_do_not_create_a_permissive_license(label):
    for usage in ('commercial','education_nc'):
        result=license_policy(label,usage)
        assert not result['allowed'] and result['conflict']
        assert not manual_allowed({'rights':label},usage)


@pytest.mark.parametrize('url',[
    'https://creativecommons.org/publicdomain/zero/1.0evil',
    'https://creativecommons.org/publicdomain/mark/1.0evil',
    'https://creativecommons.org/publicdomain/zero/1.0/unverified',
    'https://creativecommons.org/publicdomain/mark/1.0/deed.en/extra',
])
def test_public_domain_urls_require_an_exact_version_path(url):
    assert not license_policy('',license_url=url)['allowed']


@pytest.mark.parametrize('path',['zero/1.0/','mark/1.0/','zero/1.0/legalcode','mark/1.0/deed.it','zero/1.0/deed.en'])
def test_public_domain_canonical_and_localized_urls_remain_supported(path):
    assert license_policy('',license_url='https://creativecommons.org/publicdomain/'+path)['allowed']


@pytest.mark.parametrize('info',[
    None,[],42,{'extmetadata':[]},{'extmetadata':None},
    {'extmetadata':{'LicenseShortName':'CC0-1.0'}},
    {'extmetadata':{'LicenseShortName':{'value':['CC0-1.0']}}},
    {'extmetadata':{'LicenseShortName':{'value':'CC0-1.0'},'LicenseUrl':None}},
    {'h3_user_replacement':True,'extmetadata':'corrupt'},
])
def test_malformed_metadata_is_excluded_without_raising(info):
    result=metadata_policy(info,'education_nc')
    assert not result['allowed'] and result['id']=='unknown'


def test_explicit_upload_with_unspecified_rights_remains_accepted():
    assert metadata_policy({'h3_user_replacement':True,'extmetadata':{}})['allowed']


def test_battle_portrait_metadata_keeps_nc_sa_and_author_in_exported_credits(tmp_path):
    import json
    from pipeline.engine.image_rights import image_license_credits,image_license_notice
    folder=tmp_path/'assets/portraits';folder.mkdir(parents=True)
    metadata={'descriptionurl':'https://example.org/portrait','extmetadata':{
        'ObjectName':{'value':'Ritratto di prova'},'Artist':{'value':'Autrice della fotografia'},
        'Attribution':{'value':''},'LicenseShortName':{'value':'CC BY-NC-SA 4.0'},
        'LicenseUrl':{'value':'https://creativecommons.org/licenses/by-nc-sa/4.0/'}}}
    (folder/'portrait.metadata.json').write_text(json.dumps(metadata),encoding='utf-8')
    (folder/'broken.metadata.json').write_text('{',encoding='utf-8')
    (folder/'invalid.metadata.json').write_text('[]',encoding='utf-8')
    (folder/'bad-source.metadata.json').write_text(json.dumps({**metadata,'descriptionurl':[]}),encoding='utf-8')
    timeline={'asset_usage':'education_nc','commanders':{
        'p':{'name':'Persona','portrait':'assets/portraits/portrait.jpg'},
        'broken':{'portrait':'assets/portraits/broken.jpg'},
        'invalid':{'portrait':'assets/portraits/invalid.jpg'},
        'bad-source':{'portrait':'assets/portraits/bad-source.jpg'}}}
    rows=image_license_credits(timeline,root=tmp_path)
    assert len(rows)==1 and rows[0]['noncommercial'] and rows[0]['sharealike']
    assert rows[0]['credit']=='Autrice della fotografia' and rows[0]['title']=='Ritratto di prova'
    notice='\n'.join(image_license_notice(timeline,root=tmp_path))
    assert 'Autrice della fotografia' in notice and 'uso non commerciale' in notice and 'stesse condizioni' in notice
    assert image_license_credits(timeline)==[]
