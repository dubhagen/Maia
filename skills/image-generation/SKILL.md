---
name: image-generation
description: Generate or edit images from text prompts. Use when the user asks to create, draw, design, or edit an image, illustration, photo, icon, poster, or any visual content.
metadata:
  maia:
    requires:
      env:
        - LITELLM_API_BASE
        - LITELLM_IMAGE_MODEL
---

# Image Generation

Generate and edit images through the configured LiteLLM endpoint. The model id is `image_model` (exported to the script as `LITELLM_IMAGE_MODEL`). Send that id unchanged. Do not ask for an OpenAI, Gemini, Seedream, Qwen, MiniMax, or LinkAI key, and do not invent a model id. Omit `model` unless the user names an id the proxy lists.

## Usage

Run `scripts/generate.py` with a JSON argument. Use the absolute `<base_dir>` path. Do not `cd` into the skill directory.

```bash
python <base_dir>/scripts/generate.py '<json_args>'
```

Images are saved under `images/` in the workspace.

Set the bash timeout to at least 300 seconds. Call the script synchronously and wait for its output.

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `prompt` | string | yes | — | Image description |
| `image_url` | string / list | no | null | Input image(s) for editing: a local path or URL |
| `quality` | string | no | auto | `low` / `medium` / `high` when the model accepts it |
| `size` | string | no | auto | `512` / `1K` / `2K` / `3K` / `4K`, or pixels such as `1024x1024` |
| `aspect_ratio` | string | no | null | `1:1` / `3:2` / `2:3` / `16:9` / `9:16` / `21:9` |
| `model` | string | no | image_model | Model id on the same LiteLLM endpoint |

### Example

```bash
python <base_dir>/scripts/generate.py '{"prompt": "A corgi astronaut floating in space"}'
```

When the user asks to edit an existing image, pass it via `image_url`. Prefer a local path. Without `image_url`, the script creates a new image.

```bash
python <base_dir>/scripts/generate.py '{"prompt": "Add a Santa hat to the dog", "image_url": "/path/to/dog.png"}'
```

### Output

```json
{
  "model": "<image_model>",
  "images": [
    {"url": "/path/to/output.png"}
  ]
}
```

Show the image with markdown (`![description](/path/to/output.png)`) or the `send` tool.

### Setup

Set `litellm_api_base` to an http(s) URL ending in `/v1`, and set `image_model` to an image model id on that endpoint. An empty `image_model` turns this skill off. The built-in image tool uses the same two settings.

### Error handling

If the script returns an error, do not retry the same request and do not look for a vendor API key. Tell the user to check the LiteLLM base URL and `image_model`.

### Notes

- HTTP timeout is 300 seconds.
- Omit `quality` and `size` to let the model choose.
- Input images are compressed to at most 4MB, with the longest edge at most 4096px.
