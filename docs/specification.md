# Vexa language specification

**Language 0.8 (in development).** [Documentation home](README.md) · [Language reference](language-reference.md) · [Tutorial](tutorial.md)

This document defines the Vexa language precisely: its lexical structure, grammar, types, scoping and evaluation. The [language reference](language-reference.md) explains each command and what it does to an image; this specification covers the language around them. The executable grammar is [src/vexa/grammar.lark](../src/vexa/grammar.lark) (an LALR(1) grammar); the checker is [src/vexa/validation.py](../src/vexa/validation.py).

## 1. Lexical structure

- **Source** is UTF-8 text, at most 20,000 characters. Lines end with LF or CRLF; a final newline is optional.
- **Statements** are one per line; there are no semicolons. Blocks are closed by `end`. Indentation is free but `vexa fmt` uses two spaces per level.
- **Whitespace** (spaces, tabs) between tokens is ignored.
- **Comments** start with `#` outside a string and run to the end of the line.
- **Names**: `[A-Za-z][A-Za-z0-9_]*`, case-sensitive.
- **Numbers**: decimal literals such as `3`, `0.25`, `12.5`. A leading `-` is the negation operator, except in the numeric arguments of `rotate` and `move`, which accept signed numbers.
- **Strings**: double quotes with JSON escapes (`\"`, `\\`, `\n`, `\uXXXX`). In expression position, `{expression}` inside a string is a placeholder; `{{` and `}}` are literal braces. Strings used as labels (`detect "traffic light"`) or paths are plain.
- **Keywords** cannot be used as variable or function names: `let const param define return if else end for each in repeat times while try break continue expect use as where and or not true false detections first last largest smallest nearest farthest`, and the command words (`detect`, `count`, `print`, `text`, `image`, `zone`, `track`, `compare` …). A keyword may still appear as a label where only a label is allowed, such as `detect first`.
- **`it`** is an ordinary name except inside the condition of `where`, where it means the current item.

## 2. Grammar

The grammar below is the essential structure in EBNF. Command forms that only take labels and numbers (`detect`, `rotate`, `style` …) are summarised; see the reference for each.

```text
program     = { statement NEWLINE } ;
statement   = command | block ;
block       = "if" expr NEWLINE body { "else" "if" expr NEWLINE body } [ "else" NEWLINE body ] "end"
            | "for" "each" NAME "in" expr NEWLINE body "end"
            | "for" "each" "image" "in" STRING NEWLINE body "end"
            | "for" "each" "frame" "in" STRING [ "every" NUMBER ("second"|"seconds") ] NEWLINE body "end"
            | "repeat" expr "times" NEWLINE body "end"
            | "while" expr NEWLINE body "end"
            | "try" NEWLINE body "else" NEWLINE body "end"
            | "define" NAME [ "(" [ param { "," param } ] ")" ] [ "->" TYPE ] NEWLINE body "end" ;
param       = NAME [ ":" TYPE ] [ "=" expr ] ;
TYPE        = "number" | "text" | "bool" | "object" | "objects" | "list" | "map" ;
body        = { statement NEWLINE } ;

command     = "let" NAME [ ":" TYPE ] "=" expr
            | "const" NAME "=" expr
            | "param" NAME "=" expr
            | "break" | "continue"
            | "record" NAME "=" expr
            | "print" expr
            | "expect" expr [ "," STRING ]
            | "return" [ expr ]
            | "use" STRING [ "as" NAME ]
            | NAME [ "(" [ expr { "," expr } ] ")" ]          (* call a function *)
            | NAME "." NAME "(" [ expr { "," expr } ] ")"     (* call a library function *)
            | vision-command ;                                 (* see the reference *)

expr        = or-expr [ "where" or-expr ] ;
or-expr     = and-expr { "or" and-expr } ;
and-expr    = not-expr { "and" not-expr } ;
not-expr    = "not" not-expr | comparison ;
comparison  = sum [ ( "==" | "!=" | "<" | "<=" | ">" | ">=" | "in" | "not" "in" ) sum ] ;
sum         = product { ( "+" | "-" ) product } ;
product     = unary { ( "*" | "/" | "%" ) unary } ;
unary       = "-" unary | postfix ;
postfix     = atom { "." NAME | "[" expr "]" | "." NAME "(" [ expr { "," expr } ] ")" } ;
atom        = NUMBER | STRING | "true" | "false" | NAME
            | NAME "(" [ expr { "," expr } ] ")"
            | "(" expr ")"
            | "[" [ expr { "," expr } ] "]"
            | "[" expr "for" "each" NAME "in" expr [ "if" expr ] "]"
            | "{" [ entry { "," entry } ] "}"
            | "count" subject
            | "text" "contains" STRING | "caption" "contains" STRING | "caption"
            | "image" ( "blurry" | "dark" | "bright" | "change" )
            | "detections"
            | ( "first" | "last" | "largest" | "smallest" | "nearest" | "farthest" ) postfix ;
entry       = ( NAME | STRING | "(" expr ")" ) ":" expr ;           (* a bare name is a text key *)
subject     = label | "text" | "masks" | "codes" | "tracks" | "pose" label
            | ( "colour" | "color" ) NAME label
            | label "in" ( "left" | "right" | "top" | "bottom" | "centre" | "center" )
            | label "in" "zone" NAME
            | label ( "left" "of" | "right" "of" | "above" | "below" ) label ;
label       = NAME | STRING ;
```

