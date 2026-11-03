"""Convert an ASCII Motion export into a game animation asset.

ASCII Motion's "TUI component" export (.tsx) embeds every frame as JSON with a color palette; this script
pulls that data out into ``rpg/ui/assets/animations/<name>.json``, which ``AsciiAnimation`` plays.

    python tools/import_ascii_motion.py path/to/export.tsx campfire --fps 10

Asset format (one string per row; ``colors`` rows use one palette key per cell, space = no color)::

    {"fps": 10, "width": 40, "height": 22, "palette": {"0": "#03071e", ...},
     "frames": [{"lines": ["  ..::  ", ...], "colors": ["  0011  ", ...]}, ...]}
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ASSET_DIR = Path(__file__).resolve().parent.parent / "rpg" / "ui" / "assets" / "animations"


def _js_object(source: str, name: str) -> str:
    """The literal after ``const NAME ... =`` up to its matching closing bracket."""
    match = re.search(rf"const {name}\b[^=]*=\s*", source)
    if not match:
        raise ValueError(f"Could not find '{name}' in the export")
    start = match.end()
    opener = source[start]
    closer = {"[": "]", "{": "}"}[opener]
    depth, in_string, escape = 0, False, False
    for i in range(start, len(source)):
        char = source[i]
        if in_string:
            escape = not escape and char == "\\"
            if char in "\"'" and not escape and char == quote:
                in_string = False
            continue
        if char in "\"'":
            in_string, quote = True, char
        elif char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return source[start:i + 1]
    raise ValueError(f"Unterminated '{name}'")


def _palette(source: str) -> dict[str, str]:
    body = _js_object(source, "COLORS_DARK")
    return {key.lstrip("c"): value for key, value in re.findall(r"(\w+)\s*:\s*'([^']+)'", body)}


def convert(source: str, fps: float) -> dict:
    palette = _palette(source)
    frames = json.loads(_js_object(source, "FRAMES"))
    width = max(len(line) for frame in frames for line in frame["content"])
    height = max(len(frame["content"]) for frame in frames)
    out = []
    for frame in frames:
        lines = [line.ljust(width) for line in frame["content"]] + [" " * width] * (height - len(frame["content"]))
        colors = [[" "] * width for _ in range(height)]
        for cell, key in frame.get("fgColors", {}).items():
            x, y = (int(v) for v in cell.split(","))
            short = key.lstrip("c")
            if short not in palette and key.startswith("#"):  # literal colors: add them to the palette
                short = next((k for k, v in palette.items() if v == key), None) or str(len(palette))
                palette.setdefault(short, key)
            if len(short) != 1:
                raise ValueError("More than 10 palette colors is not supported by this format")
            colors[y][x] = short
        out.append({"lines": lines, "colors": ["".join(row) for row in colors]})
    return {"fps": fps, "width": width, "height": height, "palette": palette, "frames": out}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("export", type=Path, help="ASCII Motion .tsx export")
    parser.add_argument("name", help="asset name, e.g. campfire")
    parser.add_argument("--fps", type=float, default=10.0, help="playback speed (default 10)")
    args = parser.parse_args()
    asset = convert(args.export.read_text(encoding="utf-8"), args.fps)
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    target = ASSET_DIR / f"{args.name}.json"
    target.write_text(json.dumps(asset, separators=(",", ":")), encoding="utf-8")
    print(f"{len(asset['frames'])} frames, {asset['width']}×{asset['height']} at {args.fps:g} fps -> {target}")


if __name__ == "__main__":
    main()
