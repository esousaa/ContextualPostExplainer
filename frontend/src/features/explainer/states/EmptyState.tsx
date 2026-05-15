import { ClipboardCheck } from "lucide-react";

export function EmptyState() {
  return (
    <section className="state-panel" aria-label="Empty state">
      <ClipboardCheck size={24} />
      <h2>Ready for analysis</h2>
      <p>The result will appear here after the backend returns cited context.</p>
    </section>
  );
}
