#!/usr/bin/env sh
# Assemble the API as a Vercel Python project in $1 (deploy it with `vercel deploy --prod` from there).
# Scans and area analyses run inside the request (JHEEL_SYNC) and the alert log lives in /tmp.
# Never PLAN.md, the DEM or the alert log; the scene images ship with the frontend instead.
set -eu
out=${1:?usage: build_vercel_api.sh OUT_DIR}
root=$(cd "$(dirname "$0")/.." && pwd)
rm -rf "$out" && mkdir -p "$out/jheel" "$out/data" "$out/web"
cp "$root/app.py" "$out/"
cp "$root/requirements-serve.txt" "$out/requirements.txt"
cp "$root"/jheel/*.py "$out/jheel/"
cp "$root/web/index.html" "$root/web/logo.png" "$out/web/"
cp "$root/data/south-lhonak.json" "$root/data/watchlist.json" "$out/data/"
# rasterio's Linux wheel links the system libexpat, which Vercel's runtime lacks: ship Debian 11's
# (deploy/vercel/libexpat.so.1, expat 2.2.10); jheel/__init__.py loads it before rasterio is imported.
mkdir -p "$out/lib" && cp "$root/deploy/vercel/libexpat.so.1" "$out/lib/"
# Vercel runs app.py as FastAPI and hands it the real request path (a rewrite to a wrapper would not).
cat > "$out/vercel.json" <<'JSON'
{ "functions": { "app.py": { "maxDuration": 300, "memory": 2048, "includeFiles": "{jheel/**,data/**,web/**,lib/**}" } } }
JSON
