"""Variables, expressions, objects, functions and the type checker."""

import numpy as np
import pytest

from vexa.ast_nodes import VexaError
from vexa.interpreter import Session, execute
from vexa.parser import parse
from vexa.validation import check_source


@pytest.fixture
def scene():
    """A red person and a blue car where FakeVision puts them."""
    picture = np.zeros((100, 120, 3), np.uint8)
    picture[10:50, 5:40] = (0, 0, 220)
    picture[20:70, 50:90] = (200, 80, 10)
    return picture


def run(source, scene, fake_vision):
    return execute(source, scene, fake_vision)["logs"]


def test_variables_arithmetic_and_strings(fake_vision, scene):
    logs = run(
        "let a = 7\nlet b = 2\nprint a / b\nprint a % b\nprint -a + b * 3\nprint (a + b) * 2\n"
        'print "a is {a}, twice {a * 2}, {{braces}}"\nprint "n=" + a\nlet a = a + 1\nprint a',
        scene,
        fake_vision,
    )
    assert logs == ["3.5", "1", "-1", "18", "a is 7, twice 14, {braces}", "n=7", "8"]


def test_logic_comparisons_and_else_if(fake_vision, scene):
    source = (
        'load "a"\ndetect all\nlet people = count person\n'
        'if people > 1\n  print "many"\nelse if people == 1 and not (count car == 0)\n'
        '  print "one, with a car"\nelse\n  print "none"\nend\n'
        'print "Car" == "car"\nprint 2 < 3 or false\nprint "b" > "a"'
    )
    assert run(source, scene, fake_vision)[2:] == ["one, with a car", "true", "true", "true"]


def test_objects_properties_where_and_picks(fake_vision, scene):
    source = (
        'load "a"\ndetect all\n'
        "for each thing in detections\n"
        '  print "{thing.name}: {thing.label} {thing.colour} {thing.position} {thing.width}x{thing.height}"\n'
        "end\n"
        'let red = detections where colour == "red" and width > 10\n'
        'print "red: {red}, {count red} of {count detections}"\n'
        "print largest detections\nprint smallest detections\nprint first detections\n"
        "print (last detections).area\nblur red\ndraw red"
    )
    logs = run(source, scene, fake_vision)
    assert logs[2:4] == ["person 1: person red top left 35x40", "car 1: car blue centre 40x50"]
    assert logs[4:9] == ["red: person 1, 1 of 2", "car 1", "person 1", "person 1", "2000"]
    assert logs[9:] == ["Blurred 1 object(s) matching red.", "Drew 1 box(es) for red."]


def test_object_variables_in_commands_and_counts(fake_vision, scene):
    source = (
        'load "a"\ndetect all\nlet cars = detections where label == "car"\n'
        "count cars\nmeasure cars\ncolour cars\ncount colour blue cars\nrecord count cars"
    )
    result = execute(source, scene, fake_vision)
    assert result["counts"] == {"cars": 1, "blue cars": 1}
    assert "car 1: 40 × 50 px" in result["logs"]
    assert result["rows"] == [{"image": "a", "cars": 1}]


def test_functions_return_recursion_and_scope(fake_vision, scene):
    source = (
        "define fact(n: number)\n  if n <= 1\n    return 1\n  end\n  return n * fact(n - 1)\nend\n"
        'define shout(word)\n  let word = word + "!"\n  print word\nend\n'
        'let word = "outer"\nprint fact(6)\nshout("hi")\nprint word\nanonymise\n'
        'define anonymise\n  print "nothing to hide"\nend'
    )
    assert run(source, scene, fake_vision) == ["720", "hi!", "outer", "nothing to hide"]


def test_functions_act_on_the_image(fake_vision, scene):
    source = (
        'define tally(label)\n  return "found " + label\nend\n'
        'define find_people\n  detect person\nend\nload "a"\nfind_people\ncount person\n'
        'print tally("cars")'
    )
    result = execute(source, scene, fake_vision)
    assert result["counts"] == {"person": 1} and result["logs"][-1] == "found cars"


def test_loops_accumulate_into_outer_variables(fake_vision, scene):
    source = (
        'load "a"\ndetect all\nlet total = 0\nfor each thing in detections\n'
        "  let total = total + thing.area\n  let seen = thing.name\nend\n"
        "record total = total\nrecord share = total / 12000"
    )
    result = execute(source, scene, fake_vision)
    assert result["rows"] == [{"image": "a", "total": 3400, "share": 3400 / 12000}]


