"""Small, dependency-free OpenAI-compatible Chat Completions client.

Security notes
--------------
* API keys are read only from environment variables named by ``api_key_env``.
  A literal ``api_key`` in config is rejected, and credentials embedded in the
  URL are rejected as well.
* Keys are never placed in returned reports, exported files, or error messages.
* Answer text and judge text are treated as untrusted data downstream; this
  layer only transports and validates the HTTP exchange.
"""
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

_BEARER_RE = re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE)
_SK_RE = re.compile(r"sk-[A-Za-z0-9._\-]+")

TRANSIENT_STATUS = {429, 500, 502, 503, 504}
MAX_RESPONSE_BYTES = 4_000_000
MAX_REQUEST_CHARS = 200_000
MAX_BACKOFF_SECONDS = 4.0
DEFAULT_TIMEOUT = 120
DEFAULT_RETRIES = 2


def mask_private(text):
    """Mask bearer tokens and ``sk-...`` secrets before anything is logged."""
    if not isinstance(text, str):
        return ""
    text = _BEARER_RE.sub("Bearer ***", text)
    text = _SK_RE.sub("sk-***", text)
    return text


class ProviderError(RuntimeError):
    """Raised for configuration, network, HTTP or response-format failures."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ProviderError("Endpoint redirected; configure the final URL explicitly.")


def validate_model(spec):
    """Validate a player/judge model spec. Raise ``ValueError`` on problems."""
    if not isinstance(spec, dict):
        raise ValueError("Model configuration must be an object")
    for field in ("name", "model", "base_url"):
        if not isinstance(spec.get(field), str) or not spec[field].strip():
            raise ValueError(f"Missing model field: {field}")
    url = urllib.parse.urlsplit(spec["base_url"])
    if url.username or url.password or url.query or url.fragment:
        raise ValueError("base_url must not contain credentials, query or fragment")
    if not url.hostname or (url.scheme != "https" and not (
        url.scheme == "http" and url.hostname in {"localhost", "127.0.0.1", "::1"}
    )):
        raise ValueError("Use HTTPS, or HTTP on localhost for a local model")
    if "api_key" in spec:
        raise ValueError("Use api_key_env, never a literal API key in config")
    key_env = spec.get("api_key_env", "")
    if not isinstance(key_env, str):
        raise ValueError("api_key_env must be a string")
    return spec


def _validate_messages(messages):
    if not isinstance(messages, list) or not messages:
        raise ProviderError("messages must be a non-empty list")
    total = 0
    for message in messages:
        if not isinstance(message, dict):
            raise ProviderError("Each message must be an object")
        if not isinstance(message.get("role"), str) or not isinstance(message.get("content"), str):
            raise ProviderError("Message role and content must be strings")
        total += len(message["content"])
    if total > MAX_REQUEST_CHARS:
        raise ProviderError(f"Request content exceeds {MAX_REQUEST_CHARS} characters")
    return messages


def _retry_delay(attempt, exc):
    retry_after = None
    if isinstance(exc, urllib.error.HTTPError):
        header = exc.headers.get("Retry-After") if exc.headers else None
        if header and header.isdigit():
            retry_after = int(header)
    if retry_after is not None:
        return min(float(retry_after), MAX_BACKOFF_SECONDS)
    return min(0.5 * (2 ** attempt), MAX_BACKOFF_SECONDS)


def _resolve_key(spec):
    key_env = spec.get("api_key_env")
    if not key_env:
        return ""
    key = os.environ.get(key_env, "")
    if not key:
        raise ProviderError(f"Missing environment variable: {key_env}")
    return key


def _request(spec, payload, timeout):
    key = _resolve_key(spec)
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if key:
        headers["Authorization"] = f"Bearer {key}"
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        spec["base_url"].rstrip("/") + "/chat/completions",
        data=body,
        headers=headers,
        method="POST",
    )
    opener = urllib.request.build_opener(NoRedirect)
    with opener.open(request, timeout=timeout) as response:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ProviderError("Response exceeded 4 MB")
    return raw


def _post_with_retry(spec, payload, timeout, retries):
    last_error = None
    for attempt in range(retries + 1):
        try:
            return _request(spec, payload, timeout)
        except urllib.error.HTTPError as exc:
            if exc.code in TRANSIENT_STATUS and attempt < retries:
                last_error = ProviderError(f"Model API returned HTTP {exc.code} (transient)")
                delay = _retry_delay(attempt, exc)
            else:
                # Do not echo response bodies that may echo headers or secrets.
                raise ProviderError(
                    f"Model API returned HTTP {exc.code}; check credentials, model name and support"
                ) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            last_error = ProviderError("Cannot reach model API or request timed out")
            if attempt == retries:
                raise last_error from None
            delay = min(0.5 * (2 ** attempt), MAX_BACKOFF_SECONDS)
        if attempt < retries:
            time.sleep(delay)
    raise last_error or ProviderError("Request failed")


def _sanitize_usage(usage):
    if not isinstance(usage, dict):
        return {}
    cleaned = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = usage.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            cleaned[key] = value
    return cleaned


def chat(spec, messages, *, temperature=0.3, max_tokens=1500,
         timeout=DEFAULT_TIMEOUT, retries=DEFAULT_RETRIES):
    """Call an OpenAI-compatible chat endpoint.

    Returns ``{"text", "seconds", "usage", "model"}``. Raises ProviderError.
    """
    validate_model(spec)
    _validate_messages(messages)
    payload = {
        "model": spec["model"],
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    start = time.monotonic()
    raw = _post_with_retry(spec, payload, timeout, retries)
    try:
        result = json.loads(raw)
        choice = result["choices"][0]
        message = choice["message"]
        content = message.get("content")
        if choice.get("finish_reason") == "length":
            raise ProviderError("Answer truncated by max_tokens; raise max_tokens or shorten the prompt")
        if not isinstance(content, str) or not content.strip():
            raise ProviderError("Model returned an empty or non-text answer")
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        raise ProviderError("Invalid Chat Completions response") from None
    return {
        "text": content.strip(),
        "seconds": round(time.monotonic() - start, 3),
        "usage": _sanitize_usage(result.get("usage", {})),
        "model": result.get("model", spec["model"]),
    }


def _extract_json_object(text):
    """Return the first balanced JSON object found in *text*, else raise."""
    text = text.strip()
    if text.startswith("```"):
        # Strip a leading ```json / ``` fence and the trailing fence.
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        text = text.rsplit("```", 1)[0].strip()
    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found")
    depth = 0
    in_string = False
    escape = False
    for index, char in enumerate(text[start:], start=start):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    raise ValueError("Unbalanced JSON object")


def parse_json(text):
    """Parse a judge verdict that may include fences or surrounding prose."""
    if not isinstance(text, str):
        raise ValueError("Judge verdict must be text")
    candidate = _extract_json_object(text)
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        raise ValueError("Judge verdict is not valid JSON") from None
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value
