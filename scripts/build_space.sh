#!/usr/bin/env sh
# Assemble the Hugging Face Space for the API in $1: only what the Dockerfile copies, plus the Space header.
# Never PLAN.md, the DEM or the alert log.
set -eu
out=${1:?usage: build_space.sh OUT_DIR}
root=$(cd "$(dirname "$0")/.." && pwd)
rm -rf "$out" && mkdir -p "$out/jheel" "$out/data"
cp "$root/Dockerfile" "$root/requirements-serve.txt" "$root/app.py" "$out/"
cp "$root"/jheel/*.py "$out/jheel/"
cp -r "$root/web" "$out/web"
cp "$root/data/south-lhonak.json" "$out/data/"
cat > "$out/README.md" <<'MD'
---
title: Jheel Prahari API
emoji: 🏔️
colorFrom: blue
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

API for Jheel Prahari, a glacial lake watch and flood early warning for South Lhonak.
The site is served separately; this Space answers its /api requests.
MD
