"""Geometric image operations: rotate, flip, resize, scale, crop and move."""

import cv2
import numpy as np

from vexa.ast_nodes import VexaError

MAX_PIXELS = 20_000_000
_QUARTER_TURNS = {
    90: cv2.ROTATE_90_COUNTERCLOCKWISE,
    180: cv2.ROTATE_180,
    270: cv2.ROTATE_90_CLOCKWISE,
}


def rotate(image, degrees):
    """Counterclockwise; quarter turns are lossless, other angles enlarge the canvas."""
    turn = degrees % 360
    if turn == 0:
        return image.copy()
    if turn in _QUARTER_TURNS:
        return cv2.rotate(image, _QUARTER_TURNS[turn])
    height, width = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), degrees, 1.0)
    cos, sin = abs(matrix[0, 0]), abs(matrix[0, 1])
    new_width, new_height = int(height * sin + width * cos), int(height * cos + width * sin)
    _check_size(new_width, new_height)
    matrix[0, 2] += new_width / 2 - width / 2
    matrix[1, 2] += new_height / 2 - height / 2
    return cv2.warpAffine(image, matrix, (new_width, new_height), flags=cv2.INTER_LINEAR)


def resize(image, width, height):
    """Resize to width × height pixels, ignoring the aspect ratio; at most 20 MP."""
    width, height = round(width), round(height)
    _check_size(width, height)
    shrinking = width * height < image.shape[0] * image.shape[1]
    return cv2.resize(
        image, (width, height), interpolation=cv2.INTER_AREA if shrinking else cv2.INTER_LINEAR
    )


def scale(image, factor):
    """Resize by factor on both sides, keeping the aspect ratio."""
    height, width = image.shape[:2]
    return resize(image, max(1, width * factor), max(1, height * factor))


def crop(image, x1, y1, x2, y2):
    """Return the (x1, y1, x2, y2) pixel area, clipped to the image."""
    height, width = image.shape[:2]
    x1, x2 = sorted((int(np.clip(x1, 0, width)), int(np.clip(x2, 0, width))))
    y1, y2 = sorted((int(np.clip(y1, 0, height)), int(np.clip(y2, 0, height))))
    if x2 - x1 < 1 or y2 - y1 < 1:
        raise VexaError(f"The crop area lies outside the {width} × {height} image.")
    return image[y1:y2, x1:x2].copy()


def move(image, dx, dy):
    """Shift right by dx and down by dy pixels; uncovered areas become black."""
    height, width = image.shape[:2]
    matrix = np.float32([[1, 0, dx], [0, 1, dy]])
    return cv2.warpAffine(image, matrix, (width, height))


def _check_size(width, height):
    if width < 1 or height < 1:
        raise VexaError("The image must stay at least 1 × 1 pixel.")
    if width * height > MAX_PIXELS:
        raise VexaError("The result would exceed 20 megapixels.")


def apply(image, kind, numbers):
    """Apply one operation by name, e.g. "rotate" or "flip_horizontal", to image.

    numbers are the operation's arguments after the image, e.g. (90,) for rotate.
    """
    if kind == "flip_horizontal":
        return cv2.flip(image, 1)
    if kind == "flip_vertical":
        return cv2.flip(image, 0)
    return {"rotate": rotate, "resize": resize, "scale": scale, "crop": crop, "move": move}[kind](
        image, *numbers
    )
