"""OCR adapter: Tesseract if the binary exists, else RapidOCR (ONNX, pip-only).

Both return the same `Token` shape (text + box + confidence), so extraction and
validation do not care which engine ran.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass

import numpy as np
from PIL import Image

_engine_name: str | None = None
_rapid = None


@dataclass
class Token:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    conf: float
    slope: float = 0.0   # dy/dx of the text line's top edge (page skew)

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2


def engine() -> str:
    global _engine_name
    if _engine_name is not None:
        return _engine_name
    if shutil.which("tesseract"):
        _engine_name = "tesseract"
    else:
        try:
            from rapidocr_onnxruntime import RapidOCR  # noqa: F401

            _engine_name = "rapidocr"
        except Exception:
            try:
                from rapidocr import RapidOCR  # noqa: F401

                _engine_name = "rapidocr-new"
            except Exception:
                _engine_name = "none"
    return _engine_name


def _tokens_tesseract(img: Image.Image) -> list[Token]:
    import pytesseract
    from pytesseract import Output

    data = pytesseract.image_to_data(img, config="--psm 6", output_type=Output.DICT)
    tokens: list[Token] = []
    for i, text in enumerate(data["text"]):
        if not str(text).strip():
            continue
        try:
            conf = float(data["conf"][i]) / 100.0
        except (TypeError, ValueError):
            conf = 0.0
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        tokens.append(Token(str(text).strip(), float(x), float(y), float(x + w), float(y + h), conf))
    return tokens


def _rapid_instance():
    global _rapid
    if _rapid is None:
        try:
            from rapidocr_onnxruntime import RapidOCR

            _rapid = RapidOCR()
        except Exception:
            from rapidocr import RapidOCR as RapidOCRNew

            _rapid = RapidOCRNew()
    return _rapid


def _slope(box) -> float:
    """Top edge of a RapidOCR quadrilateral (top-left -> top-right)."""
    (x0, y0), (x1, y1) = box[0][:2], box[1][:2]
    return (float(y1) - float(y0)) / (float(x1) - float(x0)) if float(x1) - float(x0) > 1 else 0.0


def _tokens_rapid(img: Image.Image) -> list[Token]:
    result = _rapid_instance()(np.asarray(img.convert("RGB")))
    payload = result[0] if isinstance(result, tuple) else result
    tokens: list[Token] = []
    if payload is None:
        return tokens
    # rapidocr-onnxruntime: [[box, text, score], ...]
    if isinstance(payload, (list, tuple)):
        for item in payload:
            try:
                box, text, score = item[0], item[1], item[2]
            except (TypeError, IndexError):
                continue
            xs = [float(p[0]) for p in box]
            ys = [float(p[1]) for p in box]
            tokens.append(Token(str(text).strip(), min(xs), min(ys), max(xs), max(ys), float(score),
                                _slope(box)))
        return tokens
    # rapidocr >=2 object API
    boxes = getattr(payload, "boxes", None) or []
    txts = getattr(payload, "txts", None) or []
    scores = getattr(payload, "scores", None) or []
    for box, text, score in zip(boxes, txts, scores):
        xs = [float(p[0]) for p in box]
        ys = [float(p[1]) for p in box]
        tokens.append(Token(str(text).strip(), min(xs), min(ys), max(xs), max(ys), float(score)))
    return tokens


def read(img: Image.Image) -> list[Token]:
    name = engine()
    if name == "tesseract":
        return _tokens_tesseract(img)
    if name in {"rapidocr", "rapidocr-new"}:
        return _tokens_rapid(img)
    return []


def status() -> dict:
    name = engine()
    return {
        "engine": name,
        "available": name != "none",
        "note": (
            "Tesseract binary detected"
            if name == "tesseract"
            else "RapidOCR (ONNX) - no system binary required"
            if name != "none"
            else "No OCR engine installed; uploads fall back to manual field entry"
        ),
    }
