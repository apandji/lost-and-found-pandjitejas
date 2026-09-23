#!/usr/bin/env python3
"""Import one contributor's photo batch into the matching local walks."""

import argparse
from bisect import bisect_left
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import unicodedata


ROOT = Path(__file__).resolve().parents[1]
ROUTES = ROOT / "public" / "routes"
WALKS = ROOT / "public" / "walks"
IMAGE_SUFFIXES = {".heic", ".heif", ".jpeg", ".jpg", ".png"}


def slug(value: str) -> str:
    plain = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-") or "photo"


def image_number(name: str) -> str | None:
    match = re.search(r"(\d+)$", Path(name).stem)
    return match.group(1) if match else None


def input_files(paths: list[str]) -> list[Path]:
    found = []
    for raw in paths:
        path = Path(raw).expanduser().resolve()
        if path.is_dir():
            found.extend(file for file in path.rglob("*") if file.suffix.lower() in IMAGE_SUFFIXES)
        elif path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
            found.append(path)
        else:
            raise ValueError(f"No supported photo at {path}")
    return sorted(set(found))


def captured_at(meta: dict) -> int | None:
    date = meta.get("DateTimeOriginal")
    offset = meta.get("OffsetTimeOriginal")
    if date and offset:
        try:
            return int(datetime.strptime(date + offset, "%Y:%m:%d %H:%M:%S%z").timestamp())
        except ValueError:
            pass
    gps = meta.get("GPSDateTime")
    if gps:
        try:
            return int(datetime.strptime(gps, "%Y:%m:%d %H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp())
        except ValueError:
            pass
    return None


def nearest_seconds(times: list[int], captured: int) -> int:
    index = bisect_left(times, captured)
    return min(abs(times[i] - captured) for i in (index - 1, index) if 0 <= i < len(times))


def write_route(path: Path, data: dict) -> None:
    original = path.read_text()
    before, marker, _ = original.rpartition('  "photos": [')
    if not marker:
        raise ValueError(f"Cannot update photo list in {path}")
    entries = ",\n".join("    " + json.dumps(photo, ensure_ascii=False, separators=(",", ":")) for photo in data["photos"])
    updated = before + marker + ("\n" + entries + "\n" if entries else "") + "  ]\n}\n"
    json.loads(updated)
    path.write_text(updated)


def make_image(source: Path, destination: Path, size: str, quality: str) -> None:
    if destination.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["magick", str(source), "-auto-orient", "-resize", size, "-strip", "-quality", quality, str(destination)],
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="Photos or folders from one contributor")
    parser.add_argument("--by", required=True, help="Name shown under the photos")
    parser.add_argument("--walk", help="Only match this walk ID")
    parser.add_argument("--dry-run", action="store_true", help="Report matches without changing files")
    args = parser.parse_args()

    files = input_files(args.paths)
    if not files:
        parser.error("No supported photos found")
    routes = {}
    for path in ROUTES.glob("*.json"):
        if not re.fullmatch(r"[a-f0-9]{16}", path.stem):
            continue
        data = json.loads(path.read_text())
        routes[path.stem] = (path, data, sorted(point[0] for point in data["timeline"]))
    if args.walk:
        if args.walk not in routes:
            parser.error(f"Unknown walk ID: {args.walk}")
        routes = {args.walk: routes[args.walk]}
    if not routes:
        parser.error("No walks found in public/routes")

    metadata = json.loads(subprocess.check_output(
        ["exiftool", "-json", "-DateTimeOriginal", "-OffsetTimeOriginal", "-GPSDateTime", *map(str, files)]
    ))
    added = skipped = unmatched = 0
    changed = set()
    for meta in metadata:
        source = Path(meta["SourceFile"])
        captured = captured_at(meta)
        if captured is None:
            print(f"UNMATCHED {source.name}: no capture time with a timezone")
            unmatched += 1
            continue
        distance, walk_id = min((nearest_seconds(times, captured), walk_id) for walk_id, (_, _, times) in routes.items())
        if distance >= 60:
            print(f"UNMATCHED {source.name}: nearest walk is {walk_id} ({distance}s away)")
            unmatched += 1
            continue
        _, data, _ = routes[walk_id]
        digest = sha256(source.read_bytes()).hexdigest()[:8]
        filename = f"{slug(args.by)}-{slug(source.stem)}-{digest}.jpg"
        number = image_number(source.name)
        duplicate = next((photo for photo in data["photos"] if (
            abs(photo.get("timeSeconds", -1000) - captured) <= 1
            and (photo["file"] == filename or (number and image_number(photo["file"]) == number))
        )), None)
        if duplicate:
            print(f"SKIP {source.name}: already {duplicate['file']} on {walk_id}")
            skipped += 1
            continue

        if args.dry_run:
            print(f"MATCH {source.name} -> {walk_id}/{filename} ({distance}s from route)")
            added += 1
            continue
        photo_dir = WALKS / walk_id / "photos"
        thumb_dir = WALKS / walk_id / "thumbs"
        make_image(source, photo_dir / filename, "1350x1800>", "82")
        make_image(source, thumb_dir / filename, "360x480>", "78")
        data["photos"].append({"file": filename, "timeSeconds": captured, "by": args.by})
        changed.add(walk_id)
        added += 1
        print(f"ADD {source.name} -> {walk_id}/{filename} ({distance}s from route)")

    for walk_id in changed:
        path, data, _ = routes[walk_id]
        data["photos"].sort(key=lambda photo: photo.get("timeSeconds", float("inf")))
        write_route(path, data)
    print(f"{added} {'matched' if args.dry_run else 'added'}, {skipped} already present, {unmatched} unmatched")


if __name__ == "__main__":
    main()
