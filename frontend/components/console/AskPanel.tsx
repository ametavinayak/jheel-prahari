"use client";
// Chat with Lake AI. Each answer shows the steps the server actually ran, as tool-call cards.
import { AnimatePresence, motion } from "framer-motion";
import { ArrowUp, ChevronRight, Cpu, Sparkles, Zap } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { Answer, Capabilities } from "@/lib/api";
import { api } from "@/lib/api";
import { Working } from "./Working";

type Msg = { role: "user"; text: string } | { role: "ai"; data: Answer } | { role: "error"; text: string };
const SUGGEST = ["Has the lake grown?", "Did it drain in 2023?", "When does water reach Chungthang?", "Which places are on the flood path?"];

function Orb({ busy }: { busy?: boolean }) {
  return (
    <div className="relative h-7 w-7 shrink-0">
      <div className={`absolute inset-0 rounded-full bg-[conic-gradient(from_0deg,#4fe3f0,#7a8cff,#ff7a3d,#4fe3f0)] ${busy ? "sweep" : ""}`} />
      <div className="absolute inset-[3px] rounded-full bg-ink" />
      <Sparkles className="absolute inset-0 m-auto h-3.5 w-3.5 text-glacier" />
    </div>
  );
}

function Steps({ data }: { data: Answer }) {
  const [open, setOpen] = useState(true);
  if (!data.steps?.length) return null;
  const total = data.steps.reduce((a, s) => a + s.ms, 0);
  return (
    <div className="mt-2">
      <button onClick={() => setOpen(!open)} className="flex items-center gap-1 font-mono text-[10px] text-faint hover:text-muted">
        <ChevronRight className={`h-3 w-3 transition ${open ? "rotate-90" : ""}`} /> {data.steps.length} steps · {total.toFixed(1)} ms · intent: {data.intent}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
            <div className="mt-2 space-y-1.5 border-l border-line pl-3">
              {data.steps.map((s, i) => (
                <div key={i} className="rounded-lg border border-line bg-white/[.02] px-2.5 py-1.5">
                  <div className="flex items-center justify-between font-mono text-[10px]"><span className="flex items-center gap-1 text-glacier"><Cpu className="h-3 w-3" />{s.tool}</span><span className="text-faint">{s.ms} ms</span></div>
                  <div className="mt-0.5 text-[11px] text-muted">{s.detail}{s.source && <span className="text-faint"> · {s.source}</span>}</div>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export function AskPanel() {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  const [caps, setCaps] = useState<Capabilities | null>(null);
  const [lang, setLang] = useState<"en" | "hi" | "ne">("en");
  const [simple, setSimple] = useState(false);
  useEffect(() => { api.capabilities().then(setCaps).catch(() => setCaps(null)); }, []);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, busy]);

  async function send(text: string) {
    const t = text.trim();
    if (!t || busy) return;
    setQ(""); setMsgs((m) => [...m, { role: "user", text: t }]); setBusy(true);
    try { const data = await api.ask(t, lang, simple); setMsgs((m) => [...m, { role: "ai", data }]); }
    catch (e) { setMsgs((m) => [...m, { role: "error", text: (e as Error).message }]); }
    finally { setBusy(false); }
  }

  return (
    <div className="glass flex h-full min-h-[520px] flex-col rounded-2xl">
      <div className="flex items-center gap-2 border-b border-line px-4 py-3"><Orb busy={busy} /><div><div className="text-sm font-medium">Lake AI</div><div className="font-mono text-[10px] text-faint">answers from measured satellite data · South Lhonak</div></div></div>
      <div className="thin-scroll flex-1 space-y-4 overflow-y-auto p-4">
        {msgs.length === 0 && (
          <div className="pt-6 text-center">
            <div className="text-gradient text-xl font-semibold">Ask the lake.</div>
            <p className="mt-1 text-sm text-muted">Every answer names the satellite data it came from.</p>
            <div className="mt-5 flex flex-wrap justify-center gap-2">
              {SUGGEST.map((s) => <button key={s} onClick={() => send(s)} className="rounded-full border border-line bg-white/[.03] px-3 py-1.5 text-xs text-muted transition hover:border-glacier/50 hover:text-fg">{s}</button>)}
            </div>
          </div>
        )}
        {msgs.map((m, i) => m.role === "user" ? (
          <motion.div key={i} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="ml-auto max-w-[85%] rounded-2xl rounded-br-md bg-glacier/15 px-3.5 py-2 text-sm">{m.text}</motion.div>
        ) : m.role === "ai" ? (
          <motion.div key={i} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="flex gap-2.5">
            <Orb />
            <div className="min-w-0 flex-1">
              <div className="text-sm leading-relaxed">{m.data.answer}</div>
              {m.data.engine === "gpu" && <div className="mt-1.5 flex items-center gap-1.5 font-mono text-[10px] text-glacier"><Zap className="h-3 w-3" />explained on GPU · {m.data.model} · facts only</div>}
              {m.data.measured && m.data.intent !== "help" && <div className="mt-1.5 rounded-lg border border-line bg-white/[.02] px-2.5 py-1.5 text-[11px] text-muted"><span className="font-mono text-[10px] text-faint">MEASURED · </span>{m.data.measured}</div>}
              {m.data.evidence.length > 0 && <div className="mt-2 flex flex-wrap gap-1">{m.data.evidence.map((e) => <span key={e} className="rounded-md border border-line px-1.5 py-0.5 font-mono text-[10px] text-muted">{e}</span>)}</div>}
              <Steps data={m.data} />
            </div>
          </motion.div>
        ) : (
          <div key={i} className="text-sm text-alarm">{m.text}</div>
        ))}
        {busy && <div className="flex items-start gap-2.5"><Orb busy /><div className="flex-1"><Working title="LAKE AI IS WORKING" steps={["Understand the question", "Measure the facts from satellite data", "Word the answer from those facts only (Qwen3 on our GPU)", "Check every sentence against the facts"]} /></div></div>}
        <div ref={end} />
      </div>
      <form onSubmit={(e) => { e.preventDefault(); send(q); }} className="border-t border-line p-3">
        {caps?.gpu_explainer && (
          <div className="mb-2 flex items-center gap-1.5 text-[11px]">
            <Zap className="h-3 w-3 text-glacier" />
            {([["en", "EN"], ["hi", "हिन्दी"], ["ne", "नेपाली"]] as const).map(([k, l]) => (
              <button type="button" key={k} onClick={() => setLang(k)} className={`rounded-md px-1.5 py-0.5 transition ${lang === k ? "bg-glacier text-ink font-semibold" : "text-muted hover:text-fg"}`}>{l}</button>))}
            <button type="button" onClick={() => setSimple(!simple)} className={`ml-auto rounded-md border px-2 py-0.5 transition ${simple ? "border-glacier/60 bg-glacier/10 text-glacier" : "border-line text-muted hover:text-fg"}`}>Explain simply</button>
          </div>
        )}
        <div className="flex items-center gap-2 rounded-xl border border-line bg-ink/60 px-3 py-2 focus-within:border-glacier/50">
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask about area, growth, drainage, arrival times…" className="flex-1 bg-transparent text-sm outline-none placeholder:text-faint" />
          <button disabled={!q.trim() || busy} className="grid h-7 w-7 place-items-center rounded-lg bg-glacier text-ink transition disabled:opacity-30" aria-label="Send"><ArrowUp className="h-4 w-4" /></button>
        </div>
      </form>
    </div>
  );
}
