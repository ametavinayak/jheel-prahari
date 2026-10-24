import Link from "next/link";
import Image from "next/image";
import { ArrowRight, Radar, Satellite, Mountain, Siren, ScanSearch, Waves, ShieldCheck, Snowflake } from "lucide-react";
import { lakeServer } from "@/lib/api";
import { Timelapse } from "@/components/landing/Timelapse";
import { CountUp, Reveal } from "@/components/landing/Reveal";

// The watched lake changes only when the pipeline is rerun: cache the page for an hour rather than ask the API per visit.
export const revalidate = 3600;

function Nav() {
  return (
    <header className="fixed inset-x-0 top-0 z-50">
      <div className="mx-auto mt-4 flex max-w-6xl items-center justify-between rounded-full border border-line bg-ink/60 px-4 py-2 backdrop-blur-xl">
        <Link href="/" className="flex items-center gap-2"><Image src="/logo.png" alt="Anivortex" width={120} height={35} className="h-7 w-auto" /></Link>
        <nav className="hidden items-center gap-7 text-sm text-muted md:flex">
          <a href="#problem" className="hover:text-fg">Problem</a>
          <a href="#how" className="hover:text-fg">How it works</a>
          <a href="#screen" className="hover:text-fg">Screening</a>
          <a href="#proof" className="hover:text-fg">Proof</a>
        </nav>
        <a href="/console" className="group flex items-center gap-2 rounded-full bg-fg px-4 py-1.5 text-sm font-medium text-ink transition hover:bg-white">
          Open console <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
        </a>
      </div>
    </header>
  );
}

