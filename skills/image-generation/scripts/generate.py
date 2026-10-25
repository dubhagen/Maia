#!/usr/bin/env python3
"""
Image generation through the configured LiteLLM proxy.

Usage:
    python generate.py '<json_args>'

POST {litellm_api_base}/images/generations (or /images/edits when an input
image is given). The model id is sent unchanged. An empty model or a missing
base fails closed.

Dependencies: requests (stdlib: json, sys, os, base64, io, abc, uuid, pathlib, urllib)
"""

import json
import sys
import os
import base64
import io
import time
import uuid
import re
from abc import ABC, abstractmethod
from urllib.request import urlopen, Request

try:
    import requests

    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False


# ---------------------------------------------------------------------------
# Size / aspect-ratio resolution
# ---------------------------------------------------------------------------

_SIZE_TABLE = {
    # (tier, ratio) -> "WxH"
    ("1K", "1:1"): "1024x1024",
    ("1K", "3:2"): "1536x1024",
    ("1K", "2:3"): "1024x1536",
    ("2K", "1:1"): "2048x2048",
    ("2K", "16:9"): "2048x1152",
    ("2K", "9:16"): "1152x2048",
    ("4K", "16:9"): "3840x2160",
    ("4K", "9:16"): "2160x3840",
}

_TIER_ORDER = ["1K", "2K", "4K"]
_RATIO_DEFAULT = {"1K": "1:1", "2K": "1:1", "4K": "16:9"}

_PIXEL_RE = re.compile(r"^\d+x\d+$")


def resolve_size(size: str | None, aspect_ratio: str | None) -> str | None:
    """Resolve (size, aspect_ratio) to a concrete 'WxH' string or None."""
    if size and _PIXEL_RE.match(size):
        return size
    if size and size.lower() == "auto":
        size = None
    if not size and not aspect_ratio:
        return None

    tier = size.upper() if size else None
    ratio = aspect_ratio

    if tier and ratio:
        key = (tier, ratio)
        if key in _SIZE_TABLE:
            return _SIZE_TABLE[key]
        # Upgrade: try higher tiers with same ratio
        start = _TIER_ORDER.index(tier) + 1 if tier in _TIER_ORDER else 0
        for t in _TIER_ORDER[start:]:
            if (t, ratio) in _SIZE_TABLE:
                return _SIZE_TABLE[(t, ratio)]
        # Cross-tier: any tier with this ratio
        for t in _TIER_ORDER:
            if (t, ratio) in _SIZE_TABLE:
                return _SIZE_TABLE[(t, ratio)]
        # Tier default
        if tier in _RATIO_DEFAULT:
            return _SIZE_TABLE.get((tier, _RATIO_DEFAULT[tier]))

    if tier and not ratio:
        default_ratio = _RATIO_DEFAULT.get(tier)
        if default_ratio:
            return _SIZE_TABLE.get((tier, default_ratio))

    if ratio and not tier:
        for t in _TIER_ORDER:
            if (t, ratio) in _SIZE_TABLE:
                return _SIZE_TABLE[(t, ratio)]

    return None


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------

def _load_image(source: str) -> bytes:
    """Load image from a local file path or URL."""
    if os.path.isfile(source):
        with open(source, "rb") as f:
            return f.read()
    if _HAS_REQUESTS:
        resp = requests.get(source, timeout=60)
        resp.raise_for_status()
        return resp.content
    req = Request(source)
    with urlopen(req, timeout=60) as resp:
        return resp.read()


def _decode_image_item(item: dict, *, url_first: bool = False) -> bytes | None:
    """Return the image bytes carried by an OpenAI-compatible result item.

    Some backends send both keys even when only one of them holds a value —
    e.g. an empty ``b64_json`` next to a usable ``url`` in URL output mode.
    Branching on key presence would decode the empty string into a 0-byte
    file, so branch on the value instead and fall through to the other key.
    Returns None when neither field carries a value.
    """
    keys = ("url", "b64_json") if url_first else ("b64_json", "url")
    for key in keys:
        value = item.get(key)
        if not value:
            continue
        if key == "b64_json":
            return base64.b64decode(value)
        return _load_image(value)
    return None


