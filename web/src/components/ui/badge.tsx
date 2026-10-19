import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-sm border px-1.5 py-0.5 text-2xs font-medium leading-none",
  {
    variants: {
      variant: {
        subtle: "border-transparent bg-elevated text-muted",
        outline: "border-border bg-transparent text-muted",
        accent: "border-accent/25 bg-accent/10 text-accent",
        success: "border-success/25 bg-success/10 text-success",
        danger: "border-danger/25 bg-danger/10 text-danger",
      },
    },
    defaultVariants: { variant: "subtle" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}
