import { Clock3, FileText, Gauge, SearchCheck, ShieldCheck } from "lucide-react";

import { Badge } from "../../shared/components/Badge";
import { StatusPill } from "../../shared/components/StatusPill";
import { formatSeconds } from "../../shared/utils/date";
import { confidenceTone } from "./labels";
import { WarningList } from "./WarningList";
import type { ConfigStatus, ExplanationResponse } from "./types";

type QualityPanelProps = {
  response: ExplanationResponse | null;
  configStatus: ConfigStatus | null;
};

export function QualityPanel({ configStatus, response }: QualityPanelProps) {
  const citationCoverage = response ? coveragePercent(response) : 0;
  const provider = configStatus?.live_search?.provider ?? "not set";
  const configured = configStatus?.live_search?.configured ?? false;

  return (
    <aside className="panel quality-panel" aria-labelledby="quality-title">
      <div className="panel-title">
        <div>
          <p className="eyebrow">Run quality</p>
          <h2 id="quality-title">Status</h2>
        </div>
      </div>

      <div className="metric-list">
        <StatusPill icon={<SearchCheck size={15} />} tone={configured ? "green" : "amber"}>
          {provider} {configured ? "configured" : "not configured"}
        </StatusPill>
        <StatusPill icon={<ShieldCheck size={15} />} tone={response ? confidenceTone(response.confidence) : "neutral"}>
          {response?.confidence ?? "not run"}
        </StatusPill>
        <StatusPill icon={<FileText size={15} />} tone="blue">
          {response?.sources.length ?? 0} sources
        </StatusPill>
        <StatusPill icon={<Gauge size={15} />} tone={citationCoverage === 100 ? "green" : "amber"}>
          {citationCoverage}% citation coverage
        </StatusPill>
        <StatusPill icon={<Clock3 size={15} />} tone="neutral">
          {response ? formatSeconds(response.execution_time_ms) : "0.0s"}
        </StatusPill>
      </div>

      {response?.warnings.length ? (
        <>
          <h3>Warnings</h3>
          <WarningList warnings={response.warnings} />
        </>
      ) : (
        <Badge tone="green">No global warnings</Badge>
      )}
    </aside>
  );
}

function coveragePercent(response: ExplanationResponse) {
  if (response.explanation.length === 0) {
    return 0;
  }
  const cited = response.explanation.filter((bullet) => bullet.source_ids.length > 0).length;
  return Math.round((cited / response.explanation.length) * 100);
}
