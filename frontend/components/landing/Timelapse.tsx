"use client";
// Real Sentinel-2 frames of South Lhonak, 2016 → after the 2023 burst, with the measured outline traced on top.
import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";
import type { Scene } from "@/lib/api";
import { sceneUrl } from "@/lib/api";

function rings(g: Scene["outline"]): number[][][] {
  return g.type === "Polygon" ? [g.coordinates[0]] : g.coordinates.map((p) => p[0]);
}

// image_bounds are [[south, west], [north, east]]; the frame is north-up, so lon/lat map linearly at this scale.
function toPath(scene: Scene, crop: { x0: number; y0: number; w: number; h: number }) {
  const [[s, w], [n, e]] = scene.image_bounds;
  return rings(scene.outline)
    .map((ring) => ring.map(([lon, lat], i) => {
      const x = ((lon - w) / (e - w) * 100 - crop.x0) / crop.w * 100;
      const y = ((n - lat) / (n - s) * 100 - crop.y0) / crop.h * 100;
      return `${i ? "L" : "M"}${x.toFixed(2)},${y.toFixed(2)}`;
    }).join(" ") + "Z").join(" ");
}

// The lake sits in the middle of a 13 x 11 km frame; zoom so it fills the panel.
const CROP = { x0: 14, y0: 27, w: 48, h: 36 };

export function Timelapse({ scenes }: { scenes: Scene[] }) {
  const [i, setI] = useState(0);
  const [paused, setPaused] = useState(false);
  useEffect(() => {
    if (paused) return;
    const t = setInterval(() => setI((k) => (k + 1) % scenes.length), 1700);
    return () => clearInterval(t);
  }, [paused, scenes.length]);
  const s = scenes[i];
  const path = useMemo(() => toPath(s, CROP), [s]);
  const max = Math.max(...scenes.map((x) => x.area_km2)), min = Math.min(...scenes.map((x) => x.area_km2));

  return (
    <div className="relative" onMouseEnter={() => setPaused(true)} onMouseLeave={() => setPaused(false)}>
      <div className="absolute -inset-10 rounded-[40px] bg-glacier/20 aurora" aria-hidden />
      <div className="glass relative overflow-hidden rounded-3xl">
        <div className="flex items-center justify-between border-b border-line px-4 py-2.5 font-mono text-[11px] text-muted">
          <span className="flex items-center gap-2">
            <span className="relative flex h-2 w-2"><span className="pulse-ring absolute inline-flex h-full w-full rounded-full bg-glacier" /><span className="relative inline-flex h-2 w-2 rounded-full bg-glacier" /></span>
            SENTINEL-2 · SOUTH LHONAK · 27.91°N 88.19°E
          </span>
          <span>{s.scene.slice(0, 3)} · L2A · 10 m</span>
        </div>

        <div className="relative aspect-[14/10] overflow-hidden bg-black">
          <AnimatePresence initial={false}>
            <motion.div key={s.date} className="absolute inset-0"
              initial={{ opacity: 0, scale: 1.04 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }}
              transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={sceneUrl(s)} alt={`South Lhonak lake, ${s.date}`} className="absolute max-w-none"
                style={{ width: `${10000 / CROP.w}%`, height: `${10000 / CROP.h}%`, left: `${-CROP.x0 * 100 / CROP.w}%`, top: `${-CROP.y0 * 100 / CROP.h}%` }} />
            </motion.div>
          </AnimatePresence>
          <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 h-full w-full">
            <motion.path key={s.date} d={path} fill={s.after_burst ? "rgb(255 122 61 / .18)" : "rgb(79 227 240 / .16)"}
              stroke={s.after_burst ? "#ff7a3d" : "#4fe3f0"} strokeWidth={2} vectorEffect="non-scaling-stroke" style={{ filter: "drop-shadow(0 0 6px currentColor)" }}
              initial={{ pathLength: 0, opacity: 0 }} animate={{ pathLength: 1, opacity: 1 }} transition={{ duration: 1.1, ease: "easeOut" }} />
          </svg>
          <div className="scanline opacity-60" />
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_55%,rgb(5_9_15/.75))]" />

          <div className="absolute left-4 top-4 rounded-xl border border-line bg-ink/70 px-3 py-2 backdrop-blur">
            <div className="font-mono text-[10px] tracking-widest text-muted">LAKE AREA</div>
            <div className="text-2xl font-semibold tabular-nums">{s.area_km2.toFixed(2)}<span className="ml-1 text-sm text-muted">km²</span></div>
          </div>
          <div className="absolute right-4 top-4 text-right">
            <div className="font-mono text-3xl font-semibold tabular-nums text-white drop-shadow">{s.date.slice(0, 4)}</div>
            <div className="font-mono text-[11px] text-muted">{s.date}</div>
          </div>
          {s.after_burst && (
            <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
              className="absolute bottom-4 left-4 rounded-full bg-alarm px-3 py-1 font-mono text-[11px] font-semibold text-ink glow-alarm">
              AFTER THE 3 OCT 2023 OUTBURST
            </motion.div>
          )}
        </div>

        <div className="flex items-end gap-1.5 px-4 pb-3 pt-3">
          {scenes.map((x, k) => (
            <button key={x.date} onClick={() => setI(k)} aria-label={x.date} className="group flex flex-1 flex-col items-center gap-1">
              <div className={`w-full rounded-sm transition-all ${k === i ? (x.after_burst ? "bg-alarm" : "bg-glacier") : "bg-white/15 group-hover:bg-white/30"}`}
                style={{ height: `${6 + ((x.area_km2 - min) / (max - min)) * 34}px` }} />
              <span className={`font-mono text-[9px] ${k === i ? "text-fg" : "text-faint"}`}>{x.date.slice(2, 4)}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
