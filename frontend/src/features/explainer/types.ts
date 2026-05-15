export type Confidence = "high" | "medium" | "low";

export type WarningSeverity = "info" | "warning";

export type ValidationWarning = {
  severity: WarningSeverity;
  code: string;
  message: string;
  bullet_index: number | null;
};

export type PostAuthor = {
  handle: string;
  display_name: string | null;
  did: string | null;
};

export type ImageContext = {
  url: string | null;
  alt_text: string | null;
  ocr_text: string | null;
  description: string | null;
  image_type: string | null;
};

export type PostData = {
  url: string;
  platform: "bluesky";
  author: PostAuthor;
  text: string;
  created_at: string | null;
  images: ImageContext[];
  links: string[];
  parent_text: string | null;
  quote_text: string | null;
  thread_text: string | null;
};

export type SourceCategory =
  | "primary_official"
  | "court_document"
  | "news_outlet"
  | "fact_checking"
  | "expert_commentary"
  | "social_post"
  | "thread_comment"
  | "unknown";

export type SourceRole =
  | "original_post"
  | "primary_evidence"
  | "official_position"
  | "independent_context"
  | "author_interpretation"
  | "public_reaction"
  | "background_support"
  | "image_observation";

export type SourceType = "web" | "social" | "thread" | "fixture" | "image";

export type Evidence = {
  id: string;
  title: string;
  url: string | null;
  snippet: string;
  content: string;
  source_type: SourceType;
  provider: string | null;
  query: string | null;
  canonical_url: string | null;
  published_at: string | null;
  publisher: string | null;
  source_category: SourceCategory;
  source_role: SourceRole;
  relevance_score?: number;
};

export type ClaimLabel =
  | "confirmed_fact"
  | "official_position"
  | "author_interpretation"
  | "public_reaction";

export type ContextModifier =
  | "background_context"
  | "legal_context"
  | "political_context"
  | "timeline_context";

export type ExplanationBullet = {
  text: string;
  source_ids: string[];
  claim_label: ClaimLabel;
  context_modifiers: ContextModifier[];
  confidence: Confidence;
  warnings: ValidationWarning[];
};

export type ExplanationResponse = {
  post: PostData | null;
  explanation: ExplanationBullet[];
  sources: Evidence[];
  confidence: Confidence;
  warnings: ValidationWarning[];
  execution_time_ms: number;
};

export type ExplainPostRequest = {
  url: string;
  include_debug?: boolean;
};

export type { ApiError } from "../../shared/api/errors";

export type ConfigStatus = {
  status: "ok" | "invalid";
  error?: string;
  live_search?: {
    provider: "brave" | "tavily" | "composite" | null;
    configured: boolean;
  };
};
