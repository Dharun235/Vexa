"""Lists, built-ins, repeat/while, expect, use, diagnostics, warnings and the console."""

import numpy as np
import pytest

from vexa.ast_nodes import VexaError
from vexa.cli import main
from vexa.compiler import compile_source
from vexa.interpreter import Session, execute
from vexa.parser import parse
from vexa.repl import read_entry
from vexa.runtime import Program
from vexa.validation import check_source, diagnose


def logs(source, image, vision):
    return execute(source, image, vision)["logs"]


def test_lists_and_indexing(image, fake_vision):
    source = (
        "let xs = [3, 1, 2]\nprint xs\nprint xs[1] + xs[-1]\nlet xs = xs + [10]\nprint length(xs)\n"
        'let names = ["b", "a"]\nprint sort(names)\nprint first names\nprint largest xs\n'
        "let empty = []\nprint empty\nlet empty = empty + [1]\nprint empty"
    )
    assert logs(source, image, fake_vision) == [
        "[3, 1, 2]", "5", "4", "[a, b]", "b", "10", "nothing", "[1]",
    ]  # fmt: skip


def test_builtins(image, fake_vision):
    source = (
        "let xs = [4, 1, 7]\nprint sum(xs)\nprint average(xs)\nprint min(xs)\nprint max(2, 9, 5)\n"
        "print round(10 / 3, 2)\nprint round(2.5)\nprint floor(2.7)\nprint ceil(2.1)\n"
        'print abs(-3)\nprint sqrt(16)\nprint upper("vexa") + lower("ABC")\n'
        'print as_text(1.5) + "!"\nprint as_number("7") + 1\nprint reverse(xs)\nprint range(3)'
    )
    assert logs(source, image, fake_vision) == [
        "12", "4", "1", "9", "3.33", "2", "2", "3", "3", "4", "VEXAabc", "1.5!", "8",
        "[7, 1, 4]", "[1, 2, 3]",
    ]  # fmt: skip


def test_object_lists_with_builtins(image, fake_vision):
    source = (
        'load "a"\ndetect all\nlet widths = []\nfor each thing in detections\n'
        "  let widths = widths + [thing.width]\nend\n"
        'print "{length(widths)} widths, widest {max(widths)}, mean {average(widths)}"\n'
        "print (detections)[2].name\ncount widths"
    )
    result = execute(source, image, fake_vision)
    assert result["logs"][2:4] == ["2 widths, widest 40, mean 37.5", "car 1"]
    assert result["counts"]["widths"] == 2


def test_repeat_and_while(image, fake_vision):
    source = (
        "let n = 0\nrepeat 3 times\n  let n = n + 1\nend\nlet p = 1\nwhile p < 50\n"
        '  let p = p * 3\nend\nprint "{n} {p}"\nrepeat 0 times\n  print "never"\nend'
    )
    assert logs(source, image, fake_vision) == ["3 81"]


def test_loop_limits(image, fake_vision):
    with pytest.raises(VexaError, match="never became false") as error:
        execute("let n = 0\nwhile n >= 0\n  let n = n + 1\nend", image, fake_vision)
    assert error.value.line == 2
    with pytest.raises(VexaError, match="whole number"):
        execute("repeat 2.5 times\n  print 1\nend", image, fake_vision)


def test_expect_records_checks(image, fake_vision):
    result = execute(
        'load "a"\ndetect all\nexpect count person == 1, "one person"\nexpect count car > 3',
        image,
        fake_vision,
    )
    assert result["expectations"] == [
        {"line": 3, "message": "one person", "passed": True},
        {"line": 4, "message": "line 4", "passed": False},
    ]
    assert result["logs"][-1] == "✗ expect line 4 FAILED"


def test_vexa_test_and_run_exit_codes(tmp_path, capsys, monkeypatch):
    import cv2

    from tests.conftest import FakeVision

    monkeypatch.setattr("vexa.vision.Vision", lambda model=None: FakeVision())
    image = tmp_path / "a.png"
    cv2.imwrite(str(image), np.zeros((100, 120, 3), np.uint8))
    good, bad = tmp_path / "good.vexa", tmp_path / "bad.vexa"
    good.write_text('load "a"\ndetect all\nexpect count person == 1, "one person"\n')
    bad.write_text('load "a"\ndetect all\nexpect count car == 3, "three cars"\n')
    assert main(["test", str(good), "--image", str(image)]) == 0
    assert "1 passed, 0 failed" in capsys.readouterr().out
    assert main(["test", str(good), str(bad), "--image", str(image)]) == 1
    printed = capsys.readouterr().out
    assert f"✗ {bad}:3: three cars" in printed and "1 passed, 1 failed" in printed
    output = tmp_path / "out.png"
    assert main(["run", str(bad), "--image", str(image), "--output", str(output)]) == 1


def test_use_imports_library_functions(tmp_path, monkeypatch, image, fake_vision):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "maths.vexa").write_text(
        'use "more.vexa"\ndefine square(n: number)\n  return n * n\nend\n'
    )
    (tmp_path / "lib" / "more.vexa").write_text("define double(n: number)\n  return n * 2\nend\n")
    source = 'use "lib/maths.vexa"\nprint square(3) + double(1)'
    assert logs(source, image, fake_vision) == ["11"]
    code, _ = compile_source(source)
    namespace = {}
    exec(compile(code, "compiled.py", "exec"), namespace)  # noqa: S102 - our own generated code
    program = Program(image, fake_vision)
    namespace["run"](program)
    assert program.logs == ["11"]


