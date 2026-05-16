import type { Evidence, ExplanationResponse, PostData } from "../explainer/types";

export type RunStatus = "completed" | "no_explanation" | "failed" | "unknown";

export type RunSummary = {
  run_id: string;
  mode: "live" | "eval";
  generated_at: string | null;
  input_url: string | null;
  status: RunStatus;
  confidence: string | null;
  execution_time_ms: number | null;
  source_count: number;
  cited_source_count: number;
  warning_count: number;
  bullet_count: number;
  post_author: string | null;
  post_text: string | null;
};

export type RunTimelineItem = {
  node_name: string;
  step: string;
  status: RunStatus;
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number | null;
};

export type RunDetail = {
  summary: RunSummary;
  post: PostData | null;
  response: ExplanationResponse | null;
  timeline: RunTimelineItem[];
  queries: string[];
  metrics: Record<string, unknown>;
  sources: Evidence[];
  cited_sources: Evidence[];
  warnings: unknown[];
  error: Record<string, unknown> | null;
  raw: Record<string, unknown>;
};

export type RunListResponse = {
  runs: RunSummary[];
};
