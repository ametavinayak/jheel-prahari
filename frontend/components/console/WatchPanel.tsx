"use client";
import { AnimatePresence, motion } from "framer-motion";
import { Gauge, Radio, Radar, ShieldAlert, Siren, Timer, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import type { AlertEvent, Lake, ScanState } from "@/lib/api";
import { api } from "@/lib/api";

function Card({ title, icon: Icon, tone = "cyan", children, right }: { title: string; icon: React.ElementType; tone?: "cyan" | "alarm"; children: React.ReactNode; right?: React.ReactNode }) {
  return (
    <section className="glass rounded-2xl p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className={`flex items-center gap-2 font-mono text-[11px] tracking-[.18em] ${tone === "alarm" ? "text-alarm" : "text-glacier"}`}><Icon className="h-3.5 w-3.5" />{title}</h3>
        {right}
      </div>
      {children}
    </section>
  );
}

function fmt(ms: number) {
  if (ms <= 0) return "now";
  const m = Math.floor(ms / 60000), s = Math.floor((ms % 60000) / 1000);
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function WatchPanel({ lake, sceneIdx, setSceneIdx, alerts, setAlerts }: {
  lake: Lake; sceneIdx: number; setSceneIdx: (i: number) => void; alerts: AlertEvent[]; setAlerts: (a: AlertEvent[]) => void;
}) {
  const s = lake.series[sceneIdx], d = lake.drain_check, g = lake.growth;
  const max = Math.max(...lake.series.map((x) => x.area_km2)), min = Math.min(...lake.series.map((x) => x.area_km2));
  const [scan, setScan] = useState<ScanState | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [lang, setLang] = useState<"en" | "hi" | "ne">("en");
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t); }, []);

  async function runScan() {
    setErr(null);
    try {
      // A serverless API answers the POST with the finished scan; a long-running one says "running" and is polled.
      let st = await api.startScan();
      setScan(st);
      while (st.state === "running") {
        await new Promise((r) => setTimeout(r, 2500));
        st = await api.scan();
        setScan(st);
      }
      const ev = st.alert;
      if (ev) setAlerts([ev, ...alerts.filter((x) => x.id !== ev.id)]);
    } catch (e) { setErr((e as Error).message); setScan(null); }
  }

  async function fire(src: string) {
    setBusy(src); setErr(null);
    try { const ev = await api.trigger(src); setAlerts([ev, ...alerts.filter((x) => x.id !== ev.id)]); } catch (e) { setErr((e as Error).message); } finally { setBusy(null); }
  }

  const ev = alerts[0];
  const t0 = ev ? Date.parse(ev.at_utc) : 0;
  const pts = lake.series.map((x, i) => `${(i / (lake.series.length - 1)) * 100},${100 - ((x.area_km2 - min) / (max - min)) * 80 - 10}`).join(" ");

  return (
    <div className="space-y-3">
      <Card title="LAKE AI · AREA FROM SENTINEL-2" icon={Gauge}>
        <div className="flex items-end justify-between">
          <div>
            <div className="text-3xl font-semibold tabular-nums">{s.area_km2.toFixed(2)}<span className="ml-1 text-base text-muted">km²</span></div>
            <div className="font-mono text-[11px] text-muted">{s.date}{s.after_burst ? " · after the burst" : ""}</div>
          </div>
          <div className="text-right">
            <div className="text-xl font-semibold text-glacier">+{g.pct}%</div>
            <div className="font-mono text-[11px] text-muted">{g.from.slice(0, 4)}→{g.to.slice(0, 7)} · {g.trend_km2_per_year.toFixed(3)} km²/yr</div>
          </div>
        </div>
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="mt-3 h-20 w-full overflow-visible">
          <defs><linearGradient id="ar" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#4fe3f0" stopOpacity=".35" /><stop offset="1" stopColor="#4fe3f0" stopOpacity="0" /></linearGradient></defs>
          <polygon points={`0,100 ${pts} 100,100`} fill="url(#ar)" />
          <polyline points={pts} fill="none" stroke="#4fe3f0" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
          {lake.series.map((x, i) => (
            <circle key={x.date} cx={(i / (lake.series.length - 1)) * 100} cy={100 - ((x.area_km2 - min) / (max - min)) * 80 - 10}
              r={i === sceneIdx ? 3.2 : 1.8} fill={x.after_burst ? "#ff7a3d" : i === sceneIdx ? "#fff" : "#4fe3f0"} vectorEffect="non-scaling-stroke" />
          ))}
        </svg>
        <input type="range" min={0} max={lake.series.length - 1} value={sceneIdx} onChange={(e) => setSceneIdx(+e.target.value)}
          className="mt-2 w-full accent-[#4fe3f0]" aria-label="Scene" />
        <div className="flex justify-between font-mono text-[10px] text-faint">{lake.series.map((x) => <span key={x.date}>{x.date.slice(2, 4)}</span>)}</div>
      </Card>

      <Card title="RADAR DRAIN CHECK · SENTINEL-1" icon={Radar}>
        <div className="flex items-center gap-3">
          <span className={`rounded-md px-2 py-0.5 font-mono text-[11px] font-bold ${d.drained ? "bg-alarm text-ink" : "bg-safe/20 text-safe"}`}>{d.drained ? "DRAINED" : "STABLE"}</span>
          <span className="text-sm text-muted">2023 replay · {d.before.date} → {d.after.date}</span>
        </div>
        <div className="mt-2 text-sm">Open water <b>{(d.before.water_m2 / 1e6).toFixed(2)}</b> → <b className="text-alarm">{(d.after.water_m2 / 1e6).toFixed(2)} km²</b> · {Math.round(d.area_loss * 100)}% lost</div>
        <button onClick={runScan} disabled={scan?.state === "running"}
          className="relative mt-3 flex w-full items-center justify-center gap-2 overflow-hidden rounded-xl border border-glacier/40 bg-glacier/10 px-3 py-2 text-sm font-medium text-glacier transition hover:bg-glacier/20 disabled:cursor-wait">
          {scan?.state === "running" ? <><Loader2 className="h-4 w-4 animate-spin" /> Scanning latest passes… {scan.started ? Math.round(now / 1000 - scan.started) : 0}s<span className="shimmer absolute inset-0" /></> : <><Radio className="h-4 w-4" /> Run live scan on the latest passes</>}
        </button>
        <AnimatePresence>
          {scan?.state === "done" && scan.result && (
            <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} className="mt-2 text-sm">
              <span className={`font-mono text-[11px] font-bold ${scan.result.drained ? "text-alarm" : "text-safe"}`}>{scan.result.drained ? "DRAINED" : "STABLE"}</span>
              <span className="text-muted"> · {scan.result.before.date} → {scan.result.after.date}: {(scan.result.before.water_m2 / 1e6).toFixed(2)} → {(scan.result.after.water_m2 / 1e6).toFixed(2)} km² ({(scan.result.area_loss * 100).toFixed(1)}%)</span>
            </motion.div>
          )}
          {scan?.state === "error" && <div className="mt-2 text-sm text-alarm">Scan failed: {scan.error}</div>}
        </AnimatePresence>
      </Card>

      <Card title="TRIGGER" icon={ShieldAlert} tone="alarm">
        <div className="grid grid-cols-3 gap-2">
          {[["gauge", "River gauge"], ["station", "Lake station"], ["manual", "Control room"]].map(([k, l]) => (
            <button key={k} onClick={() => fire(k)} disabled={!!busy}
              className="rounded-xl bg-alarm px-2 py-2 text-xs font-semibold text-ink transition hover:brightness-110 disabled:opacity-60">
              {busy === k ? "Sending…" : l}
            </button>
          ))}
        </div>
        {err && <div className="mt-2 text-sm text-alarm">{err}</div>}
      </Card>

      <Card title="ALERTS" icon={Siren} tone="alarm" right={ev && <span className="flex items-center gap-2">{([["en", "EN"], ["hi", "हिन्दी"], ["ne", "नेपाली"]] as const).map(([k, l]) => (
          <button key={k} onClick={() => setLang(k)} className={`rounded-md px-1.5 py-0.5 text-[11px] transition ${lang === k ? "bg-alarm text-ink font-semibold" : "text-muted hover:text-fg"}`}>{l}</button>))}
          <span className="font-mono text-[10px] text-muted">{ev.source_label} · {new Date(t0).toLocaleTimeString()}</span></span>}>
        {!ev ? <div className="text-sm text-faint">No alerts. A drained lake or any trigger sends one message per place on the flood path.</div> : (
          <div className="space-y-2">
            {ev.messages.map((m) => {
              const lo = t0 + m.eta_min * 60000 - now, hi = t0 + m.eta_max * 60000 - now;
              return (
                <motion.div key={m.place} initial={{ opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }} className="rounded-xl border border-alarm/25 bg-alarm/[.06] p-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium">{m.name}</span>
                    <span className="flex items-center gap-1 font-mono text-sm font-semibold tabular-nums text-alarm"><Timer className="h-3.5 w-3.5" />{fmt(lo)} – {fmt(hi)}</span>
                  </div>
                  <div className="mt-1 text-xs leading-relaxed text-muted"><span className="font-mono text-[10px] uppercase text-faint">{m.channel} {m.status} · </span>{m.texts?.[lang] ?? m.text}</div>
                </motion.div>
              );
            })}
          </div>
        )}
      </Card>

      <Card title="FLOOD PATH · ARRIVAL AFTER AN OUTBURST" icon={Timer}>
        <div className="space-y-2.5">
          {lake.eta.map((e) => (
            <div key={e.id}>
              <div className="flex justify-between text-sm"><span>{e.name}</span><span className="font-mono text-muted">{e.river_km} km · {e.eta_min}–{e.eta_max} min</span></div>
              <div className="mt-1 h-1 overflow-hidden rounded-full bg-white/5"><div className="h-full rounded-full bg-gradient-to-r from-alarm to-watch" style={{ width: `${(e.eta_max / lake.eta[lake.eta.length - 1].eta_max) * 100}%` }} /></div>
            </div>
          ))}
        </div>
        <div className="mt-3 text-[11px] text-faint">{lake.flowpath.length_km} km D8 path on Copernicus DEM. Calibrated on 2023: Chungthang hit {lake.calibration.minutes_min}–{lake.calibration.minutes_max} min after the landslide ({lake.speed_kmh.kmh_slow}–{lake.speed_kmh.kmh_fast} km/h).</div>
      </Card>
    </div>
  );
}
