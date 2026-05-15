import { useEffect, useMemo, useState } from "react";
import { Clock3, FileText, ShieldCheck } from "lucide-react";

import { StatusPill } from "../../shared/components/StatusPill";
import { normalizeApiError } from "../../shared/api/errors";
import { formatSeconds } from "../../shared/utils/date";
import { confidenceTone } from "./labels";
import { getConfigStatus } from "./api";
import { ExplanationPanel } from "./ExplanationPanel";
import { PostPreview } from "./PostPreview";
import { QualityPanel } from "./QualityPanel";
import { SourcePanel } from "./SourcePanel";
import { UrlInputPanel } from "./UrlInputPanel";
import { useExplainPost } from "./useExplainPost";
import { EmptyState } from "./states/EmptyState";
import { ErrorState } from "./states/ErrorState";
import { LoadingState } from "./states/LoadingState";
import { LowEvidenceState } from "./states/LowEvidenceState";
import type { ConfigStatus } from "./types";

const EXAMPLE_URL = "https://bsky.app/profile/rbreich.bsky.social/post/3mltultyalm2v";

export function ExplainerPage() {
  const [url, setUrl] = useState(EXAMPLE_URL);
  const [highlightedSourceIds, setHighlightedSourceIds] = useState<string[]>([]);
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([]);
  const [configStatus, setConfigStatus] = useState<ConfigStatus | null>(null);
  const explainer = useExplainPost();

  useEffect(() => {
    const controller = new AbortController();
    getConfigStatus(controller.signal)
      .then(setConfigStatus)
      .catch((error) => {
        setConfigStatus({
          status: "invalid",
          error: normalizeApiError(error).message
        });
      });
    return () => controller.abort();
  }, []);

  const response = explainer.status === "success" ? explainer.data : null;
  const sourceById = useMemo(
    () => new Map(response?.sources.map((source) => [source.id, source]) ?? []),
    [response]
  );

  function handleSubmit() {
    setHighlightedSourceIds([]);
    setSelectedSourceIds([]);
    void explainer.submit(url);
  }

  function handleRetry() {
    handleSubmit();
  }

  function handleSelectSource(sourceId: string) {
    setSelectedSourceIds([sourceId]);
    document.getElementById(`source-${sourceId}`)?.scrollIntoView({
      block: "nearest",
      behavior: "smooth"
    });
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">RapidCanvas case</p>
          <h1>Contextual Post Explainer</h1>
        </div>
        <div className="status-strip" aria-label="Run summary">
          <StatusPill icon={<ShieldCheck size={15} />} tone={response ? confidenceTone(response.confidence) : "neutral"}>
            {response?.confidence ?? "not run"}
          </StatusPill>
          <StatusPill icon={<FileText size={15} />} tone="blue">
            {response?.sources.length ?? 0} sources
          </StatusPill>
          <StatusPill icon={<Clock3 size={15} />} tone="neutral">
            {response ? formatSeconds(response.execution_time_ms) : "0.0s"}
          </StatusPill>
        </div>
      </header>

      <section className="workbench-grid">
        <aside className="left-rail">
          <UrlInputPanel
            disabled={explainer.status === "loading"}
            exampleUrl={EXAMPLE_URL}
            onChange={setUrl}
            onSubmit={handleSubmit}
            value={url}
          />
          <PostPreview post={response?.post ?? null} />
          {explainer.status === "loading" && <LoadingState progress={explainer.progress} />}
          {explainer.status === "idle" && <EmptyState />}
          {explainer.status === "error" && <ErrorState error={explainer.error} onRetry={handleRetry} />}
        </aside>

        <section className="center-stage">
          {response?.explanation.length ? (
            <ExplanationPanel
              bullets={response.explanation}
              onFocusSources={setHighlightedSourceIds}
              onSelectSource={handleSelectSource}
              selectedSourceIds={selectedSourceIds}
              sourceById={sourceById}
            />
          ) : response ? (
            <LowEvidenceState response={response} />
          ) : (
            <section className="panel main-panel placeholder-panel">
              <p className="eyebrow">Explanation</p>
              <h2>No run selected</h2>
            </section>
          )}
        </section>

        <aside className="right-rail">
          <QualityPanel configStatus={configStatus} response={response} />
          <SourcePanel
            highlightedSourceIds={highlightedSourceIds}
            selectedSourceIds={selectedSourceIds}
            sources={response?.sources ?? []}
          />
        </aside>
      </section>
    </main>
  );
}
