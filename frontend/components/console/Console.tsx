"use client";
import dynamic from "next/dynamic";
import Image from "next/image";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { Brain, Crosshair, History, Landmark, Loader2, Search, Sparkles, Waves, ScanSearch } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { AlertEvent, AreaJob, Lake } from "@/lib/api";
import { api } from "@/lib/api";
import type { MapApi } from "./MapView";
import { WatchPanel } from "./WatchPanel";
import { ScanPanel } from "./ScanPanel";
import { AskPanel } from "./AskPanel";
import { MemoryPanel } from "./MemoryPanel";

const MapView = dynamic(() => import("./MapView"), { ssr: false, loading: () => <div className="absolute inset-0 grid place-items-center text-faint"><Loader2 className="h-6 w-6 animate-spin" /></div> });

type Tab = "watch" | "scan" | "ask" | "memory";
const REPLAY = "2023-10-01";

export function Console() {
  const [lake, setLake] = useState<Lake | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("watch");
  const [sceneIdx, setSceneIdx] = useState(0);
  const [alerts, setAlerts] = useState<AlertEvent[]>([]);
  const [job, setJob] = useState<AreaJob | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [replay, setReplay] = useState(false);
  const mapApi = useRef<MapApi | null>(null);
  const polling = useRef(0);

  useEffect(() => {
    (async () => {
      try {
        const l = await api.lake();
        setLake(l);
        setSceneIdx(Math.max(0, l.series.findIndex((s) => s.after_burst) - 1));
        setAlerts(await api.alerts());
      } catch (e) { setErr((e as Error).message); }
    })();
  }, []);

  async function analyse(req: { query?: string; bbox?: number[] }) {
    const run = ++polling.current;
    setTab("scan"); setSelected(null);
    try {
      let j = await api.analyze({ ...req, as_of: replay ? REPLAY : undefined });
      setJob(j);
      while (j.state === "running") {
        await new Promise((r) => setTimeout(r, 2000));
        if (run !== polling.current) return; // a newer search replaced this one
        j = await api.areaJob(j.id);
        setJob(j);
      }
    } catch (e) {
      if (run === polling.current) setJob({ id: "", state: "error", stage: "", result: null, error: (e as Error).message, started: 0 });
    }
  }

  async function loadWatchlist() {
    polling.current += 1; setTab("scan"); setSelected(null);
    try {
      const w = await api.watchlist();
      const xs = w.tiles.map((t) => t.box);
      const box: [number, number, number, number] = [Math.min(...xs.map((b) => b[0])), Math.min(...xs.map((b) => b[1])), Math.max(...xs.map((b) => b[2])), Math.max(...xs.map((b) => b[3]))];
      const dates = w.tiles.map((t) => t.recent).sort();
      const olds = w.tiles.map((t) => t.older).filter((x): x is string => !!x).sort();
      setJob({ id: "watchlist", state: "done", stage: "", error: null, started: 0, result: {
        box, as_of: w.built, place: { name: `${w.region}: ${w.tiles.length} tiles screened together`, lat: (box[1] + box[3]) / 2, lon: (box[0] + box[2]) / 2 },
        recent: { item: "", date: dates[dates.length - 1] ?? w.built, clear: 1 }, older: olds.length ? { item: "", date: olds[0], clear: 1 } : null,
        lakes: w.lakes, counts: { ...w.counts, stable: 0 }, method: "" } });
    } catch (e) {
      setJob({ id: "", state: "error", stage: "", result: null, error: (e as Error).message, started: 0 });
    }
  }

  function analyseView() {
    const c = mapApi.current?.center();
    if (!c) return;
    const h = 0.08;
    analyse({ bbox: [c[1] - h, c[0] - h, c[1] + h, c[0] + h] });
  }

  if (err) return <div className="grid min-h-screen place-items-center p-6"><div className="glass max-w-md rounded-2xl p-6 text-center"><div className="eyebrow !text-alarm">Lake service offline</div><p className="mt-3 text-sm text-muted">{err}</p></div></div>;
  if (!lake) return <div className="grid min-h-screen place-items-center"><Loader2 className="h-6 w-6 animate-spin text-glacier" /></div>;

  const running = job?.state === "running";
  const alarm = alerts.length > 0;

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      {/* top bar */}
      <header className="relative z-20 flex items-center gap-4 border-b border-line bg-ink/80 px-4 py-2.5 backdrop-blur-xl">
        <Link href="/" className="shrink-0"><Image src="/logo.png" alt="Anivortex" width={110} height={32} className="h-7 w-auto" /></Link>
        <div className="hidden h-6 w-px bg-line md:block" />
        <div className="hidden shrink-0 md:block"><div className="text-sm font-semibold leading-tight">Jheel Prahari</div><div className="font-mono text-[10px] text-faint">LAKE WATCH CONSOLE</div></div>

        <form onSubmit={(e) => { e.preventDefault(); if (query.trim()) analyse({ query: query.trim() }); }} className="mx-auto flex w-full max-w-xl items-center gap-2">
          <div className="flex flex-1 items-center gap-2 rounded-xl border border-line bg-panel/80 px-3 py-2 focus-within:border-glacier/50 focus-within:glow-cyan">
            <Search className="h-4 w-4 text-faint" />
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search a place — e.g. Gurudongmar Lake, Chorabari, Kedarnath…" className="flex-1 bg-transparent text-sm outline-none placeholder:text-faint" />
            {running && <Loader2 className="h-4 w-4 animate-spin text-glacier" />}
          </div>
          <button type="submit" disabled={!query.trim() || running} className="rounded-xl bg-glacier px-3 py-2 text-sm font-medium text-ink transition hover:brightness-110 disabled:opacity-40">Screen</button>
          <button type="button" onClick={analyseView} disabled={running} title="Screen the area at the map centre" className="hidden items-center gap-1.5 rounded-xl border border-line px-3 py-2 text-sm text-muted transition hover:text-fg disabled:opacity-40 sm:flex"><Crosshair className="h-4 w-4" />Analyse view</button>
          <button type="button" onClick={loadWatchlist} disabled={running} title="Ranked list of every lake screened across the North Sikkim glacier belt" className="hidden items-center gap-1.5 rounded-xl border border-watch/40 px-3 py-2 text-sm text-watch transition hover:bg-watch/10 disabled:opacity-40 lg:flex"><Landmark className="h-4 w-4" />Sikkim watchlist</button>
        </form>

        <button onClick={() => setReplay(!replay)} title="Screen as it would have looked on 1 Oct 2023, two days before South Lhonak burst"
          className={`hidden shrink-0 items-center gap-1.5 rounded-full border px-3 py-1 font-mono text-[11px] transition lg:flex ${replay ? "border-watch/60 bg-watch/10 text-watch" : "border-line text-muted hover:text-fg"}`}>
          <History className="h-3.5 w-3.5" />{replay ? "REPLAY 1 OCT 2023" : "AS OF TODAY"}
        </button>
        <span className={`shrink-0 rounded-full px-3 py-1 font-mono text-[11px] font-semibold ${alarm ? "bg-alarm text-ink glow-alarm" : "border border-glacier/50 text-glacier"}`}>{alarm ? "ALERT" : "WATCHING"}</span>
      </header>

      <div className="relative flex flex-1 overflow-hidden">
        {/* map */}
        <div className="relative flex-1">
          <MapView lake={lake} sceneIdx={sceneIdx} showWatched={tab !== "scan" || !job} area={job?.result ?? null}
            selected={selected} onSelect={(id) => { setSelected(id); setTab("scan"); }} onReady={(a) => (mapApi.current = a)} />
          <div className="pointer-events-none absolute left-4 top-4 z-[500] flex flex-col gap-2">
            <div className="glass-dark pointer-events-auto rounded-xl px-3 py-2">
              <div className="font-mono text-[10px] text-faint">WATCHED LAKE</div>
              <button onClick={() => { setTab("watch"); mapApi.current?.flyTo(lake.lake.seed[1], lake.lake.seed[0], 13); }} className="flex items-center gap-2 text-sm font-medium hover:text-glacier"><Waves className="h-3.5 w-3.5 text-glacier" />{lake.lake.name}, Sikkim</button>
            </div>
          </div>
          <div className="pointer-events-none absolute bottom-4 left-4 z-[500] glass-dark rounded-xl px-3 py-2 font-mono text-[10px] text-muted">
            <div className="flex gap-3">
              <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-alarm" />high</span>
              <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-watch" />watch</span>
              <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-glacier" />low</span>
              <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-safe" />stable</span>
              <span className="flex items-center gap-1"><span className="h-0.5 w-3 bg-alarm" />flood path</span>
            </div>
          </div>
        </div>

        {/* right rail */}
        <aside className="relative z-10 flex w-[420px] shrink-0 flex-col border-l border-line bg-ink/85 backdrop-blur-xl max-md:absolute max-md:inset-x-0 max-md:bottom-0 max-md:h-[55vh] max-md:w-auto max-md:border-l-0 max-md:border-t">
          <nav className="flex gap-1 border-b border-line p-2">
            {([["watch", "Lake", Waves], ["scan", "Scan", ScanSearch], ["ask", "Ask AI", Sparkles], ["memory", "Memory", Brain]] as const).map(([k, l, Icon]) => (
              <button key={k} onClick={() => setTab(k)} className={`relative flex flex-1 items-center justify-center gap-1.5 rounded-lg px-2 py-2 text-xs font-medium transition ${tab === k ? "text-fg" : "text-faint hover:text-muted"}`}>
                {tab === k && <motion.span layoutId="tab" className="absolute inset-0 rounded-lg border border-line-strong bg-white/[.05]" transition={{ type: "spring", duration: 0.4 }} />}
                <Icon className="relative h-3.5 w-3.5" /><span className="relative">{l}</span>
                {k === "scan" && running && <span className="relative h-1.5 w-1.5 rounded-full bg-glacier" />}
              </button>
            ))}
          </nav>
          <div className="thin-scroll flex-1 overflow-y-auto p-3">
            <AnimatePresence mode="wait">
              <motion.div key={tab} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }} className={tab === "ask" ? "h-full" : ""}>
                {tab === "watch" && <WatchPanel lake={lake} sceneIdx={sceneIdx} setSceneIdx={setSceneIdx} alerts={alerts} setAlerts={setAlerts} />}
                {tab === "scan" && <ScanPanel job={job} selected={selected} onSelect={setSelected} />}
                {tab === "ask" && <AskPanel />}
                {tab === "memory" && <MemoryPanel />}
              </motion.div>
            </AnimatePresence>
          </div>
        </aside>
      </div>
    </div>
  );
}
