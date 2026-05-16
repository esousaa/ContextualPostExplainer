import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { mockExplanationResponse } from "../../test/mockResponse";
import { ObservabilityPage } from "./ObservabilityPage";
import type { RunDetail, RunSummary } from "./types";

describe("ObservabilityPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders run history, timeline, and diagnostics tabs", async () => {
    vi.stubGlobal("fetch", vi.fn(mockFetchRuns));
    const user = userEvent.setup();

    render(<ObservabilityPage onNavigate={vi.fn()} selectedRunId="run_observe" />);

    expect(await screen.findAllByText("run_observe")).toHaveLength(2);
    expect(screen.getByText("Reading sources")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "queries" }));

    expect(screen.getByText("Trump DOJ DC Bar lawsuit")).toBeInTheDocument();
  });

  it("renders zero-bullet runs as no explanation", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/api/runs/run_empty")) {
          return Promise.resolve(jsonResponse(emptyRunDetail));
        }
        return Promise.resolve(jsonResponse({ runs: [emptyRunSummary] }));
      }),
    );
    const user = userEvent.setup();

    render(<ObservabilityPage onNavigate={vi.fn()} selectedRunId="run_empty" />);

    expect(await screen.findAllByText("no explanation")).toHaveLength(2);
    await user.click(screen.getByRole("button", { name: "explanation" }));
    expect(screen.getByText("No bullets generated")).toBeInTheDocument();
  });
});

const runSummary: RunSummary = {
  run_id: "run_observe",
  mode: "live",
  generated_at: "2026-05-15T12:00:00+00:00",
  input_url: mockExplanationResponse.post?.url ?? null,
  status: "completed",
  confidence: "high",
  execution_time_ms: 8420,
  source_count: 2,
  cited_source_count: 2,
  warning_count: 1,
  bullet_count: 3,
  post_author: "rbreich.bsky.social",
  post_text: "The DOJ is acting as Trump's personal attorney.",
};

const runDetail: RunDetail = {
  summary: runSummary,
  post: mockExplanationResponse.post,
  response: mockExplanationResponse,
  timeline: [
    {
      node_name: "fetch_source_pages",
      step: "Reading sources",
      status: "completed",
      started_at: "2026-05-15T12:00:00+00:00",
      completed_at: "2026-05-15T12:00:01+00:00",
      duration_ms: 1000,
    },
  ],
  queries: ["Trump DOJ DC Bar lawsuit"],
  metrics: { search_results_received: 10 },
  sources: mockExplanationResponse.sources,
  cited_sources: mockExplanationResponse.sources,
  warnings: mockExplanationResponse.warnings,
  error: null,
  raw: { run_id: "run_observe" },
};

const emptyRunSummary: RunSummary = {
  ...runSummary,
  run_id: "run_empty",
  status: "no_explanation",
  confidence: "low",
  cited_source_count: 0,
  bullet_count: 0,
};

const emptyRunDetail: RunDetail = {
  ...runDetail,
  summary: emptyRunSummary,
  response: {
    ...mockExplanationResponse,
    explanation: [],
    sources: [],
    confidence: "low",
  },
};

function mockFetchRuns(input: RequestInfo | URL) {
  const url = String(input);
  if (url.includes("/api/runs/run_observe")) {
    return Promise.resolve(jsonResponse(runDetail));
  }
  if (url.includes("/api/runs")) {
    return Promise.resolve(jsonResponse({ runs: [runSummary] }));
  }
  return Promise.reject(new Error(`Unexpected URL ${url}`));
}

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}
