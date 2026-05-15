import { ShieldAlert } from "lucide-react";

import { WarningList } from "../WarningList";
import type { ExplanationResponse } from "../types";

type LowEvidenceStateProps = {
  response: ExplanationResponse;
};

export function LowEvidenceState({ response }: LowEvidenceStateProps) {
  return (
    <section className="state-panel low-evidence-state">
      <ShieldAlert size={26} />
      <h2>No reliable explanation generated</h2>
      <p>The backend returned zero bullets to avoid unsupported claims.</p>
      <WarningList warnings={response.warnings} />
    </section>
  );
}