def test_print_label_still_counts(fake_vision, scene):
    result = execute('load "a"\ndetect all\nprint car', scene, fake_vision)
    assert result["logs"][-1] == "car: 1" and result["counts"] == {"car": 1}


def test_repl_keeps_variables_and_functions(fake_vision, scene):
    session = Session(scene, fake_vision)
    session.execute(parse('load "a"\ndetect all\nlet n = count person'))
    session.execute(parse("define double(x: number)\n  return x * 2\nend"))
    assert session.execute(parse("print double(n) + 1"))["logs"] == ["3"]
    with pytest.raises(VexaError, match="n is a number; it cannot hold text"):
        session.execute(parse('let n = "x"'))
    session.execute(parse("let cars = detections"))
    session.execute(parse("rotate 90"))
    with pytest.raises(VexaError, match="Run detect"):  # cars no longer matches the pixels
        session.execute(parse("print count cars"))


def test_runtime_errors(fake_vision, scene):
    with pytest.raises(VexaError, match="Division by zero") as error:
        execute("let zero = 0\nprint 1 / zero", scene, fake_vision)
    assert error.value.line == 2
    with pytest.raises(VexaError, match="empty list"):
        execute(
            'load "a"\ndetect all\nprint first (detections where width > 999)', scene, fake_vision
        )
    with pytest.raises(VexaError, match="too many times"):
        execute("define loop(n)\n  return loop(n + 1)\nend\nprint loop(1)", scene, fake_vision)


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ('let x = 3\nlet x = "a"', "x is a number; it cannot hold text"),
        ('let x = 3\nif x\n  print "y"\nend', "if needs true or false, but this is a number"),
        ("print y", 'Unknown name "y"'),
        ("let total = 1\nprint totl + 1", 'Did you mean "total"'),
        ('let a = 1 + "x" * 2', "\\* needs a number, but this is text"),
        ('print 1 == "1"', "compares a number with text"),
        ('print "a" < 2', "compares numbers"),
        ("print not 3", "not needs true or false"),
        ('load "a"\ndetect all\nlet o = first detections\nprint o.colr', 'Did you mean "color"'),
        ("let n = 3\nprint n.width", ".width needs an object, but this is a number"),
        ('define f(a: number)\n  return a\nend\nprint f("x")', "f expects a to be a number"),
        ("define f(a)\n  return a\nend\nprint f()", "f takes 1 value"),
        ("define f\n  print 1\nend\nlet x = f()", "returns no value"),
        ("define f(a: colour)\n  print 1\nend", 'Unknown type "colour"'),
        ("define f\n  print 1\nend\ndefine f\n  print 2\nend", "already defined"),
        ("if true\n  define f\n    print 1\n  end\nend", "top level"),
        ("return 3", "only inside define"),
        ("let f = 1\ndefine f\n  print 1\nend", "f is a function"),
        ("detecc person", "Invalid detect command|Invalid command"),
        ("detecc", 'Did you mean "detect"'),
        ("if true\n  let z = 1\nend\nprint z", 'Unknown name "z"'),
        ('load "a"\nlet d = detections', "Run detect"),
        (
            'load "a"\ndetect all\nlet cs = detections\nrotate 90\nprint count cs',
            "before the image",
        ),
        ('load "a"\ndetect all\nfor each o in detections\n  rotate 90\nend', "changes the image"),
        ("let n = 3\nfor each o in n\n  print 1\nend", "needs a list of objects"),
        ('load "a"\ndetect all\nprint first 3', "first needs a list of objects"),
        ('load "a"\ndetect all\nprint detections where 3', "where needs true or false"),
        ('print "{nope}"', 'Unknown name "nope"'),
        ('define g\n  count person\nend\nload "a"\ng', "Run detect.*in g, called on line 5"),
        ('load "a"\nlet n = 2\ncount n', "n is a number, not objects"),
        ('load "a"\ndraw circles', 'Nothing to draw as "circles"'),
    ],
)
def test_checker_rejects(source, message):
    with pytest.raises(VexaError, match=message):
        check_source(source)


def test_checker_allows_variables_set_in_every_branch():
    check_source("if true\n  let x = 1\nelse\n  let x = 2\nend\nprint x + 1")
    check_source('load "a"\ndetect all\nlet o = first detections\nrotate 90\nprint "ok"')


def test_error_positions_point_at_the_expression():
    with pytest.raises(VexaError) as error:
        check_source('let a = 1\nprint "x" + (a * "y")')
    assert (error.value.line, error.value.column) == (2, 18)
