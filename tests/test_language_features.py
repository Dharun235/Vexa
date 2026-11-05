"""Maps, in, list building, try, break/continue, const/param, defaults, declared types,
named libraries, files, zones, tracking, image comparison, error recovery, trace and the
editor features that come with them."""

import io
import json

import cv2
import numpy as np
import pytest

from vexa.ast_nodes import VexaError
from vexa.cli import main
from vexa.compiler import compile_source
from vexa.formatter import format_source
from vexa.interpreter import Session, execute
from vexa.lsp import Server
from vexa.parser import parse
from vexa.runtime import Program
from vexa.validation import check_source, diagnose


def logs(source, image, vision, **options):
    return execute(source, image, vision, **options)["logs"]


def compiled(source, image, vision, parameters=None):
    code, stats = compile_source(source)
    namespace = {}
    exec(compile(code, "compiled.py", "exec"), namespace)  # noqa: S102 - our own generated code
    program = Program(image, vision, parameters=parameters)
    namespace["run"](program)
    return program, code, stats


def test_maps(image, fake_vision):
    source = (
        'let m = {car: 2, "traffic light": 1}\nprint m\nprint m["car"] + m.car\n'
        'print "car" in m\nprint "bus" not in m\nlet m = m + {bus: 4}\n'
        'print keys(m)\nprint values(m)\nprint get(m, "boat", 0)\nprint put(m, "car", 9).car\n'
        "print length(m)\nfor each key in m\n  print key\nend\n"
        'let empty = {}\nlet empty = put(empty, (upper("x")), 1)\nprint empty'
    )
    assert logs(source, image, fake_vision) == [
        "{car: 2, traffic light: 1}", "4", "true", "true", "[car, traffic light, bus]",
        "[2, 1, 4]", "0", "9", "3", "car", "traffic light", "bus", "{X: 1}",
    ]  # fmt: skip


def test_counting_labels_into_a_map(image, fake_vision):
    source = (
        'load "a"\ndetect all\nlet counts = {}\nfor each thing in detections\n'
        "  let counts = put(counts, thing.label, get(counts, thing.label, 0) + 1)\nend\n"
        'print counts\nrecord summary = counts\nexpect counts.person == 1, "one person"'
    )
    result = execute(source, image, fake_vision)
    assert result["logs"][2] == "{person: 1, car: 1}"
    assert result["rows"][0]["summary"] == "{person: 1, car: 1}"
    assert result["expectations"][0]["passed"]


def test_in_and_list_building(image, fake_vision):
    source = (
        'print 2 in [1, 2]\nprint "ex" in "Vexa"\nprint "z" not in "vexa"\n'
        "print [x * x for each x in range(4) if x % 2 == 0]\nprint [5, 1, 8] where it > 2\n"
        'load "a"\ndetect all\nprint [d.label for each d in detections where width > 36]\n'
        "print detections where it.width > 36\nprint [w for each w in [d.width for each d in detections]]"
    )
    assert logs(source, image, fake_vision)[:5] == ["true", "true", "true", "[4, 16]", "[5, 8]"]
    assert logs(source, image, fake_vision)[-3:] == ["[car]", "car 1", "[35, 40]"]


def test_text_functions(image, fake_vision):
    source = (
        'print split("a,b,,c", ",")\nprint split("  a  b ")\nprint join([1, 2, 3], "+")\n'
        'print replace("a-b-c", "-", " ")\nprint trim("  x ")\nprint starts_with("Vexa", "ve")\n'
        'print ends_with("photo.JPG", ".jpg")\nprint slice("vision", 2, 4)\nprint slice([1, 2, 3, 4], -2)\n'
        'print index_of("Vexa", "x")\nprint index_of([3, 4], 9)'
    )
    assert logs(source, image, fake_vision) == [
        "[a, b, , c]", "[a, b]", "1+2+3", "a b c", "x", "true", "true", "isi", "[3, 4]", "3", "0",
    ]  # fmt: skip


