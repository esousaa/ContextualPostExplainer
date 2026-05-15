import type { ExplanationResponse } from "../features/explainer/types";

export const mockExplanationResponse: ExplanationResponse = {
  post: {
    url: "https://bsky.app/profile/rbreich.bsky.social/post/3mltultyalm2v",
    platform: "bluesky",
    author: {
      handle: "rbreich.bsky.social",
      display_name: "Robert Reich",
      did: "did:plc:test"
    },
    text: "The DOJ is acting as Trump's personal attorney.",
    created_at: "2026-05-14T12:00:00Z",
    images: [],
    links: [],
    parent_text: null,
    quote_text: null,
    thread_text: "Thread context from Bluesky."
  },
  explanation: [
    {
      text: "The DOJ filed a lawsuit involving D.C. attorney disciplinary authorities.",
      claim_label: "confirmed_fact",
      context_modifiers: ["legal_context"],
      confidence: "high",
      warnings: [],
      source_ids: ["src_news"]
    },
    {
      text: "The department argues the disciplinary process is politically motivated.",
      claim_label: "official_position",
      context_modifiers: ["legal_context", "political_context"],
      confidence: "medium",
      warnings: [
        {
          severity: "info",
          code: "OFFICIAL_POSITION_VIA_NEWS",
          message: "Official position is supported by a news outlet report rather than a primary source.",
          bullet_index: 1
        }
      ],
      source_ids: ["src_news"]
    },
    {
      text: "The post author's framing is an interpretation of the lawsuit and its political context.",
      claim_label: "author_interpretation",
      context_modifiers: ["political_context"],
      confidence: "medium",
      warnings: [],
      source_ids: ["thread_original", "src_news"]
    }
  ],
  sources: [
    {
      id: "thread_original",
      title: "Bluesky thread by @rbreich.bsky.social",
      url: "https://bsky.app/profile/rbreich.bsky.social/post/3mltultyalm2v",
      snippet: "The DOJ is acting as Trump's personal attorney.",
      content: "The DOJ is acting as Trump's personal attorney.",
      source_type: "thread",
      provider: "bluesky",
      query: null,
      canonical_url: null,
      published_at: "2026-05-14T12:00:00Z",
      publisher: "rbreich.bsky.social",
      source_category: "social_post",
      source_role: "original_post",
      relevance_score: 0.97
    },
    {
      id: "src_news",
      title: "Justice Department sues D.C. attorney disciplinary authorities",
      url: "https://example.com/doj-dc-bar",
      snippet: "The lawsuit challenges efforts to sanction Trump administration lawyers.",
      content: "The lawsuit challenges efforts to sanction Trump administration lawyers.",
      source_type: "web",
      provider: "tavily",
      query: "Trump DOJ DC Bar lawsuit",
      canonical_url: "https://example.com/doj-dc-bar",
      published_at: "2026-05-14T10:00:00Z",
      publisher: "example.com",
      source_category: "news_outlet",
      source_role: "independent_context",
      relevance_score: 0.71
    }
  ],
  confidence: "high",
  warnings: [
    {
      severity: "info",
      code: "OFFICIAL_POSITION_VIA_NEWS",
      message: "Official position is supported by a news outlet report rather than a primary source.",
      bullet_index: 1
    }
  ],
  execution_time_ms: 8420
};
