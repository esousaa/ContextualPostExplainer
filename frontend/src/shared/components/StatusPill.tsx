import type { ReactNode } from "react";

type StatusPillProps = {
  children: ReactNode;
  icon?: ReactNode;
  tone?: "neutral" | "green" | "teal" | "amber" | "coral" | "blue";
};

export function StatusPill({ children, icon, tone = "neutral" }: StatusPillProps) {
  return (
    <span className={`status-pill ${tone}`}>
      {icon}
      {children}
    </span>
  );
}
