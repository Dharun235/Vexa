"""Small CPU image queries; no model sessions or image edits."""

import logging

import cv2
import numpy as np

from vexa.ast_nodes import VexaError


def scan_codes(image):
    """Read the QR codes and barcodes in an image.

    Returns:
        A list of dicts with the decoded ``text``, the ``format`` name and the
        ``box``: four [x, y] pixel corners, clockwise from the top left.
    """
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
    """Return the image's width, height, channel count, colour order and dtype."""
    height, width = image.shape[:2]
    return {
        "width": width,
        "height": height,
        "channels": image.shape[2],
        "color_order": "BGR",
        "dtype": str(image.dtype),
    }


def check_blur(image):
    """Score sharpness as the variance of the Laplacian; below 100 is possibly blurry.

    Large images are first shrunk so the longer side is at most 1024 pixels, so
    scores are comparable between photos of different sizes.
    """
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


def check_exposure(image):
    """Mean brightness and the share of near-black and near-white pixels."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    brightness = float(gray.mean()) / 255
    dark_share = float((gray < 30).mean())
    bright_share = float((gray > 225).mean())
    return {
        "brightness": round(brightness, 3),
        "dark_share": round(dark_share, 3),
        "bright_share": round(bright_share, 3),
        "dark": brightness < 0.25 or dark_share > 0.5,
        "bright": brightness > 0.8 or bright_share > 0.5,
    }


COLOURS = ("red", "orange", "yellow", "green", "blue", "purple", "pink", "brown", "black", "gray", "white")  # fmt: skip
MAX_COLOUR_PIXELS = 4000


def name_colour(bgr):
    """A plain colour name for one BGR value, from simple hue, saturation and value rules."""
    hue, saturation, value = (
        int(v) for v in cv2.cvtColor(np.uint8([[bgr]]), cv2.COLOR_BGR2HSV)[0, 0]
    )
    degrees = hue * 2
    if value < 50:
        return "black"
    if saturation < 45:
        return "white" if value > 190 else "black" if value < 70 else "gray"
    if degrees < 12 or degrees >= 340:
        return "pink" if saturation < 130 and value > 170 else "red"
    if degrees < 40:
        return "brown" if value < 150 else "orange"
    if degrees < 70:
        return "brown" if value < 110 else "yellow"
    if degrees < 165:
        return "green"
    if degrees < 260:
        return "blue"
    if degrees < 290:
        return "purple"
    return "pink"


def colour_of(image, box, mask=None):
    """Main colour of an object: the largest k-means cluster of its pixels, named.

    Uses the mask's pixels when there is one, otherwise the middle 60% of the box,
    which holds less background.
    """
    if mask is not None:
        x1, y1, x2, y2 = mask.box
        pixels = image[y1:y2, x1:x2][mask.pixels[: y2 - y1, : x2 - x1]]
    else:
        x1, y1, x2, y2 = box
        dx, dy = (x2 - x1) // 5, (y2 - y1) // 5
        pixels = image[y1 + dy : max(y1 + dy + 1, y2 - dy), x1 + dx : max(x1 + dx + 1, x2 - dx)]
        pixels = pixels.reshape(-1, 3)
    if not len(pixels):
        return None, None
    step = max(1, len(pixels) // MAX_COLOUR_PIXELS)
    samples = np.float32(pixels[::step])
    clusters = min(3, len(samples))
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    cv2.setRNGSeed(0)  # the same image always gives the same colour
    _, labels, centres = cv2.kmeans(samples, clusters, None, criteria, 2, cv2.KMEANS_PP_CENTERS)
    main = centres[np.bincount(labels.ravel(), minlength=clusters).argmax()]
    bgr = tuple(round(float(v)) for v in main)
    return name_colour(bgr), bgr


AREAS = ("left", "right", "top", "bottom", "centre", "center")
RELATIONS = ("left of", "right of", "above", "below")


def _centre(box):
    return (box[0] + box[2]) / 2, (box[1] + box[3]) / 2


def in_area(box, area, width, height):
    """Halves for left, right, top and bottom; the middle third both ways for centre."""
    x, y = _centre(box)
    if area in ("centre", "center"):
        return width / 3 <= x <= 2 * width / 3 and height / 3 <= y <= 2 * height / 3
    return {
        "left": x < width / 2,
        "right": x > width / 2,
        "top": y < height / 2,
        "bottom": y > height / 2,
    }[area]


def related(box, other, relation):
    """True when the centre of box lies past the matching edge of other."""
    x, y = _centre(box)
    return {
        "left of": x < other[0],
        "right of": x > other[2],
        "above": y < other[1],
        "below": y > other[3],
    }[relation]


def where(box, width, height):
    """Position on a 3 × 3 grid in words, e.g. "top left" or "centre"."""
    x, y = _centre(box)
    row = ("top", "middle", "bottom")[min(2, int(3 * y / height))]
    column = ("left", "centre", "right")[min(2, int(3 * x / width))]
    if row == "middle":
        return column
    return row if column == "centre" else f"{row} {column}"


def overlap(box, other):
    """Intersection over union of two boxes: 1 is the same box, 0 is apart."""
    x1, y1 = max(box[0], other[0]), max(box[1], other[1])
    x2, y2 = min(box[2], other[2]), min(box[3], other[3])
    inner = max(0, x2 - x1) * max(0, y2 - y1)
    area = (box[2] - box[0]) * (box[3] - box[1]) + (other[2] - other[0]) * (other[3] - other[1])
    return inner / (area - inner) if area > inner else 0.0


def changed_share(image, other):
    """Share of pixels (0 to 1) that clearly differ from another photo of the same view."""
    height, width = image.shape[:2]
    other = cv2.resize(other, (width, height), interpolation=cv2.INTER_AREA)
    first, second = (
        cv2.GaussianBlur(cv2.cvtColor(item, cv2.COLOR_BGR2GRAY), (5, 5), 0)
        for item in (image, other)
    )
    return round(float((cv2.absdiff(first, second) > 30).mean()), 3)


def draw_zones(image, zones):
    """Outline each zone and write its name."""
    image = image.copy()
    height, width = image.shape[:2]
    for name, (x1, y1, x2, y2) in zones.items():
        top_left = (round(x1 * (width - 1)), round(y1 * (height - 1)))
        bottom_right = (round(x2 * (width - 1)), round(y2 * (height - 1)))
        cv2.rectangle(image, top_left, bottom_right, (0, 200, 255), 2)
        cv2.putText(
            image,
            name,
            (top_left[0] + 4, top_left[1] + 18),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 200, 255),
            2,
        )
    return image
