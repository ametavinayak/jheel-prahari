// Server-side proxy to the Jheel Prahari API (FastAPI). The browser only ever talks to this route; the backend
// URL and token stay on the server. Only the endpoints below are forwarded.
import { NextRequest, NextResponse } from "next/server";

const BACKEND = (process.env.JHEEL_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const TOKEN = process.env.JHEEL_API_TOKEN;
const MAX_BODY = 64 * 1024;
// A serverless API runs a scan or an area analysis inside the request (about a minute, sometimes more).
export const maxDuration = 300;
const SLOW = /^(scan|analyze|memory\/(triage|briefing|log))$/;

const GET_OK = [/^lake$/, /^watchlist$/, /^capabilities$/, /^memory\/status$/, /^alerts$/, /^scan$/, /^analyze\/[0-9a-f]{10}$/, /^scenes\/\d{4}-\d{2}-\d{2}\.png$/];
const POST_OK = [/^trigger$/, /^memory\/(triage|log|briefing)$/, /^ask$/, /^scan$/, /^analyze$/];

function target(path: string) {
  return path.startsWith("scenes/") ? `${BACKEND}/${path}` : `${BACKEND}/api/${path}`;
}

async function forward(req: NextRequest, path: string, init: RequestInit) {
  const headers: Record<string, string> = {};
  if (TOKEN) headers["X-Jheel-Token"] = TOKEN;
  if (init.body) headers["Content-Type"] = "application/json";
  try {
    const res = await fetch(target(path), { ...init, headers, cache: "no-store", signal: AbortSignal.timeout(init.method === "POST" && SLOW.test(path) ? 290000 : 30000) });
    const type = res.headers.get("content-type") || "application/json";
    return new NextResponse(await res.arrayBuffer(), {
      status: res.status,
      headers: { "content-type": type, ...(path.startsWith("scenes/") ? { "cache-control": "public, max-age=86400" } : {}) },
    });
  } catch (e) {
    const reason = e instanceof Error ? e.name : "error";
    return NextResponse.json({ detail: `Lake service unreachable (${reason}). Is the API running on ${BACKEND}?` }, { status: 502 });
  }
}

export async function GET(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const path = (await ctx.params).path.join("/");
  if (!GET_OK.some((r) => r.test(path))) return NextResponse.json({ detail: "not found" }, { status: 404 });
  return forward(req, path, { method: "GET" });
}

export async function POST(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const path = (await ctx.params).path.join("/");
  if (!POST_OK.some((r) => r.test(path))) return NextResponse.json({ detail: "not found" }, { status: 404 });
  const body = await req.text();
  if (body.length > MAX_BODY) return NextResponse.json({ detail: "request too large" }, { status: 413 });
  if (body) {
    try { JSON.parse(body); } catch { return NextResponse.json({ detail: "body must be JSON" }, { status: 400 }); }
  }
  return forward(req, path, { method: "POST", body: body || "{}" });
}
