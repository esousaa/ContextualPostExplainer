import { ExternalLink } from "lucide-react";

import { sourceTypeTone } from "./labels";
import type { Evidence } from "./types";

type CitationChipProps = {
  sourceId: string;
  source?: Evidence;
  active?: boolean;
  onSelect: (sourceId: string) => void;
};

export function CitationChip({ active = false, onSelect, source, sourceId }: CitationChipProps) {
  const tone = source ? sourceTypeTone(source.source_type) : "neutral";

  return (
    <button
      className={`citation-chip ${tone} ${active ? "active" : ""}`.trim()}
      onClick={() => onSelect(sourceId)}
      title={source ? source.title : "Source not returned by backend"}
      type="button"
    >
      <span>{sourceId}</span>
      {source?.url && <ExternalLink aria-hidden size={12} />}
    </button>
  );
}
