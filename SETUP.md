# Setup

Two example routes are in Git: a path-only September 22 walk (`4432175ada5c8dac`) and the September 23 photo walk (`54278a147abb3ad1`).
The Sep 23 route and photo credits are at `public/routes/54278a147abb3ad1.json`.
Other walks and all generated image files are local assets, not part of the student checkout.

Install [Bun](https://bun.sh/) and [ImageMagick](https://imagemagick.org/) first. Then:

```sh
bun install
bun run sync:arena
bun run score:colors
bun run dev
```

`sync:arena` reads the Are.na block IDs in the route file, downloads images from the [Lost and Found channel](https://www.are.na/laurel-schwulst/lost-and-found-lj1yyngzjzm), and creates local photos and thumbnails. It skips images already present. No Are.na token is needed. One existing Andrew block is no longer public through the API, so the command retrieves its already published image from the site.

If you have an Are.na channel export ZIP, you can use that instead of the API:

```sh
bun run sync:arena --zip /path/to/lost-and-found-lj1yyngzjzm.zip
```

The separately supplied Lou photo is not on Are.na or in the ZIP; it will not appear in a fresh checkout until its source is available locally or added to the channel.

## Add a photo to the shared walk

1. Have the contributor add the photo to the [Are.na channel](https://www.are.na/laurel-schwulst/lost-and-found-lj1yyngzjzm) while signed into their own account. This preserves their Are.na credit. The channel owner can also export a ZIP using **More → Download channel**; its CSV has block IDs, but contributor names must be checked on Are.na.
2. Find the image block ID from its Are.na URL or the export CSV. Read `https://api.are.na/v3/blocks/ID` to confirm its `user.name` and `user.slug`. The export CSV does not contain contributor names, so check Are.na or ask the contributor when a block is not public.
3. Add an entry to the `photos` array in `public/routes/54278a147abb3ad1.json`:

   ```json
   {"file":"arena-50704064.jpg","by":"Sol","arenaId":50704064,"arenaUser":"sol-bae","sourceTitle":"IMG_6745.JPG","timeSeconds":1790175239}
   ```

   Use that photo's actual ID and contributor. `timeSeconds` is optional: include it only when the original photo has a trustworthy capture time with a timezone. It is a Unix timestamp in seconds. Do not substitute the Are.na upload time; omitting it keeps the photo in the gallery without placing a misleading dot on the route.
4. Run `bun run sync:arena` and `bun run score:colors`, then `bun run build`. Restart `bun run dev` if it was already running. Commit the route JSON change; generated images remain ignored by Git. Color percentages are written to `public/routes/54278a147abb3ad1.scores.json`.

For photos received directly rather than through Are.na, keep originals in `.inbox/` and run:

```sh
bun run import:photos --by "Contributor Name" --walk 54278a147abb3ad1 .inbox/their-photos
```

That importer needs `exiftool` and ImageMagick. It uses embedded capture times, skips known duplicates, and reports files it cannot place. Run with `--dry-run` to inspect matches first. Directly imported images stay local; for students to download them later, also add them to Are.na and record their block IDs as above.
