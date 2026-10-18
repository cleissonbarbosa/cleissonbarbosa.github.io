import unittest
from unittest import mock

import requests

from generate_post.adapters.api.cloudflare_text_generator import CloudflareTextGenerator
from generate_post.adapters.api.fallback_text_generator import FallbackTextGenerator
from generate_post.adapters.api.gemini_text_generator import GeminiTextGenerator
from generate_post.config.env_config import EnvConfig
from generate_post.tests.helpers import ENV, http_response

NO_SLEEP = mock.patch("generate_post.utils.retry_decorator.time.sleep")


def gemini_ok(text: str, finish: str = "STOP") -> dict:
    return {
        "candidates": [
            {
                "finishReason": finish,
                "content": {"parts": [{"text": "raciocínio", "thought": True}, {"text": text}]},
            }
        ]
    }


@NO_SLEEP
class GeminiTextGeneratorTest(unittest.TestCase):
    def setUp(self):
        self.gen = GeminiTextGenerator(env_config=ENV, models=("m1", "m2", "m3", "m4"))
        self.calls = []

    def _serve(self, *responses):
        def post(url, **kwargs):
            self.calls.append((url.rsplit("/", 1)[1], kwargs))
            response = responses[len(self.calls) - 1]
            if isinstance(response, Exception):
                raise response
            return response

        self.gen._session.post = post

    def test_falls_back_on_unavailable_truncated_timeout_and_bad_format(self, _sleep):
        self._serve(
            http_response(404, {"error": "no longer available"}),  # m1: sem retry
            http_response(200, gemini_ok("cortado", "MAX_TOKENS")),  # m2: truncou, não repete
            requests.Timeout("lento"),  # m3: timeout não repete
            http_response(200, gemini_ok("ok")),  # m4
        )

        result = self.gen.generate("sys", "prompt", parse=str.upper)

        self.assertEqual(result, "OK")  # partes de thinking ficam de fora
        self.assertEqual(
            [c[0] for c in self.calls],
            ["m1:generateContent", "m2:generateContent", "m3:generateContent", "m4:generateContent"],
        )
        config = self.calls[0][1]["json"]["generationConfig"]
        self.assertEqual(config, {"responseMimeType": "application/json", "maxOutputTokens": 32768})

    def test_parse_error_moves_to_next_model(self, _sleep):
        self._serve(http_response(200, gemini_ok("lixo")), http_response(200, gemini_ok("bom")))

        def parse(text):
            if text == "lixo":
                raise ValueError("formato errado")
            return text

        self.assertEqual(self.gen.generate("sys", "prompt", parse), "bom")
        self.assertEqual(len(self.calls), 2)


@NO_SLEEP
class CloudflareTextGeneratorTest(unittest.TestCase):
    def test_openai_compatible_call_retry_and_truncation_fallback(self, _sleep):
        gen = CloudflareTextGenerator(env_config=ENV, models=("@cf/a", "@cf/b"))
        calls = []
        responses = [
            http_response(503, {"errors": ["ocupado"]}),
            http_response(200, {"choices": [{"finish_reason": "length", "message": {"content": "cortado"}}]}),
            http_response(200, {"choices": [{"finish_reason": "stop", "message": {"content": "texto"}}]}),
        ]

        def post(url, **kwargs):
            calls.append((url, kwargs["json"]))
            return responses[len(calls) - 1]

        gen._session.post = post
        self.assertEqual(gen.generate("sys", "prompt", parse=lambda t: t), "texto")
        self.assertTrue(calls[0][0].endswith("/accounts/acc/ai/v1/chat/completions"))
        self.assertEqual([c[1]["model"] for c in calls], ["@cf/a", "@cf/a", "@cf/b"])
        self.assertEqual(calls[0][1]["messages"][0], {"role": "system", "content": "sys"})


class FallbackTextGeneratorTest(unittest.TestCase):
    def _provider(self, name, configured=True, result=None, error=None):
        provider = mock.Mock()
        provider.name = name
        provider.is_configured.return_value = configured
        provider.generate.side_effect = error or (lambda s, p, parse: parse(result))
        return provider

    def test_skips_unconfigured_and_failed_providers(self):
        offline = self._provider("sem-chave", configured=False)
        broken = self._provider("quebrado", error=RuntimeError("caiu"))
        working = self._provider("ok", result="texto")

        result = FallbackTextGenerator([offline, broken, working]).generate("s", "p", str.upper)

        self.assertEqual(result, "TEXTO")
        offline.generate.assert_not_called()

    def test_error_when_nothing_configured(self):
        gen = FallbackTextGenerator([GeminiTextGenerator(env_config=EnvConfig(None, None, None, None))])
        with self.assertRaises(RuntimeError):
            gen.generate("s", "p", str)


if __name__ == "__main__":
    unittest.main()
