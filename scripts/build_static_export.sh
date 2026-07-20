#!/usr/bin/env bash
# Regenerates the committed deployment artifact at repo-root `static/` from
# the Next.js static export. Run this locally (needs Node) whenever the
# frontend changes and before deploying — the deploy platform itself never
# needs Node, only Python (uv sync + uvicorn), because `static/` ships
# pre-built. Mirrors the existing data/scenario_runs convention: a committed
# build artifact, not one regenerated at deploy time.
set -euo pipefail
cd "$(dirname "$0")/.."

(cd frontend && npm run build)

rm -rf static
cp -r frontend/out static

echo "Wrote $(find static -type f | wc -l | tr -d ' ') files to static/"
