import type {
  ClaimLabel,
  Confidence,
  ContextModifier,
  SourceCategory,
  SourceRole,
  SourceType,
  WarningSeverity
} from "./types";

type Tone = "neutral" | "green" | "teal" | "amber" | "coral" | "blue";

export function confidenceTone(value: Confidence): Tone {
  if (value === "high") return "green";
  if (value === "medium") return "amber";
  return "coral";
}

export function severityTone(value: WarningSeverity): Tone {
  return value === "info" ? "blue" : "amber";
}

export function sourceTypeTone(value: SourceType): Tone {
  if (value === "image") return "blue";
  if (value === "thread") return "teal";
  if (value === "social") return "coral";
  if (value === "fixture") return "amber";
  return "blue";
}

export function sourceCategoryTone(value: SourceCategory): Tone {
  if (value === "primary_official" || value === "court_document") return "green";
  if (value === "news_outlet" || value === "fact_checking") return "blue";
  if (value === "social_post" || value === "thread_comment") return "coral";
  if (value === "expert_commentary") return "teal";
  return "neutral";
}

export function claimTone(value: ClaimLabel): Tone {
  if (value === "confirmed_fact") return "green";
  if (value === "official_position") return "blue";
  if (value === "author_interpretation") return "teal";
  return "coral";
}

export function readableLabel(
  value: ClaimLabel | ContextModifier | SourceCategory | SourceRole | SourceType | string
) {
  return value.replaceAll("_", " ");
}
