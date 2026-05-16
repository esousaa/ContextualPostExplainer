import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  Activity,
  ArrowLeft,
  BarChart3,
  Clock3,
  Database,
  FileText,
  Gauge,
  Search,
  ShieldCheck,
} from "lucide-react";

import { isAbortError, normalizeApiError } from "../../shared/api/errors";
import { Badge } from "../../shared/components/Badge";
import { formatSeconds } from "../../shared/utils/date";
import { getAnalysisOverview } from "./api";
import type { AnalysisAggregate, AnalysisOverview } from "./types";

type AnalysisPageProps = {
  onNavigate: (path: string) => void;
};

type Tone = "neutral" | "green" | "teal" | "amber" | "coral" | "blue";

type MetricCardData = {
  label: string;
  value: string;
  detail: string;
  tone: Tone;
  icon: ReactNode;
};

export function AnalysisPage({ onNavigate }: AnalysisPageProps) {
  const [overview, setOverview] = useState<AnalysisOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    getAnalysisOverview(controller.signal)
      .then((payload) => {
        setError(null);
        setOverview(payload);
      })
      .catch((unknownError) => {
        if (!isAbortError(unknownError)) {
          setError(normalizeApiError(unknownError).message);
        }
      })
      .finally(() => setIsLoading(false));
    return () => controller.abort();
  }, []);

  const providerCards = useMemo(
    () => (overview ? providerMetricCards(overview.provider_aggregates) : []),
    [overview],
  );
  const llmCards = useMemo(
    () => (overview ? llmMetricCards(overview.llm_aggregates) : []),
    [overview],
  );

  return (
    <main className="app-shell analysis-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">RapidCanvas case</p>
          <h1>Analysis</h1>
        </div>
        <nav className="app-nav" aria-label="Primary navigation">
          <button className="nav-button" onClick={() => onNavigate("/")} type="button">
            <ArrowLeft size={15} />
            Explain
          </button>
          <button className="nav-button active" onClick={() => onNavigate("/analysis")} type="button">
            <BarChart3 size={15} />
            Analysis
          </button>
          <button className="nav-button" onClick={() => onNavigate("/observability")} type="button">
            <Activity size={15} />
            Observability
          </button>
        </nav>
      </header>

      {error ? <p className="error-inline analysis-error">{error}</p> : null}
      {isLoading ? <LoadingAnalysisState /> : null}
      {!isLoading && !overview && !error ? <EmptyAnalysisState /> : null}
      {overview ? (
        <>
          <section className="analysis-summary-grid">
            <SummaryCard icon={<Database size={18} />} label="Runs analyzed" value={String(overview.total_runs)} />
            <SummaryCard icon={<FileText size={18} />} label="Unique URLs" value={String(overview.total_urls)} />
            <SummaryCard
              icon={<Search size={18} />}
              label="Search providers"
              value={String(overview.provider_aggregates.length)}
            />
            <SummaryCard
              icon={<BarChart3 size={18} />}
              label="LLM stacks"
              value={String(overview.llm_aggregates.length)}
            />
          </section>

          <ComparativeSection
            aggregates={overview.provider_aggregates}
            cards={providerCards}
            description="Compares retrieval quality, noise, overlap, and latency across search providers. The goal is to identify which strategy returns citable context with the lowest no explanation rate."
            primaryLabel="Provider"
            title="Search Provider"
            variant="provider"
          />

          <ComparativeSection
            aggregates={overview.llm_aggregates}
            cards={llmCards}
            description="Compares how each generation, judge, embedding, and vision stack turns retrieved context into stable, citable bullets with lower removal risk."
            primaryLabel="LLM stack"
            title="LLM"
            variant="llm"
          />
        </>
      ) : null}
    </main>
  );
}

function LoadingAnalysisState() {
  return (
    <section className="panel analysis-empty" aria-live="polite" aria-busy="true">
      <Database size={24} />
      <h2>Loading comparative artifacts…</h2>
      <p className="muted">Reading local run artifacts.</p>
    </section>
  );
}

