"use client";
// Jheel Smriti: the control room's memory, kept in Hindsight. The centrepiece is the same trigger answered twice,
// once by a system with no history and once by the agent that remembers what happened the last times.
import { motion } from "framer-motion";
import { Brain, BookOpenText, Loader2, NotebookPen, ShieldCheck, Siren } from "lucide-react";
import { useEffect, useState } from "react";
import type { Briefing, MemoryStatus, Triage } from "@/lib/api";

type Recorded = { captured: string; model: string; triage: Record<string, Triage>; briefing: Briefing };
import { api } from "@/lib/api";

const SOURCES = [["gauge", "River gauge"], ["station", "Lake station"], ["manual", "Control room"]] as const;
const TONE: Record<string, string> = {
  SEND_ALL_NOW: "bg-alarm text-ink", STANDBY_AND_VERIFY: "bg-watch text-ink", HOLD_AND_VERIFY: "bg-safe text-ink",
};

function Verdict({ t, title }: { t: Pick<Triage, "decision" | "label" | "why">; title: string }) {
  return (
    <div className="rounded-xl border border-line bg-white/[.03] p-3">
      <div className="font-mono text-[10px] tracking-[.16em] text-faint">{title}</div>
      <span className={`mt-1.5 inline-block rounded-md px-2 py-0.5 font-mono text-[11px] font-bold ${TONE[t.decision] ?? "bg-glacier text-ink"}`}>{t.label}</span>
      <p className="mt-2 text-xs leading-relaxed text-muted">{t.why}</p>
    </div>
  );
}

