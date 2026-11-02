"""Small CPU image queries; no model sessions or image edits."""

import logging

import cv2

from vexa.ast_nodes import VexaError


def scan_codes(image):
    import zxingcpp

    try:
        results = zxingcpp.read_barcodes(image)
        return [
            {
                "text": item.text,
                "format": str(item.format),
                "box": [
                    [point.x, point.y]
                    for point in (
                        item.position.top_left,
                        item.position.top_right,
                        item.position.bottom_right,
                        item.position.bottom_left,
                    )
                ],
            }
            for item in results
            if item.valid
        ]
    except Exception as exc:
        logging.getLogger(__name__).exception("Code scanning failed")
        raise VexaError(
            "Code scanning failed. Rerun with --debug for details.", kind="vision"
        ) from exc


def inspect_image(image):
    height, width = image.shape[:2]
    return {
        "width": width,
        "height": height,
        "channels": image.shape[2],
        "color_order": "BGR",
        "dtype": str(image.dtype),
    }


def check_blur(image):
    # Bound work and give the heuristic a consistent maximum resolution.
    height, width = image.shape[:2]
    scale = min(1.0, 1024 / max(height, width))
    if scale < 1:
        image = cv2.resize(
            image,
            (max(1, round(width * scale)), max(1, round(height * scale))),
            interpolation=cv2.INTER_AREA,
        )
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    return {
        "score": score,
        "threshold": 100.0,
        "possibly_blurry": score < 100,
        "analysis_width": image.shape[1],
        "analysis_height": image.shape[0],
    }
