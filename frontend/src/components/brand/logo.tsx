import { cn } from "@/lib/utils";

/**
 * Meridian's mark: a globe bisected by a line of longitude — literal to the
 * name, and reads clearly at both the 24px sidebar size and the larger
 * login-page size. A plain geometric SVG rather than a generic icon-font
 * glyph (Sparkles, etc.) so it doesn't read as a placeholder.
 */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={cn("text-primary-foreground", className)}
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.75" />
      <ellipse cx="12" cy="12" rx="4" ry="9" stroke="currentColor" strokeWidth="1.75" />
      <path d="M3 12h18" stroke="currentColor" strokeWidth="1.75" />
    </svg>
  );
}

export function Logo({
  className,
  markClassName,
  textClassName,
}: {
  className?: string;
  markClassName?: string;
  textClassName?: string;
}) {
  return (
    <span className={cn("flex items-center gap-2", className)}>
      <span
        className={cn(
          "flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-primary",
          markClassName,
        )}
      >
        <LogoMark className="h-3.5 w-3.5" />
      </span>
      <span className={cn("text-sm font-semibold tracking-tight", textClassName)}>Meridian</span>
    </span>
  );
}
