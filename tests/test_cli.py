import json

import cv2
import pytest

from vexa.cli import main
from vexa.model import model_path


@pytest.fixture
def program(tmp_path, image):
    source = tmp_path / "demo.vexa"
    source.write_text('load "image.jpg"\ndetect person\ncount person\ndraw boxes\nshow image')
    photo = tmp_path / "photo.png"
    photo.write_bytes(cv2.imencode(".png", image)[1].tobytes())
    return source, photo


def test_check_needs_no_image_or_model(program, capsys):
    assert main(["check", str(program[0])]) == 0
    assert "Syntax OK: 5" in capsys.readouterr().out


def test_run_saves_image_and_small_json(program, tmp_path, monkeypatch, fake_vision, capsys):
    monkeypatch.setattr("vexa.vision.Vision", lambda path: fake_vision)
    output, report = tmp_path / "output.png", tmp_path / "result.json"
    assert (
        main(
            [
                "run",
                str(program[0]),
                "--image",
                str(program[1]),
                "--output",
                str(output),
                "--json",
                str(report),
            ]
        )
        == 0
    )
    result = json.loads(report.read_text())
    assert result["counts"] == {"person": 1}
    assert result["image_path"] == str(output)
    assert "image" not in result
    assert cv2.imread(str(output)).sum() > 0
    assert "person: 1" in capsys.readouterr().out


def test_syntax_error_shows_file_line_and_no_traceback(tmp_path, capsys):
    source = tmp_path / "bad.vexa"
    source.write_text('load "x"\ndraw circles')
    assert main(["check", str(source)]) == 1
    error = capsys.readouterr().err
    assert f"{source}:2: syntax:" in error
    assert "Traceback" not in error


def test_missing_file_is_input_error(capsys):
    assert main(["check", "missing.vexa"]) == 2
    assert "File error" in capsys.readouterr().err


def test_run_never_overwrites_input(program, capsys):
    original = program[1].read_bytes()
    assert (
        main(["run", str(program[0]), "--image", str(program[1]), "--output", str(program[1])]) == 1
    )
    assert program[1].read_bytes() == original
    assert "Output paths must differ" in capsys.readouterr().err


def test_model_location_and_invalid_install(tmp_path, monkeypatch, capsys):
    destination = tmp_path / "models" / "model.onnx"
    monkeypatch.setenv("VEXA_MODEL_PATH", str(destination))
    assert model_path() == destination
    assert main(["model", "path"]) == 0
    assert str(destination) in capsys.readouterr().out
    invalid = tmp_path / "invalid.onnx"
    invalid.write_bytes(b"invalid")
    assert main(["model", "install", str(invalid)]) == 1
    assert not destination.exists()
    assert "Cannot install" in capsys.readouterr().err


def test_missing_model_is_clear_error(program, tmp_path, capsys):
    assert (
        main(
            [
                "run",
                str(program[0]),
                "--image",
                str(program[1]),
                "--model",
                str(tmp_path / "missing.onnx"),
            ]
        )
        == 1
    )
    assert "Model not found" in capsys.readouterr().err
