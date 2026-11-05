"""vexa compile: optimiser passes, generated Python, and equal results to the interpreter."""

import subprocess
import sys

import numpy as np
import pytest

from vexa.ast_nodes import VexaError
from vexa.cli import main
from vexa.compiler import compile_source, optimise
from vexa.interpreter import execute
from vexa.parser import parse
from vexa.runtime import Program

PROGRAMS = {
    "commands": 'load "a"\ndetect all\ncount person\nprint car\ndraw boxes\nshow image',
    "expressions": (
        "let a = 7\nlet b = 2\nprint a / b\nprint a % b\nprint -a + b * 3\n"
        'print "a is {a}, {a * 2}"\nprint "Car" == "car"\nprint 2 < 3 or false'
    ),
    "objects": (
        'load "a"\ndetect all\nlet total = 0\nfor each thing in detections\n'
        '  print "{thing.name}: {thing.colour} at {thing.position}"\n'
        "  let total = total + thing.area\nend\n"
        'let red = detections where colour == "red" and width > 10\n'
        "print largest detections\nrecord total = total\nrecord reds = count red\nblur red"
    ),
    "functions": (
        "define fact(n: number)\n  if n <= 1\n    return 1\n  end\n  return n * fact(n - 1)\nend\n"
        'define label_of(o: object)\n  return o.label + "!"\nend\n'
        'load "a"\ndetect all\nprint fact(5)\nprint label_of(first detections)\n'
        'if count person > 3\n  print "crowd"\nelse if count car == 1\n  print "one car"\n'
        'else\n  print "quiet"\nend'
    ),
    "loops": (
        'let images = 0\nfor each image in "photos/"\n  detect all\n  let images = images + 1\n'
        '  record count person\nend\nprint "{images} image(s)"\nsave csv "out.csv"'
    ),
}


@pytest.fixture
def scene():
    picture = np.zeros((100, 120, 3), np.uint8)
    picture[10:50, 5:40] = (0, 0, 220)
    picture[20:70, 50:90] = (200, 80, 10)
    return picture


def run_compiled(code, image, vision):
    namespace = {}
    exec(compile(code, "compiled.py", "exec"), namespace)  # noqa: S102 - our own generated code
    program = Program(image, vision)
    namespace["run"](program)
    return program.result()


@pytest.mark.parametrize("name", PROGRAMS)
@pytest.mark.parametrize("optimize", [False, True])
def test_compiled_programs_match_the_interpreter(
    name, optimize, scene, fake_vision, offline_models
):
    source = PROGRAMS[name]
    expected = execute(source, scene, fake_vision)
    code, _ = compile_source(source, optimize=optimize)
    actual = run_compiled(code, scene, fake_vision)
    for key in ("logs", "counts", "rows", "detections", "image"):
        assert actual[key] == expected[key], key


def test_optimiser_passes():
    source = (
        "define used\n  print 1\nend\ndefine unused\n  print 2\nend\n"
        'load "a"\nlet a = 2 * 3 + 1\nlet dead = 5\nlet b = a\nprint b\n'
        "estimate depth\nestimate depth\ndetect all\ncount person\nestimate depth\n"
        'rotate 90\nestimate depth\nif 1 > 2\n  print "never"\nelse\n  used\nend\n'
        'print "x" + 2\nif count person > 0 and true\n  print "y"\nend'
    )
    commands, stats = optimise(parse(source))
    assert (stats.functions, stats.variables, stats.branches) == (1, 1, 1)
    assert stats.analyses == 2  # after detect and count the pixels are unchanged; rotate resets
    assert stats.folded == 5  # 2 * 3, + 1, 1 > 2, "x" + 2, … and true
    kinds = [c.kind for c in commands]
    assert kinds.count("estimate_depth") == 2 and "if_block" in kinds
    assert commands[2].argument[1].value == 7  # let a = 7
    assert "dead" not in str(commands) and "unused" not in str(commands)


def test_division_by_zero_is_not_folded():
    code, stats = compile_source("print 1 / 0")
    assert "v.divide(1, 0)" in code and stats.folded == 0


def test_generated_code_uses_native_operators_for_known_types():
    code, _ = compile_source(
        'load "a"\ndetect all\nlet n = count person\nlet half = n / 2\nprint half\nprint n + 1 > 2\n'
        'print "n" + n\nlet big = detections where width > 10\nprint (first big).label + "!"'
    )
    assert "((v_n + 1) > 2)" in code and "v.add('n', v_n)" in code
    assert (
        "(_row0.get('width') > 10)" in code
        and "(v.pick('first', v_big).get('label') + '!')" in code
    )
    assert "v.divide(v_n, 2)" in code  # division keeps its zero check


def test_compile_rejects_invalid_programs():
    with pytest.raises(VexaError, match="Run detect"):
        compile_source('load "a"\ncount person')


def test_compiled_script_runs_and_reports_vexa_lines(tmp_path, scene):
    import cv2

    program = tmp_path / "zero.vexa"
    program.write_text('let n = 0\nprint "start"\nprint 10 / n\n')
    assert main(["compile", str(program)]) == 0
    script = tmp_path / "zero.py"
    assert script.is_file()
    image = tmp_path / "a.png"
    cv2.imwrite(str(image), scene)
    finished = subprocess.run(
        [sys.executable, str(script), "--image", str(image)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        check=False,
    )
    assert finished.returncode == 1
    assert "zero.vexa:3: runtime: Division by zero." in finished.stderr


def test_compile_emit_ast(tmp_path, capsys):
    program = tmp_path / "p.vexa"
    program.write_text('load "a"\nlet x = 1 + 2\nprint x\nocr\nocr\n')
    assert main(["compile", str(program), "--emit", "ast"]) == 0
    printed = capsys.readouterr().out
    assert "1 repeated analysis step(s) removed" in printed
    assert "let ('x', '3')" in printed or "let ('x', 3" in printed
