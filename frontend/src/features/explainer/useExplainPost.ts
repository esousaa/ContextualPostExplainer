import { useCallback, useRef, useState } from "react";

import { normalizeApiError } from "../../shared/api/errors";
import { explainPost } from "./api";
import type { ApiError, ExplanationResponse } from "./types";

type ExplainState =
  | { status: "idle"; data: null; error: null }
  | { status: "loading"; data: null; error: null }
  | { status: "success"; data: ExplanationResponse; error: null }
  | { status: "error"; data: null; error: ApiError };

const REQUEST_TIMEOUT_MS = 90_000;

export function useExplainPost() {
  const [state, setState] = useState<ExplainState>({
    status: "idle",
    data: null,
    error: null
  });
  const abortRef = useRef<AbortController | null>(null);

  const submit = useCallback(async (url: string) => {
    const trimmedUrl = url.trim();
    if (!trimmedUrl) {
      setState({
        status: "error",
        data: null,
        error: {
          error: "empty_url",
          message: "Enter a public Bluesky post URL."
        }
      });
      return;
    }

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const timeoutId = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

    setState({ status: "loading", data: null, error: null });

    try {
      const data = await explainPost({ url: trimmedUrl, include_debug: false }, controller.signal);
      setState({ status: "success", data, error: null });
    } catch (error) {
      setState({
        status: "error",
        data: null,
        error: normalizeApiError(error)
      });
    } finally {
      window.clearTimeout(timeoutId);
      if (abortRef.current === controller) {
        abortRef.current = null;
      }
    }
  }, []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setState({ status: "idle", data: null, error: null });
  }, []);

  return {
    ...state,
    submit,
    reset
  };
}
