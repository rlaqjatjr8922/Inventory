"""Shared image encoding for HTTP envelopes and native MCP image blocks."""

import base64
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps


MAX_IMAGE_EDGE = 1600
JPEG_QUALITY = 85


def image_response(image_id: int, path: Path) -> dict:
    """Encode the actual image format, without changing the stored original."""
    with Image.open(path) as source:
        picture = ImageOps.exif_transpose(source)
        picture.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE), Image.Resampling.LANCZOS)
        output = BytesIO()
        if source.format == "PNG":
            picture.save(output, format="PNG", optimize=True)
            mime_type = "image/png"
        else:
            picture.convert("RGB").save(
                output, format="JPEG", quality=JPEG_QUALITY, optimize=True
            )
            mime_type = "image/jpeg"
    label = f"image_id: {image_id}"
    return {
        "image_id": image_id,
        "content": label,
        "content_items": [
            {"type": "text", "text": label},
            {
                "type": "image",
                "mimeType": mime_type,
                "data": base64.b64encode(output.getvalue()).decode("ascii"),
            },
        ],
    }
