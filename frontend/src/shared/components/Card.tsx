import type { HTMLAttributes } from "react";

type CardProps = HTMLAttributes<HTMLElement> & {
  as?: "article" | "section" | "aside";
};

export function Card({ as: Component = "section", className = "", ...props }: CardProps) {
  return <Component className={`panel ${className}`.trim()} {...props} />;
}
