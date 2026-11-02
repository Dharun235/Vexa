"""Command descriptions shared by shell help and the interactive console."""

TOPICS = {
    "load": 'load "image.jpg" — use the image supplied with --image; clear prior results.',
    "detect": "detect person / detect all — find objects in the current image using CPU inference. Optional: detect person confidence 0.7 (0 to 1; default 0.25).",
    "count": "count person / count all — count the latest object detections.\ncount text — count OCR text lines after ocr.",
    "draw": "draw boxes — annotate object detections.\ndraw text — outline and number OCR text regions.",
    "print": 'print "Hello" — print literal text.\nprint person — count objects.\nprint text — print the latest OCR text.',
    "show": "show image — save the current image to the --output PNG path.",
    "ocr": "ocr — read text from the current image using offline ONNX CPU models.\nUse print text, count text, or draw text afterwards. Best tested with clear printed English.",
    "scan": "scan codes — decode QR codes and barcodes; print their format and content. Does not open links.",
    "find": 'find text "TOTAL" — case-insensitive literal search in the latest OCR lines; prints matches and positions. Run ocr first.',
    "inspect": "inspect image — report working-image dimensions, channels, color order and pixel type.",
    "check": "check blur — report a Laplacian detail score and a rough blur assessment; not a quality guarantee.",
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
