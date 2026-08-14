from __future__ import annotations

from io import BytesIO

from PIL import Image, UnidentifiedImageError

from app.errors import InvalidChartError


_ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


def validate_image_bytes(data: bytes, *, max_bytes: int) -> str:
    if not data or len(data) > max_bytes:
        raise InvalidChartError("invalid_image_size", "이미지 크기가 허용 범위를 벗어났습니다.")
    try:
        with Image.open(BytesIO(data)) as image:
            image.verify()
            width, height = image.size
            image_format = (image.format or "").upper()
    except (UnidentifiedImageError, OSError, SyntaxError) as error:
        raise InvalidChartError("image_decode_failed", "이미지 파일을 읽을 수 없습니다.") from error
    if image_format not in _ALLOWED_FORMATS:
        raise InvalidChartError("unsupported_image", "PNG, JPEG 또는 WEBP 이미지만 사용할 수 있습니다.")
    if width < 320 or height < 240:
        raise InvalidChartError("image_too_small", "차트 글자를 읽기에는 이미지 해상도가 너무 낮습니다.")
    return image_format.lower()
