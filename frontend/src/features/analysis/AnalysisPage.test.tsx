import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AnalysisPage } from "./AnalysisPage";
import type { AnalysisOverview } from "./types";

describe("AnalysisPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders provider and LLM comparative cards, charts, and readouts", async () => {
    const onNavigate = vi.fn();
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(jsonResponse(overview))));

    render(<AnalysisPage onNavigate={onNavigate} />);

    expect(await screen.findByRole("heading", { name: "Search Provider" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "LLM" })).toBeInTheDocument();
    expect(screen.getByText("Most reliable")).toBeInTheDocument();
    expect(screen.getByText("Highest bullet yield")).toBeInTheDocument();
    expect(screen.getAllByText("No explanation rate")).toHaveLength(2);
    expect(screen.getAllByText("Avg execution time")).toHaveLength(2);
    expect(screen.getByText("Search Provider assessment")).toBeInTheDocument();
    expect(screen.getByText("LLM assessment")).toBeInTheDocument();
    expect(screen.queryByText("Rerun impact")).not.toBeInTheDocument();
  });
});

const overview: AnalysisOverview = {
  total_runs: 2,
  total_urls: 1,
  provider_aggregates: [
    {
      key: "composite",
      run_count: 2,
      completed_count: 1,
      no_explanation_count: 1,
      failed_count: 0,
      avg_execution_time_ms: 1200,
      avg_bullet_count: 1.5,
      avg_cited_source_count: 1,
      avg_warning_count: 0.5,
      avg_search_results_received: 20,
      avg_search_provider_overlap_count: 2,
      avg_search_time_ms: 500,
      avg_fetch_time_ms: 400,
    },
    {
      key: "tavily",
      run_count: 2,
      completed_count: 2,
      no_explanation_count: 0,
      failed_count: 0,
      avg_execution_time_ms: 900,
      avg_bullet_count: 2,
      avg_cited_source_count: 1.5,
      avg_warning_count: 0.25,
      avg_search_results_received: 12,
      avg_search_provider_overlap_count: 0,
      avg_search_time_ms: 300,
      avg_fetch_time_ms: 350,
    },
  ],
  llm_aggregates: [
    {
      key: "gen=gpt-4o | judge=gpt-4o-mini | embed=text-embedding-3-small | vision=gpt-4o",
      run_count: 2,
      completed_count: 1,
      no_explanation_count: 1,
      failed_count: 0,
      avg_execution_time_ms: 1200,
      avg_bullet_count: 1.5,
      avg_cited_source_count: 1,
      avg_warning_count: 0.5,
      avg_search_results_received: 20,
      avg_search_provider_overlap_count: 2,
      avg_search_time_ms: 500,
      avg_fetch_time_ms: 400,
    },
    {
      key: "gen=gpt-5-mini | judge=gpt-5-mini | embed=text-embedding-3-small | vision=gpt-5.1",
      run_count: 2,
      completed_count: 2,
      no_explanation_count: 0,
      failed_count: 0,
      avg_execution_time_ms: 800,
      avg_bullet_count: 2.8,
      avg_cited_source_count: 1.8,
      avg_warning_count: 0.2,
      avg_search_results_received: 20,
      avg_search_provider_overlap_count: 2,
      avg_search_time_ms: 500,
      avg_fetch_time_ms: 400,
    },
  ],
  url_comparisons: [
    {
      url: "https://bsky.app/profile/example/post/abc",
      run_count: 2,
      behavior_changed: true,
      latest_status: "completed",
      latest_confidence: "high",
      latest_bullet_count: 3,
      bullet_counts: [0, 3],
      confidence_values: ["high", "low"],
      status_values: ["completed", "no_explanation"],
      runs: [
        {
          run_id: "run_latest",
          url: "https://bsky.app/profile/example/post/abc",
          generated_at: "2026-05-15T12:00:00+00:00",
          status: "completed",
          confidence: "high",
          search_provider: "composite",
          generation_model: "gpt-4o",
          judge_model: "gpt-4o-mini",
          embedding_model: "text-embedding-3-small",
          vision_model: "gpt-4o",
          comparison_group_id: "manual_live",
          comparison_config_id: "composite",
          bullet_count: 3,
          cited_source_count: 2,
          source_count: 4,
          warning_count: 0,
          execution_time_ms: 1200,
          search_results_received: 20,
          search_provider_overlap_count: 2,
          ranked_multi_provider_source_count: 1,
          cited_multi_provider_source_count: 1,
          search_time_ms: 500,
          fetch_time_ms: 400,
        },
      ],
    },
  ],
};

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}
