#!/usr/bin/env python3
"""Render GitHub's contribution calendar inside the profile's terminal design."""

from __future__ import annotations

import argparse
from datetime import date
import html
import json
import os
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET


LEVEL_COLORS = {
    "NONE": "#0b1710",
    "FIRST_QUARTILE": "#123d20",
    "SECOND_QUARTILE": "#1d6f32",
    "THIRD_QUARTILE": "#2ea043",
    "FOURTH_QUARTILE": "#7ee787",
}
GRID_X = 126
GRID_Y = 157
CELL_SIZE = 10
CELL_STEP = 13


def load_calendar(source: Path) -> dict:
    with source.open(encoding="utf-8") as handle:
        payload = json.load(handle)

    if payload.get("errors"):
        raise ValueError(f"GitHub GraphQL returned errors: {payload['errors']}")

    try:
        return payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    except (KeyError, TypeError) as error:
        raise ValueError("Contribution calendar is missing from the GitHub response") from error


def month_labels(calendar: dict) -> list[tuple[int, str]]:
    weeks = calendar["weeks"]
    labels: list[tuple[int, str]] = []

    for month in calendar["months"]:
        first_day = date.fromisoformat(month["firstDay"])
        week_index = next(
            (
                index
                for index, week in enumerate(weeks)
                if any(
                    date.fromisoformat(day["date"]).year == first_day.year
                    and date.fromisoformat(day["date"]).month == first_day.month
                    for day in week["contributionDays"]
                )
            ),
            None,
        )
        if week_index is not None:
            labels.append((week_index, month["name"][:3]))

    # GitHub includes the partial month at each edge of the one-year window.
    # Prefer the newer label when two labels would visually collide.
    spaced_labels: list[tuple[int, str]] = []
    for label in labels:
        if spaced_labels and label[0] - spaced_labels[-1][0] < 3:
            spaced_labels[-1] = label
        else:
            spaced_labels.append(label)

    return spaced_labels


def render(calendar: dict) -> str:
    weeks = calendar["weeks"]
    days = [day for week in weeks for day in week["contributionDays"]]
    if not days:
        raise ValueError("Contribution calendar contains no days")

    total = int(calendar["totalContributions"])
    first_date = days[0]["date"]
    last_date = days[-1]["date"]

    month_markup = "\n".join(
        f'      <text x="{GRID_X + week_index * CELL_STEP}" y="143">{html.escape(name)}</text>'
        for week_index, name in month_labels(calendar)
    )

    square_markup: list[str] = []
    for week_index, week in enumerate(weeks):
        for day in week["contributionDays"]:
            weekday = int(day["weekday"])
            count = int(day["contributionCount"])
            level = day["contributionLevel"]
            color = LEVEL_COLORS.get(level, LEVEL_COLORS["NONE"])
            stroke = ' stroke="#163d22" stroke-width="1"' if level == "NONE" else ""
            x = GRID_X + week_index * CELL_STEP
            y = GRID_Y + weekday * CELL_STEP
            label = "contribution" if count == 1 else "contributions"
            square_markup.append(
                f'      <rect x="{x}" y="{y}" width="{CELL_SIZE}" height="{CELL_SIZE}" rx="2" fill="{color}"{stroke}>'
                f'<title>{html.escape(day["date"])}: {count} {label}</title></rect>'
            )

    legend_x = 660
    legend_cells = "".join(
        f'<rect x="{legend_x + index * CELL_STEP}" y="285" width="{CELL_SIZE}" height="{CELL_SIZE}" rx="2" fill="{color}" />'
        for index, color in enumerate(LEVEL_COLORS.values())
    )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="900" height="350" viewBox="0 0 900 350" role="img" aria-labelledby="title desc">
  <title id="title">Milen Popat contribution graph</title>
  <desc id="desc">{total} GitHub contributions from {html.escape(first_date)} through {html.escape(last_date)}.</desc>

  <defs>
    <linearGradient id="surface" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#07130b" />
      <stop offset="1" stop-color="#020604" />
    </linearGradient>
    <filter id="shadow" x="-10%" y="-10%" width="120%" height="130%">
      <feDropShadow dx="0" dy="12" stdDeviation="18" flood-color="#000000" flood-opacity="0.35" />
    </filter>
  </defs>

  <rect x="18" y="18" width="864" height="314" rx="18" fill="url(#surface)" stroke="#238636" stroke-width="2" filter="url(#shadow)" />
  <path d="M18 72H882" stroke="#163d22" stroke-width="2" />

  <circle cx="51" cy="45" r="7" fill="#ff5f57" />
  <circle cx="75" cy="45" r="7" fill="#febc2e" />
  <circle cx="99" cy="45" r="7" fill="#28c840" />
  <text x="450" y="51" text-anchor="middle" fill="#7d8590" font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" font-size="14">milen@github: ~/contributions</text>

  <g font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace">
    <text x="48" y="111" fill="#7ee787" font-size="18">milen@github:~$ <tspan fill="#e6edf3">git log --graph --since=1.year</tspan></text>

    <g fill="#7d8590" font-size="11">
{month_markup}
      <text x="82" y="178">Mon</text>
      <text x="82" y="204">Wed</text>
      <text x="82" y="230">Fri</text>
    </g>

    <g>
{chr(10).join(square_markup)}
    </g>

    <text x="48" y="295" fill="#b1bac4" font-size="13">{total} contributions in the last year</text>
    <text x="620" y="295" fill="#7d8590" font-size="11">Less</text>
    {legend_cells}
    <text x="731" y="295" fill="#7d8590" font-size="11">More</text>
    <text x="48" y="318" fill="#7ee787" font-size="14">activity: visible<tspan fill="#7ee787">_</tspan></text>
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
    parser.add_argument("source", type=Path, help="GitHub contribution-calendar JSON")
    parser.add_argument("destination", type=Path, help="Terminal-styled SVG to write")
    args = parser.parse_args()
    write_atomic(args.destination, render(load_calendar(args.source)))


if __name__ == "__main__":
    main()
