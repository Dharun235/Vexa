import base64
from dataclasses import asdict

import cv2

from vexa.ast_nodes import VexaError
from vexa.parser import parse
from vexa.vision import draw_boxes


def execute(source, uploaded_image, vision):
    return execute_commands(parse(source), uploaded_image, vision)


def execute_commands(commands, uploaded_image, vision):
    image = None
    detections = []
    detected = False
    counts = {}
    logs = []
    shown = None
    for command in commands:
        kind, target = command.kind, command.argument
        try:
            if kind == "load":
                image = uploaded_image.copy()
                detections, counts, detected, shown = [], {}, False, None
                logs.append(f'Loaded image as "{target}" ({image.shape[1]} × {image.shape[0]}).')
            elif kind == "print_text":
                logs.append(target)
            else:
                if image is None:
                    raise VexaError('Load your image first: load "image.jpg"')
                if kind == "detect":
                    detections = vision.detect(image, target)
                    detected, counts = True, {}
                    logs.append(f"Detected {len(detections)} object(s) matching {target}.")
                elif kind in {"count", "print_count", "draw"}:
                    if not detected:
                        raise VexaError("Run detect before counting or drawing objects.")
                    if kind == "draw":
                        image = draw_boxes(image, detections)
                        logs.append(f"Drew {len(detections)} bounding box(es).")
                    else:
                        value = sum(target == "all" or item.label == target for item in detections)
                        counts[target] = value
                        logs.append(f"{target}: {value}")
                elif kind == "show":
                    success, encoded = cv2.imencode(".png", image)
                    if not success:
                        raise VexaError("Could not encode the result image.")
                    shown = "data:image/png;base64," + base64.b64encode(encoded).decode()
                    logs.append("Displayed image.")
        except VexaError as exc:
            exc.line = command.line
            raise
    return {
        "logs": logs,
        "counts": counts,
        "image": shown,
        "detections": [asdict(item) for item in detections],
    }
