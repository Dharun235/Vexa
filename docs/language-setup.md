# Language execution and a practical setup for Vexa

Historical research checked 2 November 2026. Shared validation and the REPL proposed below were subsequently implemented in package 0.2.0a1; see [the current guide](getting-started.md#work-interactively-in-the-terminal). This compares established tooling with Vexa 0.1.0a2. The recommendations below are a proposal; they are not newly implemented features.

## Start with three separate ideas

- **Language:** the syntax and meaning of programs.
- **Implementation:** the parser, checks, interpreter or compiler, and runtime that make those programs work.
- **Tools:** a terminal command, interactive prompt, editor, notebook, or browser that lets someone use that implementation.

The shell launches a program such as `python`, `clang++`, or `vexa`. It does not itself understand the source file's language. An editor's Run button can launch the same command. VS Code's Python tools, for example, expose file execution, a REPL, and selected-code execution through its Python integration. [Python invocation](https://docs.python.org/3/tutorial/interpreter.html), [VS Code execution](https://code.visualstudio.com/docs/python/run).

## What happens after Run?

These are simplified descriptions of common implementations, not requirements that every language must follow.

| System | Typical path | What the user runs |
| --- | --- | --- |
| Python, using CPython | Source → parsing/compilation → bytecode → Python virtual machine | `python demo.py` |
| C++, using Clang | Source → preprocessing → parsing and semantic checks → code generation/optimisation → object files → linking → executable | `clang++ demo.cpp -o demo`, then `./demo` on a Unix-like system |
| Rust, using Cargo/rustc | Source → parsing/macros → type and borrow checks → intermediate representations → code generation → linking → executable | `cargo run`, which builds when needed and runs the result |
| Vexa today | Source → Lark tokens/parse tree → command nodes → interpreter → OpenCV/ONNX Runtime → results | `vexa run demo.vexa --image photo.jpg` |

CPython compiles to bytecode internally; calling it interpreted does not mean it executes unparsed source one line at a time. [Python bytecode](https://docs.python.org/3/glossary.html#term-bytecode).

Clang's command is a driver coordinating compilation stages, including the assembler and linker. A linker combines object code and libraries; users normally let the driver coordinate it. [Clang stages](https://clang.llvm.org/docs/CommandGuide/clang.html).

Rust's compiler performs analyses including borrow checking and code generation. Cargo manages the project/build workflow and invokes the compiler. `cargo check` checks a project without producing the normal executable; it is considerably more than a syntax-only check. [Compiler overview](https://rustc-dev-guide.rust-lang.org/overview.html), [Cargo workflow](https://doc.rust-lang.org/book/ch01-03-hello-cargo.html).

Vexa's path was verified against [parser.py](../src/vexa/parser.py), [interpreter.py](../src/vexa/interpreter.py), and [cli.py](../src/vexa/cli.py). It executes its command nodes directly. It does not currently generate bytecode, object files, or native executables from `.vexa` source.

## What the components do

| Component | Plain meaning | Does Vexa need it? |
| --- | --- | --- |
| Lexer | Recognises words, strings, and punctuation as tokens | Yes; Lark supplies it |
| Parser | Checks how tokens fit together | Yes; already implemented |
| AST / command nodes | A structured representation of the program | Yes; already implemented |
| Semantic checks | Check meaning and allowed operations, beyond spelling and grammar | Yes; currently mostly checked during execution |
| Interpreter | Performs the operations represented by the program | Yes; this is the current execution engine |
| Compiler/code generator | Produces another representation such as bytecode or machine code | Optional; Vexa does not currently need a separate generator |
| Assembler/linker | Produces and combines native object code | Not a separate Vexa-user step today |
| Runtime | Supplies the services needed while the program runs | Yes; Vexa state, image operations, and ONNX CPU inference |

These definitions follow the compiler stages above; the Vexa column is an assessment of the current source. Native dependencies still contain compiled code. Installing those libraries is different from compiling each `.vexa` program. A language implementation can be written in Python and still define its own syntax and behaviour.

## Ways users access a language

| Interface | What users do | Vexa status / suggested order |
| --- | --- | --- |
| Saved file in a terminal | Write a file in any editor, then run a command | **Available.** Make this the dependable baseline |
| Editor or IDE | Edit a file, see errors, and press Run | Any editor plus its terminal works; dedicated Vexa integration is not implemented |
| Interactive prompt / REPL | Type a command, see a result, keep the session alive | Not implemented; useful next for a visual learning language |
| Inline command or standard input | Execute short snippets or pipe generated source into a runner | Not implemented; a small automation improvement after the baseline |
| Browser playground | Edit, upload an image, run, and inspect results | **Available** through `vexa serve` |
| Notebook | Execute cells through a language kernel and display rich output | Not implemented; defer until session behaviour is stable |
| Application API | Another program supplies code and input data | **Available** through the local HTTP API |

Python offers files, interactive mode, `-c`, `-m`, and standard input. That is a useful example of several entry points sharing an implementation, not a list Vexa must copy immediately. [Python command-line interfaces](https://docs.python.org/3/using/cmdline.html).

Interactive access is not mandatory for every language. C++ and Rust's normal documented build workflows work well with saved files; a REPL is a separate tooling choice. Jupyter similarly uses a kernel process to execute a language rather than making the notebook itself its interpreter. [Clang](https://clang.llvm.org/docs/CommandGuide/clang.html), [Cargo](https://doc.rust-lang.org/book/ch01-03-hello-cargo.html), [Jupyter kernels](https://jupyter-client.readthedocs.io/en/stable/kernels.html).

## Recommended next steps for Vexa

### 1. Strengthen the terminal baseline

Keep these existing entry points:

```sh
vexa --help
vexa --version
vexa check demo.vexa
vexa run demo.vexa --image photo.jpg --output result.png
vexa serve
```

Next, improve diagnostics with filename, line, column, a short source excerpt, and a suggested fix. Extend `check` to catch predictable command-order mistakes before loading an image or model. It currently checks syntax only. A program's detection accuracy and file availability still require runtime checks.

Use a shared validation function so the terminal, API, playground, and future editor integration agree. Do not run inference just to check source text.

### 2. Add a small persistent REPL

A possible interface is `vexa repl --image photo.jpg`. This command does not exist yet.

The current interpreter creates fresh state on every execution, so repeatedly calling it with one line would lose the previous image and detections. Introduce a small session abstraction first, retaining the working image, detections, counts, and one model instance. Then expose it through the REPL.

Start with one command per input, helpful errors, and a way to reset or exit. Define how `show image` saves or previews a result in a terminal. Keep the existing rule that `load` refers to a separately supplied image. REPL controls should not silently become new DSL commands.

### 3. Add a thin editor integration

Start with `.vexa` file recognition, keyword/string/comment highlighting, snippets, and a Run command that invokes the installed `vexa run`. Reuse the CLI rather than embedding a second interpreter in the extension.

For live diagnostics and completion across editors, a language server is the usual next layer. A language server analyses source; it is not the program's execution engine. Debugging is a separate integration, commonly using a debug adapter. A small initial extension does not require either protocol. [Language support](https://code.visualstudio.com/api/language-extensions/overview), [Debug adapters](https://code.visualstudio.com/api/extension-guides/debugger-extension).

### 4. Add automation and project features when justified

After the previous steps, consider standard-input execution or an inline-source option. A formatter can help if syntax grows. A project manifest becomes useful when programs actually need multiple source files, reusable modules, or per-project settings. Vexa's six-command, one-image workflow does not yet justify its own equivalent of Cargo or a separate package manager.

Notebook support should reuse the session engine. A native standalone installer can be a future distribution choice; it is distinct from compiling Vexa programs into native code.

## Decision

Keep Vexa as an interpreted language for now. Focus on a predictable shell workflow, shared validation, persistent interactive execution, and editor convenience. Reconsider bytecode or native compilation only if language features, profiling, or deployment requirements make it useful. This is an engineering recommendation, not a claim that performance has been benchmarked against a hypothetical Vexa compiler.

The existing [architecture guide](architecture.md) describes the implemented engine. This research does not change its syntax, package, or released behaviour.
