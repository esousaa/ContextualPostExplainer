import { ApiClientError } from "./errors";

type RequestOptions = RequestInit & {
  signal?: AbortSignal;
};

export async function requestJson<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers
    }
  });

  const text = await response.text();
  const payload = parseJson(text);

  if (!response.ok) {
    throw new ApiClientError({
      error: stringField(payload, "error") ?? `http_${response.status}`,
      message: stringField(payload, "message") ?? response.statusText,
      status: response.status
    });
  }

  return payload as T;
}

export function apiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL as string | undefined;
  if (configured !== undefined) return configured.replace(/\/+$/, "");
  return "http://localhost:8000";
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
      message: "The backend returned an invalid response."
    });
  }
}

function stringField(payload: Record<string, unknown> | null, field: string): string | null {
  const value = payload?.[field];
  return typeof value === "string" ? value : null;
}