Precedence, loosest first: `where`, `or`, `and`, `not`, comparisons and `in` (non-associative), `+ -`, `* / %`, unary `-`, then `.` and `[ ]`. Binary operators other than comparisons associate to the left. `if … else if … else … end` is equivalent to nested `if` blocks. After `count LABEL`, `in` starts an area or zone (`count car in left`), so write `(count car) in xs` to test membership.

The numeric argument of `detect … confidence` is an expression (`detect all confidence minimum`); the other vision-command arguments are written out.

## 3. Values and types

| Type | Values | Written as |
| --- | --- | --- |
| `number` | Double-precision numbers | `3`, `0.5`, results of `count` |
| `text` | Unicode strings | `"car"`, `"{n} cars"` |
| `bool` | `true`, `false` | comparisons, `and`/`or`/`not`, `image dark` |
| `object` | One detected object of the current image | `first detections`, a loop variable |
| `objects` | A list of objects | `detections`, `detections where …` |
| `list[number]`, `list[text]`, `list[bool]`, `list[map[…]]` | Lists of one kind | `[1, 2]`, `["a"]`, `range(3)`, `read_csv("f.csv")` |
| `map[number]`, `map[text]`, `map[bool]`, `map[object]` | Text keys to values of one kind | `{car: 2}`, `put(m, "bus", 1)` |
| `nothing` | The result of a function without a value | — |

`[]` has the type *empty list* and `{}` the type *empty map*; they fit any list or map type and become the more specific type on assignment. Lists cannot contain lists, and maps hold single values (not lists or maps); a list may hold maps. In annotations, `list` accepts any list and `map` any map.

Object properties are typed: `label`, `name`, `colour`/`color`, `position`, `posture`, `text` and `zone` are `text`; `confidence`, `x`, `y`, `width`, `height`, `area`, `distance` and `id` are `number`.

## 4. Typing rules

The checker infers a type for every expression; it rejects a program when a rule fails.

| Expression | Rule | Result |
| --- | --- | --- |
| `a + b` | numbers, or either side text (joined), or two lists or two maps of the same kind (maps: the right side wins) | `number`, `text`, the list or map type |
| `a - b`, `a * b`, `a / b`, `a % b`, `-a` | numbers | `number` |
| `a == b`, `a != b` | types that fit each other | `bool` |
| `a < b` and the other orderings | two numbers or two texts | `bool` |
| `a and b`, `a or b`, `not a` | `bool` | `bool` |
| `a in b`, `a not in b` | `b` a list and `a` fits its element; or `b` text or a map and `a` text | `bool` |
| `x.p` | `x` is an `object` and `p` a property, or `x` is a map | the property or value type |
| `xs[i]` | `xs` a list and `i` a number, or `xs` a map and `i` text | the element or value type |
| `xs where c` | `xs` is a list; `c` is `bool`; `it` is the current item, and for objects bare property names are its properties | the type of `xs` |
| `[e for each x in xs if c]` | `xs` a list (or a map: its keys); `x` has the element type inside; `c` is `bool`; `e` is not a list | list of the type of `e` |
| `{k: v, …}` | keys text; values of one kind, not lists or maps | `map[…]` |
| `first xs`, `last xs` | any list | element type |
| `largest xs`, `smallest xs` | objects (by area), numbers or text | element type |
| `nearest xs`, `farthest xs` | `objects` (by distance) | `object` |
| `count s` | as in the reference; a variable must hold a list or object | `number` |
| `f(a…)` | between the number of parameters without defaults and all parameters; annotated parameters fit | the declared return type (`-> T`), else the type of its `return`s |

Statements:

