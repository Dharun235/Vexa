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
    """number, text, bool, object, objects, list[number], list[text], list[bool] or list[any]."""
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "text"
    if isinstance(value, VObject):
        return "object"
    if isinstance(value, list):
        if value and all(isinstance(item, VObject) for item in value):
            return "objects"
        return f"list[{type_of(value[0])}]" if value else "list[any]"
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
        if value and all(isinstance(item, VObject) for item in value):
            return ", ".join(item.name for item in value)
        if not value:
            return "nothing"
        return "[" + ", ".join(show(item) for item in value) + "]"
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
    if isinstance(left, list) and isinstance(right, list):
        return left + right
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
    """first, last, largest, smallest, nearest or farthest of a list."""
    if not items:
        raise VexaError(f"{word} of an empty list: there is nothing to pick.")
    if word == "first":
        return items[0]
    if word == "last":
        return items[-1]
    if not isinstance(items[0], VObject):  # numbers or text
        return max(items) if word == "largest" else min(items)
    if word in ("largest", "smallest"):
        choose = max if word == "largest" else min
        return choose(items, key=lambda item: item.get("area"))
    choose = max if word == "nearest" else min
    return choose(items, key=lambda item: item.get("distance"))


def index(items, position):
    """items[1] is the first item (like car 1); items[-1] is the last."""
    if position != int(position):
        raise VexaError(f"A list position must be a whole number, not {show(position)}.")
    position = int(position)
    if position == 0 or abs(position) > len(items):
        size = len(items)
        raise VexaError(
            f"Position {position} is outside the list of {size} item(s); positions start at 1."
        )
    return items[position - 1 if position > 0 else position]


# Built-in functions --------------------------------------------------------------


def _numbers(name, args):
    """min, max: one list of numbers, or several numbers."""
    items = args[0] if len(args) == 1 and isinstance(args[0], list) else list(args)
    if not items:
        raise VexaError(f"{name} of an empty list.")
    return items


def b_round(value, digits=0):
    return float(round(value, int(digits)))


def b_floor(value):
    return float(math.floor(value))


def b_ceil(value):
    return float(math.ceil(value))


def b_abs(value):
    return abs(value)


def b_sqrt(value):
    if value < 0:
        raise VexaError("sqrt of a negative number.")
    return math.sqrt(value)


def b_min(*args):
    return min(_numbers("min", args))


def b_max(*args):
    return max(_numbers("max", args))


def b_sum(items):
    return float(sum(items))


def b_average(items):
    if not items:
        raise VexaError("average of an empty list.")
    return sum(items) / len(items)


def b_length(value):
    return float(len(value))


def b_as_text(value):
    return show(value)


def b_as_number(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    try:
        return float(str(value).strip())
    except ValueError:
        raise VexaError(f'"{value}" is not a number.') from None


def b_upper(value):
    return value.upper()


def b_lower(value):
    return value.lower()


def b_sort(items):
    return sorted(items)


def b_reverse(items):
    return list(reversed(items))


def b_range(count):
    if count != int(count) or count < 0:
        raise VexaError(f"range needs a whole number of 0 or more, not {show(count)}.")
    if count > 100_000:
        raise VexaError("range is limited to 100,000 numbers.")
    return [float(n) for n in range(1, int(count) + 1)]


BUILTINS = {name[2:]: function for name, function in globals().items() if name.startswith("b_")}
