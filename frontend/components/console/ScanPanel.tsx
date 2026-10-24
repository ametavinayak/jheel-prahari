"use client";
import { motion } from "framer-motion";
import { Mountain, Snowflake, TrendingUp, TriangleAlert, ShieldCheck, Loader2, MapPinned } from "lucide-react";
import type { AreaJob, AreaLake } from "@/lib/api";
import { CLASS_COLOR } from "./MapView";

const LABEL: Record<AreaLake["class"], string> = { high: "High hazard", watch: "Watch", low: "Low", stable: "Stable" };
const STAGES = ["finding the place", "recent scene", "older scene", "elevation"];

export function ScanPanel({ job, selected, onSelect }: { job: AreaJob | null; selected: string | null; onSelect: (id: string) => void }) {
  if (!job) {
    return (
      <div className="glass rounded-2xl p-6 text-center">
        <MapPinned className="mx-auto h-8 w-8 text-glacier" />
        <div className="mt-3 font-medium">Screen any area</div>
        <p className="mt-2 text-sm leading-relaxed text-muted">
          Search a place above, or pan the map and press <b className="text-fg">Analyse view</b>. Every lake in a ~18 km box is found,
          compared with an older scene and scored. Only glacier-fed, growing lakes are flagged.
        </p>
      </div>
    );
  }
  if (job.state === "running") {
    const k = Math.max(0, STAGES.indexOf(job.stage));
    return (
      <div className="glass relative overflow-hidden rounded-2xl p-5">
        <div className="flex items-center gap-2 text-sm"><Loader2 className="h-4 w-4 animate-spin text-glacier" /> Screening the area…</div>
        <ol className="mt-4 space-y-2.5">
          {["Locate the area", "Clearest recent Sentinel-2 scene", "Older scene for comparison", "Elevation + glaciers + scoring"].map((t, i) => (
            <li key={t} className={`flex items-center gap-3 text-sm ${i < k ? "text-fg" : i === k ? "text-glacier" : "text-faint"}`}>
              <span className={`grid h-5 w-5 place-items-center rounded-full border font-mono text-[10px] ${i < k ? "border-glacier bg-glacier text-ink" : i === k ? "border-glacier" : "border-line"}`}>{i < k ? "✓" : i + 1}</span>{t}
            </li>
          ))}
        </ol>
        <div className="mt-4 h-1 overflow-hidden rounded-full bg-white/5"><div className="shimmer h-full w-full" /></div>
        <div className="mt-2 font-mono text-[10px] text-faint">usually 40–60 s · reads public Copernicus data live</div>
      </div>
    );
  }
  if (job.state === "error") return <div className="glass rounded-2xl p-5 text-sm text-alarm">{job.error}</div>;

  const r = job.result!;
  return (
    <div className="space-y-3">
      <div className="glass rounded-2xl p-4">
        <div className="font-mono text-[11px] tracking-[.18em] text-glacier">AREA SCREENING</div>
        {r.place && <div className="mt-1 line-clamp-1 text-sm text-muted">{r.place.name}</div>}
        <div className="mt-3 grid grid-cols-4 gap-2">
          {(["high", "watch", "low", "stable"] as const).map((c) => (
            <div key={c} className="rounded-xl border border-line bg-white/[.02] p-2 text-center">
              <div className="text-xl font-semibold" style={{ color: CLASS_COLOR[c] }}>{r.counts[c]}</div>
              <div className="text-[10px] text-muted">{LABEL[c]}</div>
            </div>
          ))}
        </div>
        <div className="mt-3 font-mono text-[10px] leading-relaxed text-faint">
          recent {r.recent.date} · older {r.older?.date ?? "none"}{r.as_of && r.as_of < new Date().toISOString().slice(0, 10) ? ` · as of ${r.as_of}` : ""}
        </div>
      </div>
      {r.lakes.length === 0 && <div className="glass rounded-2xl p-5 text-sm text-muted">No lakes of at least 0.01 km² in this area.</div>}
      {r.lakes.map((lk, i) => (
        <motion.button key={lk.id} onClick={() => onSelect(lk.id)} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.03 }}
          className={`glass block w-full rounded-2xl p-4 text-left transition hover:border-line-strong ${selected === lk.id ? "!border-white/40" : ""}`}>
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs text-faint">{lk.id}</span>
              <span className="rounded-md px-2 py-0.5 font-mono text-[10px] font-bold" style={{ background: `${CLASS_COLOR[lk.class]}22`, color: CLASS_COLOR[lk.class] }}>{LABEL[lk.class].toUpperCase()}</span>
            </div>
            {lk.class === "stable" ? <ShieldCheck className="h-4 w-4 text-safe" /> : <div className="text-right"><div className="font-mono text-[10px] text-faint">score</div><div className="text-lg font-semibold leading-none" style={{ color: CLASS_COLOR[lk.class] }}>{lk.score}</div></div>}
          </div>
          {lk.class !== "stable" && (
            <div className="mt-2 h-1 overflow-hidden rounded-full bg-white/5"><div className="h-full rounded-full" style={{ width: `${lk.score}%`, background: CLASS_COLOR[lk.class] }} /></div>
          )}
          <div className="mt-3 grid grid-cols-4 gap-2 text-xs">
            <div><div className="text-faint">area</div><div className="font-medium">{lk.area_km2} km²</div></div>
            <div><div className="flex items-center gap-1 text-faint"><TrendingUp className="h-3 w-3" />growth</div><div className={`font-medium ${lk.growth_pct && lk.growth_pct > 5 ? "text-watch" : ""}`}>{lk.growth_pct === null ? (lk.new_lake ? "new" : "–") : `${lk.growth_pct > 0 ? "+" : ""}${lk.growth_pct}%`}</div></div>
            <div><div className="flex items-center gap-1 text-faint"><Mountain className="h-3 w-3" />elev</div><div className="font-medium">{lk.elevation_m.toLocaleString()} m</div></div>
            <div><div className="flex items-center gap-1 text-faint"><Snowflake className="h-3 w-3" />glacier</div><div className="font-medium">{lk.ice_contact ? "contact" : lk.glacier_fed ? "near" : "none"}</div></div>
          </div>
          <div className="mt-2 flex items-start gap-1.5 text-xs text-muted">{lk.class === "high" && <TriangleAlert className="mt-0.5 h-3 w-3 shrink-0 text-alarm" />}{lk.why}</div>
        </motion.button>
      ))}
      <div className="px-1 text-[10px] leading-relaxed text-faint">Screening score, not a probability: growth 40 + glacier contact 20 + size 20 + valley slope 20, only for glacier-fed lakes. {r.method.split(";")[0]}.</div>
    </div>
  );
}