def test_break_and_continue(image, fake_vision):
    source = (
        "let total = 0\nfor each n in range(10)\n  if n % 2 == 0\n    continue\n  end\n"
        "  if n > 7\n    break\n  end\n  let total = total + n\nend\nlet k = 0\nwhile true\n"
        "  let k = k + 1\n  if k == 3\n    break\n  end\nend\nrepeat 5 times\n  break\nend\n"
        'print "{total} {k}"'
    )
    assert logs(source, image, fake_vision) == ["16 3"]
    program, _, _ = compiled(source, image, fake_vision)
    assert program.logs == ["16 3"]


def test_break_in_an_image_loop_ends_it_cleanly(tmp_path, monkeypatch, image, fake_vision):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "photos").mkdir()
    for name in ("a.png", "b.png", "c.png"):
        cv2.imwrite(str(tmp_path / "photos" / name), image)
    source = 'for each image in "photos/"\n  record n = 1\n  break\nend\nprint "after"'
    result = execute(source, None, fake_vision)
    assert len(result["rows"]) == 1 and result["logs"][-1] == "after"


def test_try_else(image, fake_vision):
    source = (
        'try\n  print [1][3]\nelse\n  print "caught: " + error\nend\n'
        'try\n  print read_lines("missing.txt")\nelse\n  print error\nend\n'
        'try\n  print "fine"\nelse\n  print "never"\nend'
    )
    assert logs(source, image, fake_vision) == [
        "caught: Position 3 is outside the list of 1 item(s); positions start at 1.",
        'File not found: "missing.txt"',
        "fine",
    ]
    program, _, _ = compiled(source, image, fake_vision)
    assert program.logs == logs(source, image, fake_vision)


def test_const_and_param(image, fake_vision):
    source = (
        'const LIMIT = 2 * 3\nparam label = "person"\nparam strict = false\nparam minimum = 0.5\n'
        "define over(n: number) -> bool\n  return n > LIMIT\nend\nprint over(7)\n"
        'print "{label} {strict} {minimum}"'
    )
    assert logs(source, image, fake_vision)[-2:] == ["true", "person false 0.5"]
    overrides = {"label": "car", "strict": "TRUE", "minimum": "0.8"}
    assert logs(source, image, fake_vision, parameters=overrides)[-1] == "car true 0.8"
    program, code, stats = compiled(source, image, fake_vision, overrides)
    assert program.logs[-1] == "car true 0.8"
    assert "v_n > 6" in code.replace("(", "").replace(")", "") and stats.constants == 1
    with pytest.raises(VexaError, match="needs a number"):
        execute(source, image, fake_vision, parameters={"minimum": "high"})


def test_defaults_and_declared_types(image, fake_vision):
    source = (
        'const STEP = 10\ndefine bump(n: number, by: number = STEP, label = "x") -> text\n'
        '  return "{label}{n + by}"\nend\nprint bump(1)\nprint bump(1, 2)\nprint bump(1, 2, "y")\n'
        'let total: number = 0\nlet names: list = []\nlet names = names + ["a"]\nprint names'
    )
    expected = ["x11", "x3", "y3", "[a]"]
    assert logs(source, image, fake_vision) == expected
    program, _, _ = compiled(source, image, fake_vision)
    assert program.logs == expected


def test_named_libraries(tmp_path, monkeypatch, image, fake_vision):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "maths.vexa").write_text(
        "define square(n: number)\n  return n * n\nend\n"
        "define quad(n: number)\n  return square(square(n))\nend\n"
    )
    source = 'use "maths.vexa" as m\nprint m.quad(2)\nm.square(1)\nprint m.square(3)'
    assert logs(source, image, fake_vision) == ["16", "9"]
    program, code, _ = compiled(source, image, fake_vision)
    assert program.logs == ["16", "9"] and "def f_m__quad" in code
    with pytest.raises(VexaError, match='Unknown command or function "square"'):
        check_source('use "maths.vexa" as m\nprint square(2)')


