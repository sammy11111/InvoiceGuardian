/**
 * Loads the REAL persisted view JSON (data/scenario_views/) for tests — the
 * same files the static build embeds. Deliberately does not import
 * lib/data.ts, which is guarded by `server-only` and throws outside a
 * server/build context; this duplicates only the plain fs read.
 */
import fs from "node:fs";
import path from "node:path";

import type { ScenarioDetail, ScenarioSummary } from "@/lib/types";

const VIEWS_DIR = path.join(process.cwd(), "..", "data", "scenario_views");

export function loadScenarioDetail(invoiceId: string): ScenarioDetail {
  const raw = fs.readFileSync(path.join(VIEWS_DIR, `${invoiceId}.json`), "utf-8");
  return JSON.parse(raw) as ScenarioDetail;
}

export function loadAllScenarioSummaries(): ScenarioSummary[] {
  const raw = fs.readFileSync(path.join(VIEWS_DIR, "_index.json"), "utf-8");
  return JSON.parse(raw) as ScenarioSummary[];
}

export function loadAllScenarioDetails(): ScenarioDetail[] {
  return loadAllScenarioSummaries().map((s) => loadScenarioDetail(s.invoice_id));
}
