# Student agent handoff

- The student checkout has two example routes: a Sep 22 path-only walk (`4432175ada5c8dac`) and the shared Sep 23 photo walk (`54278a147abb3ad1`). The Sep 23 route, photo order, credits, and Are.na block IDs live in `public/routes/54278a147abb3ad1.json`. Other route files are intentionally not tracked.
- Read [SETUP.md](SETUP.md) before importing photos. Run `bun install` and `bun run sync:arena` to retrieve the Are.na images into ignored local assets. If given a channel export ZIP, use `bun run sync:arena --zip /path/to/export.zip`. Then run `bun run dev` or `bun run build`.
- New shared photos go into the [Lost and Found Are.na channel](https://www.are.na/laurel-schwulst/lost-and-found-lj1yyngzjzm). Record each new block ID and its contributor in the Sep 23 route JSON, then rerun `bun run sync:arena`. The site does not upload to Are.na by itself.
- Preserve contributor credit. Use the Are.na block's `user.name`/`user.slug`; if someone else uploaded on a contributor's behalf, check the intended credit with a human.
- Never infer a photo's capture time from its Are.na upload date. If the original has no reliable timestamp with timezone, omit `timeSeconds` and leave its route dot unset.
- Commit the route and code/docs changes. Keep originals in `.inbox/` and generated images in `public/walks/`; both are ignored by Git. Do not add the other walks or image binaries to the student repository.
