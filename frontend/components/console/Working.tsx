"use client";
// What the agent is doing while a request runs, and what it actually did once it returns. The live view lists the
// pipeline the server is running with a real elapsed clock; the trace lists the steps the server reported, with
// their measured times. Nothing here invents progress.
import { CheckCircle2, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

export function Working({ title, steps }: { title: string; steps: string[] }) {
  const [t0] = useState(() => Date.now());
  const [now, setNow] = useState(t0);
  useEffect(() => { const id = setInterval(() => setNow(Date.now()), 100); return () => clearInterval(id); }, []);
  return (
    <div data-working="1" className="mt-3 rounded-xl border border-glacier/30 bg-glacier/5 p-3">
      <div className="flex items-center justify-between font-mono text-[10px] tracking-[.14em] text-glacier">
        <span className="flex items-center gap-1.5"><Loader2 className="h-3.5 w-3.5 animate-spin" />{title}</span>
        <span className="text-muted">{((now - t0) / 1000).toFixed(1)} s</span>
      </div>
      <ol className="mt-2 space-y-1">
        {steps.map((s, i) => (
          <li key={i} className="flex items-center gap-2 text-[11px] text-muted">
            <span className="grid h-4 w-4 shrink-0 place-items-center rounded-full border border-glacier/40 font-mono text-[9px] text-glacier">{i + 1}</span>{s}
          </li>
        ))}
      </ol>
    </div>
  );
}

export function Trace({ title, steps }: { title: string; steps: { name: string; detail: string; ms: number }[] }) {
  if (!steps?.length) return null;
  const total = steps.reduce((a, s) => a + s.ms, 0);
  return (
    <div data-trace="1" className="rounded-lg border border-glacier/30 bg-glacier/[.04] p-2.5">
      <div className="flex items-center justify-between font-mono text-[10px] tracking-[.14em] text-glacier"><span>{title}</span><span className="text-faint">{(total / 1000).toFixed(1)} s</span></div>
      <ol className="mt-1.5 space-y-1">
        {steps.map((s, i) => (
          <li key={i} className="flex items-start gap-2 text-[11px]">
            <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-safe" />
            <span className="flex-1"><b className="font-medium text-fg">{s.name}</b><span className="text-muted"> · {s.detail}</span></span>
            {s.ms > 0 && <span className="font-mono text-[10px] text-faint">{s.ms >= 1000 ? `${(s.ms / 1000).toFixed(1)} s` : `${s.ms} ms`}</span>}
          </li>
        ))}
      </ol>
    </div>
  );
}
