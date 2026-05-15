import type { ReactNode } from "react";

type BadgeProps = {
  children: ReactNode;
  tone?: "neutral" | "green" | "teal" | "amber" | "coral" | "blue";
  className?: string;
};

export function Badge({ children, className = "", tone = "neutral" }: BadgeProps) {
  return <span className={`badge ${tone} ${className}`.trim()}>{children}</span>;
}
