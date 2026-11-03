"""Render the synthetic benchmark images. Ground truth is the text drawn here.

Run from the repository root: uv run python benchmarks/vision-qa/make_images.py
"""

from pathlib import Path

import cv2
import numpy as np
import zxingcpp

OUT = Path(__file__).parent / "images"
EXAMPLES = Path(__file__).parents[2] / "examples"


def text_card(name, lines, size=(900, 120 + 70 * 4)):
    image = np.full((size[1], size[0], 3), 255, np.uint8)
    for row, line in enumerate(lines):
        cv2.putText(
            image,
            line,
            (40, 80 + 70 * row),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.4,
            (20, 20, 20),
            3,
            cv2.LINE_AA,
        )
    cv2.imwrite(str(OUT / name), image)


def code_card(name, codes):
    tiles = []
    for content, fmt in codes:
        barcode = zxingcpp.create_barcode(content, getattr(zxingcpp.BarcodeFormat, fmt))
        tile = np.array(zxingcpp.write_barcode_to_image(barcode, scale=4))
        if fmt != "QRCode":
            tile = cv2.resize(tile, (tile.shape[1], 120), interpolation=cv2.INTER_NEAREST)
        side = max(tile.shape)
        tile = cv2.copyMakeBorder(
            tile,
            (side - tile.shape[0]) // 2 + 20,
            (side - tile.shape[0] + 1) // 2 + 20,
            20,
            20,
            cv2.BORDER_CONSTANT,
            value=255,
        )
        tiles.append(cv2.resize(tile, (380, 380), interpolation=cv2.INTER_NEAREST))
    cv2.imwrite(str(OUT / name), cv2.cvtColor(np.hstack(tiles), cv2.COLOR_GRAY2BGR))


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    text_card(
        "invoice.png",
        ["ACME TOOLS AB", "INVOICE NO 4821", "DUE DATE 2026-12-01", "TOTAL 88.20 EUR"],
    )
    text_card("part_label.png", ["PART 7731-B", "SERIAL SN77A12290", "LOT 2611"])
    text_card("display.png", ["PUMP 3", "PRESSURE 4.2 BAR"])
    code_card(
        "manual_codes.png", [("https://example.com/manual/77", "QRCode"), ("PN-00918", "Code128")]
    )
    labels = OUT.parent / "folders" / "labels"
    labels.mkdir(parents=True, exist_ok=True)
    cards = {
        "label_01.png": ["PART 7731-B", "SERIAL SN77A12290", "QC PASS"],
        "label_02.png": ["PART 7731-B", "SERIAL SN77A12291", "QC REJECT"],
        "label_03.png": ["PART 4410-C", "SERIAL SN44C00817", "QC PASS"],
        "label_04.png": ["PART 4410-C", "SERIAL SN44C00818", "QC REJECT"],
    }
    for name, lines in cards.items():
        text_card(f"../folders/labels/{name}", lines)
    codes = OUT.parent / "folders" / "codes"
    codes.mkdir(exist_ok=True)
    for name in ("manual_codes.png", "invoice.png"):
        (codes / name).write_bytes((OUT / name).read_bytes())
    (codes / "codes_sample.png").write_bytes((EXAMPLES / "codes_sample.png").read_bytes())
    photos = OUT.parent / "folders" / "photos"
    photos.mkdir(exist_ok=True)
    for name in ("street.jpg", "football.jpg", "dog-bicycle.jpg"):
        (photos / name).write_bytes((EXAMPLES / name).read_bytes())
    street = cv2.imread(str(EXAMPLES / "street.jpg"))
    cv2.imwrite(str(OUT / "street_sideways.jpg"), cv2.rotate(street, cv2.ROTATE_90_CLOCKWISE))
    label = cv2.imread(str(OUT / "part_label.png"))
    cv2.imwrite(str(OUT / "part_label_upside_down.png"), cv2.rotate(label, cv2.ROTATE_180))
    blurry = cv2.GaussianBlur(cv2.imread(str(EXAMPLES / "football.jpg")), (0, 0), 9)
    cv2.imwrite(str(OUT / "football_blurry.jpg"), blurry)
    # A 3-second clip at 5 fps: porch (0-1 s), football (1-2 s), street (2-3 s).
    size = (640, 480)
    writer = cv2.VideoWriter(str(OUT / "clip.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 5, size)
    for name in ("dog-bicycle.jpg", "football.jpg", "street.jpg"):
        frame = cv2.resize(cv2.imread(str(EXAMPLES / name)), size, interpolation=cv2.INTER_AREA)
        for _ in range(5):
            writer.write(frame)
    writer.release()
