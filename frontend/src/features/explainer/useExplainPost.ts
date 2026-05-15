import { useCallback, useRef, useState } from "react";

import { normalizeApiError } from "../../shared/api/errors";
import { explainPostStream } from "./api";
import { applyProgressEvent, createInitialProgress, failProgress } from "./progress";
import type { ApiError, ExplanationResponse, LiveProgressEvent, LiveProgressState } from "./types";

type ExplainState =
  | { status: "idle"; data: null; error: null; progress: LiveProgressState }
  | { status: "loading"; data: null; error: null; progress: LiveProgressState }
  | { status: "success"; data: ExplanationResponse; error: null; progress: LiveProgressState }
  | { status: "error"; data: null; error: ApiError; progress: LiveProgressState };

const REQUEST_TIMEOUT_MS = 90_000;

export function useExplainPost() {
  const [state, setState] = useState<ExplainState>({
    status: "idle",
    data: null,
    error: null,
    progress: createInitialProgress()
  });
  const abortRef = useRef<AbortController | null>(null);

  const updateProgress = useCallback((event: LiveProgressEvent) => {
    setState((current) => {
      if (current.status !== "loading") {
        return current;
      }

      return {
        ...current,
        progress: applyProgressEvent(current.progress, event)
      };
    });
  }, []);

  const submit = useCallback(async (url: string) => {
    const trimmedUrl = url.trim();
    if (!trimmedUrl) {
      setState({
        status: "error",
        data: null,
        error: {
          error: "empty_url",
          message: "Enter a public Bluesky post URL."
        },
        progress: createInitialProgress()
      });
      return;
    }

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const timeoutId = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

    setState({ status: "loading", data: null, error: null, progress: createInitialProgress() });

    try {
      const data = await explainPostStream(
        { url: trimmedUrl, include_debug: false },
        {
          signal: controller.signal,
          onProgress: (event) => {
            if (abortRef.current === controller) {
              updateProgress(event);
            }
          }
        }
      );
      if (abortRef.current !== controller) {
        return;
      }
      setState((current) => ({ status: "success", data, error: null, progress: current.progress }));
    } catch (error) {
      if (abortRef.current !== controller) {
        return;
      }
      setState((current) => ({
        status: "error",
        data: null,
        error: normalizeApiError(error),
        progress: failProgress(current.progress)
      }));
    } finally {
      window.clearTimeout(timeoutId);
      if (abortRef.current === controller) {
        abortRef.current = null;
      }
    }
  }, [updateProgress]);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setState({ status: "idle", data: null, error: null, progress: createInitialProgress() });
  }, []);

  return {
    ...state,
    submit,
    reset
  };
}