function EmptyAnalysisState() {
  return (
    <section className="panel analysis-empty">
      <Database size={24} />
      <h2>No runs found</h2>
      <p className="muted">Run the explainer at least once to populate the Analysis page.</p>
    </section>
  );
}

function SummaryCard({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <article className="panel summary-card">
      <span className="summary-icon">{icon}</span>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
    </article>
  );
}

function ComparativeSection({
  aggregates,
  cards,
  description,
  primaryLabel,
  title,
  variant,
}: {
  aggregates: AnalysisAggregate[];
  cards: MetricCardData[];
  description: string;
  primaryLabel: string;
  title: string;
  variant: "provider" | "llm";
}) {
  return (
    <section className="analysis-deep-section">
      <div className="analysis-section-head">
        <div>
          <p className="eyebrow">Comparative indicator</p>
          <h2>{title}</h2>
          <p>{description}</p>
        </div>
        <Badge tone={aggregates.length > 1 ? "green" : "amber"}>
          {aggregates.length > 1 ? "comparable" : "needs more configs"}
        </Badge>
      </div>

      <div className="analysis-card-grid">
        {cards.map((card) => (
          <MetricInsightCard card={card} key={card.label} />
        ))}
      </div>

      <div className="analysis-chart-grid">
        <ChartPanel
          aggregates={aggregates}
          formatValue={(value) => `${value.toFixed(1)}%`}
          metric={(item) => noExplanationRate(item)}
          title="No explanation rate"
          tone="coral"
        />
        <ChartPanel
          aggregates={aggregates}
          formatValue={(value) => value.toFixed(2)}
          metric={(item) => item.avg_cited_source_count}
          title="Avg cited sources"
          tone="green"
        />
        <ChartPanel
          aggregates={aggregates}
          formatValue={(value) => value.toFixed(2)}
          metric={(item) =>
            variant === "provider"
              ? item.avg_search_provider_overlap_count
              : item.avg_warning_count
          }
          title={variant === "provider" ? "Avg provider overlap" : "Avg warnings"}
          tone={variant === "provider" ? "blue" : "amber"}
        />
        <ChartPanel
          aggregates={aggregates}
          formatValue={(value) => formatSeconds(value)}
          metric={(item) => item.avg_execution_time_ms}
          title="Avg execution time"
          tone="teal"
        />
      </div>

      <AnalysisReadout aggregates={aggregates} variant={variant} />
      <AggregateTable aggregates={aggregates} primaryLabel={primaryLabel} />
    </section>
  );
}

function MetricInsightCard({ card }: { card: MetricCardData }) {
  return (
    <article className={`metric-insight-card ${card.tone}`}>
      <span className="metric-insight-icon">{card.icon}</span>
      <div>
        <p>{card.label}</p>
        <strong>{card.value}</strong>
        <span>{card.detail}</span>
      </div>
    </article>
  );
}

function ChartPanel({
  aggregates,
  formatValue,
  metric,
  title,
  tone,
}: {
  aggregates: AnalysisAggregate[];
  formatValue: (value: number) => string;
  metric: (item: AnalysisAggregate) => number | null;
  title: string;
  tone: Tone;
}) {
  const values = aggregates.map((item) => Math.max(0, metric(item) ?? 0));
  const maxValue = Math.max(...values, 1);

  return (
    <article className="panel chart-panel">
      <h3>{title}</h3>
      <div className="bar-chart">
        {aggregates.map((item) => {
          const value = Math.max(0, metric(item) ?? 0);
          return (
            <div className="bar-row" key={item.key}>
              <span className="bar-label">{compactKey(item.key)}</span>
              <div className="bar-track">
                <span
                  className={`bar-fill ${tone}`}
                  style={{ width: `${Math.max(4, (value / maxValue) * 100)}%` }}
                />
              </div>
              <strong>{formatValue(value)}</strong>
            </div>
          );
        })}
      </div>
    </article>
  );
}

