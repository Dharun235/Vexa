"""vexa fmt, the language server and error display."""

import io
import json
from pathlib import Path

import pytest

from vexa.ast_nodes import VexaError
from vexa.cli import main
from vexa.formatter import check_formatting, format_source
from vexa.lsp import Server

MESSY = (
    '# demo\nload   "street.jpg"     #the photo\n\n\n\n'
    "define   tag( obj :object ,k )\nreturn k+1*2\n     end\n"
    "detect all\nif count person>=2 and count car!=0\n"
    'print "a   b  # not a comment"\n  else if   count car>0\n      print "c"\nelse\n'
    "print tag( first detections , 2 )\nend\nmove 20 -10\n"
)
TIDY = (
    '# demo\nload "street.jpg" # the photo\n\n'
    "define tag(obj: object, k)\n  return k + 1 * 2\nend\n"
    "detect all\nif count person >= 2 and count car != 0\n"
    '  print "a   b  # not a comment"\nelse if count car > 0\n  print "c"\nelse\n'
    "  print tag(first detections, 2)\nend\nmove 20 -10\n"
)


def test_format_layout():
    assert check_formatting(MESSY) == TIDY
    assert format_source(TIDY) == TIDY  # formatting is stable


def test_format_keeps_examples_meaning():
    for path in Path("examples").glob("*.vexa"):
        source = path.read_text()
        assert format_source(check_formatting(source)) == check_formatting(source)


def test_format_refuses_to_change_meaning(monkeypatch):
    monkeypatch.setattr("vexa.formatter.format_source", lambda source: 'print "changed"\n')
    with pytest.raises(VexaError, match="change what the program means"):
        check_formatting('print "x"\n')


def test_fmt_command(tmp_path, capsys):
    path = tmp_path / "p.vexa"
    path.write_text(MESSY)
    assert main(["fmt", "--check", str(path)]) == 1
    assert "Would reformat" in capsys.readouterr().out
    assert main(["fmt", str(path)]) == 0 and capsys.readouterr().out == TIDY
    assert path.read_text() == MESSY  # printing does not touch the file
    assert main(["fmt", "--write", str(path)]) == 0
    assert path.read_text() == TIDY
    assert main(["fmt", "--check", str(path)]) == 0


def frame(message):
    body = json.dumps({"jsonrpc": "2.0", **message}).encode()
    return f"Content-Length: {len(body)}\r\n\r\n".encode() + body


def replies(output):
    data, messages = output.getvalue(), []
    while data:
        header, _, rest = data.partition(b"\r\n\r\n")
        length = int(header.split(b":")[1])
        messages.append(json.loads(rest[:length]))
        data = rest[length:]
    return messages


def test_language_server_session():
    uri = "file:///t.vexa"
    text = 'load "a"\ndetect all\nlet car = first detections\nprint car.widht\n'
    requests = [
        {"id": 1, "method": "initialize", "params": {}},
        {"method": "textDocument/didOpen", "params": {"textDocument": {"uri": uri, "text": text}}},
        {
            "id": 2,
            "method": "textDocument/completion",
            "params": {"textDocument": {"uri": uri}, "position": {"line": 3, "character": 10}},
        },
        {
            "id": 3,
            "method": "textDocument/hover",
            "params": {"textDocument": {"uri": uri}, "position": {"line": 1, "character": 2}},
        },
        {
            "method": "textDocument/didChange",
            "params": {
                "textDocument": {"uri": uri},
                "contentChanges": [{"text": "let  x=1\nprint x\n"}],
            },
        },
        {"id": 4, "method": "textDocument/formatting", "params": {"textDocument": {"uri": uri}}},
        {"id": 5, "method": "shutdown"},
        {"method": "exit"},
    ]
    output = io.BytesIO()
    Server(io.BytesIO(b"".join(frame(r) for r in requests)), output).serve()
    initialize, diagnostics, completion, hover, clean, formatting, shutdown = replies(output)
    assert initialize["result"]["capabilities"]["hoverProvider"] is True
    problem = diagnostics["params"]["diagnostics"][0]
    assert 'Did you mean "width"' in problem["message"]
    assert problem["range"]["start"] == {"line": 3, "character": 6}
    assert "width" in [item["label"] for item in completion["result"]]
    assert hover["result"]["contents"]["value"].startswith("detect person")
    assert clean["params"]["diagnostics"] == []
    assert formatting["result"][0]["newText"] == "let x = 1\nprint x\n"
    assert shutdown == {"jsonrpc": "2.0", "id": 5, "result": None}


def test_completion_lists_commands_variables_and_functions():
    from vexa.lsp import _completions

    labels = {
        item["label"] for item in _completions("let total = 1\ndefine tag\n  print 1\nend\n", 4, 0)
    }
    assert {"detect", "where", "total", "tag"} <= labels


def test_error_underlines_the_word(tmp_path, capsys):
    path = tmp_path / "bad.vexa"
    path.write_text("let total = 1\nprint totl + 1\n")
    assert main(["check", str(path)]) == 1
    error = capsys.readouterr().err
    assert 'Did you mean "total"' in error
    assert "  print totl + 1\n        ^~~~" in error


def test_vscode_extension_files_are_valid():
    folder = Path("editors/vscode")
    package = json.loads((folder / "package.json").read_text())
    assert package["contributes"]["languages"][0]["extensions"] == [".vexa"]
    grammar = json.loads((folder / "syntaxes/vexa.tmLanguage.json").read_text())
    assert grammar["scopeName"] == "source.vexa"
    json.loads((folder / "language-configuration.json").read_text())
    assert "vexa" in (folder / "extension.js").read_text()
