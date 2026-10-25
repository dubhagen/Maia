# encoding:utf-8

"""
HTTP client for one LiteLLM OpenAI-compatible endpoint.

Chat, embeddings, images, and audio all go to the configured base URL.
No host-specific attribution headers are attached.
"""

import json
import re
from typing import Any, Dict, Generator, Optional
from urllib.parse import urlparse

import requests

from common.log import logger


DEFAULT_API_BASE = ""
DEFAULT_TIMEOUT = 600


def resolve_host_headers(url: str) -> Dict[str, str]:
    """No third-party gateway headers. The only endpoint is the user's LiteLLM proxy."""
    return {}


class OpenAIHTTPError(Exception):
    """Raised for non-2xx responses. Carries status code + parsed body."""

    def __init__(self, status_code: int, body: Any, message: str = ""):
        self.status_code = status_code
        self.body = body
        # Try to extract human-readable message from OpenAI-style error envelope
        if not message and isinstance(body, dict):
            err = body.get("error") or {}
            if isinstance(err, dict):
                message = err.get("message") or ""
            elif isinstance(err, str):
                message = err
        if not message:
            message = str(body)[:500]
        self.message = message
        super().__init__(f"HTTP {status_code}: {message}")


class OpenAIHTTPClient:
    """Minimal HTTP client for OpenAI-compatible endpoints.

    Per-instance defaults (api_key / api_base / proxy / timeout) can be
    overridden on every call. Callers can also pass ``extra_headers`` for
    Azure-style ``api-key`` headers or custom routing headers.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        proxy: Optional[str] = None,
        timeout: Optional[float] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ):
        self.api_key = api_key
        self.api_base = (api_base or DEFAULT_API_BASE).rstrip("/")
        self.timeout = timeout if timeout is not None else DEFAULT_TIMEOUT
        self.proxies = (
            {"http": proxy, "https": proxy} if proxy else None
        )
        self.extra_headers = dict(extra_headers) if extra_headers else {}

    def _proxies(self, url: str, override: Optional[str] = None) -> Optional[Dict[str, str]]:
        """Use an explicit proxy when set. Otherwise skip env proxies for loopback.

        A system HTTP_PROXY would send http://127.0.0.1:4000 out to that proxy
        and the model call would fail before LiteLLM ever saw it.
        """
        if override:
            return {"http": override, "https": override}
        if self.proxies is not None:
            return self.proxies
        host = (urlparse(url).hostname or "").strip("[]").lower()
        if host in {"localhost", "127.0.0.1", "::1"}:
            return {"http": None, "https": None}
        return None

    # ------------------------------------------------------------------ #
    # Public API surface (mirrors what the old openai SDK provided)
    # ------------------------------------------------------------------ #

    def chat_completions(
        self,
        *,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        timeout: Optional[float] = None,
        proxy: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None,
        extra_query: Optional[Dict[str, str]] = None,
        path: str = "/chat/completions",
        stream: bool = False,
        **payload,
    ):
        """POST /chat/completions.

        When ``stream=True`` returns a generator yielding parsed SSE chunks
        (plain ``dict``). On error during streaming, yields a single dict with
        ``{"error": True, ...}`` and stops, matching the contract expected by
        ``agent/protocol/agent_stream.py``.
        """
        payload["stream"] = stream
        return self._request(
            path=path,
            payload=payload,
            api_key=api_key,
            api_base=api_base,
            timeout=timeout,
            proxy=proxy,
            extra_headers=extra_headers,
            extra_query=extra_query,
            stream=stream,
        )

    def completions(
        self,
        *,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        timeout: Optional[float] = None,
        **payload,
    ) -> Dict[str, Any]:
        """POST /completions (legacy text completion). Non-streaming only."""
        payload.pop("stream", None)
        return self._request(
            path="/completions",
            payload=payload,
            api_key=api_key,
            api_base=api_base,
            timeout=timeout,
            stream=False,
        )

    def images_generate(
        self,
        *,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        timeout: Optional[float] = None,
        **payload,
    ) -> Dict[str, Any]:
        """POST /images/generations."""
        return self._request(
            path="/images/generations",
            payload=payload,
            api_key=api_key,
            api_base=api_base,
            timeout=timeout,
            stream=False,
        )

    def embeddings(
        self,
        *,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        timeout: Optional[float] = None,
        **payload,
    ) -> Dict[str, Any]:
        """POST /embeddings."""
        return self._request(
            path="/embeddings",
            payload=payload,
            api_key=api_key,
            api_base=api_base,
            timeout=timeout,
            stream=False,
        )

    def audio_speech(
        self,
        *,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        timeout: Optional[float] = None,
        **payload,
    ) -> bytes:
        """POST /audio/speech. Returns the audio bytes."""
        base = (api_base or self.api_base).rstrip("/")
        url = f"{base}/audio/speech"
        headers = self._build_headers(api_key, None, url=url)
        try:
            resp = requests.post(
                url,
                headers=headers,
                json={k: v for k, v in payload.items() if v is not None},
                timeout=timeout if timeout is not None else self.timeout,
                proxies=self._proxies(url),
            )
        except requests.exceptions.Timeout as e:
            raise OpenAIHTTPError(408, {}, f"Request timed out: {e}")
        except requests.exceptions.RequestException as e:
            raise OpenAIHTTPError(0, {}, f"Request failed: {e}")
        if resp.status_code >= 400:
            try:
                body = resp.json()
            except ValueError:
                body = {"raw": resp.text[:300]}
            raise OpenAIHTTPError(resp.status_code, body)
        return resp.content

    def audio_transcriptions(
        self,
        *,
        file_path: str,
        model: str,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """POST /audio/transcriptions as multipart form data."""
        base = (api_base or self.api_base).rstrip("/")
        url = f"{base}/audio/transcriptions"
        headers = self._build_headers(api_key, None, url=url)
        headers.pop("Content-Type", None)
        try:
            with open(file_path, "rb") as handle:
                resp = requests.post(
                    url,
                    headers=headers,
                    files={"file": handle},
                    data={"model": model},
                    timeout=timeout if timeout is not None else self.timeout,
                    proxies=self._proxies(url),
                )
        except requests.exceptions.Timeout as e:
            raise OpenAIHTTPError(408, {}, f"Request timed out: {e}")
        except requests.exceptions.RequestException as e:
            raise OpenAIHTTPError(0, {}, f"Request failed: {e}")
        return self._parse_response(resp)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _build_headers(
        self,
        api_key: Optional[str],
        extra_headers: Optional[Dict[str, str]],
        url: Optional[str] = None,
    ) -> Dict[str, str]:
        key = api_key if api_key is not None else self.api_key
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        if url:
            headers.update(resolve_host_headers(url))
        if self.extra_headers:
            headers.update(self.extra_headers)
        if extra_headers:
            headers.update(extra_headers)
        return headers

    def _request(
        self,
        *,
        path: str,
        payload: Dict[str, Any],
        api_key: Optional[str],
        api_base: Optional[str],
        timeout: Optional[float],
        stream: bool,
        proxy: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None,
        extra_query: Optional[Dict[str, str]] = None,
    ):
        base = (api_base or self.api_base).rstrip("/") if api_base else self.api_base
        url = f"{base}{path}" if path.startswith("/") else f"{base}/{path}"
        headers = self._build_headers(api_key, extra_headers, url=url)
        req_timeout = timeout if timeout is not None else self.timeout
        proxies = self._proxies(url, proxy)

        # Drop None-valued keys; some providers reject explicit nulls.
        clean_payload = {k: v for k, v in payload.items() if v is not None}

        if stream:
            # Return a generator. Errors during stream are yielded as a single
            # error chunk so callers (agent_stream) can map them to their
            # existing error-handling path without try/except around the loop.
            return self._stream_chat(
                url=url,
                headers=headers,
                payload=clean_payload,
                proxies=proxies,
                timeout=req_timeout,
                params=extra_query,
            )

        try:
            resp = requests.post(
                url,
                headers=headers,
                json=clean_payload,
                timeout=req_timeout,
                proxies=proxies,
                params=extra_query,
            )
        except requests.exceptions.Timeout as e:
            raise OpenAIHTTPError(408, {}, f"Request timed out: {e}")
        except requests.exceptions.ConnectionError as e:
            raise OpenAIHTTPError(0, {}, f"Connection error: {e}")
        except requests.exceptions.RequestException as e:
            raise OpenAIHTTPError(0, {}, f"Request failed: {e}")

        return self._parse_response(resp)

    @staticmethod
    def _parse_response(resp: requests.Response) -> Dict[str, Any]:
        # Try JSON, fall back to text
        try:
            data = resp.json()
        except ValueError:
            data = {"raw": resp.text}

        if resp.status_code >= 400:
            raise OpenAIHTTPError(resp.status_code, data)

        return data

    def _stream_chat(
        self,
        *,
        url: str,
        headers: Dict[str, str],
        payload: Dict[str, Any],
        proxies: Optional[Dict[str, str]],
        timeout: float,
        params: Optional[Dict[str, str]] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """Stream SSE response and yield parsed JSON chunks.

        Yields:
            - Normal chunks: dict with ``choices[0].delta`` etc.
            - Error chunks: ``{"error": True, "message": str, "status_code": int}``
              followed by termination of the generator.
        """
        try:
            resp = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=timeout,
                proxies=proxies,
                stream=True,
                params=params,
            )
        except requests.exceptions.Timeout as e:
            yield self._make_error_chunk(408, f"Request timed out: {e}")
            return
        except requests.exceptions.ConnectionError as e:
            yield self._make_error_chunk(0, f"Connection error: {e}")
            return
        except requests.exceptions.RequestException as e:
            yield self._make_error_chunk(0, f"Request failed: {e}")
            return

        if resp.status_code >= 400:
            try:
                # Read full body once for error reporting
                try:
                    body = resp.json()
                except ValueError:
                    body = {"raw": resp.text[:1000]}
                err_msg = ""
                err_code = ""
                err_type = ""
                if isinstance(body, dict):
                    err = body.get("error") or {}
                    if isinstance(err, dict):
                        err_msg = err.get("message") or ""
                        err_code = err.get("code") or ""
                        err_type = err.get("type") or ""
                    elif isinstance(err, str):
                        err_msg = err
                if not err_msg:
                    err_msg = str(body)[:500]
                yield {
                    "error": {
                        "message": err_msg,
                        "code": err_code,
                        "type": err_type,
                    },
                    # Top-level fields kept for backward compatibility with the
                    # error-shape that `_handle_stream_response` previously emitted.
                    "message": err_msg,
                    "status_code": resp.status_code,
                }
                return
            finally:
                try:
                    resp.close()
                except Exception:
                    pass

        # IMPORTANT: do NOT use `iter_lines(decode_unicode=True)`.
        #
        # `requests` decodes per-network-chunk using the response's declared
        # encoding (often Latin-1 / ISO-8859-1 for SSE), which mangles UTF-8
        # codepoints that straddle a chunk boundary. Some upstreams (Azure
        # OpenAI proxies, Cloudflare-fronted gateways, ...) split TCP chunks
        # aggressively in the middle of multibyte characters, producing
        # garbled text and "skip malformed SSE chunk" errors.
        #
        # The fix is to read raw bytes, accumulate them until we have a
        # complete SSE event (terminated by a blank line per the SSE spec:
        # https://html.spec.whatwg.org/multipage/server-sent-events.html),
        # and only THEN decode as UTF-8. This mirrors what the official
        # openai SDK 1.x does in `openai/_streaming.py::SSEDecoder` (which
        # itself is copied from httpx-sse).
        try:
            for sse_event in self._iter_sse_events(resp):
                # `sse_event` is the joined `data:` payload as a str.
                if sse_event == "[DONE]":
                    return
                if not sse_event:
                    continue
                try:
                    chunk = json.loads(sse_event)
                except ValueError:
                    logger.debug(
                        f"[OpenAIHTTP] skip malformed SSE chunk: {sse_event[:200]}"
                    )
                    continue
                yield chunk
        except requests.exceptions.ChunkedEncodingError as e:
            yield self._make_error_chunk(0, f"Stream interrupted: {e}")
        except requests.exceptions.RequestException as e:
            yield self._make_error_chunk(0, f"Stream error: {e}")
        finally:
            try:
                resp.close()
            except Exception:
                pass

    @staticmethod
    def _iter_sse_events(resp: requests.Response) -> Generator[str, None, None]:
        """Decode an SSE byte stream into joined `data:` payloads.

        Implements the subset of the SSE spec that OpenAI / OpenAI-compatible
        endpoints actually use:
          - Events are separated by blank lines (\\r\\r, \\n\\n, or \\r\\n\\r\\n).
          - Within an event, multiple ``data:`` lines are concatenated with
            "\\n" (per spec).
          - ``event:``, ``id:``, ``retry:`` and comment lines (``:``) are
            tolerated but not yielded — for chat-completion we only care
            about the JSON payload in ``data:``.
          - Bytes are buffered until a complete event boundary is seen so
            UTF-8 codepoints split across TCP chunks decode correctly.

        Yields each event's joined ``data`` string. The terminal sentinel
        ``[DONE]`` is yielded as a literal string so the caller can break.
        """
        buf = b""
        data_lines = []
        first_line = True
        skip_lf = False
        newline = re.compile(rb"\r\n|\r|\n")

        def consume_line(raw_line):
            nonlocal first_line
            # Only the stream's initial BOM is framing. Other Unicode line
            # separators are payload and must survive inside JSON strings.
            encoding = "utf-8-sig" if first_line else "utf-8"
            first_line = False
            line = raw_line.decode(encoding, errors="replace")
            if not line:
                if data_lines:
                    event = "\n".join(data_lines)
                    data_lines.clear()
                    return event
            elif not line.startswith(":"):
                field, _, value = line.partition(":")
                if value.startswith(" "):
                    value = value[1:]
                if field == "data":
                    data_lines.append(value)
            return None

        for raw in resp.iter_content(chunk_size=None, decode_unicode=False):
            if not raw:
                continue
            # A CR at a network-chunk boundary already ended its line. The
            # optional following LF belongs to that same delimiter.
            if skip_lf:
                if raw.startswith(b"\n"):
                    raw = raw[1:]
                skip_lf = False
            buf += raw
            while (match := newline.search(buf)) is not None:
                raw_line = buf[:match.start()]
                skip_lf = match.group() == b"\r" and match.end() == len(buf)
                buf = buf[match.end():]
                event = consume_line(raw_line)
                if event is not None:
                    yield event

        # Preserve compatibility with proxies that omit the final blank line.
        if buf:
            consume_line(buf)
        if data_lines:
            yield "\n".join(data_lines)

    @staticmethod
    def _make_error_chunk(status_code: int, message: str) -> Dict[str, Any]:
        return {
            "error": {"message": message, "code": "", "type": ""},
            "message": message,
            "status_code": status_code,
        }


# A tiny helper for callers that just need a one-shot client without storing
# state. Keeps call sites cleaner than instantiating the class every time.
def get_default_client(
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    proxy: Optional[str] = None,
    timeout: Optional[float] = None,
) -> OpenAIHTTPClient:
    return OpenAIHTTPClient(
        api_key=api_key, api_base=api_base, proxy=proxy, timeout=timeout
    )
