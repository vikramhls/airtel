"""Image preprocessing: colour watermark removal, upscale, deskew, binarise.

The specimen documents carry a pink diagonal watermark. Thresholding on
darkness keeps the navy/black text and drops the pink watermark, which is a
light tint - so the watermark never reaches the OCR layer or the field parser.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

TARGET_WIDTH = 1800  # ~300 DPI equivalent for these page images


def load(source: str | Path | bytes) -> Image.Image:
    if isinstance(source, bytes):
        from io import BytesIO

        img = Image.open(BytesIO(source))
    else:
        img = Image.open(source)
    img = ImageOps.exif_transpose(img)
    if img.mode in {"RGBA", "LA", "P"}:
        background = Image.new("RGB", img.size, "white")
        img = img.convert("RGBA")
        background.paste(img, mask=img.split()[-1])
        img = background
    return img.convert("RGB")


def is_watermark_pink(pixel: tuple[int, int, int]) -> bool:
    r, g, b = pixel
    return r > 180 and abs(g - b) < 25 and (r - g) > 18


def strip_watermark(img: Image.Image) -> Image.Image:
    """Turn the light-pink watermark into white, keeping dark text intact."""
    arr = np.asarray(img).astype(np.int16)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    pink = (r > 180) & (np.abs(g - b) < 25) & ((r - g) > 18)
    arr[pink] = [255, 255, 255]
    return Image.fromarray(arr.astype(np.uint8))


def binarise(img: Image.Image) -> Image.Image:
    grey = ImageOps.grayscale(img)
    arr = np.asarray(grey).astype(np.uint8)
    # Otsu-free fixed threshold: the page is pure white, text is dark navy/black.
    out = np.where(arr < 170, 0, 255).astype(np.uint8)
    return Image.fromarray(out)


def upscale(img: Image.Image) -> Image.Image:
    if img.width >= TARGET_WIDTH:
        return img
    ratio = TARGET_WIDTH / img.width
    return img.resize((TARGET_WIDTH, int(img.height * ratio)), Image.LANCZOS)


def deskew_angle(img: Image.Image) -> float:
    """Coarse skew estimate from horizontal projection variance (fast, no cv2)."""
    try:
        import cv2  # type: ignore

        # Estimate on a thumbnail: 9 rotations of a full page is far too slow.
        thumb = img.copy()
        thumb.thumbnail((500, 500))
        arr = np.asarray(ImageOps.grayscale(thumb)).astype(np.uint8)
        inv = 255 - arr
        best_angle, best_score = 0.0, -1.0
        for angle in np.arange(-2.0, 2.1, 0.5):
            m = cv2.getRotationMatrix2D((inv.shape[1] / 2, inv.shape[0] / 2), float(angle), 1.0)
            rot = cv2.warpAffine(inv, m, (inv.shape[1], inv.shape[0]), flags=cv2.INTER_NEAREST,
                                 borderValue=0)
            projection = rot.sum(axis=1)
            score = float(np.var(projection))
            if score > best_score:
                best_angle, best_score = float(angle), score
        return best_angle
    except Exception:
        return 0.0


BLUR_MIN = 100.0  # Laplacian variance; the specimen pack scores ~930+, a blurred photo ~1


def blur_score(source: str | Path | bytes) -> float:
    """Sharpness of the original image (higher = sharper)."""
    import cv2  # type: ignore

    arr = np.asarray(ImageOps.grayscale(load(source))).astype(np.uint8)
    return float(cv2.Laplacian(arr, cv2.CV_64F).var())


def prepare_for_ocr(source: str | Path | bytes) -> Image.Image:
    img = load(source)
    img = strip_watermark(img)
    img = upscale(img)
    angle = deskew_angle(img)
    if abs(angle) >= 0.5:
        img = img.rotate(angle, resample=Image.BICUBIC, fillcolor="white", expand=False)
    return binarise(img)
