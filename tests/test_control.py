import csv

import cv2
import pytest

from vexa.ast_nodes import VexaError
from vexa.interpreter import Session
from vexa.parser import parse
from vexa.validation import check_source

LOOP = """for each image in "photos"
  detect all
  record count person
  if count car >= 1
    print "has a car"
  else
    print "no car"
  end
end
save csv "out.csv"
"""


@pytest.fixture
def photos(tmp_path, image):
    (tmp_path / "photos").mkdir()
    for name in ("b.png", "a.jpg"):
        cv2.imwrite(str(tmp_path / "photos" / name), image)
    (tmp_path / "photos" / "notes.txt").write_text("skip me")
    return tmp_path


def test_blocks_parse_into_nested_commands():
    loop, save = parse(LOOP)
    assert loop.kind == "for_each" and loop.argument == "photos"
    branch = loop.body[2]
    assert branch.condition.kind == "compare" and branch.condition.value == ">="
    assert branch.condition.args[0].value == "car" and branch.condition.args[1].value == 1.0
    assert [c.argument for c in branch.body + branch.orelse] == ["has a car", "no car"]
    assert save.kind == "save_csv"
    condition = parse('load "x"\nocr\nif text contains "TOTAL"\nrecord count text\nend')[
        2
    ].condition
    assert (condition.kind, condition.value) == ("text_contains", "TOTAL")


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ('if count person > 1\nprint "x"', "missing its end"),
        ('print "x"\nend', "end without a matching if"),
        ('for each image in "a"\nfor each image in "b"\nprint "x"\nend\nend', "cannot be nested"),
        ('for each image in "a"\nsave csv "o.csv"\nend', "after the for each loop"),
        ('save csv "../o.csv"', "relative path ending in .csv"),
        ('save csv "o.txt"', "relative path ending in .csv"),
        ('load "x"\nif count person > 1\nprint "x"\nend', "Run detect before"),
        ('load "x"\nif text contains "A"\nprint "x"\nend', "Run ocr before"),
        ('load "x"\nrecord codes', "Run scan codes before"),
        ('load "x"\ndetect person\nrecord count car', "count car after detect person"),
        ('load "x"\nif count text > 0\nprint "x"\nend', "Run ocr before"),
        ('load "x"\nocr\nif count text > 0\ndetect car\nend\ncount car', "Run detect before"),
        ('for each image in "a"\ndetect car\nend\ncount car', "Load your image first"),
    ],
)
def test_block_validation_errors(source, message):
    with pytest.raises(VexaError, match=message):
        check_source(source)


def test_for_each_records_rows_and_saves_csv(photos, fake_vision):
    session = Session(None, fake_vision, base=photos)
    result = session.execute(parse(LOOP))
    assert result["rows"] == [{"image": "a.jpg", "person": 1}, {"image": "b.png", "person": 1}]
    assert "Image 1/2: a.jpg" in result["logs"] and result["logs"].count("has a car") == 2
    with (photos / "out.csv").open() as stream:
        assert list(csv.DictReader(stream)) == [
            {"image": "a.jpg", "person": "1"},
            {"image": "b.png", "person": "1"},
        ]


def test_if_else_and_records_outside_a_loop(image, fake_vision, fake_reader):
    source = 'load "shelf.jpg"\ndetect person\nif count person > 1\nprint "many"\nelse\nprint "few"\nend\nrecord count person\nocr\nrecord text'
    result = Session(image, fake_vision, fake_reader).execute(parse(source))
    assert "few" in result["logs"] and "many" not in result["logs"]
    assert result["rows"] == [
        {"image": "shelf.jpg", "person": 1, "text": "VEXA OCR 2026 | TOTAL 123.45"}
    ]


def test_folder_and_image_errors(tmp_path, fake_vision):
    session = Session(None, fake_vision, base=tmp_path)
    with pytest.raises(VexaError, match="load needs an image"):
        session.execute(parse('load "x"'))
    with pytest.raises(VexaError, match='Folder not found: "missing"'):
        session.execute(parse('for each image in "missing"\nprint "x"\nend'))
    (tmp_path / "empty").mkdir()
    with pytest.raises(VexaError, match="No JPEG, PNG or WebP images"):
        session.execute(parse('for each image in "empty"\nprint "x"\nend'))


def test_load_inside_a_loop_reloads_that_image(photos, fake_vision):
    source = 'for each image in "photos"\n  load "image.jpg"\n  detect person\n  record count person\nend'
    result = Session(None, fake_vision, base=photos).execute(parse(source))
    assert result["rows"] == [{"image": "a.jpg", "person": 1}, {"image": "b.png", "person": 1}]
