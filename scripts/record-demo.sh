#!/usr/bin/env bash
# Steps for the Syntax Summit demo video. Run from the repository root:
#   scripts/record-demo.sh
# Each step prints its command, waits for Enter, then runs it, so the
# recording can follow the script in docs/notes/syntax-summit.md.
set -u
cd "$(dirname "$0")/../examples"
OUT="${TMPDIR:-/tmp}/vexa-demo"
mkdir -p "$OUT"
DEMO=../scripts/demo

step() {
  printf '\n\033[1;36m$ %s\033[0m' "$*"
  read -r _
  eval "$@"
}

step "cat demo.vexa"
step "vexa run demo.vexa --image street.jpg --output $OUT/demo.png"
step "cat $DEMO/mistakes.vexa"
step "vexa check $DEMO/mistakes.vexa"
step "cat street-report.vexa"
step "vexa run street-report.vexa --image street.jpg --output $OUT/report.png"
step "vexa run street-report.vexa --image street.jpg --set busy=2 --output $OUT/report.png | grep -E 'param|street'"
step "vexa run $DEMO/trace.vexa --trace"
step "vexa compile street-report.vexa -o $OUT/street_report.py"
step "sed -n '/^def run/,/^LINES/p' $OUT/street_report.py | head -30"
step "python $OUT/street_report.py --image street.jpg --output $OUT/compiled.png | tail -4"
step "vexa test checks.vexa --image street.jpg"
step "vexa run privacy.vexa --image street.jpg --output $OUT/privacy.png"
printf '\nOutputs are in %s\n' "$OUT"
