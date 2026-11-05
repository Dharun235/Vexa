"""Command descriptions shared by shell help and the interactive console."""

TOPICS = {
    "load": 'load "image.jpg" — start again from the original image (from --image, or the current image inside a for each loop) and clear prior results. The quoted name is only a label.',
    "detect": "detect person / detect all — find objects in the current image using CPU inference. Optional: detect person confidence 0.7 (0 to 1; default 0.25).\ndetect face — find faces with the YuNet face detector (after vexa model download faces, 232 KB; default confidence 0.6).",
    "count": 'count person / count all — count the latest object detections.\ncount text — count OCR text lines after ocr.\ncount masks — count nonempty masks after segment detections.\ncount pose standing — count people in a posture after estimate poses: standing, sitting, lying, "hand up" or "hands up".\ncount colour red car — count objects of a colour after colour car.\ncount car in left — count objects whose centre is in the left, right, top or bottom half, or the centre third.\ncount person left of car — count objects left of, right of, above or below another object.',
    "draw": "draw boxes — annotate object detections.\ndraw car / draw big — draw only one label, or the objects in a variable.\ndraw text — outline and number OCR text regions.\ndraw masks — overlay the latest segmentation masks.\ndraw depth — replace the image with its depth map (bright is near, dark is far) after estimate depth.\ndraw poses — draw each person's skeleton after estimate poses.",
    "print": 'print "Hello" — print literal text, with {expression} placeholders: print "{n} cars".\nprint EXPR — print any value: print n * 2, print car.colour.\nprint person — count objects (when no variable is named person).\nprint text — print the latest OCR text.\nprint masks — count the latest nonempty masks.',
    "show": "show image — save the current image to the --output PNG path.",
    "ocr": "ocr — read text from the current image using offline ONNX CPU models.\nUse print text, count text, or draw text afterwards. Best tested with clear printed English.",
    "caption": 'caption — describe the image in one sentence with Florence-2 on CPU (after vexa model download florence, about 275 MB). caption detailed — a few sentences. Then record caption, or if caption contains "dog" … end.',
    "locate": 'locate "red tie" — find regions matching any phrase with Florence-2 grounding, as detections labelled with the phrase: count "red tie", draw boxes, blur, measure and rank work on them. Slower than detect (about 2.5 s) but understands colours, parts and descriptions.',
    "blur": 'blur face / blur person / blur "license plate" — blur every object of that label in the latest detections so it cannot be recognised; follows the outline after segment detections. Use show image to save it.',
    "pixelate": "pixelate face — like blur, with large square blocks.",
    "segment": "segment detections — turn the latest object boxes into masks with EfficientSAM on CPU (up to 32). Models load only when needed; image embeddings are reused.",
    "scan": "scan codes — decode QR codes and barcodes; print their format and content. Does not open links.",
    "find": 'find text "TOTAL" — case-insensitive literal search in the latest OCR lines; prints matches and positions. Run ocr first.',
    "inspect": "inspect image — report working-image dimensions, channels, color order and pixel type.",
    "check": "check blur — report a Laplacian detail score and a rough blur assessment; not a quality guarantee.\ncheck exposure — report brightness (0 black, 1 white) and whether the image looks dark or bright. Then if image blurry / if image dark / if image bright … end.",
    "colour": "colour car / colour all — name the main colour of each detected object: red, orange, yellow, green, blue, purple, pink, brown, black, gray or white (also spelled color). Uses masks after segment detections. Then count colour red car or record colours. Lighting and shadows can shift colours.",
    "where": 'where car / where all — say where each detected object is on a 3 × 3 grid: top left, top, top right, left, centre, right, bottom left, bottom or bottom right.\nLIST where CONDITION — keep the objects for which the condition holds, e.g. detections where colour == "red" and width > 100.',
    "remove": "remove background — make everything but the main subject transparent with U²-Net-p on CPU (after vexa model download background, 4.6 MB). After segment detections it keeps exactly the segmented objects instead, with no model. show image saves a transparent PNG. Use it after rotate, crop and style.",
    "if": 'if count person > 3 … end — run the indented commands only when the condition holds; optional else. Conditions: count LABEL / count text / count masks / count codes / count pose POSTURE compared with < <= > >= == !=, or text contains "TOTAL", or caption contains "dog", or image blurry / image dark / image bright. Counts can use colour, area and relation subjects: count colour red car, count car in left, count person left of car. Any true/false expression works: if people > 2 and not image dark; chain with else if.',
    "for": 'for each car in detections … end — run the commands once per object in a list; the loop may not change the image.\nfor each image in "photos/" … end — run the commands once per JPEG, PNG or WebP image in the folder; each image starts loaded. Not nested.\nfor each frame in "clip.mp4" every 1 second — the same for video frames, closed with end (.mp4, .mov, .avi, .mkv, .webm); each row is named by its time, e.g. 2s.',
    "reference": 'reference "coin" 23.25 mm — detect a reference object of known size (its longest side; units mm, cm or m) so measure reports real units instead of pixels.',
    "measure": 'measure bolt — width × height of every bolt in the latest detections.\nmeasure gap between "bolt" and "nut" — shortest edge-to-edge gap between them (two of the same label works too). Pixels, or real units after reference.',
    "estimate": "estimate depth — predict how far every pixel is from the camera with Depth Anything V2 Small on CPU (after vexa model download depth, 27 MB). Relative only: closeness 1 is the nearest point, 0 the farthest; no metres. Cleared by transforms.\nestimate poses — find 17 body keypoints for every detected person with RTMPose-s on CPU (after detect person, and vexa model download pose, 20 MB). Reports joint angles and postures: standing, sitting, lying, hand up, hands up. Postures are simple rules on the keypoints.",
    "rank": "rank person by distance / rank all by distance — order the latest detections nearest first by closeness (0 to 1), after estimate depth and detect. Uses masks after segment detections, which is more exact for overlapping objects.",
    "export": 'export points "scene.ply" — save the image as a coloured 3D point cloud from its depth (relative scale; opens in MeshLab or Blender), after estimate depth.',
    "record": "record count person / record count text / record text / record codes / record measurements / record distances / record poses / record count pose sitting / record caption / record colours / record count colour red car / record share = cars / people — add a column to the current image's row of results.",
    "save": 'save csv "results.csv" — write all recorded rows to a CSV file (relative path). Use after a for each loop.',
    "rotate": "rotate 90 — turn the image counterclockwise by any angle (negative turns clockwise). 90, 180 and 270 are lossless; other angles enlarge the canvas. Clears earlier results.",
    "flip": "flip horizontal / flip vertical — mirror the image, which also mirrors text. For an upside-down image use rotate 180 instead. Clears earlier results.",
    "resize": "resize 640 480 — set the exact width and height in pixels. scale 0.5 — resize by a factor, keeping the shape. Clears earlier results.",
    "crop": "crop 100 50 400 300 — keep the rectangle from x1 y1 to x2 y2 (pixels, clipped to the image). Clears earlier results.",
    "move": "move 20 -10 — shift the image right by 20 and up by 10 pixels; uncovered areas turn black. Clears earlier results.",
    "style": "style sketch — restyle the image: sketch, cartoon, paint, enhance, denoise or gray (OpenCV), or mosaic, candy, udnie, rain or pointillism (neural style transfer, after vexa model download styles). Use show image to save it. Clears earlier results.",
    "translate": "translate horse to zebra — change what the image shows with a CycleGAN model: horse to zebra, zebra to horse, summer to winter, winter to summer, apple to orange, orange to apple, photo to monet / vangogh / cezanne / ukiyoe. Each needs vexa model download NAME once (45 MB, e.g. horse2zebra). Use show image to save it. Clears earlier results.",
    "let": 'let people = count person — set a variable: numbers, text, true/false, an object or a list of objects. Arithmetic + - * / %, comparisons, and / or / not, and "{people} people" placeholders in strings. Setting it again updates it; its type cannot change.',
    "define": 'define crowd(n: number) … return "busy" … end — define a function at the top level; call it as a command (crowd(3)) or in an expression (let level = crowd(3)). Parameter types: number, text, bool, object, objects. A function sees only its parameters and own variables, and works on the current image.',
    "return": "return EXPR — end a function call with a value; return alone ends it with nothing.",
    "detections": 'detections — the latest detections as objects (car 1, car 2 …), e.g. for each thing in detections, detections where colour == "red", largest detections. Properties: label, name, confidence, x, y, width, height, area, colour, position, distance, posture, text.',
    "help": "help / help ocr — show commands or details. Also available as vexa help [topic].",
    "exit": "exit / quit / :quit — leave the interactive console. Not a .vexa program command.",
    "reset": ":reset — clear session results; retain the original input image and loaded models.",
}


TOPICS["scale"] = TOPICS["resize"]
TOPICS["color"] = TOPICS["colour"]


def help_text(topic=None):
    if topic:
        return TOPICS.get(
            topic.lower(), f'Unknown help topic "{topic}". Use help to list commands.'
        )
    unique = dict.fromkeys(TOPICS.values())  # scale shares the resize entry
    return "Vexa commands (use vexa --help for shell options)\n" + "\n".join(unique)
