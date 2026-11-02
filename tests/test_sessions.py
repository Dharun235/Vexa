import cv2
import pytest
from fastapi.testclient import TestClient

from vexa.ast_nodes import VexaError
from vexa.cli import main
from vexa.interpreter import Session, execute
from vexa.main import app
from vexa.parser import parse
from vexa.validation import check_source


def test_shared_check_catches_order_and_location():
    with pytest.raises(VexaError) as error:
        check_source('load "x"\n    draw boxes')
    assert (error.value.line, error.value.column) == (2, 5)
    assert check_source('print "Hello"')


def test_whole_program_is_checked_before_inference(image):
    class NoInference:
        def detect(self, *_args):
            pytest.fail("Invalid program must not run inference")

    with pytest.raises(VexaError, match="Run detect"):
        execute('load "x"\ndetect person\nload "x"\ncount person', image, NoInference())


def test_check_and_run_reject_order_before_image_io(tmp_path, capsys):
    program = tmp_path / "bad.vexa"
    program.write_text('load "x"\ncount person')
    for args in [
        ["check", str(program)],
        ["run", str(program), "--image", str(tmp_path / "missing.png")],
    ]:
        assert main(args) == 1
        assert "Run detect" in capsys.readouterr().err


def test_api_uses_same_preflight_before_decoding():
    response = TestClient(app).post(
        "/execute",
        data={"source": 'load "x"\ncount person'},
        files={"image": ("invalid.png", b"not an image")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["line"] == 2
    assert response.json()["error"]["column"] == 1
    assert "Run detect" in response.json()["error"]["message"]


def test_session_retains_state_and_rejects_bad_submission(image, fake_vision):
    session = Session(image, fake_vision)
    session.execute(parse('load "x"'))
    session.execute(parse("detect person"))
    old_result = session.execute(parse("count person"))
    assert old_result["counts"] == {"person": 1}
    with pytest.raises(VexaError):
        session.execute(parse('load "x"\ncount person'))
    assert session.execute(parse("print person"))["counts"] == {"person": 1}
    session.reset()
    assert old_result["counts"] == {"person": 1}
    with pytest.raises(VexaError, match="Load your image"):
        session.execute(parse("count person"))


def test_failed_detection_keeps_previous_selection(image, fake_vision, monkeypatch):
    session = Session(image, fake_vision)
    session.execute(parse('load "x"\ndetect person'))

    def fail(*_args):
        raise VexaError("Detection failed")

    monkeypatch.setattr(fake_vision, "detect", fail)
    with pytest.raises(VexaError, match="Detection failed"):
        session.execute(parse("detect all"))
    assert session.execute(parse("count person"))["counts"] == {"person": 1}


def console_input(monkeypatch, entries):
    values = iter(entries)

    def read(_prompt):
        value = next(values)
        if isinstance(value, BaseException):
            raise value
        return value

    monkeypatch.setattr("builtins.input", read)


def test_repl_persists_recovers_saves_and_resets(tmp_path, image, fake_vision, monkeypatch, capsys):
    photo, output = tmp_path / "photo.png", tmp_path / "output.png"
    photo.write_bytes(cv2.imencode(".png", image)[1].tobytes())
    created = []

    def detector(path):
        created.append(path)
        return fake_vision

    monkeypatch.setattr("vexa.repl.Vision", detector)
    console_input(
        monkeypatch,
        [
            "detect person",
            'load "x"',
            "detect person",
            "count person",
            "draw boxes",
            "show image",
            ":reset",
            "count person",
            ":quit",
        ],
    )
    assert main(["repl", "--image", str(photo), "--output", str(output)]) == 0
    assert len(created) == 1
    assert cv2.imread(str(output)).sum() > 0
    captured = capsys.readouterr()
    assert "person: 1" in captured.out
    assert "Session reset" in captured.out
    assert captured.err.count("Load your image") == 2


def test_repl_interrupt_help_and_eof(tmp_path, image, fake_vision, monkeypatch, capsys):
    photo = tmp_path / "photo.png"
    photo.write_bytes(cv2.imencode(".png", image)[1].tobytes())
    monkeypatch.setattr("vexa.repl.Vision", lambda path: fake_vision)
    console_input(monkeypatch, [KeyboardInterrupt(), ":help", EOFError()])
    assert main(["repl", "--image", str(photo)]) == 0
    captured = capsys.readouterr()
    assert "Cancelled" in captured.out
    assert ":reset" in captured.out
    assert not captured.err
