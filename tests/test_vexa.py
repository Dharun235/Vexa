from pathlib import Path

import numpy as np
import pytest

from vexa.ast_nodes import VexaError
from vexa.interpreter import execute
from vexa.parser import parse
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
        "print_count",
        "show",
    ]
    assert nodes[1].argument == "traffic light"
    assert nodes[0].line == 2


@pytest.mark.parametrize(
    "source", ["", "# only a comment", "detect", "draw circles", "load ../secret"]
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
    result = execute('load "x"\ndetect person\ncount car\nshow image\nload "y"', image, fake_vision)
    assert result["counts"] == {}
    assert result["image"] is None
    result = execute('load "x"\ndetect person\ncount car', image, fake_vision)
    assert result["counts"]["car"] == 0


@pytest.mark.parametrize("path", list(Path("examples").glob("*.vexa")))
def test_examples(path, image, fake_vision):
    assert execute(path.read_text(), image, fake_vision)["image"]


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


def test_unknown_label(image):
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
