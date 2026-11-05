const assert = require("assert");
const path = require("path");
const vscode = require("vscode");

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function until(check, what) {
  for (let i = 0; i < 100; i++) {
    const value = await check();
    if (value) return value;
    await sleep(100);
  }
  throw new Error("timed out waiting for " + what);
}

exports.run = async function () {
  const file = path.join(__dirname, "..", "workspace", "p.vexa");
  const uri = vscode.Uri.file(file);
  const document = await vscode.workspace.openTextDocument(uri);
  await vscode.window.showTextDocument(document);
  assert.strictEqual(document.languageId, "vexa");
  const results = [];
  const ok = (name) => { results.push(name); console.log("PASS " + name); };

  const problems = await until(() => {
    const d = vscode.languages.getDiagnostics(uri);
    return d.length >= 2 ? d : null;
  }, "diagnostics");
  const error = problems.find((d) => d.message.includes('Unknown name "totl"'));
  const warning = problems.find((d) => d.message.includes("unused is set but never used"));
  assert.ok(error && error.severity === vscode.DiagnosticSeverity.Error, "error diagnostic");
  assert.ok(warning && warning.severity === vscode.DiagnosticSeverity.Warning, "warning diagnostic");
  assert.strictEqual(error.range.start.line, 10);
  ok("diagnostics (error + warning severity)");

  const definition = await vscode.commands.executeCommand("vscode.executeDefinitionProvider", uri, new vscode.Position(9, 8));
  const target = definition[0].targetRange || definition[0].range;
  assert.strictEqual(target.start.line, 1);
  ok("go to definition");

  const references = await vscode.commands.executeCommand("vscode.executeReferenceProvider", uri, new vscode.Position(7, 5));
  assert.strictEqual(references.length, 2);
  ok("find references");

  const edit = await vscode.commands.executeCommand("vscode.executeDocumentRenameProvider", uri, new vscode.Position(7, 5), "crowd_size");
  assert.strictEqual(edit.get(uri).length, 2);
  ok("rename");

  const symbols = await vscode.commands.executeCommand("vscode.executeDocumentSymbolProvider", uri);
  assert.deepStrictEqual(symbols.map((s) => s.name), ["LIMIT", "crowd", "people", "unused"]);
  ok("document symbols");

  const hover = await vscode.commands.executeCommand("vscode.executeHoverProvider", uri, new vscode.Position(9, 8));
  assert.ok(hover[0].contents[0].value.includes("define crowd"));
  ok("hover");

  const signature = await vscode.commands.executeCommand("vscode.executeSignatureHelpProvider", uri, new vscode.Position(9, 20), ",");
  assert.ok(signature.signatures[0].label.startsWith("crowd(") && signature.activeParameter === 1);
  ok("signature help");

  const completions = await vscode.commands.executeCommand("vscode.executeCompletionItemProvider", uri, new vscode.Position(10, 6));
  const labels = completions.items.map((i) => (typeof i.label === "string" ? i.label : i.label.label));
  assert.ok(labels.includes("people") && labels.includes("crowd") && labels.includes("split"));
  ok("completion");

  const messy = await vscode.workspace.openTextDocument({ language: "vexa", content: "if true\nprint   1+2\nend\n" });
  const edits = await vscode.commands.executeCommand("vscode.executeFormatDocumentProvider", messy.uri, { tabSize: 2, insertSpaces: true });
  const apply = new vscode.WorkspaceEdit();
  edits.forEach((e) => apply.replace(messy.uri, e.range, e.newText));
  await vscode.workspace.applyEdit(apply);
  assert.strictEqual(messy.getText(), "if true\n  print 1 + 2\nend\n");
  ok("formatting");

  const tokens = await vscode.commands.executeCommand("_workbench.captureSyntaxTokens", uri).catch(() => null);
  if (tokens) {
    const scope = (word) => tokens.find((t) => t.c === word);
    console.log("tokens: const →", JSON.stringify(scope("const")?.t), " number type →", JSON.stringify(scope("number")?.t));
  }
  console.log("ALL " + results.length + " VS CODE CHECKS PASSED");
};
