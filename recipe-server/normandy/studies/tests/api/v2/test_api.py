from urllib.parse import urlparse

import pytest
from pathlib import Path

from django.conf import settings

from normandy.base.tests import Whatever
from normandy.studies.models import Extension
from normandy.studies.tests import ExtensionFactory
from normandy.studies.api.v2.fields import ExtensionFileField


@pytest.mark.django_db
class TestExtensionAPI(object):
    def test_it_works(self, api_client):
        res = api_client.get('/api/v2/extension/')
        assert res.status_code == 200
        assert res.data['results'] == []

    def test_it_serves_extensions(self, api_client):
        extension = ExtensionFactory(
            name='foo',
        )

        res = api_client.get('/api/v2/extension/')
        assert res.status_code == 200
        assert res.data['results'] == [
            {
                'id': extension.id,
                'name': 'foo',
                'xpi': Whatever(),
            }
        ]

    def test_list_view_includes_cache_headers(self, api_client):
        res = api_client.get('/api/v2/extension/')
        assert res.status_code == 200
        # It isn't important to assert a particular value for max-age
        assert 'max-age=' in res['Cache-Control']
        assert 'public' in res['Cache-Control']

    def test_detail_view_includes_cache_headers(self, api_client):
        extension = ExtensionFactory()
        res = api_client.get('/api/v2/extension/{id}/'.format(id=extension.id))
        assert res.status_code == 200
        # It isn't important to assert a particular value for max-age
        assert 'max-age=' in res['Cache-Control']
        assert 'public' in res['Cache-Control']

    def test_list_sets_no_cookies(self, api_client):
        res = api_client.get('/api/v2/extension/')
        assert res.status_code == 200
        assert 'Cookies' not in res

    def test_detail_sets_no_cookies(self, api_client):
        extension = ExtensionFactory()
        res = api_client.get('/api/v2/extension/{id}/'.format(id=extension.id))
        assert res.status_code == 200
        assert res.client.cookies == {}

    def test_filtering_by_name(self, api_client):
        matching_extension = ExtensionFactory()
        ExtensionFactory()  # Generate another extension that will not match

        res = api_client.get(f'/api/v2/extension/?text={matching_extension.name}')
        assert res.status_code == 200
        assert [ext['name'] for ext in res.data['results']] == [matching_extension.name]

    def test_filtering_by_xpi(self, api_client):
        matching_extension = ExtensionFactory()
        ExtensionFactory()  # Generate another extension that will not match

        res = api_client.get(f'/api/v2/extension/?text={matching_extension.xpi}')
        assert res.status_code == 200
        expected_path = matching_extension.xpi.url
        assert [urlparse(ext['xpi']).path for ext in res.data['results']] == [expected_path]

    def _upload_extension(self, api_client, path):
        with open(path, 'rb') as f:
            res = api_client.post('/api/v2/extension/', {
                'name': 'test extension',
                'xpi': f,
            }, format='multipart')
        return res

    def test_upload_works_webext(self, api_client):
        path = Path(settings.BASE_DIR) / 'normandy/studies/tests/data/webext-signed.xpi'
        res = self._upload_extension(api_client, path)
        assert res.status_code == 201  # created
        Extension.objects.filter(id=res.data['id']).exists()

    def test_upload_works_legacy(self, api_client):
        path = './normandy/studies/tests/data/legacy-signed.xpi'
        res = self._upload_extension(api_client, path)
        assert res.status_code == 201  # created
        Extension.objects.filter(id=res.data['id']).exists()

    def test_uploads_must_be_zips(self, api_client):
        path = './normandy/studies/tests/data/not-an-addon.txt'
        res = self._upload_extension(api_client, path)
        assert res.status_code == 400  # Client error
        assert res.data == {'xpi': [ExtensionFileField.default_error_messages['not_a_zip']]}

    def test_uploads_must_be_signed_webext(self, api_client):
        path = './normandy/studies/tests/data/webext-unsigned.xpi'
        res = self._upload_extension(api_client, path)
        assert res.status_code == 400  # Client error
        assert res.data == {'xpi': [ExtensionFileField.default_error_messages['not_signed']]}

    def test_uploads_must_be_signed_legacy(self, api_client):
        path = './normandy/studies/tests/data/legacy-unsigned.xpi'
        res = self._upload_extension(api_client, path)
        assert res.status_code == 400  # Client error
        assert res.data == {'xpi': [ExtensionFileField.default_error_messages['not_signed']]}

    def test_uploaded_webexts_must_have_id(self, api_client):
        # NB: This is a fragile test. It uses a unsigned webext, and
        # so it relies on the ID check happening before the signing
        # check, so that the error comes from the former.
        path = './normandy/studies/tests/data/webext-no-id-unsigned.xpi'
        res = self._upload_extension(api_client, path)
        assert res.status_code == 400  # Client error
        assert res.data == {'xpi': [ExtensionFileField.default_error_messages['no_id']]}
