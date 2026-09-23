import { readdir, readFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join } from "node:path";

export interface WalkPhoto {
  src: string;
  thumbnailSrc: string;
  by: string | null;
  marker: [number, number] | null;
  color: string | null;
  colorKey: string | null;
  colorPct: number | null;
}

export interface WalkStanding {
  by: string;
  average: number;
  colorKey: string;
}

export interface Walk {
  id: string;
  date: string;
  startedAt: number;
  duration: string;
  thumbnailPath: string;
  path: string;
  photos: WalkPhoto[];
  standings: WalkStanding[];
}

interface WalkData {
  date: string;
  thumbnailPath: string;
  path: string;
  timeline: Array<[timeSeconds: number, x: number, y: number]>;
  photos: Array<{ file: string; timeSeconds?: number; by?: string }>;
  photoPrompts?: Record<string, { type: string; value: string }>;
}

interface WalkScores {
  photos?: Record<string, number>;
}

const walksRoot = join(process.cwd(), "public", "routes");

function markerAtTime(timeline: WalkData["timeline"], timeSeconds?: number): [number, number] | null {
  if (timeSeconds === undefined || !Number.isFinite(timeSeconds)) return null;
  let nearest: [number, number] | null = null;
  let distance = 60;
  for (const [at, x, y] of timeline) {
    const delta = Math.abs(at - timeSeconds);
    if (delta < distance) { nearest = [x, y]; distance = delta; }
  }
  return nearest;
}

function colorLabel(value: string): string {
  return value.split(/\s+/).map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(" ");
}

function colorKey(value: string): string {
  return value.trim().toLowerCase().replace(/\s+/g, "-");
}

async function loadScores(id: string): Promise<WalkScores["photos"]> {
  const file = join(walksRoot, `${id}.scores.json`);
  if (!existsSync(file)) return {};
  const data = JSON.parse(await readFile(file, "utf8")) as WalkScores;
  return data.photos ?? {};
}

function standingsFor(photos: WalkPhoto[]): WalkStanding[] {
  const totals = new Map<string, { sum: number; count: number; colorKey: string }>();
  for (const photo of photos) {
    if (!photo.by || photo.colorPct === null || !photo.colorKey) continue;
    const current = totals.get(photo.by) ?? { sum: 0, count: 0, colorKey: photo.colorKey };
    current.sum += photo.colorPct;
    current.count += 1;
    totals.set(photo.by, current);
  }
  return [...totals.entries()]
    .map(([by, { sum, count, colorKey }]) => ({ by, average: Math.round(sum / count), colorKey }))
    .sort((a, b) => b.average - a.average || a.by.localeCompare(b.by));
}

export async function loadWalks(): Promise<Walk[]> {
  const files = (existsSync(walksRoot) ? await readdir(walksRoot) : []).filter((file) => /^[a-f0-9]{16}\.json$/.test(file));
  const walks = await Promise.all(files.map(async (file) => {
    const id = file.slice(0, -5);
    const data = JSON.parse(await readFile(join(walksRoot, file), "utf8")) as WalkData;
    if (!data.path || !data.thumbnailPath || !data.timeline.length) throw new Error(`Invalid walk: ${id}`);
    const minutes = Math.round((data.timeline.at(-1)![0] - data.timeline[0][0]) / 60);
    const duration = `${minutes >= 60 ? `${Math.floor(minutes / 60)}h ` : ""}${minutes % 60}m`;
    const scores = await loadScores(id);
    const prompts = data.photoPrompts ?? {};
    const photos = data.photos.filter((photo) => existsSync(join(process.cwd(), "public", "walks", id, "photos", photo.file))).sort((a, b) => (a.timeSeconds ?? Infinity) - (b.timeSeconds ?? Infinity)).map((photo): WalkPhoto => {
      const src = `/walks/${id}/photos/${encodeURIComponent(photo.file)}`;
      const thumbnailSrc = `/walks/${id}/thumbs/${encodeURIComponent(photo.file)}`;
      const prompt = photo.by ? prompts[photo.by] : undefined;
      const promptColor = prompt?.type === "color" ? prompt.value : undefined;
      const raw = promptColor !== undefined ? scores[photo.file] : undefined;
      const scored = raw !== undefined;
      return {
        src,
        thumbnailSrc: existsSync(join(process.cwd(), "public", "walks", id, "thumbs", photo.file)) ? thumbnailSrc : src,
        by: photo.by ?? null,
        marker: markerAtTime(data.timeline, photo.timeSeconds),
        color: scored && promptColor ? colorLabel(promptColor) : null,
        colorKey: scored && promptColor ? colorKey(promptColor) : null,
        colorPct: scored ? Math.round(raw) : null,
      };
    });
    return { id, date: data.date, startedAt: data.timeline[0][0], duration, thumbnailPath: data.thumbnailPath, path: data.path, photos, standings: standingsFor(photos) };
  }));
  return walks.sort((a, b) => b.startedAt - a.startedAt);
}
