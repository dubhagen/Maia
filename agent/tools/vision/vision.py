"""Vision tool. Images go to the LiteLLM proxy as chat completions.

``vision_model`` overrides the chat model. When it is empty, the chat model
is used if the proxy says that model accepts images. The model id is sent
unchanged.
"""

import base64
import os
import re
import subprocess
import tempfile
from typing import Any, Dict

import requests

from agent.tools.base_tool import BaseTool, ToolResult
from agent.tools.utils.url_safety import validate_url_safe, safe_get
from common.log import logger
from common.media_download import MAX_IMAGE_BYTES, MediaTooLargeError, read_response
from common.utils import expand_path
from config import conf

DEFAULT_TIMEOUT = 180


def resolve_vision_model() -> str:
    """Model id for an image question.

    An explicit ``vision_model`` wins. Otherwise the chat model is used when
    the proxy lists it as vision-capable, or when discovery does not say
    otherwise. A chat model the proxy tags as text-only stays off.
    """
    explicit = str(conf().get("vision_model") or "").strip()
    if explicit:
        return explicit
    chat = str(conf().get("model") or "").strip()
    if not chat:
        return ""
    try:
        from channel.web.api.models import configured_litellm_models
        found, _error = configured_litellm_models()
    except Exception:
        return chat
    match = next((item for item in found if item.get("name") == chat), None)
    if match is None:
        return chat
    if "vision" in (match.get("capabilities") or []):
        return chat
    return ""
MAX_TOKENS = 4000
COMPRESS_THRESHOLD = 1_048_576  # 1 MB

SUPPORTED_EXTENSIONS = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
}


class VisionAPIError(Exception):
    """Raised when a Vision API call fails and should trigger fallback."""
    pass


