import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  BarChart3,
  Clock3,
  Database,
  FileText,
  ListChecks,
  Search,
  ShieldCheck,
} from "lucide-react";

import { Badge } from "../../shared/components/Badge";
import { StatusPill } from "../../shared/components/StatusPill";
import { isAbortError, normalizeApiError } from "../../shared/api/errors";
import { formatDate, formatSeconds } from "../../shared/utils/date";
import { ClaimBadge } from "../explainer/ClaimBadge";
import { SourceRoleBadge } from "../explainer/SourceRoleBadge";
import { WarningList } from "../explainer/WarningList";
import { confidenceTone, readableLabel } from "../explainer/labels";
import { getRunDetail, getRuns } from "./api";
import type { RunDetail, RunStatus, RunSummary } from "./types";

type ObservabilityPageProps = {
  selectedRunId?: string | null;
  onNavigate: (path: string) => void;
};

type RunTab = "timeline" | "post" | "explanation" | "sources" | "queries" | "diagnostics" | "raw";
type Tone = "neutral" | "green" | "teal" | "amber" | "coral" | "blue";

const TABS: RunTab[] = ["timeline", "post", "explanation", "sources", "queries", "diagnostics", "raw"];

export function ObservabilityPage({ onNavigate, selectedRunId }: ObservabilityPageProps) {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [detail, setDetail] = useState<RunDetail | null>(null);
  const [activeTab, setActiveTab] = useState<RunTab>("timeline");
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<RunStatus | "all">("all");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getRuns(controller.signal)
      .then((payload) => {
        setError(null);
        setRuns(payload.runs);
        if (!selectedRunId && payload.runs[0]) {
          onNavigate(`/observability/${payload.runs[0].run_id}`);
        }
      })
      .catch((unknownError) => {
        if (!isAbortError(unknownError)) {
          setError(normalizeApiError(unknownError).message);
        }
      });
    return () => controller.abort();
  }, [onNavigate, selectedRunId]);

  useEffect(() => {
    if (!selectedRunId) {
      setDetail(null);
      return;
    }

    const controller = new AbortController();
    getRunDetail(selectedRunId, controller.signal)
      .then((payload) => {
        setError(null);
        setDetail(payload);
        setActiveTab("timeline");
      })
      .catch((unknownError) => {
        if (!isAbortError(unknownError)) {
          setError(normalizeApiError(unknownError).message);
        }
      });
    return () => controller.abort();
  }, [selectedRunId]);

  const filteredRuns = useMemo(
    () =>
      runs.filter((run) => {
        const searchable = `${run.run_id} ${run.input_url ?? ""} ${run.post_author ?? ""} ${run.post_text ?? ""}`.toLowerCase();
        const matchesSearch = searchable.includes(searchTerm.trim().toLowerCase());
        const matchesStatus = statusFilter === "all" || run.status === statusFilter;
        return matchesSearch && matchesStatus;
      }),
    [runs, searchTerm, statusFilter],
  );

  return (
    <main className="app-shell observability-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">RapidCanvas case</p>
          <h1>Observability</h1>
        </div>
        <nav className="app-nav" aria-label="Primary navigation">
          <button className="nav-button" onClick={() => onNavigate("/")} type="button">
            <ArrowLeft size={15} />
            Explain
          </button>
          <button className="nav-button" onClick={() => onNavigate("/analysis")} type="button">
            <BarChart3 size={15} />
            Analysis
          </button>
          <button className="nav-button active" onClick={() => onNavigate("/observability")} type="button">
            Observability
          </button>
        </nav>
      </header>

      <section className="observability-grid">
        <aside className="panel run-history-panel">
          <div className="panel-title">
            <div>
              <p className="eyebrow">Run history</p>
              <h2>Runs</h2>
            </div>
            <span className="panel-count">{filteredRuns.length}</span>
          </div>

          <div className="run-filters">
            <label className="search-box">
              <Search size={15} />
              <input
                onChange={(event) => setSearchTerm(event.target.value)}
                placeholder="Search URL, run id, author"
                value={searchTerm}
              />
            </label>
            <select onChange={(event) => setStatusFilter(event.target.value as RunStatus | "all")} value={statusFilter}>
              <option value="all">All statuses</option>
              <option value="completed">Completed</option>
              <option value="no_explanation">No explanation</option>
              <option value="failed">Failed</option>
              <option value="unknown">Unknown</option>
            </select>
          </div>

          {error ? <p className="error-inline">{error}</p> : null}
          <div className="run-list">
            {filteredRuns.map((run) => (
              <RunHistoryItem
                active={run.run_id === selectedRunId}
                key={run.run_id}
                onSelect={() => onNavigate(`/observability/${run.run_id}`)}
                run={run}
              />
            ))}
            {filteredRuns.length === 0 ? <p className="muted">No runs found.</p> : null}
          </div>
        </aside>

        <section className="panel run-detail-panel">
          {detail ? (
            <>
              <RunDetailHeader detail={detail} />
              <div className="trace-tabs" role="tablist" aria-label="Run detail sections">
                {TABS.map((tab) => (
                  <button
                    className={tab === activeTab ? "trace-tab active" : "trace-tab"}
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    type="button"
                  >
                    {readableLabel(tab)}
                  </button>
                ))}
              </div>
              <RunTabContent detail={detail} tab={activeTab} />
            </>
          ) : (
            <div className="empty-detail">
              <Database size={28} />
              <h2>No run selected</h2>
              <p>Select a run from the history list to inspect its trace.</p>
            </div>
          )}
        </section>
      </section>
    </main>
  );
}

