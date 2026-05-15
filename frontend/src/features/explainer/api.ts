import { apiBaseUrl, requestJson } from "../../shared/api/client";
import { ApiClientError } from "../../shared/api/errors";
import { readSseStream } from "../../shared/api/sse";
import type {
  ConfigStatus,
  ExplainPostRequest,
  ExplanationResponse,
  LiveErrorEvent,
  LiveProgressEvent,
} from "./types";

type ExplainPostStreamOptions = {
  signal?: AbortSignal;
  onProgress: (event: LiveProgressEvent) => void;
};

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

export async function explainPostStream(
  request: ExplainPostRequest,
  options: ExplainPostStreamOptions,
): Promise<ExplanationResponse> {
  const response = await fetch(`${apiBaseUrl()}/api/explain/stream`, {
    method: "POST",
    body: JSON.stringify({
      url: request.url,
      include_debug: request.include_debug ?? false,
    }),
    headers: {
      "Content-Type": "application/json",
    },
    signal: options.signal,
  });

  if (!response.ok) {
    throw await apiErrorFromResponse(response);
  }

  if (!response.body) {
    throw new ApiClientError({
      error: "missing_stream_body",
      message: "The backend did not return a readable stream.",
    });
  }

  let finalResponse: ExplanationResponse | null = null;

  await readSseStream(response.body, (message) => {
    const payload = parseJson(message.data);
    if (!payload) {
      throw new ApiClientError({
        error: "empty_stream_event",
        message: "The backend returned an empty stream event.",
      });
    }

    if (message.event === "progress") {
      options.onProgress(payload as LiveProgressEvent);
      return;
    }

    if (message.event === "result") {
      finalResponse = payload as ExplanationResponse;
      return;
    }

    if (message.event === "error") {
      throw apiErrorFromStreamPayload(payload as Partial<LiveErrorEvent>);
    }
  });

  if (!finalResponse) {
    throw new ApiClientError({
      error: "missing_stream_result",
      message: "The backend stream ended without a result.",
    });
  }

  return finalResponse;
}

export function getConfigStatus(signal?: AbortSignal): Promise<ConfigStatus> {
  return requestJson<ConfigStatus>("/api/config/status", {
    method: "GET",
    signal
  });
}

async function apiErrorFromResponse(response: Response): Promise<ApiClientError> {
  const payload = parseJson(await response.text());
  return new ApiClientError({
    error: stringField(payload, "error") ?? `http_${response.status}`,
    message: stringField(payload, "message") ?? response.statusText,
    status: response.status,
  });
}

function apiErrorFromStreamPayload(payload: Partial<LiveErrorEvent>): ApiClientError {
  return new ApiClientError({
    error: typeof payload.error === "string" ? payload.error : "stream_error",
    message: typeof payload.message === "string" ? payload.message : "The backend stream failed.",
    status: typeof payload.status === "number" ? payload.status : undefined,
  });
}

function parseJson(text: string): Record<string, unknown> | null {
  if (!text.trim()) {
    return null;
  }

  try {
    return JSON.parse(text) as Record<string, unknown>;
  } catch {
    throw new ApiClientError({
      error: "invalid_json",
      message: "The backend returned an invalid stream event.",
    });
  }
}

function stringField(payload: Record<string, unknown> | null, field: string): string | null {
  const value = payload?.[field];
  return typeof value === "string" ? value : null;
}
