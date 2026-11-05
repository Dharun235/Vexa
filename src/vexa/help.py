"""Command descriptions shared by shell help and the interactive console."""

TOPICS = {
    "load": 'load "image.jpg" — start again from the original image (from --image, or the current image inside a for each loop) and clear prior results. The quoted name is only a label.',
    "detect": "detect person / detect all — find objects in the current image using CPU inference. Optional: detect person confidence 0.7 (0 to 1; default 0.25).\ndetect face — find faces with the YuNet face detector (after vexa model download faces, 232 KB; default confidence 0.6).",
    "count": 'count person / count all — count the latest object detections.\ncount text — count OCR text lines after ocr.\ncount masks — count nonempty masks after segment detections.\ncount pose standing — count people in a posture after estimate poses: standing, sitting, lying, "hand up" or "hands up".\ncount colour red car — count objects of a colour after colour car.\ncount car in left — count objects whose centre is in the left, right, top or bottom half, or the centre third.\ncount person left of car — count objects left of, right of, above or below another object.\ncount person in zone door — count objects whose centre is inside a zone.\ncount tracks — how many different objects track has followed so far.',
    "draw": "draw boxes — annotate object detections.\ndraw car / draw big — draw only one label, or the objects in a variable.\ndraw text — outline and number OCR text regions.\ndraw masks — overlay the latest segmentation masks.\ndraw depth — replace the image with its depth map (bright is near, dark is far) after estimate depth.\ndraw poses — draw each person's skeleton after estimate poses.\ndraw zones — outline every zone with its name.",
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
    "let": 'let people = count person — set a variable: numbers, text, true/false, objects, lists or maps. Arithmetic + - * / %, comparisons, in / not in, and / or / not, and "{people} people" placeholders in strings. Setting it again updates it; its type cannot change. Optional type: let n: number = 0.',
    "define": 'define crowd(n: number, limit: number = 3) -> text … return "busy" … end — define a function at the top level; call it as a command (crowd(3)) or in an expression (let level = crowd(3, 5)). Parameter types: number, text, bool, object, objects, list, map. Parameters with a default (a value or a const) may be left out; -> TYPE declares what it returns. A function sees its parameters, its own variables and the program\'s const and param values, and works on the current image.',
    "return": "return EXPR — end a function call with a value; return alone ends it with nothing.",
    "repeat": "repeat 3 times … end — run the commands a number of times (a whole number, at most 10,000).",
    "while": "while n < 100 … end — run the commands while the condition holds; stops with an error after 10,000 turns.",
    "expect": 'expect count person == 4, "four people" — check a condition: prints ✓ or ✗ and keeps going. vexa run exits with status 1 if any expect failed; vexa test FILE… reports them all.',
    "use": 'use "helpers.vexa" — import the functions of a library file (a file of define … end blocks), relative to the program\'s folder. use "helpers.vexa" as h — keep them apart: call h.crowd(3).',
    "lists": "[1, 2, 3] / xs[1] (the first item; xs[-1] is the last) / xs + [4] / x in xs / for each x in xs / length(xs) / [x * 2 for each x in xs if x > 1] / xs where it > 1. A list holds one kind of value; detections is a list of objects; a list can hold maps but not lists.",
    "functions": 'Built-in functions: round(x) / round(x, 2), floor, ceil, abs, sqrt, min(list) / min(a, b), max, sum(list), average(list), length(list, text or map), as_text(x), as_number(text), upper, lower, trim, split(text) / split(text, ","), join(list, ", "), replace(text, old, new), starts_with, ends_with, slice(list or text, start, end), index_of(list or text, item), sort(list), reverse(list), range(n) → [1 … n], keys(map), values(map), get(map, key, default), put(map, key, value), random(low, high), now(), read_lines(file), read_csv(file) → a list of maps.',
    "detections": 'detections — the latest detections as objects (car 1, car 2 …), e.g. for each thing in detections, detections where colour == "red", largest detections. Properties: label, name, confidence, x, y, width, height, area, colour, position, distance, posture, text, zone, id.',
    "const": "const LIMIT = 3 — a value that never changes; functions can read it. Write const and param at the top of the program. vexa compile puts the value where it is used.",
    "param": "param threshold = 0.5 — a value the user can set when running: vexa run p.vexa --set threshold=0.7. The default (a number, text or true/false) gives its type; functions can read it.",
    "maps": '{car: 3, "traffic light": 1} — text keys and one kind of value. m["car"] or m.car reads a value; "car" in m tests a key; m + {bus: 2} adds or replaces; keys(m), values(m), get(m, "bus", 0), put(m, "bus", 2), for each key in m. A computed key goes in brackets: {(thing.label): 1}.',
    "try": "try … else … end — run the commands; if one fails (a missing file, a position outside a list, a model error), run the else part instead, where error holds the message.",
    "break": "break — leave the loop around it now. continue — go on with the loop's next turn.",
    "zone": 'zone door 0.6 0.2 1 1 — name a rectangle by left, top, right and bottom as fractions of the image (0 to 1), so it fits any image size. Then count person in zone door, detections where zone == "door", draw zones.',
    "track": 'track person — after detect, give each person an id that stays the same from one video frame to the next (by box overlap). Then thing.id, and count tracks for how many different people were seen, e.g. for each frame in "clip.mp4" every 0.5 seconds … track person … end.',
    "compare": 'compare with "empty.jpg" — measure how much of the current image differs from another photo of the same view; then image change is the share (0 to 1), e.g. if image change > 0.05 … end.',
    "help": "help / help ocr — show commands or details. Also available as vexa help [topic].",
    "exit": "exit / quit / :quit — leave the interactive console. Not a .vexa program command.",
    "reset": ":reset — clear session results; retain the original input image and loaded models.",
}


TOPICS["scale"] = TOPICS["resize"]
TOPICS["color"] = TOPICS["colour"]
TOPICS["continue"] = TOPICS["break"]


def help_text(topic=None):
    """Return help for one command, or a list of all commands when no topic is given."""
    if topic:
        return TOPICS.get(
            topic.lower(), f'Unknown help topic "{topic}". Use help to list commands.'
        )
    unique = dict.fromkeys(TOPICS.values())  # scale shares the resize entry
    return "Vexa commands (use vexa --help for shell options)\n" + "\n".join(unique)