def test_library_paths_follow_the_program_file(tmp_path, capsys):
    folder = tmp_path / "project"
    folder.mkdir()
    (folder / "lib.vexa").write_text('define hello\n  print "hi"\nend\n')
    (folder / "main.vexa").write_text('use "lib.vexa"\nhello\n')
    assert main(["check", str(folder / "main.vexa")]) == 0
    assert "Check OK" in capsys.readouterr().out


def test_reading_files(tmp_path, monkeypatch, image, fake_vision):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "limits.csv").write_text("label,limit\nperson,2\ncar,1\n")
    (tmp_path / "words.txt").write_text("exit\nstop\n")
    source = (
        'let rows = read_csv("limits.csv")\nfor each row in rows\n'
        '  print "{row.label} ≤ {as_number(row[\\"limit\\"]) + 1}"\nend\n'
        'print read_lines("words.txt")'
    )
    assert logs(source, image, fake_vision) == ["person ≤ 3", "car ≤ 2", "[exit, stop]"]
    with pytest.raises(VexaError, match="relative path"):
        execute('print read_lines("/etc/hosts")', image, fake_vision)


def test_random_and_now(image, fake_vision):
    found = logs("print random(1, 3)\nprint length(now())", image, fake_vision)
    assert found[0] in ("1", "2", "3") and found[1] == "19"


def test_zones(image, fake_vision):
    source = (
        'zone left_side 0 0 0.4 1\nzone right_side 0.4 0 1 1\nload "a"\ndetect all\n'
        "count person in zone left_side\ncount all in zone right_side\n"
        'print [d.zone for each d in detections]\nprint length(detections where zone == "right_side")\n'
        "draw zones\nshow image"
    )
    result = execute(source, image, fake_vision)
    assert result["counts"] == {"person in zone left_side": 1, "all in zone right_side": 1}
    assert result["logs"][-4:-1] == ["[left_side, right_side]", "1", "Drew 2 zone(s)."]
    with pytest.raises(VexaError, match='Unknown zone "door"'):
        check_source('load "a"\ndetect all\ncount person in zone door')
    with pytest.raises(VexaError, match="fractions"):
        check_source("zone door 0.5 0 0.2 1")


def test_tracking_across_frames(tmp_path, monkeypatch, image, fake_vision):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "frames").mkdir()
    for name in ("1.png", "2.png", "3.png"):
        cv2.imwrite(str(tmp_path / "frames" / name), image)
    source = (
        'for each image in "frames/"\n  detect all\n  track all\n'
        "  record ids = [d.id for each d in detections]\nend\ncount tracks"
    )
    result = execute(source, None, fake_vision)
    assert [row["ids"] for row in result["rows"]] == ["[1, 2]"] * 3
    assert result["counts"]["tracks"] == 2 and result["tracks"] == 2
    with pytest.raises(VexaError, match="Run track"):
        check_source('load "a"\ndetect all\ncount tracks')