@pytest.mark.parametrize(
    ("files", "source", "message"),
    [
        ({}, 'use "missing.vexa"', "Library not found"),
        ({"a.vexa": 'print "x"\n'}, 'use "a.vexa"', "holds only define"),
        ({"a.vexa": 'use "b.vexa"\n', "b.vexa": 'use "a.vexa"\n'}, 'use "a.vexa"', "uses itself"),
        ({}, 'use "../x.vexa"', "relative path"),
        (
            {"a.vexa": "define f\n  print 1\nend\n"},
            'use "a.vexa"\ndefine f\n  print 2\nend',
            "already defined",
        ),
        ({"a.vexa": "define f\n  count person\nend\n"}, 'use "a.vexa"\nload "x"\nf', "Run detect"),
    ],
)
def test_use_errors(files, source, message, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for name, text in files.items():
        (tmp_path / name).write_text(text)
    with pytest.raises(VexaError, match=message):
        check_source(source)


def test_library_errors_name_the_library_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.vexa").write_text('define f\n  print "x" * 2\nend\n')
    with pytest.raises(VexaError) as error:
        check_source('use "a.vexa"\nf')
    assert error.value.file == "a.vexa" and error.value.line == 2


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ('let xs = [1, "a"]', "mixes a number and text"),
        ("let xs = [[1]]", "cannot hold lists"),
        ("let n = 3\nprint n[1]", "picks from a list"),
        ('let xs = [1]\nprint xs["a"]', "position needs a number"),
        ('let xs = [1]\nlet xs = ["a"]', "a list of numbers; it cannot hold a list of text"),
        ('print sum(["a"])', "sum takes a list of numbers"),
        ("print round()", "round takes a number"),
        ("print upper(3)", "upper takes text"),
        ("print nearest [1, 2]", "nearest needs a list of objects"),
        ('repeat "x" times\n  print 1\nend', "repeat needs a number"),
        ("while 3\n  print 1\nend", "while needs true or false"),
        ("expect 3", "expect needs true or false"),
        ("define sum(x)\n  return x\nend", "built-in function"),
        ("repeat 2 times\n  let inside = 1\nend\nprint inside", 'Unknown name "inside"'),
    ],
)
def test_checker_rejects(source, message):
    with pytest.raises(VexaError, match=message):
        check_source(source)


def test_diagnose_reports_every_error_and_warnings():
    source = (
        'let total = 1\nprint totl\nlet unused = 3\nload "a"\ncount person\n'
        'let n = "x" * 2\nprint n\ndefine f\n  return 1\n  print "x"\nend\nprint total'
    )
    errors, warnings = diagnose(source)
    assert [(e.line, e.kind) for e in errors] == [(2, "check"), (5, "check"), (6, "check")]
    assert [w.message for w in warnings] == [
        "unused is set but never used.",
        "The function f is never called.",
        "This never runs: it comes after return.",
    ]
    errors, _ = diagnose('print "unclosed')
    assert errors[0].kind == "syntax"


def test_check_prints_all_problems(tmp_path, capsys):
    path = tmp_path / "p.vexa"
    path.write_text("print a\nprint b\nlet c = 1\n")
    assert main(["check", str(path)]) == 1
    error = capsys.readouterr().err
    assert 'Unknown name "a"' in error and 'Unknown name "b"' in error
    assert "warning: c is set but never used." in error.replace("\n", " ") or "c is set" in error
    assert "2 error(s), 1 warning(s)." in error


def test_console_reads_whole_blocks():
    answers = iter(["  if true", '    print "x"', "  end", "  let y = 2", "end"])
    entry = read_entry("define f(x)", lambda prompt: next(answers))
    assert entry.splitlines()[-1] == "end" and len(entry.splitlines()) == 6
    assert read_entry('print "one line"', lambda prompt: pytest.fail("asked")) == 'print "one line"'
    session = Session(np.zeros((10, 10, 3), np.uint8), None)
    session.execute(parse(entry))
    assert "f" in session.functions
    session.execute(parse("let xs = [1, 2]"))
    assert session.execute(parse("print sum(xs)"))["logs"] == ["3"]


def test_compiled_standard_library_matches_interpreter(image, fake_vision):
    source = (
        "let xs = [3, 1, 2]\nlet total = 0\nfor each x in sort(xs)\n  let total = total + x\nend\n"
        "repeat 2 times\n  let total = total * 2\nend\nlet k = 1\nwhile k < 10\n  let k = k + 4\nend\n"
        'print "{total} {k} {xs[2]} {round(average(xs), 1)} {range(2)}"\n'
        'load "a"\ndetect all\nexpect count person == 1, "person"\nprint upper("ok")'
    )
    expected = execute(source, image, fake_vision)
    code, _ = compile_source(source)
    namespace = {}
    exec(compile(code, "compiled.py", "exec"), namespace)  # noqa: S102 - our own generated code
    program = Program(image, fake_vision)
    namespace["run"](program)
    actual = program.result()
    assert actual["logs"] == expected["logs"]
    assert actual["expectations"] == expected["expectations"]