function RunHistoryItem({
  active,
  onSelect,
  run,
}: {
  active: boolean;
  onSelect: () => void;
  run: RunSummary;
}) {
  return (
    <button className={active ? "run-row active" : "run-row"} onClick={onSelect} type="button">
      <span className="run-row-head">
        <strong>{run.run_id}</strong>
        <Badge tone={statusTone(run.status)}>{statusLabel(run.status)}</Badge>
      </span>
      <span className="run-row-url">{run.input_url ?? "No input URL"}</span>
      <span className="run-row-meta">
        {run.execution_time_ms !== null ? formatSeconds(run.execution_time_ms) : "n/a"}
        {" · "}
        {run.confidence ?? "no confidence"}
        {" · "}
        {run.bullet_count} bullets
      </span>
      <span className="run-row-meta">
        {run.cited_source_count} cited sources · {run.warning_count} warnings · {formatDate(run.generated_at)}
      </span>
    </button>
  );
}

function RunDetailHeader({ detail }: { detail: RunDetail }) {
  const summary = detail.summary;

  return (
    <div className="run-detail-head">
      <div>
        <p className="eyebrow">Selected run</p>
        <h2>{summary.run_id}</h2>
        <p className="muted">{summary.input_url}</p>
      </div>
      <div className="status-strip">
        <StatusPill icon={<ShieldCheck size={15} />} tone={runConfidenceTone(summary.confidence)}>
          {summary.confidence ?? "no confidence"}
        </StatusPill>
        <StatusPill icon={<ListChecks size={15} />} tone={statusTone(summary.status)}>
          {statusLabel(summary.status)}
        </StatusPill>
        <StatusPill icon={<Clock3 size={15} />} tone="neutral">
          {summary.execution_time_ms !== null ? formatSeconds(summary.execution_time_ms) : "n/a"}
        </StatusPill>
        <StatusPill icon={<FileText size={15} />} tone="blue">
          {summary.cited_source_count} cited
        </StatusPill>
      </div>
    </div>
  );
}

function RunTabContent({ detail, tab }: { detail: RunDetail; tab: RunTab }) {
  if (tab === "timeline") {
    return <TimelineTab detail={detail} />;
  }
  if (tab === "post") {
    return <PostTab detail={detail} />;
  }
  if (tab === "explanation") {
    return <ExplanationTab detail={detail} />;
  }
  if (tab === "sources") {
    return <SourcesTab detail={detail} />;
  }
  if (tab === "queries") {
    return <QueriesTab detail={detail} />;
  }
  if (tab === "diagnostics") {
    return <DiagnosticsTab detail={detail} />;
  }
  return <RawTab detail={detail} />;
}

function TimelineTab({ detail }: { detail: RunDetail }) {
  return (
    <div className="trace-section">
      {detail.timeline.map((item) => (
        <div className="timeline-row" key={item.node_name}>
          <span className={`timeline-dot ${item.status}`} />
          <div>
            <strong>{readableLabel(item.node_name)}</strong>
            <span>{item.step}</span>
          </div>
          <Badge tone={statusTone(item.status)}>{statusLabel(item.status)}</Badge>
          <span className="timeline-duration">
            {item.duration_ms !== null ? formatSeconds(item.duration_ms) : item.status === "completed" ? "n/a" : "open"}
          </span>
        </div>
      ))}
      {detail.error ? (
        <div className="trace-error">
          <AlertTriangle size={16} />
          <span>{String(detail.error.message ?? "Run failed.")}</span>
        </div>
      ) : null}
    </div>
  );
}

