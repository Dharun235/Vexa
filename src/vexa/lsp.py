"""vexa lsp: a small Language Server Protocol server over stdin and stdout.

Editors (VS Code with editors/vscode, Neovim, Helix, Zed …) get the
checker's errors as you type, completion of commands, variables and object
properties, help on hover, and formatting. Standard library only.
"""

import json
import re
import sys

from vexa.ast_nodes import VexaError

_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_QUOTED = re.compile(r'"[^"]*"')
_KEYWORDS = (
    "let", "define", "return", "if", "else", "end", "for", "each", "in", "where", "and", "or",
    "not", "true", "false", "detections", "first", "last", "largest", "smallest", "nearest",
    "farthest", "image", "frame", "every", "seconds",
)  # fmt: skip


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
    items += [{"label": name, "kind": 6, "detail": "variable"} for name in sorted(names)]
    items += [{"label": name, "kind": 3, "detail": "function"} for name in sorted(functions)]
    return items


def _hover(text, line, character):
    from vexa.help import TOPICS
    from vexa.values import PROPERTIES

    word = _word_at(text, line, character)
    if word in TOPICS:
        return {"contents": {"kind": "markdown", "value": TOPICS[word]}}
    if word in PROPERTIES:
        return {"contents": f"Object property {word}: {PROPERTIES[word]}"}
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
        diagnostics = _diagnostics(self.documents.get(uri, ""))
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
        elif method == "exit":
            self.running = False
            return
        if "id" in message:
            self.send({"id": message["id"], "result": result})

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
