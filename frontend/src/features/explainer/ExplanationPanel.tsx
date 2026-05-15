import { ShieldCheck } from "lucide-react";

import { Badge } from "../../shared/components/Badge";
import { confidenceTone, readableLabel } from "./labels";
import { CitationChip } from "./CitationChip";
import { ClaimBadge } from "./ClaimBadge";
import { WarningList } from "./WarningList";
import type { Evidence, ExplanationBullet } from "./types";

type ExplanationPanelProps = {
  bullets: ExplanationBullet[];
  sourceById: Map<string, Evidence>;
  selectedSourceIds: string[];
  onSelectSource: (sourceId: string) => void;
  onFocusSources: (sourceIds: string[]) => void;
};

export function ExplanationPanel({
  bullets,
  onFocusSources,
  onSelectSource,
  selectedSourceIds,
  sourceById
}: ExplanationPanelProps) {
  return (
    <section className="panel main-panel" aria-labelledby="explanation-title">
      <div className="panel-title">
        <div>
          <p className="eyebrow">Cited explanation</p>
          <h2 id="explanation-title">Explanation</h2>
        </div>
        <span className="panel-count">{bullets.length} bullets</span>
      </div>

      <div className="bullet-stack">
        {bullets.map((bullet, index) => (
          <article
            className="explanation-item"
            key={`${bullet.text}-${index}`}
            onBlur={() => onFocusSources([])}
            onFocus={() => onFocusSources(bullet.source_ids)}
            onMouseEnter={() => onFocusSources(bullet.source_ids)}
          >
            <div className="bullet-index">{index + 1}</div>
            <div className="bullet-content">
              <div className="bullet-meta">
                <ClaimBadge value={bullet.claim_label} />
                <Badge tone={confidenceTone(bullet.confidence)}>
                  <ShieldCheck size={13} />
                  {bullet.confidence}
                </Badge>
                {bullet.context_modifiers.map((modifier) => (
                  <Badge key={modifier} tone="neutral">
                    {readableLabel(modifier)}
                  </Badge>
                ))}
              </div>
              <p>{bullet.text}</p>
              <div className="citation-row" aria-label={`Sources for bullet ${index + 1}`}>
                {bullet.source_ids.map((sourceId) => (
                  <CitationChip
                    active={selectedSourceIds.includes(sourceId)}
                    key={sourceId}
                    onSelect={onSelectSource}
                    source={sourceById.get(sourceId)}
                    sourceId={sourceId}
                  />
                ))}
              </div>
              <WarningList compact warnings={bullet.warnings} />
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