export default async function Home() {
  const lake = await lakeServer();
  const g = lake.growth, d = lake.drain_check;
  const dam = lake.eta.find((e) => e.id === "chungthang") ?? lake.eta[0];

  return (
    <main className="relative overflow-x-hidden">
      <Nav />

      {/* HERO */}
      <section className="relative grain">
        <div className="bg-grid absolute inset-0" aria-hidden />
        <div className="absolute left-1/2 top-[-20%] h-[600px] w-[900px] -translate-x-1/2 rounded-full bg-glacier/10 aurora" aria-hidden />
        <div className="relative mx-auto grid max-w-6xl items-center gap-14 px-6 pb-20 pt-36 lg:grid-cols-[1.05fr_1fr]">
          <div>
            <Reveal>
              <div className="inline-flex items-center gap-2 rounded-full border border-line bg-white/[.03] px-3 py-1 font-mono text-[11px] text-muted">
                <span className="h-1.5 w-1.5 rounded-full bg-safe" /> Live on Sentinel-1 · Sentinel-2 · Copernicus DEM
              </div>
            </Reveal>
            <Reveal delay={0.08}>
              <h1 className="mt-6 text-[clamp(2.6rem,6vw,4.9rem)] font-semibold leading-[0.98] tracking-[-0.045em]">
                <span className="text-gradient">Every glacial lake, watched.</span><br />
                <span className="font-serif text-[1.08em] font-normal italic tracking-[-0.02em] text-white/55">Every village, warned.</span>
              </h1>
            </Reveal>
            <Reveal delay={0.16}>
              <p className="mt-6 max-w-lg text-lg leading-relaxed text-muted">
                Jheel Prahari reads every new satellite pass over India&apos;s high-risk glacial lakes, tells a dangerous lake from a quiet one,
                and when one bursts gives every place downstream its own countdown.
              </p>
            </Reveal>
            <Reveal delay={0.24}>
              <div className="mt-9 flex flex-wrap items-center gap-3">
                <a href="/console" className="group flex items-center gap-2 rounded-full bg-glacier px-6 py-3 font-medium text-ink glow-cyan transition hover:brightness-110">
                  Open the console <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
                </a>
                <a href="#proof" className="rounded-full border border-line-strong px-6 py-3 text-fg/90 transition hover:bg-white/5">See the 2023 replay</a>
              </div>
            </Reveal>
          </div>
          <Reveal delay={0.2}><Timelapse scenes={lake.series} /></Reveal>
        </div>

        {/* stat strip: every number is measured by the pipeline */}
        <div className="relative mx-auto max-w-6xl px-6 pb-24">
          <div className="grid grid-cols-2 gap-px overflow-hidden rounded-2xl border border-line bg-line md:grid-cols-4">
            {[
              { v: <CountUp to={g.pct} decimals={0} prefix="+" suffix="%" />, l: `lake growth, ${g.from.slice(0, 4)}–${g.to.slice(0, 4)}` },
              { v: <CountUp to={d.area_loss * 100} suffix="%" />, l: "of the water gone in 12 days — caught by radar" },
              { v: <CountUp to={lake.flowpath.length_km} suffix=" km" />, l: "flood path traced from the terrain" },
              { v: <span className="tabular-nums">{dam.eta_min}–{dam.eta_max}<span className="text-2xl text-muted"> min</span></span>, l: "warning time Chungthang never got" },
            ].map((s, k) => (
              <div key={k} className="bg-ink/90 p-6">
                <div className="text-4xl font-semibold tracking-tight">{s.v}</div>
                <div className="mt-2 text-sm text-muted">{s.l}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* PROBLEM */}
      <section id="problem" className="relative border-t border-line">
        <div className="mx-auto max-w-6xl px-6 py-28">
          <Reveal><div className="eyebrow">01 · The problem</div></Reveal>
          <Reveal delay={0.05}>
            <h2 className="mt-4 max-w-3xl text-[clamp(2rem,4vw,3.3rem)] font-semibold leading-[1.05] tracking-[-0.035em]">
              South Lhonak was on the high-risk list for years. <span className="text-white/45">On 3 October 2023 it burst at night, and nobody downstream was told.</span>
            </h2>
          </Reveal>
          <div className="mt-14 grid gap-5 md:grid-cols-3">
            {[
              { icon: Mountain, n: "189", t: "high-risk glacial lakes", b: "on NDMA's list for India, 40 in Sikkim alone. Glaciers retreat; new lakes form every year." },
              { icon: Satellite, n: "Free", t: "images, unread", b: "Sentinel satellites image every lake every few days. Reading them still takes an expert per lake." },
              { icon: Siren, n: "0", t: "minutes of warning", b: "The Teesta-III dam and 13 bridges were gone before any alert said how much time anyone had." },
            ].map(({ icon: Icon, n, t, b }, k) => (
              <Reveal key={t} delay={k * 0.08}>
                <div className="glass group h-full rounded-2xl p-7 transition hover:border-line-strong">
                  <Icon className="h-5 w-5 text-glacier" />
                  <div className="mt-6 text-5xl font-semibold tracking-tight">{n}</div>
                  <div className="mt-1 font-medium">{t}</div>
                  <p className="mt-3 text-sm leading-relaxed text-muted">{b}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* HOW IT WORKS */}
      <section id="how" className="relative border-t border-line">
        <div className="bg-grid absolute inset-0 opacity-60" aria-hidden />
        <div className="relative mx-auto max-w-6xl px-6 py-28">
          <Reveal><div className="eyebrow">02 · How it works</div></Reveal>
          <Reveal delay={0.05}><h2 className="mt-4 text-[clamp(2rem,4vw,3.3rem)] font-semibold tracking-[-0.035em]">From orbit to a siren, in four steps.</h2></Reveal>
          <div className="relative mt-16 grid gap-5 md:grid-cols-4">
            <div className="absolute left-0 right-0 top-[38px] hidden h-px bg-gradient-to-r from-glacier/0 via-glacier/50 to-alarm/60 md:block" aria-hidden />
            {[
              { icon: Satellite, k: "Watch", b: "Every new Sentinel-2 and Sentinel-1 scene over a lake is read as it is published. Lake AI outlines the water to the pixel." },
              { icon: ScanSearch, k: "Screen", b: "Each lake is matched across years. Only glacier-fed, growing lakes are flagged; quiet lakes stay quiet." },
              { icon: Radar, k: "Detect", b: "Radar sees through cloud and night. A lake that loses a quarter of its water between passes is an alarm." },
              { icon: Siren, k: "Warn", b: "The flood path is traced in advance. Every place on it gets its own time window and action, in seconds." },
            ].map(({ icon: Icon, k, b }, i) => (
              <Reveal key={k} delay={i * 0.1}>
                <div className="relative">
                  <div className={`relative z-10 grid h-[76px] w-[76px] place-items-center rounded-2xl border ${i === 3 ? "border-alarm/50 bg-alarm/10" : "border-glacier/40 bg-glacier/10"} backdrop-blur`}>
                    <Icon className={`h-7 w-7 ${i === 3 ? "text-alarm" : "text-glacier"}`} />
                  </div>
                  <div className="mt-6 font-mono text-xs text-faint">0{i + 1}</div>
                  <div className="mt-1 text-xl font-semibold">{k}</div>
                  <p className="mt-2 text-sm leading-relaxed text-muted">{b}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* SCREENING */}
      <section id="screen" className="relative border-t border-line">
        <div className="mx-auto max-w-6xl px-6 py-28">
          <Reveal><div className="eyebrow">03 · Screening</div></Reveal>
          <Reveal delay={0.05}>
            <h2 className="mt-4 max-w-3xl text-[clamp(2rem,4vw,3.3rem)] font-semibold leading-[1.05] tracking-[-0.035em]">
              It knows a dangerous lake <span className="font-serif font-normal italic text-white/60">from a quiet one.</span>
            </h2>
          </Reveal>
          <Reveal delay={0.1}><p className="mt-5 max-w-2xl text-muted">Search any place in the console. Every lake in the area is found, compared with an older scene, and scored. Two real results:</p></Reveal>
          <div className="mt-12 grid gap-5 md:grid-cols-2">
            <Reveal>
              <div className="relative h-full overflow-hidden rounded-2xl border border-alarm/40 bg-gradient-to-b from-alarm/[.08] to-transparent p-7 glow-alarm">
                <div className="flex items-start justify-between">
                  <div><div className="font-mono text-xs text-alarm">HIGH HAZARD · SCORE 65</div><div className="mt-2 text-2xl font-semibold">South Lhonak</div><div className="text-sm text-muted">screened as of 1 Oct 2023, two days before it burst</div></div>
                  <Waves className="h-6 w-6 text-alarm" />
                </div>
                <dl className="mt-7 grid grid-cols-2 gap-4 text-sm">
                  <div><dt className="text-faint">Area</dt><dd className="text-lg font-medium">1.29 → 1.64 km²</dd></div>
                  <div><dt className="text-faint">Growth since 2016</dt><dd className="text-lg font-medium text-alarm">+27%</dd></div>
                  <div><dt className="text-faint">Elevation</dt><dd className="text-lg font-medium">5,194 m</dd></div>
                  <div><dt className="text-faint">Glacier</dt><dd className="text-lg font-medium">in contact</dd></div>
                </dl>
              </div>
            </Reveal>
            <Reveal delay={0.1}>
              <div className="relative h-full overflow-hidden rounded-2xl border border-safe/30 bg-gradient-to-b from-safe/[.06] to-transparent p-7">
                <div className="flex items-start justify-between">
                  <div><div className="font-mono text-xs text-safe">STABLE · NOT GLACIER-FED</div><div className="mt-2 text-2xl font-semibold">Tsomgo lake</div><div className="text-sm text-muted">screened as of Oct 2026</div></div>
                  <ShieldCheck className="h-6 w-6 text-safe" />
                </div>
                <dl className="mt-7 grid grid-cols-2 gap-4 text-sm">
                  <div><dt className="text-faint">Area</dt><dd className="text-lg font-medium">0.22 → 0.24 km²</dd></div>
                  <div><dt className="text-faint">Growth since 2019</dt><dd className="text-lg font-medium">+9%</dd></div>
                  <div><dt className="text-faint">Elevation</dt><dd className="text-lg font-medium">3,751 m</dd></div>
                  <div><dt className="text-faint">Glacier</dt><dd className="flex items-center gap-1 text-lg font-medium">none near <Snowflake className="h-4 w-4 text-faint" /></dd></div>
                </dl>
                <p className="mt-6 text-sm text-muted">Bigger isn&apos;t dangerous on its own. No glacier feeds it, so it is never flagged.</p>
              </div>
            </Reveal>
          </div>
        </div>
      </section>

      {/* PROOF */}
      <section id="proof" className="relative border-t border-line">
        <div className="mx-auto max-w-6xl px-6 py-28">
          <Reveal><div className="eyebrow">04 · Proof</div></Reveal>
          <Reveal delay={0.05}><h2 className="mt-4 text-[clamp(2rem,4vw,3.3rem)] font-semibold tracking-[-0.035em]">Replayed on the night it happened.</h2></Reveal>
          <div className="mt-12 grid gap-px overflow-hidden rounded-2xl border border-line bg-line md:grid-cols-6">
            <div className="bg-ink p-8 md:col-span-3">
              <div className="eyebrow !text-alarm">Radar drain check</div>
              <div className="mt-5 flex items-end gap-4">
                <div><div className="text-sm text-faint">{d.before.date}</div><div className="text-3xl font-semibold">{(d.before.water_m2 / 1e6).toFixed(2)} km²</div></div>
                <ArrowRight className="mb-2 h-5 w-5 text-faint" />
                <div><div className="text-sm text-faint">{d.after.date}</div><div className="text-3xl font-semibold text-alarm">{(d.after.water_m2 / 1e6).toFixed(2)} km²</div></div>
              </div>
              <p className="mt-5 text-sm text-muted">Sentinel-1 radar, through cloud. {Math.round(d.area_loss * 100)}% of the open water gone → <span className="font-semibold text-alarm">DRAINED</span>. The same check on two calm passes before the burst: −2%, no alarm.</p>
            </div>
            <div className="bg-ink p-8 md:col-span-3">
              <div className="eyebrow">Arrival after the outburst</div>
              <div className="mt-5 space-y-3">
                {lake.eta.map((e) => (
                  <div key={e.id} className="grid grid-cols-[1fr_auto] items-center gap-4">
                    <div>
                      <div className="flex justify-between text-sm"><span>{e.name}</span><span className="font-mono text-muted">{e.eta_min}–{e.eta_max} min</span></div>
                      <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-white/5">
                        <div className="h-full rounded-full bg-gradient-to-r from-alarm to-watch" style={{ width: `${(e.eta_max / lake.eta[lake.eta.length - 1].eta_max) * 100}%` }} />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              <p className="mt-5 text-xs text-faint">Calibrated on 2023: the flood reached Chungthang {lake.calibration.minutes_min}–{lake.calibration.minutes_max} min after the landslide.</p>
            </div>
            {[
              { k: `${g.from_km2.toFixed(2)} → ${g.to_km2.toFixed(2)} km²`, l: "lake area, Sentinel-2" },
              { k: `${lake.series.length} scenes`, l: "clearest ice-free pass each year" },
              { k: "₹0", l: "data cost — open Copernicus" },
            ].map((s) => (
              <div key={s.l} className="bg-ink p-8 md:col-span-2"><div className="text-2xl font-semibold">{s.k}</div><div className="mt-1 text-sm text-muted">{s.l}</div></div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="relative border-t border-line">
        <div className="absolute left-1/2 top-1/2 h-[400px] w-[700px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-glacier/10 aurora" aria-hidden />
        <div className="relative mx-auto max-w-4xl px-6 py-32 text-center">
          <Reveal><h2 className="text-[clamp(2.2rem,5vw,4rem)] font-semibold leading-[1.02] tracking-[-0.04em]"><span className="text-gradient">Watch every lake.</span><br /><span className="font-serif font-normal italic text-white/60">Warn every place.</span></h2></Reveal>
          <Reveal delay={0.1}>
            <a href="/console" className="group mt-10 inline-flex items-center gap-2 rounded-full bg-glacier px-7 py-3.5 font-medium text-ink glow-cyan transition hover:brightness-110">
              Search a lake <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
            </a>
          </Reveal>
        </div>
      </section>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-6 py-8 text-sm text-faint">
          <span>Team Anivortex · GTB4CEC, New Delhi · Colossal-A-Pitch, Avinya &apos;26</span>
          <span>Imagery © ESA Copernicus · DEM © Copernicus · Places © OpenStreetMap</span>
        </div>
      </footer>
    </main>
  );
}
