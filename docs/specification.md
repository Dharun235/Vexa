# Vexa language specification

**Language 0.7 (in development).** [Documentation home](README.md) · [Language reference](language-reference.md) · [Tutorial](tutorial.md)

This document defines the Vexa language precisely: its lexical structure, grammar, types, scoping and evaluation. The [language reference](language-reference.md) explains each command and what it does to an image; this specification covers the language around them. The executable grammar is [src/vexa/grammar.lark](../src/vexa/grammar.lark) (an LALR(1) grammar); the checker is [src/vexa/validation.py](../src/vexa/validation.py).

## 1. Lexical structure

- **Source** is UTF-8 text, at most 20,000 characters. Lines end with LF or CRLF; a final newline is optional.
- **Statements** are one per line; there are no semicolons. Blocks are closed by `end`. Indentation is free but `vexa fmt` uses two spaces per level.
- **Whitespace** (spaces, tabs) between tokens is ignored.
- **Comments** start with `#` outside a string and run to the end of the line.
- **Names**: `[A-Za-z][A-Za-z0-9_]*`, case-sensitive.
- **Numbers**: decimal literals such as `3`, `0.25`, `12.5`. A leading `-` is the negation operator, except in the numeric arguments of `rotate` and `move`, which accept signed numbers.
- **Strings**: double quotes with JSON escapes (`\"`, `\\`, `\n`, `\uXXXX`). In expression position, `{expression}` inside a string is a placeholder; `{{` and `}}` are literal braces. Strings used as labels (`detect "traffic light"`) or paths are plain.
- **Keywords** cannot be used as variable or function names: `let define return if else end for each in repeat times while expect use where and or not true false detections first last largest smallest nearest farthest`, and the command words (`detect`, `count`, `print`, `text`, `image` …). A keyword may still appear as a label where only a label is allowed, such as `detect first`.

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
            | "define" NAME [ "(" [ param { "," param } ] ")" ] NEWLINE body "end" ;
param       = NAME [ ":" TYPE ] ;
TYPE        = "number" | "text" | "bool" | "object" | "objects" | "list" ;
body        = { statement NEWLINE } ;

command     = "let" NAME "=" expr
            | "record" NAME "=" expr
            | "print" expr
            | "expect" expr [ "," STRING ]
            | "return" [ expr ]
            | "use" STRING
            | NAME [ "(" [ expr { "," expr } ] ")" ]          (* call a function *)
            | vision-command ;                                 (* see the reference *)

expr        = or-expr [ "where" or-expr ] ;
or-expr     = and-expr { "or" and-expr } ;
and-expr    = not-expr { "and" not-expr } ;
not-expr    = "not" not-expr | comparison ;
comparison  = sum [ ( "==" | "!=" | "<" | "<=" | ">" | ">=" ) sum ] ;
sum         = product { ( "+" | "-" ) product } ;
product     = unary { ( "*" | "/" | "%" ) unary } ;
unary       = "-" unary | postfix ;
postfix     = atom { "." NAME | "[" expr "]" } ;
atom        = NUMBER | STRING | "true" | "false" | NAME
            | NAME "(" [ expr { "," expr } ] ")"
            | "(" expr ")"
            | "[" [ expr { "," expr } ] "]"
            | "count" subject
            | "text" "contains" STRING | "caption" "contains" STRING | "caption"
            | "image" ( "blurry" | "dark" | "bright" )
            | "detections"
            | ( "first" | "last" | "largest" | "smallest" | "nearest" | "farthest" ) postfix ;
subject     = label | "text" | "masks" | "codes" | "pose" label
            | ( "colour" | "color" ) NAME label
            | label "in" ( "left" | "right" | "top" | "bottom" | "centre" | "center" )
            | label ( "left" "of" | "right" "of" | "above" | "below" ) label ;
