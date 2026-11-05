// Vexa for VS Code: a small Language Server Protocol client with no dependencies.
// It starts `vexa lsp` and connects VS Code's features to it: errors and warnings,
// completion, hover, go to definition, references, rename, outline, signature help
// and formatting.
const vscode = require("vscode");
const { spawn } = require("child_process");

let server;
let diagnostics;
let output;
let buffer = Buffer.alloc(0);
let nextId = 1;
const pending = new Map();
let lastError = null; // message of the last error reply, shown when rename is refused
const TIMEOUT_MS = 10000;

function send(message) {
  if (!server || server.exitCode !== null) return false;
  const body = Buffer.from(JSON.stringify({ jsonrpc: "2.0", ...message }), "utf8");
  server.stdin.write(`Content-Length: ${body.length}\r\n\r\n`);
  server.stdin.write(body);
  return true;
}

// A request resolves with the result, or null on an error reply, a stopped server or a timeout,
// so a broken server never leaves VS Code waiting.
function request(method, params) {
  const id = nextId++;
  return new Promise((resolve) => {
    const timer = setTimeout(() => {
      pending.delete(id);
      resolve(null);
    }, TIMEOUT_MS);
    pending.set(id, (result) => {
      clearTimeout(timer);
      resolve(result);
    });
    if (!send({ id, method, params })) pending.get(id)(null);
  });
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

function where(document, position) {
  return {
    textDocument: { uri: document.uri.toString() },
    position: { line: position.line, character: position.character },
  };
}

function location(item) {
  return new vscode.Location(vscode.Uri.parse(item.uri), range(item.range));
}

function handle(message) {
  if (message.id !== undefined && pending.has(message.id)) {
    const done = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) {
      output.appendLine(`vexa lsp: ${message.error.message}`);
      lastError = message.error.message;
      done(null);
    } else {
      done(message.result === undefined ? null : message.result);
    }
  } else if (message.method === "textDocument/publishDiagnostics") {
    const uri = vscode.Uri.parse(message.params.uri);
    diagnostics.set(
      uri,
      message.params.diagnostics.map((d) => {
        const severity =
          d.severity === 2 ? vscode.DiagnosticSeverity.Warning : vscode.DiagnosticSeverity.Error;
        const item = new vscode.Diagnostic(range(d.range), d.message, severity);
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
    textDocument: {
      uri: document.uri.toString(),
      languageId: "vexa",
      version: document.version,
      text: document.getText(),
    },
  });
}

async function start() {
  const command = vscode.workspace.getConfiguration("vexa").get("path") || "vexa";
  buffer = Buffer.alloc(0);
  server = spawn(command, ["lsp"]);
  server.on("error", (error) => {
    vscode.window.showErrorMessage(
      `Vexa: could not start "${command} lsp" (${error.message}). Install Vexa or set vexa.path.`
    );
  });
  server.stdout.on("data", receive);
  server.stderr.on("data", (chunk) => output.append(chunk.toString()));
  await request("initialize", { processId: process.pid, rootUri: null, capabilities: {} });
  notify("initialized", {});
  vscode.workspace.textDocuments.forEach(opened);
}

function stop() {
  if (!server) return;
  notify("shutdown", null);
  notify("exit", null);
  server.kill();
  server = undefined;
  pending.forEach((done) => done(null));
  pending.clear();
}

async function activate(context) {
  diagnostics = vscode.languages.createDiagnosticCollection("vexa");
  output = vscode.window.createOutputChannel("Vexa");
  await start();
  const selector = { language: "vexa" };
  context.subscriptions.push(
    diagnostics,
    output,
    vscode.commands.registerCommand("vexa.restartServer", async () => {
      stop();
      diagnostics.clear();
      await start();
    }),
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
          const items = await request("textDocument/completion", where(document, position));
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
        const hover = await request("textDocument/hover", where(document, position));
        if (!hover) return null;
        const value = typeof hover.contents === "string" ? hover.contents : hover.contents.value;
        return new vscode.Hover(new vscode.MarkdownString(value));
      },
    }),
    vscode.languages.registerDefinitionProvider(selector, {
      async provideDefinition(document, position) {
        const found = await request("textDocument/definition", where(document, position));
        return found ? location(found) : null;
      },
    }),
    vscode.languages.registerReferenceProvider(selector, {
      async provideReferences(document, position) {
        const found = await request("textDocument/references", where(document, position));
        return (found || []).map(location);
      },
    }),
    vscode.languages.registerRenameProvider(selector, {
      async provideRenameEdits(document, position, newName) {
        lastError = null;
        const found = await request("textDocument/rename", { ...where(document, position), newName });
        if (!found) throw new Error(lastError || "Vexa cannot rename this.");
        const edit = new vscode.WorkspaceEdit();
        for (const [uri, edits] of Object.entries(found.changes || {})) {
          for (const item of edits) edit.replace(vscode.Uri.parse(uri), range(item.range), item.newText);
        }
        return edit;
      },
    }),
    vscode.languages.registerDocumentSymbolProvider(selector, {
      async provideDocumentSymbols(document) {
        const found = await request("textDocument/documentSymbol", {
          textDocument: { uri: document.uri.toString() },
        });
        return (found || []).map(
          (item) =>
            new vscode.DocumentSymbol(item.name, "", item.kind - 1, range(item.range), range(item.selectionRange))
        );
      },
    }),
    vscode.languages.registerSignatureHelpProvider(
      selector,
      {
        async provideSignatureHelp(document, position) {
          const found = await request("textDocument/signatureHelp", where(document, position));
          if (!found) return null;
          const help = new vscode.SignatureHelp();
          help.signatures = found.signatures.map((s) => {
            const signature = new vscode.SignatureInformation(s.label);
            signature.parameters = s.parameters.map((p) => new vscode.ParameterInformation(p.label));
            return signature;
          });
          help.activeSignature = found.activeSignature;
          help.activeParameter = found.activeParameter;
          return help;
        },
      },
      "(",
      ","
    ),
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
  stop();
  return undefined;
}

module.exports = { activate, deactivate };