def _compress_image(data: bytes, max_bytes: int = 4 * 1024 * 1024, max_edge: int = 4096) -> bytes:
    """Compress image to fit size/dimension limits. Requires Pillow only when needed."""
    if len(data) <= max_bytes:
        try:
            from PIL import Image

            img = Image.open(io.BytesIO(data))
            w, h = img.size
            if max(w, h) <= max_edge:
                return data
        except ImportError:
            return data
        except Exception:
            return data

    try:
        from PIL import Image
    except ImportError:
        return data

    img = Image.open(io.BytesIO(data))
    w, h = img.size
    # Image.resize() clears .format, so read it first.
    fmt = img.format or "PNG"

    if max(w, h) > max_edge:
        ratio = max_edge / max(w, h)
        w, h = int(w * ratio), int(h * ratio)
        img = img.resize((w, h), Image.LANCZOS)

    buf = io.BytesIO()
    if fmt.upper() == "JPEG":
        quality = 85
        while True:
            buf.seek(0)
            buf.truncate()
            img.save(buf, format="JPEG", quality=quality)
            if buf.tell() <= max_bytes or quality <= 20:
                break
            quality -= 10
    else:
        img.save(buf, format=fmt)
        if buf.tell() > max_bytes:
            buf.seek(0)
            buf.truncate()
            img.save(buf, format="JPEG", quality=75)
    return buf.getvalue()


def _save_image(data: bytes, output_dir: str) -> str:
    """Save image bytes to output_dir and return the path."""
    os.makedirs(output_dir, exist_ok=True)
    ext = "png"
    if data[:3] == b"\xff\xd8\xff":
        ext = "jpg"
    elif data[:4] == b"RIFF":
        ext = "webp"
    filename = f"{uuid.uuid4().hex[:12]}.{ext}"
    path = os.path.join(output_dir, filename)
    with open(path, "wb") as f:
        f.write(data)
    return path


def _apply_attribution_headers(headers: dict) -> None:
    """No third-party attribution headers."""
    del headers


# ---------------------------------------------------------------------------
# Provider interface
# ---------------------------------------------------------------------------

