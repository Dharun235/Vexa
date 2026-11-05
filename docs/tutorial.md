# Learn Vexa in 25 minutes

[Documentation home](README.md) · [Language reference](language-reference.md) · [Specification](specification.md)

Each lesson is a complete program you can save as a `.vexa` file and run with `vexa run lesson.vexa --image street.jpg` (the photo is in [examples](../examples/)). Every example on this page is run by Vexa's test suite, so they all work.

## 1. Commands

A program is a list of commands, one per line.

```vexa
load "street.jpg"
detect person
count person
draw boxes
show image
```

`load` starts from the photo, `detect` finds people, `count` prints how many, `draw boxes` marks them and `show image` saves the result to `vexa-output.png`. Run `vexa check lesson.vexa` first: it checks the program without an image or a model, and points at mistakes such as `count car` after `detect person`.

## 2. Variables and text

```vexa
load "street.jpg"
detect all
let people = count person
let buses = count bus
print "{people} people and {buses} bus(es)"
print "people per bus: {round(people / max(buses, 1), 1)}"
```

`let` stores a value. `{…}` inside a string puts a value in the text. Values have types (numbers, text, true/false, objects, lists), and the checker stops a program that mixes them up, such as `"a" * 2`.

## 3. Decisions

```vexa
load "street.jpg"
check exposure
detect person
let people = count person
if image dark
  print "too dark to judge"
else if people >= 4
  print "crowded"
else
  print "quiet"
end
```

Conditions are true or false: comparisons, `and`, `or`, `not`, and checks such as `image dark` or `text contains "EXIT"`.

## 4. Objects

Every detection is an object with properties.

```vexa
load "street.jpg"
detect all
for each thing in detections
  print "{thing.name}: {thing.colour}, {thing.position}, {thing.width} px wide"
end
let big = detections where area > 20000 and label != "bus"
print "big non-buses: {big}"
let closest = nearest (detections where label == "person")
blur closest
show image
```

`detections where …` keeps the objects for which the condition holds; inside it, `area`, `label` and the other properties refer to each object. `nearest` uses depth estimation, which runs automatically the first time a distance is needed.

## 5. Lists

```vexa
load "street.jpg"
detect person
let heights = []
for each person in detections
  let heights = heights + [person.height]
end
print "tallest {max(heights)} px, average {round(average(heights))} px"
print "first person: {heights[1]} px"
```

Lists hold one kind of value. `xs[1]` is the first item. Built-in functions such as `sum`, `average`, `max`, `sort` and `length` work on them; `vexa help functions` lists them all.

## 6. Functions

```vexa
define crowd_level(people: number)
  if people >= 4
    return "crowded"
  else if people >= 1
    return "a few people"
  end
  return "empty"
end

define anonymise
  detect face
  blur face
end

load "street.jpg"
detect person
print crowd_level(count person)
anonymise
show image
```

`define` makes a function; `return` gives back a value. A function can work on the image (`anonymise`) or compute a value (`crowd_level`). Put functions you reuse in a file such as `helpers.vexa` and import them with `use "helpers.vexa"`.

## 7. Many photos

```vexa
let total = 0
for each image in "photos/"
  detect person
  let total = total + count person
  record count person
end
print "{total} people in all photos"
save csv "people.csv"
```

The loop runs once per photo in the folder. `record` adds a column to that photo's row, and `save csv` writes the table. The same works on video with `for each frame in "clip.mp4" every 1 second`.

## 8. Checks you can automate

```vexa
load "street.jpg"
detect all
expect count person >= 1, "someone is in the photo"
expect count bus == 1, "exactly one bus"
```

`expect` prints ✓ or ✗ for each check. `vexa test checks.vexa --image street.jpg` runs one or more programs and exits with status 1 if any check fails, so you can check a camera's view in a script or CI.

## 9. Maps, settings and errors

```vexa
param busy = 3

load "street.jpg"
detect all
let counts = {}
for each thing in detections
  let counts = put(counts, thing.label, get(counts, thing.label, 0) + 1)
end
print counts
if "person" in counts and counts.person >= busy
  print "busy street"
end
try
  print counts.bicycle
else
  print "no bicycles: {error}"
end
```

A map pairs text keys with values: `counts.person` (or `counts["person"]`) reads one, and `put` gives a new map with one key set. `param` is a setting with a default: `vexa run lesson.vexa --image street.jpg --set busy=5` changes it without editing the program. `try … else` runs the `else` part when something fails while running, here a missing key, with `error` holding the message.

## 10. Compile and format

```sh
vexa fmt --write lesson.vexa        # tidy layout
vexa compile lesson.vexa            # writes lesson.py
python lesson.py --image street.jpg
```

The compiler turns a program into a standalone, optimised Python script that gives the same results. Editors with the language server (`vexa lsp`, or the [VS Code extension](../editors/vscode/README.md)) show errors as you type, jump to definitions and rename names; see [Editor support](editors.md). `vexa run --trace` prints every step when a program surprises you.

## Next

- [Language reference](language-reference.md): every command and what it does to an image.
- [Specification](specification.md): grammar, types, scoping and evaluation, precisely.
- [Examples](../examples/): complete programs.