function PostTab({ detail }: { detail: RunDetail }) {
  const post = detail.post;
  if (!post) {
    return <p className="muted">No post payload was recorded for this run.</p>;
  }

  return (
    <div className="trace-section readable-block">
      <h3>@{post.author.handle}</h3>
      <p>{post.text || "No post text."}</p>
      <div className="post-facts">
        <span>{formatDate(post.created_at)}</span>
        <span>{post.images.length} images</span>
        <span>{post.links.length} links</span>
      </div>
      {post.images.map((image, index) => (
        <div className="image-source-block" key={`${image.url}-${index}`}>
          <strong>Image {index + 1}</strong>
          {image.ocr_text ? <p>OCR: {image.ocr_text}</p> : null}
          {image.description ? <p>Description: {image.description}</p> : null}
          {image.alt_text ? <p>Alt text: {image.alt_text}</p> : null}
        </div>
      ))}
    </div>
  );
}

function ExplanationTab({ detail }: { detail: RunDetail }) {
  const explanation = detail.response?.explanation ?? [];
  if (explanation.length === 0) {
    return (
      <div className="trace-section">
        <h3>No bullets generated</h3>
        <WarningList warnings={detail.response?.warnings ?? []} />
      </div>
    );
  }

  return (
    <div className="trace-section trace-bullet-list">
      {explanation.map((bullet, index) => (
        <article className="trace-bullet" key={`${bullet.text}-${index}`}>
          <div className="bullet-index">{index + 1}</div>
          <div>
            <div className="bullet-meta">
              <ClaimBadge value={bullet.claim_label} />
              <Badge tone={confidenceTone(bullet.confidence)}>{bullet.confidence}</Badge>
            </div>
            <p>{bullet.text}</p>
            <span className="muted">Sources: {bullet.source_ids.join(", ")}</span>
            <WarningList compact warnings={bullet.warnings} />
          </div>
        </article>
      ))}
    </div>
  );
}

function SourcesTab({ detail }: { detail: RunDetail }) {
  const sources = detail.sources.length ? detail.sources : detail.cited_sources;
  return (
    <div className="trace-section source-list">
      {sources.map((source) => (
        <article className="trace-source" key={source.id}>
          <div className="source-card-head">
            <Badge tone={source.source_type === "web" ? "blue" : "teal"}>{source.source_type}</Badge>
            <span className="muted">{source.relevance_score?.toFixed(2) ?? "unranked"}</span>
          </div>
          <h3>{source.title}</h3>
          <p>{source.snippet || source.content}</p>
          <div className="source-role-badges">
            <SourceRoleBadge category={source.source_category} role={source.source_role} />
          </div>
          <span className="source-meta">{source.publisher ?? source.provider ?? "unknown source"}</span>
        </article>
      ))}
    </div>
  );
}

function QueriesTab({ detail }: { detail: RunDetail }) {
  return (
    <div className="trace-section query-list">
      {detail.queries.map((query) => (
        <div className="query-row" key={query}>
          <Search size={15} />
          <span>{query}</span>
        </div>
      ))}
      {detail.queries.length === 0 ? <p className="muted">No queries recorded.</p> : null}
    </div>
  );
}

function DiagnosticsTab({ detail }: { detail: RunDetail }) {
  return (
    <div className="trace-section diagnostics-grid">
      <MetricCard label="Search results" value={metricValue(detail.metrics.search_results_received)} />
      <MetricCard label="Sources" value={String(detail.summary.source_count)} />
      <MetricCard label="Cited sources" value={String(detail.summary.cited_source_count)} />
      <MetricCard label="Warnings" value={String(detail.summary.warning_count)} />
      <pre className="json-block">{JSON.stringify(detail.metrics, null, 2)}</pre>
    </div>
  );
}

function RawTab({ detail }: { detail: RunDetail }) {
  return (
    <div className="trace-section">
      <pre className="json-block">{JSON.stringify(detail.raw, null, 2)}</pre>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function statusTone(status: RunStatus): Tone {
  if (status === "completed") {
    return "green";
  }
  if (status === "no_explanation") {
    return "amber";
  }
  if (status === "failed") {
    return "coral";
  }
  return "neutral";
}

function statusLabel(status: RunStatus): string {
  if (status === "no_explanation") {
    return "no explanation";
  }
  return status;
}

function runConfidenceTone(confidence: string | null): Tone {
  if (confidence === "high") {
    return "green";
  }
  if (confidence === "medium") {
    return "amber";
  }
  if (confidence === "low") {
    return "coral";
  }
  return "neutral";
}

function metricValue(value: unknown): string {
  return typeof value === "number" || typeof value === "string" ? String(value) : "n/a";
}
