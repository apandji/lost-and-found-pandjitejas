#!/usr/bin/env python3
"""Download the shared Sep 23 walk's referenced Are.na images into ignored public assets."""

import argparse
import csv
import json
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
from urllib.request import Request, urlopen
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
WALK_ID = "54278a147abb3ad1"
CHANNEL = "lost-and-found-lj1yyngzjzm"
ROUTE = ROOT / "public" / "routes" / f"{WALK_ID}.json"
ASSETS = ROOT / "public" / "walks" / WALK_ID
USER_AGENT = "lost-and-found-photo-sync/1.0"
FALLBACKS = {
    # This block is in the channel export but is no longer readable via the public API.
    50704147: f"https://lost-and-found-bgo.pages.dev/walks/{WALK_ID}/photos/arena-50704147.jpg",
}


def open_url(url: str):
    return urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=30)


def channel_images(wanted: set[int]) -> dict[int, dict]:
    found = {}
    page = 1
    while wanted - found.keys():
        url = f"https://api.are.na/v3/channels/{CHANNEL}/contents?per=24&page={page}"
        with open_url(url) as response:
            result = json.load(response)
        for block in result["data"]:
            if block["id"] in wanted and block.get("type") == "Image":
                found[block["id"]] = block
        page = result["meta"]["next_page"]
        if page is None:
            break
    return found


def make_image(source: Path, destination: Path, size: str, quality: str) -> None:
    if destination.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=destination.parent) as directory:
        temporary = Path(directory) / "image.jpg"
        subprocess.run(
            ["magick", str(source), "-auto-orient", "-resize", size, "-strip", "-quality", quality, str(temporary)],
            check=True,
        )
        temporary.replace(destination)


def zip_images(archive: ZipFile) -> dict[int, str]:
    csv_name = next((name for name in archive.namelist() if name.endswith(".csv")), None)
    if csv_name is None:
        raise SystemExit("Are.na ZIP has no CSV manifest")
    with archive.open(csv_name) as stream:
        rows = csv.DictReader(line.decode("utf-8-sig") for line in stream)
        return {int(row["ID"]): row["Filename"] for row in rows if row["ID"] and row["Filename"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", type=Path, help="Use a downloaded Are.na channel ZIP instead of the public API")
    args = parser.parse_args()
    if not shutil.which("magick"):
        raise SystemExit("ImageMagick is required (install it, then rerun this command)")
    photos = [photo for photo in json.loads(ROUTE.read_text())["photos"] if "arenaId" in photo]
    missing = [photo for photo in photos if not all(
        (ASSETS / folder / photo["file"]).exists() for folder in ("photos", "thumbs")
    )]
    if not missing:
        print(f"All {len(photos)} Are.na photos are already available locally")
        return

    need_originals = {photo["arenaId"] for photo in missing if not (ASSETS / "photos" / photo["file"]).exists()}
    archive = ZipFile(args.zip.expanduser()) if args.zip else None
    filenames = zip_images(archive) if archive else {}
    blocks = {} if archive else channel_images(need_originals)
    unavailable = need_originals - (filenames.keys() if archive else blocks.keys() | FALLBACKS.keys())
    if unavailable:
        source = "ZIP" if archive else "public channel"
        raise SystemExit(f"Image blocks not found in {source}: {sorted(unavailable)}")

    try:
        for photo in missing:
            full = ASSETS / "photos" / photo["file"]
            thumb = ASSETS / "thumbs" / photo["file"]
            if not full.exists():
                block = blocks.get(photo["arenaId"])
                if block:
                    expected_user = photo.get("arenaUser")
                    actual_user = block["user"]["slug"]
                    if expected_user and actual_user != expected_user:
                        raise SystemExit(f"Are.na contributor changed for block {photo['arenaId']}: {actual_user}")
                with TemporaryDirectory() as directory:
                    original = Path(directory) / "original"
                    if archive:
                        stream = archive.open(filenames[photo["arenaId"]])
                    else:
                        stream = open_url(block["image"]["src"] if block else FALLBACKS[photo["arenaId"]])
                    with stream, original.open("wb") as output:
                        shutil.copyfileobj(stream, output)
                    make_image(original, full, "1350x1800>", "82")
            make_image(full, thumb, "360x480>", "78")
            print(f"Ready {photo['file']} ({photo['by']})")
    finally:
        if archive:
            archive.close()
    print(f"Synced {len(missing)} of {len(photos)} Are.na photos")


if __name__ == "__main__":
    main()
