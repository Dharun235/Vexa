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
    "for": 'for each image in "photos/" … end — run the commands once per JPEG, PNG or WebP image in the folder; each image starts loaded. Not nested.',
    "record": "record count person / record count text / record text / record codes — add a column to the current image's row of results.",
    "save": 'save csv "results.csv" — write all recorded rows to a CSV file (relative path). Use after a for each loop.',
    "help": "help / help ocr — show commands or details. Also available as vexa help [topic].",
    "exit": "exit / quit / :quit — leave the interactive console. Not a .vexa program command.",
    "reset": ":reset — clear session results; retain the original input image and loaded models.",
}


def help_text(topic=None):
    if topic:
        return TOPICS.get(
            topic.lower(), f'Unknown help topic "{topic}". Use help to list commands.'
        )
    return "Vexa commands (use vexa --help for shell options)\n" + "\n".join(TOPICS.values())
