"""Language values: numbers, text, true/false, objects and lists of objects.

The interpreter and compiled programs share these, so both give the same answers.
Object properties such as colour or distance are measured the first time they
are read and then kept.
"""

import math

from vexa.ast_nodes import VexaError

# Property name → type, for the checker and for bare names inside where.
PROPERTIES = {
    "label": "text",
    "name": "text",
    "confidence": "number",
    "x": "number",
    "y": "number",
    "width": "number",
    "height": "number",
    "area": "number",
    "colour": "text",
    "color": "text",
    "position": "text",
    "distance": "number",
    "posture": "text",
    "text": "text",
}
PICKS = ("first", "last", "largest", "smallest", "nearest", "farthest")


class VObject:
    """One detected object as a value; session supplies the image and models."""

    __slots__ = ("cache", "detection", "generation", "name", "session")

    def __init__(self, session, detection, name):
        self.session, self.detection, self.name = session, detection, name
        self.generation = session.generation
        self.cache = {}

    def __repr__(self):
        return self.name

    def get(self, prop):
        if self.generation != self.session.generation:
            raise VexaError(
                f"{self.name} belongs to an earlier image: the image changed since it was found."
            )
        if prop not in PROPERTIES:
            raise VexaError(f'Objects have no property "{prop}".')
        prop = "colour" if prop == "color" else prop
        if prop not in self.cache:
            self.cache[prop] = self._measure(prop)
        return self.cache[prop]

    def _measure(self, prop):
        x1, y1, x2, y2 = self.detection.box
        if prop == "label":
            return self.detection.label
        if prop == "name":
            return self.name
        if prop == "confidence":
            return round(float(self.detection.confidence), 3)
        if prop == "x":
            return (x1 + x2) / 2
        if prop == "y":
            return (y1 + y2) / 2
        if prop == "width":
            return float(x2 - x1)
        if prop == "height":
            return float(y2 - y1)
        if prop == "area":
            return float((x2 - x1) * (y2 - y1))
        return self.session.measure_object(self, prop)


def type_of(value):
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "text"
    if isinstance(value, VObject):
        return "object"
    if isinstance(value, list):
        return "objects"
    return "nothing"


def show(value):
    """Text form of a value for print, strings and CSV."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if math.isfinite(value) and value == int(value):
            return str(int(value))
        return f"{value:.4g}" if abs(value) < 1e6 else f"{value:.6g}"
    if isinstance(value, list):
        return ", ".join(item.name for item in value) or "nothing"
    if value is None:
        return "nothing"
    return str(value)


def record_value(value):
    """CSV cells keep numbers and text; objects become their names."""
    if isinstance(value, float) and math.isfinite(value) and value == int(value):
        return int(value)
    if isinstance(value, (VObject, list)) or value is None:
        return show(value)
    return value


def add(left, right):
    if isinstance(left, str) or isinstance(right, str):
        return show(left) + show(right)
    return left + right


def divide(left, right):
    if right == 0:
        raise VexaError("Division by zero.")
    return left / right


def modulo(left, right):
    if right == 0:
        raise VexaError("Division by zero.")
    return left % right


def equal(left, right):
    """== ignores case for text, so "Car" == "car"."""
    if isinstance(left, str) and isinstance(right, str):
        return left.casefold() == right.casefold()
    return left == right


def compare(operator, left, right):
    if operator == "==":
        return equal(left, right)
    if operator == "!=":
        return not equal(left, right)
    if isinstance(left, str) and isinstance(right, str):
        left, right = left.casefold(), right.casefold()
    return {"<": left < right, "<=": left <= right, ">": left > right, ">=": left >= right}[
        operator
    ]


def pick(word, items):
    """first, last, largest, smallest, nearest or farthest of a list; nothing if empty."""
    if not items:
        raise VexaError(f"{word} of an empty list: there is no object to pick.")
    if word == "first":
        return items[0]
    if word == "last":
        return items[-1]
    if word in ("largest", "smallest"):
        choose = max if word == "largest" else min
        return choose(items, key=lambda item: item.get("area"))
    choose = max if word == "nearest" else min
    return choose(items, key=lambda item: item.get("distance"))
