"""vexa lsp: a small Language Server Protocol server over stdin and stdout.

Editors (VS Code with editors/vscode, Neovim, Helix, Zed …) get the
checker's errors and warnings as you type, completion, help on hover,
go to definition, find references, rename, an outline of the file,
signature help and formatting. Standard library only.
"""

import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

from vexa.ast_nodes import VexaError

_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_QUOTED = re.compile(r'"[^"]*"')
_KEYWORDS = (
    "let", "define", "return", "if", "else", "end", "for", "each", "in", "where", "and", "or",
    "not", "true", "false", "detections", "first", "last", "largest", "smallest", "nearest",
    "farthest", "image", "frame", "every", "seconds", "const", "param", "try", "break",
    "continue", "repeat", "times", "while", "expect", "use", "as", "it", "zone", "track",
    "compare", "with", "change", "tracks",
)  # fmt: skip
SIGNATURES = {
    "round": "round(x: number, digits: number = 0) -> number",
    "floor": "floor(x: number) -> number",
    "ceil": "ceil(x: number) -> number",
    "abs": "abs(x: number) -> number",
    "sqrt": "sqrt(x: number) -> number",
    "min": "min(xs: list) -> number  ·  min(a, b, …)",
    "max": "max(xs: list) -> number  ·  max(a, b, …)",
    "sum": "sum(xs: list) -> number",
    "average": "average(xs: list) -> number",
    "length": "length(x: list | text | map) -> number",
    "as_text": "as_text(x) -> text",
    "as_number": "as_number(x: text) -> number",
    "upper": "upper(t: text) -> text",
    "lower": "lower(t: text) -> text",
    "trim": "trim(t: text) -> text",
    "split": 'split(t: text, separator: text = " ") -> list',
    "join": 'join(xs: list, separator: text = "") -> text',
    "replace": "replace(t: text, old: text, new: text) -> text",
    "starts_with": "starts_with(t: text, prefix: text) -> bool",
    "ends_with": "ends_with(t: text, suffix: text) -> bool",
    "slice": "slice(x: list | text, start: number, end: number = -1)",
    "index_of": "index_of(x: list | text, item) -> number",
    "sort": "sort(xs: list) -> list",
    "reverse": "reverse(xs: list) -> list",
    "range": "range(n: number) -> list",
    "keys": "keys(m: map) -> list",
    "values": "values(m: map) -> list",
    "get": "get(m: map, key: text, default)",
    "put": "put(m: map, key: text, value) -> map",
    "random": "random(low: number, high: number) -> number",
    "now": "now() -> text",
    "read_lines": "read_lines(file: text) -> list",
    "read_csv": "read_csv(file: text) -> list",
}
_DEFINING = re.compile(
    r"^\s*(?:let|const|param)\s+(\w+)|^\s*define\s+(\w+)|for\s+each\s+(\w+)\s+in\b"
)
_DEFINE = re.compile(r"^\s*define\s+([\w]+)\s*(\(([^)]*)\))?\s*(->\s*\w+)?")


def _path(uri):
    """The folder of a file:// document, for use paths; None for unsaved documents."""
    parsed = urlparse(uri or "")
    return Path(unquote(parsed.path)).parent if parsed.scheme == "file" else None


def _tokens(text):
    """(line, start, end, word) for every name outside comments and plain string text; names
    inside {…} placeholders of strings count."""
    for number, line in enumerate(text.splitlines()):
        position = 0
        while position < len(line):
            char = line[position]
            if char == "#":
                break
            if char == '"':
                end = position + 1
                while end < len(line) and line[end] != '"':
                    if line[end] == "\\":
                        end += 1
                    elif line[end] == "{" and line[end + 1 : end + 2] != "{":
                        close = line.find("}", end)
                        close = len(line) if close < 0 else close
                        for match in _WORD.finditer(line, end + 1, close):
                            yield number, match.start(), match.end(), match.group()
                        end = close
                    end += 1
                position = end + 1
                continue
            match = _WORD.match(line, position)
            if match:
                yield number, match.start(), match.end(), match.group()
                position = match.end()
            else:
                position += 1


def _definition(text, word):
    """(line, start, end) of the first line that defines word, or None."""
    lines = text.splitlines()
    for number, line in enumerate(lines):
        match = _DEFINING.search(line.split("#")[0])
        if match and word in match.groups():
            start = line.find(word, match.start())
            return number, start, start + len(word)
        header = _DEFINE.match(line)
        if header and header.group(3) and re.search(rf"\b{re.escape(word)}\b", header.group(3)):
            start = line.find(word, header.start(3))
            return number, start, start + len(word)
    return None


def _references(text, word):
    return [(n, start, end) for n, start, end, found in _tokens(text) if found == word]


def _range(line, start, end):
    return {"start": {"line": line, "character": start}, "end": {"line": line, "character": end}}


