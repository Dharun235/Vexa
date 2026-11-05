"""Render a command's real terminal output as an SVG for the README.

    uv run python scripts/terminal-svg.py --cwd scripts/demo OUTPUT.svg vexa check mistakes.vexa

Error kinds, carets and file positions are coloured. The image is static, so it looks the
same in every viewer.
"""

import argparse
import html
import re
import subprocess
import textwrap

WIDTH = 96  # characters per line before wrapping
CHAR, LINE, PAD = 8.4, 19, 18


def colour(line):
    """(text, css class) pieces for one output line."""
    if re.match(r"^\s*\^~*\s*$", line):
        return [(line, "caret")]
    match = re.match(r"^(\S+:\d+:\d+: )(check|syntax|warning)(:.*)$", line)
    if match:
        kind = "warn" if match.group(2) == "warning" else "error"
        return [(match.group(1), "place"), (match.group(2), kind), (match.group(3), "")]
    if re.match(r"^\d+ error", line):
        return [(line, "summary")]
    if line.startswith("  "):
        return [(line, "code")]
    return [(line, "")]


def render(command, output):
    lines = [("$ " + command, [("$ ", "prompt"), (command, "command")])]
    for raw in output.rstrip("\n").splitlines():
        if re.match(r"^\s*\^~*\s*$", raw) or raw.startswith("  "):
            lines.append((raw, colour(raw)))
            continue
        for part in textwrap.wrap(raw, WIDTH, subsequent_indent="    ") or [""]:
            lines.append((part, colour(part) if not part.startswith("    ") else [(part, "")]))
    width = PAD * 2 + CHAR * max(len(text) for text, _ in lines)
    height = PAD * 2 + 26 + LINE * len(lines)
    rows = []
    for number, (_, pieces) in enumerate(lines):
        spans = "".join(
            f'<tspan class="{css}">{html.escape(text)}</tspan>' if css else html.escape(text)
            for text, css in pieces
        )
        y = PAD + 26 + LINE * (number + 1) - 5
        rows.append(f'<text x="{PAD}" y="{y}" xml:space="preserve">{spans}</text>')
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" viewBox="0 0 {width:.0f} {height:.0f}" role="img" aria-label="Terminal: {html.escape(command)}">
<style>
text {{ font: 14px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; fill: #d4d4d4; }}
.prompt {{ fill: #6a9955; }} .command {{ fill: #ffffff; font-weight: bold; }}
.place {{ fill: #9cdcfe; }} .error {{ fill: #f48771; font-weight: bold; }} .warn {{ fill: #dcdcaa; font-weight: bold; }}
.caret {{ fill: #f48771; }} .code {{ fill: #ce9178; }} .summary {{ fill: #ffffff; font-weight: bold; }}
</style>
<rect width="100%" height="100%" rx="10" fill="#1e1e1e"/>
<circle cx="{PAD + 6}" cy="{PAD + 4}" r="6" fill="#ff5f57"/><circle cx="{PAD + 26}" cy="{PAD + 4}" r="6" fill="#febc2e"/><circle cx="{PAD + 46}" cy="{PAD + 4}" r="6" fill="#28c840"/>
{chr(10).join(rows)}
</svg>
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    parser.add_argument("--cwd", default=".")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = [part for part in args.command if part != "--"]
    result = subprocess.run(command, cwd=args.cwd, capture_output=True, text=True, check=False)
    with open(args.output, "w", encoding="utf-8") as stream:
        stream.write(render(" ".join(command), result.stdout + result.stderr))


if __name__ == "__main__":
    main()
