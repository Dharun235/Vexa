// Integration test: opens the extension in a downloaded VS Code and checks every feature
// against the real `vexa lsp`. Run from editors/vscode/test: npm ci && npm test
// VEXA_PATH chooses the vexa command (default: vexa on PATH).
const fs = require("fs");
const os = require("os");
const path = require("path");
const { runTests } = require("@vscode/test-electron");

(async () => {
  const workspace = path.join(__dirname, "workspace");
  fs.mkdirSync(path.join(workspace, ".vscode"), { recursive: true });
  fs.writeFileSync(
    path.join(workspace, ".vscode", "settings.json"),
    JSON.stringify({ "vexa.path": process.env.VEXA_PATH || "vexa" }, null, 2)
  );
  // A short user-data folder: VS Code's socket path must stay under the macOS limit.
  const userData = fs.mkdtempSync(path.join(os.tmpdir(), "vexa-vsc-"));
  try {
    await runTests({
      version: "1.95.3",
      extensionDevelopmentPath: path.join(__dirname, ".."),
      extensionTestsPath: path.join(__dirname, "suite", "index.js"),
      launchArgs: [workspace, "--disable-extensions", `--user-data-dir=${userData}`],
    });
  } catch (error) {
    console.error("VS Code tests failed:", error.message);
    process.exitCode = 1;
  } finally {
    fs.rmSync(userData, { recursive: true, force: true });
  }
})();