function AnalysisReadout({
  aggregates,
  variant,
}: {
  aggregates: AnalysisAggregate[];
  variant: "provider" | "llm";
}) {
  const reliability = bestBy(aggregates, noExplanationRate, "asc");
  const coverage = bestBy(aggregates, (item) => item.avg_cited_source_count, "desc");
  const speed = bestBy(aggregates, (item) => item.avg_execution_time_ms, "asc");
  const overlap = bestBy(aggregates, (item) => item.avg_search_provider_overlap_count, "desc");
  const warnings = bestBy(aggregates, (item) => item.avg_warning_count, "asc");

  return (
    <article className="panel analysis-readout">
      <div>
        <p className="eyebrow">Comparative reading</p>
        <h3>{variant === "provider" ? "Search Provider assessment" : "LLM assessment"}</h3>
      </div>
      <div className="readout-grid">
        <ReadoutItem
          label="Reliability"
          text={
            reliability
              ? `${reliability.key} has the lowest no explanation rate at ${noExplanationRate(reliability).toFixed(1)}%.`
              : "More runs are needed to evaluate reliability."
          }
        />
        <ReadoutItem
          label="Citation coverage proxy"
          text={
            coverage
              ? `${coverage.key} has the highest average cited-source count at ${numberValue(coverage.avg_cited_source_count)}.`
              : "Cited-source coverage is not available yet."
          }
        />
        <ReadoutItem
          label="Latency"
          text={
            speed
              ? `${speed.key} is fastest on average at ${durationValue(speed.avg_execution_time_ms)}.`
              : "Latency data is not available yet."
          }
        />
        <ReadoutItem
          label={variant === "provider" ? "Provider agreement" : "Warning pressure"}
          text={
            variant === "provider"
              ? overlap
                ? `${overlap.key} has the strongest provider-overlap signal at ${numberValue(overlap.avg_search_provider_overlap_count)}.`
                : "Provider overlap requires composite runs."
              : warnings
                ? `${warnings.key} has the lowest average warning count at ${numberValue(warnings.avg_warning_count)}.`
                : "Warning data is not available yet."
          }
        />
      </div>
    </article>
  );
}

function ReadoutItem({ label, text }: { label: string; text: string }) {
  return (
    <div className="readout-item">
      <span>{label}</span>
      <p>{text}</p>
    </div>
  );
}

