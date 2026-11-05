import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from vexa.ast_nodes import VexaError
from vexa.cli import main
from vexa.help import help_text
from vexa.interpreter import Session
from vexa.ocr import TextReader
from vexa.parser import parse
from vexa.validation import check_source


def test_text_commands_share_preflight():
    commands = check_source('load "x"\nocr\nprint text\ncount text\ndraw text\nshow image')
    assert [item.kind for item in commands] == [
        "load",
        "ocr",
        "print_ocr",
        "count_text",
        "draw_text",
        "show",
    ]
    for source in [
        "ocr",
        'load "x"\nprint text',
        'load "x"\ncount text',
        'load "x"\ndraw text',
        'load "x"\nocr\nload "x"\nprint text',
    ]:
        with pytest.raises(VexaError):
            check_source(source)


def test_ocr_results_drawing_and_reset(image, fake_vision, fake_reader):
    session = Session(image, fake_vision, fake_reader)
    session.execute(parse('load "x"\nocr'))
    result = session.execute(parse("print text\ncount text\ndraw text\nshow image"))
    assert result["counts"]["text"] == 2
    assert result["text"] == "VEXA OCR 2026\nTOTAL 123.45"
    assert result["text_regions"][0]["confidence"] == 0.98
    assert len(result["text_regions"][0]["box"]) == 4
    assert "TOTAL 123.45" in result["logs"]
    assert cv2.imdecode(np.frombuffer(result["image"], np.uint8), cv2.IMREAD_COLOR).sum() > 0
    assert image.sum() == 0
    assert fake_reader.calls == 1
    session.reset()
    assert session.reader is fake_reader
    assert not session.ocr_done and not session.text_regions
    session.execute(parse('load "x"\nocr'))
    assert fake_reader.calls == 2


def test_ocr_and_objects_coexist(image, fake_vision, fake_reader):
    session = Session(image, fake_vision, fake_reader)
    result = session.execute(parse('load "x"\ndetect person\ncount person\nocr\ncount text'))
    assert result["counts"] == {"person": 1, "text": 2}
    assert result["detections"][0]["label"] == "person"
    result = session.execute(parse("detect person"))
    assert result["counts"] == {"text": 2}
    assert result["text"].startswith("VEXA")


def test_failed_ocr_keeps_previous_text(image, fake_vision, fake_reader, monkeypatch):
    session = Session(image, fake_vision, fake_reader)
    session.execute(parse('load "x"\nocr'))

    def fail(_image):
        raise VexaError("OCR unavailable", kind="ocr")

    monkeypatch.setattr(fake_reader, "read", fail)
    with pytest.raises(VexaError):
        session.execute(parse("ocr"))
    assert session.execute(parse("print text"))["text"].startswith("VEXA")


def test_no_text_is_valid(image, fake_vision, fake_reader, monkeypatch):
    monkeypatch.setattr(fake_reader, "read", lambda image: [])
    session = Session(image, fake_vision, fake_reader)
    result = session.execute(parse('load "x"\nocr\nprint text\ncount text'))
    assert result["text"] == "" and result["text_regions"] == []
    assert result["counts"]["text"] == 0
    assert "No text found." in result["logs"]


def test_shell_help_needs_no_image(capsys):
    assert main(["help"]) == 0
    assert "ocr" in capsys.readouterr().out
    assert main(["help", "ocr"]) == 0
    assert "print text" in capsys.readouterr().out
    assert "Unknown help topic" in help_text("missing")


def test_plain_help_and_exit_in_repl(tmp_path, image, monkeypatch, capsys):
    photo = tmp_path / "photo.png"
    photo.write_bytes(cv2.imencode(".png", image)[1].tobytes())
    entries = iter(["help", "help ocr", "exit"])
    monkeypatch.setattr("builtins.input", lambda _: next(entries))
    assert main(["repl", "--image", str(photo)]) == 0
    captured = capsys.readouterr()
    assert "Vexa commands" in captured.out
    assert "print text" in captured.out
    assert not captured.err


def test_cli_ocr_report(tmp_path, image, fake_reader, monkeypatch):
    monkeypatch.setattr("vexa.ocr.TextReader", lambda: fake_reader)
    program, photo, report = tmp_path / "ocr.vexa", tmp_path / "photo.png", tmp_path / "result.json"
    program.write_text('load "x"\nocr\nprint text\ncount text')
    photo.write_bytes(cv2.imencode(".png", image)[1].tobytes())
    assert main(["run", str(program), "--image", str(photo), "--json", str(report)]) == 0
    result = json.loads(report.read_text())
    assert result["text_regions"][0]["text"] == "VEXA OCR 2026"
    assert result["counts"]["text"] == 2


def test_real_ocr_offline_and_cached(monkeypatch):
    import requests
    from rapidocr.utils.download_file import DownloadFile

    def no_download(*_args, **_kwargs):
        pytest.fail("OCR must run with installed models and no downloads")

    monkeypatch.setattr(DownloadFile, "run", no_download)
    monkeypatch.setattr(requests.sessions.Session, "request", no_download)
    reader = TextReader()
    image = cv2.imread(str(Path("examples/ocr_sample.png")))
    regions = reader.read(image)
    assert "VEXA" in "\n".join(item.text for item in regions).upper()
    assert "123.45" in "\n".join(item.text for item in regions)
    engine = reader.engine
    assert reader.read(np.full((100, 300, 3), 255, dtype=np.uint8)) == []
    assert reader.engine is engine
    for stage in [engine.text_det, engine.text_cls, engine.text_rec]:
        assert stage.session.session.get_providers() == ["CPUExecutionProvider"]
