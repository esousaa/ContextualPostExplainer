import { requestJson } from "../../shared/api/client";
import type { AnalysisOverview } from "./types";

export function getAnalysisOverview(signal?: AbortSignal): Promise<AnalysisOverview> {
  return requestJson<AnalysisOverview>("/api/analysis?limit=500", {
    method: "GET",
    signal,
  });
}
