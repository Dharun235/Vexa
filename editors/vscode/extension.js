// Vexa for VS Code: a small Language Server Protocol client with no dependencies.
// It starts `vexa lsp` and shows its errors, completions, hover help and formatting.
const vscode = require("vscode");
const { spawn } = require("child_process");

let server;
let diagnostics;
let buffer = Buffer.alloc(0);
let nextId = 1;
const pending = new Map();

function send(message) {
  if (!server || server.exitCode !== null) return;
  const body = Buffer.from(JSON.stringify({ jsonrpc: "2.0", ...message }), "utf8");
  server.stdin.write(`Content-Length: ${body.length}\r\n\r\n`);
  server.stdin.write(body);
}

function request(method, params) {
  const id = nextId++;
  send({ id, method, params });
  return new Promise((resolve) => pending.set(id, resolve));
}

function notify(method, params) {
  send({ method, params });
}

function receive(chunk) {
  buffer = Buffer.concat([buffer, chunk]);
  for (;;) {
    const split = buffer.indexOf("\r\n\r\n");
    if (split < 0) return;
    const header = buffer.subarray(0, split).toString("ascii");
    const length = Number((/Content-Length: (\d+)/i.exec(header) || [0, 0])[1]);
    if (buffer.length < split + 4 + length) return;
    const body = buffer.subarray(split + 4, split + 4 + length).toString("utf8");
    buffer = buffer.subarray(split + 4 + length);
    handle(JSON.parse(body));
  }
}

function range(r) {
  return new vscode.Range(r.start.line, r.start.character, r.end.line, r.end.character);
}

function handle(message) {
  if (message.id !== undefined && pending.has(message.id)) {
    pending.get(message.id)(message.result);
    pending.delete(message.id);
  } else if (message.method === "textDocument/publishDiagnostics") {
    const uri = vscode.Uri.parse(message.params.uri);
    diagnostics.set(
      uri,
      message.params.diagnostics.map((d) => {
        const item = new vscode.Diagnostic(range(d.range), d.message, vscode.DiagnosticSeverity.Error);
        item.source = "vexa";
        return item;
      })
    );
  }
}

function isVexa(document) {
  return document.languageId === "vexa";
}

function opened(document) {
  if (!isVexa(document)) return;
  notify("textDocument/didOpen", {
    textDocument: { uri: document.uri.toString(), languageId: "vexa", version: document.version, text: document.getText() },
  });
}

async function activate(context) {
  diagnostics = vscode.languages.createDiagnosticCollection("vexa");
  const command = vscode.workspace.getConfiguration("vexa").get("path") || "vexa";
  server = spawn(command, ["lsp"]);
  server.on("error", (error) => {
    vscode.window.showErrorMessage(`Vexa: could not start "${command} lsp" (${error.message}). Install Vexa or set vexa.path.`);
  });
  server.stdout.on("data", receive);
  await request("initialize", { processId: process.pid, rootUri: null, capabilities: {} });
  notify("initialized", {});
  vscode.workspace.textDocuments.forEach(opened);
  const selector = { language: "vexa" };
  context.subscriptions.push(
    diagnostics,
    vscode.workspace.onDidOpenTextDocument(opened),
    vscode.workspace.onDidChangeTextDocument((event) => {
      if (!isVexa(event.document)) return;
      notify("textDocument/didChange", {
        textDocument: { uri: event.document.uri.toString(), version: event.document.version },
        contentChanges: [{ text: event.document.getText() }],
      });
    }),
    vscode.workspace.onDidCloseTextDocument((document) => {
      if (!isVexa(document)) return;
      notify("textDocument/didClose", { textDocument: { uri: document.uri.toString() } });
      diagnostics.delete(document.uri);
    }),
    vscode.languages.registerCompletionItemProvider(
      selector,
      {
        async provideCompletionItems(document, position) {
          const items = await request("textDocument/completion", {
            textDocument: { uri: document.uri.toString() },
            position: { line: position.line, character: position.character },
          });
          return (items || []).map((item) => {
            const completion = new vscode.CompletionItem(item.label, (item.kind || 1) - 1);
            completion.detail = item.detail;
            return completion;
          });
        },
      },
      "."
    ),
    vscode.languages.registerHoverProvider(selector, {
      async provideHover(document, position) {
        const hover = await request("textDocument/hover", {
          textDocument: { uri: document.uri.toString() },
          position: { line: position.line, character: position.character },
        });
        if (!hover) return null;
        const value = typeof hover.contents === "string" ? hover.contents : hover.contents.value;
        return new vscode.Hover(new vscode.MarkdownString(value));
      },
    }),
    vscode.languages.registerDocumentFormattingEditProvider(selector, {
      async provideDocumentFormattingEdits(document) {
        const edits = await request("textDocument/formatting", {
          textDocument: { uri: document.uri.toString() },
          options: { tabSize: 2, insertSpaces: true },
        });
        return (edits || []).map((edit) => vscode.TextEdit.replace(range(edit.range), edit.newText));
      },
    })
  );
}

function deactivate() {
  if (!server) return undefined;
  notify("shutdown", null);
  notify("exit", null);
  server.kill();
  return undefined;
}

module.exports = { activate, deactivate };
