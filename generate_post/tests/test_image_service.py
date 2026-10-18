import base64
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import requests

from generate_post.adapters.api import cloudflare_image_service
from generate_post.adapters.api.cloudflare_image_service import CloudflareImageService
from generate_post.tests.helpers import ENV, http_response

PNG = b"\x89PNG" + b"0" * 2000


@mock.patch("generate_post.utils.retry_decorator.time.sleep")
class CloudflareImageServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        patcher = mock.patch.object(cloudflare_image_service, "ASSETS_DIR", Path(self.tmp.name))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)
        self.service = CloudflareImageService(env_config=ENV)
        self.requests = []

    def _serve(self, responses):
        def post(url, **kwargs):
            prepared = requests.Request(
                "POST", url, headers=kwargs["headers"], files=kwargs.get("files"), json=kwargs.get("json")
            ).prepare()
            self.requests.append((url.rsplit("@cf/", 1)[1], prepared))
            return responses[len(self.requests) - 1]

        self.service._session.post = post

    def test_flux2_multipart_then_fallback(self, _sleep):
        ok = http_response(200, {"success": True, "result": {"image": base64.b64encode(PNG).decode()}})
        self._serve([http_response(500, {"errors": ["x"]}), http_response(500, {"errors": ["x"]}), ok])

        path = self.service.generate_image("a crab guarding memory blocks")

        model, prepared = self.requests[0]
        self.assertEqual(model, "black-forest-labs/flux-2-klein-9b")
        self.assertTrue(prepared.headers["Content-Type"].startswith("multipart/form-data"))
        body = prepared.body.decode()
        self.assertIn('name="width"\r\n\r\n1280', body)
        self.assertIn('name="height"\r\n\r\n672', body)
        self.assertIn("a crab guarding memory blocks", body)
        self.assertNotIn("filename=", body)
        self.assertEqual(self.requests[2][0], "black-forest-labs/flux-2-klein-4b")
        self.assertEqual((Path(self.tmp.name) / path.rsplit("/", 1)[1]).read_bytes(), PNG)

    def test_returns_none_when_every_model_fails(self, _sleep):
        self._serve([http_response(503, {"errors": ["x"]})] * 8)
        self.assertIsNone(self.service.generate_image("algo"))
        self.assertEqual(len(self.requests), 8)


if __name__ == "__main__":
    unittest.main()