def test_compare_images(tmp_path, monkeypatch, fake_vision):
    monkeypatch.chdir(tmp_path)
    empty = np.zeros((100, 120, 3), np.uint8)
    cv2.imwrite(str(tmp_path / "empty.png"), empty)
    scene = empty.copy()
    scene[:50, :60] = 255  # a quarter of the image changed
    source = 'load "a"\ncompare with "empty.png"\nprint round(image change, 1)\nif image change > 0.2\n  print "moved"\nend'
    assert logs(source, scene, fake_vision)[-2:] == ["0.3", "moved"]
    with pytest.raises(VexaError, match="before image change"):
        check_source('load "a"\nprint image change')


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("break", "only inside a loop"),
        ("define f\n  continue\nend\nrepeat 2 times\n  f\nend", "only inside a loop"),
        ('let m = {a: 1, b: "x"}', "mixes a number and text"),
        ("let m = {a: [1]}", "single values"),
        ("let m = {(1): 2}", "map key needs text"),
        ("let m = {a: 1}\nprint m[1]", "map key needs text"),
        ('print 1 in "abc"', "looks for text"),
        ('print "a" in [1, 2]', "never holds text"),
        ("let x = it", "inside … where"),
        ("print [[x] for each x in [1]]", "cannot hold lists"),
        ("let x = 1\nconst A = 2", "top of the program"),
        ("const A = 1\nlet A = 2", "cannot change"),
        ("define f\n  return 1\nend\nconst A = f()", "built-in functions only"),
        ("param p = 1 + 1", "needs a number, text or true/false"),
        ("define f(n = m)\n  return n\nend", "written out"),
        ("define f(a = 1, b)\n  return b\nend", "parameters with defaults come last"),
        ('define f(a: number = "x")\n  return a\nend', "its default is text"),
        ('define f -> number\n  return "x"\nend', "returns text"),
        ("define f -> number\n  print 1\nend", "never returns one"),
        ('let n: number = "x"', "declared a number"),
        ("define f(a, b = 1)\n  return a\nend\nprint f()", "takes 1 to 2 value"),
        ("try\n  print 1\nelse\n  let error = 2\nend", "is text; it cannot hold a number"),
        ('load "a"\ncompare with "x.txt"', "path to an image"),
        ('load "a"\ntrack person', "Run detect"),
        ("print read_csv(3)", "a file name"),
    ],
)
def test_checker_rejects(source, message):
    with pytest.raises(VexaError, match=message):
        check_source(source)


def test_syntax_errors_are_all_reported():
    errors, _ = diagnose('load "a"\ndetect\nif count person >\n  print 1\nend\nlet = 3\nend\n')
    assert [(e.line, e.kind) for e in errors] == [(2, "syntax"), (3, "syntax"), (6, "syntax"),
                                                  (7, "syntax")]  # fmt: skip


def test_optimiser_propagates_constants_and_drops_unreachable_code():
    source = (
        'const DEBUG = false\nconst SCALE = 2\nif DEBUG\n  print "debug"\nend\n'
        "define f(n: number)\n  return n * SCALE\n  print 1\nend\nprint f(3)"
    )
    code, stats = compile_source(source)
    assert "debug" not in code and "(v_n * 2)" in code and "v_DEBUG" not in code
    assert stats.branches == 1 and stats.unreachable == 1 and stats.constants == 2


def test_compiled_matches_interpreter_on_new_features(tmp_path, monkeypatch, image, fake_vision):
    monkeypatch.chdir(tmp_path)
    source = (
        'const MIN = 36\nparam who = "car"\nzone left 0 0 0.4 1\nload "a"\ndetect all\n'
        "let widths = {}\nfor each d in detections\n  let widths = put(widths, d.label, d.width)\nend\n"
        "print widths\nprint [d.zone for each d in detections if d.width > MIN]\n"
        'print who in widths\ntry\n  print widths.boat\nelse\n  print "no boat"\nend\n'
        "count person in zone left\ntrack all\ncount tracks"
    )
    expected = execute(source, image, fake_vision, parameters={"who": "person"})
    program, _, _ = compiled(source, image, fake_vision, {"who": "person"})
    assert program.logs == expected["logs"]
    assert program.result()["counts"] == expected["counts"]


def test_cli_set_and_trace(tmp_path, capsys, monkeypatch, fake_vision):
    monkeypatch.setattr("vexa.vision.Vision", lambda model=None: fake_vision)
    program = tmp_path / "p.vexa"
    program.write_text("param n = 2\nlet doubled = n * 2\nprint doubled\n")
    assert (
        main(["run", str(program), "--set", "n=5", "--trace", "--output", str(tmp_path / "o.png")])
        == 0
    )
    printed = capsys.readouterr().out.splitlines()
    assert "[2] let doubled = n * 2" in printed and "[2]   doubled = 10" in printed
    assert printed[-1] == "10"
    assert main(["run", str(program), "--set", "m=1"]) == 1
    assert "has no param m" in capsys.readouterr().err
    assert main(["run", str(program), "--set", "oops"]) == 1


