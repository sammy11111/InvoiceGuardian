import "server-only";

import fs from "node:fs";
import path from "node:path";

import type { ScenarioDetail, ScenarioSummary } from "./types";

/**
 * Reads the pre-computed view JSON that
 * `python -m invoiceguardian.analyze --all --persist` writes to
 * `data/scenario_views/`. Runs only in Server Components, at `next build`
 * time for the static export — no client-side fetch, no runtime dependency
 * on FastAPI being reachable. See src/invoiceguardian/api/export.py for the
 * single implementation of this projection logic.
 */
const VIEWS_DIR = path.join(process.cwd(), "..", "data", "scenario_views");

export function getAllScenarioSummaries(): ScenarioSummary[] {
  const raw = fs.readFileSync(path.join(VIEWS_DIR, "_index.json"), "utf-8");
  return JSON.parse(raw) as ScenarioSummary[];
}

export function getScenarioDetail(invoiceId: string): ScenarioDetail {
  const raw = fs.readFileSync(path.join(VIEWS_DIR, `${invoiceId}.json`), "utf-8");
  return JSON.parse(raw) as ScenarioDetail;
}

export function getAllScenarioDetails(): ScenarioDetail[] {
  return getAllScenarioSummaries().map((s) => getScenarioDetail(s.invoice_id));
}