class ImageProvider(ABC):
    """Abstract base class for image generation providers."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        *,
        image_url: str | list | None = None,
        quality: str | None = None,
        size: str | None = None,
        aspect_ratio: str | None = None,
        output_dir: str = ".",
    ) -> list[str]:
        """Generate image(s) and return list of local file paths.

        `size` may be a tier ("1K" / "2K" / "4K" / "512") or pixels ("WxH").
        Providers that need pixel sizes should call `resolve_size(size, aspect_ratio)`.
        """
        ...


class OpenAIProvider(ImageProvider):
    """OpenAI-compatible image generations and edits on the LiteLLM base."""

    def __init__(self, api_key: str, api_base: str, model: str):
        chosen = (model or "").strip()
        if not chosen:
            raise RuntimeError("image model id is required")
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")
        self.model = chosen

    def _headers(self) -> dict:
        if not self.api_key:
            return {}
        return {
            "Authorization": f"Bearer {self.api_key}",
        }

    @staticmethod
    def _raise_for_api_error(resp):
        """Raise with server error details instead of bare HTTP status."""
        if resp.status_code >= 400:
            try:
                body = resp.json()
                msg = body.get("error", {}).get("message") or body.get("message") or resp.text
            except Exception:
                msg = resp.text or resp.reason
            raise RuntimeError(f"API {resp.status_code}: {msg} (url: {resp.url})")

    @staticmethod
    def _raise_for_business_error(result: dict):
        """Raise when an OpenAI-compatible backend returns HTTP 200 plus `error`."""
        if isinstance(result, dict) and result.get("error"):
            err = result["error"]
            if isinstance(err, dict):
                msg = err.get("message") or err.get("code") or str(err)
            else:
                msg = str(err)
            raise RuntimeError(f"API error: {msg}")

    def _post_json(self, url: str, payload: dict) -> dict:
        headers = {**self._headers(), "Content-Type": "application/json"}
        if _HAS_REQUESTS:
            resp = requests.post(url, headers=headers, json=payload, timeout=300)
            self._raise_for_api_error(resp)
            result = resp.json()
        else:
            data = json.dumps(payload).encode()
            req = Request(url, data=data, headers=headers, method="POST")
            with urlopen(req, timeout=300) as r:
                result = json.loads(r.read())
        self._raise_for_business_error(result)
        return result

    def _post_multipart(self, url: str, fields: dict, files: list[tuple]) -> dict:
        """POST multipart/form-data using requests (or fall back to urllib)."""
        headers = self._headers()
        if _HAS_REQUESTS:
            resp = requests.post(url, headers=headers, data=fields, files=files, timeout=300)
            self._raise_for_api_error(resp)
            result = resp.json()
            self._raise_for_business_error(result)
            return result
        boundary = uuid.uuid4().hex
        body = b""
        for key, val in fields.items():
            body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{val}\r\n".encode()
        for field_name, (filename, filedata, content_type) in files:
            body += (
                f"--{boundary}\r\n"
                f"Content-Disposition: form-data; name=\"{field_name}\"; filename=\"{filename}\"\r\n"
                f"Content-Type: {content_type}\r\n\r\n"
            ).encode() + filedata + b"\r\n"
        body += f"--{boundary}--\r\n".encode()
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        req = Request(url, data=body, headers=headers, method="POST")
        with urlopen(req, timeout=300) as r:
            result = json.loads(r.read())
        self._raise_for_business_error(result)
        return result

    def generate(
        self,
        prompt: str,
        *,
        image_url=None,
        quality: str | None = None,
        size: str | None = None,
        aspect_ratio: str | None = None,
        output_dir: str = ".",
    ) -> list[str]:
        # OpenAI Images API expects pixel size like 1024x1024.
        resolved = resolve_size(size, aspect_ratio) if (size or aspect_ratio) else None
        if image_url:
            paths = self._edit(prompt, image_url=image_url, quality=quality, size=resolved, output_dir=output_dir)
        else:
            paths = self._create(prompt, quality=quality, size=resolved, output_dir=output_dir)
        if not paths:
            raise RuntimeError("provider returned no image (empty data)")
        return paths

    def _create(self, prompt: str, *, quality: str | None, size: str | None, output_dir: str) -> list[str]:
        url = f"{self.api_base}/images/generations"
        payload: dict = {
            "model": self.model,
            "prompt": prompt,
        }
        if quality:
            payload["quality"] = quality
        if size:
            payload["size"] = size
        result = self._post_json(url, payload)
        return self._save_results(result, output_dir)

    def _edit(
        self,
        prompt: str,
        *,
        image_url,
        quality: str | None,
        size: str | None,
        output_dir: str,
    ) -> list[str]:
        urls = image_url if isinstance(image_url, list) else [image_url]
        image_data_list = [_compress_image(_load_image(u)) for u in urls]

        url = f"{self.api_base}/images/edits"

        fields = {"model": self.model, "prompt": prompt}
        if quality:
            fields["quality"] = quality
        if size:
            fields["size"] = size

        files = []
        for i, img_bytes in enumerate(image_data_list):
            ext = "png"
            if img_bytes[:3] == b"\xff\xd8\xff":
                ext = "jpg"
            field_name = "image[]" if len(image_data_list) > 1 else "image"
            files.append((field_name, (f"image_{i}.{ext}", img_bytes, f"image/{ext}")))

        result = self._post_multipart(url, fields, files)
        return self._save_results(result, output_dir)

    @staticmethod
    def _save_results(result: dict, output_dir: str) -> list[str]:
        paths = []
        for item in result.get("data", []):
            raw = _decode_image_item(item)
            if raw:
                paths.append(_save_image(raw, output_dir))
        return paths


def _build_providers(model: str, provider_id: str = "") -> list[tuple[str, ImageProvider]]:
    """One LiteLLM image provider. Vendor keys are not read.

    ``provider_id`` is ignored. An empty model or a missing base returns no
    provider so the caller fails closed instead of guessing a vendor model.
    """
    del provider_id
    base = (os.environ.get("LITELLM_API_BASE") or "").strip().rstrip("/")
    if not base.startswith(("http://", "https://")) or not base.endswith("/v1"):
        return []
    chosen = (
        (model or "").strip()
        or (os.environ.get("LITELLM_IMAGE_MODEL") or "").strip()
        or (os.environ.get("IMAGE_MODEL") or "").strip()
    )
    if not chosen:
        return []
    key = (os.environ.get("LITELLM_API_KEY") or "").strip()
    return [("LiteLLM", OpenAIProvider(api_key=key, api_base=base, model=chosen))]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: python generate.py '<json_args>'"}))
        sys.exit(1)

    try:
        raw = sys.argv[1]
        try:
            args = json.loads(raw)
        except json.JSONDecodeError:
            # Curly quotes used as JSON delimiters; never straighten valid payloads.
            raw = raw.replace('\u201c', '"').replace('\u201d', '"').replace('\u2018', "'").replace('\u2019', "'")
            args = json.loads(raw)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {e}"}))
        sys.exit(1)

    if not isinstance(args, dict):
        print(json.dumps({"error": "Arguments must be a JSON object"}))
        sys.exit(1)

    prompt = args.get("prompt")
    if not prompt:
        print(json.dumps({"error": "Missing required parameter: prompt"}))
        sys.exit(1)

    # Model id priority: call argument, skill config, then image_model.
    # An empty id fails closed. Vendor keys are not consulted.
    model = (
        args.get("model")
        or os.environ.get("SKILL_IMAGE_GENERATION_MODEL")
        or os.environ.get("LITELLM_IMAGE_MODEL")
        or ""
    )
    provider_id = args.get("provider") or os.environ.get("SKILL_IMAGE_GENERATION_PROVIDER") or ""
    quality = args.get("quality")
    size = args.get("size")
    aspect_ratio = args.get("aspect_ratio")
    image_url = args.get("image_url")

    # Resolve output dir independently of the live cwd (the agent may `cd`
    # elsewhere, e.g. into this skill's dir, which gets wiped on restart).
    # Priority: explicit IMAGE_OUTPUT_DIR -> workspace/project dir -> cwd.
    output_base = os.environ.get("IMAGE_OUTPUT_DIR")
    if not output_base:
        workspace = os.environ.get("AGENT_WORKSPACE") or os.getcwd()
        output_base = os.path.join(workspace, "images")
    output_dir = output_base

    providers = _build_providers(model, provider_id=provider_id)
    if not providers:
        target = f"model '{model}'" if model else "image generation"
        print(json.dumps({
            "error": (
                f"Image generation is off for {target}. "
                "Set litellm_api_base (http(s) URL ending in /v1) and image_model."
            )
        }, ensure_ascii=False))
        sys.exit(1)

    errors = []
    for label, provider in providers:
        try:
            attempt_model = getattr(provider, "model", model) or "auto"
            print(f"[image-generation] Trying {label} (model={attempt_model})...", file=sys.stderr)
            t0 = time.time()
            paths = provider.generate(
                prompt,
                image_url=image_url,
                quality=quality,
                size=size,
                aspect_ratio=aspect_ratio,
                output_dir=output_dir,
            )
            elapsed = time.time() - t0
            # Resolved model id (after alias expansion) actually sent to the API
            actual_model = getattr(provider, "model", model)
            print(
                f"[image-generation] ✅ {label} succeeded in {elapsed:.1f}s "
                f"(model={actual_model})",
                file=sys.stderr,
            )
            result = {
                "model": actual_model,
                "images": [{"url": p} for p in paths],
            }
            print(json.dumps(result, ensure_ascii=False))
            return
        except Exception as e:
            elapsed = time.time() - t0
            print(f"[image-generation] ❌ {label} failed in {elapsed:.1f}s: {e}", file=sys.stderr)
            errors.append(f"{label}: {e}")

    hint = " | ".join(errors)
    print(json.dumps({
        "error": f"Image generation failed — {hint}. "
                 "Do NOT retry with the same parameters. "
                 "Ask the user to check litellm_api_base and image_model "
                 "on the LiteLLM endpoint."
    }, ensure_ascii=False))
    sys.exit(1)


if __name__ == "__main__":
    main()
