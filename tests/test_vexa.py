from pathlib import Path

import numpy as np
import pytest

from vexa.ast_nodes import VexaError
from vexa.interpreter import execute
from vexa.parser import parse
from vexa.validation import check_source
from vexa.vision import Vision, decode_image


def test_parser_commands_comments_and_quoted_labels():
    nodes = parse(
        '# hello\nload "a.jpg"\ndetect "traffic light"\ncount all\ndraw boxes\nprint "ok"\nprint all\nshow image\n'
    )
    assert [node.kind for node in nodes] == [
        "load",
        "detect",
        "count",
        "draw",
        "print_text",
        "print_value",
        "show",
    ]
    assert nodes[1].argument == "traffic light"
    assert nodes[0].line == 2


@pytest.mark.parametrize(
    "source", ["", "# only a comment", "detect", "draw boxes now", "load ../secret"]
)
def test_invalid_programs(source):
    with pytest.raises(VexaError) as error:
        parse(source)
    assert error.value.kind == "syntax"


def test_all_commands_execute(image, fake_vision):
    result = execute(
        'load "anything.jpg"\ndetect all\ncount person\nprint car\nprint "done"\ndraw boxes\nshow image',
        image,
        fake_vision,
    )
    assert result["counts"] == {"person": 1, "car": 1}
    assert "done" in result["logs"]
    assert len(result["detections"]) == 2
    output = decode_image(result["image"])
    assert output.shape == image.shape
    assert output.sum() > 0
    assert image.sum() == 0


@pytest.mark.parametrize(
    "source,line",
    [("detect person", 1), ('load "x"\ncount person', 2), ('load "x"\ndraw boxes', 2)],
)
def test_command_order_errors(image, fake_vision, source, line):
    with pytest.raises(VexaError) as error:
        execute(source, image, fake_vision)
    assert error.value.line == line


def test_zero_counts_and_load_resets_state(image, fake_vision):
    result = execute('load "x"\ndetect all\ncount bus\nshow image\nload "y"', image, fake_vision)
    assert result["counts"] == {}
    assert result["image"] is None
    result = execute('load "x"\ndetect all\ncount bus', image, fake_vision)
    assert result["counts"]["bus"] == 0


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("detect person\ncount car", "count car after detect person always gives 0"),
        ("detect person\nprint car", "print car counts again, and after detect person"),
    ],
)
def test_count_must_match_latest_detection(source, message):
    with pytest.raises(VexaError, match=message) as error:
        check_source(f'load "x"\n{source}')
    assert error.value.line == 3


def test_count_after_matching_or_all_detection_is_valid():
    check_source('load "x"\ndetect person\ncount person\ncount all\ndetect all\ncount car')


def test_unknown_labels_suggest_a_detectable_one(image, fake_vision):
    from vexa.vision import unknown_label

    labels = ["person", "truck", "dining table"]
    assert (
        unknown_label("pickup truck", labels)
        == 'Unknown object "pickup truck". Did you mean "truck"?'
    )
    assert 'Did you mean "person"' in unknown_label("persn", labels)
    assert "not one of the 3 detectable labels" in unknown_label("tree", labels)
    fake_vision.labels = {0: "person", 1: "car"}
    with pytest.raises(VexaError, match='Unknown object "tree"'):
        execute('load "x"\ndetect all\ncount tree', image, fake_vision)


@pytest.mark.parametrize("path", sorted(Path("examples").resolve().glob("*.vexa")))
def test_examples(path, image, fake_vision, fake_reader, fake_segmenter, offline_models):
    assert execute(path.read_text(), image, fake_vision, fake_reader, fake_segmenter)["logs"]


def test_load_alias_never_reads_a_path(image, fake_vision):
    result = execute('load "../../secret"\ndetect person\ncount person', image, fake_vision)
    assert result["counts"] == {"person": 1}


def test_image_size_limit():
    with pytest.raises(VexaError, match="10 MB"):
        decode_image(b"x" * (10 * 1024 * 1024 + 1))


def test_onnx_decode_filters_nms_and_maps_boxes(image):
    vision = Vision()
    vision.labels = {0: "person", 1: "car"}
    rows = np.array(
        [
            [30, 40, 20, 40, 0.9, 0.1],
            [30, 40, 20, 40, 0.8, 0.1],
            [70, 40, 20, 20, 0.1, 0.85],
            [20, 20, 10, 10, 0.1, 0.1],
        ]
    )
    result = vision._decode(rows, image.shape, "all", 1, 0, 0)
    assert len(result) == 2
    assert result[0].box == (20, 20, 40, 60)
    assert len(vision._decode(rows, image.shape, "car", 1, 0, 0)) == 1


def test_onnx_preprocessing(image):
    from vexa.vision import prepare_image

    tensor, scale, left, top = prepare_image(image)
    assert tensor.shape == (1, 3, 640, 640)
    assert tensor.dtype == np.float32
    assert scale == 640 / 120
    assert left == 0 and top > 0


def test_unknown_label(image, monkeypatch):
    monkeypatch.setattr("vexa.openvocab.installed", lambda: False)
    vision = Vision()
    vision.model = object()
    vision.labels = {0: "person"}
    with pytest.raises(VexaError, match="Unknown object"):
        vision.detect(image, "dragon")


@pytest.mark.parametrize("data", [b"", b"not an image"])
def test_invalid_image_data(data):
    with pytest.raises(VexaError) as error:
        decode_image(data)
    assert error.value.kind == "image"


def test_invalid_string_escape():
    with pytest.raises(VexaError) as error:
        parse(r'print "bad\q"')
    assert error.value.kind == "syntax"
    assert error.value.line == 1


def test_syntax_errors_show_the_usage_of_the_command():
    with pytest.raises(VexaError, match='Invalid print command. Use: print "Hello"') as error:
        parse('load "x"\nprint "a" + text')
    assert error.value.line == 2
    with pytest.raises(VexaError, match="Invalid command. Run vexa help"):
        parse("frobnicate now")
    with pytest.raises(
        VexaError, match='Unknown command or function "detecc". Did you mean "detect"'
    ):
        check_source("detecc")
