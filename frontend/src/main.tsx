import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import Editor, { loader } from "@monaco-editor/react";
import * as monaco from "monaco-editor/esm/vs/editor/editor.api";
import EditorWorker from "monaco-editor/esm/vs/editor/editor.worker?worker";
import "./style.css";

self.MonacoEnvironment = { getWorker: () => new EditorWorker() };
loader.config({ monaco });
monaco.languages.register({ id: "vexa" });
monaco.languages.setMonarchTokensProvider("vexa", {
  tokenizer: {
    root: [
      [/#.*$/, "comment"],
      [/"([^"\\]|\\.)*"/, "string"],
      [/\b(load|detect|count|draw|print|show)\b/, "keyword"],
      [/\b(boxes|image|all)\b/, "type"],
    ],
  },
});
const examples = [
  {
    name: "People on the street",
    target: "person",
    description: "Find people and count the crowd.",
  },
  {
    name: "Find every object",
    target: "all",
    description: "Explore everything the model recognises.",
  },
  {
    name: "Vehicle counter",
    target: "car",
    description: "Count the cars in your photograph.",
  },
];
const program = (target: string) =>
  `load "image.jpg"\ndetect ${target}\ncount ${target}\ndraw boxes\nshow image`;
type Result = {
  logs: string[];
  counts: Record<string, number>;
  image: string | null;
  detections: unknown[];
};
type Failure = { message: string; line?: number; column?: number };
function App() {
  const [source, setSource] = useState(program("person"));
  const [file, setFile] = useState<File>();
  const [preview, setPreview] = useState("");
  const [result, setResult] = useState<Result>();
  const [error, setError] = useState<Failure>();
  const [running, setRunning] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [tab, setTab] = useState("image");
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (!file) return;
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  function chooseFile(value?: File) {
    if (!value) return;
    if (value.size > 10 * 1024 * 1024) {
      setError({ message: "Choose an image smaller than 10 MB." });
      return;
    }
    setFile(value);
    setResult(undefined);
    setError(undefined);
  }
  async function run() {
    if (!file) {
      setError({ message: "Add an image to run your program." });
      return;
    }
    setRunning(true);
    setError(undefined);
    setResult(undefined);
    const start = performance.now();
    try {
      const body = new FormData();
      body.append("source", source);
      body.append("image", file);
      const response = await fetch("/execute", { method: "POST", body });
      const data = await response.json();
      if (!response.ok) {
        setError(
          data.error ?? { message: "The request could not be completed." },
        );
        return;
      }
      setResult(data);
      setTab("image");
    } catch {
      setError({
        message: "Cannot reach Vexa. Check that the local backend is running.",
      });
    } finally {
      setRunning(false);
      setElapsed((performance.now() - start) / 1000);
    }
  }
  return (
    <div className="app">
      <header>
        <a className="brand" href="/">
          vexa<span>✳</span>
        </a>
        <span className="header-label">THE COMPUTER VISION PLAYGROUND</span>
        <span className="local">
          <i /> Local workspace
        </span>
      </header>
      <main>
        <div className="intro">
          <div>
            <div className="eyebrow">A LITTLE CODE. A NEW WAY TO SEE.</div>
            <h1>Vision in a few words.</h1>
            <p>
              Upload an image. Tell Vexa what to look for. See what you find.
            </p>
          </div>
          <span className="version">
            PLAYGROUND <b>v0.1</b>
          </span>
        </div>
        <div className="workspace">
          <section className="left-column">
            <div className="panel upload-panel">
              <div className="panel-heading">
                <span>
                  <em>01</em> Your image
                </span>
                <span>JPG, PNG, WEBP · UP TO 10 MB</span>
              </div>
              <button
                disabled={running}
                className={"upload " + (preview ? "has-image" : "")}
                onClick={() => input.current?.click()}
                onDragOver={(event) => event.preventDefault()}
                onDrop={(event) => {
                  event.preventDefault();
                  if (!running) chooseFile(event.dataTransfer.files[0]);
                }}
              >
                {preview ? (
                  <>
                    <img src={preview} alt="Uploaded source" />
                    <span className="image-name">
                      {file?.name} · Click to replace
                    </span>
                  </>
                ) : (
                  <>
                    <span className="upload-icon">↥</span>
                    <strong>Drop an image here</strong>
                    <span>or click to browse your files</span>
                    <small>Your images stay on this computer.</small>
                  </>
                )}
              </button>
              <input
                ref={input}
                hidden
                type="file"
                accept="image/jpeg,image/png,image/webp"
                onChange={(event) => chooseFile(event.target.files?.[0])}
              />
            </div>
            <div className="panel code-panel">
              <div className="panel-heading">
                <span>
                  <em>02</em> Your program
                </span>
                <span className="filename">main.vexa</span>
              </div>
              <div className="editor">
                <Editor
                  language="vexa"
                  value={source}
                  onChange={(value) => {
                    setSource(value ?? "");
                    setResult(undefined);
                  }}
                  options={{
                    readOnly: running,
                    minimap: { enabled: false },
                    fontSize: 15,
                    lineHeight: 29,
                    padding: { top: 24 },
                    scrollBeyondLastLine: false,
                    automaticLayout: true,
                    overviewRulerLanes: 0,
                    lineNumbersMinChars: 3,
                    fontFamily: '"SFMono-Regular", Consolas, monospace',
                  }}
                />
              </div>
              <div className="run-bar">
                <span>
                  {running
                    ? "Running locally · ONNX CPU inference…"
                    : "Five lines from idea to insight."}
                </span>
                <button className="primary" disabled={running} onClick={run}>
                  {running ? "◌ Running…" : "▶ Run program"}
                </button>
              </div>
            </div>
          </section>
          <section className="panel output-panel">
            <div className="panel-heading">
              <span>
                <em>03</em> The result
              </span>
              <span className={"status " + (result ? "success" : "")}>
                {running
                  ? "PROCESSING"
                  : result
                    ? "COMPLETE"
                    : "READY WHEN YOU ARE"}
              </span>
            </div>
            <div className="tabs">
              <button
                className={tab === "image" ? "active" : ""}
                onClick={() => setTab("image")}
              >
                Image output
              </button>
              <button
                className={tab === "logs" ? "active" : ""}
                onClick={() => setTab("logs")}
              >
                Execution log {result && <b>{result.logs.length}</b>}
              </button>
            </div>
            <div className="output-body" aria-live="polite">
              {error ? (
                <div className="error">
                  <strong>
                    {error.line
                      ? `Line ${error.line}${error.column ? `, column ${error.column}` : ""}`
                      : "Something needs your attention"}
                  </strong>
                  <p>{error.message}</p>
                </div>
              ) : running ? (
                <div className="empty">
                  <span className="spinner">◌</span>
                  <h2>Taking a closer look…</h2>
                  <p>
                    Vexa is running your program locally.
                    <br />
                    Using a compact YOLO model on CPU.
                  </p>
                </div>
              ) : result ? (
                tab === "logs" ? (
                  <ol className="logs">
                    {result.logs.map((line, index) => (
                      <li key={index}>{line}</li>
                    ))}
                  </ol>
                ) : result.image ? (
                  <img
                    className="result-image"
                    src={result.image}
                    alt="Processed image with detected objects"
                  />
                ) : (
                  <div className="empty">
                    <h2>Program complete</h2>
                    <p>
                      Add <code>show image</code> to display your image.
                    </p>
                  </div>
                )
              ) : (
                <div className="empty">
                  <span className="view-icon">⌗</span>
                  <h2>A fresh perspective awaits.</h2>
                  <p>
                    Your processed image and object counts
                    <br />
                    will appear here when you run your program.
                  </p>
                  <span className="empty-tag">IMAGE → CODE → DISCOVERY</span>
                </div>
              )}
            </div>
            <div className="result-footer">
              {result ? (
                <>
                  <div className="counts">
                    {Object.entries(result.counts).map(([label, count]) => (
                      <span key={label}>
                        <b>{count}</b> {label}
                      </span>
                    ))}
                    {!Object.keys(result.counts).length && (
                      <span>No counts requested</span>
                    )}
                  </div>
                  <div className="result-meta">
                    <span>Completed in {elapsed.toFixed(2)}s</span>
                    {result.image && (
                      <a href={result.image} download="vexa-result.png">
                        Download image ↗
                      </a>
                    )}
                  </div>
                </>
              ) : (
                <span>Built for curiosity. Powered by YOLO + ONNX CPU.</span>
              )}
            </div>
          </section>
        </div>
        <section className="examples">
          <div className="examples-title">
            <span className="eyebrow">START SOMEWHERE</span>
            <h2>Small programs. Real possibilities.</h2>
          </div>
          {examples.map((example, index) => (
            <button
              disabled={running}
              key={example.target}
              onClick={() => {
                setSource(program(example.target));
                setResult(undefined);
                setError(undefined);
              }}
            >
              <span className="example-number">0{index + 1}</span>
              <div>
                <strong>{example.name}</strong>
                <p>{example.description}</p>
              </div>
              <span>↗</span>
            </button>
          ))}
        </section>
        <details className="reference">
          <summary>
            Six commands. Everything you need.{" "}
            <span>View language guide +</span>
          </summary>
          <div>
            {[
              [
                'load "image.jpg"',
                "Use the uploaded image. The filename is an alias.",
              ],
              [
                "detect person",
                'Find a COCO object label, or use all. Quote multiword labels: "traffic light".',
              ],
              [
                "count person",
                "Count matching objects from the latest detection.",
              ],
              ["draw boxes", "Draw boxes around the latest detections."],
              ['print "Hello"', "Print text; print person displays its count."],
              ["show image", "Display the current image. Place after drawing."],
            ].map(([code, help]) => (
              <p key={code}>
                <code>{code}</code>
                <span>{help}</span>
              </p>
            ))}
          </div>
        </details>
      </main>
      <footer>
        <span>vexa / See what a few words can do.</span>
        <span>LOCAL FIRST · NO TRAINING REQUIRED</span>
      </footer>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
