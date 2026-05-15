import { CheckCircle2, Loader2 } from "lucide-react";

const steps = ["Fetching post", "Searching context", "Ranking evidence", "Generating explanation"];

export function LoadingState() {
  return (
    <section className="state-panel loading-state" aria-live="polite">
      <Loader2 className="spin" size={26} />
      <h2>Running live analysis</h2>
      <div className="pipeline-list">
        {steps.map((step) => (
          <div className="pipeline-step" key={step}>
            <CheckCircle2 size={16} />
            <span>{step}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