def test_formatter_handles_new_blocks():
    source = "define f(a=1)->number\nreturn a\nend\ntry\nrepeat 2 times\nbreak\nend\nelse\nprint error\nend\n"
    formatted = format_source(source)
    assert formatted == (
        "define f(a = 1) -> number\n  return a\nend\ntry\n  repeat 2 times\n    break\n  end\n"
        "else\n  print error\nend\n"
    )
    assert parse(formatted)


def test_console_reads_try_blocks():
    from vexa.repl import read_entry

    answers = iter(["  print 1", "else", "  print error", "end"])
    assert read_entry("try", lambda prompt: next(answers)).count("\n") == 4
    session = Session(np.zeros((10, 10, 3), np.uint8), None)
    session.execute(parse("const A = 3"))
    session.execute(parse("define f\n  return A\nend"))
    assert session.execute(parse("print f()"))["logs"] == ["3"]


def _message(body):
    data = json.dumps(body).encode()
    return f"Content-Length: {len(data)}\r\n\r\n".encode() + data


def test_language_server_navigation():
    text = (
        "const LIMIT = 3\ndefine crowd(n: number, limit: number = LIMIT) -> text\n"
        '  return "{n}"\nend\nlet people = 4\nprint crowd(people, 2)\nprint "{people}!"\n'
    )
    uri = "file:///tmp/p.vexa"
    requests = [
        {"id": 1, "method": "initialize", "params": {}},
        {"method": "textDocument/didOpen", "params": {"textDocument": {"uri": uri, "text": text}}},
        {"id": 2, "method": "textDocument/definition",
         "params": {"textDocument": {"uri": uri}, "position": {"line": 5, "character": 8}}},
        {"id": 3, "method": "textDocument/references",
         "params": {"textDocument": {"uri": uri}, "position": {"line": 4, "character": 5}}},
        {"id": 4, "method": "textDocument/rename",
         "params": {"textDocument": {"uri": uri}, "position": {"line": 4, "character": 5},
                    "newName": "crowd_size"}},
        {"id": 5, "method": "textDocument/documentSymbol", "params": {"textDocument": {"uri": uri}}},
        {"id": 6, "method": "textDocument/signatureHelp",
         "params": {"textDocument": {"uri": uri}, "position": {"line": 5, "character": 19}}},
        {"id": 7, "method": "textDocument/rename",
         "params": {"textDocument": {"uri": uri}, "position": {"line": 5, "character": 2},
                    "newName": "say"}},
        {"method": "exit"},
    ]  # fmt: skip
    output = io.BytesIO()
    Server(io.BytesIO(b"".join(_message(r) for r in requests)), output).serve()
    replies = {}
    stream = io.BytesIO(output.getvalue())
    while True:
        header = stream.readline()
        if not header:
            break
        length = int(header.split(b":")[1])
        stream.readline()
        reply = json.loads(stream.read(length))
        replies[reply.get("id")] = reply
    capabilities = replies[1]["result"]["capabilities"]
    assert capabilities["renameProvider"] and capabilities["definitionProvider"]
    assert replies[2]["result"]["range"]["start"] == {"line": 1, "character": 7}
    assert len(replies[3]["result"]) == 3  # let, the call and the {people} placeholder
    assert len(replies[4]["result"]["changes"][uri]) == 3
    assert [s["name"] for s in replies[5]["result"]] == ["LIMIT", "crowd", "people"]
    assert replies[6]["result"]["activeParameter"] == 1
    assert "error" in replies[7]