export function MemoryPanel() {
  const [st, setSt] = useState<MemoryStatus | null>(null);
  const [source, setSource] = useState<string>("gauge");
  const [radar, setRadar] = useState<"calm" | "drained">("calm");
  const [busy, setBusy] = useState<string | null>(null);
  const [res, setRes] = useState<Triage | null>(null);
  const [off, setOff] = useState<Triage | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [saved, setSaved] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<string>("");
  const [trig, setTrig] = useState<string>("gauge");
  const [brief, setBrief] = useState<Briefing | null>(null);

  const [rec, setRec] = useState<Recorded | null>(null);
  const [checking, setChecking] = useState(true);

  // No Hindsight server behind this deployment: replay a run captured from the live agent, and say so on screen.
  useEffect(() => {
    let dead = false;
    const loadRecorded = (): Promise<unknown> => fetch("/recorded-memory.json").then((r) => (r.ok ? r.json() : null)).then((j) => !dead && setRec(j)).catch(() => !dead && setRec(null));
    (async () => {
      // the first Hindsight call can take a few seconds: try a few times before declaring it offline
      for (let i = 0; i < 3 && !dead; i++) {
        try { const s = await api.memoryStatus(); if (s.ok) { setSt(s); setChecking(false); return; } setSt(s); } catch { setSt(null); }
        await new Promise((r) => setTimeout(r, 1500));
      }
      if (!dead) { await loadRecorded(); setChecking(false); }
    })();
    return () => { dead = true; };
  }, []);

  async function run() {
    setBusy("triage"); setErr(null); setRes(null); setOff(null);
    try {
      if (!st?.ok && rec) {
        await new Promise((r) => setTimeout(r, 900));
        setOff(rec.triage[`${source}|${radar}|0`]); setRes(rec.triage[`${source}|${radar}|1`]);
      } else {
        const [a, b] = await Promise.all([api.triage(source, radar, false), api.triage(source, radar, true)]);
        setOff(a); setRes(b);
      }
    } catch (e) { setErr((e as Error).message); } finally { setBusy(null); }
  }
  async function save() {
    if (!note.trim()) return;
    setBusy("log"); setErr(null); setSaved(null);
    try { await api.memoryLog(note.trim(), outcome || undefined, outcome ? trig : undefined); setSaved("Stored in memory. The next triage can recall it."); setNote(""); }
    catch (e) { setErr((e as Error).message); } finally { setBusy(null); }
  }
  async function briefing() {
    setBusy("brief"); setErr(null); setBrief(null);
    try { setBrief(!st?.ok && rec ? rec.briefing : await api.briefing()); } catch (e) { setErr((e as Error).message); } finally { setBusy(null); }
  }

  const live = !!st?.ok;
  const online = live || !!rec;
  return (
    <div className="space-y-3">
      <section className="glass rounded-2xl p-4">
        <div className="flex items-center justify-between">
          <h3 className="flex items-center gap-2 font-mono text-[11px] tracking-[.18em] text-glacier"><Brain className="h-3.5 w-3.5" />JHEEL SMRITI · CONTROL-ROOM MEMORY</h3>
          <span className={`rounded-full px-2 py-0.5 font-mono text-[10px] font-semibold ${checking ? "bg-white/10 text-muted" : live ? "bg-safe/20 text-safe" : rec ? "bg-watch/20 text-watch" : "bg-alarm/20 text-alarm"}`}>{checking ? "CHECKING…" : live ? "HINDSIGHT ONLINE" : rec ? "RECORDED RUN" : "MEMORY OFFLINE"}</span>
        </div>
        <p className="mt-2 text-xs leading-relaxed text-muted">An agent that remembers every alert, drill and field check, so it can tell a real trigger from the gauge that cries wolf every time it rains. Memory lives in <b className="text-fg">Hindsight</b>, bank <span className="font-mono">{st?.bank ?? "…"}</span>.</p>
        {!checking && !live && rec && <p className="mt-2 text-xs text-watch">This deployment has no Hindsight server behind it. What you see is a run captured from the live agent on {rec.captured} ({rec.model}). Run the console locally with the memory server to teach it new events.</p>}
        {!checking && !online && <p className="mt-2 text-xs text-alarm">No Hindsight server reachable{st?.error ? ` (${st.error})` : ""}. The rest of the console works without it.</p>}
      </section>

      <section className="glass rounded-2xl p-4">
        <h3 className="flex items-center gap-2 font-mono text-[11px] tracking-[.18em] text-alarm"><Siren className="h-3.5 w-3.5" />A TRIGGER ARRIVES · SAME INPUT, TWO AGENTS</h3>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {SOURCES.map(([k, l]) => <button key={k} onClick={() => setSource(k)} className={`rounded-lg border px-2.5 py-1.5 text-xs transition ${source === k ? "border-alarm/60 bg-alarm/10 text-alarm" : "border-line text-muted hover:text-fg"}`}>{l}</button>)}
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs">
          <span className="text-faint">Radar pass after the trigger:</span>
          <button onClick={() => setRadar("calm")} className={`rounded-lg border px-2.5 py-1.5 transition ${radar === "calm" ? "border-safe/60 bg-safe/10 text-safe" : "border-line text-muted hover:text-fg"}`}>Calm: −2%</button>
          <button onClick={() => setRadar("drained")} className={`rounded-lg border px-2.5 py-1.5 transition ${radar === "drained" ? "border-alarm/60 bg-alarm/10 text-alarm" : "border-line text-muted hover:text-fg"}`}>Drained: 52% (2023)</button>
        </div>
        <button onClick={run} disabled={!online || busy === "triage"} className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl bg-alarm px-3 py-2 text-sm font-semibold text-ink transition hover:brightness-110 disabled:opacity-40">
          {busy === "triage" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Siren className="h-4 w-4" />}{busy === "triage" ? "Recalling from memory…" : "Fire the trigger"}
        </button>
        {res && off && (
          <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="mt-3 space-y-2">
            <div className="text-xs text-muted">{res.radar}</div>
            <div className="grid gap-2">
              <Verdict t={off} title="WITHOUT MEMORY" />
              <Verdict t={res} title="WITH HINDSIGHT MEMORY" />
            </div>
            {res.decision === "SEND_ALL_NOW" && radar === "drained" && (
              <div className="flex items-start gap-2 rounded-lg border border-safe/30 bg-safe/5 p-2.5 text-[11px] text-muted"><ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-safe" />Safety rule: memory can make the agent more careful about an unconfirmed trigger, but it can never hold back a radar-confirmed drain.</div>
            )}
            {res.lessons?.length > 0 && (
              <div className="rounded-lg border border-line p-2.5"><div className="font-mono text-[10px] tracking-[.14em] text-faint">LESSONS IT APPLIED</div><ul className="mt-1 list-disc space-y-0.5 pl-4 text-[11px] text-muted">{res.lessons.map((l, i) => <li key={i}>{l.text}<div className="font-mono text-[10px] text-faint">from memory{l.when ? ` · ${l.when.slice(0, 10)}` : ""}: {l.from}</div></li>)}</ul></div>
            )}
            <details className="rounded-lg border border-line p-2.5" open>
              <summary className="cursor-pointer font-mono text-[10px] tracking-[.14em] text-glacier">RECALLED FROM HINDSIGHT · {res.recalled.length} MEMORIES · {res.false_alarms} FALSE ALARMS COUNTED</summary>
              <div className="mt-2 space-y-1.5">
                {res.recalled.map((m, i) => (
                  <div key={i} className={`rounded-md border px-2 py-1.5 text-[11px] leading-snug ${res.false_alarm_ids.includes(i) ? "border-watch/40 bg-watch/5" : "border-line bg-white/[.02]"}`}>
                    <span className="font-mono text-[10px] text-faint">{m.type ?? "memory"}{m.when ? ` · ${m.when.slice(0, 10)}` : ""} · </span>{m.text}
                  </div>
                ))}
              </div>
            </details>
            {res.note && <div className="text-[11px] text-faint">{res.note}</div>}
          </motion.div>
        )}
      </section>

      <section className="glass rounded-2xl p-4">
        <h3 className="flex items-center gap-2 font-mono text-[11px] tracking-[.18em] text-glacier"><NotebookPen className="h-3.5 w-3.5" />TEACH IT · LOG WHAT REALLY HAPPENED</h3>
        <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={3} maxLength={1500} placeholder="e.g. River gauge fired at 02:10, radar showed no change. False alarm: rain surge at the gauge again."
          className="mt-2 w-full rounded-xl border border-line bg-ink/60 px-3 py-2 text-xs outline-none placeholder:text-faint focus:border-glacier/50" />
        <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[11px]">
          <span className="text-faint">Outcome:</span>
          {([["", "Just a note"], ["false-alarm", "False alarm"], ["confirmed", "Confirmed"]] as const).map(([k, l]) => (
            <button key={k} onClick={() => setOutcome(k)} className={`rounded-md border px-2 py-0.5 transition ${outcome === k ? "border-glacier/60 bg-glacier/10 text-glacier" : "border-line text-muted hover:text-fg"}`}>{l}</button>))}
          {outcome && <><span className="ml-1 text-faint">from</span>{SOURCES.map(([k, l]) => (
            <button key={k} onClick={() => setTrig(k)} className={`rounded-md border px-2 py-0.5 transition ${trig === k ? "border-watch/60 bg-watch/10 text-watch" : "border-line text-muted hover:text-fg"}`}>{l}</button>))}</>}
        </div>
        <div className="mt-2 flex items-center gap-2">
          <button onClick={save} disabled={!live || !note.trim() || busy === "log"} className="flex items-center gap-1.5 rounded-lg bg-glacier px-3 py-1.5 text-xs font-medium text-ink disabled:opacity-40">{busy === "log" && <Loader2 className="h-3 w-3 animate-spin" />}Remember this</button>
          {saved && <span className="text-[11px] text-safe">{saved}</span>}
        </div>
      </section>

      <section className="glass rounded-2xl p-4">
        <h3 className="flex items-center gap-2 font-mono text-[11px] tracking-[.18em] text-glacier"><BookOpenText className="h-3.5 w-3.5" />SHIFT HANDOVER</h3>
        <button onClick={briefing} disabled={!online || busy === "brief"} className="mt-2 flex items-center gap-1.5 rounded-lg border border-glacier/40 bg-glacier/10 px-3 py-1.5 text-xs font-medium text-glacier disabled:opacity-40">{busy === "brief" && <Loader2 className="h-3 w-3 animate-spin" />}Brief the incoming officer</button>
        {brief && (
          <div className="mt-2 space-y-2">
            {brief.note && <p className="text-xs text-muted">{brief.note}</p>}
            {brief.bullets.map((b) => (
              <div key={b.heading} className="rounded-lg border border-line bg-white/[.02] p-2.5">
                <div className="font-mono text-[10px] tracking-[.14em] text-glacier">{b.heading.toUpperCase()}</div>
                <p className="mt-1 text-xs leading-relaxed text-muted">{b.text}</p>
              </div>
            ))}
            {brief.bullets.length > 0 && <div className="font-mono text-[10px] text-faint">built from {brief.memories} recalled memories · every number checked against them</div>}
          </div>
        )}
      </section>
      {err && <div className="rounded-lg border border-alarm/30 bg-alarm/5 p-2.5 text-xs text-alarm">{err}</div>}
    </div>
  );
}
