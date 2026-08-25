#!/usr/bin/env python3
"""Render live streak statistics inside the profile's terminal design."""

from __future__ import annotations

import argparse
import html
import os
from pathlib import Path
import re
import tempfile
import xml.etree.ElementTree as ET


NUMBER_RE = re.compile(r"^[\d,.]+[kKmMbB]?$")


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def extract_group(root: ET.Element, label: str) -> tuple[str, str]:
    """Return the value and date range from the group containing ``label``."""
    for group in (element for element in root.iter() if local_name(element.tag) == "g"):
        values = [
            "".join(text.itertext()).strip()
            for text in group.iter()
            if local_name(text.tag) == "text"
        ]
        if len(values) != 3 or label not in values:
            continue

        remaining = [value for value in values if value != label]
        number = next((value for value in remaining if NUMBER_RE.fullmatch(value)), None)
        date_range = next((value for value in remaining if value != number), None)
        if number and date_range:
            return number, date_range

    raise ValueError(f"Could not find the {label!r} group in the source SVG")


def render(source: Path) -> str:
    root = ET.parse(source).getroot()
    total, total_range = extract_group(root, "Total Contributions")
    current, current_range = extract_group(root, "Current Streak")
    longest, longest_range = extract_group(root, "Longest Streak")

    values = {
        "total": html.escape(total),
        "total_range": html.escape(total_range),
        "current": html.escape(current),
        "current_range": html.escape(current_range),
        "longest": html.escape(longest),
        "longest_range": html.escape(longest_range),
    }

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="900" height="330" viewBox="0 0 900 330" role="img" aria-labelledby="title desc">
  <title id="title">Milen Popat GitHub status</title>
  <desc id="desc">{values["total"]} total contributions, a current streak of {values["current"]}, and a longest streak of {values["longest"]}.</desc>

  <defs>
    <linearGradient id="surface" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#07130b" />
      <stop offset="1" stop-color="#020604" />
    </linearGradient>
    <filter id="shadow" x="-10%" y="-10%" width="120%" height="130%">
      <feDropShadow dx="0" dy="12" stdDeviation="18" flood-color="#000000" flood-opacity="0.35" />
    </filter>
  </defs>

  <rect x="18" y="18" width="864" height="294" rx="18" fill="url(#surface)" stroke="#238636" stroke-width="2" filter="url(#shadow)" />
  <path d="M18 72H882" stroke="#163d22" stroke-width="2" />

  <circle cx="51" cy="45" r="7" fill="#ff5f57" />
  <circle cx="75" cy="45" r="7" fill="#febc2e" />
  <circle cx="99" cy="45" r="7" fill="#28c840" />
  <text x="450" y="51" text-anchor="middle" fill="#7d8590" font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" font-size="14">milen@github: ~/status</text>

  <g font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace">
    <text x="48" y="111" fill="#7ee787" font-size="18">milen@github:~$ <tspan fill="#e6edf3">git status</tspan></text>

    <path d="M310 140V268M590 140V268" stroke="#163d22" stroke-width="2" />

    <g text-anchor="middle">
      <text x="170" y="184" fill="#7ee787" font-size="32" font-weight="700">{values["total"]}</text>
      <text x="170" y="220" fill="#7ee787" font-size="15">Total Contributions</text>
      <text x="170" y="252" fill="#b1bac4" font-size="13">{values["total_range"]}</text>

      <text x="450" y="184" fill="#f0f6fc" font-size="32" font-weight="700">{values["current"]}</text>
      <text x="450" y="220" fill="#f0f6fc" font-size="15">Current Streak</text>
      <text x="450" y="252" fill="#b1bac4" font-size="13">{values["current_range"]}</text>

      <text x="730" y="184" fill="#7ee787" font-size="32" font-weight="700">{values["longest"]}</text>
      <text x="730" y="220" fill="#7ee787" font-size="15">Longest Streak</text>
      <text x="730" y="252" fill="#b1bac4" font-size="13">{values["longest_range"]}</text>
    </g>

    <text x="48" y="291" fill="#7ee787" font-size="15">contributions: active<tspan fill="#7ee787">_</tspan></text>
  </g>
</svg>
'''


def write_atomic(destination: Path, content: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp",
        delete=False,
    ) as temporary:
        temporary.write(content)
        temporary_path = Path(temporary.name)

    try:
        ET.parse(temporary_path)
        os.replace(temporary_path, destination)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Raw streak SVG generated by the action")
    parser.add_argument("destination", type=Path, help="Terminal-styled SVG to write")
    args = parser.parse_args()
    write_atomic(args.destination, render(args.source))


if __name__ == "__main__":
    main()
