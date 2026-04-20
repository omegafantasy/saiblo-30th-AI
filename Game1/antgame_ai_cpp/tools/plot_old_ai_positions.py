#!/usr/bin/env python3
from __future__ import annotations

import ast
import math
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.lines import Line2D
from matplotlib.patches import RegularPolygon


REPO_ROOT = Path(__file__).resolve().parents[3]
OLD_AI_MAIN = REPO_ROOT / "past_AIs" / "ANTWar-AI" / "main.cpp"
CONSTANTS_PY = REPO_ROOT / "Game1" / "Ant-Game" / "SDK" / "utils" / "constants.py"
DEFAULT_OUTPUT = REPO_ROOT / "Game1" / "antgame_ai_cpp" / "old_ai_position_battlefield.png"


def parse_code_map(text: str) -> dict[str, int]:
    match = re.search(r"const int\s+([^;]+);", text, re.S)
    if not match:
        raise ValueError("failed to parse code definitions from old AI")
    mapping: dict[str, int] = {}
    for chunk in match.group(1).replace("\n", " ").split(","):
        item = chunk.strip()
        if not item:
            continue
        name, value = [part.strip() for part in item.split("=")]
        mapping[name] = int(value)
    return mapping


def parse_positions(text: str) -> list[list[tuple[int, int]]]:
    match = re.search(
        r"int positions\[2\]\[35\]\[2\]\s*=\s*(.*?)\s*;\s*bool emp_flag",
        text,
        re.S,
    )
    if not match:
        raise ValueError("failed to parse positions array from old AI")
    pairs = re.findall(r"\{\s*(-?\d+)\s*,\s*(-?\d+)\s*\}", match.group(1))
    coords = [(int(x), int(y)) for x, y in pairs]
    if len(coords) != 70:
        raise ValueError(f"unexpected number of position entries: {len(coords)}")
    return [coords[:35], coords[35:]]


def parse_map_property(text: str) -> tuple[tuple[tuple[int, ...], ...], int]:
    match = re.search(r"MAP_PROPERTY\s*=\s*(\(.+?\))\s*\n\nPATH_CELLS", text, re.S)
    if not match:
        raise ValueError("failed to parse MAP_PROPERTY from constants.py")
    map_property = ast.literal_eval(match.group(1))
    return map_property, len(map_property)


def center_xy(x: int, y: int, radius: float) -> tuple[float, float]:
    # The game's neighbor table is an odd-r offset system, but the rendered
    # hexes are flat-top. Odd rows are shifted left by half of the
    # center-to-center horizontal spacing.
    #
    # Let `radius` be the hex circumradius. For flat-top hexes:
    #   adjacent center distance = 1.5 * radius
    #   row-to-row vertical step = sqrt(3) / 2 * adjacent_distance
    step_x = 1.5 * radius
    return (
        step_x * x - 0.5 * step_x * (y & 1),
        -(math.sqrt(3.0) * 0.5 * step_x) * y,
    )


def build_legend(terrain_colors: dict[int, str], side_style: dict[int, dict[str, object]]) -> list[Line2D]:
    return [
        Line2D(
            [0],
            [0],
            marker="h",
            color="none",
            markerfacecolor=terrain_colors[0],
            markeredgecolor="#8c8c8c",
            markersize=12,
            label="Path",
        ),
        Line2D(
            [0],
            [0],
            marker="h",
            color="none",
            markerfacecolor=terrain_colors[1],
            markeredgecolor="#8c8c8c",
            markersize=12,
            label="Barrier",
        ),
        Line2D(
            [0],
            [0],
            marker="h",
            color="none",
            markerfacecolor=terrain_colors[2],
            markeredgecolor="#8c8c8c",
            markersize=12,
            label="P0 Highland",
        ),
        Line2D(
            [0],
            [0],
            marker="h",
            color="none",
            markerfacecolor=terrain_colors[3],
            markeredgecolor="#8c8c8c",
            markersize=12,
            label="P1 Highland",
        ),
        Line2D(
            [0],
            [0],
            marker=str(side_style[0]["marker"]),
            color=str(side_style[0]["color"]),
            linestyle="None",
            markersize=8,
            label="P0 old-AI slots",
        ),
        Line2D(
            [0],
            [0],
            marker=str(side_style[1]["marker"]),
            color=str(side_style[1]["color"]),
            linestyle="None",
            markersize=8,
            label="P1 old-AI slots",
        ),
    ]