def _symbols(text):
    """Functions, constants, params and variables, each once, for the outline."""
    found, seen = [], set()
    for number, line in enumerate(text.splitlines()):
        code = line.split("#")[0]
        header = _DEFINE.match(code)
        kinds = [(header.group(1), 12)] if header else []
        match = re.match(r"^\s*(let|const|param)\s+(\w+)", code)
        if match:
            kinds.append((match.group(2), 14 if match.group(1) != "let" else 13))
        for name, kind in kinds:
            if name in seen:
                continue
            seen.add(name)
            start = line.find(name)
            place = _range(number, start, start + len(name))
            found.append(
                {"name": name, "kind": kind, "range": _range(number, 0, len(line)),
                 "selectionRange": place}
            )  # fmt: skip
    return found


def _signature(text, line, character):
    """Signature help for the innermost unclosed call before the cursor on this line."""
    lines = text.splitlines()
    before = lines[line][:character] if line < len(lines) else ""
    depth, active = 0, 0
    for position in range(len(before) - 1, -1, -1):
        char = before[position]
        if char == ")":
            depth += 1
        elif char == "(":
            if depth == 0:
                name = re.search(r"([\w.]+)\s*$", before[:position])
                return _signature_of(text, name.group(1), active) if name else None
            depth -= 1
        elif char == "," and depth == 0:
            active += 1
    return None


def _signature_of(text, name, active):
    label = SIGNATURES.get(name)
    if label is None:
        for line in text.splitlines():
            header = _DEFINE.match(line)
            if header and header.group(1) == name:
                label = line.strip().removeprefix("define ").strip()
                break
    if label is None:
        return None
    inside = label[label.find("(") + 1 : label.find(")")]
    params = [{"label": part.strip()} for part in inside.split(",") if part.strip()]
    return {
        "signatures": [{"label": label, "parameters": params}],
        "activeSignature": 0,
        "activeParameter": min(active, max(len(params) - 1, 0)),
    }


def _diagnostics(text, base=None):
    """Every error (severity 1) and warning (severity 2) in the document."""
    from vexa.validation import diagnose

    errors, warnings = diagnose(text, base)
    lines = text.splitlines() or [""]
    found = []
    for problem, severity in [(e, 1) for e in errors] + [(w, 2) for w in warnings]:
        message = problem.message
        line = max(0, min((problem.line or 1) - 1, len(lines) - 1))
        start = max(0, (problem.column or 1) - 1)
        if problem.file:  # inside a used library: show it on the first line
            message = f"{problem.file}:{problem.line}: {message}"
            line, start = 0, 0
        token = _WORD.match(lines[line], start) or _QUOTED.match(lines[line], start)
        end = token.end() if token else len(lines[line])
        found.append(
            {
                "range": {
                    "start": {"line": line, "character": start if problem.column else 0},
                    "end": {"line": line, "character": max(end, start + 1)},
                },
                "severity": severity,
                "source": "vexa",
                "message": message,
            }
        )
    return found


def _word_at(text, line, character):
    lines = text.splitlines()
    if line >= len(lines):
        return ""
    for match in _WORD.finditer(lines[line]):
        if match.start() <= character <= match.end():
            return match.group()
    return ""


def _completions(text, line, character):
    from vexa.help import TOPICS
    from vexa.values import PROPERTIES

    lines = text.splitlines()
    before = lines[line][:character] if line < len(lines) else ""
    if re.search(r"[A-Za-z_][A-Za-z0-9_]*\.\w*$", before):  # after "car." offer properties
        return [{"label": name, "kind": 10, "detail": kind} for name, kind in PROPERTIES.items()]
    names = set(re.findall(r"^\s*let\s+([A-Za-z_]\w*)", text, re.MULTILINE))
    names |= set(re.findall(r"^\s*for\s+each\s+([A-Za-z_]\w*)\s+in\b", text, re.MULTILINE))
    functions = set(re.findall(r"^\s*define\s+([A-Za-z_]\w*)", text, re.MULTILINE))
    items = [
        {"label": name, "kind": 14, "detail": TOPICS[name].split("\n")[0][:80]}
        for name in TOPICS
        if not name.startswith(":")
    ]
    items += [{"label": word, "kind": 14} for word in _KEYWORDS if word not in TOPICS]
    items += [{"label": name, "kind": 3, "detail": label} for name, label in SIGNATURES.items()]
    items += [{"label": name, "kind": 6, "detail": "variable"} for name in sorted(names)]
    items += [{"label": name, "kind": 3, "detail": "function"} for name in sorted(functions)]
    return items


def _hover(text, line, character):
    from vexa.help import TOPICS
    from vexa.values import PROPERTIES

    word = _word_at(text, line, character)
    if word in TOPICS:
        return {"contents": {"kind": "markdown", "value": TOPICS[word]}}
    if word in SIGNATURES:
        return {"contents": {"kind": "markdown", "value": f"`{SIGNATURES[word]}`"}}
    if word in PROPERTIES:
        return {"contents": f"Object property {word}: {PROPERTIES[word]}"}
    for line_text in text.splitlines():
        header = _DEFINE.match(line_text)
        if header and header.group(1) == word:
            return {"contents": {"kind": "markdown", "value": f"`{line_text.strip()}`"}}
    return None


