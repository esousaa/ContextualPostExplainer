import { requestJson } from "../../shared/api/client";
import type { ConfigStatus, ExplainPostRequest, ExplanationResponse } from "./types";

export function explainPost(
  request: ExplainPostRequest,
  signal?: AbortSignal
): Promise<ExplanationResponse> {
  return requestJson<ExplanationResponse>("/api/explain", {
    method: "POST",
    body: JSON.stringify({
      url: request.url,
      include_debug: request.include_debug ?? false
    }),
    signal
  });
}

export function getConfigStatus(signal?: AbortSignal): Promise<ConfigStatus> {
  return requestJson<ConfigStatus>("/api/config/status", {
    method: "GET",
    signal
  });
}