label       = NAME | STRING ;
```

Precedence, loosest first: `where`, `or`, `and`, `not`, comparisons (non-associative), `+ -`, `* / %`, unary `-`, then `.` and `[ ]`. Binary operators other than comparisons associate to the left. `if … else if … else … end` is equivalent to nested `if` blocks.

## 3. Values and types

| Type | Values | Written as |
| --- | --- | --- |
| `number` | Double-precision numbers | `3`, `0.5`, results of `count` |
| `text` | Unicode strings | `"car"`, `"{n} cars"` |
| `bool` | `true`, `false` | comparisons, `and`/`or`/`not`, `image dark` |
| `object` | One detected object of the current image | `first detections`, a loop variable |
| `objects` | A list of objects | `detections`, `detections where …` |
| `list[number]`, `list[text]`, `list[bool]` | Lists of one kind | `[1, 2]`, `["a"]`, `range(3)` |
| `nothing` | The result of a function without a value | — |

`[]` has the type *empty list*, which fits any list type and becomes the more specific type on assignment. Lists cannot contain lists. In parameter annotations, `list` accepts any list.

Object properties are typed: `label`, `name`, `colour`/`color`, `position`, `posture` and `text` are `text`; `confidence`, `x`, `y`, `width`, `height`, `area` and `distance` are `number`.

## 4. Typing rules

The checker infers a type for every expression; it rejects a program when a rule fails.

| Expression | Rule | Result |
| --- | --- | --- |
| `a + b` | numbers, or either side text (joined), or two lists of the same kind | `number`, `text` or the list type |
| `a - b`, `a * b`, `a / b`, `a % b`, `-a` | numbers | `number` |
| `a == b`, `a != b` | types that fit each other | `bool` |
| `a < b` and the other orderings | two numbers or two texts | `bool` |
| `a and b`, `a or b`, `not a` | `bool` | `bool` |
| `x.p` | `x` is an `object`, `p` a property | the property type |
| `xs[i]` | `xs` a list, `i` a number | the element type |
| `xs where c` | `xs` is `objects`; `c` is `bool`, where bare property names mean the current object's | `objects` |
| `first xs`, `last xs` | any list | element type |
| `largest xs`, `smallest xs` | objects (by area), numbers or text | element type |
| `nearest xs`, `farthest xs` | `objects` (by distance) | `object` |
| `count s` | as in the reference; a variable must hold a list or object | `number` |
| `f(a…)` | the argument count matches; annotated parameters fit | the function's return type |

Statements:

- `if`, `while`, `expect` conditions must be `bool`; there is no implicit truthiness, so `if count person` is an error.
- `let x = e` creates `x` with the type of `e`, or updates an existing `x`, whose type cannot change (an empty list may become a specific list).
- `for each x in e` needs a list; `x` has the element type.
- `repeat e times` needs a number.
- A function's return type is the type of its `return` expressions (different types make it unknown); without `return … value`, it returns `nothing`, which cannot be used as a value.
- Unknown names, properties and functions are errors, with a suggestion when a close match exists.

## 5. Scopes and names

- A program has one top-level scope. Each function call has its own scope holding its parameters and the variables it sets; functions do not see top-level variables. Function names and variable names share one namespace; built-in function names are reserved.
- `define` may only appear at the top level; functions can be called before their definition. `use` may only appear at the top level and imports the defines of a library file.
- `let` inside a block updates a variable that already exists outside it. A variable first set inside `for each`, `repeat`, `while` or a single `if` branch is not available after the block; one set in every branch of an `if … else` is.
- `print NAME` where no variable is called `NAME` counts the label `NAME`, for compatibility with earlier versions.

## 6. Evaluation

- Statements run top to bottom. Expressions evaluate left to right; `and` and `or` short-circuit.
- Text comparison with `==`, `!=` and the orderings ignores case.
- Numbers print without a trailing `.0` when whole; lists print as `[1, 2]`; object lists print their names.
- List positions start at 1; negative positions count from the end. Out-of-range positions, division by zero, `as_number` of non-numeric text and `first` of an empty list are run-time errors that stop the program at that line.
- `repeat` and `while` stop with an error after 10,000 turns; function calls nest at most 100 deep.
- `expect` records a check and continues; a failed check makes `vexa run` exit with status 1.

## 7. Images, results and objects

Vision commands act on one current image and its results (detections, masks, OCR text, depth, poses, colours, caption). The checker follows which results exist along every path: using a result before the command that produces it (`count car` before `detect`, `if text contains …` before `ocr`) is an error, and results produced inside a block are not available after it. A function body is checked once on its own and again at every call, with the caller's state.

Objects belong to the image they were found in. `load`, the transforms (`rotate`, `flip`, `resize`, `scale`, `crop`, `move`), `style`, `translate` and each new loop image replace the pixels; objects found before cannot be used afterwards, and a `for each` loop over objects may not change the image. Object properties are computed on first use: `distance` estimates depth once, `posture` estimates the person's pose, `text` reads text inside the box.

## 8. Diagnostics

Errors carry a kind (`syntax`, `check`, `runtime`, `input`, `vision` …), a line and a column. `vexa check` and the language server report every checker error in a file and these warnings: a variable set but never used, a function never called, and statements after `return` in the same block. Syntax errors stop at the first one.

## 9. Implementations

`vexa run` interprets the checked syntax tree. `vexa compile` translates it into a Python script after constant folding and dead-code removal; the script uses the same runtime, so both give the same results, which the test suite verifies.