function AggregateTable({ aggregates, primaryLabel }: { aggregates: AnalysisAggregate[]; primaryLabel: string }) {
  if (aggregates.length === 0) {
    return (
      <section className="panel analysis-table-panel">
        <p className="muted">No comparable runs found.</p>
      </section>
    );
  }

  return (
    <section className="panel analysis-table-panel">
      <div className="panel-title">
        <div>
          <p className="eyebrow">Detailed metrics</p>
          <h3>{primaryLabel}</h3>
        </div>
      </div>
      <div className="comparison-table-wrap">
        <table className="comparison-table">
          <thead>
            <tr>
              <th>{primaryLabel}</th>
              <th>Runs</th>
              <th>No explanation</th>
              <th>Success rate</th>
              <th>Avg bullets</th>
              <th>Avg cited</th>
              <th>Avg search results</th>
              <th>Avg overlap</th>
              <th>Avg warnings</th>
              <th>Avg time</th>
            </tr>
          </thead>
          <tbody>
            {aggregates.map((item) => (
              <tr key={item.key}>
                <td className="comparison-key">{item.key}</td>
                <td>{item.run_count}</td>
                <td>{item.no_explanation_count}</td>
                <td>{successRate(item).toFixed(1)}%</td>
                <td>{numberValue(item.avg_bullet_count)}</td>
                <td>{numberValue(item.avg_cited_source_count)}</td>
                <td>{numberValue(item.avg_search_results_received)}</td>
                <td>{numberValue(item.avg_search_provider_overlap_count)}</td>
                <td>{numberValue(item.avg_warning_count)}</td>
                <td>{durationValue(item.avg_execution_time_ms)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function providerMetricCards(aggregates: AnalysisAggregate[]): MetricCardData[] {
  const reliability = bestBy(aggregates, noExplanationRate, "asc");
  const coverage = bestBy(aggregates, (item) => item.avg_cited_source_count, "desc");
  const overlap = bestBy(aggregates, (item) => item.avg_search_provider_overlap_count, "desc");
  const speed = bestBy(aggregates, (item) => item.avg_execution_time_ms, "asc");

  return [
    {
      label: "Most reliable",
      value: reliability?.key ?? "n/a",
      detail: reliability ? `${noExplanationRate(reliability).toFixed(1)}% no explanation` : "needs runs",
      tone: "green",
      icon: <ShieldCheck size={18} />,
    },
    {
      label: "Best citation proxy",
      value: coverage?.key ?? "n/a",
      detail: coverage ? `${numberValue(coverage.avg_cited_source_count)} avg cited sources` : "needs runs",
      tone: "blue",
      icon: <FileText size={18} />,
    },
    {
      label: "Strongest overlap",
      value: overlap?.key ?? "n/a",
      detail: overlap ? `${numberValue(overlap.avg_search_provider_overlap_count)} avg shared sources` : "needs composite",
      tone: "teal",
      icon: <Search size={18} />,
    },
    {
      label: "Fastest provider",
      value: speed?.key ?? "n/a",
      detail: speed ? `${durationValue(speed.avg_execution_time_ms)} avg execution` : "needs timing",
      tone: "amber",
      icon: <Clock3 size={18} />,
    },
  ];
}

function llmMetricCards(aggregates: AnalysisAggregate[]): MetricCardData[] {
  const reliability = bestBy(aggregates, noExplanationRate, "asc");
  const bullets = bestBy(aggregates, (item) => item.avg_bullet_count, "desc");
  const warnings = bestBy(aggregates, (item) => item.avg_warning_count, "asc");
  const speed = bestBy(aggregates, (item) => item.avg_execution_time_ms, "asc");

  return [
    {
      label: "Most reliable stack",
      value: reliability ? compactKey(reliability.key) : "n/a",
      detail: reliability ? `${noExplanationRate(reliability).toFixed(1)}% no explanation` : "needs runs",
      tone: "green",
      icon: <ShieldCheck size={18} />,
    },
    {
      label: "Highest bullet yield",
      value: bullets ? compactKey(bullets.key) : "n/a",
      detail: bullets ? `${numberValue(bullets.avg_bullet_count)} avg bullets` : "needs runs",
      tone: "blue",
      icon: <BarChart3 size={18} />,
    },
    {
      label: "Lowest warning pressure",
      value: warnings ? compactKey(warnings.key) : "n/a",
      detail: warnings ? `${numberValue(warnings.avg_warning_count)} avg warnings` : "needs validation",
      tone: "teal",
      icon: <Gauge size={18} />,
    },
    {
      label: "Fastest stack",
      value: speed ? compactKey(speed.key) : "n/a",
      detail: speed ? `${durationValue(speed.avg_execution_time_ms)} avg execution` : "needs timing",
      tone: "amber",
      icon: <Clock3 size={18} />,
    },
  ];
}

function bestBy(
  aggregates: AnalysisAggregate[],
  metric: (item: AnalysisAggregate) => number | null,
  direction: "asc" | "desc",
): AnalysisAggregate | null {
  const candidates = aggregates.filter((item) => metric(item) !== null);
  if (candidates.length === 0) return null;
  return [...candidates].sort((left, right) => {
    const leftValue = metric(left) ?? 0;
    const rightValue = metric(right) ?? 0;
    return direction === "asc" ? leftValue - rightValue : rightValue - leftValue;
  })[0];
}

function noExplanationRate(item: AnalysisAggregate): number {
  return item.run_count > 0 ? (item.no_explanation_count / item.run_count) * 100 : 0;
}

function successRate(item: AnalysisAggregate): number {
  return item.run_count > 0 ? (item.completed_count / item.run_count) * 100 : 0;
}

function numberValue(value: number | null): string {
  return value === null ? "n/a" : value.toFixed(2);
}

function durationValue(value: number | null): string {
  return value === null ? "n/a" : formatSeconds(value);
}

function compactKey(value: string): string {
  if (!value.includes("|")) return value;
  const generation = value.match(/gen=([^|]+)/)?.[1]?.trim() ?? "unknown";
  const embedding = value.match(/embed=([^|]+)/)?.[1]?.trim() ?? "unknown";
  return `${generation} / ${embedding}`;
}
