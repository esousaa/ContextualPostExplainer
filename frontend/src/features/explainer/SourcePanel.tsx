import { ExternalLink, FileText } from "lucide-react";

import { Badge } from "../../shared/components/Badge";
import { hostFromUrl } from "../../shared/utils/url";
import { readableLabel, sourceTypeTone } from "./labels";
import { SourceRoleBadge } from "./SourceRoleBadge";
import type { Evidence } from "./types";

type SourcePanelProps = {
  sources: Evidence[];
  highlightedSourceIds: string[];
  selectedSourceIds: string[];
};

export function SourcePanel({ highlightedSourceIds, selectedSourceIds, sources }: SourcePanelProps) {
  return (
    <section className="panel source-panel" aria-labelledby="sources-title">
      <div className="panel-title">
        <div>
          <p className="eyebrow">Evidence</p>
          <h2 id="sources-title">Sources</h2>
        </div>
        <span className="panel-count">{sources.length}</span>
      </div>

      {sources.length === 0 ? (
        <p className="muted">No sources returned.</p>
      ) : (
        <div className="source-list">
          {sources.map((source) => {
            const highlighted =
              highlightedSourceIds.includes(source.id) || selectedSourceIds.includes(source.id);
            const host = source.publisher || hostFromUrl(source.url);
            return (
              <article
                className={highlighted ? "source-card highlighted" : "source-card"}
                id={`source-${source.id}`}
                key={source.id}
              >
                <div className="source-card-head">
                  <Badge tone={sourceTypeTone(source.source_type)}>
                    <FileText size={13} />
                    {readableLabel(source.source_type)}
                  </Badge>
                  {source.url && (
                    <a href={source.url} rel="noreferrer" target="_blank" title={`Open ${source.title}`}>
                      <ExternalLink size={15} />
                    </a>
                  )}
                </div>
                <h3>{source.title}</h3>
                {source.source_type === "image" ? (
                  <ImageSourceContent source={source} />
                ) : (
                  <p>{source.snippet}</p>
                )}
                <SourceRoleBadge category={source.source_category} role={source.source_role} />
                <div className="source-meta">
                  {host && <span>{host}</span>}
                  <ProviderSummary source={source} />
                  {typeof source.relevance_score === "number" && (
                    <span>{source.relevance_score.toFixed(2)} relevance</span>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}

function ProviderSummary({ source }: { source: Evidence }) {
  const providers = source.providers.length > 0 ? source.providers : providerList(source.provider);
  if (providers.length === 0) return null;

  return (
    <span>
      {providers.join(" + ")}
      {source.provider_result_count > 1 && ` · ${source.provider_result_count} providers`}
    </span>
  );
}

function ImageSourceContent({ source }: { source: Evidence }) {
  const content = parseImageSourceContent(source.content || source.snippet);

  if (!content.visibleText && !content.visualDescription && !content.imageType) {
    return <p>{source.snippet}</p>;
  }

  return (
    <div className="image-source-content">
      {content.imageType && (
        <div className="image-source-block compact">
          <strong>Image type</strong>
          <span>{content.imageType}</span>
        </div>
      )}
      {content.visibleText && (
        <div className="image-source-block">
          <strong>Extracted text</strong>
          <p>{content.visibleText}</p>
        </div>
      )}
      {content.visualDescription && (
        <div className="image-source-block">
          <strong>Visual description</strong>
          <p>{content.visualDescription}</p>
        </div>
      )}
    </div>
  );
}

function parseImageSourceContent(content: string) {
  return {
    imageType: extractSection(content, "Image type", "Visible text"),
    visibleText: extractSection(content, "Visible text", "Visual description"),
    visualDescription: extractSection(content, "Visual description")
  };
}

function extractSection(content: string, startLabel: string, endLabel?: string) {
  const startToken = `${startLabel}:`;
  const start = content.indexOf(startToken);
  if (start === -1) return "";

  const valueStart = start + startToken.length;
  const end = endLabel ? content.indexOf(`${endLabel}:`, valueStart) : -1;
  return content.slice(valueStart, end === -1 ? undefined : end).trim();
}

function providerList(provider: string | null) {
  if (!provider) return [];
  return provider
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
}