- `if`, `while`, `expect` conditions must be `bool`; there is no implicit truthiness, so `if count person` is an error.
- `let x = e` creates `x` with the type of `e`, or updates an existing `x`, whose type cannot change (an empty list or map may become a specific one). `let x: T = e` also requires `e` to fit `T`, and later values too.
- `const` and `param` come before every other top-level command (`use` and `define` may come first). Neither can be changed. A `const` value uses literals, operators, built-in functions and earlier constants; a `param` default is a number, text or true/false, and `--set NAME=VALUE` replaces it, read as the default's type.
- Parameter defaults are written-out values or constants; parameters with defaults come last. With `-> T`, every `return` must give a value that fits `T`.
- `break` and `continue` must be inside a loop of the same function.
- `try A else B end`: if a statement of `A` fails at run time, `B` runs with `error` (text) holding the message. As with `if`, results made inside either part are not available after it.
- `for each x in e` needs a list; `x` has the element type.
- `repeat e times` needs a number.
- A function's return type is the type of its `return` expressions (different types make it unknown); without `return … value`, it returns `nothing`, which cannot be used as a value.
- Unknown names, properties and functions are errors, with a suggestion when a close match exists.

## 5. Scopes and names

- A program has one top-level scope. Each function call has its own scope holding its parameters and the variables it sets; functions do not see top-level variables, but they read the program's `const` and `param` values (a parameter of the same name hides one). Function names and variable names share one namespace; built-in function names are reserved.
- `define` may only appear at the top level; functions can be called before their definition. `use` may only appear at the top level and imports the defines of a library file, relative to the program file's folder. With `use "f.vexa" as m`, its functions are named `m.f` and calls between them inside the library keep working.
- The variable of a `[… for each x in …]` exists only inside the brackets.
- `let` inside a block updates a variable that already exists outside it. A variable first set inside `for each`, `repeat`, `while` or a single `if` branch is not available after the block; one set in every branch of an `if … else` is.
- `print NAME` where no variable is called `NAME` counts the label `NAME`, for compatibility with earlier versions.

## 6. Evaluation

- Statements run top to bottom. Expressions evaluate left to right; `and` and `or` short-circuit.
- Text comparison with `==`, `!=`, the orderings, `in` on text, `starts_with` and `ends_with` ignores case. Map keys are exact.
- Numbers print without a trailing `.0` when whole; lists print as `[1, 2]`; object lists print their names.
- List positions start at 1; negative positions count from the end. Out-of-range positions, division by zero, `as_number` of non-numeric text and `first` of an empty list are run-time errors that stop the program at that line.
- `repeat` and `while` stop with an error after 10,000 turns; function calls nest at most 100 deep.
- `break` leaves the innermost loop; `continue` starts its next turn (a `while` tests its condition again). Leaving an image or frame loop ends the loop's image as usual.
- `try … else` catches errors of kinds `runtime`, `input` and `vision` raised while its body runs, including inside called functions; checker errors never reach run time.
- `read_csv` and `read_lines` read files relative to the working folder (UTF-8, at most 5 MB); `random` and `now` are the only other built-ins whose result is not determined by their arguments.
- `expect` records a check and continues; a failed check makes `vexa run` exit with status 1.

## 7. Images, results and objects

Vision commands act on one current image and its results (detections, masks, OCR text, depth, poses, colours, caption). The checker follows which results exist along every path: using a result before the command that produces it (`count car` before `detect`, `if text contains …` before `ocr`) is an error, and results produced inside a block are not available after it. A function body is checked once on its own and again at every call, with the caller's state.

Zones (`zone NAME left top right bottom`, fractions of the image) and tracks (`track LABEL`) belong to the program, not to one image: they last through `load`, transforms and loop images, so `count tracks` after a video loop counts every object followed. An object is in a zone when its box centre is. `track` matches each object to the previous frame's object of the same label that overlaps it most (intersection over union at least 0.3), otherwise gives it a new id; `id` is 0 for objects that were not tracked. `compare with "f.jpg"` measures the share of pixels that differ clearly from another photo of the same view (resized to match), available as `image change` until the pixels change.

Objects belong to the image they were found in. `load`, the transforms (`rotate`, `flip`, `resize`, `scale`, `crop`, `move`), `style`, `translate` and each new loop image replace the pixels; objects found before cannot be used afterwards, and a `for each` loop over objects may not change the image. Object properties are computed on first use: `distance` estimates depth once, `posture` estimates the person's pose, `text` reads text inside the box.

## 8. Diagnostics

Errors carry a kind (`syntax`, `check`, `runtime`, `input`, `vision` …), a line and a column. `vexa check` and the language server report every error in a file and these warnings: a variable, `const` or `param` set but never used, a function never called, and statements after `return`, `break` or `continue` in the same block. After a syntax error, the parser replaces the bad line with a stand-in that keeps the blocks around it balanced and continues, so several syntax errors are reported at once.

## 9. Implementations

`vexa run` interprets the checked syntax tree (`--trace` logs each line as it runs and each value `let` sets). `vexa compile` translates it into a Python script after constant folding, constant propagation, removal of branches that never run, unreachable statements, unused variables and functions, and repeated analyses; the script uses the same runtime, so both give the same results, which the test suite verifies.
