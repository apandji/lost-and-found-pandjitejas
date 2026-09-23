#!/usr/bin/env python3
"""Score walk photos by how much of each author's assigned color they contain."""

import json
import shutil
import subprocess
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROUTES = ROOT / "public" / "routes"
WALKS = ROOT / "public" / "walks"
MAX_EDGE = 320

# HSV boxes. Hue is degrees (None = ignore hue). Saturation and value are 0–1.
# Light / dark green share a hue and split on value, with a gap between them.
# Black / white / silver ignore hue and sit in stacked low-saturation bands.
COLORS = {
    "yellow": {"h": [(38, 72)], "s": (0.28, 1.0), "v": (0.32, 1.0)},
    "red": {"h": [(0, 14), (346, 360)], "s": (0.32, 1.0), "v": (0.18, 1.0)},
    "blue": {"h": [(195, 255)], "s": (0.25, 1.0), "v": (0.18, 1.0)},
    "light green": {"h": [(70, 160)], "s": (0.08, 1.0), "v": (0.50, 1.0)},
    "dark green": {"h": [(80, 155)], "s": (0.10, 1.0), "v": (0.0, 0.55)},
    "black": {"h": None, "s": (0.0, 0.30), "v": (0.0, 0.40)},
    "white": {"h": None, "s": (0.0, 0.15), "v": (0.85, 1.0)},
    "silver": {"h": None, "s": (0.0, 0.12), "v": (0.48, 0.78)},
}


def rgb_to_hsv(r: int, g: int, b: int) -> tuple[float, float, float]:
    r_, g_, b_ = r / 255.0, g / 255.0, b / 255.0
    mx, mn = max(r_, g_, b_), min(r_, g_, b_)
    delta = mx - mn
    value = mx
    saturation = 0.0 if mx == 0 else delta / mx
    if delta == 0:
        hue = 0.0
    elif mx == r_:
        hue = (60 * ((g_ - b_) / delta) + 360) % 360
    elif mx == g_:
        hue = 60 * ((b_ - r_) / delta) + 120
    else:
        hue = 60 * ((r_ - g_) / delta) + 240
    return hue, saturation, value


def in_range(value: float, bounds: tuple[float, float]) -> bool:
    return bounds[0] <= value <= bounds[1]


def pixel_matches(h: float, s: float, v: float, box: dict) -> bool:
    if not in_range(s, box["s"]) or not in_range(v, box["v"]):
        return False
    hues = box["h"]
    if hues is None:
        return True
    return any(start <= h <= end for start, end in hues)


def json_colors() -> dict:
    packed = {}
    for name, box in COLORS.items():
        packed[name] = {
            "h": None if box["h"] is None else [list(span) for span in box["h"]],
            "s": list(box["s"]),
            "v": list(box["v"]),
        }
    return packed


def sample_pixels(path: Path) -> bytes:
    raw = subprocess.run(
        ["magick", str(path), "-auto-orient", "-resize", f"{MAX_EDGE}x{MAX_EDGE}>", "-depth", "8", "rgb:-"],
        check=True,
        capture_output=True,
    )
    if len(raw.stdout) % 3:
        raise SystemExit(f"Pixel dump size mismatch for {path.name}: {len(raw.stdout)}")
    return raw.stdout


def score_image(path: Path, box: dict) -> float:
    pixels = sample_pixels(path)
    matched = 0
    count = len(pixels) // 3
    for i in range(0, len(pixels), 3):
        if pixel_matches(*rgb_to_hsv(pixels[i], pixels[i + 1], pixels[i + 2]), box):
            matched += 1
    return 100.0 * matched / count if count else 0.0


def color_label(value: str) -> str:
    return " ".join(part.capitalize() for part in value.split())


def score_walk(route: Path) -> dict | None:
    data = json.loads(route.read_text())
    prompts = data.get("photoPrompts") or {}
    walk_id = route.stem
    photos_dir = WALKS / walk_id / "photos"
    photos: dict[str, float] = {}
    totals: dict[str, list[float]] = defaultdict(list)

    for photo in data.get("photos") or []:
        name = photo.get("by")
        file = photo.get("file")
        prompt = prompts.get(name) if name else None
        if not file or not prompt or prompt.get("type") != "color":
            continue
        value = prompt.get("value")
        box = COLORS.get(value)
        source = photos_dir / file
        if box is None or not source.exists():
            continue
        percent = round(score_image(source, box), 1)
        photos[file] = percent
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
    return {"photos": photos, "people": people, "colors": json_colors()}


def main() -> None:
    if not shutil.which("magick"):
        raise SystemExit("ImageMagick is required (install it, then rerun this command)")
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
