import json
import urllib.error

import pytest

import provider
from provider import ProviderError, chat, mask_private, parse_json, validate_model


class FakeResponse:
    def __init__(self, payload):
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self, n=None):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _opener_with(behavior):
    class FakeOpener:
        def open(self, req, timeout=None):
            return behavior(req)
    return FakeOpener()


def test_mask_private_redacts_tokens():
    text = "Authorization: Bearer sk-abcd1234, also sk-xyz.987"
    masked = mask_private(text)
    assert "sk-abcd1234" not in masked and "sk-xyz.987" not in masked
    assert "Bearer ***" in masked and "sk-***" in masked
    assert mask_private(None) == ""


def test_parse_json_strips_fence_and_prose():
    fenced = "```json\n{\"winner\": \"A\", \"reason\": \"ok\", \"scores\": {\"A\": 1, \"B\": 2}}\n```"
    assert parse_json(fenced)["winner"] == "A"
    prose = "Here is the verdict: {\"winner\": \"tie\"} thanks"
    assert parse_json(prose)["winner"] == "tie"


def test_parse_json_rejects_invalid_inputs():
    with pytest.raises(ValueError):
        parse_json("no json here")
    with pytest.raises(ValueError):
        parse_json("[1, 2, 3]")
    with pytest.raises(ValueError):
        parse_json("{broken")


def test_validate_model_rejects_bad_specs():
    with pytest.raises(ValueError):
        validate_model({"name": "x", "model": "m", "base_url": "https://example.com/v1",
                        "api_key": "x"})
    with pytest.raises(ValueError):
        validate_model({"name": "x", "model": "m", "base_url": "http://example.com/v1"})
    with pytest.raises(ValueError):
        validate_model({"name": "x", "base_url": "https://example.com/v1"})


def test_retry_succeeds_after_transient_429(monkeypatch):
    calls = {"n": 0}

    def behavior(req):
        calls["n"] += 1
        if calls["n"] == 1:
            raise urllib.error.HTTPError(req.full_url, 429, "Too many", {}, None)
        return FakeResponse({"choices": [{"message": {"content": "hello"},
                                          "finish_reason": "stop"}],
                             "usage": {"total_tokens": 5}})

    monkeypatch.setattr(provider.urllib.request, "build_opener",
                        lambda *a: _opener_with(behavior))
    out = chat({"name": "x", "model": "m", "base_url": "https://example.com/v1"},
               [{"role": "user", "content": "hi"}], retries=2)
    assert out["text"] == "hello"
    assert calls["n"] == 2


def test_error_message_never_leaks_key(monkeypatch):
    monkeypatch.setenv("PROV_KEY", "super-secret-value")

    def behavior(req):
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, None)

    monkeypatch.setattr(provider.urllib.request, "build_opener",
                        lambda *a: _opener_with(behavior))
    spec = {"name": "x", "model": "m", "base_url": "https://example.com/v1",
            "api_key_env": "PROV_KEY"}
    with pytest.raises(ProviderError) as exc:
        chat(spec, [{"role": "user", "content": "hi"}], retries=0)
    assert "super-secret-value" not in str(exc.value)


def test_network_failure_raises_provider_error(monkeypatch):
    def behavior(req):
        raise urllib.error.URLError("dns failure")

    monkeypatch.setattr(provider.urllib.request, "build_opener",
                        lambda *a: _opener_with(behavior))
    with pytest.raises(ProviderError):
        chat({"name": "x", "model": "m", "base_url": "https://example.com/v1"},
             [{"role": "user", "content": "hi"}], retries=0)


def test_empty_content_is_rejected(monkeypatch):
    monkeypatch.setattr(provider.urllib.request, "build_opener",
                        lambda *a: _opener_with(
                            lambda req: FakeResponse({"choices": [
                                {"message": {"content": "   "}, "finish_reason": "stop"}]})))
    with pytest.raises(ProviderError):
        chat({"name": "x", "model": "m", "base_url": "https://example.com/v1"},
             [{"role": "user", "content": "hi"}])


def test_retry_after_header_controls_backoff(monkeypatch):
    sleeps = []
    monkeypatch.setattr(provider.time, "sleep", lambda s: sleeps.append(s))
    calls = {"n": 0}

    def behavior(req):
        calls["n"] += 1
        if calls["n"] == 1:
            raise urllib.error.HTTPError(
                req.full_url, 429, "Too many", {"Retry-After": "2"}, None)
        return FakeResponse({"choices": [{"message": {"content": "ok"},
                                          "finish_reason": "stop"}]})

    monkeypatch.setattr(provider.urllib.request, "build_opener",
                        lambda *a: _opener_with(behavior))
    chat({"name": "x", "model": "m", "base_url": "https://example.com/v1"}, [
        {"role": "user", "content": "hi"}])
    assert calls["n"] == 2
    assert sleeps and abs(sleeps[0] - 2.0) < 1e-6


def test_oversized_messages_rejected_before_request(monkeypatch):
    opened = {"n": 0}
    monkeypatch.setattr(provider.urllib.request, "build_opener",
                        lambda *a: _opener_with(lambda req: opened.__setitem__("n", 1)))
    big = [{"role": "user", "content": "x" * (provider.MAX_REQUEST_CHARS + 1)}]
    with pytest.raises(ProviderError):
        chat({"name": "x", "model": "m", "base_url": "https://example.com/v1"}, big)
    assert opened["n"] == 0


def test_invalid_message_shape_rejected():
    with pytest.raises(ProviderError):
        chat({"name": "x", "model": "m", "base_url": "https://example.com/v1"}, "not-a-list")
    with pytest.raises(ProviderError):
        chat({"name": "x", "model": "m", "base_url": "https://example.com/v1"},
             [{"role": "user", "content": 5}])


def test_empty_choices_rejected(monkeypatch):
    monkeypatch.setattr(provider.urllib.request, "build_opener",
                        lambda *a: _opener_with(
                            lambda req: FakeResponse({"choices": []})))
    with pytest.raises(ProviderError):
        chat({"name": "x", "model": "m", "base_url": "https://example.com/v1"},
             [{"role": "user", "content": "hi"}])


def test_missing_message_rejected(monkeypatch):
    monkeypatch.setattr(provider.urllib.request, "build_opener",
                        lambda *a: _opener_with(
                            lambda req: FakeResponse({"choices": [{"no_message": True}]})))
    with pytest.raises(ProviderError):
        chat({"name": "x", "model": "m", "base_url": "https://example.com/v1"},
             [{"role": "user", "content": "hi"}])


def test_usage_is_sanitized(monkeypatch):
    monkeypatch.setattr(provider.urllib.request, "build_opener",
                        lambda *a: _opener_with(
                            lambda req: FakeResponse({"choices": [
                                {"message": {"content": "ok"}, "finish_reason": "stop"}],
                                "usage": {"prompt_tokens": 3, "completion_tokens": 2,
                                          "total_tokens": 5, "weird": "x"}})))
    out = chat({"name": "x", "model": "m", "base_url": "https://example.com/v1"},
               [{"role": "user", "content": "hi"}])
    assert out["usage"] == {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5}