class Vision(BaseTool):
    """Analyze images using Vision API"""

    name: str = "vision"
    description: str = (
        "Analyze a local image or image URL (jpg/jpeg/png) using Vision API. "
        "Can describe content, extract text, identify objects, colors, etc. "
    )

    params: dict = {
        "type": "object",
        "properties": {
            "image": {
                "type": "string",
                "description": "Local file path or HTTP(S) URL of the image to analyze",
            },
            "question": {
                "type": "string",
                "description": "Question to ask about the image",
            },
        },
        "required": ["image", "question"],
    }

    def __init__(self, config: dict = None):
        self.config = config or {}
        # Declaring cwd is also what makes the bridge inject the workspace.
        self.cwd = self.config.get("cwd", os.getcwd())

    def _resolve_path(self, path: str) -> str:
        """Resolve a local image path the same way the file tools do."""
        path = expand_path(path)
        if os.path.isabs(path):
            return path
        return os.path.abspath(os.path.join(self.cwd, path))

    @staticmethod
    def is_available() -> bool:
        return True

    def execute(self, args: Dict[str, Any]) -> ToolResult:
        image = args.get("image", "").strip()
        question = args.get("question", "").strip()

        if not image:
            return ToolResult.fail("Error: 'image' parameter is required")
        if not question:
            return ToolResult.fail("Error: 'question' parameter is required")

        model = resolve_vision_model()
        if not model:
            return ToolResult.fail(
                "Error: vision is off. Set vision_model to a model id that accepts images, "
                "or choose a chat model that accepts images."
            )

        try:
            image_content = self._build_image_content(image)
        except Exception as e:
            return ToolResult.fail(f"Error: {e}")

        image_url = ""
        if isinstance(image_content, dict):
            image_url = ((image_content.get("image_url") or {}).get("url") or "")
        if not image_url:
            return ToolResult.fail("Error: could not read the image")

        from models.litellm.litellm_bot import LiteLLMBot
        result = LiteLLMBot().call_vision(image_url, question, model=model, max_tokens=MAX_TOKENS)
        if not isinstance(result, dict) or result.get("error"):
            message = result.get("message") if isinstance(result, dict) else "vision request failed"
            return ToolResult.fail(f"Error: {message}")
        content = result.get("content") or ""
        if not str(content).strip():
            return ToolResult.fail("Error: vision model returned an empty answer")
        return ToolResult.success(content)

    @staticmethod
    def _validate_url_safe(url: str) -> None:
        """Reject URLs that target private/loopback/link-local addresses (SSRF guard).

        Resolves the hostname to its IP address(es) and blocks any that fall
        into non-public ranges.  Also rejects URLs with no host, non-HTTP(S)
        schemes, or hosts that fail DNS resolution.

        Delegates to the shared ``agent.tools.utils.url_safety`` helper so the
        same guard protects every tool that fetches model-supplied URLs.

        Raises:
            ValueError: if the URL targets a disallowed address.
        """
        validate_url_safe(url)

    def _build_image_content(self, image: str) -> dict:
        """
        Build the image_url content block.
        Both remote URLs and local files are converted to base64 data URLs
        so every bot backend can consume them without extra downloads.
        """
        if image.startswith(("http://", "https://")):
            self._validate_url_safe(image)
            return self._download_to_data_url(image)

        resolved = self._resolve_path(image)
        if not os.path.isfile(resolved):
            raise FileNotFoundError(
                f"Image file not found: {image}"
                + (f" (resolved to {resolved})" if resolved != image else "")
            )
        image = resolved

        ext = image.rsplit(".", 1)[-1].lower() if "." in image else ""
        mime_type = SUPPORTED_EXTENSIONS.get(ext)
        if not mime_type:
            raise ValueError(
                f"Unsupported image format '.{ext}'. "
                f"Supported: {', '.join(SUPPORTED_EXTENSIONS.keys())}"
            )

        file_path = self._maybe_compress(image)
        if file_path != image:
            mime_type = "image/jpeg"
        try:
            with open(file_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
        finally:
            if file_path != image and os.path.exists(file_path):
                os.remove(file_path)

        data_url = f"data:{mime_type};base64,{b64}"
        return {"type": "image_url", "image_url": {"url": data_url}}

    @staticmethod
    def _download_to_data_url(url: str) -> dict:
        """Download a remote image and return it as a base64 data URL.

        Fetches through the shared redirect-aware SSRF helper. The guard in
        ``_validate_url_safe`` only checks the URL the model supplied, so a
        public URL that 3xx-redirects into a loopback / link-local /
        cloud-metadata address would otherwise be pulled in unchecked.
        """
        resp = safe_get(url, timeout=30, stream=True)
        try:
            if resp.status_code != 200:
                raise VisionAPIError(f"Failed to download image: HTTP {resp.status_code}")
            content_type = resp.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
            if not content_type.startswith("image/"):
                content_type = "image/jpeg"
            try:
                image = read_response(resp, MAX_IMAGE_BYTES)
            except MediaTooLargeError as error:
                raise VisionAPIError(
                    f"Image too large: over {MAX_IMAGE_BYTES} bytes, url={url}"
                ) from error
            b64 = base64.b64encode(image).decode("ascii")
        finally:
            resp.close()
        data_url = f"data:{content_type};base64,{b64}"
        return {"type": "image_url", "image_url": {"url": data_url}}

    @staticmethod
    def _maybe_compress(path: str) -> str:
        """Compress image to under COMPRESS_THRESHOLD with max long-edge 1536px."""
        file_size = os.path.getsize(path)
        if file_size <= COMPRESS_THRESHOLD:
            return path

        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp.close()

        def _try_sips(max_dim: str, quality: str) -> bool:
            try:
                info = subprocess.run(
                    ["sips", "-g", "pixelHeight", "-g", "pixelWidth", path],
                    capture_output=True, text=True, check=True,
                )
                dimensions = {}
                for line in info.stdout.splitlines():
                    name, _, value = line.strip().partition(": ")
                    if name in ("pixelHeight", "pixelWidth"):
                        dimensions[name] = int(value)
                if len(dimensions) != 2 or min(dimensions.values()) <= 0:
                    return False
                # Unlike convert's ">" geometry, sips -Z also enlarges images.
                # Omit resampling when the source already fits the maximum.
                resize = ["-Z", max_dim] if max(dimensions.values()) > int(max_dim) else []
                subprocess.run(
                    ["sips", *resize, "-s", "format", "jpeg", "-s", "formatOptions", quality,
                     path, "--out", tmp.name],
                    capture_output=True, check=True,
                )
                return True
            except (FileNotFoundError, subprocess.CalledProcessError, ValueError):
                return False

        def _try_convert(max_dim: str, quality: str) -> bool:
            try:
                subprocess.run(
                    ["convert", path, "-resize", f"{max_dim}x{max_dim}>",
                     "-quality", quality, tmp.name],
                    capture_output=True, check=True,
                )
                return True
            except (FileNotFoundError, subprocess.CalledProcessError):
                return False

        attempts = [
            ("1536", "85"),
            ("1536", "70"),
            ("1536", "50"),
        ]

        for max_dim, quality in attempts:
            ok = _try_sips(max_dim, quality) or _try_convert(max_dim, quality)
            if not ok:
                continue
            new_size = os.path.getsize(tmp.name)
            logger.debug(f"[Vision] Compressed image "
                         f"({file_size // 1024}KB -> {new_size // 1024}KB, "
                         f"max_dim={max_dim}, q={quality})")
            if new_size <= COMPRESS_THRESHOLD:
                return tmp.name

        if os.path.exists(tmp.name) and os.path.getsize(tmp.name) > 0:
            return tmp.name

        os.remove(tmp.name)
        return path
