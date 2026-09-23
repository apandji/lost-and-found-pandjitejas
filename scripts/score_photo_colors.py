#!/usr/bin/env python3
"""Score walk photos from a colorgram palette (top colors + share)."""

import json
import math
from collections import defaultdict
from pathlib import Path

try:
    import colorgram
    from PIL import Image
except ImportError:
    raise SystemExit("Install scoring deps first: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt")


ROOT = Path(__file__).resolve().parents[1]
ROUTES = ROOT / "public" / "routes"
WALKS = ROOT / "public" / "walks"
MAX_EDGE = 400
EXTRACT = 8
STORE = 5
MAX_DELTA_E = 22.0

# Lab anchors for each assigned prompt. A swatch counts if its nearest
# prompt is the author's color and ΔE is within MAX_DELTA_E.
ANCHORS = {
    "yellow": [(230, 190, 30), (212, 175, 55), (238, 210, 80)],
    "red": [(194, 40, 40), (180, 30, 45), (120, 20, 25), (90, 15, 20)],
    "blue": [(40, 90, 190), (70, 130, 200), (50, 80, 160)],
    "light green": [(150, 200, 110), (180, 210, 140), (130, 170, 80)],
    "dark green": [(30, 90, 45), (45, 80, 40), (31, 51, 30)],
    "black": [(15, 15, 15), (40, 40, 40)],
    "white": [(245, 245, 245), (230, 230, 228)],
    "silver": [(168, 172, 178), (140, 144, 150)],
}


def srgb_to_linear(channel: float) -> float:
    channel /= 255.0
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def rgb_to_lab(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    r, g, b = (srgb_to_linear(channel) for channel in rgb)
    x = r * 0.4124564 + g * 0.3575761 + b * 0.1804375
    y = r * 0.2126729 + g * 0.7151522 + b * 0.0721750
    z = r * 0.0193339 + g * 0.1191920 + b * 0.9503041

    def pivot(value: float) -> float:
        return value ** (1 / 3) if value > 0.008856 else (7.787 * value + 16 / 116)

    fx, fy, fz = pivot(x / 0.95047), pivot(y), pivot(z / 1.08883)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def delta_e(left: tuple[float, float, float], right: tuple[float, float, float]) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(left, right)))


ANCHOR_LAB = {name: [rgb_to_lab(rgb) for rgb in swatches] for name, swatches in ANCHORS.items()}


def nearest_prompt(rgb: tuple[int, int, int]) -> tuple[str, float]:
    lab = rgb_to_lab(rgb)
    best_name = ""
    best_distance = math.inf
    for name, anchors in ANCHOR_LAB.items():
        distance = min(delta_e(lab, anchor) for anchor in anchors)
        if distance < best_distance:
            best_name, best_distance = name, distance
    return best_name, best_distance


def hex_color(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def extract_palette(path: Path) -> list[dict]:
    image = Image.open(path)
    image.thumbnail((MAX_EDGE, MAX_EDGE))
    colors = colorgram.extract(image, EXTRACT)
    palette = []
    for color in colors:
        rgb = (color.rgb.r, color.rgb.g, color.rgb.b)
        name, distance = nearest_prompt(rgb)
        palette.append({
            "hex": hex_color(rgb),
            "pct": round(100.0 * color.proportion, 1),
            "nearest": name,
            "deltaE": round(distance, 1),
        })
    return palette


def score_palette(palette: list[dict], assigned: str) -> float:
    return round(sum(swatch["pct"] for swatch in palette if swatch["nearest"] == assigned and swatch["deltaE"] <= MAX_DELTA_E), 1)


def color_label(value: str) -> str:
    return " ".join(part.capitalize() for part in value.split())


def score_walk(route: Path) -> dict | None:
    data = json.loads(route.read_text())
    prompts = data.get("photoPrompts") or {}
    photos_dir = WALKS / route.stem / "photos"
    photos: dict[str, dict] = {}
    totals: dict[str, list[float]] = defaultdict(list)

    for photo in data.get("photos") or []:
        name = photo.get("by")
        file = photo.get("file")
        prompt = prompts.get(name) if name else None
        if not file or not prompt or prompt.get("type") != "color":
            continue
        assigned = prompt.get("value")
        source = photos_dir / file
        if assigned not in ANCHORS or not source.exists():
            continue
        palette = extract_palette(source)
        percent = score_palette(palette, assigned)
        photos[file] = {
            "pct": percent,
            "palette": [{"hex": swatch["hex"], "pct": swatch["pct"]} for swatch in palette[:STORE]],
        }
        totals[name].append(percent)

    if not photos:
        return None

    people = {
        name: {
            "color": color_label(prompts[name]["value"]),
            "average": round(sum(scores) / len(scores), 1),
            "count": len(scores),
        }
        for name, scores in totals.items()
    }
    return {
        "engine": "colorgram",
        "photos": photos,
        "people": people,
        "anchors": {name: [hex_color(rgb) for rgb in swatches] for name, swatches in ANCHORS.items()},
    }


def main() -> None:
    routes = sorted(path for path in ROUTES.glob("*.json") if path.name.count(".") == 1)
    if not routes:
        raise SystemExit("No walk route files found")
    wrote = 0
    for route in routes:
        result = score_walk(route)
        if result is None:
            continue
        destination = route.with_suffix(".scores.json")
        destination.write_text(json.dumps(result, indent=2) + "\n")
        wrote += 1
        print(f"{route.stem}")
        for name, row in sorted(result["people"].items(), key=lambda item: (-item[1]["average"], item[0])):
            print(f"  {name:10} {row['average']:5.1f}%  {row['color']}  ({row['count']})")
    if not wrote:
        print("No color-prompted photos found to score")


if __name__ == "__main__":
    main()
