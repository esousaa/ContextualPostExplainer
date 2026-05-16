import type { RunStatus } from "../observability/types";

export type AnalysisRunMetrics = {
  run_id: string;
  url: string | null;
  generated_at: string | null;
  status: RunStatus;
  confidence: string | null;
  search_provider: string | null;
  generation_model: string | null;
  judge_model: string | null;
  embedding_model: string | null;
  vision_model: string | null;
  comparison_group_id: string | null;
  comparison_config_id: string | null;
  bullet_count: number;
  cited_source_count: number;
  source_count: number;
  warning_count: number;
  execution_time_ms: number | null;
  search_results_received: number | null;
  search_provider_overlap_count: number | null;
  ranked_multi_provider_source_count: number | null;
  cited_multi_provider_source_count: number | null;
  search_time_ms: number | null;
  fetch_time_ms: number | null;
};

export type AnalysisAggregate = {
  key: string;
  run_count: number;
  completed_count: number;
  no_explanation_count: number;
  failed_count: number;
  avg_execution_time_ms: number | null;
  avg_bullet_count: number | null;
  avg_cited_source_count: number | null;
  avg_warning_count: number | null;
  avg_search_results_received: number | null;
  avg_search_provider_overlap_count: number | null;
  avg_search_time_ms: number | null;
  avg_fetch_time_ms: number | null;
};

export type UrlBehaviorComparison = {
  url: string;
  run_count: number;
  behavior_changed: boolean;
  latest_status: RunStatus;
  latest_confidence: string | null;
  latest_bullet_count: number;
  bullet_counts: number[];
  confidence_values: string[];
  status_values: RunStatus[];
  runs: AnalysisRunMetrics[];
};

export type AnalysisOverview = {
  total_runs: number;
  total_urls: number;
  provider_aggregates: AnalysisAggregate[];
  llm_aggregates: AnalysisAggregate[];
  url_comparisons: UrlBehaviorComparison[];
};
