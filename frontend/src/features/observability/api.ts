import { requestJson } from "../../shared/api/client";
import type { RunDetail, RunListResponse } from "./types";

export function getRuns(signal?: AbortSignal): Promise<RunListResponse> {
  return requestJson<RunListResponse>("/api/runs?mode=live&limit=100", {
    method: "GET",
    signal,
  });
}

export function getRunDetail(runId: string, signal?: AbortSignal): Promise<RunDetail> {
  return requestJson<RunDetail>(`/api/runs/${encodeURIComponent(runId)}?mode=live`, {
    method: "GET",
    signal,
  });
}