def _formatting(text):
    from vexa.formatter import check_formatting

    try:
        formatted = check_formatting(text)
    except VexaError:
        return []
    if formatted == text:
        return []
    end = {"line": len(text.splitlines()) + 1, "character": 0}
    return [{"range": {"start": {"line": 0, "character": 0}, "end": end}, "newText": formatted}]


class Server:
    def __init__(self, reader=None, writer=None):
        self.reader = reader or sys.stdin.buffer
        self.writer = writer or sys.stdout.buffer
        self.documents = {}
        self.running = True

    def read(self):
        headers = {}
        while True:
            line = self.reader.readline()
            if not line:
                return None
            line = line.decode("ascii").strip()
            if not line:
                break
            key, _, value = line.partition(":")
            headers[key.strip().lower()] = value.strip()
        body = self.reader.read(int(headers.get("content-length", 0)))
        return json.loads(body)

    def send(self, message):
        body = json.dumps({"jsonrpc": "2.0", **message}).encode("utf-8")
        self.writer.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body)
        self.writer.flush()

    def publish(self, uri):
        diagnostics = _diagnostics(self.documents.get(uri, ""), _path(uri))
        self.send(
            {
                "method": "textDocument/publishDiagnostics",
                "params": {"uri": uri, "diagnostics": diagnostics},
            }
        )

    def handle(self, message):
        method, params = message.get("method"), message.get("params") or {}
        result = None
        if method == "initialize":
            result = {
                "capabilities": {
                    "textDocumentSync": 1,
                    "completionProvider": {"triggerCharacters": ["."]},
                    "hoverProvider": True,
                    "documentFormattingProvider": True,
                    "definitionProvider": True,
                    "referencesProvider": True,
                    "renameProvider": True,
                    "documentSymbolProvider": True,
                    "signatureHelpProvider": {"triggerCharacters": ["(", ","]},
                },
                "serverInfo": {"name": "vexa"},
            }
        elif method in ("textDocument/didOpen", "textDocument/didChange"):
            document = params["textDocument"]
            text = (
                document["text"]
                if method.endswith("didOpen")
                else params["contentChanges"][-1]["text"]
            )
            self.documents[document["uri"]] = text
            self.publish(document["uri"])
        elif method == "textDocument/didClose":
            self.documents.pop(params["textDocument"]["uri"], None)
        elif method in ("textDocument/completion", "textDocument/hover"):
            text = self.documents.get(params["textDocument"]["uri"], "")
            position = params["position"]
            handler = _completions if method.endswith("completion") else _hover
            result = handler(text, position["line"], position["character"])
        elif method == "textDocument/formatting":
            result = _formatting(self.documents.get(params["textDocument"]["uri"], ""))
        elif method in (
            "textDocument/definition",
            "textDocument/references",
            "textDocument/rename",
            "textDocument/signatureHelp",
        ):
            uri = params["textDocument"]["uri"]
            text = self.documents.get(uri, "")
            line, character = params["position"]["line"], params["position"]["character"]
            word = _word_at(text, line, character)
            if method.endswith("signatureHelp"):
                result = _signature(text, line, character)
            elif method.endswith("definition"):
                place = _definition(text, word) if word else None
                result = {"uri": uri, "range": _range(*place)} if place else None
            elif method.endswith("references"):
                result = [{"uri": uri, "range": _range(*r)} for r in _references(text, word)]
            else:
                result = self._rename(uri, text, word, params.get("newName", ""))
                if isinstance(result, str):
                    self.send({"id": message["id"], "error": {"code": -32602, "message": result}})
                    return
        elif method == "textDocument/documentSymbol":
            result = _symbols(self.documents.get(params["textDocument"]["uri"], ""))
        elif method == "exit":
            self.running = False
            return
        if "id" in message:
            self.send({"id": message["id"], "result": result})

    @staticmethod
    def _rename(uri, text, word, new):
        """A workspace edit renaming a variable or function, or a message why not."""
        from vexa.values import BUILTINS, PROPERTIES

        if not word or _definition(text, word) is None:
            return "Rename works on variables, constants, params and functions defined here."
        if word in BUILTINS or word in PROPERTIES or word in _KEYWORDS:
            return f"{word} is part of the language and cannot be renamed."
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", new) or new in _KEYWORDS:
            return f"{new!r} is not a valid name."
        edits = [{"range": _range(*r), "newText": new} for r in _references(text, word)]
        return {"changes": {uri: edits}}

    def serve(self):
        while self.running:
            message = self.read()
            if message is None:
                break
            try:
                self.handle(message)
            except Exception as exc:  # noqa: BLE001 - an editor server must keep serving
                if "id" in message:
                    self.send({"id": message["id"], "error": {"code": -32603, "message": str(exc)}})


def main():
    Server().serve()
    return 0