def main() -> int:
    code_map = parse_code_map(OLD_AI_MAIN.read_text(encoding="utf-8"))
    positions = parse_positions(OLD_AI_MAIN.read_text(encoding="utf-8"))
    map_property, map_size = parse_map_property(CONSTANTS_PY.read_text(encoding="utf-8"))
    name_by_index = {index: name for name, index in code_map.items()}

    terrain_colors = {
        0: "#f7f1df",
        1: "#2f3b45",
        2: "#d9ecff",
        3: "#ffe0e0",
    }
    side_style = {
        0: {"color": "#0f4c81", "marker": "o", "size": 34, "dx": -0.08},
        1: {"color": "#b23a48", "marker": "s", "size": 34, "dx": 0.08},
    }

    layout_radius = 0.56
    # Keep the already-correct center layout, but shrink the rendered hexes so
    # adjacent cells meet exactly instead of slightly overlapping.
    hex_radius = layout_radius * (math.sqrt(3.0) / 2.0)
    fig, ax = plt.subplots(figsize=(18, 16), dpi=220)
    ax.set_facecolor("white")

    valid_centers: list[tuple[float, float]] = []
    for x in range(map_size):
        for y in range(map_size):
            terrain = map_property[x][y]
            if terrain == -1:
                continue
            cx, cy = center_xy(x, y, layout_radius)
            valid_centers.append((cx, cy))
            patch = RegularPolygon(
                (cx, cy),
                numVertices=6,
                radius=hex_radius,
                orientation=0.0,
                facecolor=terrain_colors[terrain],
                edgecolor="#8c8c8c",
                linewidth=0.8,
            )
            ax.add_patch(patch)
            ax.text(
                cx,
                cy - 0.33 * hex_radius,
                f"({x},{y})",
                ha="center",
                va="center",
                fontsize=5.0,
                color="#666666",
            )

    for side in (0, 1):
        style = side_style[side]
        for index, (x, y) in enumerate(positions[side]):
            name = name_by_index[index]
            cx, cy = center_xy(x, y, layout_radius)
            ax.scatter(
                [cx],
                [cy],
                s=float(style["size"]),
                c=str(style["color"]),
                marker=str(style["marker"]),
                zorder=5,
            )
            label = ax.text(
                cx + float(style["dx"]) * hex_radius,
                cy + 0.18 * hex_radius,
                name,
                ha="center",
                va="bottom",
                fontsize=7.6,
                color=str(style["color"]),
                weight="bold",
                zorder=6,
            )
            label.set_path_effects([pe.withStroke(linewidth=2.3, foreground="white")])

    for side in (0, 1):
        bx, by = positions[side][code_map["BASE"]]
        cx, cy = center_xy(bx, by, layout_radius)
        ax.scatter(
            [cx],
            [cy],
            s=180,
            facecolors="none",
            edgecolors=str(side_style[side]["color"]),
            linewidths=2.2,
            zorder=7,
        )

    ax.legend(
        handles=build_legend(terrain_colors, side_style),
        loc="upper center",
        ncol=3,
        frameon=False,
        bbox_to_anchor=(0.5, 1.03),
        fontsize=10,
    )
    ax.set_title("ANTWar Old AI Position Labels on Current Battlefield", fontsize=18, weight="bold", pad=28)
    ax.text(
        0.5,
        1.005,
        "Strict pointy-top odd-r hex geometry; labels parsed from past_AIs/ANTWar-AI/main.cpp",
        transform=ax.transAxes,
        ha="center",
        va="bottom",
        fontsize=10,
        color="#555555",
    )

    xs = [point[0] for point in valid_centers]
    ys = [point[1] for point in valid_centers]
    ax.set_xlim(min(xs) - 2.0 * hex_radius, max(xs) + 2.0 * hex_radius)
    ax.set_ylim(min(ys) - 2.5 * hex_radius, max(ys) + 3.0 * hex_radius)
    ax.set_aspect("equal")
    ax.axis("off")

    fig.tight_layout()
    fig.savefig(DEFAULT_OUTPUT, bbox_inches="tight")
    print(DEFAULT_OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
