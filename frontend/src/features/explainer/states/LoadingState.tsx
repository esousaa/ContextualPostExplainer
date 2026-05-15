import { Check, Circle, Loader2, X } from "lucide-react";
import { useEffect, useState } from "react";

import { formatSeconds } from "../../../shared/utils/date";
import { activeStepStartedAt, getPipelineStepStatus, PIPELINE_STEPS } from "../progress";
import type { LiveProgressState, PipelineStepStatus } from "../types";

function StepIcon({ status }: { status: PipelineStepStatus }) {
  if (status === "completed") {
    return <Check size={12} strokeWidth={4} />;
  }

  if (status === "active") {
    return <Loader2 className="spin" size={13} />;
  }

  if (status === "failed") {
    return <X size={12} strokeWidth={4} />;
  }

  return <Circle size={10} />;
}

type LoadingStateProps = {
  progress: LiveProgressState;
};

export function LoadingState({ progress }: LoadingStateProps) {
  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      setNowMs(Date.now());
    }, 500);

    return () => window.clearInterval(intervalId);
  }, []);

  const startedAt = activeStepStartedAt(progress);
  const activeElapsedMs = startedAt ? Math.max(0, nowMs - Date.parse(startedAt)) : 0;

  return (
    <section className="state-panel loading-state" aria-live="polite">
      <Loader2 className="spin" size={26} />
      <h2>Running live analysis</h2>
      <div className="pipeline-list">
        {PIPELINE_STEPS.map((step) => {
          const status = getPipelineStepStatus(progress, step);

          return (
            <div className={`pipeline-step ${status}`} key={step}>
              <span className={`pipeline-icon ${status}`} aria-hidden="true">
                <StepIcon status={status} />
              </span>
              <span className="pipeline-step-copy">
                <span>{step}</span>
                {status === "active" && startedAt ? (
                  <small>{formatSeconds(activeElapsedMs)}</small>
                ) : null}
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
