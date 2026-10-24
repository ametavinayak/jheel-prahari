// Shapes returned by the Jheel Prahari API, and the browser-side client (always through /api/jheel).

export type Scene = {
  date: string; scene: string; area_km2: number; clear_over_lake: number; after_burst: boolean;
  outline: GeoJSON.Polygon | GeoJSON.MultiPolygon; image: string; image_bounds: [[number, number], [number, number]];
};
export type Pass = { item: string; date: string; water_m2: number };
export type DrainCheck = { before: Pass; after: Pass; threshold_db: number; area_loss: number; mean_log_ratio_db: number; drained: boolean };
export type EtaRow = {
  id: string; name: string; kind: string; lat: number; lon: number; action: string;
  river_km: number; offset_m: number; on_path: boolean; eta_min: number; eta_max: number;
};
export type Lake = {
  lake: { id: string; name: string; aoi: number[]; seed: [number, number] };
  series: Scene[];
  growth: { from: string; to: string; from_km2: number; to_km2: number; pct: number; trend_km2_per_year: number; years: number };
  drain_check: DrainCheck;
  flowpath: GeoJSON.LineString & { length_km: number };
  eta: EtaRow[];
  speed_kmh: { kmh_fast: number; kmh_slow: number };
  calibration: { asset: string; minutes_min: number; minutes_max: number };
  method: Record<string, string>;
};
export type AlertMsg = { place: string; name: string; kind: string; river_km: number; eta_min: number; eta_max: number; text: string; channel: string; status: string };
export type AlertEvent = { id: string; lake: string; source: string; source_label: string; detail: string | null; at_utc: string; messages: AlertMsg[] };
export type ScanState = { state: "idle" | "running" | "done" | "error"; result: DrainCheck | null; error: string | null; started: number | null; alert: AlertEvent | null };
export type Step = { tool: string; detail: string; source: string | null; ms: number };
export type Answer = { answer: string; evidence: string[]; intent: string; steps: Step[] };

export type AreaLake = {
  id: string; class: "high" | "watch" | "low" | "stable"; score: number; why: string;
  area_km2: number; old_area_km2: number | null; growth_pct: number | null; new_lake: boolean;
  elevation_m: number; ice_contact: boolean; glacier_fed: boolean; outlet_slope_deg: number | null;
  lat: number; lon: number; outline: GeoJSON.Polygon | GeoJSON.MultiPolygon;
};
export type AreaResult = {
  box: [number, number, number, number]; as_of: string; place: { name: string; lat: number; lon: number } | null;
  recent: { item: string; date: string; clear: number }; older: { item: string; date: string; clear: number } | null;
  lakes: AreaLake[]; counts: Record<"high" | "watch" | "low" | "stable", number>; method: string;
};
export type AreaJob = { id: string; state: "running" | "done" | "error"; stage: string; result: AreaResult | null; error: string | null; started: number };

// Scene images are static, so they ship with the site and come off the CDN: public/scenes holds web/scenes as
// WebP (2 MB PNG -> ~170 KB; the PNGs made the landing timelapse starve every other request).
export const sceneUrl = (s: Scene) => `/${s.image.replace(/\.png$/, ".webp")}`;

async function call<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api/jheel/${path}`, body === undefined ? { cache: "no-store" } : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || res.statusText);
  return data as T;
}

export const api = {
  lake: () => call<Lake>("lake"),
  alerts: () => call<AlertEvent[]>("alerts"),
  trigger: (source: string) => call<AlertEvent>("trigger", { source }),
  ask: (question: string) => call<Answer>("ask", { question }),
  startScan: () => call<ScanState>("scan", {}),
  scan: () => call<ScanState>("scan"),
  analyze: (req: { query?: string; bbox?: number[]; as_of?: string }) => call<AreaJob>("analyze", req),
  areaJob: (id: string) => call<AreaJob>(`analyze/${id}`),
};

// Server components read the backend directly (no proxy hop, no client loading state). A failure throws: the
// build then fails loudly, and a failed hourly refresh keeps serving the last good page instead of caching an error.
export async function lakeServer(): Promise<Lake> {
  const base = (process.env.JHEEL_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
  const r = await fetch(`${base}/api/lake`, { next: { revalidate: 3600 }, signal: AbortSignal.timeout(15000) });
  if (!r.ok) throw new Error(`lake API answered ${r.status} at ${base}`);
  return (await r.json()) as Lake;
}
