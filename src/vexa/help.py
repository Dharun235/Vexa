"""Command descriptions shared by shell help and the interactive console."""

TOPICS = {
    "load": 'load "image.jpg" — start again from the original image (from --image, or the current image inside a for each loop) and clear prior results. The quoted name is only a label.',
    "detect": "detect person / detect all — find objects in the current image using CPU inference. Optional: detect person confidence 0.7 (0 to 1; default 0.25).",
    "count": "count person / count all — count the latest object detections.\ncount text — count OCR text lines after ocr.\ncount masks — count nonempty masks after segment detections.",
    "draw": "draw boxes — annotate object detections.\ndraw text — outline and number OCR text regions.\ndraw masks — overlay the latest segmentation masks.",
    "print": 'print "Hello" — print literal text.\nprint person — count objects.\nprint text — print the latest OCR text.\nprint masks — count the latest nonempty masks.',
    "show": "show image — save the current image to the --output PNG path.",
    "ocr": "ocr — read text from the current image using offline ONNX CPU models.\nUse print text, count text, or draw text afterwards. Best tested with clear printed English.",
    "segment": "segment detections — turn the latest object boxes into masks with EfficientSAM on CPU (up to 32). Models load only when needed; image embeddings are reused.",
    "scan": "scan codes — decode QR codes and barcodes; print their format and content. Does not open links.",
    "find": 'find text "TOTAL" — case-insensitive literal search in the latest OCR lines; prints matches and positions. Run ocr first.',
    "inspect": "inspect image — report working-image dimensions, channels, color order and pixel type.",
    "check": "check blur — report a Laplacian detail score and a rough blur assessment; not a quality guarantee.",
    "if": 'if count person > 3 … end — run the indented commands only when the condition holds; optional else. Conditions: count LABEL / count text / count masks / count codes compared with < <= > >= == !=, or text contains "TOTAL".',
    "for": 'for each image in "photos/" … end — run the commands once per JPEG, PNG or WebP image in the folder; each image starts loaded. Not nested.\nfor each frame in "clip.mp4" every 1 second — the same for video frames, closed with end (.mp4, .mov, .avi, .mkv, .webm); each row is named by its time, e.g. 2s.',
    "reference": 'reference "coin" 23.25 mm — detect a reference object of known size (its longest side; units mm, cm or m) so measure reports real units instead of pixels.',
    "measure": 'measure bolt — width × height of every bolt in the latest detections.\nmeasure gap between "bolt" and "nut" — shortest edge-to-edge gap between them (two of the same label works too). Pixels, or real units after reference.',
    "record": "record count person / record count text / record text / record codes / record measurements — add a column to the current image's row of results.",
    "save": 'save csv "results.csv" — write all recorded rows to a CSV file (relative path). Use after a for each loop.',
    "rotate": "rotate 90 — turn the image counterclockwise by any angle (negative turns clockwise). 90, 180 and 270 are lossless; other angles enlarge the canvas. Clears earlier results.",
    "flip": "flip horizontal / flip vertical — mirror the image, which also mirrors text. For an upside-down image use rotate 180 instead. Clears earlier results.",
    "resize": "resize 640 480 — set the exact width and height in pixels. scale 0.5 — resize by a factor, keeping the shape. Clears earlier results.",
    "crop": "crop 100 50 400 300 — keep the rectangle from x1 y1 to x2 y2 (pixels, clipped to the image). Clears earlier results.",
    "move": "move 20 -10 — shift the image right by 20 and up by 10 pixels; uncovered areas turn black. Clears earlier results.",
    "style": "style sketch — restyle the image: sketch, cartoon, paint, enhance, denoise or gray (OpenCV), or mosaic, candy, udnie, rain or pointillism (neural style transfer, after vexa model download styles). Use show image to save it. Clears earlier results.",
    "help": "help / help ocr — show commands or details. Also available as vexa help [topic].",
    "exit": "exit / quit / :quit — leave the interactive console. Not a .vexa program command.",
    "reset": ":reset — clear session results; retain the original input image and loaded models.",
}


TOPICS["scale"] = TOPICS["resize"]


def help_text(topic=None):
    if topic:
        return TOPICS.get(
            topic.lower(), f'Unknown help topic "{topic}". Use help to list commands.'
        )
    unique = dict.fromkeys(TOPICS.values())  # scale shares the resize entry
    return "Vexa commands (use vexa --help for shell options)\n" + "\n".join(unique)
